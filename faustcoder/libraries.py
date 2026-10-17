"""Pinned faustlibraries tree for the compiler harness.

The tree is commit ``2edec0537f53`` (ADR-0004 / T05). It is fetched on the
host by ``scripts/fetch-faustlibraries.sh`` and checked against
``FAUSTLIBRARIES_TREE_SHA256`` before any compile. The sandboxed worker
never downloads it. It only reads the directory Python passes in.

The canonical hash covers every regular ``*.lib`` file in that checkout.
Paths are relative and sorted. Each entry is the UTF-8 path, a newline, an
8-byte big-endian length, and the file bytes. A symlink ``.lib`` is refused.
Other files in the checkout, including the ``formalisation`` symlink, are
not part of the hash and are not staged.

Faust's own install copies ``old/*.lib`` and ``dx7/*.lib`` to the top of
the share directory. ``stdfaust.lib`` imports ``dx7.lib`` by that flat name,
and ``sf.lib`` imports ``old/effect.lib`` by its repo path. The share
directory keeps both layouts. The hash is of the checkout, not of the
duplicated flat copies.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from faustcoder.sandbox import SandboxError

FAUSTLIBRARIES_COMMIT = "2edec0537f53"
FAUSTLIBRARIES_COMMIT_FULL = "2edec0537f536eaa130d42c354884d7db971663c"
FAUSTLIBRARIES_VERSION = "2.80.0"
# sha256 of the canonical *.lib tree at FAUSTLIBRARIES_COMMIT.
FAUSTLIBRARIES_TREE_SHA256 = "edf8f43966942ec96ec2e46341af49454c311586a62879b430687c9ffd434173"
_VERSION = re.compile(
    rb"version\s*=\s*(\d+),\s*//\s*MAJOR version when we make incompatible API changes,\s*"
    rb"(\d+),\s*//\s*MINOR version when we add functionality in a backwards compatible manner,\s*"
    rb"(\d+);\s*//\s*PATCH version"
)
_FLAT_DIRS = frozenset({"old", "dx7"})
_LOCK = threading.Lock()
_TREES: dict[str, "LibraryTree"] = {}
_SHARES: dict[str, Path] = {}


@dataclass(frozen=True)
class LibraryTree:
    """One verified faustlibraries checkout."""

    root: Path
    commit: str
    version: str
    sha256: str


def library_root() -> Path:
    """Return the checkout that compiles are staged from.

    ``FAUSTCODER_LIBRARIES`` overrides the default
    ``faust/libraries/<commit>`` directory. The sandbox does not read this
    variable; Python resolves the path and passes it on the command line.
    """
    override = os.environ.get("FAUSTCODER_LIBRARIES")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parent.parent / "faust" / "libraries" / FAUSTLIBRARIES_COMMIT


def canonical_tree_sha256(root: Path) -> str:
    """Hash the ``*.lib`` files under ``root``.

    One changed library byte changes this digest. The digest is the value
    recorded in ``environment_digest``.
    """
    if not root.is_dir():
        raise SandboxError(f"faustlibraries tree is not a directory: {root}")
    files: list[tuple[str, bytes]] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            if path.suffix == ".lib":
                raise SandboxError(f"faustlibraries tree contains a symlink: {path}")
            continue
        if path.is_file() and path.suffix == ".lib":
            files.append((path.relative_to(root).as_posix(), path.read_bytes()))
    chunks: list[bytes] = []
    for rel, data in sorted(files):
        chunks.append(rel.encode("utf-8") + b"\n" + len(data).to_bytes(8, "big") + data)
    return hashlib.sha256(b"".join(chunks)).hexdigest()


def require_library_tree() -> LibraryTree:
    """Return the pinned tree, or raise when it is missing or mismatched."""
    root = library_root()
    key = str(root)
    with _LOCK:
        cached = _TREES.get(key)
    if cached is not None:
        return cached
    if not root.is_dir():
        raise SandboxError(
            "pinned faustlibraries tree is missing; run scripts/fetch-faustlibraries.sh"
        )
    digest = canonical_tree_sha256(root)
    if digest != FAUSTLIBRARIES_TREE_SHA256:
        raise SandboxError(
            "pinned faustlibraries tree sha256 does not match "
            f"{FAUSTLIBRARIES_COMMIT}: {digest}"
        )
    version = _version_of(root / "version.lib")
    if version != FAUSTLIBRARIES_VERSION:
        raise SandboxError(
            f"pinned version.lib declares {version}, expected {FAUSTLIBRARIES_VERSION}"
        )
    tree = LibraryTree(
        root=root,
        commit=FAUSTLIBRARIES_COMMIT,
        version=version,
        sha256=digest,
    )
    with _LOCK:
        _TREES[key] = tree
    return tree


def share_directory(tree: LibraryTree | None = None) -> Path:
    """Return the host directory mounted at ``/usr/share/faust``.

    Native Faust receives this path as ``-I``. The worker reads it and
    copies it into the Emscripten filesystem. The path is not part of the
    receipt.
    """
    resolved = tree or require_library_tree()
    key = str(resolved.root)
    with _LOCK:
        cached = _SHARES.get(key)
    if cached is not None and (cached / ".tree-sha256").is_file():
        return cached
    dest = resolved.root.parent / f"share-{resolved.commit}"
    stamp = dest / ".tree-sha256"
    if stamp.is_file() and stamp.read_text(encoding="ascii").strip() == resolved.sha256:
        with _LOCK:
            _SHARES[key] = dest
        return dest
    temporary = Path(tempfile.mkdtemp(prefix="faustcoder-share-", dir=resolved.root.parent))
    try:
        for rel, source in _share_files(resolved.root):
            target = temporary / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        (temporary / ".tree-sha256").write_text(resolved.sha256 + "\n", encoding="ascii")
        if dest.exists():
            shutil.rmtree(dest)
        temporary.rename(dest)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    with _LOCK:
        _SHARES[key] = dest
    return dest


def _share_files(root: Path) -> list[tuple[str, Path]]:
    mapping: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file() or path.suffix != ".lib":
            continue
        rel = path.relative_to(root).as_posix()
        mapping[rel] = path
        parts = rel.split("/")
        if len(parts) == 2 and parts[0] in _FLAT_DIRS:
            flat = parts[1]
            previous = mapping.get(flat)
            if previous is not None and previous != path:
                raise SandboxError(f"faustlibraries install path collides: {flat}")
            mapping[flat] = path
    return sorted(mapping.items())


def _version_of(path: Path) -> str:
    if not path.is_file():
        raise SandboxError("pinned version.lib is missing")
    match = _VERSION.search(path.read_bytes())
    if match is None:
        raise SandboxError("pinned version.lib does not declare vl.version")
    return ".".join(part.decode("ascii") for part in match.groups())


def main() -> None:
    tree = require_library_tree()
    print(f"{tree.sha256}  {tree.root}")


if __name__ == "__main__":
    main()

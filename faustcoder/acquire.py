"""Fetch one pinned git blob and verify its bytes (task T06).

Acquisition reads a full 40-hex commit and a git blob sha. A branch
name, a tag name and a short hash are refused before any read. The
bytes are checked with the git blob id (40 hex sha1, or 64 hex sha256; the zero id is refused):

``sha1("blob {length}\\0" + bytes)``.

Two transports are implemented. ``GitFetcher`` uses local ``git
cat-file`` and checks that ``pin:path`` resolves to the claimed blob.
``GitHubRawFetcher`` uses ``https://raw.githubusercontent.com`` at that
commit and path, refuses redirects, and leaves the blob-id check to
:func:`fetch_verified`. Neither transport accepts a mutable ref.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from faustcoder.errors import AcquireError

COMMIT_RE_TEXT = r"^[0-9a-f]{40}$"
MAX_BLOB_BYTES = 1_048_576
_GIT_TIMEOUT_SECONDS = 30
_BLOB_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_BLOB_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ZERO_BLOB = frozenset({"0" * 40, "0" * 64})


class BlobFetcher(Protocol):
    """Return the bytes at ``repo`` / ``pin`` / ``path``."""

    def fetch(self, repo: str, pin: str, path: str, blob_sha: str) -> bytes:
        """Fetch one object. Callers verify ``blob_sha`` themselves."""


def git_blob_sha1(data: bytes) -> str:
    """Return the lowercase git blob id of ``data``."""
    return _git_blob_digest(data, "sha1")


def git_blob_sha256(data: bytes) -> str:
    """Return the lowercase git sha256 blob id of ``data``."""
    return _git_blob_digest(data, "sha256")


def blob_id_algorithm(blob_sha: str) -> str:
    """Return ``sha1`` or ``sha256``. Reject a zero id and any other shape."""
    if (
        not isinstance(blob_sha, str)
        or blob_sha in _ZERO_BLOB
        or (
            _BLOB_SHA1.fullmatch(blob_sha) is None
            and _BLOB_SHA256.fullmatch(blob_sha) is None
        )
    ):
        raise AcquireError(
            "blob_sha must be 40 lowercase hex characters or 64 for sha256"
        )
    if _BLOB_SHA1.fullmatch(blob_sha):
        return "sha1"
    return "sha256"


def git_blob_id(data: bytes, blob_sha: str) -> str:
    """Hash ``data`` with the algorithm implied by ``blob_sha``."""
    if blob_id_algorithm(blob_sha) == "sha1":
        return git_blob_sha1(data)
    return git_blob_sha256(data)


def _git_blob_digest(data: bytes, algorithm: str) -> str:
    if not isinstance(data, (bytes, bytearray)):
        raise AcquireError("blob bytes are required")
    header = f"blob {len(data)}\0".encode("ascii")
    body = header + bytes(data)
    if algorithm == "sha1":
        return hashlib.sha1(body).hexdigest()
    if algorithm == "sha256":
        return hashlib.sha256(body).hexdigest()
    raise AcquireError("blob id algorithm is not sha1 or sha256")


def require_pin(pin: str) -> None:
    """Raise unless ``pin`` is a full lowercase commit sha."""
    if not isinstance(pin, str) or len(pin) != 40 or any(
        char not in "0123456789abcdef" for char in pin
    ):
        raise AcquireError("pin must be a full lowercase commit sha")


def fetch_verified(
    fetcher: BlobFetcher, repo: str, pin: str, path: str, blob_sha: str
) -> bytes:
    """Fetch ``path`` at ``pin`` and require the bytes to hash to ``blob_sha``."""
    require_pin(pin)
    blob_id_algorithm(blob_sha)
    try:
        data = fetcher.fetch(repo, pin, path, blob_sha)
    except AcquireError:
        raise
    except Exception as exc:
        raise AcquireError("fetch failed") from exc
    if not isinstance(data, (bytes, bytearray)):
        raise AcquireError("fetcher returned non-bytes")
    raw = bytes(data)
    if len(raw) > MAX_BLOB_BYTES:
        raise AcquireError("blob exceeds the size limit")
    if git_blob_id(raw, blob_sha) != blob_sha:
        raise AcquireError("bytes do not match blob_sha")
    return raw


class DirectoryFetcher:
    """Read ``root/owner/name/pin/path`` from a local fixture tree."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    def fetch(self, repo: str, pin: str, path: str, blob_sha: str) -> bytes:
        require_pin(pin)
        target = _fixture_path(self.root, repo, pin, path)
        if target.is_symlink() or not target.is_file():
            raise AcquireError("fixture blob is missing")
        return target.read_bytes()


class GitFetcher:
    """Read a blob from local clones with ``git cat-file``."""

    def __init__(self, roots: Mapping[str, Path | str]) -> None:
        self.roots = {repo: Path(path) for repo, path in roots.items()}

    def fetch(self, repo: str, pin: str, path: str, blob_sha: str) -> bytes:
        require_pin(pin)
        root = self.roots.get(repo)
        if root is None:
            raise AcquireError("no local git root for the repository")
        commit = _git_text(root, ["rev-parse", "--verify", f"{pin}^{{commit}}"])
        if commit != pin:
            raise AcquireError("pin is not that commit")
        found = _git_text(root, ["rev-parse", "--verify", f"{pin}:{path}"])
        if found != blob_sha:
            raise AcquireError("blob sha does not match the path at the pin")
        return _git(root, ["cat-file", "blob", blob_sha])


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(  # type: ignore[override]
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        raise AcquireError("redirect refused")


def _default_github_open(
    request: urllib.request.Request, timeout: float
) -> urllib.request.addinfourl:
    opener = urllib.request.build_opener(_NoRedirect)
    return opener.open(request, timeout=timeout)


class GitHubRawFetcher:
    """Fetch ``raw.githubusercontent.com/{repo}/{commit}/{path}``."""

    def __init__(
        self,
        opener: Callable[..., object] | None = None,
        timeout: float = 30,
    ) -> None:
        self._opener = opener or _default_github_open
        self.timeout = timeout

    def fetch(self, repo: str, pin: str, path: str, blob_sha: str) -> bytes:
        require_pin(pin)
        url = raw_url(repo, pin, path)
        request = urllib.request.Request(url, headers={"User-Agent": "faustcoder-snapshot"})
        try:
            response = self._opener(request, timeout=self.timeout)
        except AcquireError:
            raise
        except urllib.error.HTTPError as exc:
            raise AcquireError(f"github raw http {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise AcquireError("github raw request failed") from exc
        try:
            read = getattr(response, "read", None)
            if read is None:
                raise AcquireError("github raw response is empty")
            data = read(MAX_BLOB_BYTES + 1)
            if not isinstance(data, (bytes, bytearray)):
                raise AcquireError("github raw response is not bytes")
            return bytes(data)
        finally:
            close = getattr(response, "close", None)
            if close is not None:
                close()


def raw_url(repo: str, pin: str, path: str) -> str:
    """Return the raw URL for a commit and a relative path."""
    require_pin(pin)
    if not _safe_repo(repo) or not _safe_path(path):
        raise AcquireError("repository or path is not a pinned raw path")
    quoted = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    return f"https://raw.githubusercontent.com/{repo}/{pin}/{quoted}"


def _safe_repo(repo: str) -> bool:
    if not isinstance(repo, str) or repo.count("/") != 1:
        return False
    owner, name = repo.split("/")
    return bool(owner) and bool(name) and _segment(owner) and _segment(name)


def _safe_path(path: str) -> bool:
    if not isinstance(path, str) or not path or path.startswith(("/", "\\")):
        return False
    if "\\" in path or any(ord(char) < 32 for char in path):
        return False
    parts = path.split("/")
    return all(part not in ("", ".", "..") and _segment(part) for part in parts)


def _segment(part: str) -> bool:
    if any(char in ":?#%@" for char in part):
        return False
    return not part.startswith("-")


def _fixture_path(root: Path, repo: str, pin: str, path: str) -> Path:
    if not _safe_repo(repo) or not _safe_path(path):
        raise AcquireError("repository or path is not a fixture path")
    target = root.joinpath(*repo.split("/"), pin, *path.split("/")).resolve()
    if target != root and root not in target.parents:
        raise AcquireError("path escaped the fixture root")
    return target


def _git(root: Path, args: list[str]) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AcquireError("git failed") from exc
    if completed.returncode != 0:
        raise AcquireError("git failed")
    return completed.stdout


def _git_text(root: Path, args: list[str]) -> str:
    return _git(root, args).decode("ascii", errors="replace").strip()

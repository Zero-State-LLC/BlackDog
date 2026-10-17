"""Write-once, content-addressed artifact store on the local filesystem.

Layout: ``<root>/sha256/<artifact_id>.json`` plus
``<artifact_id>.envelope_digest``. The object file is the canonical
encoding of one envelope (see ``faustcoder.canonical``). The sidecar is
``sha256:`` plus the hex SHA-256 of those exact bytes. ``artifact_id``
remains the payload hash. Writes create a temporary file in the same
directory, ``fsync`` it, then hard-link it into place so a crash cannot
publish a partial object. An id that already exists is returned
unchanged when the bytes match and rejected when they do not. Existing
object bytes are never overwritten. A missing sidecar for an unchanged
object is written on ``put``. A sidecar that does not match is rejected
and left in place.

``put``, ``get`` and ``list`` reject parent cycles. Parents are
``content_digest`` values (``sha256:<hex>``) and must already exist.
``get`` and ``list`` require canonical object bytes, a matching envelope
digest, and a payload hash that matches the filename. ``exists`` reports
whether the object file or a symlink is present and does not verify
either digest.
"""

from __future__ import annotations

import copy
import os
import re
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from faustcoder.canonical import (
    CONTENT_DIGEST_RE,
    canonical_bytes,
    digest_hex,
    envelope_digest_for,
    loads_strict,
    parse_reference,
)
from faustcoder.errors import (
    ArtifactNotFoundError,
    CanonicalError,
    CycleError,
    DigestMismatchError,
    MissingParentError,
    MutationError,
    SchemaValidationError,
    TamperError,
)
from faustcoder.schemas import validate

_ENVELOPE_SCHEMA = "artifact-envelope.schema.json"
_OBJECT_NAME = re.compile(r"^([0-9a-f]{64})\.json$")
_WITNESS_NAME = re.compile(r"^([0-9a-f]{64})\.envelope_digest$")
_WHITE = 0
_GRAY = 1
_BLACK = 2


class ArtifactStore:
    """Filesystem artifact store rooted at one directory."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    def put(self, envelope: Mapping[str, Any]) -> str:
        """Store ``envelope`` and return its artifact id.

        Identical canonical bytes are an idempotent success. Different
        bytes for the same id raise MutationError and leave the stored
        file unchanged.
        """
        if not isinstance(envelope, dict):
            raise CanonicalError("envelope must be a JSON object")
        validate(envelope, _ENVELOPE_SCHEMA)
        digest = digest_hex(envelope["payload"])
        if (
            envelope["artifact_id"] != digest
            or envelope["content_digest"] != f"sha256:{digest}"
        ):
            raise DigestMismatchError(
                "artifact_id and content_digest must be the SHA-256 of "
                f"the canonical payload ({digest})"
            )
        data = canonical_bytes(envelope)
        self._assert_acyclic(digest, envelope["parents"])
        path = self.path_for(digest)
        if _present(path):
            self._require_same_bytes(path, data, digest)
            self._ensure_witness(digest, data)
            return digest
        self._atomic_create(path, data, digest)
        self._ensure_witness(digest, data)
        return digest

    def get(self, reference: str) -> dict[str, Any]:
        """Return a copy of the envelope, verifying the hash and the DAG."""
        artifact_id = parse_reference(reference)
        envelope = self._read_envelope(artifact_id)
        self._assert_acyclic(artifact_id, envelope["parents"])
        return copy.deepcopy(envelope)

    def exists(self, reference: str) -> bool:
        """Return whether a file or symlink is present for ``reference``.

        This does not verify the content digest. ``get`` does.
        """
        path = self.path_for(reference)
        return path.is_symlink() or path.is_file()

    def list(self) -> list[str]:
        """Return stored artifact ids, sorted, after verifying each one.

        Unexpected entries in the object directory raise TamperError.
        In-progress ``.tmp-`` files are ignored.
        """
        artifact_ids = self._scan_ids()
        loaded = [
            (artifact_id, self._read_envelope(artifact_id))
            for artifact_id in artifact_ids
        ]
        for artifact_id, envelope in loaded:
            self._assert_acyclic(artifact_id, envelope["parents"])
        return [artifact_id for artifact_id, _envelope in loaded]

    def path_for(self, reference: str) -> Path:
        """Return ``<root>/sha256/<artifact_id>.json`` without creating it."""
        artifact_id = parse_reference(reference)
        return self.root / "sha256" / f"{artifact_id}.json"

    def envelope_digest_path_for(self, reference: str) -> Path:
        """Return the sidecar path for an artifact reference."""
        artifact_id = parse_reference(reference)
        return self.root / "sha256" / f"{artifact_id}.envelope_digest"

    def _read_envelope(self, artifact_id: str) -> dict[str, Any]:
        path = self.path_for(artifact_id)
        if path.is_symlink():
            raise TamperError(artifact_id, "object path is a symlink")
        try:
            raw = _read_nofollow(path)
        except FileNotFoundError as exc:
            raise ArtifactNotFoundError(artifact_id) from exc
        try:
            text = raw.decode("utf-8")
            parsed = loads_strict(text)
        except (UnicodeDecodeError, CanonicalError) as exc:
            raise TamperError(
                artifact_id, "object is not strict canonical JSON"
            ) from exc
        if not isinstance(parsed, dict):
            raise TamperError(artifact_id, "object is not a JSON object")
        if raw != canonical_bytes(parsed):
            raise TamperError(artifact_id, "object bytes are not canonical")
        try:
            validate(parsed, _ENVELOPE_SCHEMA)
        except SchemaValidationError as exc:
            raise TamperError(artifact_id, "object failed envelope schema") from exc
        self._verify_witness(artifact_id, raw)
        payload_digest = digest_hex(parsed["payload"])
        if parsed.get("artifact_id") != payload_digest:
            raise TamperError(artifact_id, "artifact_id does not match payload")
        if parsed.get("content_digest") != f"sha256:{payload_digest}":
            raise TamperError(artifact_id, "content_digest does not match payload")
        if artifact_id != payload_digest:
            raise TamperError(artifact_id, "filename does not match payload digest")
        return parsed

    def _assert_acyclic(self, origin: str, parents: Sequence[str]) -> None:
        """Reject a parent walk that repeats a node or misses a parent.

        ``origin`` is treated as already on the stack so a self-parent is
        a cycle even though the new object is not stored yet. Nodes
        already known to be acyclic ancestors are not expanded twice
        (a diamond is not a cycle).
        """
        color: dict[str, int] = {origin: _GRAY}
        stack: list[tuple[str, list[str]]] = [(origin, list(parents))]
        while stack:
            _node, remaining = stack[-1]
            if not remaining:
                finished, _remaining = stack.pop()
                color[finished] = _BLACK
                continue
            parent_digest = remaining.pop(0)
            parent_id = _parent_id(parent_digest)
            state = color.get(parent_id, _WHITE)
            if state == _GRAY:
                raise CycleError(f"parent cycle involving sha256:{parent_id}")
            if state == _BLACK:
                continue
            try:
                parent = self._read_envelope(parent_id)
            except ArtifactNotFoundError as exc:
                raise MissingParentError(f"sha256:{parent_id}") from exc
            color[parent_id] = _GRAY
            stack.append((parent_id, list(parent["parents"])))

    def _scan_ids(self) -> list[str]:
        directory = self.root / "sha256"
        if not directory.exists() and not directory.is_symlink():
            return []
        if directory.is_symlink() or not directory.is_dir():
            raise TamperError("sha256", "object directory is not a real directory")
        artifact_ids: list[str] = []
        seen: set[str] = set()
        witnesses: list[str] = []
        for entry in directory.iterdir():
            name = entry.name
            if name.startswith("."):
                continue
            if entry.is_symlink():
                raise TamperError(name, "symlink in the object directory")
            object_match = _OBJECT_NAME.fullmatch(name)
            witness_match = _WITNESS_NAME.fullmatch(name)
            if object_match is not None and entry.is_file():
                artifact_ids.append(object_match.group(1))
                seen.add(object_match.group(1))
            elif witness_match is not None and entry.is_file():
                witnesses.append(witness_match.group(1))
            else:
                raise TamperError(name, "unexpected entry in the object directory")
        for witness_id in witnesses:
            if witness_id not in seen:
                raise TamperError(
                    witness_id, "envelope digest without an object"
                )
        artifact_ids.sort()
        return artifact_ids

    def _ensure_witness(self, artifact_id: str, envelope_bytes: bytes) -> None:
        path = self.envelope_digest_path_for(artifact_id)
        expected = envelope_digest_for(envelope_bytes).encode("ascii")
        if path.is_symlink():
            raise TamperError(artifact_id, "envelope digest path is a symlink")
        if not path.exists():
            self._atomic_create(path, expected, artifact_id, conflict="tamper")
            return
        self._require_witness_bytes(path, expected, artifact_id)

    def _verify_witness(self, artifact_id: str, envelope_bytes: bytes) -> None:
        path = self.envelope_digest_path_for(artifact_id)
        if path.is_symlink():
            raise TamperError(artifact_id, "envelope digest path is a symlink")
        try:
            stored = _read_nofollow(path)
        except FileNotFoundError as exc:
            raise TamperError(artifact_id, "missing envelope digest") from exc
        expected = envelope_digest_for(envelope_bytes).encode("ascii")
        if stored != expected:
            raise TamperError(artifact_id, "envelope digest mismatch")

    def _require_witness_bytes(
        self, path: Path, expected: bytes, artifact_id: str
    ) -> None:
        try:
            existing = _read_nofollow(path)
        except FileNotFoundError as exc:
            raise TamperError(artifact_id, "missing envelope digest") from exc
        if existing != expected:
            raise TamperError(artifact_id, "envelope digest mismatch")

    def _require_same_bytes(self, path: Path, data: bytes, artifact_id: str) -> None:
        if path.is_symlink():
            raise TamperError(artifact_id, "object path is a symlink")
        try:
            existing = _read_nofollow(path)
        except FileNotFoundError as exc:
            raise ArtifactNotFoundError(artifact_id) from exc
        if existing != data:
            raise MutationError(artifact_id)

    def _atomic_create(
        self,
        path: Path,
        data: bytes,
        artifact_id: str,
        *,
        conflict: str = "mutation",
    ) -> None:
        directory = path.parent
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / f".tmp-{os.getpid()}-{uuid.uuid4().hex}"
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o644,
        )
        try:
            try:
                _write_all(descriptor, data)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            try:
                os.link(temporary, path)
            except FileExistsError:
                if conflict == "tamper":
                    self._require_witness_bytes(path, data, artifact_id)
                else:
                    self._require_same_bytes(path, data, artifact_id)
                return
            _fsync_dir(directory)
        finally:
            temporary.unlink(missing_ok=True)


def _present(path: Path) -> bool:
    return path.is_symlink() or path.exists()


def _parent_id(content_digest: str) -> str:
    if CONTENT_DIGEST_RE.fullmatch(content_digest) is None:
        raise TamperError(content_digest, "parent is not a content digest")
    return content_digest.split(":", 1)[1]


def _read_nofollow(path: Path) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise TamperError(
            path.name, "object could not be read without following links"
        ) from exc
    try:
        chunks: list[bytes] = []
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            chunks.append(block)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = os.write(descriptor, view[offset:])
        if written == 0:
            raise OSError("short write while storing an artifact")
        offset += written


def _fsync_dir(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

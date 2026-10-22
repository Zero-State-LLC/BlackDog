"""Verified, externally reviewed byte ranges; not a Faust parser or rights grant.

The caller pins the canonical manifest digest independently of the document.
Review must establish complete function boundaries and dependency safety. Hashes
prove that the reviewed selection is unchanged, not that its semantics are safe.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from faustcoder.canonical import canonical_bytes, sha256_prefixed
from faustcoder.errors import InventoryError
from faustcoder.inventory import Unit

VERSION = "function-spans.v1"


def verify_manifest(
    document: Mapping[str, Any] | None,
    expected_digest: str | None,
    units: Sequence[Unit],
    inventory_digest: str,
    notice_digest: str,
) -> dict[str, dict[str, Any]]:
    """Require exactly one reviewed span per admitted function, before fetching."""
    functions = {u.unit_id: u for u in units if u.function}
    if document is None:
        if expected_digest is not None or functions:
            raise InventoryError(
                "function spans and an independently pinned digest are required"
            )
        return {}
    keys = {"schema_version", "inventory_digest", "notice_digest", "reviewer", "spans"}
    if not isinstance(document, Mapping) or set(document) != keys:
        raise InventoryError("invalid function span manifest fields")
    digest = sha256_prefixed(canonical_bytes(document))
    if expected_digest != digest:
        raise InventoryError("function span manifest digest mismatch")
    if document["schema_version"] != VERSION:
        raise InventoryError("unsupported function span manifest version")
    if (
        document["inventory_digest"] != inventory_digest
        or document["notice_digest"] != notice_digest
    ):
        raise InventoryError("function spans do not match inventory/notice pins")
    if not isinstance(document["reviewer"], str) or not document["reviewer"].strip():
        raise InventoryError("function span reviewer is required")
    if not isinstance(document["spans"], list):
        raise InventoryError("function spans must be an array")
    result: dict[str, dict[str, Any]] = {}
    ranges: dict[tuple[str, str, str, str], list[tuple[int, int]]] = {}
    fields = {
        "unit_id",
        "repo",
        "pin",
        "path",
        "blob_sha",
        "function",
        "start_byte",
        "end_byte",
        "sha256",
    }
    for row in document["spans"]:
        if not isinstance(row, Mapping) or set(row) != fields:
            raise InventoryError("invalid function span fields")
        uid = row["unit_id"]
        if not isinstance(uid, str) or uid not in functions or uid in result:
            raise InventoryError("unknown or duplicate function span unit")
        unit = functions[uid]
        if any(
            row[k] != getattr(unit, k)
            for k in ("repo", "pin", "path", "blob_sha", "function")
        ):
            raise InventoryError("function span identity mismatch")
        start, end = row["start_byte"], row["end_byte"]
        if type(start) is not int or type(end) is not int or start < 0 or end <= start:
            raise InventoryError("invalid function span byte range")
        value = row["sha256"]
        if (
            not isinstance(value, str)
            or len(value) != 71
            or not value.startswith("sha256:")
            or any(c not in "0123456789abcdef" for c in value[7:])
        ):
            raise InventoryError("invalid function span sha256")
        key = (unit.repo, unit.pin, unit.path, unit.blob_sha)
        previous = ranges.setdefault(key, [])
        if any(start < b and a < end for a, b in previous):
            raise InventoryError("overlapping function spans")
        previous.append((start, end))
        result[uid] = dict(row, manifest_digest=digest)
    if set(result) != set(functions):
        raise InventoryError("missing function spans")
    return result


def extract_span(raw: bytes, span: Mapping[str, Any]) -> bytes:
    """Select exact original bytes, refusing stale hashes and UTF-8 boundaries."""
    start, end = span["start_byte"], span["end_byte"]
    if end > len(raw):
        raise InventoryError("function span out of bounds")
    selected = raw[start:end]
    if sha256_prefixed(selected) != span["sha256"]:
        raise InventoryError("function span content digest mismatch")
    try:
        raw[:start].decode("utf-8")
        selected.decode("utf-8")
        raw[end:].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InventoryError("function span splits UTF-8 or source is invalid") from exc
    if not selected.strip():
        raise InventoryError("empty function span")
    return selected

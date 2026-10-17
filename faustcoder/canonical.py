"""Canonical JSON and content digests for FaustCoder artifacts.

Normative rules (V0.1)
----------------------
Canonical JSON is the UTF-8 encoding of one JSON value with no
insignificant whitespace. The encoder is ``json.dumps`` with
``sort_keys=True``, ``separators=(",", ":")``, ``ensure_ascii=False``
and ``allow_nan=False``, after the value is checked to contain only
JSON objects (string keys), arrays (lists), strings, finite numbers,
booleans and null.

1. Objects. Keys are sorted by Unicode code point, ascending. That
   order matches UTF-8 byte order. Duplicate keys are rejected on
   decode.
2. Arrays. Order is preserved. Tuples and other sequences are rejected
   rather than coerced to arrays.
3. Strings. Encoded as UTF-8 JSON strings. Solidus (U+002F) is not
   escaped. Characters U+0000 through U+001F are escaped. Non-ASCII
   characters are written as UTF-8, not as ``\\u`` escapes. Strings are
   not Unicode-normalized: code-point sequences that render alike are
   different values when their code points differ.
4. Numbers. Integers are base 10 with no leading zeros and no decimal
   point. Non-integers use the shortest round-trip form produced by
   ``json.dumps``. NaN and infinities are rejected. ``-0.0`` is
   distinct from ``0.0``. Booleans are ``true`` and ``false``, not
   ``1`` and ``0``.
5. Whitespace. The only separators are a comma between values and a
   colon between a key and its value. There is no trailing newline.

Digest scope
------------
``content_digest`` is SHA-256 over the canonical encoding of the
envelope field named ``payload``, and of that field only. ``artifact_id``
is the lowercase hexadecimal digest (64 characters). ``content_digest``
is the ASCII string ``sha256:`` followed by ``artifact_id``.

This is the minimal reading of data-model.md, which calls
``artifact_id`` a stable id and ``content_digest`` the ``sha256:<hex>``
of the canonical payload, without saying which bytes are hashed or that
the two fields are the same digest. Envelope fields other than
``payload`` (``parents``, ``producer``, ``created_at``,
``schema_version``) are not part of the id. The first stored envelope
for a payload wins; a later envelope with the same payload and
different bytes is a mutation and is rejected.

The file on disk is the canonical encoding of the whole envelope.

Envelope integrity
------------------
``artifact_id`` stays the payload hash. data-model.md does not define a
digest over the rest of the envelope, and the envelope schema rejects
extra fields. The store therefore writes a sidecar,
``<artifact_id>.envelope_digest``, whose contents are ``sha256:`` plus
the hex SHA-256 of the canonical envelope file bytes. Nothing is
excluded: the digest is not inside the hashed bytes. ``get`` and
``list`` recompute it and reject a mismatch, so a rewrite of
``producer``, ``created_at``, ``parents``, ``schema_version``,
``artifact_id``, ``content_digest`` or ``payload`` is detected when the
sidecar is left unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from typing import Any

from faustcoder.errors import CanonicalError, InvalidReferenceError

ARTIFACT_ID_RE = re.compile(r"^[0-9a-f]{64}$")
CONTENT_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_bytes(value: object) -> bytes:
    """Return the canonical UTF-8 encoding of a JSON value."""
    _reject_non_json(value)
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalError(str(exc)) from exc
    return text.encode("utf-8")


def digest_hex(payload: object) -> str:
    """Return the lowercase SHA-256 hex digest of a canonical payload."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def content_digest_for(payload: object) -> str:
    """Return ``sha256:<hex>`` for a canonical payload."""
    return f"sha256:{digest_hex(payload)}"


def sha256_prefixed(data: bytes) -> str:
    """Return ``sha256:<hex>`` of raw bytes, not of canonical JSON."""
    if not isinstance(data, (bytes, bytearray)):
        raise CanonicalError("sha256 input must be bytes")
    return "sha256:" + hashlib.sha256(bytes(data)).hexdigest()


def envelope_digest_for(envelope_bytes: bytes) -> str:
    """Return ``sha256:<hex>`` of the canonical envelope file bytes.

    This is not the artifact id. The id remains the payload hash.
    """
    if not isinstance(envelope_bytes, (bytes, bytearray)):
        raise CanonicalError("envelope digest input must be bytes")
    return "sha256:" + hashlib.sha256(bytes(envelope_bytes)).hexdigest()


def loads_strict(text: str) -> Any:
    """Parse JSON, rejecting duplicate object keys."""
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise CanonicalError(str(exc)) from exc


def parse_reference(reference: str) -> str:
    """Return the 64-char hex id from a bare id or ``sha256:`` digest."""
    if not isinstance(reference, str):
        raise InvalidReferenceError("artifact reference must be a string")
    if ARTIFACT_ID_RE.fullmatch(reference):
        return reference
    if CONTENT_DIGEST_RE.fullmatch(reference):
        return reference.split(":", 1)[1]
    raise InvalidReferenceError(
        "artifact reference must be 64 lowercase hex characters "
        "or sha256:<64 lowercase hex>"
    )


def build_envelope(
    *,
    schema_version: str,
    created_at: str,
    producer: str,
    parents: list[str] | tuple[str, ...],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build an envelope whose id and content_digest match ``payload``.

    Does not validate the envelope schema and does not check that
    parents exist. ``ArtifactStore.put`` does both. The returned
    envelope keeps the caller's payload object; mutating it after this
    call invalidates the digest.
    """
    if isinstance(payload, dict):
        payload_object: dict[str, Any] = payload
    else:
        raise CanonicalError("payload must be a JSON object")
    parent_list = list(parents)
    for parent in parent_list:
        if not isinstance(parent, str) or CONTENT_DIGEST_RE.fullmatch(parent) is None:
            raise InvalidReferenceError(
                "parents must be sha256:<64 lowercase hex> content digests"
            )
    digest = digest_hex(payload_object)
    return {
        "schema_version": schema_version,
        "artifact_id": digest,
        "content_digest": f"sha256:{digest}",
        "created_at": created_at,
        "producer": producer,
        "parents": parent_list,
        "payload": payload_object,
    }


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise CanonicalError(f"duplicate key: {key}")
        obj[key] = value
    return obj


def _reject_non_json(value: object) -> None:
    if value is None or isinstance(value, str):
        return
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalError("non-finite numbers are rejected")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalError("object keys must be strings")
            _reject_non_json(item)
        return
    if isinstance(value, list):
        for item in value:
            _reject_non_json(item)
        return
    raise CanonicalError(f"unsupported JSON type: {type(value).__name__}")

"""Deterministic Faust source normalization (task T06).

The transform is a pure function of the fetched bytes:

1. Reject UTF-16 BOMs and NUL bytes. Accept UTF-8, stripping a single
   leading UTF-8 BOM. Invalid UTF-8 is a transform error.
2. Convert CRLF and lone CR to LF. This is the only line-ending change.
3. Strip trailing U+0020 and U+0009 from each line. No other character
   is removed. Leading whitespace, blank lines and a final LF stay.
4. Do not Unicode-normalize. The canonical JSON rules in
   ``faustcoder.canonical`` treat distinct code points as distinct, and
   this step follows that.

The original digest is SHA-256 of the fetched file bytes, before any of
the steps above. The normalized digest is SHA-256 of the UTF-8 text
that remains. Function slices are inclusive line ranges on the
line-ending-normalized text, counted from 1, applied before trailing
whitespace is stripped. The range is inventory data. This module does
not parse Faust (spec §4.2).

A unit whose lines are all empty after stripping is a transform error.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from faustcoder.canonical import canonical_bytes, sha256_prefixed
from faustcoder.errors import NormalizeError

DIAGNOSTICS = frozenset(
    {
        "empty",
        "invalid-utf8",
        "utf-16-bom",
        "nul-byte",
        "slice-out-of-range",
        "slice-empty",
    }
)


@dataclass(frozen=True)
class LineSlice:
    """Inclusive 1-based line range on LF-normalized text."""

    name: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class NormalizedText:
    """Normalized unit text plus the two provenance digests."""

    text: str
    original_sha256: str
    normalized_sha256: str


def normalize_bytes(raw: bytes, line_slice: LineSlice | None = None) -> NormalizedText:
    """Return the normalized unit, or raise ``NormalizeError``."""
    if not isinstance(raw, (bytes, bytearray)):
        raise NormalizeError("invalid-utf8")
    raw_bytes = bytes(raw)
    original = sha256_prefixed(raw_bytes)
    if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise NormalizeError("utf-16-bom")
    if b"\x00" in raw_bytes:
        raise NormalizeError("nul-byte")
    body = raw_bytes[3:] if raw_bytes.startswith(b"\xef\xbb\xbf") else raw_bytes
    try:
        decoded = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise NormalizeError("invalid-utf8") from exc
    lines = decoded.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if line_slice is not None:
        if (
            line_slice.start_line < 1
            or line_slice.end_line < line_slice.start_line
            or line_slice.end_line > len(lines)
        ):
            raise NormalizeError("slice-out-of-range")
        lines = lines[line_slice.start_line - 1 : line_slice.end_line]
    stripped = [line.rstrip(" \t") for line in lines]
    if not any(line != "" for line in stripped):
        reason = "slice-empty" if line_slice is not None else "empty"
        raise NormalizeError(reason)
    text = "\n".join(stripped)
    return NormalizedText(
        text=text,
        original_sha256=original,
        normalized_sha256=sha256_prefixed(text.encode("utf-8")),
    )


@dataclass(frozen=True)
class NormalizedFile:
    """One file's normalization inside a unit."""

    role: str
    path: str
    blob_sha: str
    normalized: NormalizedText


@dataclass(frozen=True)
class NormalizedGroup:
    """A unit's files, kept together.

    A single file keeps that file's digests. A multi-file source hashes
    the canonical list of its members, primary first and imports by
    path. The joined text is what near-duplicate comparison sees. The
    group is one unit, not one cluster member per file.
    """

    text: str
    original_sha256: str
    normalized_sha256: str
    files: tuple[NormalizedFile, ...]


def combine_files(files: Sequence[NormalizedFile]) -> NormalizedGroup:
    """Group already-normalized files into one unit."""
    if not files:
        raise NormalizeError("empty")
    ordered = tuple(
        sorted(files, key=lambda item: (item.role != "primary", item.path))
    )
    if sum(item.role == "primary" for item in ordered) != 1:
        raise NormalizeError("empty")
    if len(ordered) == 1:
        only = ordered[0]
        return NormalizedGroup(
            text=only.normalized.text,
            original_sha256=only.normalized.original_sha256,
            normalized_sha256=only.normalized.normalized_sha256,
            files=ordered,
        )
    texts = [item.normalized.text for item in ordered]
    original_payload = [
        {
            "blob_sha": item.blob_sha,
            "original_sha256": item.normalized.original_sha256,
            "path": item.path,
            "role": item.role,
        }
        for item in ordered
    ]
    return NormalizedGroup(
        text="\n".join(texts),
        original_sha256=sha256_prefixed(canonical_bytes(original_payload)),
        normalized_sha256=sha256_prefixed(canonical_bytes(texts)),
        files=ordered,
    )

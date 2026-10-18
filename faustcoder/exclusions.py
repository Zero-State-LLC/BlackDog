"""Sources the wasm harness records instead of compiling.

These are Faust 2.88.0 examples. Their bytes are not vendored. The manifest
stores the path, the sha256 of the exact source, and the sha256 of that
source after T06 normalization. ``compile_source`` matches either digest
and raises :class:`CompilerExclusion` before the worker starts, so the
result is not a CompilerReceipt with ``diagnostic_class`` ``other``.

T06 normalization forces LF newlines and strips trailing spaces and tabs
on each line. Six of the eight raw hashes differ after that transform.
``physicalModeling/faust-stk/modalBar.dsp`` and ``SAM/effects/effects.dsp``
are unchanged. Keying on the normalized hash as well as the raw hash keeps
those six excluded once T06 has normalized them.

``stk_ffunction`` is the five ``examples/physicalModeling/faust-stk`` files
whose ``ffunction`` calls need STK C headers. The wasm build of libfaust
cannot link those headers.

``multi_file_ffunction`` is three of the thirteen multi-file examples. Sibling
imports resolve, and the entry still embeds ``ffunction(float fastpow2(float),
"fast_pow2.h", "")``, which the wasm backend rejects. They are the echo
entry, the effects echo entry, and the effects chain that components the
echo. The other ten multi-file examples compile.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

_MANIFEST = (
    Path(__file__).resolve().parent.parent / "faust" / "exclusions" / "wasm-examples-2.88.0.json"
)


class CompilerExclusion(Exception):
    """A known source was not compiled and was not graded as ``other``.

    An exclusion of model output is a failure. It is not a pass and not
    an ungraded refuge. ``grade_compiler_exclusion`` grades it at the
    ``parse_error`` rung (spec §23 A1). ``reward_disposition`` is
    ``failure``.
    """

    reward_disposition = "failure"

    def __init__(self, exclusion: "SourceExclusion") -> None:
        self.exclusion = exclusion
        super().__init__(f"excluded: {exclusion.path}: {exclusion.reason}")


@dataclass(frozen=True)
class SourceExclusion:
    """One source the wasm harness refuses to grade."""

    group: str
    path: str
    sha256: str
    normalized_sha256: str
    reason: str


def normalize_source(source: str) -> str:
    """Apply the T06 newline and trailing-whitespace normalization.

    CR and CRLF become LF. Spaces and tabs at the end of a line are
    removed. No other byte changes.
    """
    text = source.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip(" \t") for line in text.split("\n"))


def exclusions() -> tuple[SourceExclusion, ...]:
    """Return the recorded exclusions, in manifest order."""
    body = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    items: list[SourceExclusion] = []
    for group in ("stk_ffunction", "multi_file_ffunction"):
        for entry in body[group]:
            items.append(
                SourceExclusion(
                    group=group,
                    path=entry["path"],
                    sha256=entry["sha256"],
                    normalized_sha256=entry["normalized_sha256"],
                    reason=entry["reason"],
                )
            )
    return tuple(items)


def exclusion_for_source(source: str) -> SourceExclusion | None:
    """Return the exclusion matching ``source``, raw or T06-normalized."""
    raw = hashlib.sha256(source.encode("utf-8")).hexdigest()
    normalized = hashlib.sha256(normalize_source(source).encode("utf-8")).hexdigest()
    for item in exclusions():
        if item.sha256 == raw or item.normalized_sha256 == normalized:
            return item
    return None

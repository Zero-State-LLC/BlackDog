"""Sources the wasm harness records instead of compiling.

These are Faust 2.88.0 examples. Their bytes are not vendored. The manifest
stores the path and sha256. ``compile_source`` matches the source digest and
raises :class:`CompilerExclusion` before the worker starts, so the result is
not a CompilerReceipt with ``diagnostic_class`` ``other``.

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
    """A known source was not compiled and was not graded as ``other``."""

    def __init__(self, exclusion: "SourceExclusion") -> None:
        self.exclusion = exclusion
        super().__init__(f"excluded: {exclusion.path}: {exclusion.reason}")


@dataclass(frozen=True)
class SourceExclusion:
    """One source the wasm harness refuses to grade."""

    group: str
    path: str
    sha256: str
    reason: str


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
                    reason=entry["reason"],
                )
            )
    return tuple(items)


def exclusion_for_source(source: str) -> SourceExclusion | None:
    """Return the exclusion whose sha256 is ``source``, or None."""
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    for item in exclusions():
        if item.sha256 == digest:
            return item
    return None

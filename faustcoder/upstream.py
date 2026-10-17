"""Cleared blobs that stay cleared when a later copy is rejected.

Syfala commit ``c893f4ce0d9aaf15d11dc9cf4d2abe67ea830c3f`` (2024-02-13,
``dev/main`` #3) brought in copies of four upstream files. The syfala
row lists no blobs today. If it ever does, those four originals are the
upstream sources and are not quarantined for matching the copy.

The key is the upstream blob sha. This is an allowlist with a recorded
provenance, not a date or similarity heuristic. ``virtualAnalog.dsp``
and ``virtualAnalogForBrowser.dsp`` are the two SAM files contained by
syfala ``examples/faust/virtualAnalogForBrowser.dsp``.
"""

from __future__ import annotations

from dataclasses import dataclass

SYFALA_COMMIT = "c893f4ce0d9aaf15d11dc9cf4d2abe67ea830c3f"
COPIED_ON = "2024-02-13"


@dataclass(frozen=True)
class UpstreamOriginal:
    """One cleared blob that a later rejected tree copied."""

    blob_sha: str
    repo: str
    path: str
    copy_repo: str
    copy_path: str
    copied_on: str
    evidence: str


UPSTREAM_ORIGINALS: tuple[UpstreamOriginal, ...] = (
    UpstreamOriginal(
        blob_sha="e442c3d60a7bad0afa8de6bff4334923fbc627c0",
        repo="grame-cncm/faustplayground",
        path="public/faust-modules/combined/Birds.dsp",
        copy_repo="inria-emeraude/syfala",
        copy_path="examples/faust/birds.dsp",
        copied_on=COPIED_ON,
        evidence=SYFALA_COMMIT,
    ),
    UpstreamOriginal(
        blob_sha="ec6d4ffb0377f360d4a9c997df773865e22b1cc1",
        repo="grame-cncm/faust",
        path="examples/physicalModeling/old/harpe.dsp",
        copy_repo="inria-emeraude/syfala",
        copy_path="examples/faust/harp.dsp",
        copied_on=COPIED_ON,
        evidence=SYFALA_COMMIT,
    ),
    UpstreamOriginal(
        blob_sha="f14ca97f91375d8d84d59fd67564719e52124e8d",
        repo="grame-cncm/faust",
        path="examples/SAM/virtualAnalog/virtualAnalog.dsp",
        copy_repo="inria-emeraude/syfala",
        copy_path="examples/faust/virtualAnalogForBrowser.dsp",
        copied_on=COPIED_ON,
        evidence=SYFALA_COMMIT,
    ),
    UpstreamOriginal(
        blob_sha="33cbf6614a886e120b52d297b9a7868972741f9e",
        repo="grame-cncm/faust",
        path="examples/SAM/virtualAnalog/virtualAnalogForBrowser.dsp",
        copy_repo="inria-emeraude/syfala",
        copy_path="examples/faust/virtualAnalogForBrowser.dsp",
        copied_on=COPIED_ON,
        evidence=SYFALA_COMMIT,
    ),
)

UPSTREAM_BLOB_SHAS = frozenset(item.blob_sha for item in UPSTREAM_ORIGINALS)


def is_upstream_original(blob_sha: str) -> bool:
    """Return whether ``blob_sha`` is an allowlisted upstream original."""
    return blob_sha in UPSTREAM_BLOB_SHAS

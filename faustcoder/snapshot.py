"""Compile a deterministic dedup manifest and commit it to the artifact store.

Admission is a T05 ``rights-inventory.v1`` entry plus a matching
``notice-manifest.v1`` row. This module does not write ``rights_cleared``
or a RightsRecord, and it never uses the actor as ``reviewer``.

The manifest payload is a canonical function of the cleared units and
the fetched bytes. ``generated_at`` and ``created_at`` are not in it.
``split_frozen`` is not emitted. The record type is ``DedupManifest``.

Near-duplicate families share rights. Every member gets the intersection
of the family's flags. A family whose licenses differ is quarantined
with reason ``needs-human``.

``rights_rejected`` and ``needs_human`` units that name a blob are
fetched and clustered, and never emitted. A cleared unit in a family
with one of them is ``needs-human`` as well, including when the cleared
text is only an excerpt of the non-cleared text. Intersection with a
rejected member's empty flags is the same outcome: nothing is stored.
An allowlisted upstream original stays cleared only when every
non-cleared member of its family is that entry's recorded copy.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from faustcoder.acquire import BlobFetcher, fetch_verified, git_blob_id
from faustcoder.canonical import build_envelope
from faustcoder.compiler_gate import assert_corpus_compile_disabled
from faustcoder.dataset import PRODUCER, SCHEMA_VERSION, receipt_payload
from faustcoder.errors import AcquireError, InventoryError, NormalizeError
from faustcoder.inventory import (
    FFUNCTION_REASON,
    NEEDS_HUMAN_REASON,
    Corpus,
    InventoryExclusion,
    Notice,
    Unit,
    parse_corpus,
    source_uri,
)
from faustcoder.neardup import (
    CHAR_DENOMINATOR,
    CHAR_MIN_LENGTH,
    CHAR_N,
    CHAR_NUMERATOR,
    CONTAINMENT_DENOMINATOR,
    CONTAINMENT_NUMERATOR,
    TOKEN_FLOOR,
    TOKEN_FLOOR_STATUS,
    NGRAM_N,
    SHORT_SKELETON_DENOMINATOR,
    SHORT_SKELETON_NUMERATOR,
    THRESHOLD_DENOMINATOR,
    THRESHOLD_NUMERATOR,
    cluster_families,
    tokens,
)
from faustcoder.upstream import exempt_upstream_original
from faustcoder.normalize import normalize_bytes
from faustcoder.policy import ordered_flags
from faustcoder.store import ArtifactStore

_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_MANIFEST_VERSION = "t06-dedup-manifest.v1"


@dataclass
class _Norm:
    unit: Unit
    text: str | None
    original_sha256: str | None
    normalized_sha256: str | None
    failure: str | None
    exclusion: str | None


@dataclass
class _Member:
    norm: _Norm
    family: str
    admitted: tuple[str, ...]
    effective: tuple[str, ...]
    narrowed: bool
    leak: bool = False
    mixed: bool = False
    licenses: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompiledSnapshot:
    """Envelopes in parent order, manifest last."""

    envelopes: tuple[dict[str, Any], ...]
    manifest_digest: str
    unit_count: int
    excluded_count: int


def compile_snapshot(
    inventory: Mapping[str, Any],
    notice: Mapping[str, Any],
    fetcher: BlobFetcher,
    *,
    actor: str,
    created_at: str,
    compile_check: bool = False,
    sealed: Sequence[Mapping[str, str]] = (),
) -> CompiledSnapshot:
    """Build the manifest. Does not write a rights transition.

    ``compile_check`` defaults to false. Turning it on raises
    ``CompilerGateError`` and does not call the compiler.
    """
    assert_corpus_compile_disabled(compile_check)
    _check_run(actor, created_at)
    corpus = parse_corpus(inventory, notice)
    sealed_keys = _sealed_keys(sealed)
    units = tuple(_mark_sealed(unit, sealed_keys) for unit in corpus.units)
    blobs = _fetch(units + corpus.comparisons, fetcher)
    prepared = [_prepare(unit, blobs) for unit in units]
    comparable = [
        item
        for item in prepared
        if item.text is not None and item.exclusion is None and item.failure is None
    ]
    for item in prepared:
        if item.unit.holdout and item.failure is not None:
            raise NormalizeError(item.failure)
    compared = _comparison_norms(corpus.comparisons, blobs)
    excerpt_ids = [item.unit.unit_id for item in compared if item.text]
    excerpt_ids.extend(
        item.unit.unit_id for item in comparable if item.unit.holdout and item.text
    )
    families = cluster_families(
        [
            (item.unit.unit_id, item.text or "")
            for item in comparable + compared
            if item.text
        ],
        excerpt_ids,
    )
    sealed_ids = {item.unit.unit_id for item in comparable if item.unit.holdout}
    tainted = {families[item_id] for item_id in sealed_ids}
    members = _members(comparable, families, tainted)
    _narrow(members)
    _quarantine_uncleared_families(members, compared, families)
    excluded = _excluded(corpus, prepared, members, compared, families)
    return _assemble(
        members, excluded, comparable, prepared, families, corpus, actor, created_at
    )


def commit_snapshot(store: ArtifactStore, compiled: CompiledSnapshot) -> str:
    """Store ``compiled`` and return the manifest content digest."""
    for envelope in compiled.envelopes:
        store.put(envelope)
    return compiled.manifest_digest


def _mark_sealed(unit: Unit, sealed_keys: set[tuple[str, str, str, str]]) -> Unit:
    key = (unit.repo, unit.pin, unit.path, unit.function)
    if key not in sealed_keys:
        return unit
    return replace(unit, holdout=True)


def _sealed_keys(sealed: Sequence[Mapping[str, str]]) -> set[tuple[str, str, str, str]]:
    keys: set[tuple[str, str, str, str]] = set()
    for item in sealed:
        if not isinstance(item, Mapping):
            raise InventoryError("sealed unit must be an object")
        keys.add(
            (
                str(item.get("repo") or ""),
                str(item.get("commit") or item.get("pin") or ""),
                str(item.get("path") or ""),
                str(item.get("function") or ""),
            )
        )
    return keys


def _prepare(unit: Unit, blobs: dict[tuple[str, str, str, str], bytes]) -> _Norm:
    raw = blobs[(unit.repo, unit.pin, unit.path, unit.blob_sha)]
    # Hash the ingested bytes before any transform. T05 binds the claimed
    # blob id, not the text, so a tampered body with the same claim is refused.
    if git_blob_id(raw, unit.blob_sha) != unit.blob_sha:
        raise AcquireError("ingested bytes do not match blob_sha")
    try:
        normalized = normalize_bytes(raw, None)
    except NormalizeError as exc:
        return _Norm(unit, None, None, None, exc.reason, None)
    exclusion = FFUNCTION_REASON if FFUNCTION_REASON in tokens(normalized.text) else None
    return _Norm(
        unit,
        normalized.text,
        normalized.original_sha256,
        normalized.normalized_sha256,
        None,
        exclusion,
    )


def _comparison_norms(
    comparisons: tuple[Unit, ...], blobs: dict[tuple[str, str, str, str], bytes]
) -> list[_Norm]:
    """Normalize non-cleared blobs for clustering. Never a stored example.

    A failure here aborts the run. Skipping the blob would let a cleared
    near-copy through uncompared.
    """
    prepared: list[_Norm] = []
    for unit in comparisons:
        item = _prepare(unit, blobs)
        if item.failure is not None or item.text is None:
            raise NormalizeError(item.failure or "comparison unit did not normalize")
        prepared.append(replace(item, exclusion=None))
    return prepared


def _quarantine_uncleared_families(
    members: list[_Member], compared: list[_Norm], families: dict[str, str]
) -> None:
    """A family that contains a non-cleared member admits nothing.

    The rejected member's flags are empty, so the intersection is empty.
    The cleared members are ``needs-human`` and are not emitted. That
    includes a cleared file whose shingles cover at least half of a
    rejected text (reverse containment). An allowlisted upstream
    original stays cleared only when every non-cleared member of that
    family is the recorded copy.
    """
    peers_of: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for item in compared:
        peers_of[families[item.unit.unit_id]].append((item.unit.repo, item.unit.path))
    for member in members:
        peers = peers_of.get(member.family)
        if not peers:
            continue
        if exempt_upstream_original(member.norm.unit.blob_sha, peers):
            continue
        member.mixed = True
        member.effective = ()
        member.narrowed = True


def _members(
    comparable: list[_Norm], families: dict[str, str], tainted: set[str]
) -> list[_Member]:
    members: list[_Member] = []
    for item in comparable:
        if item.unit.holdout or item.text is None:
            continue
        family = families[item.unit.unit_id]
        members.append(
            _Member(
                norm=item,
                family=family,
                admitted=item.unit.eligible_for,
                effective=item.unit.eligible_for,
                narrowed=False,
                leak=family in tainted,
            )
        )
    return members


def _narrow(members: list[_Member]) -> None:
    """Apply one family's rights to every member of that family."""
    groups: dict[str, list[_Member]] = defaultdict(list)
    for member in members:
        groups[member.family].append(member)
    for group in groups.values():
        licenses = tuple(sorted({member.norm.unit.license for member in group}))
        if len(licenses) > 1:
            for member in group:
                member.mixed = True
                member.licenses = licenses
                member.effective = ()
                member.narrowed = True
            continue
        common: set[str] | None = None
        for member in group:
            flags = set(member.admitted)
            common = flags if common is None else common & flags
        effective = tuple(ordered_flags(common or set()))
        for member in group:
            member.effective = effective
            member.narrowed = list(effective) != list(member.admitted)


def _excluded(
    corpus: Corpus,
    prepared: list[_Norm],
    members: list[_Member],
    compared: list[_Norm],
    families: dict[str, str],
) -> list[dict[str, Any]]:
    comparison_family = {item.unit.unit_id: families[item.unit.unit_id] for item in compared}
    rows = []
    for item in corpus.excluded:
        row = _inventory_exclusion(item)
        if item.unit_id in comparison_family:
            row["duplicate_family"] = comparison_family[item.unit_id]
        rows.append(row)
    for item in prepared:
        if item.exclusion is not None and not item.unit.holdout:
            rows.append(_exclusion(item.unit, item.exclusion, None, "scan"))
        elif item.failure is not None and not item.unit.holdout:
            rows.append(_exclusion(item.unit, item.failure, None, "normalize"))
    for member in members:
        if member.mixed:
            rows.append(_exclusion(member.norm.unit, NEEDS_HUMAN_REASON, member.family, "dedup"))
        elif member.leak:
            rows.append(_exclusion(member.norm.unit, "holdout-family", member.family, "dedup"))
    return rows


def _assemble(
    members: list[_Member],
    excluded: list[dict[str, Any]],
    comparable: list[_Norm],
    prepared: list[_Norm],
    families: dict[str, str],
    corpus: Corpus,
    actor: str,
    created_at: str,
) -> CompiledSnapshot:
    envelopes: list[dict[str, Any]] = []
    example_digests: list[str] = []
    manifest_units: list[dict[str, Any]] = []
    for item in sorted(prepared, key=lambda row: row.unit.unit_id):
        if item.failure is None or item.unit.holdout:
            continue
        envelopes.extend(_failure_envelopes(item, actor, created_at))
    for member in sorted(members, key=lambda item: item.norm.unit.unit_id):
        if member.mixed:
            continue
        built = _unit_envelopes(member, actor, created_at)
        envelopes.extend(built)
        if member.leak:
            continue
        example = next(
            item for item in built if item["payload"].get("record_type") == "Example"
        )
        example_digests.append(example["content_digest"])
        manifest_units.append(_manifest_unit(member))
    excluded_rows = sorted(excluded, key=lambda row: row["unit_id"])
    manifest_payload = {
        "example_digests": sorted(example_digests),
        "excluded": excluded_rows,
        "inventory_digest": corpus.inventory_digest,
        "lifecycle": "DEDUPED",
        "near_duplicate": {
            "algorithm": "token-shingle-jaccard",
            "char_min_length": CHAR_MIN_LENGTH,
            "char_n": CHAR_N,
            "char_threshold": f"{CHAR_NUMERATOR}/{CHAR_DENOMINATOR}",
            "containment": f"{CONTAINMENT_NUMERATOR}/{CONTAINMENT_DENOMINATOR}",
            "min_tokens": TOKEN_FLOOR,
            "n": NGRAM_N,
            "short_skeleton_threshold": (
                f"{SHORT_SKELETON_NUMERATOR}/{SHORT_SKELETON_DENOMINATOR}"
            ),
            "threshold": f"{THRESHOLD_NUMERATOR}/{THRESHOLD_DENOMINATOR}",
            "token_floor": TOKEN_FLOOR,
            "token_floor_status": TOKEN_FLOOR_STATUS,
            "verbatim_run": TOKEN_FLOOR,
        },
        "normalization": {
            "encoding": "utf-8",
            "line_endings": "lf",
            "strip_trailing": "space-and-tab",
            "unicode_normalization": "none",
        },
        "notice_digest": corpus.notice_digest,
        "record_type": "DedupManifest",
        "sealed": _sealed_rows(comparable, families),
        "snapshot_version": _MANIFEST_VERSION,
        "split_frozen": False,
        "units": sorted(
            manifest_units,
            key=lambda row: (
                row["repo"],
                row["pin"],
                row["path"],
                row["function"],
                row["unit_id"],
            ),
        ),
    }
    parents = sorted(envelope["content_digest"] for envelope in envelopes)
    manifest = _envelope(manifest_payload, parents, created_at)
    envelopes.append(manifest)
    return CompiledSnapshot(
        envelopes=tuple(envelopes),
        manifest_digest=manifest["content_digest"],
        unit_count=len(manifest_units),
        excluded_count=len(excluded_rows),
    )


def _unit_envelopes(
    member: _Member, actor: str, created_at: str
) -> list[dict[str, Any]]:
    unit = member.norm.unit
    source = _envelope(_source_payload(unit), [], created_at)
    source_digest = source["content_digest"]
    example_payload = {
        "blob_sha": unit.blob_sha,
        "duplicate_family": member.family,
        "faust_source": member.norm.text,
        "function": unit.function,
        "normalized_sha256": member.norm.normalized_sha256,
        "original_sha256": member.norm.original_sha256,
        "record_type": "Example",
        "source_digest": source_digest,
        "unit_id": unit.unit_id,
    }
    example = _envelope(example_payload, [source_digest], created_at)
    example_digest = example["content_digest"]
    normalized_receipt = _receipt(
        actor=actor,
        timestamp=created_at,
        input_hashes=[source_digest, example_digest],
        from_state="RIGHTS_CLEARED",
        event="normalized",
        to_state="NORMALIZED",
        disposition="normalized",
        parents=[source_digest, example_digest],
    )
    if member.leak:
        event = "duplicate_or_leak_found"
        to_state = "QUARANTINED"
        disposition = f"excluded: conflicting family {member.family}"
    else:
        event = "dedup_passed"
        to_state = "DEDUPED"
        disposition = f"duplicate_family={member.family}"
    dedup_parents = [source_digest, example_digest, normalized_receipt["content_digest"]]
    dedup = _receipt(
        actor=actor,
        timestamp=created_at,
        input_hashes=dedup_parents,
        from_state="NORMALIZED",
        event=event,
        to_state=to_state,
        disposition=disposition,
        parents=dedup_parents,
    )
    return [source, example, normalized_receipt, dedup]


def _failure_envelopes(item: _Norm, actor: str, created_at: str) -> list[dict[str, Any]]:
    """Record a normalize failure without minting a rights clearance."""
    unit = item.unit
    source = _envelope(_source_payload(unit), [], created_at)
    source_digest = source["content_digest"]
    failed = _receipt(
        actor=actor,
        timestamp=created_at,
        input_hashes=[source_digest],
        from_state="RIGHTS_CLEARED",
        event="normalize_failed",
        to_state="QUARANTINED",
        disposition=f"normalize_failed: {item.failure}",
        parents=[source_digest],
    )
    return [source, failed]


def _manifest_unit(member: _Member) -> dict[str, Any]:
    unit = member.norm.unit
    return {
        "admitted_eligible_for": list(member.admitted),
        "attribution": unit.attribution,
        "blob_sha": unit.blob_sha,
        "duplicate_family": member.family,
        "eligible_for": list(member.effective),
        "entry_id": unit.entry_id,
        "evidence_label": unit.evidence_label,
        "function": unit.function,
        "impulse": unit.impulse,
        "license": unit.license,
        "normalized_sha256": member.norm.normalized_sha256,
        "notice": _notice_payload(unit.notice),
        "original_sha256": member.norm.original_sha256,
        "path": unit.path,
        "pin": unit.pin,
        "repo": unit.repo,
        "reviewer": unit.reviewer,
        "rights_narrowed": member.narrowed,
        "training_only": list(member.effective) == ["train"],
        "unit_id": unit.unit_id,
    }


def _sealed_rows(
    comparable: list[_Norm], families: dict[str, str]
) -> list[dict[str, Any]]:
    rows = []
    for item in comparable:
        if not item.unit.holdout or item.normalized_sha256 is None:
            continue
        rows.append(
            {
                "duplicate_family": families[item.unit.unit_id],
                "entry_id": item.unit.entry_id,
                "function": item.unit.function,
                "license": item.unit.license,
                "normalized_sha256": item.normalized_sha256,
                "path": item.unit.path,
                "pin": item.unit.pin,
                "repo": item.unit.repo,
                "unit_id": item.unit.unit_id,
            }
        )
    rows.sort(key=lambda row: row["unit_id"])
    return rows


def _inventory_exclusion(item: InventoryExclusion) -> dict[str, Any]:
    return {
        "duplicate_family": None,
        "entry_id": item.entry_id,
        "function": item.function,
        "origin": item.origin,
        "path": item.path,
        "pin": item.pin,
        "reason": item.reason,
        "repo": item.repo,
        "unit_id": item.unit_id,
    }


def _exclusion(
    unit: Unit, reason: str, family: str | None, origin: str
) -> dict[str, Any]:
    return {
        "duplicate_family": family,
        "entry_id": unit.entry_id,
        "function": unit.function,
        "origin": origin,
        "path": unit.path,
        "pin": unit.pin,
        "reason": reason,
        "repo": unit.repo,
        "unit_id": unit.unit_id,
    }


def _source_payload(unit: Unit) -> dict[str, Any]:
    """Content-bearing source fields. No ``retrieved_at`` and no actor."""
    return {
        "license_claim": unit.license,
        "record_type": "SourceRecord",
        "unit_id": unit.unit_id,
        "uri": source_uri(unit),
    }


def _notice_payload(notice: Notice | None) -> dict[str, str] | None:
    if notice is None:
        return None
    return {
        "blob_sha": notice.blob_sha,
        "copyright": notice.copyright,
        "function": notice.function,
        "license": notice.license,
        "path": notice.path,
    }


def _fetch(
    units: tuple[Unit, ...], fetcher: BlobFetcher
) -> dict[tuple[str, str, str, str], bytes]:
    cache: dict[tuple[str, str, str, str], bytes] = {}
    for unit in units:
        key = (unit.repo, unit.pin, unit.path, unit.blob_sha)
        if key not in cache:
            cache[key] = fetch_verified(
                fetcher, unit.repo, unit.pin, unit.path, unit.blob_sha
            )
    return cache


def _receipt(
    *,
    actor: str,
    timestamp: str,
    input_hashes: list[str],
    from_state: str,
    event: str,
    to_state: str,
    disposition: str,
    parents: list[str],
) -> dict[str, Any]:
    payload = receipt_payload(
        actor=actor,
        timestamp=timestamp,
        input_hashes=input_hashes,
        from_state=from_state,
        event=event,
        to_state=to_state,
        disposition=disposition,
    )
    return _envelope(payload, parents, timestamp)


def _envelope(
    payload: Mapping[str, Any], parents: list[str], created_at: str
) -> dict[str, Any]:
    return build_envelope(
        schema_version=SCHEMA_VERSION,
        created_at=created_at,
        producer=PRODUCER,
        parents=sorted(set(parents)),
        payload=dict(payload),
    )


def _check_run(actor: str, created_at: str) -> None:
    if (
        not isinstance(actor, str)
        or not actor.strip()
        or len(actor) > 120
        or any(ord(char) < 32 for char in actor)
    ):
        raise AcquireError("actor is missing")
    if not isinstance(created_at, str) or _TIME.fullmatch(created_at) is None:
        raise AcquireError("created_at must be a UTC RFC3339 timestamp")

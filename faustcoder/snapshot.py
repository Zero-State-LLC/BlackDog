"""Compile a deterministic dedup manifest and commit it to the artifact store.

The manifest payload is a canonical function of the inventory and the
fetched bytes. It does not include the run timestamp. Envelope
``created_at`` and receipt ``timestamp`` use the caller-supplied
``created_at``, so a second run with the same value stores identical
bytes. ``split_frozen`` is not emitted. The record type is
``DedupManifest`` and ``lifecycle`` stays ``DEDUPED``. Spec §7.1 writes
``DatasetSnapshot`` on the T07 freeze, together with the signed split.

Vendored units are fetched only to compare normalized hashes with the
named upstream unit. Sealed holdout units are fetched and compared in
memory. Their text is not stored. An acquired unit in the same
near-duplicate family is quarantined with ``duplicate_or_leak_found``.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from faustcoder.acquire import BlobFetcher, fetch_verified
from faustcoder.canonical import build_envelope
from faustcoder.compiler_gate import assert_corpus_compile_disabled
from faustcoder.dataset import PRODUCER, SCHEMA_VERSION, receipt_payload
from faustcoder.errors import AcquireError, InventoryError, NormalizeError
from faustcoder.inventory import (
    FFUNCTION_REASON,
    POLICY_ID,
    Notice,
    Unit,
    parse_inventory,
    source_uri,
)
from faustcoder.neardup import (
    MIN_TOKENS,
    NGRAM_N,
    THRESHOLD_DENOMINATOR,
    THRESHOLD_NUMERATOR,
    cluster_families,
    tokens,
)
from faustcoder.normalize import (
    LineSlice,
    NormalizedFile,
    NormalizedGroup,
    combine_files,
    normalize_bytes,
)
from faustcoder.policy import check_unit, ordered_flags
from faustcoder.store import ArtifactStore

_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_MANIFEST_VERSION = "t06-dedup-manifest.v1"


@dataclass
class _Norm:
    unit: Unit
    group: NormalizedGroup | None
    failure: str | None
    exclusion: str | None


@dataclass
class _Member:
    norm: _Norm
    family: str
    admitted: tuple[str, ...]
    effective: tuple[str, ...]
    narrowed: bool
    vendored: list[dict[str, Any]] = field(default_factory=list)
    leak: bool = False


@dataclass(frozen=True)
class CompiledSnapshot:
    """Envelopes in parent order, manifest last."""

    envelopes: tuple[dict[str, Any], ...]
    manifest_digest: str
    unit_count: int
    excluded_count: int


def compile_snapshot(
    document: Mapping[str, Any],
    fetcher: BlobFetcher,
    *,
    actor: str,
    created_at: str,
    compile_check: bool = False,
) -> CompiledSnapshot:
    """Build the manifest and its parent artifacts. Does not touch the store.

    ``compile_check`` defaults to false. Turning it on raises
    ``CompilerGateError`` and does not call the compiler. T03b has not
    staged the pinned faustlibraries into the harness, so a compiler
    receipt is not a signal for this corpus.
    """
    assert_corpus_compile_disabled(compile_check)
    _check_run(actor, created_at)
    units = parse_inventory(document)
    for unit in units:
        check_unit(unit)
    blobs = _fetch(units, fetcher)
    prepared = [_prepare(unit, blobs) for unit in units if unit.decision != "reject"]
    by_id = {item.unit.unit_id: item for item in prepared}
    comparable = [
        item
        for item in prepared
        if item.unit.decision != "vendored"
        and item.group is not None
        and item.exclusion is None
    ]
    for item in prepared:
        if item.unit.holdout and item.failure is not None:
            raise NormalizeError(item.failure)
    families = cluster_families(
        [
            (item.unit.unit_id, item.group.text)
            for item in comparable
            if item.group is not None
        ]
    )
    sealed_ids = {item.unit.unit_id for item in comparable if item.unit.holdout}
    tainted = {families[item_id] for item_id in sealed_ids}
    members = _members(comparable, families, tainted)
    _narrow(members)
    excluded = _excluded(units, prepared, members)
    _attach_vendored(prepared, by_id, members, excluded)
    return _assemble(members, excluded, comparable, prepared, families, actor, created_at)


def commit_snapshot(store: ArtifactStore, compiled: CompiledSnapshot) -> str:
    """Store ``compiled`` and return the manifest content digest."""
    for envelope in compiled.envelopes:
        store.put(envelope)
    return compiled.manifest_digest


def _prepare(unit: Unit, blobs: dict[tuple[str, str, str, str], bytes]) -> _Norm:
    line_slice = None
    if unit.slice is not None:
        line_slice = LineSlice(
            unit.slice.name, unit.slice.start_line, unit.slice.end_line
        )
    normalized_files: list[NormalizedFile] = []
    for member in unit.files:
        raw = blobs[(unit.repo, unit.pin, member.path, member.blob_sha)]
        try:
            normalized = normalize_bytes(raw, line_slice)
        except NormalizeError as exc:
            return _Norm(unit, None, exc.reason, None)
        normalized_files.append(
            NormalizedFile(
                role=member.role,
                path=member.path,
                blob_sha=member.blob_sha,
                normalized=normalized,
            )
        )
    group = combine_files(normalized_files)
    _require_import_references(unit, group)
    exclusion = FFUNCTION_REASON if _has_ffunction(group) else None
    return _Norm(unit, group, None, exclusion)


def _require_import_references(unit: Unit, group: NormalizedGroup) -> None:
    primary = next(item for item in group.files if item.role == "primary")
    for item in group.files:
        if item.role != "import":
            continue
        basename = item.path.rsplit("/", 1)[-1]
        if f'"{basename}"' not in primary.normalized.text:
            raise InventoryError(
                f"{unit.unit_id}: import {basename} is not named by the primary file"
            )


def _has_ffunction(group: NormalizedGroup) -> bool:
    return any(FFUNCTION_REASON in tokens(item.normalized.text) for item in group.files)


def _members(
    comparable: list[_Norm], families: dict[str, str], tainted: set[str]
) -> list[_Member]:
    members: list[_Member] = []
    for item in comparable:
        if item.unit.holdout or item.group is None:
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
    groups: dict[str, list[_Member]] = defaultdict(list)
    for member in members:
        if member.leak or member.norm.group is None:
            continue
        groups[member.norm.group.normalized_sha256].append(member)
    for group in groups.values():
        common: set[str] | None = None
        for member in group:
            flags = set(member.admitted)
            common = flags if common is None else common & flags
        effective = tuple(ordered_flags(common or set()))
        for member in group:
            member.effective = effective
            member.narrowed = list(effective) != list(member.admitted)


def _excluded(
    units: tuple[Unit, ...],
    prepared: list[_Norm],
    members: list[_Member],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for unit in units:
        if unit.decision == "reject":
            rows.append(_exclusion(unit, unit.reason, None, "inventory"))
    for item in prepared:
        if item.exclusion is not None and item.unit.decision != "vendored":
            rows.append(_exclusion(item.unit, item.exclusion, None, "scan"))
        elif item.failure is not None and item.unit.decision != "vendored" and not item.unit.holdout:
            rows.append(_exclusion(item.unit, item.failure, None, "normalize"))
    for member in members:
        if member.leak:
            rows.append(_exclusion(member.norm.unit, "holdout-family", member.family, "dedup"))
    return rows


def _attach_vendored(
    prepared: list[_Norm],
    by_id: dict[str, _Norm],
    members: list[_Member],
    excluded: list[dict[str, Any]],
) -> None:
    member_by_id = {member.norm.unit.unit_id: member for member in members}
    excluded_by_id = {row["unit_id"]: row for row in excluded}
    for item in prepared:
        if item.unit.decision != "vendored":
            continue
        upstream_id = item.unit.upstream_unit_id or ""
        upstream = by_id.get(upstream_id)
        copy = _vendored_copy(item)
        if (
            upstream is None
            or upstream.group is None
            or item.group is None
            or upstream.exclusion is not None
        ):
            reason = (
                "vendored-unreadable"
                if item.failure is not None
                else "vendored-upstream-unavailable"
            )
            excluded.append(_exclusion(item.unit, reason, None, "vendored"))
            continue
        if item.group.normalized_sha256 != upstream.group.normalized_sha256:
            excluded.append(_exclusion(item.unit, "vendored-stale", None, "vendored"))
            continue
        member = member_by_id.get(upstream_id)
        if member is not None:
            member.vendored.append(copy)
            continue
        row = excluded_by_id.get(upstream_id)
        if row is not None:
            row["vendored_copies"].append(copy)
            continue
        excluded.append(
            _exclusion(item.unit, "vendored-upstream-unavailable", None, "vendored")
        )


def _vendored_copy(item: _Norm) -> dict[str, Any]:
    files = []
    if item.group is not None:
        files = [
            {"blob_sha": member.blob_sha, "path": member.path, "role": member.role}
            for member in item.group.files
        ]
    return {
        "blob_sha": item.unit.blob_sha,
        "files": files,
        "path": item.unit.path,
        "pin": item.unit.pin,
        "repo": item.unit.repo,
        "unit_id": item.unit.unit_id,
    }


def _assemble(
    members: list[_Member],
    excluded: list[dict[str, Any]],
    comparable: list[_Norm],
    prepared: list[_Norm],
    families: dict[str, str],
    actor: str,
    created_at: str,
) -> CompiledSnapshot:
    envelopes: list[dict[str, Any]] = []
    example_digests: list[str] = []
    manifest_units: list[dict[str, Any]] = []
    for item in sorted(prepared, key=lambda row: row.unit.unit_id):
        if item.failure is None or item.unit.decision == "vendored" or item.unit.holdout:
            continue
        envelopes.extend(_failure_envelopes(item, actor, created_at))
    for member in sorted(members, key=lambda item: item.norm.unit.unit_id):
        built = _unit_envelopes(member, actor, created_at)
        envelopes.extend(built)
        if member.leak:
            continue
        example = next(
            item for item in built if item["payload"].get("record_type") == "Example"
        )
        example_digests.append(example["content_digest"])
        manifest_units.append(_manifest_unit(member))
    sealed = _sealed_rows(comparable, families)
    excluded_rows = sorted(excluded, key=lambda row: row["unit_id"])
    for row in excluded_rows:
        row["vendored_copies"] = sorted(
            row["vendored_copies"],
            key=lambda copy: (copy["repo"], copy["pin"], copy["path"], copy["unit_id"]),
        )
    manifest_payload = {
        "example_digests": sorted(example_digests),
        "excluded": excluded_rows,
        "lifecycle": "DEDUPED",
        "near_duplicate": {
            "algorithm": "token-shingle-jaccard",
            "min_tokens": MIN_TOKENS,
            "n": NGRAM_N,
            "threshold": f"{THRESHOLD_NUMERATOR}/{THRESHOLD_DENOMINATOR}",
        },
        "normalization": {
            "encoding": "utf-8",
            "line_endings": "lf",
            "strip_trailing": "space-and-tab",
            "unicode_normalization": "none",
        },
        "policy": POLICY_ID,
        "record_type": "DedupManifest",
        "sealed": sealed,
        "snapshot_version": _MANIFEST_VERSION,
        "split_frozen": False,
        "units": sorted(
            manifest_units,
            key=lambda row: (
                row["repo"],
                row["pin"],
                row["path"],
                "" if row["slice"] is None else row["slice"]["name"],
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
    normalized = member.norm.group
    assert normalized is not None
    source = _envelope(_source_payload(unit), [], created_at)
    source_digest = source["content_digest"]
    rights = _envelope(_rights_payload(unit, source_digest, actor), [source_digest], created_at)
    rights_digest = rights["content_digest"]
    rights_receipt = _receipt(
        actor=actor,
        timestamp=created_at,
        input_hashes=[source_digest, rights_digest],
        from_state="DISCOVERED",
        event="rights_cleared",
        to_state="RIGHTS_CLEARED",
        disposition=f"cleared: {unit.license}",
        parents=[source_digest, rights_digest],
    )
    example_payload = {
        "blob_sha": unit.blob_sha,
        "duplicate_family": member.family,
        "faust_source": normalized.text,
        "normalized_sha256": normalized.normalized_sha256,
        "original_sha256": normalized.original_sha256,
        "record_type": "Example",
        "source_digest": source_digest,
        "unit_id": unit.unit_id,
    }
    example = _envelope(example_payload, [source_digest, rights_digest], created_at)
    example_digest = example["content_digest"]
    normalized_receipt = _receipt(
        actor=actor,
        timestamp=created_at,
        input_hashes=[
            source_digest,
            rights_digest,
            rights_receipt["content_digest"],
            example_digest,
        ],
        from_state="RIGHTS_CLEARED",
        event="normalized",
        to_state="NORMALIZED",
        disposition="normalized",
        parents=[
            source_digest,
            rights_digest,
            rights_receipt["content_digest"],
            example_digest,
        ],
    )
    if member.leak:
        event = "duplicate_or_leak_found"
        to_state = "QUARANTINED"
        disposition = f"excluded: conflicting family {member.family}"
    else:
        event = "dedup_passed"
        to_state = "DEDUPED"
        disposition = f"duplicate_family={member.family}"
    dedup_parents = [
        source_digest,
        rights_digest,
        example_digest,
        normalized_receipt["content_digest"],
    ]
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
    return [source, rights, rights_receipt, example, normalized_receipt, dedup]


def _failure_envelopes(item: _Norm, actor: str, created_at: str) -> list[dict[str, Any]]:
    unit = item.unit
    source = _envelope(_source_payload(unit), [], created_at)
    source_digest = source["content_digest"]
    rights = _envelope(_rights_payload(unit, source_digest, actor), [source_digest], created_at)
    rights_digest = rights["content_digest"]
    rights_receipt = _receipt(
        actor=actor,
        timestamp=created_at,
        input_hashes=[source_digest, rights_digest],
        from_state="DISCOVERED",
        event="rights_cleared",
        to_state="RIGHTS_CLEARED",
        disposition=f"cleared: {unit.license}",
        parents=[source_digest, rights_digest],
    )
    failed = _receipt(
        actor=actor,
        timestamp=created_at,
        input_hashes=[source_digest, rights_digest, rights_receipt["content_digest"]],
        from_state="RIGHTS_CLEARED",
        event="normalize_failed",
        to_state="QUARANTINED",
        disposition=f"normalize_failed: {item.failure}",
        parents=[source_digest, rights_digest, rights_receipt["content_digest"]],
    )
    return [source, rights, rights_receipt, failed]


def _rights_payload(unit: Unit, source_digest: str, actor: str) -> dict[str, Any]:
    return {
        "attribution": unit.attribution,
        "eligible_for": list(unit.eligible_for),
        "license": unit.license,
        "record_type": "RightsRecord",
        "reviewer": unit.reviewer or actor,
        "subject": source_digest,
        "unit_id": unit.unit_id,
    }


def _manifest_unit(member: _Member) -> dict[str, Any]:
    unit = member.norm.unit
    normalized = member.norm.group
    assert normalized is not None
    return {
        "admitted_eligible_for": list(member.admitted),
        "attribution": unit.attribution,
        "blob_sha": unit.blob_sha,
        "duplicate_family": member.family,
        "eligible_for": list(member.effective),
        "files": _manifest_files(normalized),
        "evidence_label": unit.evidence_label,
        "impulse": unit.impulse,
        "license": unit.license,
        "normalized_sha256": normalized.normalized_sha256,
        "notice": _notice_payload(unit.notice),
        "original_sha256": normalized.original_sha256,
        "path": unit.path,
        "pin": unit.pin,
        "repo": unit.repo,
        "reviewer": unit.reviewer,
        "rights_narrowed": member.narrowed,
        "slice": _slice_payload(unit),
        "source_id": unit.source_id,
        "training_only": list(member.effective) == ["train"],
        "unit_id": unit.unit_id,
        "vendored_copies": sorted(
            member.vendored,
            key=lambda copy: (copy["repo"], copy["pin"], copy["path"], copy["unit_id"]),
        ),
    }


def _sealed_rows(
    comparable: list[_Norm], families: dict[str, str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in comparable:
        if not item.unit.holdout or item.group is None:
            continue
        rows.append(
            {
                "duplicate_family": families[item.unit.unit_id],
                "license": item.unit.license,
                "normalized_sha256": item.group.normalized_sha256,
                "path": item.unit.path,
                "pin": item.unit.pin,
                "repo": item.unit.repo,
                "source_id": item.unit.source_id,
                "unit_id": item.unit.unit_id,
            }
        )
    rows.sort(key=lambda row: row["unit_id"])
    return rows


def _manifest_files(group: NormalizedGroup) -> list[dict[str, str]]:
    return [
        {
            "blob_sha": item.blob_sha,
            "normalized_sha256": item.normalized.normalized_sha256,
            "original_sha256": item.normalized.original_sha256,
            "path": item.path,
            "role": item.role,
        }
        for item in group.files
    ]


def _exclusion(
    unit: Unit, reason: str, family: str | None, origin: str
) -> dict[str, Any]:
    return {
        "duplicate_family": family,
        "origin": origin,
        "path": unit.path,
        "pin": unit.pin,
        "reason": reason,
        "repo": unit.repo,
        "unit_id": unit.unit_id,
        "vendored_copies": [],
    }


def _source_payload(unit: Unit) -> dict[str, Any]:
    return {
        "license_claim": unit.license,
        "record_type": "SourceRecord",
        "retrieved_at": unit.generated_at,
        "unit_id": unit.unit_id,
        "uri": source_uri(unit),
    }


def _notice_payload(notice: Notice | None) -> dict[str, str] | None:
    if notice is None:
        return None
    return {
        "blob_sha": notice.blob_sha,
        "copyright": notice.copyright,
        "license": notice.license,
        "path": notice.path,
    }


def _slice_payload(unit: Unit) -> dict[str, Any] | None:
    if unit.slice is None:
        return None
    return {
        "end_line": unit.slice.end_line,
        "name": unit.slice.name,
        "start_line": unit.slice.start_line,
    }


def _fetch(
    units: tuple[Unit, ...], fetcher: BlobFetcher
) -> dict[tuple[str, str, str, str], bytes]:
    cache: dict[tuple[str, str, str, str], bytes] = {}
    for unit in units:
        if unit.decision == "reject":
            continue
        for member in unit.files:
            _cached(cache, fetcher, unit.repo, unit.pin, member.path, member.blob_sha)
        if unit.notice is not None:
            data = _cached(
                cache,
                fetcher,
                unit.repo,
                unit.pin,
                unit.notice.path,
                unit.notice.blob_sha,
            )
            _require_copyright(data, unit)
    return cache


def _cached(
    cache: dict[tuple[str, str, str, str], bytes],
    fetcher: BlobFetcher,
    repo: str,
    pin: str,
    path: str,
    blob_sha: str,
) -> bytes:
    key = (repo, pin, path, blob_sha)
    if key not in cache:
        cache[key] = fetch_verified(fetcher, repo, pin, path, blob_sha)
    return cache[key]


def _require_copyright(data: bytes, unit: Unit) -> None:
    notice = unit.notice
    if notice is None:
        return
    if data.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in data:
        raise AcquireError(f"{unit.unit_id}: notice encoding is not utf-8")
    body = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AcquireError(f"{unit.unit_id}: notice encoding is not utf-8") from exc
    if notice.copyright not in text:
        raise AcquireError(f"{unit.unit_id}: notice blob does not contain the copyright")


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

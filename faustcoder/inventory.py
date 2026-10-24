"""Admission from a T05 rights inventory and notice manifest.

T06 does not keep a parallel inventory schema. A unit is one file or
one function of a ``rights-inventory.v1`` entry: ``path``, ``function``
and ``blob_sha``. A cleared unit also needs a ``notice-manifest.v1``
row at the same commit. ``rights_rejected`` and ``needs_human`` rows that name a blob are
comparison-only. The snapshot fetches them for near-duplicate
clustering and does not admit them. A row with no blob is an
exclusion and is not fetched.

``generated_at`` is not part of the content digest. Re-signing an
inventory without changing entries does not change the snapshot.

This module does not clear rights. Admission of a cleared unit calls
``faustcoder.rights.guard_cleared_unit``, the T05 guard. The documents
must match the pinned content digests of ``corpus/rights-inventory.v1.json``
and ``corpus/notice-manifest.v1.json``. A missing reviewer is not filled
in from the snapshot actor.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from faustcoder.canonical import canonical_bytes, sha256_prefixed
from faustcoder.errors import InventoryError, LicenseEvidenceError, NeedsHumanDecision
from faustcoder.rights import guard_cleared_unit
from faustcoder.rights_policy import is_impulse_path

INVENTORY_VERSION = "rights-inventory.v1"
NOTICE_VERSION = "notice-manifest.v1"
# Content digests of the T05 corpus files. ``generated_at`` is omitted
# and entries are sorted, so a re-sign does not move the pin.
# 2026-10-24: exact helper MIT author confirmation; see
# docs/analysis/helper-author-confirmation-2026-10-24.json.
# Historical receipts retain their earlier pins and require a new replay.
PINNED_INVENTORY_DIGEST = (
    "sha256:358ff7b792ff4f3e32b1619ff81030fdc61b8b575e29778a7b625a83665d1065"
)
PINNED_NOTICE_DIGEST = (
    "sha256:1a6d5c0ea41d2e6ccc14dd2127ca8a3e92e4ef06ad66bf857b8bd729a7d4897a"
)
FFUNCTION_REASON = "ffunction"
NEEDS_HUMAN_REASON = "needs-human"
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ZERO_BLOB = frozenset({"0" * 40, "0" * 64})
_DECISIONS = frozenset({"rights_cleared", "rights_rejected", "needs_human"})
_FLAGS = ("train", "eval", "redistribute")


@dataclass(frozen=True)
class Notice:
    """One notice-manifest row. Not the notice bytes."""

    path: str
    blob_sha: str
    copyright: str
    license: str
    function: str


@dataclass(frozen=True)
class Unit:
    """One cleared file or function. Program text is not a field."""

    unit_id: str
    entry_id: str
    decision: str
    repo: str
    pin: str
    path: str
    blob_sha: str
    function: str
    license: str
    eligible_for: tuple[str, ...]
    evidence_label: str
    attribution: str
    notice: Notice | None
    reviewer: str
    reason: str
    impulse: bool
    holdout: bool
    training_only: bool


@dataclass(frozen=True)
class InventoryExclusion:
    """A row unit that is not admitted."""

    unit_id: str
    entry_id: str
    repo: str
    pin: str
    path: str
    function: str
    reason: str
    origin: str


@dataclass(frozen=True)
class Corpus:
    """Admitted units, comparison-only units, and the content digests.

    ``comparisons`` are ``rights_rejected`` and ``needs_human`` units that
    name a real blob. They are fetched for near-duplicate clustering and
    are never admitted.
    """

    units: tuple[Unit, ...]
    excluded: tuple[InventoryExclusion, ...]
    inventory_digest: str
    notice_digest: str
    comparisons: tuple[Unit, ...] = ()


def content_digest(document: Mapping[str, Any]) -> str:
    """Digest content-bearing fields. ``generated_at`` is omitted.

    Entry order is not content. The list is sorted by its canonical
    encoding before the hash, so a reshuffle of the same rows does not
    change the digest.
    """
    if not isinstance(document, Mapping):
        raise InventoryError("inventory must be a JSON object")
    body = {key: value for key, value in document.items() if key != "generated_at"}
    entries = body.get("entries")
    if isinstance(entries, list):
        body = dict(body)
        body["entries"] = sorted(entries, key=canonical_bytes)
    return sha256_prefixed(canonical_bytes(body))


def parse_corpus(
    inventory: Mapping[str, Any], notice: Mapping[str, Any]
) -> Corpus:
    """Return cleared units. Raise ``InventoryError`` on a bad document."""
    _check_time(inventory.get("generated_at"), "inventory generated_at")
    _check_time(notice.get("generated_at"), "notice generated_at")
    if inventory.get("schema_version") != INVENTORY_VERSION:
        raise InventoryError("unsupported inventory schema_version")
    if notice.get("schema_version") != NOTICE_VERSION:
        raise InventoryError("unsupported notice schema_version")
    entries = inventory.get("entries")
    rows = notice.get("entries")
    if not isinstance(entries, list) or not entries:
        raise InventoryError("inventory has no entries")
    if not isinstance(rows, list):
        raise InventoryError("notice manifest entries must be a list")
    inventory_digest, notice_digest = _pinned_digests(inventory, notice)
    notices = _notice_index(rows)
    admitted: list[Unit] = []
    excluded: list[InventoryExclusion] = []
    comparisons: list[Unit] = []
    pending: list[tuple[Unit, tuple[str, str, str, str]]] = []
    blocked: set[tuple[str, str, str, str]] = set()
    seen: set[tuple[str, str, str, str]] = set()
    by_id: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, Mapping) and isinstance(entry.get("id"), str):
            entry_id = str(entry["id"])
            if entry_id in by_id:
                raise InventoryError(f"{entry_id}: inventory entry id is repeated")
            by_id[entry_id] = entry
        pieces, blocks = _entry(entry, notices)
        blocked.update(blocks)
        for unit, blob_key in pieces:
            identity = (unit.repo, unit.pin, unit.path, unit.function)
            if identity in seen:
                raise InventoryError(f"{unit.entry_id}: {unit.path} is already in a row")
            seen.add(identity)
            if unit.decision == "rights_cleared":
                pending.append((unit, blob_key))
            else:
                excluded.append(_exclude(unit, unit.reason or unit.decision, "inventory"))
                if unit.blob_sha != "0" * 40:
                    comparisons.append(unit)
    for unit, blob_key in pending:
        if blob_key in blocked:
            excluded.append(
                _exclude(
                    unit,
                    NEEDS_HUMAN_REASON,
                    "inventory",
                )
            )
            continue
        if unit.notice is None:
            excluded.append(_exclude(unit, "notice-missing", "inventory"))
            continue
        if len(unit.reviewer) < 3:
            excluded.append(_exclude(unit, NEEDS_HUMAN_REASON, "inventory"))
            continue
        refusal = _cleared_refusal(by_id[unit.entry_id], unit, inventory, notice)
        if refusal is not None:
            excluded.append(_exclude(unit, refusal, "inventory"))
            continue
        admitted.append(unit)
    admitted.sort(key=lambda item: (item.repo, item.pin, item.path, item.function, item.unit_id))
    comparisons.sort(key=lambda item: (item.repo, item.pin, item.path, item.function, item.unit_id))
    excluded.sort(key=lambda item: item.unit_id)
    return Corpus(
        units=tuple(admitted),
        excluded=tuple(excluded),
        inventory_digest=inventory_digest,
        notice_digest=notice_digest,
        comparisons=tuple(comparisons),
    )


def source_uri(unit: Unit) -> str:
    """Return the T05 blob URL. A function name is the fragment."""
    base = f"https://github.com/{unit.repo}/blob/{unit.pin}/{unit.path}"
    if unit.function:
        return f"{base}#{unit.function}"
    return base


def _pinned_digests(
    inventory: Mapping[str, Any], notice: Mapping[str, Any]
) -> tuple[str, str]:
    """Refuse a document whose content digest is not the T05 corpus pin."""
    inventory_digest = content_digest(inventory)
    notice_digest = content_digest(notice)
    if inventory_digest != PINNED_INVENTORY_DIGEST:
        raise InventoryError("inventory digest does not match the T05 pin")
    if notice_digest != PINNED_NOTICE_DIGEST:
        raise InventoryError("notice digest does not match the T05 pin")
    return inventory_digest, notice_digest


def _cleared_refusal(
    entry: Mapping[str, Any],
    unit: Unit,
    inventory: Mapping[str, Any],
    notice: Mapping[str, Any],
) -> str | None:
    """Return an exclusion reason when T05's guard refuses the unit."""
    evidence_uri = entry.get("evidence_uri") or entry.get("url") or ""
    if not isinstance(evidence_uri, str):
        evidence_uri = ""
    try:
        guard_cleared_unit(
            inventory,
            notice,
            repo=unit.repo,
            commit=unit.pin,
            path=unit.path,
            function=unit.function,
            blob_sha=unit.blob_sha,
            license_name=unit.license,
            eligible_for=list(entry.get("eligible_for") or []),
            attribution=unit.attribution,
            evidence_label=unit.evidence_label,
            evidence_uri=evidence_uri,
            reason=unit.reason,
            reviewer=unit.reviewer,
            inventory_id=unit.entry_id,
        )
    except (LicenseEvidenceError, NeedsHumanDecision) as exc:
        message = str(exc)
        if "impulse-test" in message:
            return "impulse-eval"
        if "notice" in message:
            return "notice-missing"
        return NEEDS_HUMAN_REASON
    return None


def _entry(
    entry: object, notices: dict[tuple[str, str, str, str], Notice]
) -> tuple[list[tuple[Unit, tuple[str, str, str, str]]], set[tuple[str, str, str, str]]]:
    if not isinstance(entry, Mapping):
        raise InventoryError("inventory entry must be an object")
    entry_id = entry.get("id")
    if not isinstance(entry_id, str) or not entry_id.strip():
        raise InventoryError("inventory entry id is missing")
    decision = entry.get("decision")
    if decision not in _DECISIONS:
        raise InventoryError(f"{entry_id}: decision is not a T05 outcome")
    pin = entry.get("pin")
    if not isinstance(pin, Mapping):
        raise InventoryError(f"{entry_id}: pin must name a repo and commit")
    repo = _repo(pin.get("repo"), entry_id)
    commit = _hex40(pin.get("commit"), f"{entry_id}: commit")
    license_name = _text(entry.get("license"), f"{entry_id}: license")
    flags = _flags(entry.get("eligible_for"), entry_id)
    reviewer = entry.get("reviewer") or ""
    if not isinstance(reviewer, str):
        raise InventoryError(f"{entry_id}: reviewer must be a string")
    reviewer = reviewer.strip()
    reason = entry.get("reason") or ""
    if not isinstance(reason, str):
        raise InventoryError(f"{entry_id}: reason must be a string")
    attribution = entry.get("attribution") or ""
    if not isinstance(attribution, str):
        raise InventoryError(f"{entry_id}: attribution must be a string")
    label = entry.get("evidence_label") or "OBSERVED"
    if label not in {"OBSERVED", "INFERRED"}:
        raise InventoryError(f"{entry_id}: evidence_label is not a label")
    if label == "INFERRED" and decision == "rights_cleared" and len(reviewer) < 3:
        raise InventoryError(f"{entry_id}: an inferred clearance needs a named reviewer")
    files = entry.get("files") or []
    functions = entry.get("functions") or []
    if not isinstance(files, list) or not isinstance(functions, list):
        raise InventoryError(f"{entry_id}: files must be a list")
    specs = [_file_spec(item, entry_id) for item in files]
    specs.extend(_function_spec(item, entry_id) for item in functions)
    listed = "files" in entry or "functions" in entry
    if listed and "file_count" in entry and entry.get("file_count") != len(specs):
        raise InventoryError(f"{entry_id}: file_count does not match the file list")
    pieces: list[tuple[Unit, tuple[str, str, str, str]]] = []
    blocked: set[tuple[str, str, str, str]] = set()
    if not specs:
        unit = _unit(
            entry_id=entry_id,
            decision=str(decision),
            repo=repo,
            commit=commit,
            path=_text(entry.get("path") or entry_id, f"{entry_id}: path"),
            blob_sha="0" * 40,
            function="",
            license_name=license_name,
            flags=flags,
            label=str(label),
            attribution=attribution.strip(),
            reviewer=reviewer,
            reason=reason.strip(),
            notice=None,
        )
        blob_key = (repo, commit, unit.path, unit.blob_sha)
        if decision != "rights_cleared":
            blocked.add(blob_key)
        pieces.append((unit, blob_key))
        return pieces, blocked
    for path, blob_sha, function in specs:
        notice = notices.get((commit, path, function, blob_sha))
        if notice is not None and notice.license != license_name:
            notice = None
        unit = _unit(
            entry_id=entry_id,
            decision=str(decision),
            repo=repo,
            commit=commit,
            path=path,
            blob_sha=blob_sha,
            function=function,
            license_name=license_name,
            flags=flags,
            label=str(label),
            attribution=attribution.strip(),
            reviewer=reviewer,
            reason=reason.strip(),
            notice=notice if decision == "rights_cleared" else None,
        )
        blob_key = (repo, commit, path, blob_sha)
        if decision != "rights_cleared":
            blocked.add(blob_key)
        pieces.append((unit, blob_key))
    return pieces, blocked


def _unit(
    *,
    entry_id: str,
    decision: str,
    repo: str,
    commit: str,
    path: str,
    blob_sha: str,
    function: str,
    license_name: str,
    flags: tuple[str, ...],
    label: str,
    attribution: str,
    reviewer: str,
    reason: str,
    notice: Notice | None,
) -> Unit:
    identity = canonical_bytes(
        {
            "blob_sha": blob_sha,
            "commit": commit,
            "entry": entry_id,
            "function": function,
            "path": path,
            "repo": repo,
        }
    )
    unit_id = "u" + hashlib.sha256(identity).hexdigest()[:20]
    return Unit(
        unit_id=unit_id,
        entry_id=entry_id,
        decision=decision,
        repo=repo,
        pin=commit,
        path=path,
        blob_sha=blob_sha,
        function=function,
        license=license_name,
        eligible_for=flags,
        evidence_label=label,
        attribution=attribution,
        notice=notice,
        reviewer=reviewer,
        reason=reason,
        impulse=is_impulse_path(path, entry_id),
        holdout=False,
        training_only=flags == ("train",),
    )


def _exclude(unit: Unit, reason: str, origin: str) -> InventoryExclusion:
    return InventoryExclusion(
        unit_id=unit.unit_id,
        entry_id=unit.entry_id,
        repo=unit.repo,
        pin=unit.pin,
        path=unit.path,
        function=unit.function,
        reason=reason,
        origin=origin,
    )


def _notice_index(
    rows: list[object],
) -> dict[tuple[str, str, str, str], Notice]:
    index: dict[tuple[str, str, str, str], Notice] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise InventoryError("notice row must be an object")
        commit = _hex40(row.get("commit"), "notice commit")
        path = _path(row.get("path"), "notice path")
        blob_sha = _blob_sha(row.get("blob_sha"), "notice blob_sha")
        function = row.get("function") or ""
        if not isinstance(function, str):
            raise InventoryError("notice function must be a string")
        copyright_text = _text(row.get("copyright"), "notice copyright")
        license_name = _text(row.get("license"), "notice license")
        key = (commit, path, function, blob_sha)
        if key in index:
            raise InventoryError(f"notice manifest repeats {path}")
        index[key] = Notice(
            path=path,
            blob_sha=blob_sha,
            copyright=copyright_text,
            license=license_name,
            function=function,
        )
    return index


def _file_spec(value: object, entry_id: str) -> tuple[str, str, str]:
    if not isinstance(value, Mapping):
        raise InventoryError(f"{entry_id}: file entry must be an object")
    return (
        _path(value.get("path"), f"{entry_id}: path"),
        _blob_sha(value.get("blob_sha"), f"{entry_id}: blob_sha"),
        "",
    )


def _function_spec(value: object, entry_id: str) -> tuple[str, str, str]:
    if not isinstance(value, Mapping):
        raise InventoryError(f"{entry_id}: function entry must be an object")
    function = value.get("function")
    if not isinstance(function, str) or not function.strip():
        raise InventoryError(f"{entry_id}: function name is missing")
    return (
        _path(value.get("path"), f"{entry_id}: path"),
        _blob_sha(value.get("blob_sha"), f"{entry_id}: blob_sha"),
        function.strip(),
    )


def _flags(value: object, entry_id: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(
        isinstance(item, bool) or not isinstance(item, str) for item in value
    ):
        raise InventoryError(f"{entry_id}: eligible_for must be a list of flags")
    if any(item not in _FLAGS for item in value):
        raise InventoryError(f"{entry_id}: eligible_for has an unknown flag")
    return tuple(flag for flag in _FLAGS if flag in value)


def _check_time(value: object, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or _TIME.fullmatch(value) is None:
        raise InventoryError(f"{field} must be a UTC RFC3339 timestamp")


def _hex40(value: object, field: str) -> str:
    if not isinstance(value, str) or _HEX40.fullmatch(value) is None:
        raise InventoryError(f"{field} must be 40 lowercase hex characters")
    return value


def _blob_sha(value: object, field: str) -> str:
    """Accept a sha1 blob id or a sha256 blob id. Reject the zero placeholder."""
    if not isinstance(value, str) or (
        _HEX40.fullmatch(value) is None and _HEX64.fullmatch(value) is None
    ):
        raise InventoryError(
            f"{field} must be 40 lowercase hex characters or 64 for sha256"
        )
    if value in _ZERO_BLOB:
        raise InventoryError(f"{field} must be a git object id")
    return value


def _repo(value: object, entry_id: str) -> str:
    if not isinstance(value, str) or value.count("/") != 1:
        raise InventoryError(f"{entry_id}: repo must be owner/name")
    return value


def _path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        raise InventoryError(f"{field} must be a relative path")
    if "\\" in value or any(part in ("", ".", "..") for part in value.split("/")):
        raise InventoryError(f"{field} must be a relative path")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InventoryError(f"{field} is missing")
    return value.strip()

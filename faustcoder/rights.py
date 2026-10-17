"""Dataset rights transitions for spec §7.1 (task T05).

The transition table is the contract. This module executes only
``rights_cleared`` and ``rights_rejected``. Later events stay in the
table so a skipped rights check is rejected, and their effects are left
to the tasks that own them.

There is no contract schema for ``SourceRecord`` or ``RightsRecord``.
data-model.md infers their fields. ``record_type`` and the
``LicenseEvidence`` payload are SPECULATIVE discriminators so the store
can tell artifacts apart. They are not a new contract: ``contracts/``
is unchanged. The transition receipt uses
``transition-receipt.schema.json``.

License policy follows ADR-0003 (D-004, D-007). It is not legal advice.
A SPECULATIVE evidence label is not evidence, and an unrecognized
license stays ``DISCOVERED`` (``needs_human``) instead of being cleared
or rejected.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from faustcoder.canonical import build_envelope, parse_reference
from faustcoder.errors import (
    IllegalTransitionError,
    LicenseEvidenceError,
    NeedsHumanDecision,
    SourceContentError,
    TransitionNotImplemented,
)
from faustcoder.rights_policy import (
    LicenseClassification,
    assert_eval_split_allowed,
    classify_license,
    commit_in_uri,
    is_impulse_path,
    is_placeholder,
    overlay_eligible,
    same_license,
    valid_actor,
)
from faustcoder.schemas import validate
from faustcoder.store import ArtifactStore

SCHEMA_VERSION = "0.3.0"
PRODUCER = "faustcoder.rights"
RECEIPT_SCHEMA = "transition-receipt.schema.json"
INVENTORY_VERSION = "rights-inventory.v1"

INITIAL_STATE = "DISCOVERED"
DATASET_STATES = frozenset(
    {
        "DISCOVERED",
        "RIGHTS_CLEARED",
        "NORMALIZED",
        "DEDUPED",
        "FROZEN",
        "QUARANTINED",
    }
)
FINAL_STATES = frozenset({"FROZEN", "QUARANTINED"})
DATASET_EVENTS = frozenset(
    {
        "rights_cleared",
        "rights_rejected",
        "normalized",
        "normalize_failed",
        "dedup_passed",
        "duplicate_or_leak_found",
        "split_frozen",
    }
)
DECISIONS = frozenset({"rights_cleared", "rights_rejected", "needs_human"})
EVIDENCE_LABELS = frozenset({"OBSERVED", "INFERRED", "SPECULATIVE"})
USABLE_LABELS = frozenset({"OBSERVED", "INFERRED"})
ELIGIBILITY = frozenset({"train", "eval", "redistribute"})
TRAIN_ONLY = ("train",)
REDISTRIBUTABLE = ("train", "eval", "redistribute")

_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$"
)
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SOURCE_FIELDS = frozenset(
    {"record_type", "uri", "retrieved_at", "license_claim"}
)
_RIGHTS_FIELDS = frozenset(
    {"record_type", "license", "eligible_for", "attribution", "reviewer"}
)
_EVIDENCE_FIELDS = frozenset(
    {
        "record_type",
        "license",
        "evidence_label",
        "evidence_uri",
        "attribution",
        "eligible_for",
        "reason",
        "reviewer",
        "inventory_id",
    }
)


@dataclass(frozen=True)
class Transition:
    """One row of the dataset transition table (spec §7.1)."""

    from_state: str
    event: str
    to_state: str
    guard: str
    effect: str
    implemented: bool


@dataclass(frozen=True)
class TransitionResult:
    """Receipt written by one successful rights transition."""

    state: str
    receipt: dict[str, Any]
    rights_record_id: str | None


TRANSITIONS: tuple[Transition, ...] = (
    Transition(
        "DISCOVERED",
        "rights_cleared",
        "RIGHTS_CLEARED",
        "RightsRecord shows license eligibility, attribution, and a notice row (R-002, R-014, D-013)",
        "Write RightsRecord; append receipt",
        True,
    ),
    Transition(
        "DISCOVERED",
        "rights_rejected",
        "QUARANTINED",
        "License ineligible, unknown or restricted (R-014)",
        "Write exclusion receipt with reason; content not copied into any snapshot",
        True,
    ),
    Transition(
        "RIGHTS_CLEARED",
        "normalized",
        "NORMALIZED",
        "Deterministic transform succeeded",
        "Write normalized Example as new node, parent = source; append receipt",
        False,
    ),
    Transition(
        "RIGHTS_CLEARED",
        "normalize_failed",
        "QUARANTINED",
        "Transform error (INFERRED)",
        "Append receipt with diagnostics (INFERRED)",
        False,
    ),
    Transition(
        "NORMALIZED",
        "dedup_passed",
        "DEDUPED",
        "No exact or near-duplicate family conflict; not in holdout family (R-003)",
        "Record duplicate-family id; append receipt",
        False,
    ),
    Transition(
        "NORMALIZED",
        "duplicate_or_leak_found",
        "QUARANTINED",
        "Duplicate or holdout-contamination match (R-003)",
        "Append exclusion receipt naming the conflicting family",
        False,
    ),
    Transition(
        "DEDUPED",
        "split_frozen",
        "FROZEN",
        "SplitManifest assigns the item by project, near-duplicate family and provenance (R-003)",
        "Write DatasetSnapshot and signed SplitManifest digests; append receipt",
        False,
    ),
)

_BY_EDGE = {(row.from_state, row.event): row for row in TRANSITIONS}


def lookup_transition(from_state: str, event: str) -> Transition | None:
    """Return the table row, or None when the edge is illegal."""
    return _BY_EDGE.get((from_state, event))


def register_source(
    store: ArtifactStore,
    payload: Mapping[str, Any],
    *,
    created_at: str,
    producer: str = PRODUCER,
) -> dict[str, Any]:
    """Store one SourceRecord. The payload must not contain program text."""
    _check_source_payload(payload)
    envelope = build_envelope(
        schema_version=SCHEMA_VERSION,
        created_at=created_at,
        producer=producer,
        parents=[],
        payload=dict(payload),
    )
    store.put(envelope)
    return envelope


def current_state(store: ArtifactStore, source: str) -> str:
    """Return the dataset state implied by receipts for ``source``."""
    source_id = parse_reference(source)
    envelope = store.get(source_id)
    _check_source_payload(envelope["payload"])
    return _state_from_receipts(store, envelope["content_digest"])


def apply_transition(
    store: ArtifactStore,
    source: str,
    event: str,
    evidence: Mapping[str, Any],
    *,
    actor: str,
    timestamp: str,
    created_at: str | None = None,
    inventory: Mapping[str, Any] | None = None,
    notice: Mapping[str, Any] | None = None,
) -> TransitionResult:
    """Append one rights transition, or raise without writing.

    ``rights_cleared`` stores a RightsRecord and a receipt. It requires
    an inventory row, a pinned commit, and a notice manifest entry.
    ``rights_rejected`` stores the license evidence and an exclusion
    receipt. The source payload is not copied into either.
    """
    if not isinstance(event, str) or event not in DATASET_EVENTS:
        raise IllegalTransitionError(current_state(store, source), str(event))
    _check_actor(actor)
    _check_time(timestamp, "timestamp")
    stamped = timestamp if created_at is None else created_at
    _check_time(stamped, "created_at")

    source_id = parse_reference(source)
    source_envelope = store.get(source_id)
    _check_source_payload(source_envelope["payload"])
    source_digest = source_envelope["content_digest"]
    state = _state_from_receipts(store, source_digest)
    edge = lookup_transition(state, event)
    if edge is None:
        raise IllegalTransitionError(state, event)
    if not edge.implemented:
        raise TransitionNotImplemented(state, event)

    checked = _check_evidence(evidence)
    classification = classify_license(checked["license"])
    entry = _guard(
        event,
        checked,
        classification,
        source_envelope["payload"],
        inventory,
        notice,
    )

    evidence_payload = dict(checked)
    evidence_envelope = build_envelope(
        schema_version=SCHEMA_VERSION,
        created_at=stamped,
        producer=PRODUCER,
        parents=[source_digest],
        payload=evidence_payload,
    )
    rights_envelope: dict[str, Any] | None = None
    if event == "rights_cleared":
        reviewer = checked.get("reviewer") or (entry or {}).get("reviewer") or actor
        rights_payload = {
            "record_type": "RightsRecord",
            "license": classification.canonical_license,
            "eligible_for": list(checked["eligible_for"]),
            "attribution": checked["attribution"],
            "reviewer": reviewer,
        }
        _check_rights_payload(rights_payload)
        rights_envelope = build_envelope(
            schema_version=SCHEMA_VERSION,
            created_at=stamped,
            producer=PRODUCER,
            parents=[source_digest, evidence_envelope["content_digest"]],
            payload=rights_payload,
        )

    input_hashes = [source_digest, evidence_envelope["content_digest"]]
    parents = [source_digest, evidence_envelope["content_digest"]]
    if rights_envelope is not None:
        input_hashes.append(rights_envelope["content_digest"])
        parents.append(rights_envelope["content_digest"])
    disposition = _disposition(event, classification, checked["reason"])
    receipt_payload = {
        "actor": actor,
        "timestamp": timestamp,
        "input_hashes": input_hashes,
        "machine": "dataset",
        "from": state,
        "event": event,
        "to": edge.to_state,
        "disposition": disposition,
    }
    validate(receipt_payload, RECEIPT_SCHEMA)
    receipt_envelope = build_envelope(
        schema_version=SCHEMA_VERSION,
        created_at=stamped,
        producer=PRODUCER,
        parents=parents,
        payload=receipt_payload,
    )

    store.put(evidence_envelope)
    rights_id: str | None = None
    if rights_envelope is not None:
        # The id is the payload hash. Two sources with the same license,
        # eligibility, attribution, and reviewer share one RightsRecord.
        # A second put would try to attach different parents to that id.
        if not store.exists(rights_envelope["artifact_id"]):
            store.put(rights_envelope)
        rights_id = rights_envelope["artifact_id"]
    store.put(receipt_envelope)
    return TransitionResult(edge.to_state, receipt_envelope, rights_id)


def load_inventory(path: Path | str) -> dict[str, Any]:
    """Load the rights inventory and reject a row the policy would not sign."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise LicenseEvidenceError("inventory must be a JSON object")
    if raw.get("schema_version") != INVENTORY_VERSION:
        raise LicenseEvidenceError("unsupported inventory schema_version")
    entries = raw.get("entries")
    if not isinstance(entries, list) or not entries:
        raise LicenseEvidenceError("inventory has no entries")
    notice_path = Path(path).with_name("notice-manifest.v1.json")
    notice = (
        json.loads(notice_path.read_text(encoding="utf-8"))
        if notice_path.is_file()
        else {"entries": []}
    )
    seen: set[str] = set()
    units: set[tuple[str, str, str]] = set()
    for entry in entries:
        _check_inventory_entry(entry, seen)
        _check_units(entry, units)
        if isinstance(entry, dict) and entry.get("decision") == "rights_cleared":
            _require_notice(entry, notice)
    return raw


def _guard(
    event: str,
    evidence: Mapping[str, Any],
    classification: LicenseClassification,
    source_payload: Mapping[str, Any],
    inventory: Mapping[str, Any] | None,
    notice: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if evidence["evidence_label"] not in USABLE_LABELS:
        raise LicenseEvidenceError(
            "speculative claims are not license evidence"
        )
    if len(evidence["reason"].strip()) < 3:
        raise LicenseEvidenceError("a transition requires a reason")
    if event == "rights_rejected":
        if classification.decision == "needs_human":
            raise NeedsHumanDecision(classification.rationale)
        if classification.decision != "rights_rejected":
            raise LicenseEvidenceError(
                "rights_rejected requires an ineligible, unknown, or restricted license"
            )
        if evidence["eligible_for"] != []:
            raise LicenseEvidenceError(
                "eligible_for does not match the license class"
            )
        return None
    if classification.decision == "needs_human":
        raise NeedsHumanDecision(classification.rationale)
    if classification.decision != "rights_cleared":
        raise LicenseEvidenceError(
            "rights_cleared requires an eligible license with attribution"
        )
    if not same_license(str(evidence["license"]), str(source_payload["license_claim"])):
        raise NeedsHumanDecision(
            "evidence license does not match the source license claim"
        )
    if is_placeholder(evidence.get("attribution")):
        raise LicenseEvidenceError("rights_cleared requires attribution")
    pinned = commit_in_uri(source_payload.get("uri"))
    if pinned is None:
        raise LicenseEvidenceError(
            "source URL is not pinned to an immutable commit"
        )
    entry = _matching_entry(inventory, evidence.get("inventory_id"))
    if entry.get("decision") != "rights_cleared":
        raise LicenseEvidenceError(
            "inventory row is not a rights_cleared decision"
        )
    if not same_license(str(entry.get("license")), str(evidence["license"])):
        raise LicenseEvidenceError("inventory license does not match the evidence")
    pin = entry.get("pin")
    if not isinstance(pin, dict) or pin.get("commit") != pinned:
        raise LicenseEvidenceError("source URL is not pinned to the inventory commit")
    if list(evidence["eligible_for"]) != list(entry.get("eligible_for") or []):
        raise LicenseEvidenceError("eligible_for does not match the inventory row")
    allowed = set(
        overlay_eligible(
            classification,
            path=str(entry.get("path") or ""),
            entry_id=str(entry.get("id") or ""),
        )
    )
    if not set(evidence["eligible_for"]) <= allowed or not evidence["eligible_for"]:
        raise LicenseEvidenceError("eligible_for does not match the license class")
    if entry.get("attribution_complete") is not True and not valid_actor(
        evidence.get("reviewer") or entry.get("reviewer")
    ):
        raise LicenseEvidenceError(
            "incomplete attribution needs a named reviewer"
        )
    reviewer = evidence.get("reviewer") or entry.get("reviewer")
    if evidence["evidence_label"] == "INFERRED" and not valid_actor(reviewer):
        raise LicenseEvidenceError(
            "an inferred clearance requires a named reviewer"
        )
    if "redistribute" in evidence["eligible_for"] and not classification.redistribute:
        raise LicenseEvidenceError("this license cannot be redistributed")
    _require_notice(entry, notice)
    for unit_path in _unit_paths(entry):
        if "eval" in evidence["eligible_for"]:
            assert_eval_split_allowed(unit_path, str(entry.get("id")), "eval")
    return entry


def _disposition(
    event: str, classification: LicenseClassification, reason: str
) -> str:
    if event == "rights_rejected":
        return f"excluded: {reason}"
    return f"cleared: {classification.canonical_license}: {reason}"


def _state_from_receipts(store: ArtifactStore, source_digest: str) -> str:
    receipts = _receipts_for(store, source_digest)
    if not receipts:
        return INITIAL_STATE
    heads = [
        item
        for item in receipts
        if not any(
            item["content_digest"] in other["parents"]
            for other in receipts
            if other["content_digest"] != item["content_digest"]
        )
    ]
    if len(heads) != 1:
        raise IllegalTransitionError(
            INITIAL_STATE, f"divergent receipts ({len(heads)})"
        )
    state = heads[0]["payload"]["to"]
    if state not in DATASET_STATES:
        raise IllegalTransitionError(str(state), "unknown-state")
    return state


def _receipts_for(
    store: ArtifactStore, source_digest: str
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for artifact_id in store.list():
        envelope = store.get(artifact_id)
        payload = envelope["payload"]
        if payload.get("machine") != "dataset" or "event" not in payload:
            continue
        validate(payload, RECEIPT_SCHEMA)
        if source_digest in payload["input_hashes"]:
            found.append(envelope)
    return found


def _check_inventory_entry(entry: object, seen: set[str]) -> None:
    if not isinstance(entry, dict):
        raise LicenseEvidenceError("inventory entry must be an object")
    entry_id = entry.get("id")
    if not isinstance(entry_id, str) or not entry_id or entry_id in seen:
        raise LicenseEvidenceError("inventory entry id is missing or repeated")
    seen.add(entry_id)
    decision = entry.get("decision")
    if decision not in DECISIONS:
        raise LicenseEvidenceError(f"{entry_id}: decision is not a rights outcome")
    label = entry.get("evidence_label")
    if label not in EVIDENCE_LABELS:
        raise LicenseEvidenceError(f"{entry_id}: evidence_label is not a label")
    if label == "SPECULATIVE" and (
        decision != "needs_human" or entry.get("attribution_complete") is not False
    ):
        raise LicenseEvidenceError(
            f"{entry_id}: a speculative row cannot be transitioned"
        )
    license_name = entry.get("license")
    if not isinstance(license_name, str):
        raise LicenseEvidenceError(f"{entry_id}: license must be a string")
    classification = classify_license(license_name)
    _check_decision_is_not_looser(entry_id, decision, classification.decision)
    eligible = entry.get("eligible_for")
    if not isinstance(eligible, list):
        raise LicenseEvidenceError(f"{entry_id}: eligible_for must be a list")
    allowed = set(
        overlay_eligible(
            classification,
            path=str(entry.get("path") or ""),
            entry_id=entry_id,
        )
    )
    if decision == "rights_cleared" and (
        not eligible or not set(eligible) <= allowed
    ):
        raise LicenseEvidenceError(f"{entry_id}: eligible_for disagrees with policy")
    if decision == "rights_cleared" and (
        ("redistribute" in eligible) != bool(entry.get("redistribute"))
    ):
        raise LicenseEvidenceError(f"{entry_id}: redistribute flag disagrees with eligible_for")
    if is_impulse_path(str(entry.get("path") or ""), entry_id) and "eval" in eligible:
        raise LicenseEvidenceError(f"{entry_id}: impulse-test files cannot enter eval")
    if decision != "rights_cleared" and eligible != []:
        raise LicenseEvidenceError(
            f"{entry_id}: only a clearance grants eligible_for"
        )
    if decision == "rights_rejected" and entry.get("attribution_complete") is not True:
        raise LicenseEvidenceError(
            f"{entry_id}: a rejection needs complete attribution"
        )
    if (
        decision == "rights_cleared"
        and entry.get("attribution_complete") is not True
        and not valid_actor(entry.get("reviewer"))
    ):
        raise LicenseEvidenceError(
            f"{entry_id}: incomplete attribution needs a named reviewer"
        )
    for key in (
        "name",
        "url",
        "path",
        "reason",
        "attribution",
        "evidence_uri",
        "redistribution",
        "training",
        "emitting_code",
    ):
        if not isinstance(entry.get(key), str) or not entry[key].strip():
            raise LicenseEvidenceError(f"{entry_id}: {key} is empty")
    if len(entry["reason"]) > 800 or len(entry["attribution"]) > 800:
        raise LicenseEvidenceError(f"{entry_id}: text field is too long")
    if not entry["url"].startswith("https://") or not entry[
        "evidence_uri"
    ].startswith("https://"):
        raise LicenseEvidenceError(f"{entry_id}: url must be https")
    pin = entry.get("pin")
    if (
        not isinstance(pin, dict)
        or not isinstance(pin.get("repo"), str)
        or not pin["repo"].strip()
        or not isinstance(pin.get("ref"), str)
        or not pin["ref"].strip()
        or not _GIT_COMMIT.fullmatch(str(pin.get("commit", "")))
    ):
        raise LicenseEvidenceError(f"{entry_id}: pin is missing a repo, ref, or commit")
    if not isinstance(entry.get("copyleft"), bool):
        raise LicenseEvidenceError(f"{entry_id}: copyleft must be a boolean")
    if not isinstance(entry.get("redistribute"), bool):
        raise LicenseEvidenceError(f"{entry_id}: redistribute must be a boolean")
    reviewer = entry.get("reviewer")
    if reviewer is not None and not valid_actor(reviewer):
        raise LicenseEvidenceError(f"{entry_id}: reviewer is not a named person")
    if (
        decision == "rights_cleared"
        and entry.get("evidence_label") == "INFERRED"
        and not valid_actor(reviewer)
    ):
        raise LicenseEvidenceError(
            f"{entry_id}: an inferred clearance requires a named reviewer"
        )
    if not isinstance(entry.get("attribution_complete"), bool):
        raise LicenseEvidenceError(f"{entry_id}: attribution_complete must be a boolean")
    flags = entry.get("danny_flags")
    if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
        raise LicenseEvidenceError(f"{entry_id}: danny_flags must be strings")
    claims = entry.get("claims")
    if not isinstance(claims, list) or not claims:
        raise LicenseEvidenceError(f"{entry_id}: claims are required")
    for claim in claims:
        if not isinstance(claim, dict):
            raise LicenseEvidenceError(f"{entry_id}: claim must be an object")
        if claim.get("label") not in EVIDENCE_LABELS:
            raise LicenseEvidenceError(f"{entry_id}: claim label is unknown")
        statement = claim.get("statement")
        if not isinstance(statement, str) or len(statement) > 800:
            raise LicenseEvidenceError(f"{entry_id}: claim statement is missing or long")
        if "process =" in statement or "import(" in statement:
            raise SourceContentError(f"{entry_id}: claim contains program text")
    count = entry.get("file_count")
    if count is not None and (not isinstance(count, int) or count < 0):
        raise LicenseEvidenceError(f"{entry_id}: file_count must be an integer or null")


def _check_decision_is_not_looser(
    entry_id: str, decision: str, policy_decision: str
) -> None:
    """An inventory row may be stricter than the license class, never looser."""
    if policy_decision == "rights_rejected" and decision != "rights_rejected":
        raise LicenseEvidenceError(
            f"{entry_id}: policy rejects this license"
        )
    if policy_decision == "needs_human" and decision != "needs_human":
        raise LicenseEvidenceError(
            f"{entry_id}: an unrecognized license cannot be cleared or rejected"
        )
    if policy_decision == "rights_cleared" and decision == "rights_rejected":
        raise LicenseEvidenceError(
            f"{entry_id}: an allowlisted license cannot be rejected by the inventory"
        )


def _check_source_payload(payload: Mapping[str, Any]) -> None:
    _check_fields(payload, _SOURCE_FIELDS, "SourceRecord")
    if payload.get("record_type") != "SourceRecord":
        raise SourceContentError("payload is not a SourceRecord")
    _check_https(payload.get("uri"), "uri")
    _check_time(payload.get("retrieved_at"), "retrieved_at")
    claim = payload.get("license_claim")
    if not isinstance(claim, str) or not claim.strip() or len(claim) > 400:
        raise LicenseEvidenceError("license_claim is missing or too long")


def _check_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise LicenseEvidenceError("license evidence must be an object")
    _check_fields(evidence, _EVIDENCE_FIELDS, "LicenseEvidence")
    if evidence.get("record_type") != "LicenseEvidence":
        raise LicenseEvidenceError("evidence record_type is not LicenseEvidence")
    label = evidence.get("evidence_label")
    if label not in EVIDENCE_LABELS:
        raise LicenseEvidenceError("evidence_label is not OBSERVED, INFERRED, or SPECULATIVE")
    _check_https(evidence.get("evidence_uri"), "evidence_uri")
    for key, limit in (("attribution", 800), ("reason", 800), ("license", 120)):
        value = evidence.get(key)
        if not isinstance(value, str) or len(value) > limit:
            raise LicenseEvidenceError(f"{key} is missing or too long")
    eligible = evidence.get("eligible_for")
    if not isinstance(eligible, list) or any(item not in ELIGIBILITY for item in eligible):
        raise LicenseEvidenceError("eligible_for has an unknown use")
    if len(set(eligible)) != len(eligible):
        raise LicenseEvidenceError("eligible_for repeats a use")
    return evidence


def _check_rights_payload(payload: Mapping[str, Any]) -> None:
    _check_fields(payload, _RIGHTS_FIELDS, "RightsRecord")
    if payload.get("record_type") != "RightsRecord":
        raise SourceContentError("payload is not a RightsRecord")


def _check_fields(
    payload: Mapping[str, Any], allowed: frozenset[str], name: str
) -> None:
    if not isinstance(payload, dict):
        raise SourceContentError(f"{name} must be an object")
    extra = set(payload) - allowed
    if extra:
        raise SourceContentError(
            f"{name} has fields that are not metadata: {sorted(extra)}"
        )


def _check_https(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.startswith("https://") or len(value) > 500:
        raise LicenseEvidenceError(f"{field} must be an https URL")


def _check_time(value: object, field: str) -> None:
    if not isinstance(value, str) or _TIME.fullmatch(value) is None:
        raise LicenseEvidenceError(f"{field} must be an RFC3339 timestamp")


def _check_actor(actor: object) -> None:
    if not valid_actor(actor):
        raise LicenseEvidenceError("actor is missing or not a valid name")


def _matching_entry(
    inventory: Mapping[str, Any] | None, entry_id: object
) -> dict[str, Any]:
    if not isinstance(entry_id, str) or not entry_id.strip():
        raise LicenseEvidenceError("rights_cleared has no matching inventory row")
    entries = inventory.get("entries") if isinstance(inventory, Mapping) else None
    if not isinstance(entries, list):
        raise LicenseEvidenceError("rights_cleared has no matching inventory row")
    matches = [
        entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("id") == entry_id
    ]
    if len(matches) != 1:
        raise LicenseEvidenceError("rights_cleared has no matching inventory row")
    return matches[0]


def _units(entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    files = entry.get("files") or []
    functions = entry.get("functions") or []
    if not isinstance(files, list) or not isinstance(functions, list):
        raise LicenseEvidenceError(f"{entry.get('id')}: files must be a list")
    for item in files:
        if not isinstance(item, dict):
            raise LicenseEvidenceError(f"{entry.get('id')}: file entry must be an object")
        units.append({"path": item.get("path"), "blob_sha": item.get("blob_sha")})
    for item in functions:
        if not isinstance(item, dict):
            raise LicenseEvidenceError(f"{entry.get('id')}: function entry must be an object")
        units.append(
            {
                "path": item.get("path"),
                "blob_sha": item.get("blob_sha"),
                "function": item.get("function"),
            }
        )
    return units


def _unit_paths(entry: Mapping[str, Any]) -> list[str]:
    paths = [str(entry.get("path") or "")]
    paths.extend(str(unit.get("path") or "") for unit in _units(entry))
    return paths


def _check_units(entry: Mapping[str, Any], seen: set[tuple[str, str, str]]) -> None:
    if not isinstance(entry, dict):
        return
    entry_id = str(entry.get("id"))
    pin = entry.get("pin") if isinstance(entry.get("pin"), dict) else {}
    repo = str(pin.get("repo") or "")
    for unit in _units(entry):
        path = unit.get("path")
        blob = unit.get("blob_sha")
        function = unit.get("function") or ""
        if not isinstance(path, str) or not path or path.startswith("/"):
            raise LicenseEvidenceError(f"{entry_id}: unit path is missing")
        if not isinstance(blob, str) or _GIT_COMMIT.fullmatch(blob) is None:
            raise LicenseEvidenceError(f"{entry_id}: blob_sha is not a git blob id")
        if not isinstance(function, str):
            raise LicenseEvidenceError(f"{entry_id}: function name is not a string")
        key = (repo, path, function)
        if key in seen:
            raise LicenseEvidenceError(f"{entry_id}: {path} is already in another row")
        seen.add(key)
    if entry.get("decision") == "rights_cleared":
        units = _units(entry)
        if not units:
            raise LicenseEvidenceError(f"{entry_id}: a clearance lists no files")
        if entry.get("file_count") != len(units):
            raise LicenseEvidenceError(f"{entry_id}: file_count does not match the file list")


def _require_notice(entry: Mapping[str, Any], notice: Mapping[str, Any] | None) -> None:
    if not isinstance(notice, Mapping):
        raise LicenseEvidenceError("rights_cleared requires a notice manifest")
    rows = notice.get("entries")
    if not isinstance(rows, list):
        raise LicenseEvidenceError("rights_cleared requires a notice manifest")
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        index[(str(row.get("commit")), str(row.get("path")), str(row.get("function") or ""))] = row
    commit = str(entry["pin"]["commit"])
    entry_id = str(entry.get("id"))
    for unit in _units(entry):
        key = (commit, str(unit["path"]), str(unit.get("function") or ""))
        row = index.get(key)
        if row is None or row.get("blob_sha") != unit["blob_sha"]:
            raise LicenseEvidenceError(f"{entry_id}: notice manifest has no row for {key[1]}")
        if is_placeholder(row.get("copyright")):
            raise LicenseEvidenceError(f"{entry_id}: notice row has no copyright")
        if not same_license(str(row.get("license")), str(entry.get("license"))):
            raise LicenseEvidenceError(f"{entry_id}: notice license does not match the row")

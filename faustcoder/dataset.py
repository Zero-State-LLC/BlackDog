"""Dataset state machine for the transitions T06 owns (spec §7.1).

``rights_cleared`` and ``rights_rejected`` are not in this table and
this module does not execute them. Those edges belong to
``faustcoder.rights`` (T05). Calling them here raises
``TransitionNotImplemented`` and writes nothing.

T06 executes ``normalized``, ``normalize_failed``, ``dedup_passed`` and
``duplicate_or_leak_found``. ``split_frozen`` stays unimplemented.
``normalized`` requires a RightsRecord and a ``rights_cleared`` receipt
whose envelope producer is ``faustcoder.rights``.

Receipt envelopes use producer ``faustcoder.snapshot``, so they are not
T05 rights receipts. The receipt payload still uses machine ``dataset``
because that is the schema enum.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from faustcoder.canonical import build_envelope
from faustcoder.errors import (
    GuardError,
    IllegalTransitionError,
    TransitionNotImplemented,
)
from faustcoder.schemas import validate
from faustcoder.store import ArtifactStore

SCHEMA_VERSION = "0.3.0"
PRODUCER = "faustcoder.snapshot"
RIGHTS_PRODUCER = "faustcoder.rights"
RECEIPT_SCHEMA = "transition-receipt.schema.json"
RIGHTS_EVENTS = frozenset({"rights_cleared", "rights_rejected"})
MACHINE = "dataset"

INITIAL_STATE = "DISCOVERED"
STATES = frozenset(
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

_DIAGNOSTICS = frozenset(
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
class Transition:
    """One row of spec §7.1."""

    from_state: str
    event: str
    guard: str
    to_state: str
    effect: str
    implemented: bool


TRANSITIONS: tuple[Transition, ...] = (
    Transition(
        "RIGHTS_CLEARED",
        "normalized",
        "Deterministic transform succeeded",
        "NORMALIZED",
        "Write normalized Example as new node, parent = source; append receipt",
        True,
    ),
    Transition(
        "RIGHTS_CLEARED",
        "normalize_failed",
        "Transform error (INFERRED)",
        "QUARANTINED",
        "Append receipt with diagnostics (INFERRED)",
        True,
    ),
    Transition(
        "NORMALIZED",
        "dedup_passed",
        "No exact or near-duplicate family conflict; not in holdout family (R-003)",
        "DEDUPED",
        "Record duplicate-family id; append receipt",
        True,
    ),
    Transition(
        "NORMALIZED",
        "duplicate_or_leak_found",
        "Duplicate or holdout-contamination match (R-003)",
        "QUARANTINED",
        "Append exclusion receipt naming the conflicting family",
        True,
    ),
    Transition(
        "DEDUPED",
        "split_frozen",
        "SplitManifest assigns the item by project, near-duplicate family and provenance (R-003)",
        "FROZEN",
        "Write DatasetSnapshot and signed SplitManifest digests (KANBAN T07); append receipt",
        False,
    ),
)

_BY_EDGE = {(row.from_state, row.event): row for row in TRANSITIONS}


def lookup_transition(from_state: str, event: str) -> Transition | None:
    """Return the table row, or ``None`` when the edge is illegal."""
    return _BY_EDGE.get((from_state, event))


def receipt_payload(
    *,
    actor: str,
    timestamp: str,
    input_hashes: Sequence[str],
    from_state: str,
    event: str,
    to_state: str,
    disposition: str,
) -> dict[str, Any]:
    """Build and schema-check one transition receipt payload."""
    payload = {
        "actor": actor,
        "timestamp": timestamp,
        "input_hashes": sorted(set(input_hashes)),
        "machine": MACHINE,
        "from": from_state,
        "event": event,
        "to": to_state,
        "disposition": disposition,
    }
    validate(payload, RECEIPT_SCHEMA)
    return payload


def register_source(
    store: ArtifactStore,
    payload: Mapping[str, Any],
    *,
    created_at: str,
) -> dict[str, Any]:
    """Store one SourceRecord. The payload must not carry program text."""
    _check_source(payload)
    envelope = build_envelope(
        schema_version=SCHEMA_VERSION,
        created_at=created_at,
        producer=PRODUCER,
        parents=[],
        payload=dict(payload),
    )
    store.put(envelope)
    return envelope


def current_state(store: ArtifactStore, source: str) -> str:
    """Return the dataset state implied by receipts for ``source``."""
    source_envelope = store.get(source)
    _check_source(source_envelope["payload"])
    return _state_from_receipts(store, source_envelope["content_digest"])


def apply_transition(
    store: ArtifactStore,
    source: str,
    event: str,
    effect: Mapping[str, Any],
    *,
    actor: str,
    timestamp: str,
) -> dict[str, Any]:
    """Append one dataset transition, or raise without writing.

    ``timestamp`` is also the envelope ``created_at``. A repeated call
    from the new state is an illegal edge. The snapshot compiler does
    not use this function; it builds the same receipt payloads and puts
    the batch once, so a second compile with the same timestamp is an
    idempotent store put.
    """
    _check_actor(actor)
    source_envelope = store.get(source)
    _check_source(source_envelope["payload"])
    source_digest = source_envelope["content_digest"]
    state = _state_from_receipts(store, source_digest)
    if event in RIGHTS_EVENTS:
        raise TransitionNotImplemented(state, event)
    edge = lookup_transition(state, event)
    if edge is None:
        raise IllegalTransitionError(state, event)
    if not edge.implemented:
        raise TransitionNotImplemented(state, event)
    envelopes = _effect_envelopes(
        store,
        source_digest=source_digest,
        edge=edge,
        effect=effect,
        actor=actor,
        timestamp=timestamp,
    )
    for envelope in envelopes:
        store.put(envelope)
    return envelopes[-1]


def _effect_envelopes(
    store: ArtifactStore,
    *,
    source_digest: str,
    edge: Transition,
    effect: Mapping[str, Any],
    actor: str,
    timestamp: str,
) -> list[dict[str, Any]]:
    if edge.event == "normalized":
        return _normalized(store, source_digest, effect, actor, timestamp)
    if edge.event == "normalize_failed":
        return _normalize_failed(store, source_digest, effect, actor, timestamp)
    if edge.event == "dedup_passed":
        return _dedup(store, source_digest, effect, actor, timestamp, conflict=False)
    if edge.event == "duplicate_or_leak_found":
        return _dedup(store, source_digest, effect, actor, timestamp, conflict=True)
    raise TransitionNotImplemented(edge.from_state, edge.event)


def _normalized(
    store: ArtifactStore,
    source_digest: str,
    effect: Mapping[str, Any],
    actor: str,
    timestamp: str,
) -> list[dict[str, Any]]:
    text = effect.get("faust_source")
    if not isinstance(text, str) or text == "":
        raise GuardError("normalized requires the normalized source")
    normalized = _text(effect.get("normalized_sha256"), "normalized_sha256")
    from faustcoder.canonical import sha256_prefixed

    if sha256_prefixed(text.encode("utf-8")) != normalized:
        raise GuardError("normalized digest does not match the normalized text")
    family = _digest(effect.get("duplicate_family"), "duplicate_family")
    original = _digest(effect.get("original_sha256"), "original_sha256")
    blob_sha = _text(effect.get("blob_sha"), "blob_sha")
    unit_id = _text(effect.get("unit_id"), "unit_id")
    rights_digest, rights_receipt = _t05_rights(store, source_digest)
    example = {
        "record_type": "Example",
        "source_digest": source_digest,
        "faust_source": text,
        "duplicate_family": family,
        "unit_id": unit_id,
        "original_sha256": original,
        "normalized_sha256": normalized,
        "blob_sha": blob_sha,
    }
    example_envelope = _envelope(example, [source_digest, rights_digest], timestamp)
    receipt = _receipt_envelope(
        actor=actor,
        timestamp=timestamp,
        input_hashes=[
            source_digest,
            rights_digest,
            rights_receipt,
            example_envelope["content_digest"],
        ],
        from_state="RIGHTS_CLEARED",
        event="normalized",
        to_state="NORMALIZED",
        disposition="normalized",
        parents=[
            source_digest,
            rights_digest,
            rights_receipt,
            example_envelope["content_digest"],
        ],
    )
    return [example_envelope, receipt]


def _normalize_failed(
    store: ArtifactStore,
    source_digest: str,
    effect: Mapping[str, Any],
    actor: str,
    timestamp: str,
) -> list[dict[str, Any]]:
    diagnostics = effect.get("diagnostics")
    if diagnostics not in _DIAGNOSTICS:
        raise GuardError("normalize_failed diagnostics are not a known token")
    rights_digest, rights_receipt = _t05_rights(store, source_digest)
    receipt = _receipt_envelope(
        actor=actor,
        timestamp=timestamp,
        input_hashes=[source_digest, rights_digest, rights_receipt],
        from_state="RIGHTS_CLEARED",
        event="normalize_failed",
        to_state="QUARANTINED",
        disposition=f"normalize_failed: {diagnostics}",
        parents=[source_digest, rights_digest, rights_receipt],
    )
    return [receipt]


def _dedup(
    store: ArtifactStore,
    source_digest: str,
    effect: Mapping[str, Any],
    actor: str,
    timestamp: str,
    *,
    conflict: bool,
) -> list[dict[str, Any]]:
    family = _digest(effect.get("duplicate_family"), "duplicate_family")
    if bool(effect.get("conflict")) != conflict:
        raise GuardError("dedup conflict flag does not match the event")
    example = _example_for(store, source_digest)
    if example is None:
        raise GuardError("dedup requires the normalized example")
    if example["payload"].get("duplicate_family") != family:
        raise GuardError("duplicate family does not match the example")
    rights_digest, rights_receipt = _t05_rights(store, source_digest)
    normalize_receipt = _receipt_digest(store, source_digest, "normalized")
    if conflict:
        event = "duplicate_or_leak_found"
        to_state = "QUARANTINED"
        disposition = f"excluded: conflicting family {family}"
    else:
        event = "dedup_passed"
        to_state = "DEDUPED"
        disposition = f"duplicate_family={family}"
    parents = [
        source_digest,
        rights_digest,
        rights_receipt,
        example["content_digest"],
        normalize_receipt,
    ]
    receipt = _receipt_envelope(
        actor=actor,
        timestamp=timestamp,
        input_hashes=parents,
        from_state="NORMALIZED",
        event=event,
        to_state=to_state,
        disposition=disposition,
        parents=parents,
    )
    return [receipt]


def _t05_rights(store: ArtifactStore, source_digest: str) -> tuple[str, str]:
    """Return the T05 RightsRecord digest and the rights_cleared receipt digest."""
    receipts = [
        envelope
        for envelope in _receipts_for(store, source_digest)
        if envelope.get("producer") == RIGHTS_PRODUCER
        and envelope["payload"].get("event") == "rights_cleared"
    ]
    if len(receipts) != 1:
        raise GuardError("normalized requires a T05 rights receipt")
    receipt = receipts[0]
    found: list[str] = []
    for parent in receipt["parents"]:
        envelope = store.get(parent)
        payload = envelope["payload"]
        if (
            envelope.get("producer") == RIGHTS_PRODUCER
            and payload.get("record_type") == "RightsRecord"
        ):
            found.append(envelope["content_digest"])
    if len(found) != 1:
        raise GuardError("normalized requires a T05 RightsRecord")
    return found[0], receipt["content_digest"]


def _example_for(store: ArtifactStore, source_digest: str) -> dict[str, Any] | None:
    for artifact_id in store.list():
        envelope = store.get(artifact_id)
        payload = envelope["payload"]
        if (
            payload.get("record_type") == "Example"
            and payload.get("source_digest") == source_digest
        ):
            return envelope
    return None


def _receipt_digest(store: ArtifactStore, source_digest: str, event: str) -> str:
    found = [
        envelope["content_digest"]
        for envelope in _receipts_for(store, source_digest)
        if envelope["payload"].get("event") == event
    ]
    if len(found) != 1:
        raise GuardError(f"missing {event} receipt")
    return found[0]


def _state_from_receipts(store: ArtifactStore, source_digest: str) -> str:
    receipts = _receipts_for(store, source_digest)
    if not receipts:
        return INITIAL_STATE
    digests = {envelope["content_digest"] for envelope in receipts}
    heads = [
        envelope
        for envelope in receipts
        if not any(
            envelope["content_digest"] in other["parents"]
            for other in receipts
            if other["content_digest"] != envelope["content_digest"]
        )
    ]
    if len(heads) != 1:
        raise IllegalTransitionError(INITIAL_STATE, f"divergent receipts ({len(heads)})")
    state = heads[0]["payload"]["to"]
    if state not in STATES:
        raise IllegalTransitionError(str(state), "unknown-state")
    if heads[0]["content_digest"] not in digests:
        raise IllegalTransitionError(state, "unknown-state")
    return str(state)


def _receipts_for(store: ArtifactStore, source_digest: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for artifact_id in store.list():
        envelope = store.get(artifact_id)
        payload = envelope["payload"]
        if payload.get("machine") != MACHINE or "event" not in payload:
            continue
        validate(payload, RECEIPT_SCHEMA)
        if source_digest in payload["input_hashes"]:
            found.append(envelope)
    return found


def _receipt_envelope(
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


def _check_source(payload: Mapping[str, Any]) -> None:
    if payload.get("record_type") != "SourceRecord":
        raise GuardError("source record_type is not SourceRecord")
    required = {"record_type", "uri", "license_claim", "unit_id"}
    # ``retrieved_at`` is optional. The snapshot omits it so a re-sign
    # of the inventory does not change the source digest. The stepwise
    # API still accepts a source that carries the field.
    allowed = required | {"retrieved_at"}
    if not required <= set(payload) <= allowed:
        raise GuardError("source payload fields are not the source contract")
    for key in ("faust_source", "text", "bytes"):
        if key in payload:
            raise GuardError("source payload carries program text")
    for key in ("uri", "license_claim", "unit_id"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise GuardError(f"source {key} is missing")
    if "retrieved_at" in payload and (
        not isinstance(payload.get("retrieved_at"), str) or not payload["retrieved_at"]
    ):
        raise GuardError("source retrieved_at is missing")


def _check_actor(actor: object) -> None:
    if not isinstance(actor, str) or not actor.strip() or any(ord(char) < 32 for char in actor):
        raise GuardError("actor is missing")


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GuardError(f"{field} is missing")
    return value


def _digest(value: object, field: str) -> str:
    text = _text(value, field)
    if len(text) != 7 + 64 or not text.startswith("sha256:"):
        raise GuardError(f"{field} is not a sha256 digest")
    hex_part = text.split(":", 1)[1]
    if any(char not in "0123456789abcdef" for char in hex_part):
        raise GuardError(f"{field} is not a sha256 digest")
    return text

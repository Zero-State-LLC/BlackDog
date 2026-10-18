"""Dataset machine against spec §7.1. Rights edges belong to T05."""

from __future__ import annotations

from pathlib import Path

import pytest

from faustcoder.canonical import build_envelope, sha256_prefixed
from faustcoder.dataset import (
    PRODUCER,
    RIGHTS_PRODUCER,
    SCHEMA_VERSION,
    TRANSITIONS,
    apply_transition,
    current_state,
    receipt_payload,
    register_source,
)
from faustcoder.errors import (
    GuardError,
    IllegalTransitionError,
    TransitionNotImplemented,
)
from faustcoder.store import ArtifactStore

TS = "2026-10-17T20:00:00Z"
ACTOR = "snapshot-bot"
TEXT = "process = 1;"
FAMILY = sha256_prefixed(b"family")
RIGHTS_EVENTS = frozenset({"rights_cleared", "rights_rejected"})


def _source(store: ArtifactStore, *, license_claim: str = "MIT", unit_id: str = "osc") -> str:
    envelope = register_source(
        store,
        {
            "record_type": "SourceRecord",
            "uri": "https://github.com/acme/widgets/blob/" + "a" * 40 + f"/{unit_id}.dsp#unit={unit_id}",
            "retrieved_at": "2026-10-17T13:04:00Z",
            "license_claim": license_claim,
            "unit_id": unit_id,
        },
        created_at=TS,
    )
    return envelope["content_digest"]


def _seed_t05(store: ArtifactStore, source: str, *, license_name: str = "MIT") -> None:
    """Write one T05 clearance. T06 does not mint this receipt."""
    rights = build_envelope(
        schema_version=SCHEMA_VERSION,
        created_at=TS,
        producer=RIGHTS_PRODUCER,
        parents=[],
        payload={
            "record_type": "RightsRecord",
            "license": license_name,
            "eligible_for": ["train", "eval", "redistribute"],
            "attribution": "Acme Example",
            "reviewer": "Boof (delegated by Danny 2026-10-17)",
        },
    )
    store.put(rights)
    payload = receipt_payload(
        actor="rights-bot",
        timestamp=TS,
        input_hashes=[source],
        from_state="DISCOVERED",
        event="rights_cleared",
        to_state="RIGHTS_CLEARED",
        disposition=f"cleared: {license_name}",
    )
    receipt = build_envelope(
        schema_version=SCHEMA_VERSION,
        created_at=TS,
        producer=RIGHTS_PRODUCER,
        parents=[rights["content_digest"]],
        payload=payload,
    )
    store.put(receipt)


def _normalized(store: ArtifactStore, source: str) -> None:
    apply_transition(
        store,
        source,
        "normalized",
        {
            "faust_source": TEXT,
            "normalized_sha256": sha256_prefixed(TEXT.encode()),
            "original_sha256": sha256_prefixed(b"process = 1;\n"),
            "duplicate_family": FAMILY,
            "blob_sha": "b" * 40,
            "unit_id": "osc",
        },
        actor=ACTOR,
        timestamp=TS,
    )


def _spec_rows() -> list[tuple[str, ...]]:
    text = Path("specs/001-faustcoder/spec.md").read_text(encoding="utf-8")
    start = text.index("### 7.1 Dataset item lifecycle")
    end = text.index("Illegal transitions:", start)
    rows = []
    for line in text[start:end].splitlines():
        if not line.startswith("| ") or line.startswith("| From") or line.startswith("|---"):
            continue
        rows.append(tuple(cell.strip() for cell in line.strip().strip("|").split("|")))
    return rows


def test_transition_table_omits_the_rights_edges() -> None:
    rows = _spec_rows()
    owned = [row for row in rows if row[1] not in RIGHTS_EVENTS]
    assert owned == [
        (row.from_state, row.event, row.guard, row.to_state, row.effect) for row in TRANSITIONS
    ]
    assert {row[1] for row in rows} >= RIGHTS_EVENTS
    assert {row.event for row in TRANSITIONS}.isdisjoint(RIGHTS_EVENTS)
    assert TRANSITIONS[-1].event == "split_frozen"
    assert TRANSITIONS[-1].implemented is False
    assert all(row.implemented for row in TRANSITIONS[:-1])


def test_runbook_carries_the_table_and_diagram() -> None:
    runbook = Path("docs/runbooks/t06-normalize-dedup.md").read_text(encoding="utf-8")
    assert "| From | Event | Guard | To | Effect |" in runbook
    assert "stateDiagram-v2" in runbook
    assert "rights_cleared" in runbook
    assert "split_frozen" in runbook


def test_t06_does_not_clear_rights(store: ArtifactStore) -> None:
    """The adversary probe: a GPL claim cannot be rewritten as MIT here."""
    source = _source(store, license_claim="GPL-2.0-or-later", unit_id="guitarix")
    before = store.list()
    with pytest.raises(TransitionNotImplemented):
        apply_transition(
            store,
            source,
            "rights_cleared",
            {
                "license": "MIT",
                "attribution": "abc",
                "eligible_for": ["train", "eval", "redistribute"],
                "reviewer": "abc",
                "unit_id": "made-up",
            },
            actor="bot",
            timestamp=TS,
        )
    assert store.list() == before
    assert current_state(store, source) == "DISCOVERED"
    with pytest.raises(TransitionNotImplemented):
        apply_transition(
            store,
            source,
            "rights_rejected",
            {"license": "GPL-2.0-or-later", "reason": "agpl"},
            actor=ACTOR,
            timestamp=TS,
        )
    assert store.list() == before


def test_legal_path_stops_before_split_frozen(store: ArtifactStore) -> None:
    source = _source(store)
    assert current_state(store, source) == "DISCOVERED"
    _seed_t05(store, source)
    assert current_state(store, source) == "RIGHTS_CLEARED"
    _normalized(store, source)
    assert current_state(store, source) == "NORMALIZED"
    apply_transition(
        store,
        source,
        "dedup_passed",
        {"duplicate_family": FAMILY, "conflict": False},
        actor=ACTOR,
        timestamp=TS,
    )
    assert current_state(store, source) == "DEDUPED"
    producers = {
        store.get(artifact_id)["producer"]
        for artifact_id in store.list()
        if store.get(artifact_id)["payload"].get("machine") == "dataset"
    }
    assert PRODUCER in producers
    assert RIGHTS_PRODUCER in producers
    t06 = [
        store.get(artifact_id)
        for artifact_id in store.list()
        if store.get(artifact_id)["payload"].get("event") == "dedup_passed"
    ]
    assert t06[0]["producer"] == PRODUCER
    before = store.list()
    with pytest.raises(TransitionNotImplemented):
        apply_transition(
            store,
            source,
            "split_frozen",
            {},
            actor=ACTOR,
            timestamp=TS,
        )
    assert store.list() == before
    assert current_state(store, source) == "DEDUPED"


def test_rights_cannot_be_skipped_and_a_snapshot_receipt_is_not_t05(
    store: ArtifactStore,
) -> None:
    source = _source(store)
    before = store.list()
    with pytest.raises(IllegalTransitionError):
        apply_transition(
            store,
            source,
            "normalized",
            {"faust_source": TEXT},
            actor=ACTOR,
            timestamp=TS,
        )
    assert store.list() == before
    forged = build_envelope(
        schema_version=SCHEMA_VERSION,
        created_at=TS,
        producer=PRODUCER,
        parents=[],
        payload=receipt_payload(
            actor=ACTOR,
            timestamp=TS,
            input_hashes=[source],
            from_state="DISCOVERED",
            event="rights_cleared",
            to_state="RIGHTS_CLEARED",
            disposition="cleared: MIT",
        ),
    )
    store.put(forged)
    with pytest.raises(GuardError, match="T05"):
        _normalized(store, source)
    assert current_state(store, source) == "RIGHTS_CLEARED"
    examples = [
        artifact_id
        for artifact_id in store.list()
        if store.get(artifact_id)["payload"].get("record_type") == "Example"
    ]
    assert examples == []


def test_normalize_failed_quarantines_without_program_text(store: ArtifactStore) -> None:
    source = _source(store)
    _seed_t05(store, source)
    apply_transition(
        store,
        source,
        "normalize_failed",
        {"diagnostics": "empty"},
        actor=ACTOR,
        timestamp=TS,
    )
    assert current_state(store, source) == "QUARANTINED"
    for artifact_id in store.list():
        payload = store.get(artifact_id)["payload"]
        assert "faust_source" not in payload
        assert payload.get("disposition", "").find("process") == -1
        if payload.get("event") == "normalize_failed":
            assert store.get(artifact_id)["producer"] == PRODUCER


def test_duplicate_or_leak_found_names_the_family(store: ArtifactStore) -> None:
    source = _source(store)
    _seed_t05(store, source)
    _normalized(store, source)
    apply_transition(
        store,
        source,
        "duplicate_or_leak_found",
        {"duplicate_family": FAMILY, "conflict": True},
        actor=ACTOR,
        timestamp=TS,
    )
    assert current_state(store, source) == "QUARANTINED"
    receipts = [
        store.get(artifact_id)["payload"]
        for artifact_id in store.list()
        if store.get(artifact_id)["payload"].get("event") == "duplicate_or_leak_found"
    ]
    assert receipts[0]["disposition"] == f"excluded: conflicting family {FAMILY}"

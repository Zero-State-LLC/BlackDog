"""Dataset machine against spec §7.1. split_frozen is not executed."""

from __future__ import annotations

from pathlib import Path

import pytest

from faustcoder.canonical import sha256_prefixed
from faustcoder.dataset import (
    TRANSITIONS,
    apply_transition,
    current_state,
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


def _source(store: ArtifactStore) -> str:
    envelope = register_source(
        store,
        {
            "record_type": "SourceRecord",
            "uri": "https://github.com/acme/widgets/blob/" + "a" * 40 + "/osc.dsp#unit=osc",
            "retrieved_at": "2026-10-17T13:04:00Z",
            "license_claim": "MIT",
            "unit_id": "osc",
        },
        created_at=TS,
    )
    return envelope["content_digest"]


def _rights(store: ArtifactStore, source: str) -> None:
    apply_transition(
        store,
        source,
        "rights_cleared",
        {
            "license": "MIT",
            "attribution": "Acme Example",
            "eligible_for": ["train", "eval", "redistribute"],
            "reviewer": "Danny",
            "unit_id": "osc",
        },
        actor=ACTOR,
        timestamp=TS,
    )


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


def test_transition_table_matches_spec() -> None:
    text = Path("specs/001-faustcoder/spec.md").read_text(encoding="utf-8")
    start = text.index("### 7.1 Dataset item lifecycle")
    end = text.index("Illegal transitions:", start)
    rows = []
    for line in text[start:end].splitlines():
        if not line.startswith("| ") or line.startswith("| From") or line.startswith("|---"):
            continue
        rows.append(tuple(cell.strip() for cell in line.strip().strip("|").split("|")))
    assert rows == [
        (row.from_state, row.event, row.guard, row.to_state, row.effect) for row in TRANSITIONS
    ]
    assert TRANSITIONS[-1].implemented is False
    assert all(row.implemented for row in TRANSITIONS[:-1])


def test_runbook_carries_the_table_and_diagram() -> None:
    runbook = Path("docs/runbooks/t06-normalize-dedup.md").read_text(encoding="utf-8")
    assert "| From | Event | Guard | To | Effect |" in runbook
    assert "stateDiagram-v2" in runbook
    assert "rights_cleared" in runbook
    assert "split_frozen" in runbook


def test_legal_path_stops_before_split_frozen(store: ArtifactStore) -> None:
    source = _source(store)
    assert current_state(store, source) == "DISCOVERED"
    _rights(store, source)
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


def test_rights_cannot_be_skipped_and_a_failed_guard_writes_nothing(store: ArtifactStore) -> None:
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
    with pytest.raises(GuardError):
        apply_transition(
            store,
            source,
            "rights_cleared",
            {
                "license": "AGPL-3.0-only",
                "attribution": "Acme Example",
                "eligible_for": ["train"],
                "reviewer": "Danny",
                "unit_id": "osc",
            },
            actor=ACTOR,
            timestamp=TS,
        )
    assert store.list() == before
    assert current_state(store, source) == "DISCOVERED"


def test_rights_rejected_and_normalize_failed_quarantine_without_program_text(
    store: ArtifactStore,
) -> None:
    rejected = register_source(
        store,
        {
            "record_type": "SourceRecord",
            "uri": "https://github.com/acme/widgets/blob/" + "a" * 40 + "/agpl.dsp#unit=agpl",
            "retrieved_at": "2026-10-17T13:04:00Z",
            "license_claim": "AGPL-3.0-only",
            "unit_id": "agpl",
        },
        created_at=TS,
    )
    apply_transition(
        store,
        rejected["content_digest"],
        "rights_rejected",
        {"license": "AGPL-3.0-only", "reason": "agpl"},
        actor=ACTOR,
        timestamp=TS,
    )
    assert current_state(store, rejected["content_digest"]) == "QUARANTINED"
    with pytest.raises(IllegalTransitionError):
        apply_transition(
            store,
            rejected["content_digest"],
            "rights_cleared",
            {
                "license": "MIT",
                "attribution": "Acme Example",
                "eligible_for": ["train"],
                "reviewer": "Danny",
                "unit_id": "agpl",
            },
            actor=ACTOR,
            timestamp=TS,
        )
    source = _source(store)
    _rights(store, source)
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


def test_duplicate_or_leak_found_names_the_family(store: ArtifactStore) -> None:
    source = _source(store)
    _rights(store, source)
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

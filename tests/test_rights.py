"""Dataset rights transitions and the T05 source inventory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from faustcoder import (
    IllegalTransitionError,
    LicenseEvidenceError,
    NeedsHumanDecision,
    SourceContentError,
    TransitionNotImplemented,
    apply_transition,
    canonical_bytes,
    classify_license,
    digest_hex,
    envelope_digest_for,
    load_inventory,
    register_source,
)
from faustcoder.rights import DATASET_EVENTS, FINAL_STATES, TRANSITIONS, current_state
from faustcoder.schemas import validate
from faustcoder.store import ArtifactStore
from tests.support import make_envelope

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "corpus" / "rights-inventory.v1.json"
WHEN = "2026-10-17T00:00:00Z"
ACTOR = "t05-test"
COMMIT = "a" * 40
BLOB = "b" * 40


def _source(
    claim: str = "MIT",
    commit: str = COMMIT,
    path: str = "example.dsp",
    blob: str = BLOB,
    function: str = "",
    repo: str = "example/faust",
) -> dict:
    fragment = f"#{function}" if function else ""
    payload = {
        "record_type": "SourceRecord",
        "uri": f"https://github.com/{repo}/blob/{commit}/{path}{fragment}",
        "retrieved_at": WHEN,
        "license_claim": claim,
    }
    if blob:
        payload["blob_sha"] = blob
    return payload


def _evidence(license_name: str = "MIT", **overrides: object) -> dict:
    payload: dict = {
        "record_type": "LicenseEvidence",
        "license": license_name,
        "evidence_label": "OBSERVED",
        "evidence_uri": "https://example.com/LICENSE",
        "attribution": "Copyright 2020 Example Author",
        "eligible_for": ["train", "eval", "redistribute"],
        "reason": "D-004 allowlist",
        "inventory_id": "row-1",
    }
    payload.update(overrides)
    return payload


def _clearance(license_name: str = "MIT", **evidence_overrides: object) -> tuple[dict, dict, dict]:
    evidence = _evidence(license_name, **evidence_overrides)
    entry = {
        "id": "row-1",
        "decision": "rights_cleared",
        "license": evidence["license"],
        "evidence_label": evidence["evidence_label"],
        "eligible_for": evidence["eligible_for"],
        "attribution_complete": True,
        "pin": {"repo": "example/faust", "commit": COMMIT, "ref": "test"},
        "path": "example.dsp",
        "reviewer": evidence.get("reviewer"),
        "redistribute": "redistribute" in evidence["eligible_for"],
        "files": [{"path": "example.dsp", "blob_sha": BLOB}],
    }
    notice = {
        "entries": [
            {
                "commit": COMMIT,
                "path": "example.dsp",
                "blob_sha": BLOB,
                "function": None,
                "copyright": evidence["attribution"],
                "license": evidence["license"],
            }
        ]
    }
    return {"entries": [entry]}, notice, evidence


def _register(store: ArtifactStore, claim: str = "MIT") -> dict:
    return register_source(store, _source(claim), created_at=WHEN)


def _assert_receipt_digest(store: ArtifactStore, artifact_id: str) -> dict:
    stored = store.get(artifact_id)
    assert stored["artifact_id"] == digest_hex(stored["payload"])
    assert stored["content_digest"] == "sha256:" + stored["artifact_id"]
    raw = store.path_for(artifact_id).read_bytes()
    assert raw == canonical_bytes(stored)
    sidecar = store.envelope_digest_path_for(artifact_id).read_bytes()
    assert sidecar == envelope_digest_for(raw).encode("ascii")
    validate(stored["payload"], "transition-receipt.schema.json")
    return stored


def test_table_matches_the_spec_events() -> None:
    assert {row.event for row in TRANSITIONS} == DATASET_EVENTS
    implemented = {row.event for row in TRANSITIONS if row.implemented}
    assert implemented == {"rights_cleared", "rights_rejected"}
    assert TRANSITIONS[0].from_state == "DISCOVERED"
    assert TRANSITIONS[0].to_state == "RIGHTS_CLEARED"
    assert FINAL_STATES == frozenset({"FROZEN", "QUARANTINED"})


def test_classify_allowlist_copyleft_and_unknown() -> None:
    mit = classify_license("MIT")
    assert mit.decision == "rights_cleared"
    assert mit.eligible_for == ("train", "eval", "redistribute")
    gpl = classify_license("GPL v3")
    assert gpl.decision == "rights_cleared"
    assert gpl.eligible_for == ("train",)
    assert classify_license("AGPL-3.0-only").decision == "rights_rejected"
    assert classify_license("unlicensed").decision == "rights_rejected"
    assert classify_license("CC-BY-NC-SA-4.0").decision == "rights_rejected"
    stk = classify_license("STK-4.3")
    assert stk.decision == "rights_cleared"
    assert stk.redistribute is True
    bare = classify_license("BSD")
    assert bare.eligible_for == ("train", "eval")
    assert bare.redistribute is False
    assert classify_license("mixed").decision == "needs_human"


def test_rights_cleared_writes_rights_record_and_receipt(store: ArtifactStore) -> None:
    source = _register(store)
    inventory, notice, evidence = _clearance()
    result = apply_transition(
        store,
        source["content_digest"],
        "rights_cleared",
        evidence,
        actor=ACTOR,
        timestamp=WHEN,
        inventory=inventory,
        notice=notice,
    )
    assert result.state == "RIGHTS_CLEARED"
    assert current_state(store, source["artifact_id"]) == "RIGHTS_CLEARED"
    receipt = _assert_receipt_digest(store, result.receipt["artifact_id"])
    assert receipt["payload"]["from"] == "DISCOVERED"
    assert receipt["payload"]["event"] == "rights_cleared"
    assert receipt["payload"]["to"] == "RIGHTS_CLEARED"
    assert receipt["payload"]["disposition"].startswith("cleared: MIT:")
    assert source["content_digest"] in receipt["payload"]["input_hashes"]
    rights = store.get(result.rights_record_id or "")
    assert rights["payload"]["record_type"] == "RightsRecord"
    assert rights["payload"]["eligible_for"] == ["train", "eval", "redistribute"]
    assert rights["payload"]["reviewer"] == ACTOR
    assert source["content_digest"] in rights["parents"]
    assert store.get(source["artifact_id"])["payload"] == source["payload"]


def test_rights_rejected_writes_exclusion_receipt_without_copying_source(
    store: ArtifactStore,
) -> None:
    source = _register(store, "unlicensed")
    before = store.get(source["artifact_id"])["payload"]
    result = apply_transition(
        store,
        source["artifact_id"],
        "rights_rejected",
        _evidence(
            "unlicensed",
            attribution="none stated",
            eligible_for=[],
            reason="D-004 excludes unlicensed code",
        ),
        actor=ACTOR,
        timestamp=WHEN,
    )
    assert result.state == "QUARANTINED"
    assert result.rights_record_id is None
    receipt = _assert_receipt_digest(store, result.receipt["artifact_id"])
    assert receipt["payload"]["disposition"] == "excluded: D-004 excludes unlicensed code"
    assert receipt["payload"]["to"] == "QUARANTINED"
    kinds = [store.get(item)["payload"].get("record_type") for item in store.list()]
    assert "RightsRecord" not in kinds
    assert store.get(source["artifact_id"])["payload"] == before
    for item in store.list():
        payload = store.get(item)["payload"]
        assert "faust_source" not in payload
        joined = " ".join(str(value) for value in payload.values())
        assert "process =" not in joined


def test_gpl_clearance_cannot_claim_redistribution(store: ArtifactStore) -> None:
    source = _register(store, "GPL v3")
    wide_inventory, wide_notice, wide = _clearance(
        "GPL v3", reason="training only"
    )
    with pytest.raises(LicenseEvidenceError, match="eligible_for"):
        apply_transition(
            store,
            source["artifact_id"],
            "rights_cleared",
            wide,
            actor=ACTOR,
            timestamp=WHEN,
            inventory=wide_inventory,
            notice=wide_notice,
        )
    assert store.list() == [source["artifact_id"]]
    inventory, notice, evidence = _clearance(
        "GPL v3", eligible_for=["train"], reason="training only"
    )
    result = apply_transition(
        store,
        source["artifact_id"],
        "rights_cleared",
        evidence,
        actor=ACTOR,
        timestamp=WHEN,
        inventory=inventory,
        notice=notice,
    )
    assert result.state == "RIGHTS_CLEARED"
    rights = store.get(result.rights_record_id or "")
    assert rights["payload"]["eligible_for"] == ["train"]


def test_no_transition_without_license_evidence(store: ArtifactStore) -> None:
    source = _register(store)
    with pytest.raises(LicenseEvidenceError):
        apply_transition(
            store,
            source["artifact_id"],
            "rights_cleared",
            _evidence(evidence_label="SPECULATIVE"),
            actor=ACTOR,
            timestamp=WHEN,
        )
    with pytest.raises(LicenseEvidenceError):
        apply_transition(
            store,
            source["artifact_id"],
            "rights_cleared",
            _evidence(attribution=""),
            actor=ACTOR,
            timestamp=WHEN,
        )
    with pytest.raises(NeedsHumanDecision):
        apply_transition(
            store,
            source["artifact_id"],
            "rights_cleared",
            _evidence("STK-4.3", eligible_for=[], reason="STK is not an accepted name"),
            actor=ACTOR,
            timestamp=WHEN,
        )
    assert current_state(store, source["artifact_id"]) == "DISCOVERED"
    assert store.list() == [source["artifact_id"]]


def test_illegal_and_unimplemented_transitions_write_nothing(
    store: ArtifactStore,
) -> None:
    source = _register(store)
    for event in ("normalized", "dedup_passed", "split_frozen", "normalize_failed"):
        with pytest.raises(IllegalTransitionError):
            apply_transition(
                store,
                source["artifact_id"],
                event,
                _evidence(),
                actor=ACTOR,
                timestamp=WHEN,
            )
    assert store.list() == [source["artifact_id"]]
    inventory, notice, evidence = _clearance()
    cleared = apply_transition(
        store,
        source["artifact_id"],
        "rights_cleared",
        evidence,
        actor=ACTOR,
        timestamp=WHEN,
        inventory=inventory,
        notice=notice,
    )
    existing = set(store.list())
    with pytest.raises(TransitionNotImplemented):
        apply_transition(
            store,
            source["artifact_id"],
            "normalized",
            _evidence(),
            actor=ACTOR,
            timestamp=WHEN,
        )
    with pytest.raises(IllegalTransitionError):
        apply_transition(
            store,
            source["artifact_id"],
            "rights_rejected",
            _evidence("unlicensed", eligible_for=[], reason="too late"),
            actor=ACTOR,
            timestamp=WHEN,
        )
    assert set(store.list()) == existing
    assert current_state(store, source["artifact_id"]) == cleared.state


def test_quarantine_and_frozen_are_final(store: ArtifactStore) -> None:
    source = _register(store, "AGPL-3.0-only")
    apply_transition(
        store,
        source["artifact_id"],
        "rights_rejected",
        _evidence(
            "AGPL-3.0-only",
            eligible_for=[],
            reason="D-007 excludes AGPL",
        ),
        actor=ACTOR,
        timestamp=WHEN,
    )
    with pytest.raises(IllegalTransitionError):
        apply_transition(
            store,
            source["artifact_id"],
            "rights_cleared",
            _evidence(),
            actor=ACTOR,
            timestamp=WHEN,
        )

    frozen_source = _register(store, "MIT frozen")
    receipt = {
        "actor": ACTOR,
        "timestamp": WHEN,
        "input_hashes": [frozen_source["content_digest"]],
        "machine": "dataset",
        "from": "DEDUPED",
        "event": "split_frozen",
        "to": "FROZEN",
        "disposition": "frozen by test",
    }
    validate(receipt, "transition-receipt.schema.json")
    envelope = make_envelope(
        receipt,
        parents=[frozen_source["content_digest"]],
        producer="t05-test",
    )
    store.put(envelope)
    assert current_state(store, frozen_source["artifact_id"]) == "FROZEN"
    with pytest.raises(IllegalTransitionError):
        apply_transition(
            store,
            frozen_source["artifact_id"],
            "rights_rejected",
            _evidence("unlicensed", eligible_for=[], reason="frozen"),
            actor=ACTOR,
            timestamp=WHEN,
        )


def test_divergent_receipts_are_refused(store: ArtifactStore) -> None:
    source = _register(store)
    for name in ("one", "two"):
        payload = {
            "actor": ACTOR,
            "timestamp": WHEN,
            "input_hashes": [source["content_digest"]],
            "machine": "dataset",
            "from": "DISCOVERED",
            "event": "rights_cleared",
            "to": "RIGHTS_CLEARED",
            "disposition": name,
        }
        store.put(
            make_envelope(payload, parents=[source["content_digest"]], producer="t05-test")
        )
    with pytest.raises(IllegalTransitionError, match="divergent"):
        current_state(store, source["artifact_id"])


def test_source_payload_rejects_program_text(store: ArtifactStore) -> None:
    payload = _source()
    payload["faust_source"] = "not stored"
    with pytest.raises(SourceContentError):
        register_source(store, payload, created_at=WHEN)
    assert store.list() == []


def _entry(inventory: dict, entry_id: str) -> dict:
    return next(item for item in inventory["entries"] if item["id"] == entry_id)


def _row_evidence(entry: dict, **overrides: object) -> dict:
    payload: dict = {
        "record_type": "LicenseEvidence",
        "license": entry["license"],
        "evidence_label": entry["evidence_label"],
        "evidence_uri": entry["evidence_uri"],
        "attribution": entry["attribution"],
        "eligible_for": list(entry["eligible_for"]),
        "reason": entry["reason"],
        "inventory_id": entry["id"],
    }
    if entry.get("reviewer"):
        payload["reviewer"] = entry["reviewer"]
    payload.update(overrides)
    return payload


def _refuse_clearance(
    store: ArtifactStore,
    inventory: dict,
    notice: dict,
    row: dict,
    unit: dict,
    claim: str,
    *,
    repo: str | None = None,
    match: str = "source path is not a unit",
) -> None:
    source = register_source(
        store,
        _source(
            claim,
            commit=row["pin"]["commit"],
            path=unit["path"],
            blob=unit["blob_sha"],
            function=str(unit.get("function") or ""),
            repo=repo or row["pin"]["repo"],
        ),
        created_at=WHEN,
    )
    before = set(store.list())
    with pytest.raises(LicenseEvidenceError, match=match):
        apply_transition(
            store,
            source["artifact_id"],
            "rights_cleared",
            _row_evidence(row),
            actor="t05-inventory",
            timestamp=WHEN,
            inventory=inventory,
            notice=notice,
        )
    assert set(store.list()) == before
    assert current_state(store, source["artifact_id"]) == "DISCOVERED"


def test_inventory_rows_match_policy_and_transition(store: ArtifactStore) -> None:
    inventory = load_inventory(INVENTORY)
    counts = {"rights_cleared": 0, "rights_rejected": 0, "needs_human": 0}
    for entry in inventory["entries"]:
        counts[entry["decision"]] += 1
        if entry["decision"] == "rights_cleared":
            units = list(entry.get("files") or []) + list(entry.get("functions") or [])
            unit = units[0]
            payload = _source(
                entry["license"][:400],
                commit=entry["pin"]["commit"],
                path=unit["path"],
                blob=unit["blob_sha"],
                function=str(unit.get("function") or ""),
                repo=entry["pin"]["repo"],
            )
        else:
            payload = {
                "record_type": "SourceRecord",
                "uri": entry["url"].rstrip("/") + "/" + entry["id"],
                "retrieved_at": WHEN,
                "license_claim": entry["license"][:400],
            }
        source = register_source(
            store,
            payload,
            created_at=WHEN,
        )
        evidence = {
            "record_type": "LicenseEvidence",
            "license": entry["license"],
            "evidence_label": entry["evidence_label"],
            "evidence_uri": entry["evidence_uri"],
            "attribution": entry["attribution"],
            "eligible_for": entry["eligible_for"],
            "reason": entry["reason"],
            "inventory_id": entry["id"],
        }
        if entry.get("reviewer"):
            evidence["reviewer"] = entry["reviewer"]
        notice = json.loads((ROOT / "corpus" / "notice-manifest.v1.json").read_text())
        if entry["decision"] == "rights_cleared":
            result = apply_transition(
                store,
                source["artifact_id"],
                "rights_cleared",
                evidence,
                actor="t05-inventory",
                timestamp=WHEN,
                inventory=inventory,
                notice=notice,
            )
            assert result.state == "RIGHTS_CLEARED"
            _assert_receipt_digest(store, result.receipt["artifact_id"])
            assert result.rights_record_id is not None
        elif entry["decision"] == "rights_rejected":
            result = apply_transition(
                store,
                source["artifact_id"],
                "rights_rejected",
                evidence,
                actor="t05-inventory",
                timestamp=WHEN,
            )
            assert result.state == "QUARANTINED"
            receipt = _assert_receipt_digest(store, result.receipt["artifact_id"])
            assert receipt["payload"]["disposition"].startswith("excluded:")
            assert result.rights_record_id is None
        else:
            before = set(store.list())
            with pytest.raises((NeedsHumanDecision, LicenseEvidenceError)):
                apply_transition(
                    store,
                    source["artifact_id"],
                    "rights_cleared",
                    evidence,
                    actor="t05-inventory",
                    timestamp=WHEN,
                )
            assert set(store.list()) == before
            assert current_state(store, source["artifact_id"]) == "DISCOVERED"
    assert counts == {
        "rights_cleared": 31,
        "rights_rejected": 14,
        "needs_human": 2,
    }


def test_inventory_and_docs_name_every_row() -> None:
    inventory = load_inventory(INVENTORY)
    summary = (ROOT / "docs" / "rights-inventory.md").read_text(encoding="utf-8")
    machine = (ROOT / "docs" / "dataset-lifecycle.md").read_text(encoding="utf-8")
    counts = {"rights_cleared": 0, "rights_rejected": 0, "needs_human": 0}
    for entry in inventory["entries"]:
        counts[entry["decision"]] += 1
    assert "stateDiagram-v2" in machine
    assert "| From | Event | Guard | To | Effect |" in machine
    for row in TRANSITIONS:
        assert f"| {row.from_state} | {row.event} |" in machine
    assert f"**{counts['rights_cleared']} cleared**" in summary
    assert f"**{counts['rights_rejected']} rejected**" in summary
    assert f"**{counts['needs_human']} need a human**" in summary
    for entry in inventory["entries"]:
        assert entry["id"] in summary
    blob = INVENTORY.read_text(encoding="utf-8")
    assert "process =" not in blob
    assert "import(" not in blob


def test_adversary_probe_cannot_clear(store: ArtifactStore) -> None:
    """The review probe: mutable URL, mismatched license, inferred, n/a, actor x."""
    source = register_source(
        store,
        {
            "record_type": "SourceRecord",
            "uri": "https://github.com/grame-cncm/faust/tree/main/examples/foo.dsp",
            "retrieved_at": WHEN,
            "license_claim": "MIT",
        },
        created_at=WHEN,
    )
    with pytest.raises((LicenseEvidenceError, NeedsHumanDecision)):
        apply_transition(
            store,
            source["artifact_id"],
            "rights_cleared",
            _evidence(
                "GPL",
                evidence_label="INFERRED",
                evidence_uri="https://example.com/LICENSE",
                attribution="n/a",
                eligible_for=["train"],
                reason="self asserted",
                inventory_id="missing",
            ),
            actor="x",
            timestamp=WHEN,
        )
    assert current_state(store, source["artifact_id"]) == "DISCOVERED"
    assert store.list() == [source["artifact_id"]]


def test_clearance_rejects_each_evidence_mismatch(store: ArtifactStore) -> None:
    source = _register(store)
    inventory, notice, evidence = _clearance()
    cases = [
        ("actor", {}, None, "x"),
        ("uri", {}, _source("MIT", commit="main"), ACTOR),
        ("attribution", {"attribution": "n/a"}, None, ACTOR),
        ("license", {"license": "GPL"}, None, ACTOR),
        ("inventory", {"inventory_id": "missing"}, None, ACTOR),
        ("reviewer", {"evidence_label": "INFERRED", "reviewer": None}, None, ACTOR),
    ]
    for _name, overrides, replacement, actor in cases:
        payload = dict(evidence)
        payload.update(overrides)
        used = source
        if replacement is not None:
            used = register_source(store, replacement, created_at=WHEN)
        with pytest.raises((LicenseEvidenceError, NeedsHumanDecision)):
            apply_transition(
                store,
                used["artifact_id"],
                "rights_cleared",
                payload,
                actor=actor,
                timestamp=WHEN,
                inventory=inventory,
                notice=notice,
            )
        assert current_state(store, used["artifact_id"]) == "DISCOVERED"
    refused = dict(inventory)
    refused["entries"] = [dict(inventory["entries"][0], decision="needs_human")]
    with pytest.raises(LicenseEvidenceError, match="not a rights_cleared"):
        apply_transition(
            store,
            source["artifact_id"],
            "rights_cleared",
            evidence,
            actor=ACTOR,
            timestamp=WHEN,
            inventory=refused,
            notice=notice,
        )
    assert current_state(store, source["artifact_id"]) == "DISCOVERED"


def test_clearance_binds_the_source_to_one_unit(store: ArtifactStore) -> None:
    """A pinned commit cannot borrow another row's files or redistribute rights."""
    inventory = load_inventory(INVENTORY)
    notice = json.loads((ROOT / "corpus" / "notice-manifest.v1.json").read_text())
    headerless = _entry(inventory, "faust-examples-headerless")
    mit = _entry(inventory, "faust-examples-mit")
    nlffm = _entry(inventory, "faust-examples-copyright-only")["files"][0]
    guitarix = _entry(inventory, "faust-examples-guitarix")["files"][0]
    impulse = _entry(inventory, "faust-impulse-headerless")["files"][0]
    owned = headerless["files"][0]
    assert nlffm["path"].endswith("NLFfm.dsp")
    assert guitarix["path"].endswith("guitarix.dsp")
    assert owned["path"] == "examples/SAM/16_channel_volume/16_channel_volume.dsp"
    assert "impulse-tests" in impulse["path"]
    cases = [
        (headerless, nlffm, headerless["license"]),
        (headerless, guitarix, headerless["license"]),
        (
            headerless,
            {"path": "examples/not/a/real/file.dsp", "blob_sha": "c" * 40},
            headerless["license"],
        ),
        (mit, owned, mit["license"]),
        (mit, impulse, mit["license"]),
    ]
    for row, unit, claim in cases:
        _refuse_clearance(store, inventory, notice, row, unit, claim)
    _refuse_clearance(
        store,
        inventory,
        notice,
        headerless,
        {"path": owned["path"], "blob_sha": "d" * 40},
        headerless["license"],
        match="blob_sha does not match",
    )
    _refuse_clearance(
        store,
        inventory,
        notice,
        headerless,
        owned,
        headerless["license"],
        repo="other/faust",
        match="inventory repo and commit",
    )
    sliced = _entry(inventory, "faustlibraries-stk-4.3")
    bare = dict(sliced["functions"][0])
    bare["function"] = ""
    _refuse_clearance(store, inventory, notice, sliced, bare, sliced["license"])


def test_eval_guard_uses_the_source_path(store: ArtifactStore) -> None:
    """An impulse path cannot take eval, including on a row that also lists it."""
    impulse = "tests/impulse-tests/dsp/borrowed.dsp"
    entry = {
        "id": "row-mixed",
        "decision": "rights_cleared",
        "license": "MIT",
        "evidence_label": "OBSERVED",
        "eligible_for": ["train", "eval", "redistribute"],
        "attribution_complete": True,
        "pin": {"repo": "example/faust", "commit": COMMIT, "ref": "test"},
        "path": "examples/",
        "reviewer": None,
        "redistribute": True,
        "files": [
            {"path": "example.dsp", "blob_sha": BLOB},
            {"path": impulse, "blob_sha": "c" * 40},
        ],
    }
    notice = {
        "entries": [
            {
                "commit": COMMIT,
                "path": "example.dsp",
                "blob_sha": BLOB,
                "function": None,
                "copyright": "Copyright 2020 Example Author",
                "license": "MIT",
            },
            {
                "commit": COMMIT,
                "path": impulse,
                "blob_sha": "c" * 40,
                "function": None,
                "copyright": "Copyright 2020 Example Author",
                "license": "MIT",
            },
        ]
    }
    inventory = {"entries": [entry]}
    evidence = _evidence(inventory_id="row-mixed")
    blocked = register_source(
        store,
        _source(path=impulse, blob="c" * 40),
        created_at=WHEN,
    )
    before = set(store.list())
    with pytest.raises(LicenseEvidenceError, match="impulse-test"):
        apply_transition(
            store,
            blocked["artifact_id"],
            "rights_cleared",
            evidence,
            actor=ACTOR,
            timestamp=WHEN,
            inventory=inventory,
            notice=notice,
        )
    assert set(store.list()) == before
    assert current_state(store, blocked["artifact_id"]) == "DISCOVERED"
    allowed = register_source(store, _source(), created_at=WHEN)
    result = apply_transition(
        store,
        allowed["artifact_id"],
        "rights_cleared",
        evidence,
        actor=ACTOR,
        timestamp=WHEN,
        inventory=inventory,
        notice=notice,
    )
    assert result.state == "RIGHTS_CLEARED"


def test_impulse_eval_uses_entry_id_not_a_path_substring(store: ArtifactStore) -> None:
    """faust-impulse-* refuses eval. A path that only contains 'impulse' does not."""
    path = "examples/impulseResponse.dsp"
    entry = {
        "id": "faust-impulse-readme",
        "decision": "rights_cleared",
        "license": "MIT",
        "evidence_label": "OBSERVED",
        "eligible_for": ["train", "eval", "redistribute"],
        "attribution_complete": True,
        "pin": {"repo": "example/faust", "commit": COMMIT, "ref": "test"},
        "path": "examples/",
        "reviewer": None,
        "redistribute": True,
        "files": [{"path": path, "blob_sha": BLOB}],
    }
    notice = {
        "entries": [
            {
                "commit": COMMIT,
                "path": path,
                "blob_sha": BLOB,
                "function": None,
                "copyright": "Copyright 2020 Example Author",
                "license": "MIT",
            }
        ]
    }
    evidence = _evidence(inventory_id="faust-impulse-readme")
    blocked = register_source(store, _source(path=path), created_at=WHEN)
    before = set(store.list())
    with pytest.raises(LicenseEvidenceError, match="impulse-test"):
        apply_transition(
            store,
            blocked["artifact_id"],
            "rights_cleared",
            evidence,
            actor=ACTOR,
            timestamp=WHEN,
            inventory={"entries": [entry]},
            notice=notice,
        )
    assert set(store.list()) == before
    plain = dict(entry)
    plain["id"] = "faust-examples-mit"
    allowed = register_source(store, _source(path=path), created_at=WHEN)
    result = apply_transition(
        store,
        allowed["artifact_id"],
        "rights_cleared",
        _evidence(inventory_id="faust-examples-mit"),
        actor=ACTOR,
        timestamp=WHEN,
        inventory={"entries": [plain]},
        notice=notice,
    )
    assert result.state == "RIGHTS_CLEARED"


def test_inferred_reviewer_is_the_evidence_or_the_unit(
    store: ArtifactStore,
) -> None:
    source = _register(store)
    inventory, notice, evidence = _clearance(
        evidence_label="INFERRED", reviewer=None
    )
    inventory["entries"][0]["reviewer"] = "Boof (delegated by Danny 2026-10-17)"
    before = set(store.list())
    with pytest.raises(LicenseEvidenceError, match="named reviewer"):
        apply_transition(
            store,
            source["artifact_id"],
            "rights_cleared",
            evidence,
            actor=ACTOR,
            timestamp=WHEN,
            inventory=inventory,
            notice=notice,
        )
    assert set(store.list()) == before
    inventory["entries"][0]["files"][0]["reviewer"] = "Unit Reviewer"
    result = apply_transition(
        store,
        source["artifact_id"],
        "rights_cleared",
        evidence,
        actor=ACTOR,
        timestamp=WHEN,
        inventory=inventory,
        notice=notice,
    )
    assert result.state == "RIGHTS_CLEARED"


def test_stk_redistribution_bundles_the_permission_notice() -> None:
    inventory = load_inventory(INVENTORY)
    notice = json.loads((ROOT / "corpus" / "notice-manifest.v1.json").read_text())
    body = " ".join(notice["license_texts"]["STK-4.3"].split())
    assert "Permission is hereby granted" in body
    assert "this permission notice shall be included" in body
    assert "Perry R. Cook" in body
    index = {
        (row["commit"], row["path"], row.get("function") or ""): row
        for row in notice["entries"]
    }
    seen = 0
    for entry in inventory["entries"]:
        if entry["license"] != "STK-4.3":
            continue
        units = list(entry.get("files") or []) + list(entry.get("functions") or [])
        for unit in units:
            row = index[
                (entry["pin"]["commit"], unit["path"], unit.get("function") or "")
            ]
            seen += 1
            if "redistribute" in entry["eligible_for"]:
                assert "bundles the STK-4.3 permission notice" in row["license_notice"]
            else:
                assert "license_notice" not in row
    assert seen > 0


@pytest.mark.parametrize("function", ["_tanhalf", "_tpt_df"])
def test_author_confirmed_helpers_require_exact_notice(store: ArtifactStore, function: str) -> None:
    inventory = load_inventory(INVENTORY)
    entry = next(row for row in inventory["entries"] if row["id"] == "faustlibraries-author-confirmed-helpers-mit")
    unit = next(row for row in entry["functions"] if row["function"] == function)
    source = register_source(store, _source(
        "MIT", commit=entry["pin"]["commit"], path=unit["path"],
        blob=unit["blob_sha"], function=function, repo=entry["pin"]["repo"],
    ), created_at=WHEN)
    evidence = _evidence(
        evidence_uri=entry["evidence_uri"], attribution=entry["attribution"],
        reason=entry["reason"], inventory_id=entry["id"], reviewer=entry["reviewer"],
    )
    notice = json.loads((ROOT / "corpus" / "notice-manifest.v1.json").read_text())
    missing = dict(notice, entries=[row for row in notice["entries"] if not (
        row["commit"] == entry["pin"]["commit"] and row["path"] == "filters.lib"
        and row["function"] == function
    )])
    with pytest.raises(LicenseEvidenceError):
        apply_transition(store, source["artifact_id"], "rights_cleared", evidence,
                         actor=ACTOR, timestamp="2026-10-24T08:00:00Z",
                         inventory=inventory, notice=missing)
    assert current_state(store, source["artifact_id"]) == "DISCOVERED"
    result = apply_transition(store, source["artifact_id"], "rights_cleared", evidence,
                              actor=ACTOR, timestamp="2026-10-24T08:00:00Z",
                              inventory=inventory, notice=notice)
    assert result.state == "RIGHTS_CLEARED"
    assert entry["eligible_for"] == ["train", "eval", "redistribute"]

from pathlib import Path
from faustcoder.readiness import assess


def test_missing_evidence_never_passes(tmp_path: Path):
    result = assess(tmp_path)
    assert result["pilot_ready"] is False
    assert result["training_authorized"] is False
    assert all(row["status"] == "NOT_VERIFIED" for row in result["evidence"])
    assert len(result["blockers"]) == 10


def test_document_presence_is_not_approval(tmp_path: Path):
    p = tmp_path / "specs/001-faustcoder/spec.md"
    p.parent.mkdir(parents=True)
    p.write_text("sample", encoding="utf-8")
    result = assess(tmp_path)
    item = next(x for x in result["evidence"] if x["gate"] == "canonical_spec")
    assert item["status"] == "PRESENT_NOT_VALIDATED"
    assert len(item["sha256"]) == 64
    assert not result["pilot_ready"]


def test_modes_do_not_force_full_corpus_gates_on_pilot(tmp_path):
    pilot = assess(tmp_path)
    assert "two_host_floor" not in {b["gate"] for b in pilot["blockers"]}
    assert "t07_signed_split" in {b["gate"] for b in pilot["blockers"]}
    synthetic = assess(tmp_path, mode="synthetic")
    assert synthetic["diagnostic_only"]
    assert not synthetic["training_authorized"]
    assert {b["gate"] for b in synthetic["blockers"]} == {"environment_probe", "synthetic_checkpoint_probe"}
    full = assess(tmp_path, mode="full")
    assert "two_host_floor" in {b["gate"] for b in full["blockers"]}


def test_pilot_approval_names_cannot_satisfy_full_mode(tmp_path):
    result = assess(tmp_path, mode="full")
    gates = {row["gate"] for row in result["blockers"]}
    assert "full_training_authorization" in gates
    assert "approved_full_dataset" in gates
    assert "pilot_training_authorization" not in gates
    assert "approved_pilot_dataset" not in gates
    assert not result["training_authorized"]

from pathlib import Path
from faustcoder.readiness import assess


def test_missing_evidence_never_passes(tmp_path: Path):
    result = assess(tmp_path)
    assert result["pilot_ready"] is False
    assert result["training_authorized"] is False
    assert all(row["status"] == "NOT_VERIFIED" for row in result["evidence"])
    assert len(result["blockers"]) == 7


def test_document_presence_is_not_approval(tmp_path: Path):
    p = tmp_path / "specs/001-faustcoder/spec.md"
    p.parent.mkdir(parents=True)
    p.write_text("sample", encoding="utf-8")
    result = assess(tmp_path)
    item = next(x for x in result["evidence"] if x["gate"] == "canonical_spec")
    assert item["status"] == "PRESENT_NOT_VALIDATED"
    assert len(item["sha256"]) == 64
    assert not result["pilot_ready"]

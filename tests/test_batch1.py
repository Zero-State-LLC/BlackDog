"""Evidence must explain detections without changing qualification decisions."""

import json
from types import SimpleNamespace
from contextlib import contextmanager
import pytest
from diagnostics.batch1_review import evidence_paths, trace_path
from diagnostics.batch1_acquire import run, pinned_url
from faustcoder.neardup import cluster_families


@pytest.mark.parametrize("floor", [40, 30, 20])
def test_trace_preserves_families_and_explains_collective_support(floor):
    rejected = " ".join(f"lib.fn{i}" for i in range(80))
    items = [("reject", rejected)] + [
        (str(j), " ".join(f"lib.fn{i}" for i in range(start, start + 25)))
        for j, start in enumerate((0, 25, 50))
    ]
    edges = []
    families = cluster_families(items, ["reject"], floor=floor, evidence=edges)
    assert families == cluster_families(items, ["reject"], floor=floor)
    assert families == cluster_families(list(reversed(items)), ["reject"], floor=floor)
    paths = evidence_paths(edges, ["reject"])
    assert set(paths) == set(families)
    assert all(trace_path(str(j), paths) for j in range(3))
    supports = {e["group_id"]: e for e in edges if e["reason"] == "collective_support"}
    for edge in edges:
        if edge["reason"] == "collective_union":
            support = supports[edge["group_id"]]
            assert edge["left"] in support["contributors"]
            assert support["covered"] * 2 >= support["denominator"]
            assert len(support["contributors"]) >= 3


def test_trace_does_not_invent_paths_for_unflagged_source():
    items = [
        ("r", "process=aa.member(1);"),
        ("copy", "process=aa.member(1);"),
        ("other", " ".join(f"xyz.op{i}" for i in range(100))),
    ]
    edges = []
    families = cluster_families(items, ["r"], evidence=edges)
    paths = evidence_paths(edges, ["r"])
    assert "copy" in paths and "other" not in paths
    assert families["other"] != families["r"]


@pytest.mark.parametrize("width", [40, 64])
@pytest.mark.parametrize("valid", [False, True])
def test_acquisition_verifies_declared_hash_without_admission(
    tmp_path, monkeypatch, width, valid
):
    from diagnostics import batch1_acquire as m

    repo = tmp_path / "repo"
    (repo / "corpus").mkdir(parents=True)
    for name in ("rights-inventory.v1.json", "notice-manifest.v1.json"):
        (repo / "corpus" / name).write_text("{}")
    from faustcoder.acquire import git_blob_id

    raw = b"process = _;"
    blob = git_blob_id(raw, "b" * width)
    unit = SimpleNamespace(
        repo="owner/repo", pin="a" * 40, path="example name.dsp", blob_sha=blob
    )
    assert "%20" in pinned_url(unit)
    corpus = SimpleNamespace(
        units=[unit], comparisons=[], inventory_digest="inv", notice_digest="notice"
    )
    monkeypatch.setattr(m, "parse_corpus", lambda *a: corpus)

    @contextmanager
    def fake_fetch(*args, **kwargs):
        yield SimpleNamespace(read=lambda limit: raw if valid else b"wrong content")

    monkeypatch.setattr(m, "urlopen", fake_fetch)
    monkeypatch.setattr(m.time, "sleep", lambda seconds: None)
    for name, data in [
        ("discovery", {"blob_locations": {}}),
        ("sources", {}),
        ("missing", {"missing_blobs": [blob]}),
    ]:
        (tmp_path / name).write_text(json.dumps(data))
    out = tmp_path / "out"
    run(repo, tmp_path / "discovery", tmp_path / "sources", tmp_path / "missing", out)
    report = json.loads((out / "summary.json").read_text())
    assert report["verified"] == int(valid)
    assert report["unavailable"] == ([] if valid else [blob])
    assert report["production_approved"] is False
    sources = json.loads((out / "sources.json").read_text())
    if valid:
        assert (out / "blobs" / blob).read_bytes() == raw
        assert sources == {blob: str((out / "blobs" / blob).resolve())}
    else:
        assert not list((out / "blobs").iterdir())
        assert sources == {}
    with pytest.raises(FileExistsError):
        run(
            repo,
            tmp_path / "discovery",
            tmp_path / "sources",
            tmp_path / "missing",
            out,
        )


@pytest.mark.parametrize("width", [40, 64])
def test_complete_review_serializes_inventory_tuples_without_approval(
    tmp_path, monkeypatch, width
):
    from diagnostics import batch1_review as m
    from faustcoder.inventory import Unit
    from faustcoder.acquire import git_blob_id

    repo = tmp_path / "repo"
    (repo / "corpus").mkdir(parents=True)
    for name in ("rights-inventory.v1.json", "notice-manifest.v1.json"):
        (repo / "corpus" / name).write_text("{}")
    for name in (
        "diagnostics/batch1_review.py",
        "faustcoder/neardup.py",
        "faustcoder/normalize.py",
        "faustcoder/inventory.py",
        "faustcoder/function_spans.py",
    ):
        p = repo / name
        p.parent.mkdir(exist_ok=True)
        p.write_text("# fixture")
    raw = b"process = _;"
    blob = git_blob_id(raw, "b" * width)
    source = tmp_path / "source"
    source.write_bytes(raw)
    unit = Unit(
        "u1",
        "entry",
        "rights_cleared",
        "owner/repo",
        "a" * 40,
        "one.dsp",
        blob,
        "",
        "MIT",
        ("train", "eval"),
        "OBSERVED",
        "fixture",
        None,
        "reviewer",
        "fixture",
        False,
        False,
        False,
    )
    corpus = SimpleNamespace(
        units=(unit,), comparisons=(), inventory_digest="inv", notice_digest="notice"
    )
    monkeypatch.setattr(m, "parse_corpus", lambda *a: corpus)
    monkeypatch.setattr(m, "verify_manifest", lambda *a: {})
    acquisition = tmp_path / "acquisition"
    acquisition.mkdir()
    docs = {
        "sources.json": {blob: str(source)},
        "discovery.json": {"blob_locations": {}},
    }
    for name, data in docs.items():
        (acquisition / name).write_text(json.dumps(data))
    for name, data in [
        ("candidate", {}),
        ("qualification", {"units": []}),
        ("groups", []),
        ("baseline", {"rows": [{"unit_id": "u1"}]}),
    ]:
        (tmp_path / name).write_text(json.dumps(data))
    out = tmp_path / "review"
    m.run(
        repo,
        acquisition,
        tmp_path / "candidate",
        tmp_path / "qualification",
        tmp_path / "groups",
        tmp_path / "baseline",
        out,
    )
    ledger = json.loads((out / "candidate-ledger.json").read_text())
    assert ledger["production_approved"] is False and ledger["t07_frozen"] is False
    assert ledger["units"][0]["adjudication"] == "UNREVIEWED"
    assert ledger["units"][0]["eligible_for"] == ["train", "eval"]
    assert len(json.loads((out / "packet-index.json").read_text())) == 1
    assert (
        json.loads((out / "batch2-proposed-subset.json").read_text())["admitted"]
        is False
    )

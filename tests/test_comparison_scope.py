"""Opt-in comparison scope (UNREVIEWED proposal): default unchanged, runs kept."""

import pytest

from faustcoder.comparison_scope import ComparisonScope, idiom_shingles, scoped
from faustcoder.neardup import cluster_families, shingles, tokens


def _prog(seed: str, n: int) -> str:
    # Qualified members stay literal on the canonical stream, so seeds differ there too.
    return "\n".join(f"{seed}{i} = {seed}.f{i}({i}) : {seed}.g{i};" for i in range(n))


IDIOM_LINES = [f"common{i} = hslider(\"g{i}\", 0.5, 0, 1, 0.01) : si.smoo;" for i in range(8)]


def _interleave(seed: str) -> str:
    # Idiom lines are separated by unique lines, so no 40-token run is shared.
    return "\n".join(f"{line}\n{seed}{i} = {seed}.u{i};" for i, line in enumerate(IDIOM_LINES))


def _pool():
    items = [("cmp", _interleave("rej") + "\n" + _prog("rej", 3))]
    for k in range(6):  # six cleared files carry the idiom and their own code
        items.append((f"c{k}", _interleave(f"own{k}")))
    return items


def test_scope_validation():
    assert ComparisonScope(5).describe() == {"version": "t06-idiom-filter-df.v2", "idiom_min_docs": 5, "idiom_min_repos": 2}
    for bad in (1, 0, -3, 2.0, True, "5"):
        with pytest.raises(ValueError):
            ComparisonScope(bad)
    with pytest.raises(ValueError):
        ComparisonScope(5, version="other")
    with pytest.raises(TypeError):
        cluster_families([("a", "x")], scope={"idiom_min_docs": 5})


def test_idiom_counts_only_non_comparison_items():
    sets = {"a": frozenset({"s1", "s2"}), "b": frozenset({"s1"}), "cmp": frozenset({"s1", "s2"})}
    assert idiom_shingles(sets, {"cmp"}, 2, item_repos={"a": "r1", "b": "r2"}) == frozenset({"s1"})
    assert scoped({"s1", "s2"}, None) == frozenset({"s1", "s2"})
    assert scoped({"s1", "s2"}, frozenset({"s1"})) == frozenset({"s2"})


def test_none_scope_is_identical_to_default():
    items = _pool()
    ev_a, ev_b = [], []
    assert cluster_families(items, ["cmp"], evidence=ev_a) == cluster_families(items, ["cmp"], evidence=ev_b, scope=None)
    assert ev_a == ev_b
    assert not any(e["reason"] == "comparison_scope" for e in ev_a)


def test_scope_drops_idiom_only_containment_and_records_itself():
    items = _pool()
    base = cluster_families(items, ["cmp"])
    assert len({base[k] for k, _ in items}) == 1  # idiom alone joins everything today
    ev = []
    got = cluster_families(items, ["cmp"], evidence=ev, scope=ComparisonScope(3), item_repos={k: "repo/" + k for k, _ in items})
    assert all(got[f"c{k}"] != got["cmp"] for k in range(6))
    marks = [e for e in ev if e["reason"] == "comparison_scope"]
    assert {e["stream"] for e in marks} == {"raw", "canonical"}
    assert all(e["idiom_min_docs"] == 3 and e["idiom_shingles"] > 0 for e in marks)


def test_scope_keeps_floor_verbatim_run_even_inside_idiom():
    items = _pool()
    comp = dict(items)["cmp"]
    # A cleared file that copies the whole comparison text verbatim (>= 40 tokens).
    assert len(tokens(comp)) >= 40
    items.append(("copy", _prog("mine", 10) + "\n" + comp))
    got = cluster_families(items, ["cmp"], scope=ComparisonScope(3), item_repos={k: "repo/" + k for k, _ in items})
    assert got["copy"] == got["cmp"]


def test_scope_keeps_unique_containment():
    items = _pool()
    comp = dict(items)["cmp"]
    unique = _prog("rej", 3)
    assert shingles(tokens(unique))
    # Copy only the unique rejected part (under the floor): reverse containment
    # on the scoped comparison shingles still joins.
    items.append(("excerpt", _prog("mine2", 2) + "\n" + unique))
    got = cluster_families(items, ["cmp"], scope=ComparisonScope(3), item_repos={k: "repo/" + k for k, _ in items})
    assert got["excerpt"] == got["cmp"]
    assert comp  # comparison unchanged


def test_scope_never_changes_exact_or_jaccard_between_pool_items():
    items = _pool() + [("dup", dict(_pool())["c0"])]
    got = cluster_families(items, ["cmp"], scope=ComparisonScope(3), item_repos={k: "repo/" + k for k, _ in items})
    assert got["dup"] == got["c0"]


def test_scope_verbatim_run_is_the_join_reason_for_a_padded_copy():
    items = _pool()
    comp_lines = dict(items)["cmp"].split("\n")
    chunk = "\n".join(comp_lines[:6])  # about 50 contiguous tokens of the comparison
    assert len(tokens(chunk)) >= 40
    items.append(("padded", _prog("pad", 40) + "\n" + chunk))
    ev = []
    got = cluster_families(items, ["cmp"], evidence=ev, scope=ComparisonScope(3), item_repos={k: "repo/" + k for k, _ in items})
    assert got["padded"] == got["cmp"]
    assert any(e.get("left") == "padded" and e["reason"] == "verbatim_run" for e in ev)


@pytest.fixture
def packet_run(tmp_path, monkeypatch):
    from dataclasses import dataclass
    from types import SimpleNamespace
    from pathlib import Path
    import json
    from diagnostics import batch1_review as module
    from faustcoder.acquire import git_blob_id
    @dataclass
    class Unit:
        unit_id: str = "unit"
        repo: str = "owner/project"
        pin: str = "a" * 40
        path: str = "example.dsp"
        function: object = None
        blob_sha: str = ""
        decision: str = "candidate"
        entry_id: str = "entry"
        eligible_for: tuple = ()
    root = tmp_path / "repo"
    (root / "corpus").mkdir(parents=True)
    for name in ("rights-inventory.v1.json", "notice-manifest.v1.json"):
        (root / "corpus" / name).write_text("{}")
    for name in ("diagnostics/batch1_review.py", "faustcoder/neardup.py", "faustcoder/normalize.py",
                 "faustcoder/inventory.py", "faustcoder/function_spans.py", "faustcoder/comparison_scope.py"):
        dest = root / name
        dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(Path(name).read_bytes())
    raw = b"process = _;"
    source = tmp_path / "source.dsp"
    source.write_bytes(raw)
    unit = Unit(blob_sha=git_blob_id(raw, "a" * 40))
    monkeypatch.setattr(module, "parse_corpus", lambda *args: SimpleNamespace(
        units=[unit], comparisons=[], inventory_digest="inv", notice_digest="notice"))
    monkeypatch.setattr(module, "verify_manifest", lambda *args: {})
    inputs = {"sources.json": {unit.blob_sha: str(source)}, "discovery.json": {"blob_locations": {}},
              "candidate.json": {}, "qualification.json": {"units": []}, "groups.json": [], "baseline.json": {"rows": []}}
    for name, data in inputs.items():
        (tmp_path / name).write_text(json.dumps(data))
    def run(name, scope=None):
        out = tmp_path / name
        module.run(root, tmp_path, tmp_path / "candidate.json", tmp_path / "qualification.json",
                   tmp_path / "groups.json", tmp_path / "baseline.json", out, scope)
        return out
    return run, root


def test_binding_records_scope_and_every_output(packet_run):
    import json
    from hashlib import sha256
    run, _ = packet_run
    for name, scope in (("off", None), ("on", ComparisonScope(3))):
        out = run(name, scope)
        binding = json.loads((out / "binding.json").read_text())
        descriptor = binding["comparison_scope"]
        assert descriptor["enabled"] == (scope is not None)
        assert descriptor["idiom_min_docs"] == (3 if scope else None)
        assert descriptor["version"]
        assert descriptor["idiom_set_sha256"].startswith("sha256:")
        files = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()} - {"binding.json"}
        assert set(binding["outputs"]) == files
        for name, receipt in binding["outputs"].items():
            assert receipt["sha256"] == "sha256:" + sha256((out / name).read_bytes()).hexdigest()
            assert receipt["comparison_scope"] == descriptor
        if scope:
            for name in ["candidate-ledger.json", "summary.json"] + [str(p.relative_to(out)) for p in (out / "packets").glob("*.json")]:
                assert json.loads((out / name).read_text())["comparison_scope"] == descriptor
            assert all(descriptor["idiom_set_sha256"] in p.read_text() for p in (out / "packets").glob("*.md"))


def test_scope_module_changes_off_binding(packet_run):
    import json
    run, root = packet_run
    a = json.loads((run("before") / "binding.json").read_text())
    p = root / "faustcoder/comparison_scope.py"
    p.write_text(p.read_text() + "\n# mutation\n")
    b = json.loads((run("after") / "binding.json").read_text())
    assert a["code"]["faustcoder/comparison_scope.py"] != b["code"]["faustcoder/comparison_scope.py"]


def test_on_outputs_rejected_under_off_binding(packet_run):
    import json
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    off, on = run("off"), run("on", ComparisonScope(3))
    validate_outputs(off)
    validate_outputs(on)
    (on / "binding.json").write_bytes((off / "binding.json").read_bytes())
    with pytest.raises(ValueError):
        validate_outputs(on)


def test_one_repo_copies_are_not_idiom():
    sets = {str(i): frozenset({"copied"}) for i in range(10)}
    repos = {str(i): "same/repository" for i in range(10)}
    assert idiom_shingles(sets, [], 3, item_repos=repos, min_repos=2) == frozenset()
    repos["9"] = "different/repository"
    assert idiom_shingles(sets, [], 3, item_repos=repos, min_repos=2) == frozenset({"copied"})


def _collective(scope):
    whole = " ".join(f"lib.fn{i}" for i in range(100))
    items = [("cmp", whole)] + [(str(j), " ".join(f"lib.fn{i}" for i in range(start, start+25)))
                                for j, start in enumerate((0, 25, 50))]
    items += [("noise", " ".join(f"lib.fn{i}" for i in range(5)) + " " + _prog("noise", 20))]
    ev = []
    result = cluster_families(items, ["cmp"], evidence=ev, scope=scope)
    return result, [e for e in ev if e["reason"] == "collective_support"]


def test_collective_only_joins_coverage_units_and_scope_binds_ids():
    result, groups = _collective(ComparisonScope(200))
    assert groups
    assert all(set(g["contributors"]) == {"0", "1", "2"} for g in groups)
    assert result["noise"] != result["cmp"]
    _, other = _collective(ComparisonScope(400))
    assert {g["group_id"] for g in groups}.isdisjoint(g["group_id"] for g in other)



def test_group_ids_bind_scope_even_when_coverage_is_identical():
    _, a = _collective(ComparisonScope(200))
    _, b = _collective(ComparisonScope(400))
    assert a and b
    assert [e["contributors"] for e in a] == [e["contributors"] for e in b]
    assert {e["group_id"] for e in a}.isdisjoint(e["group_id"] for e in b)


def test_distinct_plant_summary_and_nonmonotonic_flips():
    from diagnostics.scope_plant_check import summarize
    rows = [dict(window_id="w", multiplicity=m, host=str(h), raw_tokens=39,
                 baseline="raw:forward_containment", floor_artifact=False,
                 scope_df5="", scope_df10="raw:forward_containment", scope_df20="")
            for m, h in ((1, 0), (2, 0), (2, 1))]
    rows.append(dict(window_id="gain", multiplicity=1, host="x", raw_tokens=40,
                     baseline="", floor_artifact=False, scope_df5="hit", scope_df10="hit", scope_df20="hit"))
    rows.append(dict(window_id="floor", multiplicity=1, host="x", raw_tokens=39,
                     baseline="hit", floor_artifact=True, scope_df5="", scope_df10="", scope_df20=""))
    result = summarize(rows, [5,10,20])
    assert result["by_D"]["5"]["lost_windows"] == 1
    assert result["by_D"]["5"]["gained_windows"] == 1
    assert result["by_D"]["5"]["net_windows"] == 0
    assert result["by_D"]["5"]["floor_artifact_windows"] == 1
    assert result["by_D_and_m"]["D5_m2"]["lost_windows"] == 1
    assert result["by_D_and_m"]["D5_m2"]["lost_rows"] == 2
    assert len(result["nonmonotonic_rows"]) == 3


def test_floor_artifact_is_separate_from_true_plant_detection():
    from diagnostics.scope_plant_check import floor_artifact
    host = " ".join(f"token{i}" for i in range(39))
    whole = host + " " + " ".join(f"other.fn{i}" for i in range(70))
    assert floor_artifact(host, host + " addition", whole, ["raw:forward_containment"])
    assert not floor_artifact(host, host + " addition", whole, ["raw:verbatim_run"])
    assert not floor_artifact(host + " addition", host + " addition more", whole, ["raw:forward_containment"])


def test_boundary_windows_cover_each_token_width():
    from diagnostics.scope_plant_check import boundary_windows
    windows = [dict(window_id="source", source_blob="blob", raw_tokens="50", text=" ".join(f"lib.fn{i}" for i in range(50)))]
    extra = boundary_windows(windows)
    assert {len(tokens(w["text"])) for w in extra} == set(range(36, 50))
    assert len({w["window_id"] for w in extra}) == 14



def test_single_repository_copy_is_not_suppressed_in_clustering():
    items = _pool()
    result = cluster_families(items, ["cmp"], scope=ComparisonScope(3),
                              item_repos={k: "one/repository" for k,_ in items})
    assert all(result[k] == result["cmp"] for k,_ in items)


def test_plant_repository_delta_matches_learned_idiom():
    from collections import Counter
    from diagnostics.scope_plant_check import DocFreq
    base = {"raw": Counter({"shared": 4, "solo": 8})}
    delta = {"raw": Counter({"shared": -1})}
    support = {"raw": Counter({"shared": 2, "solo": 1})}
    repo_delta = {"raw": Counter({"shared": -1})}
    view = DocFreq(base, delta, 3, support, repo_delta, 2)["raw"]
    assert "solo" not in view
    assert "shared" not in view
    repo_delta["raw"]["shared"] = 0
    assert "shared" in view


def test_idiom_filter_name_and_repo_validation():
    from faustcoder.comparison_scope import IdiomFilter
    assert ComparisonScope is IdiomFilter
    for bad in (1, True, "2", 2.5):
        with pytest.raises(ValueError):
            IdiomFilter(5, idiom_min_repos=bad)

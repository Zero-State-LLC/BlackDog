"""Opt-in idiom filter (UNREVIEWED proposal): shipping collective rule unchanged."""

import unicodedata

import pytest

from faustcoder.idiom_filter import IdiomFilter, idiom_shingles, scoped
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
    assert IdiomFilter(5).describe() == {"version": "t06-idiom-filter-df.v2", "idiom_min_docs": 5, "idiom_min_repos": 2}
    for bad in (1, 0, -3, 2.0, True, "5"):
        with pytest.raises(ValueError):
            IdiomFilter(bad)
    with pytest.raises(ValueError, match="unknown idiom filter version"):
        IdiomFilter(5, version="other")
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
    assert not any(e["reason"] == "idiom_filter" for e in ev_a)


def test_scope_drops_idiom_only_containment_and_records_itself():
    items = _pool()
    base = cluster_families(items, ["cmp"])
    assert len({base[k] for k, _ in items}) == 1  # idiom alone joins everything today
    ev = []
    got = cluster_families(items, ["cmp"], evidence=ev, scope=IdiomFilter(3), item_repos={k: "repo/" + k for k, _ in items})
    assert all(got[f"c{k}"] != got["cmp"] for k in range(6))
    marks = [e for e in ev if e["reason"] == "idiom_filter"]
    assert {e["stream"] for e in marks} == {"raw", "canonical"}
    assert all(e["idiom_min_docs"] == 3 and e["idiom_shingles"] > 0 for e in marks)


def test_scope_keeps_floor_verbatim_run_even_inside_idiom():
    items = _pool()
    comp = dict(items)["cmp"]
    # A cleared file that copies the whole comparison text verbatim (>= 40 tokens).
    assert len(tokens(comp)) >= 40
    items.append(("copy", _prog("mine", 10) + "\n" + comp))
    got = cluster_families(items, ["cmp"], scope=IdiomFilter(3), item_repos={k: "repo/" + k for k, _ in items})
    assert got["copy"] == got["cmp"]


def test_scope_keeps_unique_containment():
    items = _pool()
    comp = dict(items)["cmp"]
    unique = _prog("rej", 3)
    assert shingles(tokens(unique))
    # Copy only the unique rejected part (under the floor): reverse containment
    # on the scoped comparison shingles still joins.
    items.append(("excerpt", _prog("mine2", 2) + "\n" + unique))
    got = cluster_families(items, ["cmp"], scope=IdiomFilter(3), item_repos={k: "repo/" + k for k, _ in items})
    assert got["excerpt"] == got["cmp"]
    assert comp  # comparison unchanged


def test_scope_never_changes_exact_or_jaccard_between_pool_items():
    items = _pool() + [("dup", dict(_pool())["c0"])]
    got = cluster_families(items, ["cmp"], scope=IdiomFilter(3), item_repos={k: "repo/" + k for k, _ in items})
    assert got["dup"] == got["c0"]


def test_scope_verbatim_run_is_the_join_reason_for_a_padded_copy():
    items = _pool()
    comp_lines = dict(items)["cmp"].split("\n")
    chunk = "\n".join(comp_lines[:6])  # about 50 contiguous tokens of the comparison
    assert len(tokens(chunk)) >= 40
    items.append(("padded", _prog("pad", 40) + "\n" + chunk))
    ev = []
    got = cluster_families(items, ["cmp"], evidence=ev, scope=IdiomFilter(3), item_repos={k: "repo/" + k for k, _ in items})
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
                 "faustcoder/inventory.py", "faustcoder/function_spans.py", "faustcoder/idiom_filter.py"):
        dest = root / name
        dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(Path(name).read_bytes())
    idiom = "\n".join(
        f'common{i} = hslider("g{i}", 0.5, 0, 1, 0.01) : si.smoo;' for i in range(8)
    ).encode()
    cleared = []
    locations = {}
    for unit_id, repo, extra in (
        ("a", "owner/one", b"\nprocess = a.only;"),
        ("b", "owner/one", b"\nprocess = b.only;"),
        ("c", "owner/two", b"\nprocess = c.only;"),
    ):
        raw = idiom + extra
        source = tmp_path / f"{unit_id}.dsp"
        source.write_bytes(raw)
        blob = git_blob_id(raw, "a" * 40)
        locations[blob] = str(source)
        cleared.append(Unit(unit_id=unit_id, repo=repo, path=f"{unit_id}.dsp",
                            blob_sha=blob, entry_id=unit_id))
    comp_raw = idiom + b"\nprocess = rejected.tail;"
    comp_source = tmp_path / "rejected.dsp"
    comp_source.write_bytes(comp_raw)
    comp_blob = git_blob_id(comp_raw, "a" * 40)
    locations[comp_blob] = str(comp_source)
    comparison = Unit(unit_id="cmp", repo="owner/rejected", path="rejected.dsp",
                      blob_sha=comp_blob, decision="rights_rejected", entry_id="cmp")
    monkeypatch.setattr(module, "parse_corpus", lambda *args: SimpleNamespace(
        units=cleared, comparisons=[comparison], inventory_digest="inv", notice_digest="notice"))
    monkeypatch.setattr(module, "verify_manifest", lambda *args: {})
    inputs = {"sources.json": locations, "discovery.json": {"blob_locations": {}},
              "candidate.json": {}, "qualification.json": {"units": []}, "groups.json": [], "baseline.json": {"rows": []}}
    for name, data in inputs.items():
        (tmp_path / name).write_text(json.dumps(data))
    def run(name, scope=None, marginal_coverage=False):
        out = tmp_path / name
        module.run(root, tmp_path, tmp_path / "candidate.json", tmp_path / "qualification.json",
                   tmp_path / "groups.json", tmp_path / "baseline.json", out, scope,
                   marginal_coverage=marginal_coverage)
        return out
    return run, root


def test_binding_records_scope_and_every_output(packet_run):
    import json
    from hashlib import sha256
    run, _ = packet_run
    digests = {}
    for name, scope in (("off", None), ("on", IdiomFilter(3))):
        out = run(name, scope)
        binding = json.loads((out / "binding.json").read_text())
        descriptor = binding["idiom_filter"]
        assert "faustcoder/idiom_filter.py" in binding["code"]
        assert binding["marginal_coverage"] is False
        assert descriptor["enabled"] == (scope is not None)
        assert descriptor["label"] == ("idiom_filter:D=3:k=2" if scope else "scope=off")
        assert descriptor["idiom_min_docs"] == (3 if scope else None)
        assert descriptor["version"]
        assert descriptor["idiom_set_sha256"].startswith("sha256:")
        digests[name] = descriptor["idiom_set_sha256"]
        files = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()} - {"binding.json"}
        assert set(binding["outputs"]) == files
        for receipt_name, receipt in binding["outputs"].items():
            assert receipt["sha256"] == "sha256:" + sha256((out / receipt_name).read_bytes()).hexdigest()
            assert receipt["idiom_filter"] == descriptor
            assert receipt["marginal_coverage"] is False
        named = ["candidate-ledger.json", "summary.json"] + [
            str(p.relative_to(out)) for p in (out / "packets").glob("*.json")
        ]
        for named_file in named:
            payload = json.loads((out / named_file).read_text())
            assert payload["idiom_filter"] == descriptor
            assert payload["marginal_coverage"] is False
        assert all(
            descriptor["label"] in p.read_text()
            and descriptor["idiom_set_sha256"] in p.read_text()
            and "Marginal coverage: `off`" in p.read_text()
            for p in (out / "packets").glob("*.md")
        )
    assert digests["off"] != digests["on"]


def test_scope_module_changes_off_binding(packet_run):
    import json
    run, root = packet_run
    a = json.loads((run("before") / "binding.json").read_text())
    p = root / "faustcoder/idiom_filter.py"
    p.write_text(p.read_text() + "\n# mutation\n")
    b = json.loads((run("after") / "binding.json").read_text())
    assert a["code"]["faustcoder/idiom_filter.py"] != b["code"]["faustcoder/idiom_filter.py"]


def test_on_outputs_rejected_under_off_binding(packet_run):
    import json
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    off, on = run("off"), run("on", IdiomFilter(3))
    validate_outputs(off)
    validate_outputs(on)
    off_binding = json.loads((off / "binding.json").read_text())
    on_binding = json.loads((on / "binding.json").read_text())
    assert off_binding["idiom_filter"]["idiom_set_sha256"] != on_binding["idiom_filter"]["idiom_set_sha256"]
    (on / "binding.json").write_bytes((off / "binding.json").read_bytes())
    with pytest.raises(ValueError, match="output hash mismatch"):
        validate_outputs(on)


def test_deleted_scope_binding_is_rejected(packet_run):
    import json
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    out = run("off")
    validate_outputs(out)
    binding = json.loads((out / "binding.json").read_text())
    del binding["idiom_filter"]
    (out / "binding.json").write_text(json.dumps(binding))
    with pytest.raises(ValueError, match="omits idiom filter"):
        validate_outputs(out)


def test_deleted_scope_module_binding_is_rejected(packet_run):
    import json
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    out = run("off")
    binding = json.loads((out / "binding.json").read_text())
    del binding["code"]["faustcoder/idiom_filter.py"]
    (out / "binding.json").write_text(json.dumps(binding))
    with pytest.raises(ValueError, match="idiom_filter.py"):
        validate_outputs(out)


def test_output_hash_mismatch_is_rejected(packet_run):
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    out = run("off")
    ledger = out / "candidate-ledger.json"
    ledger.write_bytes(ledger.read_bytes() + b" ")
    with pytest.raises(ValueError, match="output hash mismatch"):
        validate_outputs(out)


def _rewrite_binding(out, binding):
    import json
    (out / "binding.json").write_text(json.dumps(binding))


def test_output_inventory_mismatch_is_rejected(packet_run):
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    out = run("off")
    (out / "extra.json").write_text("{}\n")
    with pytest.raises(ValueError, match="output inventory mismatch"):
        validate_outputs(out)


def test_per_receipt_scope_mismatch_is_rejected(packet_run):
    import json
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    out = run("off")
    binding = json.loads((out / "binding.json").read_text())
    name = "summary.json"
    binding["outputs"][name]["idiom_filter"] = {**binding["idiom_filter"], "label": "tampered"}
    _rewrite_binding(out, binding)
    with pytest.raises(ValueError, match="output scope mismatch: summary.json"):
        validate_outputs(out)


@pytest.mark.parametrize("name", ["candidate-ledger.json", "summary.json"])
def test_inline_scope_mismatch_is_rejected(packet_run, name):
    import json
    from faustcoder.canonical import sha256_prefixed
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    out = run("off")
    binding = json.loads((out / "binding.json").read_text())
    payload = json.loads((out / name).read_text())
    payload["idiom_filter"] = {**payload["idiom_filter"], "label": "tampered"}
    raw = json.dumps(payload).encode() + b"\n"
    (out / name).write_bytes(raw)
    binding["outputs"][name]["sha256"] = sha256_prefixed(raw)
    _rewrite_binding(out, binding)
    with pytest.raises(ValueError, match="inline scope mismatch: " + name):
        validate_outputs(out)


def test_packet_json_scope_mismatch_is_rejected(packet_run):
    import json
    from faustcoder.canonical import sha256_prefixed
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    out = run("off")
    binding = json.loads((out / "binding.json").read_text())
    packet = next((out / "packets").glob("*.json"))
    payload = json.loads(packet.read_text())
    payload["idiom_filter"] = {**payload["idiom_filter"], "label": "tampered"}
    raw = json.dumps(payload).encode() + b"\n"
    packet.write_bytes(raw)
    rel = str(packet.relative_to(out))
    binding["outputs"][rel]["sha256"] = sha256_prefixed(raw)
    _rewrite_binding(out, binding)
    with pytest.raises(ValueError, match="packet scope mismatch: " + packet.name):
        validate_outputs(out)


def test_packet_md_scope_name_missing_is_rejected(packet_run):
    import json
    from faustcoder.canonical import sha256_prefixed
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    out = run("off")
    binding = json.loads((out / "binding.json").read_text())
    packet = next((out / "packets").glob("*.md"))
    label = binding["idiom_filter"]["label"]
    raw = packet.read_text().replace(label, "scope=tampered").encode()
    packet.write_bytes(raw)
    rel = str(packet.relative_to(out))
    binding["outputs"][rel]["sha256"] = sha256_prefixed(raw)
    _rewrite_binding(out, binding)
    with pytest.raises(ValueError, match="packet scope name missing: " + packet.name):
        validate_outputs(out)


def test_packet_json_marginal_mismatch_is_rejected(packet_run):
    import json
    from faustcoder.canonical import sha256_prefixed
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    out = run("off")
    binding = json.loads((out / "binding.json").read_text())
    packet = next((out / "packets").glob("*.json"))
    payload = json.loads(packet.read_text())
    payload["marginal_coverage"] = not binding["marginal_coverage"]
    raw = json.dumps(payload).encode() + b"\n"
    packet.write_bytes(raw)
    rel = str(packet.relative_to(out))
    binding["outputs"][rel]["sha256"] = sha256_prefixed(raw)
    _rewrite_binding(out, binding)
    with pytest.raises(ValueError, match="packet marginal coverage mismatch: " + packet.name):
        validate_outputs(out)


def test_packet_md_marginal_missing_is_rejected(packet_run):
    import json
    from faustcoder.canonical import sha256_prefixed
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    out = run("off")
    binding = json.loads((out / "binding.json").read_text())
    packet = next((out / "packets").glob("*.md"))
    label = "Marginal coverage: `off`"
    raw = packet.read_text().replace(label, "Marginal coverage: `on`").encode()
    packet.write_bytes(raw)
    rel = str(packet.relative_to(out))
    binding["outputs"][rel]["sha256"] = sha256_prefixed(raw)
    _rewrite_binding(out, binding)
    with pytest.raises(ValueError, match="packet marginal coverage missing: " + packet.name):
        validate_outputs(out)


def test_run_calls_validate_outputs(packet_run, monkeypatch):
    from diagnostics import batch1_review as module
    called = []
    original = module.validate_outputs

    def spy(output):
        called.append(output)
        return original(output)

    monkeypatch.setattr(module, "validate_outputs", spy)
    run, _ = packet_run
    out = run("checked")
    assert called == [out]


def test_marginal_coverage_is_recorded_in_binding(packet_run):
    import json
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    out = run("marginal", marginal_coverage=True)
    binding = json.loads((out / "binding.json").read_text())
    assert binding["marginal_coverage"] is True
    assert all(receipt["marginal_coverage"] is True for receipt in binding["outputs"].values())
    ledger = json.loads((out / "candidate-ledger.json").read_text())
    summary = json.loads((out / "summary.json").read_text())
    assert ledger["marginal_coverage"] is True
    assert summary["marginal_coverage"] is True
    assert all(json.loads(p.read_text())["marginal_coverage"] is True for p in (out / "packets").glob("*.json"))
    assert all("Marginal coverage: `on`" in p.read_text() for p in (out / "packets").glob("*.md"))
    validate_outputs(out)
    del binding["marginal_coverage"]
    _rewrite_binding(out, binding)
    with pytest.raises(ValueError, match="omits marginal coverage"):
        validate_outputs(out)


def test_flipped_marginal_flag_fails_without_rewriting_outputs(packet_run):
    """T1: receipts and the top-level flag can both say false while payloads stay true."""
    import json
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    out = run("marginal-flip", marginal_coverage=True)
    validate_outputs(out)
    binding = json.loads((out / "binding.json").read_text())
    binding["marginal_coverage"] = False
    for receipt in binding["outputs"].values():
        receipt["marginal_coverage"] = False
    _rewrite_binding(out, binding)
    with pytest.raises(ValueError, match="inline marginal coverage mismatch"):
        validate_outputs(out)


def test_per_receipt_marginal_mismatch_is_rejected(packet_run):
    """N5: dropping the per-receipt flag check lets one receipt lie."""
    import json
    from diagnostics.batch1_review import validate_outputs
    run, _ = packet_run
    out = run("marginal-receipt", marginal_coverage=True)
    binding = json.loads((out / "binding.json").read_text())
    name = "summary.json"
    binding["outputs"][name]["marginal_coverage"] = False
    _rewrite_binding(out, binding)
    with pytest.raises(ValueError, match="output marginal coverage mismatch: summary.json"):
        validate_outputs(out)


def test_run_marginal_coverage_changes_the_ledger(tmp_path, monkeypatch):
    """N3: ignoring --marginal-coverage leaves the noise unit quarantined."""
    import json
    from dataclasses import dataclass
    from pathlib import Path
    from types import SimpleNamespace
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

    alphabet = _symbol_alphabet()
    pieces = [_piece(alphabet, i * 18, 18) for i in range(4)]
    noise = " ".join(pieces[0].split()[:5]) + " " + " ".join(alphabet[80:110])
    texts = {f"c{i}": pieces[i] for i in range(4)}
    texts["noise"] = noise
    texts["cmp"] = " ".join(pieces)
    root = tmp_path / "repo"
    (root / "corpus").mkdir(parents=True)
    for name in ("rights-inventory.v1.json", "notice-manifest.v1.json"):
        (root / "corpus" / name).write_text("{}")
    for name in (
        "diagnostics/batch1_review.py", "faustcoder/neardup.py", "faustcoder/normalize.py",
        "faustcoder/inventory.py", "faustcoder/function_spans.py", "faustcoder/idiom_filter.py",
    ):
        dest = root / name
        dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(Path(name).read_bytes())
    cleared = []
    locations = {}
    for unit_id, body in texts.items():
        raw = (body + "\n").encode()
        source = tmp_path / f"{unit_id}.dsp"
        source.write_bytes(raw)
        blob = git_blob_id(raw, "a" * 40)
        locations[blob] = str(source)
        if unit_id == "cmp":
            comparison = Unit(unit_id="cmp", repo="owner/rejected", path="rejected.dsp",
                              blob_sha=blob, decision="rights_rejected", entry_id="cmp")
        else:
            cleared.append(Unit(unit_id=unit_id, repo="owner/" + unit_id, path=f"{unit_id}.dsp",
                                blob_sha=blob, entry_id=unit_id))
    monkeypatch.setattr(module, "parse_corpus", lambda *args: SimpleNamespace(
        units=cleared, comparisons=[comparison], inventory_digest="inv", notice_digest="notice"))
    monkeypatch.setattr(module, "verify_manifest", lambda *args: {})
    inputs = {
        "sources.json": locations,
        "discovery.json": {"blob_locations": {}},
        "candidate.json": {},
        "qualification.json": {"units": []},
        "groups.json": [],
        "baseline.json": {"rows": []},
    }
    for name, data in inputs.items():
        (tmp_path / name).write_text(json.dumps(data))

    def once(name, marginal_coverage):
        out = tmp_path / name
        module.run(root, tmp_path, tmp_path / "candidate.json", tmp_path / "qualification.json",
                   tmp_path / "groups.json", tmp_path / "baseline.json", out,
                   marginal_coverage=marginal_coverage)
        ledger = json.loads((out / "candidate-ledger.json").read_text())
        return {row["unit_id"]: row["quarantine_candidate"] for row in ledger["units"]}

    default = once("default-rule", False)
    opted = once("marginal-rule", True)
    assert default["noise"] is True
    assert all(default[f"c{i}"] is True for i in range(4))
    assert opted["noise"] is False
    assert all(opted[f"c{i}"] is True for i in range(4))


def test_learned_sets_change_idiom_digest():
    from faustcoder.idiom_filter import scope_descriptor
    scope = IdiomFilter(2)
    empty = scope_descriptor(scope, {})
    learned = scope_descriptor(scope, {"raw": frozenset({"shingle-a"}), "canonical": frozenset()})
    other = scope_descriptor(scope, {"raw": frozenset({"shingle-b"}), "canonical": frozenset()})
    assert empty["idiom_set_sha256"] != learned["idiom_set_sha256"]
    assert learned["idiom_set_sha256"] != other["idiom_set_sha256"]


def test_cli_defaults_leave_filter_and_marginal_off(monkeypatch):
    import sys
    from diagnostics import batch1_review as module
    seen = {}

    def fake_run(*args, scope=None, marginal_coverage=False):
        seen["scope"] = scope
        seen["marginal_coverage"] = marginal_coverage

    monkeypatch.setattr(module, "run", fake_run)
    argv = ["batch1_review", "--repo", "r", "--acquisition", "a", "--candidate", "c",
            "--qualification", "q", "--groups", "g", "--baseline", "b", "--output", "o"]
    monkeypatch.setattr(sys, "argv", argv)
    module.main()
    assert seen == {"scope": None, "marginal_coverage": False}
    monkeypatch.setattr(sys, "argv", argv + ["--idiom-filter-min-docs", "4", "--marginal-coverage"])
    module.main()
    assert seen["scope"] == IdiomFilter(4)
    assert seen["marginal_coverage"] is True
    monkeypatch.setattr(sys, "argv", argv + ["--comparison-scope-min-docs", "4"])
    with pytest.raises(SystemExit):
        module.main()


def test_one_repo_copies_are_not_idiom():
    sets = {str(i): frozenset({"copied"}) for i in range(10)}
    repos = {str(i): "same/repository" for i in range(10)}
    assert idiom_shingles(sets, [], 3, item_repos=repos, min_repos=2) == frozenset()
    repos["9"] = "different/repository"
    assert idiom_shingles(sets, [], 3, item_repos=repos, min_repos=2) == frozenset({"copied"})


def _symbol_alphabet():
    chars = []
    for cp in range(0x21, 0x2200):
        ch = chr(cp)
        if ch.isspace() or ch in '"\\_':
            continue
        if unicodedata.category(ch)[0] not in "PS":
            continue
        if unicodedata.normalize("NFKC", ch) != ch:
            continue
        chars.append(ch)
    return chars


def _piece(alphabet, start, count):
    return " ".join(alphabet[start:start + count])


def _groups(items, comparison, **kwargs):
    evidence = []
    result = cluster_families(items, comparison, evidence=evidence, **kwargs)
    return result, [edge for edge in evidence if edge["reason"] == "collective_support"]


def _three_way_items(alphabet, start=0):
    pieces = [_piece(alphabet, start + i * 18, 18) for i in range(3)]
    noise = " ".join(pieces[0].split()[:5]) + " " + " ".join(alphabet[start + 80:start + 110])
    items = [("cmp", " ".join(pieces))] + [(f"c{i}", pieces[i]) for i in range(3)] + [("noise", noise)]
    return items


def test_marginal_selection_keeps_adding_while_new_coverage_remains():
    from faustcoder.neardup import select_collective_contributors
    whole = frozenset(f"s{i}" for i in range(12))
    overlaps = {
        "a": frozenset(f"s{i}" for i in range(4)),
        "b": frozenset(f"s{i}" for i in range(4, 8)),
        "c": frozenset({"s8", "s9"}),
        "d": frozenset({"s10", "s11"}),
        "noise": frozenset({"s0"}),
    }
    # a and b already cover more than half. d still adds shingles, so it joins.
    assert select_collective_contributors(overlaps, whole) == ["a", "b", "c", "d"]


def test_opt_in_catches_three_way_split_and_excludes_noise():
    items = _three_way_items(_symbol_alphabet())
    result, groups = _groups(items, ["cmp"], marginal_coverage=True)
    assert {group["stream"] for group in groups} == {"raw", "canonical"}
    assert all(group["contributors"] == ["c0", "c1", "c2"] for group in groups)
    assert all(result[f"c{i}"] == result["cmp"] for i in range(3))
    assert result["noise"] != result["cmp"]


def test_default_any_overlap_joins_incidental_noise():
    items = _three_way_items(_symbol_alphabet())
    result, groups = _groups(items, ["cmp"])
    assert groups
    assert all("noise" in group["contributors"] for group in groups)
    assert result["noise"] == result["cmp"]
    assert all(result[f"c{i}"] == result["cmp"] for i in range(3))


def test_opt_in_catches_interleaved_three_way_split():
    alphabet = _symbol_alphabet()
    chunks = [_piece(alphabet, i * 14, 14).split() for i in range(6)]
    order = [host + part * 3 for part in range(2) for host in range(3)]
    whole = " ".join(" ".join(chunks[i]) for i in order)
    pad = " ".join([alphabet[200]] * 30)
    items = [("cmp", whole)]
    for host in range(3):
        body = " ".join(" ".join(chunks[host + part * 3]) + " " + pad for part in range(2))
        items.append((f"h{host}", body))
    result, groups = _groups(items, ["cmp"], marginal_coverage=True)
    assert groups
    assert all(group["contributors"] == ["h0", "h1", "h2"] for group in groups)
    assert all(result[f"h{i}"] == result["cmp"] for i in range(3))
    # Two hosts already cover half, so the removed early stop is what adds the third.
    from faustcoder.neardup import shingles as token_shingles
    covered = token_shingles(tokens(items[1][1])) | token_shingles(tokens(items[2][1]))
    whole_shingles = token_shingles(tokens(whole))
    assert len(covered & whole_shingles) * 2 >= len(whole_shingles)


def test_opt_in_catches_two_independent_three_way_copies():
    alphabet = _symbol_alphabet()
    items = []
    cursor = 0
    first_piece = None
    for name in ("a", "b"):
        pieces = []
        for index in range(3):
            text = _piece(alphabet, cursor, 18)
            cursor += 18
            pieces.append(text)
            if first_piece is None:
                first_piece = text
            items.append((f"{name}{index}", text))
        items.append((f"cmp{name}", " ".join(pieces)))
    # Subset of a selected piece, plus tokens absent from both comparisons.
    noise = " ".join(first_piece.split()[:5]) + " " + " ".join(alphabet[cursor:cursor + 30])
    items.append(("noise", noise))
    result, groups = _groups(items, ["cmpa", "cmpb"], marginal_coverage=True)
    assert result["cmpa"] != result["cmpb"]
    for name in ("a", "b"):
        members = [f"{name}{index}" for index in range(3)]
        assert all(result[member] == result[f"cmp{name}"] for member in members)
        mine = [group for group in groups if group["comparison"] == f"cmp{name}"]
        assert {group["stream"] for group in mine} == {"raw", "canonical"}
        assert all(group["contributors"] == members for group in mine)
    assert result["noise"] != result["cmpa"]
    assert result["noise"] != result["cmpb"]
    for stream in ("raw", "canonical"):
        streamed = [group for group in groups if group["stream"] == stream]
        assert streamed
        assert all("noise" not in group["contributors"] for group in streamed)


def _assert_opt_in_k_way(k):
    alphabet = _symbol_alphabet()
    pieces = [_piece(alphabet, i * 18, 18) for i in range(k)]
    noise = " ".join(pieces[0].split()[:5]) + " " + " ".join(alphabet[k * 18:k * 18 + 30])
    items = [("cmp", " ".join(pieces))] + [(f"c{i}", pieces[i]) for i in range(k)] + [("noise", noise)]
    result, groups = _groups(items, ["cmp"], marginal_coverage=True)
    expect = sorted(f"c{i}" for i in range(k))
    assert {group["stream"] for group in groups} == {"raw", "canonical"}
    for stream in ("raw", "canonical"):
        streamed = [group for group in groups if group["stream"] == stream]
        assert streamed
        assert all(group["contributors"] == expect for group in streamed)
        assert all("noise" not in group["contributors"] for group in streamed)
    assert all(result[name] == result["cmp"] for name in expect)
    assert result["noise"] != result["cmp"]


def test_opt_in_four_way_includes_every_copy_and_excludes_noise():
    _assert_opt_in_k_way(4)


def test_opt_in_five_way_includes_every_copy_and_excludes_noise():
    _assert_opt_in_k_way(5)


def test_opt_in_six_way_includes_every_copy_and_excludes_noise():
    _assert_opt_in_k_way(6)


def test_opt_in_group_id_keeps_marginal_marker():
    """N6: dropping the marginal mark makes the group id the bare main key."""
    from faustcoder.canonical import canonical_bytes, sha256_prefixed
    from faustcoder.neardup import COLLECTIVE_MIN_MARGINAL
    items = _three_way_items(_symbol_alphabet())
    _, groups = _groups(items, ["cmp"], marginal_coverage=True)
    assert groups
    marker = {"marginal_coverage": True, "collective_min_marginal": COLLECTIVE_MIN_MARGINAL}
    for group in groups:
        canonical = group["stream"] == "canonical"
        bare = [group["comparison"], group["contributors"], canonical, group["floor"]]
        marked = [*bare, marker]
        assert group["group_id"] == sha256_prefixed(canonical_bytes(marked))
        assert group["group_id"] != sha256_prefixed(canonical_bytes(bare))
        assert group["marginal_coverage"] is True
        assert group["collective_min_marginal"] == COLLECTIVE_MIN_MARGINAL


def test_scope_off_group_id_is_the_unmarked_main_key():
    from faustcoder.canonical import canonical_bytes, sha256_prefixed
    alphabet = _symbol_alphabet()
    pieces = [_piece(alphabet, i * 18, 18) for i in range(3)]
    items = [("cmp", " ".join(pieces))] + [(f"c{i}", pieces[i]) for i in range(3)]
    _, groups = _groups(items, ["cmp"])
    assert groups
    for group in groups:
        canonical = group["stream"] == "canonical"
        bare = [group["comparison"], group["contributors"], canonical, group["floor"]]
        assert group["group_id"] == sha256_prefixed(canonical_bytes(bare))
        assert "idiom_filter" not in group
        assert "marginal_coverage" not in group


def test_enabled_filter_changes_group_id_when_coverage_matches():
    alphabet = _symbol_alphabet()
    pieces = [_piece(alphabet, i * 18, 18) for i in range(3)]
    items = [("cmp", " ".join(pieces))] + [(f"c{i}", pieces[i]) for i in range(3)]
    repos = {key: "repo/" + key for key, _ in items}
    _, off = _groups(items, ["cmp"])
    _, on = _groups(items, ["cmp"], scope=IdiomFilter(200), item_repos=repos)
    assert off and on
    assert [group["contributors"] for group in off] == [group["contributors"] for group in on]
    assert {group["group_id"] for group in off}.isdisjoint(group["group_id"] for group in on)


def test_collective_min_marginal_applies_only_when_opt_in(monkeypatch):
    from faustcoder import neardup
    monkeypatch.setattr(neardup, "COLLECTIVE_MIN_MARGINAL", 10**6)
    alphabet = _symbol_alphabet()
    pieces = [_piece(alphabet, i * 18, 18) for i in range(3)]
    items = [("cmp", " ".join(pieces))] + [(f"c{i}", pieces[i]) for i in range(3)]
    _, default_groups = _groups(items, ["cmp"])
    assert default_groups
    _, opted = _groups(items, ["cmp"], marginal_coverage=True)
    assert opted == []


def test_group_ids_bind_filter_settings_when_coverage_matches():
    alphabet = _symbol_alphabet()
    pieces = [_piece(alphabet, i * 18, 18) for i in range(3)]
    items = [("cmp", " ".join(pieces))] + [(f"c{i}", pieces[i]) for i in range(3)]
    repos = {key: "repo/" + key for key, _ in items}
    _, low = _groups(items, ["cmp"], scope=IdiomFilter(200), item_repos=repos)
    _, high = _groups(items, ["cmp"], scope=IdiomFilter(400), item_repos=repos)
    assert low and high
    assert [group["contributors"] for group in low] == [group["contributors"] for group in high]
    assert {group["group_id"] for group in low}.isdisjoint(group["group_id"] for group in high)


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
    result = cluster_families(items, ["cmp"], scope=IdiomFilter(3),
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
    assert IdiomFilter.__module__ == "faustcoder.idiom_filter"
    for bad in (1, True, "2", 2.5):
        with pytest.raises(ValueError):
            IdiomFilter(5, idiom_min_repos=bad)


def test_opt_in_thirteen_way_includes_every_copy_and_excludes_noise():
    _assert_opt_in_k_way(13)

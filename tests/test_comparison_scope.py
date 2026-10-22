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
    assert ComparisonScope(5).describe() == {"version": "t06-comparison-scope-df.v1", "idiom_min_docs": 5}
    for bad in (1, 0, -3, 2.0, True, "5"):
        with pytest.raises(ValueError):
            ComparisonScope(bad)
    with pytest.raises(ValueError):
        ComparisonScope(5, version="other")
    with pytest.raises(TypeError):
        cluster_families([("a", "x")], scope={"idiom_min_docs": 5})


def test_idiom_counts_only_non_comparison_items():
    sets = {"a": frozenset({"s1", "s2"}), "b": frozenset({"s1"}), "cmp": frozenset({"s1", "s2"})}
    assert idiom_shingles(sets, {"cmp"}, 2) == frozenset({"s1"})
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
    got = cluster_families(items, ["cmp"], evidence=ev, scope=ComparisonScope(3))
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
    got = cluster_families(items, ["cmp"], scope=ComparisonScope(3))
    assert got["copy"] == got["cmp"]


def test_scope_keeps_unique_containment():
    items = _pool()
    comp = dict(items)["cmp"]
    unique = _prog("rej", 3)
    assert shingles(tokens(unique))
    # Copy only the unique rejected part (under the floor): reverse containment
    # on the scoped comparison shingles still joins.
    items.append(("excerpt", _prog("mine2", 2) + "\n" + unique))
    got = cluster_families(items, ["cmp"], scope=ComparisonScope(3))
    assert got["excerpt"] == got["cmp"]
    assert comp  # comparison unchanged


def test_scope_never_changes_exact_or_jaccard_between_pool_items():
    items = _pool() + [("dup", dict(_pool())["c0"])]
    got = cluster_families(items, ["cmp"], scope=ComparisonScope(3))
    assert got["dup"] == got["c0"]


def test_scope_verbatim_run_is_the_join_reason_for_a_padded_copy():
    items = _pool()
    comp_lines = dict(items)["cmp"].split("\n")
    chunk = "\n".join(comp_lines[:6])  # about 50 contiguous tokens of the comparison
    assert len(tokens(chunk)) >= 40
    items.append(("padded", _prog("pad", 40) + "\n" + chunk))
    ev = []
    got = cluster_families(items, ["cmp"], evidence=ev, scope=ComparisonScope(3))
    assert got["padded"] == got["cmp"]
    assert any(e.get("left") == "padded" and e["reason"] == "verbatim_run" for e in ev)

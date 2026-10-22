"""Before/after diff of two batch1_review outputs (labels, links, groups).

"Labels" here are detector outputs only: family id and quarantine_candidate
per unit. They are not COPY/NOT_COPY labels. "Links" are joining-forest
edges and collective-support sets. Nothing here approves anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def load(root: Path):
    ledger = json.loads((root / "candidate-ledger.json").read_text())["units"]
    match = json.loads((root / "match-evidence.json").read_text())
    short = json.loads((root / "short-collision-groups.json").read_text())["groups"]
    rows = {r["unit_id"]: r for r in ledger}
    edges = match["edges"]
    links = {(e["left"], e["right"], e["reason"], e["stream"]) for e in edges if "left" in e}
    collective = {(e["comparison"], e["stream"]): e for e in edges if e["reason"] == "collective_support"}
    return rows, edges, links, collective, short


def path_reasons(row, edges):
    return sorted({edges[i]["reason"] + ":" + edges[i]["stream"] for i in row.get("evidence_path", [])})


def reason_counts(links) -> dict:
    return dict(Counter(f"{r}:{s}" for _, _, r, s in links))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--cohort", type=Path, help="S1 scope-ledger.UNAPPROVED.json (174-unit deep-review scope)")
    ap.add_argument("--focus", nargs="*", default=[], help="unit ids to report individually")
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    b_rows, b_edges, b_links, b_coll, b_short = load(a.before)
    a_rows, a_edges, a_links, a_coll, a_short = load(a.after)
    if set(b_rows) != set(a_rows):
        raise ValueError("unit sets differ")
    cohort = set()
    if a.cohort:
        led = json.loads(a.cohort.read_text())
        cohort = {u["unit_id"] for u in led["units"] if u.get("category") != "deferred"}
    units = []
    for k in sorted(b_rows):
        br, ar = b_rows[k], a_rows[k]
        units.append(dict(
            unit_id=k, repo=br["repo"], path=br["path"], function=br.get("function"),
            in_cohort=k in cohort,
            quarantine_before=br.get("quarantine_candidate"), quarantine_after=ar.get("quarantine_candidate"),
            family_before=br.get("family"), family_after=ar.get("family"),
            path_reasons_before=path_reasons(br, b_edges), path_reasons_after=path_reasons(ar, a_edges),
        ))
    flips = Counter((u["quarantine_before"], u["quarantine_after"]) for u in units)
    def count(sel):
        return dict(
            units=len(sel),
            quarantine_before=sum(bool(u["quarantine_before"]) for u in sel),
            quarantine_after=sum(bool(u["quarantine_after"]) for u in sel),
            unflagged_by_scope=sum(bool(u["quarantine_before"]) and u["quarantine_after"] is False for u in sel),
            newly_flagged=sum(u["quarantine_before"] is False and bool(u["quarantine_after"]) for u in sel),
            family_id_changed=sum(u["family_before"] != u["family_after"] for u in sel),
            unflagged_after_by_repo=dict(Counter(u["repo"] for u in sel if u["quarantine_after"] is False)),
        )
    coll = []
    for key in sorted(set(b_coll) | set(a_coll)):
        be, ae = b_coll.get(key), a_coll.get(key)
        coll.append(dict(
            comparison=key[0], stream=key[1],
            before=None if not be else dict(group_id=be["group_id"], contributors=len(be["contributors"]),
                                           covered=be["covered"], denominator=be["denominator"]),
            after=None if not ae else dict(group_id=ae["group_id"], contributors=len(ae["contributors"]),
                                          covered=ae["covered"], denominator=ae["denominator"]),
        ))
    scope_rows = [e for e in a_edges if e["reason"] in ("idiom_filter", "comparison_scope")]
    result = dict(
        note="Detector outputs only; not COPY/NOT_COPY labels; nothing approved.",
        before=str(a.before), after=str(a.after),
        before_tree_sha256=hashlib.sha256(json.dumps(tree_hashes(a.before), sort_keys=True).encode()).hexdigest(),
        after_tree_sha256=hashlib.sha256(json.dumps(tree_hashes(a.after), sort_keys=True).encode()).hexdigest(),
        before_files={f: sha(a.before / f) for f in ("candidate-ledger.json", "match-evidence.json", "short-collision-groups.json", "summary.json", "binding.json")},
        after_files={f: sha(a.after / f) for f in ("candidate-ledger.json", "match-evidence.json", "short-collision-groups.json", "summary.json", "binding.json")},
        idiom_filter=scope_rows,
        pool=count(units), cohort_174=count([u for u in units if u["in_cohort"]]) if cohort else None,
        quarantine_transitions={f"{k[0]}->{k[1]}": v for k, v in flips.items()},
        links=dict(before=len(b_links), after=len(a_links), removed=len(b_links - a_links), added=len(a_links - b_links),
                   reasons_before=reason_counts(b_links), reasons_after=reason_counts(a_links)),
        collective_support_sets=dict(before=len(b_coll), after=len(a_coll),
                                     group_id_changed=sum(1 for c in coll if c["before"] and c["after"] and c["before"]["group_id"] != c["after"]["group_id"]),
                                     detail=coll),
        short_collision_groups=dict(before=len(b_short), after=len(a_short), identical=b_short == a_short),
        focus=[u for u in units if u["unit_id"] in set(a.focus)],
    )
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output / "diff-summary.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    with (a.output / "unit-diff.jsonl").open("w") as fh:
        for u in units:
            fh.write(json.dumps(u, sort_keys=True) + "\n")
    with (a.output / "links-removed.jsonl").open("w") as fh:
        for link in sorted(b_links - a_links):
            fh.write(json.dumps(link) + "\n")
    with (a.output / "links-added.jsonl").open("w") as fh:
        for link in sorted(a_links - b_links):
            fh.write(json.dumps(link) + "\n")
    print(json.dumps({k: result[k] for k in ("pool", "cohort_174", "quarantine_transitions", "links", "short_collision_groups")}, indent=1))


if __name__ == "__main__":
    main()

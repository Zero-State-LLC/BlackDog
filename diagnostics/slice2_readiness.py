"""Offline Slice 2 candidate screening; never approves or freezes a dataset.

Reads only explicitly supplied local blob locations and verifies every used blob.
No network, compiler, training, key generation or production store writes.
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from collections import Counter, defaultdict

from faustcoder.acquire import git_blob_sha1
from faustcoder.canonical import canonical_bytes, content_digest_for, sha256_prefixed
from faustcoder.function_spans import verify_manifest, extract_span
from faustcoder.inventory import parse_corpus
from faustcoder.normalize import normalize_bytes
from faustcoder.neardup import cluster_families, canonical_tokens, COMPARISON_VERSION
from faustcoder.floor_readiness import assess_plants
from faustcoder.split import audit_assignments


def run(
    repo: Path,
    candidate_path: Path,
    sources_path: Path,
    discovery_path: Path,
    qualification_path: Path,
    output: Path,
) -> dict:
    inputs = {
        name: json.loads(path.read_text())
        for name, path in {
            "inventory": repo / "corpus/rights-inventory.v1.json",
            "notice": repo / "corpus/notice-manifest.v1.json",
            "candidate": candidate_path,
            "sources": sources_path,
            "discovery": discovery_path,
            "qualification": qualification_path,
        }.items()
    }
    corpus = parse_corpus(inputs["inventory"], inputs["notice"])
    # This pins candidate bytes for this diagnostic only, not independent approval.
    spans = verify_manifest(
        inputs["candidate"],
        content_digest_for(inputs["candidate"]),
        corpus.units,
        corpus.inventory_digest,
        corpus.notice_digest,
    )
    locations = dict(inputs["sources"])
    for blob, paths in inputs["discovery"]["blob_locations"].items():
        if paths:
            locations.setdefault(blob, paths[0])
    blobs = {}
    missing = set()
    failed = {}
    for unit in corpus.units + corpus.comparisons:
        if unit.blob_sha in blobs or unit.blob_sha in missing:
            continue
        path = locations.get(unit.blob_sha)
        if not path or not Path(path).is_file():
            missing.add(unit.blob_sha)
            continue
        raw = Path(path).read_bytes()
        if git_blob_sha1(raw) != unit.blob_sha:
            raise ValueError("local blob mismatch: " + unit.blob_sha)
        blobs[unit.blob_sha] = raw
    texts = []
    rows = []
    comparison = []
    seen_comparison = set()
    for unit in corpus.units:
        if unit.blob_sha not in blobs:
            continue
        raw = blobs[unit.blob_sha]
        if unit.function:
            raw = extract_span(raw, spans[unit.unit_id])
        try:
            norm = normalize_bytes(raw)
        except Exception as exc:
            failed[unit.unit_id] = str(exc)
            continue
        texts.append((unit.unit_id, norm.text))
        rows.append(
            {
                "unit_id": unit.unit_id,
                "repo": unit.repo,
                "pin": unit.pin,
                "path": unit.path,
                "function": unit.function,
                "blob_sha": unit.blob_sha,
                "original_sha256": norm.original_sha256,
                "normalized_sha256": norm.normalized_sha256,
                "eligible_for": list(unit.eligible_for),
                "impulse": unit.impulse,
                "training_only": list(unit.eligible_for) == ["train"],
                "approval": "unapproved_candidate",
            }
        )
    for unit in corpus.comparisons:
        if unit.blob_sha not in blobs or unit.blob_sha in seen_comparison:
            continue
        seen_comparison.add(unit.blob_sha)
        key = "comparison:" + unit.blob_sha
        try:
            text = normalize_bytes(blobs[unit.blob_sha]).text
        except Exception as exc:
            failed[key] = str(exc)
            continue
        texts.append((key, text))
        comparison.append(key)
    output.mkdir(parents=True, exist_ok=False)

    def save(name, data):
        (output / name).write_bytes(canonical_bytes(data) + b"\n")

    code_paths = [
        "faustcoder/neardup.py",
        "faustcoder/snapshot.py",
        "faustcoder/function_spans.py",
        "faustcoder/split.py",
        "faustcoder/floor_readiness.py",
        "diagnostics/slice2_readiness.py",
    ]
    binding = {
        "inputs": {k: content_digest_for(v) for k, v in inputs.items()},
        "code": {
            name: sha256_prefixed((repo / name).read_bytes()) for name in code_paths
        },
        "comparison_version": COMPARISON_VERSION,
        "production_approved": False,
    }
    save("binding.json", binding)
    summaries = {}
    maps = {}
    quarantines = {}
    for floor in (40, 30, 20):
        families = cluster_families(texts, comparison, floor=floor)
        maps[floor] = families
        bad = {families[key] for key in comparison}
        quarantined = sorted(
            row["unit_id"] for row in rows if families[row["unit_id"]] in bad
        )
        quarantines[floor] = set(quarantined)
        groups = defaultdict(list)
        for row in rows:
            groups[families[row["unit_id"]]].append(row["unit_id"])
        save(
            f"families-{floor}.json",
            {"families": families, "quarantine_candidates": quarantined},
        )
        summaries[str(floor)] = {
            "families": len(set(families.values())),
            "quarantine_candidates": len(quarantined),
            "cleared_candidate_rows": len(rows) - len(quarantined),
        }
        print("floor", floor, summaries[str(floor)], flush=True)
    natural = sorted(set().union(*quarantines.values()))
    save(
        "natural-review-queue.json",
        {
            "origin": "union of shipping comparison detections; detector-biased candidate pool",
            "labels_frozen": False,
            "items": [
                {
                    "unit_id": key,
                    "flagged_floors": [
                        f for f in (40, 30, 20) if key in quarantines[f]
                    ],
                    "adjudication": "UNADJUDICATED",
                }
                for key in natural
            ],
        },
    )
    # Exact replay check at the operating floor, with reversed traversal.
    if maps[40] != cluster_families(
        list(reversed(texts)), list(reversed(comparison)), floor=40
    ):
        raise ValueError("family replay mismatch")
    units = {r["unit_id"] for r in rows}
    dependencies = {
        r["unit_id"]: r["dependency_evidence"].get("direct_candidate_unit_ids", [])
        for r in inputs["qualification"]["units"]
        if r["unit_id"] in units
    }
    for key in units:
        dependencies.setdefault(key, [])
    rows = [dict(row, duplicate_family=maps[40][row["unit_id"]]) for row in rows]
    assignments = {key: "train" for key in units}
    assignment_errors = audit_assignments(rows, assignments, dependencies)
    external = sum(
        bool(r["dependency_evidence"].get("qualified_references"))
        for r in inputs["qualification"]["units"]
    )
    exact = defaultdict(list)
    for key, text in texts:
        tok = canonical_tokens(text)
        if 0 < len(tok) < 15:
            exact[content_digest_for(list(tok))].append(key)
    short_groups = [sorted(group) for group in exact.values() if len(group) > 1]
    save(
        "sub15-canonical-review.json",
        {
            "groups": short_groups,
            "idiom_pairs_approved": [],
            "status": "requires human adjudication; no exemption applied",
        },
    )
    save(
        "dependency-family-audit.json",
        {
            "assignments": assignments,
            "dependencies": dependencies,
            "assignment_errors": assignment_errors,
            "external_member_units": external,
            "closure_status": "proposed lexical overapproximation, not certified",
            "development": [],
            "holdout": [],
            "rows": rows,
        },
    )
    # No fabricated 100-item cells: report actual absent approved plant evidence.
    floor_readiness = assess_plants([], {str(f): {} for f in (40, 30, 20)})
    save("floor-readiness.json", floor_readiness)
    blockers = [
        "independent span/closure approval absent",
        "qualified independent development data absent",
        "newly authored holdout and separate custody absent",
        "trusted split signer not configured",
        "real-window/two-project cleared-host planted gold set absent",
        "natural-copy and FP human adjudication absent",
        "explicit floor decision absent",
        "proposed dependencies are not certified",
    ]
    if missing:
        blockers.append("missing pinned blobs")
    report = {
        "record_type": "Slice2Readiness",
        "candidate_rows": len(rows),
        "verified_blobs": len(blobs),
        "missing_blob_count": len(missing),
        "missing_blobs": sorted(missing),
        "normalization_failures": failed,
        "comparison_blobs": len(comparison),
        "floors": summaries,
        "order_invariant": True,
        "projects": dict(Counter(row["repo"] for row in rows)),
        "sub15_review_groups": len(short_groups),
        "surviving_projects": dict(
            Counter(
                row["repo"] for row in rows if row["unit_id"] not in quarantines[40]
            )
        ),
        "blockers": blockers,
        "production_approved": False,
        "split_frozen": False,
        "token_floor": 40,
        "token_floor_status": "provisional",
    }
    save("summary.json", report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in (
        "repo",
        "candidate",
        "sources",
        "discovery",
        "qualification",
        "output",
    ):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    print(
        json.dumps(
            run(a.repo, a.candidate, a.sources, a.discovery, a.qualification, a.output),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

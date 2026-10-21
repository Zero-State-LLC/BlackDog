"""Build source-bound Batch 1 review packets. Never clears rights or freezes T07."""

import argparse
import json
from collections import defaultdict, Counter, deque
from dataclasses import asdict
from pathlib import Path
from faustcoder.acquire import git_blob_sha1
from faustcoder.canonical import canonical_bytes, content_digest_for, sha256_prefixed
from faustcoder.inventory import parse_corpus
from faustcoder.function_spans import verify_manifest, extract_span
from faustcoder.normalize import normalize_bytes
from faustcoder.neardup import cluster_families, canonical_tokens, tokens, shingles


def evidence_paths(edges, comparison_ids):
    """Multi-source shortest paths over observed joining edges, not copy labels."""
    adjacency = defaultdict(list)
    for index, edge in enumerate(edges):
        if "left" in edge:
            adjacency[edge["left"]].append((edge["right"], index))
            adjacency[edge["right"]].append((edge["left"], index))
    previous = {key: None for key in comparison_ids}
    queue = deque(sorted(comparison_ids))
    while queue:
        current = queue.popleft()
        for neighbor, index in sorted(adjacency[current]):
            if neighbor not in previous:
                previous[neighbor] = (current, index)
                queue.append(neighbor)
    return previous


def trace_path(key, previous):
    result = []
    while key in previous and previous[key] is not None:
        key, index = previous[key]
        result.append(index)
    return result


def run(repo, acquisition, candidate, qualification, groups, baseline, output):
    inventory = json.loads((repo / "corpus/rights-inventory.v1.json").read_text())
    notice = json.loads((repo / "corpus/notice-manifest.v1.json").read_text())
    corpus = parse_corpus(inventory, notice)
    proposal = json.loads(candidate.read_text())
    spans = verify_manifest(
        proposal,
        content_digest_for(proposal),
        corpus.units,
        corpus.inventory_digest,
        corpus.notice_digest,
    )
    locations = json.loads((acquisition / "sources.json").read_text())
    discovery = json.loads((acquisition / "discovery.json").read_text())
    for blob, paths in discovery["blob_locations"].items():
        if paths:
            locations.setdefault(blob, paths[0])
    qualified = json.loads(qualification.read_text())
    qual = {u["unit_id"]: u for u in qualified["units"]}
    plans = json.loads(groups.read_text())
    plan_for = {key: g for g in plans for key in g["unit_ids"]}
    old = json.loads(baseline.read_text())
    oldrows = {r["unit_id"]: r for r in old["rows"]}
    output.mkdir(parents=True, exist_ok=False)
    (output / "sources").mkdir()
    (output / "packets").mkdir()

    def save(name, data):
        (output / name).write_bytes(
            canonical_bytes(json.loads(json.dumps(data))) + b"\n"
        )

    bindings = {
        "inventory": content_digest_for(inventory),
        "notice": content_digest_for(notice),
        "candidate": content_digest_for(proposal),
        "qualification": content_digest_for(qualified),
        "group_plans": content_digest_for(plans),
        "baseline": content_digest_for(old),
        "sources": content_digest_for(locations),
        "code": {
            f: sha256_prefixed((repo / f).read_bytes())
            for f in (
                "diagnostics/batch1_review.py",
                "faustcoder/neardup.py",
                "faustcoder/normalize.py",
                "faustcoder/inventory.py",
                "faustcoder/function_spans.py",
            )
        },
        "production_approved": False,
        "t07_frozen": False,
        "token_floor": 40,
        "token_floor_status": "provisional",
    }
    save("binding.json", bindings)
    blobs = {}
    missing = []
    for u in corpus.units + corpus.comparisons:
        if u.blob_sha in blobs:
            continue
        path = locations.get(u.blob_sha)
        if not path or not Path(path).is_file():
            missing.append(u.blob_sha)
            continue
        raw = Path(path).read_bytes()
        if git_blob_sha1(raw) != u.blob_sha:
            raise ValueError("source hash mismatch: " + u.blob_sha)
        blobs[u.blob_sha] = raw
    text = {}
    metadata = {}
    rows = []
    comparison = []
    failures = []
    for u in corpus.units:
        row = asdict(u)
        row.update(
            production_approved=False,
            adjudication="UNREVIEWED",
            original_scope=u.unit_id in oldrows,
        )
        if u.blob_sha not in blobs:
            row.update(status="blocked_missing_blob", blockers=["missing_pinned_blob"])
            rows.append(row)
            continue
        raw = blobs[u.blob_sha]
        span = spans.get(u.unit_id) if u.function else None
        if u.function:
            raw = extract_span(raw, span)
        (output / "sources" / f"{u.unit_id}.dsp").write_bytes(raw)
        row.update(
            source_path=locations[u.blob_sha],
            selected_source=f"sources/{u.unit_id}.dsp",
            original_span=span,
            source_sha256=sha256_prefixed(raw),
        )
        try:
            norm = normalize_bytes(raw)
        except Exception as exc:
            row.update(
                status="blocked_normalization",
                blockers=["normalization_failed"],
                error=str(exc),
            )
            failures.append(u.unit_id)
            rows.append(row)
            continue
        text[u.unit_id] = norm.text
        metadata[u.unit_id] = dict(
            repo=u.repo,
            pin=u.pin,
            path=u.path,
            function=u.function,
            blob_sha=u.blob_sha,
            decision=u.decision,
            selected_source=row["selected_source"],
        )
        q = qual.get(u.unit_id)
        plan = plan_for.get(u.unit_id)
        row.update(
            normalized_sha256=norm.normalized_sha256,
            raw_tokens=len(tokens(norm.text)),
            canonical_tokens=len(canonical_tokens(norm.text)),
            prior_qualification=q or {"status": "not_previously_contract_qualified"},
            proposed_dependencies=q["dependency_evidence"]
            if q
            else {"status": "unreviewed_whole_file"},
            behavior_plan=plan["behavior_plan"]
            if plan
            else {
                "status": "needs_independent_contract",
                "requirements": [
                    "resolve imports and rights",
                    "declare controls/input/output shapes",
                    "independent semantic reference at 44100/48000",
                    "negative dependency/reference controls; unchanged limits/tolerances",
                ],
            },
            group=plan["group"] if plan else u.repo + "::" + u.entry_id,
            blockers=[
                "independent_source_closure_review",
                "human_leakage_adjudication",
            ],
            status="candidate_only",
        )
        rows.append(row)
    for u in corpus.comparisons:
        key = "comparison:" + u.blob_sha
        if key in text or u.blob_sha not in blobs:
            continue
        try:
            norm = normalize_bytes(blobs[u.blob_sha])
        except Exception:
            failures.append(key)
            continue
        text[key] = norm.text
        comparison.append(key)
        metadata[key] = dict(
            repo=u.repo,
            pin=u.pin,
            path=u.path,
            function="WHOLE_BLOB_COMPARISON",
            blob_sha=u.blob_sha,
            decision=u.decision,
            source_path=locations[u.blob_sha],
            inventory_aliases=[
                asdict(v) for v in corpus.comparisons if v.blob_sha == u.blob_sha
            ],
        )
    save("source-index.json", metadata)
    edges = []
    families = cluster_families(sorted(text.items()), comparison, evidence=edges)
    # A joining forest must reconstruct the complete family membership exactly.
    previous = evidence_paths(edges, comparison)
    tainted = {families[k] for k in comparison}
    if {k for k in text if families[k] in tainted} != set(previous):
        raise ValueError("trace does not explain quarantined family membership")
    short = defaultdict(list)
    for k, t in text.items():
        tok = canonical_tokens(t)
        if 0 < len(tok) < 15:
            short[content_digest_for(list(tok))].append(k)
    shortgroups = [sorted(v) for v in short.values() if len(v) > 1]
    save(
        "short-collision-groups.json",
        {"groups": shortgroups, "adjudication": "UNREVIEWED"},
    )
    for e in edges:
        if "left" not in e:
            continue
        left = text[e["left"]]
        right = text[e["right"]]
        tokenize = canonical_tokens if e["stream"] == "canonical" else tokens
        shared = sorted(shingles(tokenize(left)) & shingles(tokenize(right)))
        e["shared_shingle_example"] = shared[0] if shared else None
        e["left_excerpt"] = left[:240]
        e["right_excerpt"] = right[:240]
        e["caution"] = (
            "collective contribution is not individual copy proof"
            if e["reason"] == "collective_union"
            else "detector evidence, not human adjudication"
        )
    save(
        "match-evidence.json",
        {
            "scope": "deterministic joining forest; not exhaustive pairwise matches",
            "edges": edges,
            "families": families,
            "comparison_ids": comparison,
        },
    )
    byid = {r["unit_id"]: r for r in rows}
    packets = defaultdict(list)
    for row in rows:
        k = row["unit_id"]
        if k not in text:
            continue
        row["family"] = families[k]
        row["quarantine_candidate"] = families[k] in tainted
        row["evidence_path"] = trace_path(k, previous)
        q = qual.get(k, {})
        row["bounded_contract_pass"] = q.get("status") == "bounded_contract_pass"
        deps = q.get("dependency_evidence", {})
        row["dependency_closure_unit_ids"] = deps.get(
            "transitive_candidate_unit_ids", []
        )
        row["unresolved_external_members"] = deps.get("qualified_references", [])
        row["dependency_not_in_ledger"] = [
            d for d in row["dependency_closure_unit_ids"] if d not in byid
        ]
        if row["quarantine_candidate"]:
            row["blockers"].append("quarantine_match_requires_review")
        if row["unresolved_external_members"]:
            row["blockers"].append("external_dependency_review")
        if not row["bounded_contract_pass"]:
            row["blockers"].append("executable_semantic_contract_required")
        if missing or failures:
            row["blockers"].append("incomplete_comparison_scope")
        row["review_priority"] = (
            "P0_bounded_contract"
            if row["bounded_contract_pass"]
            else "P1_eval_project"
            if "eval" in row["eligible_for"]
            and row["repo"] != "grame-cncm/faustlibraries"
            else "P2_remaining"
        )
        packets[row["group"]].append(k)
    if not set(oldrows) <= set(byid):
        raise ValueError("lost original candidates")
    save(
        "candidate-ledger.json",
        {
            "units": rows,
            "production_approved": False,
            "t07_frozen": False,
            "token_floor": 40,
            "token_floor_status": "provisional",
        },
    )
    save(
        "comparison-ledger.json",
        {
            "units": [asdict(u) for u in corpus.comparisons],
            "missing_blobs": sorted(set(missing)),
            "normalization_failures": failures,
            "comparison_only": True,
        },
    )
    packet_index = []
    for group, members in sorted(packets.items()):
        packet_id = content_digest_for(group).split(":")[1][:16]
        indexes = sorted({i for k in members for i in byid[k]["evidence_path"]})
        packet = dict(
            group=group,
            unit_ids=members,
            evidence_edge_indexes=indexes,
            collective_support_ids=sorted(
                {edges[i]["group_id"] for i in indexes if "group_id" in edges[i]}
            ),
            proposed_dependency_closure=sorted(
                {d for k in members for d in byid[k]["dependency_closure_unit_ids"]}
            ),
            decision="UNREVIEWED",
            production_approved=False,
            review_instructions=[
                "Verify source and notice for each member; group approval is not a blanket rights grant",
                "Inspect selected source, direct evidence path and collective support; label COPY/NOT_COPY only on content",
                "Review scope/overloads/external dependencies; retain unresolved cases as blocked",
                "Approve concrete compiler and semantic contracts before Batch 2 execution",
            ],
        )
        save("packets/" + packet_id + ".json", packet)
        lines = [
            "# " + group,
            "",
            "Status: UNREVIEWED; no admission approval.",
            "",
            "| Unit | Function / path | Priority | Quarantine | Prior contract | Evidence path |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for k in members:
            v = byid[k]
            label = (v["function"] or v["path"]).replace("|", "\\|")
            lines.append(
                f"| {k} | {label} | {v['review_priority']} | {v['quarantine_candidate']} | {v['bounded_contract_pass']} | {v['evidence_path']} |"
            )
        lines += [
            "",
            "Full source, rights, dependency and behavior details are keyed by unit in candidate-ledger.json.",
            "Match paths index match-evidence.json; collective support sets are not pairwise proof.",
            "",
            *["- " + x for x in packet["review_instructions"]],
        ]
        (output / "packets" / f"{packet_id}.md").write_text("\n".join(lines) + "\n")
        packet_index.append(
            dict(
                packet_id=packet_id,
                group=group,
                members=len(members),
                bounded_pass=sum(byid[k]["bounded_contract_pass"] for k in members),
            )
        )
    save("packet-index.json", packet_index)
    first_wave = [
        r["unit_id"]
        for r in rows
        if r.get("bounded_contract_pass")
        or r.get("review_priority") == "P1_eval_project"
    ]
    save(
        "batch2-proposed-subset.json",
        dict(
            unit_ids=first_wave,
            selection="all bounded-contract passes plus all non-faustlibraries eval-project candidates",
            admitted=False,
            dependencies_must_be_reviewed=True,
            human_checkpoint="approve individual dispositions and contracts; unresolved members stay quarantined",
        ),
    )
    save(
        "review-decisions.UNAPPROVED.json",
        dict(
            units=[
                dict(
                    unit_id=r["unit_id"],
                    copy_label="UNREVIEWED",
                    closure="UNREVIEWED",
                    contract="UNREVIEWED",
                    reviewer=None,
                )
                for r in rows
            ],
            production_approved=False,
        ),
    )
    summary = dict(
        candidate_rows=len(rows),
        original_rows=len(oldrows),
        new_rows=len(rows) - len(oldrows),
        verified_blobs=len(blobs),
        comparison_blobs=len(comparison),
        missing_blobs=sorted(set(missing)),
        normalization_failures=failures,
        packets=len(packet_index),
        evidence_edges=sum("left" in e for e in edges),
        collective_support_sets=sum(e["reason"] == "collective_support" for e in edges),
        quarantine_candidates=sum(r.get("quarantine_candidate", False) for r in rows),
        short_collision_groups=len(shortgroups),
        bounded_contract_passes=sum(
            r.get("bounded_contract_pass", False) for r in rows
        ),
        external_member_units=sum(
            bool(r.get("unresolved_external_members")) for r in rows
        ),
        proposed_first_wave=len(first_wave),
        projects=dict(Counter(r["repo"] for r in rows)),
        unflagged_projects=dict(
            Counter(r["repo"] for r in rows if r.get("quarantine_candidate") is False)
        ),
        all_dispositions="UNREVIEWED; candidate only",
        token_floor=40,
        token_floor_status="provisional",
        t07_frozen=False,
    )
    save("summary.json", summary)
    print(json.dumps(summary, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in (
        "repo",
        "acquisition",
        "candidate",
        "qualification",
        "groups",
        "baseline",
        "output",
    ):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    run(
        a.repo,
        a.acquisition,
        a.candidate,
        a.qualification,
        a.groups,
        a.baseline,
        a.output,
    )


if __name__ == "__main__":
    main()

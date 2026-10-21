"""Fail-closed qualification of FLOOR measurement evidence (not floor approval)."""

from collections import defaultdict
from faustcoder.floor_protocol import (
    FLOOR_BUCKETS,
    FLOOR_GATED_OPERATORS,
    FLOOR_CANDIDATES,
    FLOOR_CELL_N,
    FLOOR_MIN_DISTINCT_WINDOWS,
    FLOOR_RECALL_LOWER_BOUND,
    wilson_lower,
)


def assess_plants(plants: list[dict], outcomes: dict) -> dict:
    """Keep the same ground-truth denominators at every floor.

    Each plant binds a real rejected window to a distinct cleared host/project.
    Caller must separately verify those provenance/rights claims. This checker
    never authorizes a floor; natural-copy and human FP adjudication are separate.
    """
    cells = defaultdict(list)
    seen = set()
    for p in plants:
        if p["id"] in seen:
            raise ValueError("duplicate planted item")
        seen.add(p["id"])
        if p["operator"] not in FLOOR_GATED_OPERATORS:
            raise ValueError("unknown gated operator")
        if type(p["tokens"]) is not int or p["tokens"] < 15:
            raise ValueError("plant outside gated buckets")
        for field in ("window_digest", "host_digest", "host_repo", "reject_digest"):
            if not isinstance(p.get(field), str) or not p[field]:
                raise ValueError("missing plant provenance: " + field)
        bucket = next(
            i
            for i, (lo, hi) in enumerate(FLOOR_BUCKETS)
            if p["tokens"] >= lo and (hi is None or p["tokens"] <= hi)
        )
        cells[(bucket, p["operator"])].append(p)
    result = {}
    for floor in FLOOR_CANDIDATES:
        measured = outcomes.get(str(floor), {})
        if set(measured) != seen or any(type(v) is not bool for v in measured.values()):
            raise ValueError("complete boolean outcomes required at every floor")
        reports = []
        for bucket in range(4):
            for operator in FLOOR_GATED_OPERATORS:
                rows = cells[(bucket, operator)]
                windows = defaultdict(list)
                for p in rows:
                    windows[(p["reject_digest"], p["window_digest"])].append(p)
                errors = []
                if len(rows) != FLOOR_CELL_N:
                    errors.append("requires 100 plants")
                if len(windows) < FLOOR_MIN_DISTINCT_WINDOWS:
                    errors.append("requires 50 distinct real windows")
                if any(
                    len(v) != 2
                    or len({p["host_repo"] for p in v}) != 2
                    or len({p["host_digest"] for p in v}) != 2
                    for v in windows.values()
                ):
                    errors.append(
                        "each window requires two distinct cleared hosts in different repos"
                    )
                hits = sum(measured[p["id"]] for p in rows)
                lower = wilson_lower(hits, len(rows)) if rows else 0
                if lower < FLOOR_RECALL_LOWER_BOUND:
                    errors.append("Wilson recall below bound")
                reports.append(
                    {
                        "bucket": list(FLOOR_BUCKETS[bucket]),
                        "operator": operator,
                        "n": len(rows),
                        "detected": hits,
                        "wilson_lower": lower,
                        "blockers": errors,
                    }
                )
        result[str(floor)] = {
            "cells": reports,
            "recall_pass": all(not r["blockers"] for r in reports),
        }
    return {
        "floors": result,
        "floor_accepted": False,
        "remaining_gates": [
            "verified real-window and host provenance",
            "natural-copy adjudication",
            "hand-labelled FP budget",
            "unresolved sub-15/union hits",
            "recurring-miss review",
            "explicit floor decision",
        ],
    }

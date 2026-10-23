"""Read-only BlackDog readiness assessment. No admission or training actions.

Run: python -m faustcoder.readiness --repo-root . --json
This reports evidence found in a checkout; absence means NOT_VERIFIED, never FAIL.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

GATES = (
    ("repository_spec", "docs/specs/qualification-recovery-2026-10-23.md", "engineering"),
    ("canonical_spec", "specs/001-faustcoder/spec.md", "engineering"),
    ("qualification_runbook", "docs/runbooks/qualification-sprint.md", "engineering"),
    ("spark_runbook", "docs/runbooks/spark-local-setup.md", "engineering"),
)
OWNER_GATES = ("approved_pilot_dataset", "approved_model", "pilot_training_authorization")
QUALIFICATION_GATES = ("source_rights", "family_disjoint_split", "two_host_floor", "private_custody")


def assess(root: Path) -> dict:
    evidence = []
    for name, relative, lane in GATES:
        path = root / relative
        if path.is_file():
            data = path.read_bytes()
            evidence.append({"gate": name, "lane": lane, "status": "PRESENT_NOT_VALIDATED",
                             "path": relative, "sha256": hashlib.sha256(data).hexdigest()})
        else:
            evidence.append({"gate": name, "lane": lane, "status": "NOT_VERIFIED", "path": relative})
    blockers = [{"gate": name, "status": "NOT_VERIFIED", "reason": "No scoped approval or validated receipt supplied"}
                for name in (*QUALIFICATION_GATES, *OWNER_GATES)]
    return {"schema_version": 1, "mode": "READ_ONLY", "training_authorized": False,
            "pilot_ready": False, "evidence": evidence, "blockers": blockers,
            "next_safe_action": "Generate synthetic fixtures and collect qualification receipts",
            "note": "Documentation hashes prove only local bytes, not approval or execution. No external receipt discovery."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true", help="Print machine-readable readiness report")
    args = parser.parse_args(argv)
    result = assess(args.repo_root)
    if args.json:
        print(json.dumps(result, sort_keys=True, indent=2))
    else:
        print("BlackDog: pilot NOT VERIFIED; training NOT AUTHORIZED")
        for blocker in result["blockers"]:
            print(f" - {blocker['gate']}: {blocker['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Read-only BlackDog readiness assessment. No admission or training actions.

Run: python -m faustcoder.readiness --repo-root . --json
This reports evidence found in a checkout; absence means NOT_VERIFIED, never FAIL.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from faustcoder.errors import ArtifactStoreError

from faustcoder.readiness_manifest import (
    ManifestError, load_manifest, read_beneath, verify_manifest,
)

GATES = (
    ("repository_spec", "docs/specs/qualification-recovery-2026-10-23.md", "engineering"),
    ("canonical_spec", "specs/001-faustcoder/spec.md", "engineering"),
    ("qualification_runbook", "docs/runbooks/qualification-sprint.md", "engineering"),
    ("spark_runbook", "docs/runbooks/spark-local-setup.md", "engineering"),
)
OWNER_GATES = ("approved_pilot_dataset", "approved_model", "pilot_training_authorization")
FULL_OWNER_GATES = ("approved_full_dataset", "approved_model", "full_training_authorization")
QUALIFICATION_GATES = ("source_rights", "family_disjoint_split", "two_host_floor", "private_custody")
MODE_GATES = {
    "synthetic": ("environment_probe", "synthetic_checkpoint_probe"),
    "pilot": ("instruction_pair_contract", "source_rights", "family_disjoint_split", "t07_signed_split",
              "t08_baseline", "a2_path_eval_so", "gd1_group_drop", "environment_probe",
              *OWNER_GATES),
    "full": (*QUALIFICATION_GATES, *FULL_OWNER_GATES, "t07_signed_split", "t08_baseline",
             "a2_path_eval_so", "gd1_group_drop", "environment_probe"),
}
GATE_ACTIONS = {
    "instruction_pair_contract": "Verify prompt provenance, qualified targets, compiler/signal evidence and signed partition membership",
    "source_rights": "Verify the exact selected units against existing rights and closure receipts",
    "family_disjoint_split": "Replay project, family and lineage separation for the selected dataset",
    "t07_signed_split": "Verify signed T07 split, including any recorded provisional-floor caveat and recheck",
    "t08_baseline": "Run and independently replay the pinned baseline on the development suite",
    "a2_path_eval_so": "Verify task-bound reward integration tests on the pinned Linux compiler",
    "gd1_group_drop": "Verify whole-group quarantine/drop tests and declared halt policy",
    "environment_probe": "Verify the preserved Spark candidate and representative model probe receipts",
    "synthetic_checkpoint_probe": "Run generated-fixture checkpoint/resume diagnostics in an isolated environment",
    "approved_pilot_dataset": "Bind the minimum qualified dataset to one bounded pilot proposal",
    "approved_full_dataset": "Verify complete corpus admission and exact full-training dataset scope",
    "full_training_authorization": "Obtain the explicit full-corpus training decision; a bounded pilot approval is insufficient",
    "approved_model": "Reuse the exact approved local model revision and verify its model manifest",
    "pilot_training_authorization": "Obtain one scoped human decision on the complete bounded pilot package",
    "two_host_floor": "Verify two cleared hosts and replay ratified FLOOR protocol",
    "private_custody": "Verify the current human custody decision and access evidence without reading private tasks",
}


def assess(root: Path, *, manifest_path: Path | None = None,
           evidence_root: Path | None = None, mode: str = "pilot",
           scope_digest: str | None = None, scope_path: Path | None = None,
           trusted_split_public_key: str | None = None) -> dict:
    if mode not in MODE_GATES:
        raise ValueError("unknown operating mode")
    evidence = []
    for name, relative, lane in GATES:
        try:
            data = read_beneath(root, relative)
            evidence.append({"gate": name, "lane": lane, "status": "PRESENT_NOT_VALIDATED",
                             "path": relative, "sha256": hashlib.sha256(data).hexdigest()})
        except (OSError, ManifestError):
            evidence.append({"gate": name, "lane": lane, "status": "NOT_VERIFIED", "path": relative})
    blockers = [{"gate": name, "status": "NOT_VERIFIED", "code": "missing_validated_evidence",
                 "reason": "No scoped approval or validated receipt supplied",
                 "next_action": GATE_ACTIONS[name]}
                for name in MODE_GATES[mode]]
    verification = {"verified": [], "blockers": []}
    if manifest_path is not None:
        if evidence_root is None or scope_digest is None:
            verification["blockers"].append({"gate": "manifest_scope", "status": "INVALID",
                "code": "explicit_scope_required", "next_action": "Supply --evidence-root and --scope-digest"})
        else:
            try:
                manifest = load_manifest(manifest_path)
                scope = None
                if scope_path is not None:
                    from faustcoder.readiness_evidence import load_scope
                    scope = load_scope(scope_path, scope_digest, mode)
                verification = verify_manifest(manifest, evidence_root, mode=mode, scope_digest=scope_digest,
                                               scope=scope, trusted_split_public_key=trusted_split_public_key)
                verification["manifest_sha256"] = manifest.sha256
            except (ArtifactStoreError, OSError, ValueError, TypeError):
                verification["blockers"].append({"gate": "manifest", "status": "INVALID",
                    "code": "invalid_manifest", "next_action": "Repair the manifest schema or unsafe file reference"})
    cleared = set(verification.get("verified_gates", []))
    blockers = [row for row in blockers if row["gate"] not in cleared]
    blockers.extend(verification["blockers"])
    next_blocker = next((row for row in blockers if row.get("status") == "INVALID"),
                        blockers[0] if blockers else None)
    next_action = (next_blocker.get("next_action", "Repair invalid supplied evidence")
                   if next_blocker else "Assemble the scoped pilot decision package")
    return {"schema_version": 1, "operating_mode": mode, "scope_digest": scope_digest,
            "receipt_verification": verification, "verified_gates": sorted(cleared), "mode": "READ_ONLY", "training_authorized": False,
            "pilot_ready": False, "diagnostic_only": mode == "synthetic",
            "deferred_full_corpus_gates": list(QUALIFICATION_GATES[2:]) if mode == "pilot" else [],
            "evidence": evidence, "blockers": blockers,
            "next_safe_action": next_action,
            "note": "Integrity is not semantic validation or authorization. No receipt contents or private tasks are disclosed."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--manifest", type=Path, help="External evidence index, never authorization")
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--scope-digest", help="SHA-256 of the exact immutable run scope")
    parser.add_argument("--scope-file", type=Path, help="Exact run scope; SHA-256 must match --scope-digest")
    parser.add_argument("--trusted-split-public-key", type=Path, help="Out-of-band custodian public key, never a private key")
    parser.add_argument("--mode", choices=("synthetic", "pilot", "full"), default="pilot")
    parser.add_argument("--json", action="store_true", help="Print machine-readable readiness report")
    args = parser.parse_args(argv)
    trusted_key = None
    if args.trusted_split_public_key is not None:
        try:
            from faustcoder.readiness_evidence import load_public_key
            trusted_key = load_public_key(args.trusted_split_public_key,
                                          excluded_roots=(args.evidence_root,) if args.evidence_root is not None else ())
        except (OSError, ValueError, UnicodeError):
            print(json.dumps({"training_authorized": False, "pilot_ready": False,
                              "blockers": [{"gate": "signer_trust", "status": "INVALID",
                                            "code": "invalid_public_key_input"}]}))
            return 2
    result = assess(args.repo_root, manifest_path=args.manifest,
                    evidence_root=args.evidence_root, mode=args.mode, scope_digest=args.scope_digest,
                    scope_path=args.scope_file, trusted_split_public_key=trusted_key)
    if args.json:
        print(json.dumps(result, sort_keys=True, indent=2))
    else:
        print(f"BlackDog: {args.mode} NOT VERIFIED; training AUTHORIZATION NOT VERIFIED")
        for blocker in result["blockers"]:
            print(f" - {blocker['gate']}: {blocker['status']}")
    return 2 if any(b.get("status") == "INVALID" for b in result["blockers"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())

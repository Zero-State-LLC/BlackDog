"""T07 signed proposal verification; production freeze remains gated.

The caller supplies a public key from an independently trusted channel, never
from the signed document. No private keys or global allowed-signers are read.
The guarded freeze API needs a trusted custodian signature over independent
review commitments and an explicit provisional-floor route. Production T07
remains unfrozen; only disposable regression stores exercise that API here.
"""

from __future__ import annotations

import subprocess
import tempfile
import base64
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Mapping

from faustcoder.canonical import (
    canonical_bytes,
    content_digest_for,
    CONTENT_DIGEST_RE,
    build_envelope,
)
from faustcoder.neardup import COMPARISON_VERSION, TOKEN_FLOOR

NAMESPACE = "blackdog-t07-split-v1"
PRINCIPAL = "t07-custodian"


def audit_assignments(
    rows: list[dict],
    assignments: Mapping[str, str],
    dependencies: Mapping[str, list[str]],
) -> list[str]:
    """Audit project, family, provenance and transitive dependency separation.

    Rows must be derived from a verified dedup snapshot. This is not rights
    admission, nor proof that a caller supplied a complete dependency graph.
    """
    errors = set()
    by_id = {}
    for row in rows:
        key = row["unit_id"]
        if key in by_id:
            raise ValueError("duplicate unit id")
        for field in ("repo", "duplicate_family", "original_sha256"):
            if not isinstance(row.get(field), str) or not row[field]:
                raise ValueError("missing provenance/family: " + field)
        by_id[key] = row
    if set(assignments) != set(by_id):
        errors.add("assignments must cover exactly the snapshot units")
    if set(dependencies) != set(by_id):
        errors.add("dependency disposition required for every unit")
    groups = {}
    for key, row in sorted(by_id.items()):
        split = assignments.get(key)
        if split not in {"train", "development", "holdout"}:
            errors.add("invalid or missing partition: " + key)
            continue
        required = "train" if split == "train" else "eval"
        if required not in row.get("eligible_for", []):
            errors.add("forbidden rights: " + key)
        if split != "train" and (row.get("impulse") or row.get("training_only")):
            errors.add("training-only evaluation: " + key)
        for field in ("repo", "duplicate_family", "original_sha256"):
            groups.setdefault((field, row[field]), set()).add(split)
        for dep in dependencies.get(key, []):
            if dep not in by_id:
                errors.add("unresolved dependency: " + key + " -> " + dep)
            elif assignments.get(dep) != split:
                errors.add("cross-split dependency: " + key + " -> " + dep)
    for (field, value), partitions in sorted(groups.items()):
        if len(partitions) > 1:
            errors.add("cross-split " + field + ": " + value)
    return sorted(errors)


def split_candidate(
    dedup: dict,
    assignments: Mapping[str, str],
    dependencies: Mapping[str, list[str]],
    *,
    blockers: list[str],
    readiness: dict | None = None,
) -> dict:
    """Build a deterministic, explicitly unfrozen candidate; never signs it."""
    if (
        dedup.get("record_type") != "DedupManifest"
        or dedup.get("split_frozen") is not False
    ):
        raise ValueError("expected unfrozen DedupManifest")
    near = dedup.get("near_duplicate", {})
    if (
        near.get("algorithm") != COMPARISON_VERSION
        or near.get("token_floor") != TOKEN_FLOOR
    ):
        raise ValueError("stale comparison pipeline or measurement-only floor")
    if near.get("measurement_only") is not False:
        raise ValueError("measurement manifest cannot be frozen")
    readiness = readiness or {}
    errors = readiness_errors(readiness)
    errors += audit_assignments(dedup["units"], assignments, dependencies)
    if set(assignments.values()) != {"train", "development", "holdout"}:
        errors.append("qualified train/development/holdout partitions required")
    return {
        "record_type": "SplitCandidate",
        "version": "t07-split-candidate.v1",
        "dedup_digest": content_digest_for(dedup),
        "assignments": dict(sorted(assignments.items())),
        "dependencies": {k: sorted(set(v)) for k, v in sorted(dependencies.items())},
        "blockers": sorted(set(blockers + errors)),
        "readiness": readiness,
        "token_floor": TOKEN_FLOOR,
        "token_floor_status": "provisional",
        "split_frozen": False,
    }


def verify_signed_candidate(
    candidate: dict, signature: bytes, trusted_public_key: str, *, dedup: dict
) -> str:
    """Verify detached SSH signature and recompute bound assignment checks.

    A valid signature establishes integrity and signer identity only. It does
    not turn a blocked proposal into a freeze or establish independent custody.
    Temporary public verification files contain no private key material.
    """
    fields = trusted_public_key.strip().split()
    if (
        len(fields) != 2
        or fields[0] != "ssh-ed25519"
        or any(c in trusted_public_key for c in "\r\n")
    ):
        raise ValueError(
            "expected a trusted single Ed25519 public key, without comment"
        )
    rebuilt = split_candidate(
        dedup,
        candidate["assignments"],
        candidate["dependencies"],
        blockers=candidate["blockers"],
        readiness=candidate["readiness"],
    )
    if canonical_bytes(candidate) != canonical_bytes(rebuilt):
        raise ValueError("candidate mismatch or tampered snapshot")
    with tempfile.TemporaryDirectory(prefix="blackdog-split-public-") as directory:
        root = Path(directory)
        allowed = root / "signers"
        signed = root / "manifest.sig"
        allowed.write_text(
            f'{PRINCIPAL} namespaces="{NAMESPACE}" {trusted_public_key}\n'
        )
        signed.write_bytes(signature)
        result = subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "verify",
                "-f",
                str(allowed),
                "-I",
                PRINCIPAL,
                "-n",
                NAMESPACE,
                "-s",
                str(signed),
            ],
            input=canonical_bytes(candidate),
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise ValueError("invalid split signature or signer")
    return content_digest_for(candidate)


def readiness_errors(readiness: dict) -> list[str]:
    errors = []
    for field in (
        "reviewer",
        "custodian",
        "holdout_author",
        "leakage_caveat",
        "recheck_due",
    ):
        if not isinstance(readiness.get(field), str) or not readiness[field].strip():
            errors.append("missing independent attestation: " + field)
    for field in (
        "source_closure_review_digest",
        "development_review_digest",
        "holdout_review_digest",
        "leakage_review_digest",
        "holdout_content_digest",
    ):
        if not isinstance(readiness.get(field), str) or not CONTENT_DIGEST_RE.fullmatch(
            readiness[field]
        ):
            errors.append("missing bound review: " + field)
    if readiness.get("floor_route") != "explicit-provisional":
        errors.append("explicit provisional floor authorization required")
    if readiness.get("newly_authored_holdout") is not True:
        errors.append("newly authored independent holdout required")
    if readiness.get("recheck_due"):
        try:
            due = datetime.fromisoformat(
                readiness["recheck_due"].replace("Z", "+00:00")
            )
            if due.tzinfo is None:
                raise ValueError()
        except (ValueError, TypeError):
            errors.append("invalid scheduled novelty recheck")
    return errors


def require_freeze_ready(candidate: dict) -> None:
    if candidate.get("blockers") or readiness_errors(candidate.get("readiness", {})):
        raise ValueError("T07 remains unfrozen: unresolved signed qualification gates")


def _utc_now() -> datetime:
    """Read the evaluator host clock; never accept caller-supplied freshness."""
    return datetime.now(timezone.utc)


def _require_current_recheck(candidate: dict) -> None:
    due = datetime.fromisoformat(
        candidate["readiness"]["recheck_due"].replace("Z", "+00:00")
    )
    if due <= _utc_now():
        raise ValueError("novelty recheck is overdue")


def freeze_signed_split(
    store,
    dedup_digest: str,
    candidate: dict,
    signature: bytes,
    trusted_public_key: str,
    *,
    created_at: str,
) -> str:
    """Emit a signed SplitManifest and DatasetSnapshot after all guards pass.

    Only the out-of-band trusted custodian signature authorizes the attested
    provisional route. The caller must keep the store private to the evaluator;
    no holdout task bytes or private key enter this module. No production caller
    is configured by default. Generic dataset.apply_transition cannot bypass it.
    """
    from faustcoder.dataset import current_state, receipt_payload

    dedup_envelope = store.get(dedup_digest)
    if dedup_envelope["producer"] != "faustcoder.snapshot":
        raise ValueError("untrusted dedup producer")
    dedup = dedup_envelope["payload"]
    verify_signed_candidate(candidate, signature, trusted_public_key, dedup=dedup)
    require_freeze_ready(candidate)
    _require_current_recheck(candidate)
    now = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    due = datetime.fromisoformat(
        candidate["readiness"]["recheck_due"].replace("Z", "+00:00")
    )
    if now.tzinfo is None or due <= now:
        raise ValueError("novelty recheck must be scheduled in the future")
    # Preflight all source states before writing anything.
    sources = {}
    source_states = {}
    for digest in dedup["example_digests"]:
        e = store.get(digest)["payload"]
        if e.get("record_type") != "Example" or e["unit_id"] in sources:
            raise ValueError("invalid snapshot examples")
        source = e["source_digest"]
        state = current_state(store, source)
        if state not in {"DEDUPED", "FROZEN"}:
            raise ValueError("split source must be DEDUPED or exactly resumable")
        source_states[source] = state
        sources[e["unit_id"]] = source
    if set(sources) != set(candidate["assignments"]):
        raise ValueError("snapshot example coverage mismatch")
    previous = {}
    for artifact in store.list():
        envelope = store.get(artifact)
        payload = envelope["payload"]
        if payload.get("event") == "dedup_passed":
            for source in sources.values():
                if source in payload.get("input_hashes", []):
                    if source in previous:
                        raise ValueError("ambiguous dedup receipt")
                    previous[source] = envelope["content_digest"]
    if set(previous) != set(sources.values()):
        raise ValueError("missing dedup receipts")

    def envelope(payload, parents):
        return build_envelope(
            schema_version="0.3.0",
            created_at=created_at,
            producer="faustcoder.split",
            parents=sorted(set(parents)),
            payload=payload,
        )

    signed = envelope(
        {
            "record_type": "SplitManifest",
            "candidate": candidate,
            "signature": base64.b64encode(signature).decode("ascii"),
            "namespace": NAMESPACE,
        },
        [dedup_digest],
    )
    snapshot = envelope(
        {
            "record_type": "DatasetSnapshot",
            "dedup_digest": dedup_digest,
            "split_manifest_digest": signed["content_digest"],
            "split_frozen": True,
            "token_floor_status": "provisional",
            "p3_holdout_exit_allowed": False,
        },
        [dedup_digest, signed["content_digest"]],
    )
    envelopes = [signed, snapshot]
    for source in sorted(sources.values()):
        parents = [
            source,
            previous[source],
            signed["content_digest"],
            snapshot["content_digest"],
        ]
        payload = receipt_payload(
            actor=candidate["readiness"]["reviewer"],
            timestamp=created_at,
            input_hashes=parents,
            from_state="DEDUPED",
            event="split_frozen",
            to_state="FROZEN",
            disposition="signed provisional split; novelty recheck required",
        )
        receipt = envelope(payload, parents)
        if source_states[source] == "FROZEN":
            # Resume only our exact interrupted operation, never an unrelated
            # freeze. Check every source before publishing any missing writes.
            if (
                not store.exists(receipt["content_digest"])
                or store.get(receipt["content_digest"]) != receipt
            ):
                raise ValueError("FROZEN source does not match this signed freeze")
        envelopes.append(receipt)
    # ArtifactStore validates schemas before put. Preflight these too, to avoid
    # validation errors after the first write. Store I/O errors remain recoverable.
    from faustcoder.schemas import validate

    for e in envelopes:
        validate(e, "artifact-envelope.schema.json")
    for e in envelopes:
        store.put(e)
    return snapshot["content_digest"]


def verify_frozen_snapshot(
    store, snapshot_digest: str, trusted_public_key: str
) -> dict:
    """Reverify a stored freeze against out-of-band signer trust before use."""
    snapshot = store.get(snapshot_digest)
    payload = snapshot["payload"]
    if (
        snapshot["producer"] != "faustcoder.split"
        or payload.get("record_type") != "DatasetSnapshot"
    ):
        raise ValueError("not a signed dataset snapshot")
    signed = store.get(payload["split_manifest_digest"])
    if (
        signed["producer"] != "faustcoder.split"
        or signed["payload"].get("record_type") != "SplitManifest"
    ):
        raise ValueError("not a split manifest")
    statement = signed["payload"]
    dedup = store.get(payload["dedup_digest"])
    if (
        dedup["producer"] != "faustcoder.snapshot"
        or statement.get("namespace") != NAMESPACE
    ):
        raise ValueError("snapshot producer or signature namespace mismatch")
    verify_signed_candidate(
        statement["candidate"],
        base64.b64decode(statement["signature"], validate=True),
        trusted_public_key,
        dedup=dedup["payload"],
    )
    require_freeze_ready(statement["candidate"])
    _require_current_recheck(statement["candidate"])
    expected = {
        "record_type": "DatasetSnapshot",
        "dedup_digest": dedup["content_digest"],
        "split_manifest_digest": signed["content_digest"],
        "split_frozen": True,
        "token_floor_status": "provisional",
        "p3_holdout_exit_allowed": False,
    }
    if payload != expected or set(snapshot["parents"]) != {
        dedup["content_digest"],
        signed["content_digest"],
    }:
        raise ValueError("snapshot binding mismatch")
    if signed["parents"] != [dedup["content_digest"]]:
        raise ValueError("split parent mismatch")
    # The snapshot is written before its transition receipts. A crash can leave
    # a valid content-addressed snapshot that is not yet a completed freeze.
    from faustcoder.dataset import current_state, receipt_payload

    sources = {}
    for digest in dedup["payload"]["example_digests"]:
        example = store.get(digest)["payload"]
        if example.get("record_type") != "Example" or example["unit_id"] in sources:
            raise ValueError("invalid snapshot examples")
        sources[example["unit_id"]] = example["source_digest"]
    if set(sources) != set(statement["candidate"]["assignments"]):
        raise ValueError("snapshot example coverage mismatch")
    envelopes = [store.get(digest) for digest in store.list()]
    for source in sorted(set(sources.values())):
        previous = [
            e["content_digest"]
            for e in envelopes
            if e["payload"].get("event") == "dedup_passed"
            and source in e["payload"].get("input_hashes", [])
        ]
        if len(previous) != 1:
            raise ValueError("missing or ambiguous dedup receipt")
        parents = sorted(
            {source, previous[0], signed["content_digest"], snapshot["content_digest"]}
        )
        expected_receipt = receipt_payload(
            actor=statement["candidate"]["readiness"]["reviewer"],
            timestamp=snapshot["created_at"],
            input_hashes=parents,
            from_state="DEDUPED",
            event="split_frozen",
            to_state="FROZEN",
            disposition="signed provisional split; novelty recheck required",
        )
        matches = [
            e
            for e in envelopes
            if e["producer"] == "faustcoder.split"
            and e["created_at"] == snapshot["created_at"]
            and e["parents"] == parents
            and e["payload"] == expected_receipt
        ]
        if len(matches) != 1 or current_state(store, source) != "FROZEN":
            raise ValueError(
                "incomplete freeze: missing exact linked transition receipt"
            )
    return payload

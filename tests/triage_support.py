"""Throwaway Ed25519 keys and root-owned allowed-signers files for triage tests.

Nothing here is a real reviewer key. Every key is generated under pytest's
temporary directory and is not committed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from faustcoder.canonical import loads_strict
from faustcoder.reward.audit import AuditReportLog
from faustcoder.reward.records import RewardKeyring
from faustcoder.reward.triage_sig import (
    NAMESPACE,
    public_fingerprint,
    sign_statement,
    write_drop,
)


def make_key(directory: Path, name: str) -> Path:
    """Generate one Ed25519 key. The private key is mode ``0600``."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    if path.exists():
        return path
    subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-f", str(path), "-N", "", "-q", "-C", name],
        check=True,
    )
    os.chmod(path, 0o600)
    return path


def signer_line(
    principal: str,
    key: Path,
    *,
    valid_after: str = "20200101000000",
    valid_before: str | None = None,
    namespace: str = NAMESPACE,
) -> str:
    """One allowed-signers line for ``key``."""
    parts = (key.with_name(key.name + ".pub")).read_text(encoding="utf-8").split()
    options = [f'namespaces="{namespace}"', f'valid-after="{valid_after}"']
    if valid_before is not None:
        options.append(f'valid-before="{valid_before}"')
    return f"{principal} {','.join(options)} {parts[0]} {parts[1]}"


def install_signers(
    directory: Path,
    lines: list[str],
    *,
    mode: int = 0o644,
    owner: str = "root:root",
    parent_mode: int = 0o755,
) -> Path:
    """Write ``lines`` and hand the file to root.

    The immediate parent is root-owned. Callers that need a bad owner or
    mode pass those in. pytest can delete the tree after a sudo chown
    back to the test user.
    """
    directory.mkdir(parents=True, exist_ok=True)
    index = 0
    while (directory / f"signers-{index}").exists():
        index += 1
    parent = directory / f"signers-{index}"
    parent.mkdir(parents=True)
    path = parent / "triage-allowed-signers"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(["sudo", "-n", "chown", "root:root", str(parent)], check=True)
    subprocess.run(["sudo", "-n", "chmod", f"{parent_mode:04o}", str(parent)], check=True)
    subprocess.run(["sudo", "-n", "chown", owner, str(path)], check=True)
    subprocess.run(["sudo", "-n", "chmod", f"{mode:04o}", str(path)], check=True)
    return path


def release_tmp(tmp_path: Path) -> None:
    """Give ``tmp_path`` back to the test user so pytest can delete it."""
    subprocess.run(
        ["sudo", "-n", "chown", "-R", f"{os.getuid()}:{os.getgid()}", str(tmp_path)],
        check=False,
    )


def halt_body(reports: AuditReportLog, record_id: str) -> dict[str, object]:
    """The newest halt line in ``reports`` that names ``record_id``."""
    chosen: dict[str, object] | None = None
    chosen_seq = -1
    for line in reports.path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        body = loads_strict(line)
        if not isinstance(body, dict) or body.get("type") != "audit_report":
            continue
        report = body.get("report")
        if not isinstance(report, dict) or report.get("p3") != "halt":
            continue
        items = report.get("disagreements")
        if not isinstance(items, list):
            continue
        if not any(isinstance(item, dict) and item.get("record_id") == record_id for item in items):
            continue
        seq = body.get("seq")
        if type(seq) is int and seq >= chosen_seq:
            chosen = body
            chosen_seq = seq
    if chosen is None:
        raise AssertionError("halt line is missing")
    return chosen


def statement_for(
    reports: AuditReportLog,
    *,
    run_id: str,
    record_id: str,
    triaged_at: str,
    fingerprint: str,
    decision: str = "accept_stored",
) -> dict[str, object]:
    """A statement bound to the newest halt that names ``record_id``."""
    body = halt_body(reports, record_id)
    report = body["report"]
    if not isinstance(report, dict):
        raise AssertionError("halt report is missing")
    seq = body["seq"]
    mac = body["mac"]
    digest = report["row_ids_digest"]
    consumed = report["consumed_id"]
    if type(seq) is not int or type(mac) is not str or type(digest) is not str or type(consumed) is not str:
        raise AssertionError("halt line is missing a binding field")
    return {
        "consumed_id": consumed,
        "decision": decision,
        "halt_report_mac": mac,
        "halt_seq": seq,
        "key_fingerprint": fingerprint,
        "record_id": record_id,
        "row_ids_digest": digest,
        "run_id": run_id,
        "triaged_at": triaged_at,
        "type": "audit_triage_statement",
        "v": 1,
    }


def enroll(
    reports: AuditReportLog,
    directory: Path,
    principals: list[tuple[str, Path]],
    *,
    valid_after: str = "20200101000000",
    valid_before: str | None = None,
    namespace: str = NAMESPACE,
) -> Path:
    """Install ``principals`` and point ``reports`` at that file."""
    path = install_signers(
        directory,
        [
            signer_line(
                name,
                key,
                valid_after=valid_after,
                valid_before=valid_before,
                namespace=namespace,
            )
            for name, key in principals
        ],
    )
    reports.allowed_signers = path
    return path


def record_signed(
    reports: AuditReportLog,
    ring: RewardKeyring,
    *,
    record_id: str,
    triaged_by: str,
    triaged_at: str,
    decision: str = "accept_stored",
    principal: str | None = None,
    key_path: Path | None = None,
) -> Path:
    """Sign one drop as ``principal`` and append it. Returns the drop path."""
    actor = triaged_by.strip()
    who = principal or actor
    material = reports.path.parent / "triage-material"
    material.mkdir(parents=True, exist_ok=True)
    key = key_path or make_key(material, who)
    if reports.allowed_signers is None:
        reports.allowed_signers = install_signers(material, [signer_line(who, key)])
    statement = statement_for(
        reports,
        run_id=ring.run_id,
        record_id=record_id,
        triaged_at=triaged_at,
        fingerprint=public_fingerprint(key),
        decision=decision,
    )
    signature = sign_statement(statement, key)
    drop = material / f"drop-{record_id[:12]}-{who}-{len(list(material.glob('drop-*')))}"
    write_drop(
        drop,
        principal=who,
        triaged_by=actor,
        statement=statement,
        signature=signature,
    )
    reports.record_triage(
        ring,
        record_id=record_id,
        triaged_by=triaged_by,
        triaged_at=triaged_at,
        drop_path=drop,
    )
    return drop

"""D3-H2-C: human triage signatures (spec §26 0.3.10, amended 0.3.11)."""

from __future__ import annotations

import os
import pwd
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from faustcoder.canonical import canonical_bytes, loads_strict
from faustcoder.cli import main
from faustcoder.reward.audit import AuditReportLog, p3_may_proceed
from faustcoder.reward.records import (
    ConsumedLog,
    RewardKeyring,
    RewardRecordError,
    derive_run_key,
    load_records,
    rl_batch_from_records,
)
from faustcoder.reward.triage_sig import (
    public_fingerprint,
    read_drop,
    require_allowed_signers,
    require_openssh,
    require_p3_grader_account,
    sign_statement,
    verify_statement,
    write_drop,
)
from faustcoder.reward.types import QuarantineQueue, UngradedRateTracker
from tests.test_reward_audit import (
    _append_halt_copy,
    _echo,
    _halt_stamp,
    _halted,
    _rows,
    _shift_stamp,
)
from tests.test_reward_records import CHECKPOINT, HARNESS, RUN, _members, _signal, _store, _write_key
from tests.triage_support import (
    enroll,
    halt_body,
    install_signers,
    make_key,
    public_fingerprint,
    record_signed,
    release_tmp,
    signer_line,
    statement_for,
)


@pytest.fixture(autouse=True)
def _pin_harness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "faustcoder.reward.records.current_harness_digest",
        lambda: HARNESS,
    )


@pytest.fixture(autouse=True)
def _return_root_owned_tmp(tmp_path: Path):
    yield
    release_tmp(tmp_path)


def _openssh(stamp: str) -> str:
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")


def _submit(
    reports: AuditReportLog,
    ring: RewardKeyring,
    record_id: str,
    triaged_at: str,
    statement: dict[str, object],
    signature: str,
    *,
    principal: str,
    triaged_by: str | None = None,
) -> None:
    material = reports.path.parent / "drops"
    material.mkdir(parents=True, exist_ok=True)
    drop = material / f"drop-{len(list(material.glob('drop-*')))}"
    write_drop(
        drop,
        principal=principal,
        triaged_by=triaged_by or principal,
        statement=statement,
        signature=signature,
    )
    reports.record_triage(
        ring,
        record_id=record_id,
        triaged_by=triaged_by or principal,
        triaged_at=triaged_at,
        drop_path=drop,
    )


def _signed_statement(
    reports: AuditReportLog,
    ring: RewardKeyring,
    record_id: str,
    triaged_at: str,
    key: Path,
    overrides: dict[str, object] | None = None,
) -> tuple[dict[str, object], str]:
    statement = statement_for(
        reports,
        run_id=ring.run_id,
        record_id=record_id,
        triaged_at=triaged_at,
        fingerprint=public_fingerprint(key),
    )
    if overrides:
        statement.update(overrides)
    signature = sign_statement(statement, key)
    return statement, signature


def _assert_stays_halted(reports: AuditReportLog, ring: RewardKeyring, consumed: ConsumedLog) -> None:
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is False


def test_one_reviewer_clears_a_halt_and_the_writer_is_the_drop_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid software-key signature clears a halt that is not late.

    The recorded writer is the drop owner. Patching the effective uid
    does not change that, and it does not make the line fail.
    """
    _secret, audit, consumed, reports, ring = _halted(tmp_path, "one")
    record_id = audit.disagreements[0].record_id
    stamp = _halt_stamp(reports)
    monkeypatch.setattr("faustcoder.reward.audit.os.geteuid", lambda: 0)
    record_signed(reports, ring, record_id=record_id, triaged_by="danny", triaged_at=stamp)
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is True
    body = loads_strict(reports.path.read_text(encoding="utf-8").splitlines()[-1])
    assert isinstance(body, dict)
    assert body["v"] == 2
    assert body["writer_uid"] == os.getuid()
    assert body["writer_user"] == pwd.getpwuid(os.getuid()).pw_name
    assert body["principal"] == "danny"
    assert body["appended_at"] >= stamp
    report = halt_body(reports, record_id)["report"]
    assert isinstance(report, dict)
    assert report["persisted_at"] == report["halted_at"] == stamp


def test_a_late_halt_needs_two_distinct_principals(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    rows = _rows(
        secret,
        "group-used",
        [("signal", "pass", _signal(source, passed=True), source)],
    )
    consumed = ConsumedLog(tmp_path / "used-consumed.jsonl")
    consumed.claim(
        "group-used",
        "used",
        task_digest_full=rows[0].task_digest_full,
        policy_checkpoint=CHECKPOINT,
        run_key=derive_run_key(secret, RUN),
    )
    ring = RewardKeyring(secret, run_id=RUN)
    reports = AuditReportLog(tmp_path / "used-reports.jsonl", consumed)
    from faustcoder.reward.audit import audit_sampled_reruns

    audit = audit_sampled_reruns(
        rows,
        ring,
        rerun=lambda _record: "fail",
        consumed=consumed,
        reports=reports,
    )
    assert audit.late_groups == ("group-used",)
    record_id = audit.disagreements[0].record_id
    stamp = _halt_stamp(reports)
    material = tmp_path / "keys"
    alice = make_key(material, "alice")
    bob = make_key(material, "bob")
    enroll(reports, material, [("alice", alice), ("bob", bob)])
    record_signed(
        reports,
        ring,
        record_id=record_id,
        triaged_by="alice",
        triaged_at=stamp,
        principal="alice",
        key_path=alice,
    )
    _assert_stays_halted(reports, ring, consumed)
    size = reports.path.stat().st_size
    with pytest.raises(RewardRecordError, match="triage"):
        record_signed(
            reports,
            ring,
            record_id=record_id,
            triaged_by="alice",
            triaged_at=stamp,
            principal="alice",
            key_path=alice,
        )
    assert reports.path.stat().st_size == size
    _assert_stays_halted(reports, ring, consumed)
    first = loads_strict(reports.path.read_text(encoding="utf-8").splitlines()[-1])
    assert isinstance(first, dict)
    forged = {key: value for key, value in first.items() if key not in {"mac", "seq", "prev"}}
    reports._append_line(derive_run_key(secret, RUN), forged)
    _assert_stays_halted(reports, ring, consumed)
    record_signed(
        reports,
        ring,
        record_id=record_id,
        triaged_by="bob",
        triaged_at=stamp,
        principal="bob",
        key_path=bob,
    )
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is True


def test_a_v2_line_without_a_signature_and_a_v1_line_stay_halted(tmp_path: Path) -> None:
    secret, audit, consumed, reports, ring = _halted(tmp_path, "version")
    record_id = audit.disagreements[0].record_id
    stamp = _halt_stamp(reports)
    key = make_key(tmp_path / "keys", "danny")
    enroll(reports, tmp_path / "keys", [("danny", key)])
    statement, signature = _signed_statement(reports, ring, record_id, stamp, key)
    uid = os.getuid()
    user = pwd.getpwuid(uid).pw_name
    common = {
        "appended_at": stamp,
        "decision": "accept_stored",
        "principal": "danny",
        "record_id": record_id,
        "run_id": RUN,
        "signature": signature,
        "statement": statement,
        "triaged_at": stamp,
        "triaged_by": "danny",
        "type": "audit_triage",
        "writer_uid": uid,
        "writer_user": user,
    }
    reports._append_line(derive_run_key(secret, RUN), {**common, "v": 1})
    _assert_stays_halted(reports, ring, consumed)
    unsigned = {key: value for key, value in common.items() if key != "signature"}
    reports._append_line(derive_run_key(secret, RUN), {**unsigned, "v": 2})
    _assert_stays_halted(reports, ring, consumed)


def test_a_forged_signature_stays_halted(tmp_path: Path) -> None:
    secret, audit, consumed, reports, ring = _halted(tmp_path, "forged-sig")
    record_id = audit.disagreements[0].record_id
    stamp = _halt_stamp(reports)
    key = make_key(tmp_path / "keys", "danny")
    enroll(reports, tmp_path / "keys", [("danny", key)])
    statement, _signature = _signed_statement(reports, ring, record_id, stamp, key)
    uid = os.getuid()
    reports._append_line(
        derive_run_key(secret, RUN),
        {
            "appended_at": stamp,
            "decision": "accept_stored",
            "principal": "danny",
            "record_id": record_id,
            "run_id": RUN,
            "signature": "-----BEGIN SSH SIGNATURE-----\nnot-a-signature\n-----END SSH SIGNATURE-----\n",
            "statement": statement,
            "triaged_at": stamp,
            "triaged_by": "danny",
            "type": "audit_triage",
            "v": 2,
            "writer_uid": uid,
            "writer_user": pwd.getpwuid(uid).pw_name,
        },
    )
    _assert_stays_halted(reports, ring, consumed)


@pytest.mark.parametrize(
    "field",
    ("run_id", "record_id", "halt_seq", "halt_report_mac", "row_ids_digest", "consumed_id"),
)
def test_a_statement_bound_to_the_wrong_field_stays_halted(tmp_path: Path, field: str) -> None:
    _secret, audit, consumed, reports, ring = _halted(tmp_path, field)
    record_id = audit.disagreements[0].record_id
    stamp = _halt_stamp(reports)
    key = make_key(tmp_path / "keys", "danny")
    enroll(reports, tmp_path / "keys", [("danny", key)])
    replacement: object
    if field == "halt_seq":
        replacement = 99
    elif field in {"halt_report_mac", "row_ids_digest", "consumed_id"}:
        replacement = "ab" * 32
    elif field == "record_id":
        replacement = "cd" * 32
    else:
        replacement = "other-run"
    statement, signature = _signed_statement(
        reports, ring, record_id, stamp, key, overrides={field: replacement}
    )
    size = reports.path.stat().st_size
    with pytest.raises(RewardRecordError, match="triage"):
        _submit(reports, ring, record_id, stamp, statement, signature, principal="danny")
    assert reports.path.stat().st_size == size
    _assert_stays_halted(reports, ring, consumed)


def test_a_key_revoked_at_appended_at_does_not_clear(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Valid at triaged_at, revoked at appended_at, including the exact second.

    OpenSSH still accepts a verify time equal to valid-before. This check
    does not.
    """
    _secret, audit, consumed, reports, ring = _halted(tmp_path, "revoke-append")
    record_id = audit.disagreements[0].record_id
    halt = _halt_stamp(reports)
    appended = _shift_stamp(halt, 4 * 60)
    revoked = _shift_stamp(halt, 2 * 60)
    key = make_key(tmp_path / "keys", "danny")
    enroll(reports, tmp_path / "keys", [("danny", key)], valid_before=_openssh(revoked))
    monkeypatch.setattr("faustcoder.reward.audit._utc_stamp", lambda: appended)
    statement, signature = _signed_statement(reports, ring, record_id, halt, key)
    size = reports.path.stat().st_size
    with pytest.raises(RewardRecordError, match="triage"):
        _submit(reports, ring, record_id, halt, statement, signature, principal="danny")
    assert reports.path.stat().st_size == size
    _assert_stays_halted(reports, ring, consumed)

    exact = _shift_stamp(halt, 60)
    monkeypatch.setattr("faustcoder.reward.audit._utc_stamp", lambda: exact)
    key_exact = make_key(tmp_path / "keys", "exact")
    enroll(reports, tmp_path / "exact", [("exact", key_exact)], valid_before=_openssh(exact))
    statement, signature = _signed_statement(reports, ring, record_id, halt, key_exact)
    with pytest.raises(RewardRecordError, match="triage"):
        _submit(
            reports,
            ring,
            record_id,
            halt,
            statement,
            signature,
            principal="exact",
        )
    _assert_stays_halted(reports, ring, consumed)


def test_a_key_revoked_at_triaged_at_does_not_clear(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The key is still valid at appended_at and revoked at triaged_at."""
    _secret, audit, consumed, reports, ring = _halted(tmp_path, "revoke-triage")
    record_id = audit.disagreements[0].record_id
    halt = _halt_stamp(reports)
    triaged = _shift_stamp(halt, 4 * 60)
    revoked = _shift_stamp(halt, 2 * 60)
    key = make_key(tmp_path / "keys", "danny")
    enroll(reports, tmp_path / "keys", [("danny", key)], valid_before=_openssh(revoked))
    monkeypatch.setattr("faustcoder.reward.audit._utc_stamp", lambda: halt)
    statement, signature = _signed_statement(reports, ring, record_id, triaged, key)
    size = reports.path.stat().st_size
    with pytest.raises(RewardRecordError, match="triage"):
        _submit(reports, ring, record_id, triaged, statement, signature, principal="danny")
    assert reports.path.stat().st_size == size
    _assert_stays_halted(reports, ring, consumed)


def test_a_key_revoked_after_appended_at_still_verifies_on_a_later_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _secret, audit, consumed, reports, ring = _halted(tmp_path, "later")
    record_id = audit.disagreements[0].record_id
    halt = _halt_stamp(reports)
    appended = _shift_stamp(halt, 60)
    revoked = _shift_stamp(halt, 10 * 60)
    key = make_key(tmp_path / "keys", "danny")
    enroll(reports, tmp_path / "keys", [("danny", key)], valid_before=_openssh(revoked))
    monkeypatch.setattr("faustcoder.reward.audit._utc_stamp", lambda: appended)
    record_signed(
        reports,
        ring,
        record_id=record_id,
        triaged_by="danny",
        triaged_at=halt,
        principal="danny",
        key_path=key,
    )
    later = datetime.fromisoformat(halt.replace("Z", "+00:00")) + timedelta(minutes=30)

    class Later(datetime):
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:
            return later

    monkeypatch.setattr("faustcoder.reward.triage_sig.datetime", Later)
    monkeypatch.setattr("faustcoder.reward.audit.datetime", Later)
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is True


def test_triaged_at_before_the_halt_and_past_the_skew_stay_halted(tmp_path: Path) -> None:
    _secret, audit, consumed, reports, ring = _halted(tmp_path, "skew")
    record_id = audit.disagreements[0].record_id
    halt = _halt_stamp(reports)
    key = make_key(tmp_path / "keys", "danny")
    enroll(reports, tmp_path / "keys", [("danny", key)])
    early = _shift_stamp(halt, -1)
    statement, signature = _signed_statement(reports, ring, record_id, early, key)
    size = reports.path.stat().st_size
    with pytest.raises(RewardRecordError, match="time"):
        _submit(reports, ring, record_id, early, statement, signature, principal="danny")
    assert reports.path.stat().st_size == size
    _assert_stays_halted(reports, ring, consumed)
    late = _shift_stamp(_stamp_from_now_local(0), 6 * 60)
    statement, signature = _signed_statement(reports, ring, record_id, late, key)
    with pytest.raises(RewardRecordError, match="time"):
        _submit(reports, ring, record_id, late, statement, signature, principal="danny")
    _assert_stays_halted(reports, ring, consumed)
    within = _shift_stamp(_stamp_from_now_local(0), 4 * 60)
    record_signed(
        reports,
        ring,
        record_id=record_id,
        triaged_by="danny",
        triaged_at=within,
        principal="danny",
        key_path=key,
    )
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is True


def _stamp_from_now_local(seconds: int) -> str:
    moment = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_pre_signing_and_a_tampered_statement_stay_halted(tmp_path: Path) -> None:
    secret, audit, consumed, reports, ring = _halted(tmp_path, "presign")
    record_id = audit.disagreements[0].record_id
    stamp = _halt_stamp(reports)
    key = make_key(tmp_path / "keys", "danny")
    enroll(reports, tmp_path / "keys", [("danny", key)])
    statement, signature = _signed_statement(
        reports,
        ring,
        record_id,
        stamp,
        key,
        overrides={"halt_report_mac": "0" * 64},
    )
    size = reports.path.stat().st_size
    with pytest.raises(RewardRecordError, match="triage"):
        _submit(reports, ring, record_id, stamp, statement, signature, principal="danny")
    assert reports.path.stat().st_size == size
    _assert_stays_halted(reports, ring, consumed)
    honest, signature = _signed_statement(reports, ring, record_id, stamp, key)
    honest["decision"] = "exclude"
    with pytest.raises(RewardRecordError, match="triage"):
        _submit(reports, ring, record_id, stamp, honest, signature, principal="danny")
    _assert_stays_halted(reports, ring, consumed)
    later = _shift_stamp(stamp, 60)
    stale, signature = _signed_statement(reports, ring, record_id, later, key)
    _append_halt_copy(reports, secret, halted_at=later)
    body = halt_body(reports, record_id)
    assert body["seq"] != stale["halt_seq"]
    with pytest.raises(RewardRecordError, match="triage"):
        _submit(reports, ring, record_id, later, stale, signature, principal="danny")
    _assert_stays_halted(reports, ring, consumed)


def test_signing_refuses_an_exposed_key(tmp_path: Path) -> None:
    _secret, audit, _consumed, reports, ring = _halted(tmp_path, "exposed")
    record_id = audit.disagreements[0].record_id
    stamp = _halt_stamp(reports)
    key = make_key(tmp_path / "keys", "danny")
    statement = statement_for(
        reports,
        run_id=ring.run_id,
        record_id=record_id,
        triaged_at=stamp,
        fingerprint=public_fingerprint(key),
    )
    os.chmod(key, 0o644)
    with pytest.raises(RewardRecordError, match="key"):
        sign_statement(statement, key)
    os.chmod(key, 0o640)
    with pytest.raises(RewardRecordError, match="key"):
        sign_statement(statement, key)
    os.chmod(key, 0o600)
    assert "BEGIN SSH SIGNATURE" in sign_statement(statement, key)


def test_a_bad_allowed_signers_file_does_not_clear_or_crash_open(tmp_path: Path) -> None:
    secret, audit, consumed, reports, ring = _halted(tmp_path, "signers")
    record_id = audit.disagreements[0].record_id
    stamp = _halt_stamp(reports)
    key = make_key(tmp_path / "keys", "danny")
    good = enroll(reports, tmp_path / "good", [("danny", key)])
    record_signed(
        reports,
        ring,
        record_id=record_id,
        triaged_by="danny",
        triaged_at=stamp,
        principal="danny",
        key_path=key,
    )
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is True
    missing_parent = tmp_path / "missing-parent"
    subprocess.run(["sudo", "-n", "mkdir", "-p", str(missing_parent)], check=True)
    subprocess.run(["sudo", "-n", "chown", "root:root", str(missing_parent)], check=True)
    subprocess.run(["sudo", "-n", "chmod", "755", str(missing_parent)], check=True)
    cases = [
        tmp_path / "no-such-file",
        install_signers(tmp_path / "mine", [signer_line("danny", key)], owner=f"{os.getuid()}:{os.getgid()}"),
        install_signers(tmp_path / "wide", [signer_line("danny", key)], mode=0o666),
        install_signers(tmp_path / "locked", [signer_line("danny", key)], mode=0o444),
        install_signers(tmp_path / "parent-wide", [signer_line("danny", key)], parent_mode=0o777),
    ]
    link_home = install_signers(tmp_path / "link-real", [signer_line("danny", key)])
    link = link_home.parent / "link"
    subprocess.run(["sudo", "-n", "ln", "-s", link_home.name, str(link)], check=True)
    cases.append(link)
    cases.append(missing_parent / "triage-allowed-signers")
    for path in cases:
        reports.allowed_signers = path
        assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is False
        with pytest.raises(RewardRecordError):
            require_allowed_signers(path)
    reports.allowed_signers = good
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is True
    # The missing parent was created as root under tmp_path. release_tmp reclaims it.
    del secret


def test_an_unknown_key_principal_or_namespace_stays_halted(tmp_path: Path) -> None:
    _secret, audit, consumed, reports, ring = _halted(tmp_path, "unknown")
    record_id = audit.disagreements[0].record_id
    stamp = _halt_stamp(reports)
    alice = make_key(tmp_path / "keys", "alice")
    bob = make_key(tmp_path / "keys", "bob")
    enroll(reports, tmp_path / "bob-only", [("bob", bob)])
    statement, signature = _signed_statement(reports, ring, record_id, stamp, alice)
    size = reports.path.stat().st_size
    with pytest.raises(RewardRecordError, match="triage"):
        _submit(reports, ring, record_id, stamp, statement, signature, principal="alice")
    assert reports.path.stat().st_size == size
    _assert_stays_halted(reports, ring, consumed)
    enroll(reports, tmp_path / "other-ns", [("alice", alice)], namespace="other")
    with pytest.raises(RewardRecordError, match="triage"):
        _submit(reports, ring, record_id, stamp, statement, signature, principal="alice")
    _assert_stays_halted(reports, ring, consumed)
    unrestricted = alice.with_name(alice.name + ".pub").read_text(encoding="utf-8").split()
    bare = install_signers(
        tmp_path / "bare",
        [f'alice valid-after="20200101000000" {unrestricted[0]} {unrestricted[1]}'],
    )
    reports.allowed_signers = bare
    with pytest.raises(RewardRecordError, match="triage"):
        _submit(reports, ring, record_id, stamp, statement, signature, principal="alice")
    _assert_stays_halted(reports, ring, consumed)


def test_a_symlink_or_grader_owned_drop_is_refused(tmp_path: Path) -> None:
    _secret, audit, consumed, reports, ring = _halted(tmp_path, "drop")
    record_id = audit.disagreements[0].record_id
    stamp = _halt_stamp(reports)
    key = make_key(tmp_path / "keys", "danny")
    enroll(reports, tmp_path / "keys", [("danny", key)])
    statement, signature = _signed_statement(reports, ring, record_id, stamp, key)
    real = tmp_path / "real-drop.json"
    write_drop(
        real,
        principal="danny",
        triaged_by="danny",
        statement=statement,
        signature=signature,
    )
    link = tmp_path / "linked-drop.json"
    link.symlink_to(real)
    size = reports.path.stat().st_size
    with pytest.raises(RewardRecordError, match="drop|triage"):
        reports.record_triage(
            ring,
            record_id=record_id,
            triaged_by="danny",
            triaged_at=stamp,
            drop_path=link,
        )
    assert reports.path.stat().st_size == size
    root_drop = tmp_path / "root-drop.json"
    write_drop(
        root_drop,
        principal="danny",
        triaged_by="danny",
        statement=statement,
        signature=signature,
    )
    subprocess.run(["sudo", "-n", "chown", "root:root", str(root_drop)], check=True)
    with pytest.raises(RewardRecordError, match="triage|writer"):
        reports.record_triage(
            ring,
            record_id=record_id,
            triaged_by="danny",
            triaged_at=stamp,
            drop_path=root_drop,
        )
    try:
        pwd.getpwnam("fc-grader")
    except KeyError:
        subprocess.run(
            [
                "sudo",
                "-n",
                "useradd",
                "--system",
                "--no-create-home",
                "--shell",
                "/usr/sbin/nologin",
                "fc-grader",
            ],
            check=True,
        )
    grader = pwd.getpwnam("fc-grader")
    grader_drop = tmp_path / "grader-drop.json"
    write_drop(
        grader_drop,
        principal="danny",
        triaged_by="danny",
        statement=statement,
        signature=signature,
    )
    subprocess.run(
        ["sudo", "-n", "chown", f"{grader.pw_uid}:{grader.pw_gid}", str(grader_drop)],
        check=True,
    )
    with pytest.raises(RewardRecordError, match="triage|writer"):
        reports.record_triage(
            ring,
            record_id=record_id,
            triaged_by="danny",
            triaged_at=stamp,
            drop_path=grader_drop,
        )
    _assert_stays_halted(reports, ring, consumed)
    with pytest.raises(RewardRecordError, match="drop"):
        read_drop(link)


def test_old_or_missing_openssh_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    version = require_openssh()
    assert version >= (8, 7)
    _secret, audit, consumed, reports, ring = _halted(tmp_path, "ssh")
    record_id = audit.disagreements[0].record_id
    stamp = _halt_stamp(reports)
    key = make_key(tmp_path / "keys", "danny")
    enroll(reports, tmp_path / "keys", [("danny", key)])
    statement, signature = _signed_statement(reports, ring, record_id, stamp, key)
    real_run = subprocess.run

    def old_ssh(args, **kwargs):
        if isinstance(args, list) and len(args) >= 2 and args[1] == "-V" and "keygen" not in str(args[0]):
            return subprocess.CompletedProcess(args, 0, "", "OpenSSH_8.6p1\n")
        return real_run(args, **kwargs)

    monkeypatch.setattr("faustcoder.reward.triage_sig.subprocess.run", old_ssh)
    with pytest.raises(RewardRecordError, match="OpenSSH 8.7"):
        _submit(reports, ring, record_id, stamp, statement, signature, principal="danny")
    _assert_stays_halted(reports, ring, consumed)
    monkeypatch.setattr("faustcoder.reward.triage_sig._which", lambda _name: None)
    with pytest.raises(RewardRecordError, match="ssh-keygen"):
        _submit(reports, ring, record_id, stamp, statement, signature, principal="danny")
    _assert_stays_halted(reports, ring, consumed)


def test_p3_refuses_uid_1000_and_a_reviewer_uid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert os.geteuid() == 1000
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-train",
        members=[("signal", "pass", _signal(source, passed=True), source)],
    )
    log = tmp_path / "rows.jsonl"
    _store(log, header, rows)
    ring = RewardKeyring(secret, run_id=RUN)
    loaded = load_records(log, ring)
    consumed = ConsumedLog(tmp_path / "consumed.jsonl")
    reports = AuditReportLog(tmp_path / "reports.jsonl", consumed)
    from faustcoder.reward.audit import audit_sampled_reruns

    audit_sampled_reruns(
        loaded.rows,
        ring,
        rerun=_echo,
        consumed=consumed,
        reports=reports,
    )
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is True
    with pytest.raises(RewardRecordError, match="uid 1000"):
        rl_batch_from_records(
            loaded.headers,
            loaded.rows,
            keyring=ring,
            expected_run_id=RUN,
            policy_checkpoints=(CHECKPOINT,),
            queue=QuarantineQueue(tmp_path / "q.jsonl"),
            rates=UngradedRateTracker(),
            consumed=consumed,
            reports=reports,
        )
    with pytest.raises(RewardRecordError, match="uid 1000"):
        require_p3_grader_account(tmp_path / "missing-signers")

    reviewer = make_key(tmp_path / "reviewer", "alice")
    signers = install_signers(tmp_path / "reviewer", [signer_line("alice", reviewer)])
    monkeypatch.setattr("faustcoder.reward.triage_sig.os.geteuid", lambda: 4242)
    real_getpwnam = pwd.getpwnam

    def same_uid(name: str):
        if name in {"fc-grader", "alice"}:
            return pwd.struct_passwd((name, "x", 4242, 4242, "", "/", "/usr/sbin/nologin"))
        return real_getpwnam(name)

    monkeypatch.setattr("faustcoder.reward.triage_sig.pwd.getpwnam", same_uid)
    with pytest.raises(RewardRecordError, match="enrolled reviewer"):
        require_p3_grader_account(signers)

    def distinct(name: str):
        if name == "fc-grader":
            return pwd.struct_passwd(("fc-grader", "x", 4242, 4242, "", "/", "/usr/sbin/nologin"))
        if name == "alice":
            return pwd.struct_passwd(("alice", "x", 1001, 1001, "", "/", "/bin/bash"))
        return real_getpwnam(name)

    monkeypatch.setattr("faustcoder.reward.triage_sig.pwd.getpwnam", distinct)
    require_p3_grader_account(signers)


def test_p3_startup_refuses_old_openssh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_run = subprocess.run

    def old_ssh(args, **kwargs):
        if isinstance(args, list) and len(args) >= 2 and args[1] == "-V" and "keygen" not in str(args[0]):
            return subprocess.CompletedProcess(args, 0, "", "OpenSSH_8.6p1\n")
        return real_run(args, **kwargs)

    monkeypatch.setattr("faustcoder.reward.triage_sig.subprocess.run", old_ssh)
    secret = _write_key(tmp_path / "reward-root.key")
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-old-ssh",
        members=[("signal", "pass", _signal(b"process = _;", passed=True), b"process = _;")],
    )
    with pytest.raises(RewardRecordError, match="OpenSSH 8.7"):
        rl_batch_from_records(
            (header,),
            tuple(rows),
            keyring=RewardKeyring(secret, run_id=RUN),
            expected_run_id=RUN,
            policy_checkpoints=(CHECKPOINT,),
            queue=QuarantineQueue(tmp_path / "q.jsonl"),
            rates=UngradedRateTracker(),
            consumed=ConsumedLog(tmp_path / "consumed.jsonl"),
            reports=AuditReportLog(tmp_path / "reports.jsonl", ConsumedLog(tmp_path / "consumed.jsonl")),
        )


def test_cli_sign_writes_a_verifiable_drop(tmp_path: Path) -> None:
    _secret, audit, _consumed, reports, ring = _halted(tmp_path, "cli")
    record_id = audit.disagreements[0].record_id
    stamp = _halt_stamp(reports)
    key = make_key(tmp_path / "keys", "danny")
    signers = enroll(reports, tmp_path / "keys", [("danny", key)])
    statement = statement_for(
        reports,
        run_id=ring.run_id,
        record_id=record_id,
        triaged_at=stamp,
        fingerprint=public_fingerprint(key),
    )
    statement_path = tmp_path / "statement.json"
    statement_path.write_bytes(canonical_bytes(statement))
    drop = tmp_path / "triage.json"
    code = main(
        [
            "triage",
            "sign",
            "--key",
            str(key),
            "--statement",
            str(statement_path),
            "--principal",
            "danny",
            "--triaged-by",
            "danny",
            "--drop",
            str(drop),
        ]
    )
    assert code == 0
    loaded = read_drop(drop)
    verify_statement(
        loaded.statement,
        loaded.signature,
        principal="danny",
        allowed_signers=signers,
        appended_at=stamp,
        triaged_at=stamp,
    )
    os.chmod(key, 0o644)
    refused = main(
        [
            "triage",
            "sign",
            "--key",
            str(key),
            "--statement",
            str(statement_path),
            "--principal",
            "danny",
            "--triaged-by",
            "danny",
            "--drop",
            str(tmp_path / "again.json"),
        ]
    )
    assert refused != 0


def test_option_b_still_refuses_a_reserved_actor(tmp_path: Path) -> None:
    _secret, audit, consumed, reports, ring = _halted(tmp_path, "option-b")
    record_id = audit.disagreements[0].record_id
    stamp = _halt_stamp(reports)
    key = make_key(tmp_path / "keys", "danny")
    enroll(reports, tmp_path / "keys", [("danny", key)])
    statement, signature = _signed_statement(reports, ring, record_id, stamp, key)
    size = reports.path.stat().st_size
    with pytest.raises(RewardRecordError, match="triage"):
        _submit(
            reports,
            ring,
            record_id,
            stamp,
            statement,
            signature,
            principal="danny",
            triaged_by="fc-grader",
        )
    assert reports.path.stat().st_size == size
    _assert_stays_halted(reports, ring, consumed)

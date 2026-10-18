"""D3-H2: sampled rerun-from-source audit before P3 (spec §26 0.3.9)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from faustcoder.canonical import canonical_bytes, loads_strict
from faustcoder.reward.audit import (
    AuditReportLog,
    _line_mac,
    audit_sampled_reruns,
    derive_audit_seed,
    p3_may_proceed,
    select_fail_sample,
)
from faustcoder.reward.records import (
    ConsumedLog,
    RewardGroupConsumed,
    RewardKeyring,
    RewardRecordError,
    derive_run_key,
    load_records,
    mac,
    rl_batch_from_records,
    verify,
)
from faustcoder.reward.types import QuarantineQueue, UngradedRateTracker
from tests.test_reward_records import (
    CHECKPOINT,
    HARNESS,
    RUN,
    _compiler,
    _members,
    _signal,
    _store,
    _write_key,
)


@pytest.fixture(autouse=True)
def _pin_harness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "faustcoder.reward.records.current_harness_digest",
        lambda: HARNESS,
    )


def _rows(secret: bytes, group_id: str, members, *, canaries: tuple[int, ...] = ()):
    _header, rows = _members(
        secret,
        run_id=RUN,
        group_id=group_id,
        members=members,
        canaries=canaries,
    )
    return tuple(rows)


def _audit(tmp_path: Path, secret: bytes, rows, rerun, *, name: str, seed=None, canary_ids=None):
    ring = RewardKeyring(secret, run_id=RUN)
    consumed = ConsumedLog(tmp_path / f"{name}-consumed.jsonl")
    reports = AuditReportLog(tmp_path / f"{name}-reports.jsonl", consumed)
    audit = audit_sampled_reruns(
        rows,
        ring,
        rerun=rerun,
        consumed=consumed,
        reports=reports,
        seed=seed,
        canary_ids=canary_ids,
    )
    return audit, consumed, reports, ring


def _echo(record):
    return record.outcome


def test_fail_sample_is_ceil_five_percent() -> None:
    assert select_fail_sample((), "seed") == ()
    for count, expected in ((1, 1), (19, 1), (20, 1), (21, 2), (40, 2), (100, 5)):
        ids = [f"id-{index:03d}" for index in range(count)]
        assert len(select_fail_sample(ids, "seed")) == expected
        assert len(select_fail_sample(ids, "seed")) == (count * 5 + 99) // 100


def test_agreement_persists_a_clear_report(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    rows = _rows(
        secret,
        "group-agree",
        [("signal", "pass", _signal(source, passed=True), source)],
    )
    seen: list[bytes] = []

    def rerun(record):
        seen.append(record.source)
        return record.outcome

    audit, consumed, reports, ring = _audit(tmp_path, secret, rows, rerun, name="agree")
    derived = derive_audit_seed(ring, RUN)
    assert audit.halted is False
    assert audit.report()["p3"] == "clear"
    assert audit.seed == derived
    assert audit.report()["seed"] == derived
    assert audit.report()["sample_ids"] == list(audit.sample_ids)
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is True
    restarted = AuditReportLog(reports.path, consumed)
    assert p3_may_proceed(RUN, keyring=ring, reports=restarted, consumed=consumed) is True
    assert consumed.disposition(rows[0].group_id) is None
    consumed_text = consumed.path.read_text(encoding="utf-8")
    assert consumed_text.startswith("audit-anchor v1 ")
    assert rows[0].group_id not in consumed_text
    assert rows[0].outcome == "pass"
    assert seen == [source]
    assert rows[0].record_id in audit.audited_ids
    again, _consumed, _reports, _ring = _audit(
        tmp_path,
        secret,
        rows,
        rerun,
        name="agree-again",
        seed=derived,
    )
    assert again.halted is False
    assert again.seed == derived


def test_pass_that_fails_on_rerun_halts_and_drops_the_group(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    good = b"process = _;"
    bad = b"process = +;"
    rows = _rows(
        secret,
        "group-flip",
        [
            ("signal", "pass", _signal(good, passed=True), good),
            ("signal", "fail", _signal(bad, passed=False), bad),
        ],
    )
    audit, consumed, reports, ring = _audit(
        tmp_path,
        secret,
        rows,
        lambda _record: "fail",
        name="flip",
    )
    report = audit.report()
    assert audit.halted is True
    assert report["p3"] == "halt"
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is False
    assert p3_may_proceed(RUN, keyring=ring, reports=AuditReportLog(reports.path, consumed), consumed=consumed) is False
    assert audit.dropped_groups == ("group-flip",)
    assert audit.late_groups == ()
    assert len(audit.sample_ids) == 1
    assert len(audit.disagreements) == 1
    item = audit.disagreements[0]
    assert item.record_id == rows[0].record_id
    assert item.stored_outcome == "pass"
    assert item.rerun_outcome == "fail"
    assert report["disagreements"][0]["row"] == "ungraded"
    assert json.loads(audit.canonical_report())["p3"] == "halt"
    assert rows[0].outcome == "pass"
    assert rows[1].outcome == "fail"
    assert audit.kept_ids == ()
    assert consumed.disposition("group-flip") == "dropped:audit"
    before = consumed.path.stat().st_size
    with pytest.raises(RewardRecordError, match="already consumed"):
        ConsumedLog(consumed.path).claim(
            "group-flip",
            "used",
            task_digest_full=rows[0].task_digest_full,
            policy_checkpoint=CHECKPOINT,
        )
    assert consumed.path.stat().st_size == before
    repeat = audit_sampled_reruns(
        rows,
        ring,
        rerun=lambda _record: "fail",
        consumed=ConsumedLog(consumed.path),
        reports=reports,
    )
    assert repeat.halted is True
    assert repeat.dropped_groups == ("group-flip",)
    assert consumed.path.stat().st_size == before
    frozen = reports.path.read_bytes()
    with pytest.raises(RewardRecordError, match="not cleared"):
        audit_sampled_reruns(
            rows,
            ring,
            rerun=_echo,
            consumed=ConsumedLog(tmp_path / "flip-echo-consumed.jsonl"),
            reports=reports,
        )
    assert reports.path.read_bytes() == frozen
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is False
    with pytest.raises(RewardRecordError, match="seed"):
        audit_sampled_reruns(
            rows,
            ring,
            seed="0" * 64,
            rerun=_echo,
            consumed=ConsumedLog(tmp_path / "flip-seed-consumed.jsonl"),
            reports=reports,
        )
    assert reports.path.read_bytes() == frozen


def test_source_attributed_rows_are_in_the_fail_sample(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = +;"
    envelope = _compiler(
        source,
        exit_code=1,
        diagnostic_class="parse_error",
        diagnostics="parse error\n",
    )
    rows = _rows(
        secret,
        "group-attributed",
        [("compiler", "source_attributed", envelope, source)],
    )
    called: list[str] = []

    def rerun(record):
        called.append(record.record_id)
        return "pass"

    audit, consumed, reports, ring = _audit(
        tmp_path,
        secret,
        rows,
        rerun,
        name="attributed",
    )
    assert audit.sample_ids == (rows[0].record_id,)
    assert called == [rows[0].record_id]
    assert audit.halted is True
    assert audit.disagreements[0].stored_outcome == "source_attributed"
    assert audit.disagreements[0].rerun_outcome == "pass"
    assert rows[0].outcome == "source_attributed"
    assert consumed.disposition("group-attributed") == "dropped:audit"
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is False


def test_foreign_seed_cannot_dodge_a_sampled_fail(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    members = []
    for index in range(21):
        source = f"process = {index};".encode()
        members.append(("signal", "fail", _signal(source, passed=False), source))
    rows = _rows(secret, "group-dodge", members)
    ring = RewardKeyring(secret, run_id=RUN)
    derived = derive_audit_seed(ring, RUN)
    ids = [row.record_id for row in rows]
    real = select_fail_sample(ids, derived)
    assert len(real) == 2
    target = real[0]
    foreign = None
    for index in range(64):
        trial = f"trial-{index}"
        if target not in select_fail_sample(ids, trial):
            foreign = trial
            break
    assert foreign is not None
    called: list[str] = []
    dodge_consumed = ConsumedLog(tmp_path / "dodge-consumed.jsonl")
    reports = AuditReportLog(tmp_path / "dodge-reports.jsonl", dodge_consumed)
    with pytest.raises(RewardRecordError, match="seed"):
        audit_sampled_reruns(
            rows,
            ring,
            seed=foreign,
            rerun=lambda record: called.append(record.record_id) or record.outcome,
            consumed=dodge_consumed,
            reports=reports,
        )
    assert called == []
    assert not reports.path.exists()
    audit, _consumed, _reports, _ring = _audit(
        tmp_path,
        secret,
        rows,
        _echo,
        name="dodge-real",
    )
    assert target in audit.sample_ids
    assert audit.seed == derived


def test_signed_canaries_are_audited_and_a_spoofed_list_is_refused(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    plain = b"process = 1;"
    marked = b"process = 2;"
    plain_env = _compiler(
        plain,
        exit_code=124,
        diagnostic_class="timeout",
        diagnostics="timeout: wall clock limit exceeded\n",
    )
    marked_env = _compiler(
        marked,
        exit_code=124,
        diagnostic_class="timeout",
        diagnostics="timeout: wall clock limit exceeded\n",
    )
    rows = _rows(
        secret,
        "group-canary",
        [
            ("compiler", "ungraded:unattributed", plain_env, plain),
            ("compiler", "ungraded:unattributed", marked_env, marked),
        ],
        canaries=(1,),
    )
    assert rows[0].canary is False
    assert rows[1].canary is True
    called: list[str] = []

    def rerun(record):
        called.append(record.record_id)
        return "pass"

    audit, consumed, reports, ring = _audit(
        tmp_path,
        secret,
        rows,
        rerun,
        name="canary",
    )
    assert audit.sample_ids == ()
    assert called == [rows[1].record_id]
    assert rows[1].record_id in audit.audited_ids
    assert rows[0].record_id not in audit.audited_ids
    assert audit.halted is True
    assert audit.disagreements[0].stored_outcome == "ungraded:unattributed"
    assert consumed.disposition("group-canary") == "dropped:audit"
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is False

    secret_ok = _write_key(tmp_path / "reward-root-ok.key")
    quiet = _rows(
        secret_ok,
        "group-quiet",
        [("compiler", "ungraded:unattributed", marked_env, marked)],
        canaries=(0,),
    )
    skipped: list[str] = []
    omit_consumed = ConsumedLog(tmp_path / "omit-consumed.jsonl")
    omitted = AuditReportLog(tmp_path / "omit-reports.jsonl", omit_consumed)
    with pytest.raises(RewardRecordError, match="canary"):
        audit_sampled_reruns(
            quiet,
            RewardKeyring(secret_ok, run_id=RUN),
            rerun=lambda record: skipped.append(record.record_id) or "pass",
            consumed=omit_consumed,
            reports=omitted,
            canary_ids=(),
        )
    assert skipped == []
    assert not omitted.path.exists()
    extra: list[str] = []
    spoof_consumed = ConsumedLog(tmp_path / "spoof-consumed.jsonl")
    spoofed = AuditReportLog(tmp_path / "spoof-reports.jsonl", spoof_consumed)
    with pytest.raises(RewardRecordError, match="canary"):
        audit_sampled_reruns(
            quiet,
            RewardKeyring(secret_ok, run_id=RUN),
            rerun=lambda record: extra.append(record.record_id) or "pass",
            consumed=spoof_consumed,
            reports=spoofed,
            canary_ids={quiet[0].record_id, "not-a-signed-canary"},
        )
    assert extra == []
    assert not spoofed.path.exists()
    matched, _consumed, _reports, _ring = _audit(
        tmp_path,
        secret_ok,
        quiet,
        lambda _record: "ungraded:unattributed",
        name="canary-match",
        canary_ids={quiet[0].record_id},
    )
    assert matched.halted is False
    assert quiet[0].record_id in matched.audited_ids


def test_sample_is_reproducible_from_the_derived_seed(tmp_path: Path) -> None:
    ids = [f"id-{index:02d}" for index in range(40)]
    first = select_fail_sample(ids, "seed-a")
    assert first == select_fail_sample(list(reversed(ids)), "seed-a")
    assert first == select_fail_sample(ids + list(ids), "seed-a")
    assert len(first) == 2
    other = select_fail_sample(ids, "seed-b")
    if other == first:
        other = select_fail_sample(ids, "seed-c")
    assert other != first
    secret = _write_key(tmp_path / "reward-root.key")
    members = []
    for index in range(20):
        source = f"process = {index};".encode()
        members.append(("signal", "fail", _signal(source, passed=False), source))
    rows = _rows(secret, "group-repro", members)
    forward, _consumed, _reports, ring = _audit(tmp_path, secret, rows, _echo, name="repro-f")
    backward, _back_consumed, _back_reports, _ring = _audit(
        tmp_path,
        secret,
        tuple(reversed(rows)),
        _echo,
        name="repro-b",
    )
    assert forward.sample_ids == backward.sample_ids
    assert len(forward.sample_ids) == 1
    assert forward.seed == derive_audit_seed(ring, RUN)
    assert forward.halted is False
    assert forward.report()["sample_ids"] == list(forward.sample_ids)
    assert forward.report()["seed"] == forward.seed


def test_hmac_invalid_rows_are_refused(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    rows = _rows(
        secret,
        "group-mac",
        [("signal", "pass", _signal(source, passed=True), source)],
    )
    bad = replace(rows[0], mac="00" * 32)
    called: list[str] = []
    mac_consumed = ConsumedLog(tmp_path / "mac-consumed.jsonl")
    reports = AuditReportLog(tmp_path / "mac-reports.jsonl", mac_consumed)
    with pytest.raises(RewardRecordError, match="HMAC"):
        audit_sampled_reruns(
            [bad],
            RewardKeyring(secret, run_id=RUN),
            rerun=lambda record: called.append(record.record_id) or record.outcome,
            consumed=mac_consumed,
            reports=reports,
        )
    assert called == []
    assert not reports.path.exists()
    assert bad.outcome == "pass"
    assert rows[0].outcome == "pass"


def test_an_already_used_group_is_reported_late(tmp_path: Path) -> None:
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
    )
    ring = RewardKeyring(secret, run_id=RUN)
    reports = AuditReportLog(tmp_path / "used-reports.jsonl", consumed)
    audit = audit_sampled_reruns(
        rows,
        ring,
        rerun=lambda _record: "fail",
        consumed=consumed,
        reports=reports,
    )
    assert audit.late_groups == ("group-used",)
    assert audit.dropped_groups == ()
    assert audit.report()["late_groups"] == [{"disposition": "late", "group_id": "group-used"}]
    assert audit.halted is True
    assert "dropped:audit" not in consumed.path.read_text(encoding="utf-8")
    assert ConsumedLog(consumed.path).disposition("group-used") == "used"
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is False


def test_an_unexpected_disposition_fails_closed_and_persists_the_halt(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    rows = _rows(
        secret,
        "group-held",
        [("signal", "pass", _signal(source, passed=True), source)],
    )
    consumed = ConsumedLog(tmp_path / "held-consumed.jsonl")
    consumed.claim(
        "group-held",
        "dropped:quarantined",
        task_digest_full=rows[0].task_digest_full,
        policy_checkpoint=CHECKPOINT,
    )
    ring = RewardKeyring(secret, run_id=RUN)
    reports = AuditReportLog(tmp_path / "held-reports.jsonl", consumed)
    with pytest.raises(RewardGroupConsumed) as raised:
        audit_sampled_reruns(
            rows,
            ring,
            rerun=lambda _record: "fail",
            consumed=consumed,
            reports=reports,
        )
    assert raised.value.group_id == "group-held"
    assert raised.value.disposition == "dropped:quarantined"
    assert ConsumedLog(consumed.path).disposition("group-held") == "dropped:quarantined"
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is False


def test_a_rerun_crash_is_a_disagreement(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    first = b"process = _;"
    second = b"process = +;"
    header_a, rows_a = _members(
        secret,
        run_id=RUN,
        group_id="group-a",
        members=[("signal", "pass", _signal(first, passed=True), first)],
    )
    header_b, rows_b = _members(
        secret,
        run_id=RUN,
        group_id="group-b",
        members=[("signal", "pass", _signal(second, passed=True), second)],
    )
    rows = tuple(rows_a + rows_b)

    def rerun(record):
        if record.group_id == "group-a":
            return "fail"
        raise RuntimeError("rerun crashed")

    audit, consumed, reports, ring = _audit(tmp_path, secret, rows, rerun, name="crash")
    assert audit.halted is True
    assert {item.group_id for item in audit.disagreements} == {"group-a", "group-b"}
    crashed = next(item for item in audit.disagreements if item.group_id == "group-b")
    assert crashed.rerun_outcome == ""
    assert set(audit.dropped_groups) == {"group-a", "group-b"}
    assert consumed.disposition("group-a") == "dropped:audit"
    assert consumed.disposition("group-b") == "dropped:audit"
    assert rows_a[0].outcome == "pass"
    assert rows_b[0].outcome == "pass"
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is False
    assert header_a.group_id == "group-a"
    assert header_b.group_id == "group-b"


def test_a_non_str_rerun_result_is_a_disagreement(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"

    class _Outcome(str):
        pass

    cases = (
        ("none", lambda _record: None),
        ("int", lambda _record: 1),
        ("subclass", lambda record: _Outcome(record.outcome)),
    )
    for name, rerun in cases:
        rows = _rows(
            secret,
            f"group-{name}",
            [("signal", "pass", _signal(source, passed=True), source)],
        )
        audit, consumed, reports, ring = _audit(tmp_path, secret, rows, rerun, name=name)
        assert audit.halted is True
        assert audit.disagreements[0].rerun_outcome == ""
        assert audit.report()["p3"] == "halt"
        assert type(audit.report()["disagreements"][0]["rerun_outcome"]) is str
        assert consumed.disposition(f"group-{name}") == "dropped:audit"
        assert rows[0].outcome == "pass"
        assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is False


def test_triage_is_the_only_clear(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    first = b"process = _;"
    second = b"process = +;"
    _header_a, rows_a = _members(
        secret,
        run_id=RUN,
        group_id="group-a",
        members=[("signal", "pass", _signal(first, passed=True), first)],
    )
    _header_b, rows_b = _members(
        secret,
        run_id=RUN,
        group_id="group-b",
        members=[("signal", "pass", _signal(second, passed=True), second)],
    )
    rows = tuple(rows_a + rows_b)
    audit, consumed, reports, ring = _audit(
        tmp_path,
        secret,
        rows,
        lambda _record: "fail",
        name="triage",
    )
    assert len(audit.disagreements) == 2
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is False
    reports.record_triage(
        ring,
        record_id=audit.disagreements[0].record_id,
        triaged_by="danny",
        triaged_at="2026-10-18T15:10:00Z",
    )
    assert p3_may_proceed(RUN, keyring=ring, reports=AuditReportLog(reports.path, consumed), consumed=consumed) is False
    size = reports.path.stat().st_size
    reports.record_triage(
        ring,
        record_id=audit.disagreements[0].record_id,
        triaged_by="danny",
        triaged_at="2026-10-18T15:10:00Z",
    )
    assert reports.path.stat().st_size == size
    with pytest.raises(RewardRecordError, match="triage"):
        reports.record_triage(
            ring,
            record_id="0" * 64,
            triaged_by="danny",
            triaged_at="2026-10-18T15:10:00Z",
        )
    reports.record_triage(
        ring,
        record_id=audit.disagreements[1].record_id,
        triaged_by="danny",
        triaged_at="2026-10-18T15:11:00Z",
    )
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is True
    assert consumed.disposition("group-a") == "dropped:audit"
    assert consumed.disposition("group-b") == "dropped:audit"
    with pytest.raises(RewardGroupConsumed) as raised:
        consumed.claim(
            "group-a",
            "used",
            task_digest_full=rows_a[0].task_digest_full,
            policy_checkpoint=CHECKPOINT,
        )
    assert raised.value.disposition == "dropped:audit"


def test_rl_batch_requires_a_clear_report_and_keeps_a_dropped_group_out(tmp_path: Path) -> None:
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
    consumed = ConsumedLog(tmp_path / "train-consumed.jsonl")
    reports = AuditReportLog(tmp_path / "train-reports.jsonl", consumed)
    with pytest.raises(RewardRecordError, match="clear audit report"):
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
    assert consumed.disposition("group-train") is None
    audit_sampled_reruns(
        loaded.rows,
        ring,
        rerun=_echo,
        consumed=ConsumedLog(tmp_path / "train-audit-consumed.jsonl"),
        reports=reports,
    )
    batch = rl_batch_from_records(
        loaded.headers,
        loaded.rows,
        keyring=ring,
        expected_run_id=RUN,
        policy_checkpoints=(CHECKPOINT,),
        queue=QuarantineQueue(tmp_path / "q2.jsonl"),
        rates=UngradedRateTracker(),
        consumed=consumed,
        reports=reports,
    )
    assert batch.rows[0]["example_id"] == rows[0].record_id
    assert batch.rows[0]["reward"] == 1.0

    halted_source = b"process = +;"
    halted_header, halted_rows = _members(
        secret,
        run_id=RUN,
        group_id="group-halted",
        members=[("signal", "pass", _signal(halted_source, passed=True), halted_source)],
    )
    halted_log = tmp_path / "halted.jsonl"
    _store(halted_log, halted_header, halted_rows)
    halted_loaded = load_records(halted_log, ring)
    halted_consumed = ConsumedLog(tmp_path / "halted-consumed.jsonl")
    halted_reports = AuditReportLog(tmp_path / "halted-reports.jsonl", halted_consumed)
    audit_sampled_reruns(
        halted_loaded.rows,
        ring,
        rerun=lambda _record: "fail",
        consumed=halted_consumed,
        reports=halted_reports,
    )
    with pytest.raises(RewardRecordError, match="clear audit report"):
        rl_batch_from_records(
            halted_loaded.headers,
            halted_loaded.rows,
            keyring=ring,
            expected_run_id=RUN,
            policy_checkpoints=(CHECKPOINT,),
            queue=QuarantineQueue(tmp_path / "q3.jsonl"),
            rates=UngradedRateTracker(),
            consumed=halted_consumed,
            reports=halted_reports,
        )
    halted_reports.record_triage(
        ring,
        record_id=halted_rows[0].record_id,
        triaged_by="danny",
        triaged_at="2026-10-18T15:12:00Z",
    )
    fresh_source = b"process = _;"
    fresh_header, fresh_rows = _members(
        secret,
        run_id=RUN,
        group_id="group-fresh",
        members=[("signal", "pass", _signal(fresh_source, passed=True), fresh_source)],
    )
    fresh_log = tmp_path / "fresh.jsonl"
    _store(fresh_log, fresh_header, fresh_rows)
    fresh_loaded = load_records(fresh_log, ring)
    with pytest.raises(RewardRecordError, match="did not cover"):
        rl_batch_from_records(
            fresh_loaded.headers,
            fresh_loaded.rows,
            keyring=ring,
            expected_run_id=RUN,
            policy_checkpoints=(CHECKPOINT,),
            queue=QuarantineQueue(tmp_path / "q4.jsonl"),
            rates=UngradedRateTracker(),
            consumed=halted_consumed,
            reports=halted_reports,
        )
    audit_sampled_reruns(
        fresh_loaded.rows,
        ring,
        rerun=_echo,
        consumed=halted_consumed,
        reports=halted_reports,
    )
    with pytest.raises(RewardGroupConsumed):
        rl_batch_from_records(
            halted_loaded.headers + fresh_loaded.headers,
            halted_loaded.rows + fresh_loaded.rows,
            keyring=ring,
            expected_run_id=RUN,
            policy_checkpoints=(CHECKPOINT,),
            queue=QuarantineQueue(tmp_path / "q4b.jsonl"),
            rates=UngradedRateTracker(),
            consumed=halted_consumed,
            reports=halted_reports,
        )
    resumed = rl_batch_from_records(
        fresh_loaded.headers,
        fresh_loaded.rows,
        keyring=ring,
        expected_run_id=RUN,
        policy_checkpoints=(CHECKPOINT,),
        queue=QuarantineQueue(tmp_path / "q5.jsonl"),
        rates=UngradedRateTracker(),
        consumed=halted_consumed,
        reports=halted_reports,
    )
    assert resumed.rows[0]["example_id"] == fresh_rows[0].record_id
    assert halted_consumed.disposition("group-halted") == "dropped:audit"
    assert halted_consumed.disposition("group-fresh") == "used"


def test_a_tampered_report_mac_does_not_read_as_clear(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    rows = _rows(
        secret,
        "group-tamper",
        [("signal", "pass", _signal(source, passed=True), source)],
    )
    _audit_result, consumed, reports, ring = _audit(tmp_path, secret, rows, _echo, name="tamper")
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is True
    raw = bytearray(reports.path.read_bytes())
    raw[0] ^= 0x01
    reports.path.write_bytes(raw)
    with pytest.raises(RewardRecordError, match="mac|corrupt"):
        p3_may_proceed(RUN, keyring=ring, reports=AuditReportLog(reports.path, consumed), consumed=consumed)


def test_a_row_signed_before_canary_is_refused_on_load(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-old",
        members=[("signal", "pass", _signal(source, passed=True), source)],
    )
    log = tmp_path / "old.jsonl"
    _store(log, header, rows)
    lines = log.read_text(encoding="utf-8").splitlines()
    body = loads_strict(lines[1])
    assert body["canary"] is False
    del body["canary"]
    lines[1] = canonical_bytes(body).decode("ascii")
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(RewardRecordError, match="not signed"):
        load_records(log, RewardKeyring(secret, run_id=RUN))


def _stored_pass(tmp_path: Path, secret: bytes, group_id: str):
    source = b"process = _;"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id=group_id,
        members=[("signal", "pass", _signal(source, passed=True), source)],
    )
    log = tmp_path / f"{group_id}.jsonl"
    _store(log, header, rows)
    loaded = load_records(log, RewardKeyring(secret, run_id=RUN))
    return loaded


def test_an_empty_audit_does_not_admit_a_row(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    ring = RewardKeyring(secret, run_id=RUN)
    consumed = ConsumedLog(tmp_path / "empty-consumed.jsonl")
    reports = AuditReportLog(tmp_path / "empty-reports.jsonl", consumed)
    audit = audit_sampled_reruns(
        (),
        ring,
        rerun=_echo,
        consumed=consumed,
        reports=reports,
    )
    assert audit.report()["p3"] == "clear"
    assert audit.row_ids == ()
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is True
    loaded = _stored_pass(tmp_path, secret, "group-empty")
    with pytest.raises(RewardRecordError, match="did not cover"):
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


def test_a_subset_audit_does_not_admit_a_left_out_canary(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    ring = RewardKeyring(secret, run_id=RUN)
    covered = _stored_pass(tmp_path, secret, "group-covered")
    marked = b"process = 2;"
    envelope = _compiler(
        marked,
        exit_code=124,
        diagnostic_class="timeout",
        diagnostics="timeout: wall clock limit exceeded\n",
    )
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-left-out",
        members=[("compiler", "ungraded:unattributed", envelope, marked)],
        canaries=(0,),
    )
    log = tmp_path / "left-out.jsonl"
    _store(log, header, rows)
    left = load_records(log, ring)
    assert left.rows[0].canary is True
    consumed = ConsumedLog(tmp_path / "subset-consumed.jsonl")
    reports = AuditReportLog(tmp_path / "subset-reports.jsonl", consumed)
    audit_sampled_reruns(
        covered.rows,
        ring,
        rerun=_echo,
        consumed=consumed,
        reports=reports,
    )
    with pytest.raises(RewardRecordError, match="did not cover"):
        rl_batch_from_records(
            covered.headers + left.headers,
            covered.rows + left.rows,
            keyring=ring,
            expected_run_id=RUN,
            policy_checkpoints=(CHECKPOINT,),
            queue=QuarantineQueue(tmp_path / "q-both.jsonl"),
            rates=UngradedRateTracker(),
            consumed=consumed,
            reports=reports,
        )
    with pytest.raises(RewardRecordError, match="did not cover"):
        rl_batch_from_records(
            left.headers,
            left.rows,
            keyring=ring,
            expected_run_id=RUN,
            policy_checkpoints=(CHECKPOINT,),
            queue=QuarantineQueue(tmp_path / "q-canary.jsonl"),
            rates=UngradedRateTracker(),
            consumed=consumed,
            reports=reports,
        )
    admitted = rl_batch_from_records(
        covered.headers,
        covered.rows,
        keyring=ring,
        expected_run_id=RUN,
        policy_checkpoints=(CHECKPOINT,),
        queue=QuarantineQueue(tmp_path / "q-covered.jsonl"),
        rates=UngradedRateTracker(),
        consumed=consumed,
        reports=reports,
    )
    assert admitted.rows[0]["example_id"] == covered.rows[0].record_id


def test_an_unsampled_fail_in_the_covered_set_trains_at_zero(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    ring = RewardKeyring(secret, run_id=RUN)
    members = []
    for index in range(21):
        source = f"process = {index};".encode()
        members.append(("signal", "fail", _signal(source, passed=False), source))
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-unsampled",
        members=members,
    )
    log = tmp_path / "unsampled.jsonl"
    _store(log, header, rows)
    loaded = load_records(log, ring)
    consumed = ConsumedLog(tmp_path / "unsampled-consumed.jsonl")
    reports = AuditReportLog(tmp_path / "unsampled-reports.jsonl", consumed)
    audit = audit_sampled_reruns(loaded.rows, ring, rerun=_echo, consumed=consumed, reports=reports)
    assert len(audit.sample_ids) == 2
    left_out = [row.record_id for row in loaded.rows if row.record_id not in audit.audited_ids]
    assert len(left_out) == 19
    batch = rl_batch_from_records(
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
    assert batch.drops == ()
    rewards = {row["example_id"]: row["reward"] for row in batch.rows}
    assert len(rewards) == 21
    assert all(rewards[record_id] == 0.0 for record_id in left_out)


def test_a_mismatched_consumed_log_is_refused(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    ring = RewardKeyring(secret, run_id=RUN)
    loaded = _stored_pass(tmp_path, secret, "group-bound")
    bound = ConsumedLog(tmp_path / "bound-consumed.jsonl")
    reports = AuditReportLog(tmp_path / "bound-reports.jsonl", bound)
    audit_sampled_reruns(loaded.rows, ring, rerun=_echo, consumed=bound, reports=reports)
    other = ConsumedLog(tmp_path / "other-consumed.jsonl")
    rebound = AuditReportLog(reports.path, other)
    with pytest.raises(RewardRecordError, match="consumed log"):
        rl_batch_from_records(
            loaded.headers,
            loaded.rows,
            keyring=ring,
            expected_run_id=RUN,
            policy_checkpoints=(CHECKPOINT,),
            queue=QuarantineQueue(tmp_path / "q.jsonl"),
            rates=UngradedRateTracker(),
            consumed=other,
            reports=rebound,
        )
    assert other.disposition("group-bound") is None


def test_truncating_the_report_does_not_restore_a_clear_line(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    ring = RewardKeyring(secret, run_id=RUN)
    first = _stored_pass(tmp_path, secret, "group-first")
    second = _stored_pass(tmp_path, secret, "group-second")
    consumed = ConsumedLog(tmp_path / "chain-consumed.jsonl")
    reports = AuditReportLog(tmp_path / "chain-reports.jsonl", consumed)
    audit_sampled_reruns(first.rows, ring, rerun=_echo, consumed=consumed, reports=reports)
    audit_sampled_reruns(
        second.rows,
        ring,
        rerun=lambda _record: "fail",
        consumed=consumed,
        reports=reports,
    )
    assert p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed) is False
    data = reports.path.read_bytes()
    prefix, _newline, _rest = data.partition(b"\n")
    reports.path.write_bytes(prefix + b"\n")
    with pytest.raises(RewardRecordError, match="rolled back"):
        p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed)
    with pytest.raises(RewardRecordError, match="rolled back"):
        rl_batch_from_records(
            first.headers,
            first.rows,
            keyring=ring,
            expected_run_id=RUN,
            policy_checkpoints=(CHECKPOINT,),
            queue=QuarantineQueue(tmp_path / "q.jsonl"),
            rates=UngradedRateTracker(),
            consumed=consumed,
            reports=reports,
        )


def test_a_tampered_report_body_fails_the_gate_mac(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    loaded = _stored_pass(tmp_path, secret, "group-body")
    consumed = ConsumedLog(tmp_path / "body-consumed.jsonl")
    reports = AuditReportLog(tmp_path / "body-reports.jsonl", consumed)
    ring = RewardKeyring(secret, run_id=RUN)
    audit_sampled_reruns(loaded.rows, ring, rerun=_echo, consumed=consumed, reports=reports)
    text = reports.path.read_text(encoding="utf-8")
    marker = '"seed":"'
    start = text.index(marker) + len(marker)
    flipped = list(text)
    flipped[start + 63] = "0" if flipped[start + 63] != "0" else "1"
    reports.path.write_text("".join(flipped), encoding="utf-8")
    with pytest.raises(RewardRecordError, match="mac"):
        p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed)


def test_audit_seed_vector_includes_the_run_id() -> None:
    """HMAC-SHA256(run key, b"d3-h2-seed" || run id). Root key is bytes 0..31."""
    ring = RewardKeyring(bytes(range(32)), run_id="run-1")
    assert (
        derive_audit_seed(ring, "run-1")
        == "7f0914a7117db5905cf37c32a6a16780bcd8e1a022f642c97e4bbdb9aeaf235e"
    )


def _resign(line: str, run_key: bytes, **updates: object) -> str:
    body = loads_strict(line)
    assert isinstance(body, dict)
    body.pop("mac", None)
    body.update(updates)
    body["mac"] = _line_mac(run_key, body)
    return canonical_bytes(body).decode("ascii")


def _anchor_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    start = data.find(b"audit-anchor v1 ")
    assert start >= 0
    return data[start : start + 248]


def _clear_then_halt(tmp_path: Path, secret: bytes, name: str):
    ring = RewardKeyring(secret, run_id=RUN)
    first = _stored_pass(tmp_path, secret, f"{name}-first")
    second = _stored_pass(tmp_path, secret, f"{name}-second")
    consumed = ConsumedLog(tmp_path / f"{name}-consumed.jsonl")
    reports = AuditReportLog(tmp_path / f"{name}-reports.jsonl", consumed)
    audit_sampled_reruns(first.rows, ring, rerun=_echo, consumed=consumed, reports=reports)
    saved = _anchor_bytes(consumed.path)
    audit_sampled_reruns(
        second.rows,
        ring,
        rerun=lambda _record: "fail",
        consumed=consumed,
        reports=reports,
    )
    return ring, first, second, consumed, reports, saved


def test_a_broken_chain_link_is_refused(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    ring, _first, _second, consumed, reports, _saved = _clear_then_halt(tmp_path, secret, "link")
    run_key = derive_run_key(secret, RUN)
    lines = reports.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    broken_prev = _resign(lines[1], run_key, prev="0" * 64)
    reports.path.write_text(lines[0] + "\n" + broken_prev + "\n", encoding="utf-8")
    with pytest.raises(RewardRecordError, match="chain"):
        p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed)
    first_body = loads_strict(lines[0])
    assert isinstance(first_body, dict)
    broken_seq = _resign(lines[1], run_key, seq=1, prev=first_body["mac"])
    reports.path.write_text(lines[0] + "\n" + broken_seq + "\n", encoding="utf-8")
    with pytest.raises(RewardRecordError, match="chain"):
        p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed)


def test_a_boolean_sequence_is_refused(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    ring = RewardKeyring(secret, run_id=RUN)
    loaded = _stored_pass(tmp_path, secret, "group-seq")
    consumed = ConsumedLog(tmp_path / "seq-consumed.jsonl")
    reports = AuditReportLog(tmp_path / "seq-reports.jsonl", consumed)
    audit_sampled_reruns(loaded.rows, ring, rerun=_echo, consumed=consumed, reports=reports)
    run_key = derive_run_key(secret, RUN)
    line = reports.path.read_text(encoding="utf-8").splitlines()[0]
    reports.path.write_text(_resign(line, run_key, seq=True) + "\n", encoding="utf-8")
    with pytest.raises(RewardRecordError, match="sequence"):
        p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed)


def test_a_new_chain_is_refused_while_an_anchor_exists(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    ring = RewardKeyring(secret, run_id=RUN)
    loaded = _stored_pass(tmp_path, secret, "group-anchor-stays")
    consumed = ConsumedLog(tmp_path / "stay-consumed.jsonl")
    reports = AuditReportLog(tmp_path / "stay-reports.jsonl", consumed)
    audit_sampled_reruns(loaded.rows, ring, rerun=_echo, consumed=consumed, reports=reports)
    reports.path.write_bytes(b"")
    with pytest.raises(RewardRecordError, match="rolled back"):
        audit_sampled_reruns(loaded.rows, ring, rerun=_echo, consumed=consumed, reports=reports)
    assert reports.path.read_bytes() == b""


def test_append_refuses_a_tail_behind_the_anchor(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    ring, _first, _second, consumed, reports, _saved = _clear_then_halt(tmp_path, secret, "behind")
    data = reports.path.read_bytes()
    prefix, _newline, _rest = data.partition(b"\n")
    reports.path.write_bytes(prefix + b"\n")
    fresh = _stored_pass(tmp_path, secret, "behind-fresh")
    with pytest.raises(RewardRecordError, match="rolled back"):
        audit_sampled_reruns(fresh.rows, ring, rerun=_echo, consumed=consumed, reports=reports)
    assert reports.path.read_bytes() == prefix + b"\n"


def test_a_tampered_anchor_mac_is_refused(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    ring = RewardKeyring(secret, run_id=RUN)
    loaded = _stored_pass(tmp_path, secret, "group-bind")
    consumed = ConsumedLog(tmp_path / "bind-consumed.jsonl")
    reports = AuditReportLog(tmp_path / "bind-reports.jsonl", consumed)
    audit_sampled_reruns(loaded.rows, ring, rerun=_echo, consumed=consumed, reports=reports)
    data = bytearray(consumed.path.read_bytes())
    start = data.find(b"audit-anchor v1 ")
    bind_at = start + 183
    data[bind_at] = ord("0") if data[bind_at] != ord("0") else ord("1")
    consumed.path.write_bytes(bytes(data))
    with pytest.raises(RewardRecordError, match="anchor"):
        p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed)


def test_an_old_anchor_spliced_over_new_claims_is_refused(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    ring, _first, _second, consumed, reports, saved = _clear_then_halt(tmp_path, secret, "splice")
    data = consumed.path.read_bytes()
    start = data.find(b"audit-anchor v1 ")
    assert data[start : start + 248] != saved
    consumed.path.write_bytes(data[:start] + saved + data[start + 248 :])
    report = reports.path.read_bytes()
    prefix, _newline, _rest = report.partition(b"\n")
    reports.path.write_bytes(prefix + b"\n")
    with pytest.raises(RewardRecordError, match="anchor"):
        p3_may_proceed(RUN, keyring=ring, reports=reports, consumed=consumed)


def test_deleting_the_report_and_anchor_does_not_allow_a_new_audit(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    ring = RewardKeyring(secret, run_id=RUN)
    loaded = _stored_pass(tmp_path, secret, "group-deleted")
    consumed = ConsumedLog(tmp_path / "deleted-consumed.jsonl")
    reports = AuditReportLog(tmp_path / "deleted-reports.jsonl", consumed)
    audit_sampled_reruns(
        loaded.rows,
        ring,
        rerun=lambda _record: "fail",
        consumed=consumed,
        reports=reports,
    )
    assert consumed.disposition("group-deleted") == "dropped:audit"
    kept = [
        line
        for line in consumed.path.read_text(encoding="utf-8").splitlines()
        if not line.startswith("audit-anchor v1 ")
    ]
    consumed.path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    reports.path.unlink()
    with pytest.raises(RewardRecordError, match="rolled back"):
        audit_sampled_reruns(loaded.rows, ring, rerun=_echo, consumed=consumed, reports=reports)
    assert reports.path.read_bytes() == b""


def test_canary_must_be_a_bool_when_the_mac_is_valid(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    ring = RewardKeyring(secret, run_id=RUN)
    source = b"process = _;"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-bool",
        members=[("signal", "pass", _signal(source, passed=True), source)],
    )
    run_key = derive_run_key(secret, RUN)
    for name, value in (("int", 1), ("text", "true")):
        forged = replace(rows[0], canary=value)
        forged = replace(
            forged,
            record_id=hashlib.sha256(canonical_bytes(forged.identity_body())).hexdigest(),
        )
        forged = replace(forged, mac=mac(forged, run_key))
        verify(forged, ring)
        log = tmp_path / f"{name}.jsonl"
        _store(log, header, [forged])
        with pytest.raises(RewardRecordError, match="canary"):
            load_records(log, ring)

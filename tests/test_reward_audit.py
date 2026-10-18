"""D3-H2: sampled rerun-from-source audit before P3."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from faustcoder.reward.audit import audit_sampled_reruns, p3_may_proceed, select_fail_sample
from faustcoder.reward.records import ConsumedLog, RewardKeyring, RewardRecordError
from tests.test_reward_records import CHECKPOINT, HARNESS, RUN, _members, _signal, _write_key


@pytest.fixture(autouse=True)
def _pin_harness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "faustcoder.reward.records.current_harness_digest",
        lambda: HARNESS,
    )


def _rows(secret: bytes, group_id: str, members: list[tuple[str, str, dict, bytes]]):
    _header, rows = _members(secret, run_id=RUN, group_id=group_id, members=members)
    return tuple(rows)


def _audit(tmp_path: Path, secret: bytes, rows, rerun, *, seed: str, canary_ids=()):
    consumed_path = tmp_path / f"consumed-{seed}.jsonl"
    audit = audit_sampled_reruns(
        rows,
        RewardKeyring(secret, run_id=RUN),
        seed=seed,
        rerun=rerun,
        consumed=ConsumedLog(consumed_path),
        canary_ids=canary_ids,
    )
    return audit, consumed_path


def test_agreement_passes(tmp_path: Path) -> None:
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

    audit, path = _audit(tmp_path, secret, rows, rerun, seed="seed-agree")
    assert audit.halted is False
    assert audit.report()["p3"] == "clear"
    assert audit.report()["seed"] == "seed-agree"
    assert p3_may_proceed(audit) is True
    assert ConsumedLog(path).disposition(rows[0].group_id) is None
    assert not path.exists()
    assert rows[0].outcome == "pass"
    assert seen == [source]
    assert rows[0].record_id in audit.audited_ids


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
    audit, path = _audit(
        tmp_path,
        secret,
        rows,
        lambda _record: "fail",
        seed="seed-flip",
    )
    report = audit.report()
    assert audit.halted is True
    assert report["p3"] == "halt"
    assert p3_may_proceed(audit) is False
    assert audit.dropped_groups == ("group-flip",)
    assert audit.sample_ids == ()
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
    assert ConsumedLog(path).disposition("group-flip") == "dropped:audit"
    before = path.stat().st_size
    with pytest.raises(RewardRecordError, match="already consumed"):
        ConsumedLog(path).claim(
            "group-flip",
            "used",
            task_digest_full=rows[0].task_digest_full,
            policy_checkpoint=CHECKPOINT,
        )
    assert path.stat().st_size == before
    repeat = audit_sampled_reruns(
        rows,
        RewardKeyring(secret, run_id=RUN),
        seed="seed-flip",
        rerun=lambda _record: "fail",
        consumed=ConsumedLog(path),
    )
    assert repeat.halted is True
    assert repeat.dropped_groups == ("group-flip",)
    assert path.stat().st_size == before


def test_sampled_fail_that_passes_on_rerun_halts(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    members = []
    for index in range(20):
        source = f"process = {index};".encode()
        members.append(("signal", "fail", _signal(source, passed=False), source))
    rows = _rows(secret, "group-sample", members)
    audit, path = _audit(
        tmp_path,
        secret,
        rows,
        lambda _record: "pass",
        seed="seed-sample",
    )
    assert len(audit.sample_ids) == 1
    assert audit.sample_ids[0] in {row.record_id for row in rows}
    assert audit.halted is True
    assert audit.report()["p3"] == "halt"
    assert audit.dropped_groups == ("group-sample",)
    assert audit.disagreements[0].record_id == audit.sample_ids[0]
    assert audit.disagreements[0].stored_outcome == "fail"
    assert audit.disagreements[0].rerun_outcome == "pass"
    stored = next(row for row in rows if row.record_id == audit.sample_ids[0])
    assert stored.outcome == "fail"
    assert ConsumedLog(path).disposition("group-sample") == "dropped:audit"
    assert p3_may_proceed(audit) is False


def test_canary_disagreement_halts(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = +;"
    rows = _rows(
        secret,
        "group-canary",
        [("signal", "fail", _signal(source, passed=False), source)],
    )
    assert select_fail_sample([rows[0].record_id], "seed-canary") == ()
    audit, path = _audit(
        tmp_path,
        secret,
        rows,
        lambda _record: "pass",
        seed="seed-canary",
        canary_ids={rows[0].record_id},
    )
    assert audit.sample_ids == ()
    assert rows[0].record_id in audit.audited_ids
    assert audit.halted is True
    assert audit.report()["p3"] == "halt"
    assert audit.disagreements[0].stored_outcome == "fail"
    assert audit.disagreements[0].rerun_outcome == "pass"
    assert audit.dropped_groups == ("group-canary",)
    assert rows[0].outcome == "fail"
    assert ConsumedLog(path).disposition("group-canary") == "dropped:audit"


def test_sample_is_reproducible_from_its_seed(tmp_path: Path) -> None:
    ids = [f"id-{index:02d}" for index in range(40)]
    first = select_fail_sample(ids, "seed-a")
    assert first == select_fail_sample(list(reversed(ids)), "seed-a")
    assert first == select_fail_sample(ids + list(ids), "seed-a")
    assert len(first) == (40 * 5) // 100
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

    def agree(record):
        return record.outcome

    forward, _forward_path = _audit(tmp_path, secret, rows, agree, seed="seed-repro")
    backward, _backward_path = _audit(
        tmp_path,
        secret,
        tuple(reversed(rows)),
        agree,
        seed="seed-repro",
    )
    assert forward.sample_ids == backward.sample_ids
    assert len(forward.sample_ids) == 1
    assert forward.halted is False
    assert forward.report()["sample_ids"] == list(forward.sample_ids)
    assert forward.report()["seed"] == "seed-repro"


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

    def rerun(record):
        called.append(record.record_id)
        return record.outcome

    path = tmp_path / "consumed-mac.jsonl"
    with pytest.raises(RewardRecordError, match="HMAC"):
        audit_sampled_reruns(
            [bad],
            RewardKeyring(secret, run_id=RUN),
            seed="seed-mac",
            rerun=rerun,
            consumed=ConsumedLog(path),
        )
    assert called == []
    assert not path.exists()
    assert bad.outcome == "pass"
    assert rows[0].outcome == "pass"

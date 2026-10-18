"""D3 option H: MAC'd reward rows, group drops, and the key file."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import signal
import stat
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from faustcoder import build_envelope
from faustcoder.reward.grader import (
    is_minted,
    task_binding_digest,
    task_digest_full,
)
from faustcoder.reward.ledger import RewardLedger
from faustcoder.canonical import canonical_bytes
from faustcoder.reward.records import (
    ConsumedLog,
    RewardKeyError,
    RewardKeyring,
    RewardRecordError,
    RewardRecordStore,
    _binding_failed,
    derive_run_key,
    load_records,
    load_root_key,
    outcome_for,
    regrade_record,
    rl_batch_from_records,
    sign_group_header,
    sign_reward_row,
    verify,
)
from faustcoder.reward.types import (
    QuarantineQueue,
    RewardableSignalReceipt,
    SourceAttributedFailure,
    TriageAttribution,
    Ungraded,
    UngradedRateTracker,
    UngradedReason,
)
from tests.support import (
    allowlisted_reward_envelope,
    compiler_failure_envelope,
    make_envelope,
)

HARNESS = "sha256:" + "cd" * 32
CHECKPOINT = "sha256:" + "11" * 32
STAMP = "2026-10-18T00:00:00Z"
RUN = "run-1"
_CLAIM_KEY = bytes(range(32))
ROLLOUT = "rollout-1"


def _task() -> dict:
    path = Path(__file__).resolve().parents[1] / "tests/fixtures/valid/task-spec.json"
    task = json.loads(path.read_text(encoding="utf-8"))
    assert task["effect"] == "linear"
    return task


def _write_key(path: Path, key: bytes | None = None) -> bytes:
    secret = os.urandom(32) if key is None else key
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o400)
    try:
        os.write(fd, secret)
    finally:
        os.close(fd)
    os.chmod(path, 0o400)
    return secret


def _leaked(blob: str, key: bytes) -> bool:
    return key.hex() in blob


def _signal(source: bytes, *, passed: bool, failures: list[str] | None = None) -> dict:
    digest = hashlib.sha256(source).hexdigest()

    def mutate(payload: dict) -> None:
        payload["source_sha256"] = digest
        payload["harness_digest"] = HARNESS
        if failures is not None:
            payload["passed"] = passed
            payload["metrics"]["failures"] = list(failures)

    return allowlisted_reward_envelope(passed=passed, mutate=mutate)


def _compiler(source: bytes, *, exit_code: int, diagnostic_class: str, diagnostics: str) -> dict:
    envelope = compiler_failure_envelope(
        exit_code=exit_code,
        diagnostic_class=diagnostic_class,
        diagnostics=diagnostics,
    )
    payload = dict(envelope["payload"])
    payload["source_sha256"] = hashlib.sha256(source).hexdigest()
    return make_envelope(payload, schema_version="0.3.2", producer="faustcoder.compiler")


def _members(
    root: bytes,
    *,
    run_id: str,
    group_id: str,
    members: list[tuple[str, str, dict, bytes]],
    task: dict | None = None,
    canaries: tuple[int, ...] = (),
):
    bound = _task() if task is None else task
    run_key = derive_run_key(root, run_id)
    marked = set(canaries)
    header = sign_group_header(
        group_id=group_id,
        task_digest_full=task_digest_full(bound),
        group_size=len(members),
        run_id=run_id,
        run_key=run_key,
    )
    rows = []
    for index, (kind, outcome, envelope, source) in enumerate(members):
        rows.append(
            sign_reward_row(
                run_key=run_key,
                run_id=run_id,
                rollout_id=ROLLOUT,
                policy_checkpoint=CHECKPOINT,
                group_id=group_id,
                group_size=len(members),
                member_index=index,
                source=source,
                task=bound,
                envelope=envelope,
                outcome=outcome,
                kind=kind,
                graded_at=STAMP,
                canary=index in marked,
            )
        )
    return header, rows


def _store(path: Path, header, rows) -> None:
    store = RewardRecordStore(path)
    store.append_header(header)
    for row in rows:
        store.append_row(row)


def _batch(
    path: Path,
    root: bytes,
    queue: QuarantineQueue,
    consumed: ConsumedLog,
    rates,
    *,
    run_id: str = RUN,
    checkpoints: tuple[str, ...] = (CHECKPOINT,),
):
    from faustcoder.reward.audit import AuditReportLog, audit_sampled_reruns

    ring = RewardKeyring(root, run_id=run_id)
    loaded = load_records(path, ring)
    reports = AuditReportLog(
        consumed.path.with_name(consumed.path.name + ".audit.jsonl"),
        consumed,
    )
    if not reports.path.is_file():
        audit_sampled_reruns(
            loaded.rows,
            ring,
            rerun=lambda record: record.outcome,
            consumed=consumed,
            reports=reports,
        )
    return rl_batch_from_records(
        loaded.headers,
        loaded.rows,
        keyring=ring,
        expected_run_id=run_id,
        policy_checkpoints=checkpoints,
        queue=queue,
        rates=rates,
        consumed=consumed,
        reports=reports,
    )


@pytest.fixture(autouse=True)
def _pin_harness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "faustcoder.reward.records.current_harness_digest",
        lambda: HARNESS,
    )


def test_root_key_file_is_refused_unless_it_is_private(tmp_path: Path) -> None:
    key_path = tmp_path / "reward-root.key"
    secret = _write_key(key_path)
    uid = os.getuid()
    assert load_root_key(key_path, grader_uid=uid) == secret
    os.chmod(key_path, 0o644)
    with pytest.raises(RewardKeyError, match="0400") as wide:
        load_root_key(key_path, grader_uid=uid)
    assert not _leaked(str(wide.value), secret)
    os.chmod(key_path, 0o600)
    with pytest.raises(RewardKeyError, match="0400"):
        load_root_key(key_path, grader_uid=uid)
    os.chmod(key_path, 0o400)
    with pytest.raises(RewardKeyError, match="grader uid"):
        load_root_key(key_path, grader_uid=uid + 1)
    link = tmp_path / "linked.key"
    link.symlink_to(key_path)
    with pytest.raises(RewardKeyError, match="cannot be opened"):
        load_root_key(link, grader_uid=uid)
    short = tmp_path / "short.key"
    _write_key(short, b"\x01" * 16)
    with pytest.raises(RewardKeyError, match="32 bytes"):
        load_root_key(short, grader_uid=uid)
    ring_a = RewardKeyring(secret, run_id="run-a")
    ring_b = RewardKeyring(secret, run_id="run-b")
    assert repr(ring_a) == "RewardKeyring(redacted)"
    assert not _leaked(repr(ring_a), secret)
    assert secret not in vars(ring_a).values()
    assert ring_a.key_id("run-a") == ring_a.key_id("run-a")
    assert ring_a.key_id("run-a") != ring_b.key_id("run-b")
    with pytest.raises(RewardKeyError, match="keyring"):
        ring_a.key_id("run-b")
    with pytest.raises(RewardKeyError, match="serialized") as pickled:
        pickle.dumps(ring_a)
    assert not _leaked(str(pickled.value), secret)
    with pytest.raises(RewardKeyError, match="grader uid"):
        load_root_key(key_path, grader_uid=0)
    os.chmod(tmp_path, 0o777)
    with pytest.raises(RewardKeyError, match="directory"):
        load_root_key(key_path, grader_uid=uid)
    os.chmod(tmp_path, 0o700)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(RewardKeyError, match="directory"):
        load_root_key(linked_parent / key_path.name, grader_uid=uid)
    grand = tmp_path / "grand"
    grand.mkdir(mode=0o700)
    nested = grand / "nested"
    nested.mkdir(mode=0o700)
    nested_key = nested / "reward-root.key"
    _write_key(nested_key, secret)
    grand_link = tmp_path / "grand-link"
    grand_link.symlink_to(grand, target_is_directory=True)
    with pytest.raises(RewardKeyError, match="directory"):
        load_root_key(grand_link / "nested" / nested_key.name, grader_uid=uid)
    assert load_root_key(nested_key, grader_uid=uid) == secret
    for raised in (
        lambda: RewardKeyring(secret, run_id="bad id"),
        lambda: derive_run_key(secret, "bad id"),
    ):
        try:
            raised()
        except RewardKeyError as exc:
            frame = exc.__traceback__
            saw_library = False
            while frame is not None:
                filename = frame.tb_frame.f_code.co_filename
                if filename.endswith("faustcoder/reward/records.py"):
                    saw_library = True
                    assert secret not in frame.tb_frame.f_locals.values()
                frame = frame.tb_next
            assert saw_library
        else:
            raise AssertionError("a bad run id was accepted")
    fifo = tmp_path / "key.fifo"
    os.mkfifo(fifo)
    with pytest.raises(RewardKeyError, match="regular"):
        load_root_key(fifo, grader_uid=uid)


def test_fresh_process_restart_keeps_a_passing_group(tmp_path: Path) -> None:
    key_path = tmp_path / "reward-root.key"
    secret = _write_key(key_path)
    log = tmp_path / "rows.jsonl"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.test_reward_records",
            "fresh",
            str(log),
            str(key_path),
            HARNESS,
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert not _leaked(completed.stdout + completed.stderr, secret)
    batch = _batch(
        log,
        secret,
        QuarantineQueue(tmp_path / "q.jsonl"),
        ConsumedLog(tmp_path / "consumed.jsonl"),
        UngradedRateTracker(),
    )
    assert len(batch.rows) == 1
    assert batch.rows[0]["reward"] == 1.0
    assert batch.drops == ()
    assert isinstance(batch.rows[0]["provenance"], RewardableSignalReceipt)
    assert is_minted(batch.rows[0]["provenance"])
    text = log.read_text(encoding="utf-8")
    assert not _leaked(text, secret)


def test_passed_flip_with_recomputed_digests_is_refused(tmp_path: Path) -> None:
    from faustcoder.reward.grader import grade_receipt

    source = b"process = _;"
    honest = _signal(source, passed=False)
    lying_payload = dict(honest["payload"])
    lying_payload["passed"] = True
    lying_payload["metrics"] = dict(lying_payload["metrics"])
    lying_payload["metrics"]["failures"] = ["impulse:reference"]
    lying = build_envelope(
        schema_version=honest["schema_version"],
        created_at=honest["created_at"],
        producer=honest["producer"],
        parents=honest["parents"],
        payload=lying_payload,
    )
    graded = grade_receipt(lying, task=_task())
    assert isinstance(graded, Ungraded)
    assert graded.reason is UngradedReason.DIGEST_MISMATCH
    assert "failures" in graded.detail

    key_path = tmp_path / "reward-root.key"
    secret = _write_key(key_path)
    log = tmp_path / "rows.jsonl"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-flip",
        members=[("signal", "fail", honest, source)],
    )
    _store(log, header, rows)
    tampered = _rewrite_envelope(log, lying)
    with pytest.raises(RewardRecordError, match="mac does not verify"):
        load_records(tampered, RewardKeyring(secret, run_id=RUN))

    with pytest.raises(RewardRecordError, match="failures"):
        _members(
            secret,
            run_id=RUN,
            group_id="group-resigned",
            members=[("signal", "pass", lying, source)],
        )


def test_duplicate_persisted_row_drops_the_group(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-dup",
        members=[("signal", "pass", _signal(source, passed=True), source)],
    )
    log = tmp_path / "rows.jsonl"
    store = RewardRecordStore(log)
    store.append_header(header)
    store.append_row(rows[0])
    store.append_row(rows[0])
    batch = _batch(
        log,
        secret,
        QuarantineQueue(tmp_path / "q.jsonl"),
        ConsumedLog(tmp_path / "consumed.jsonl"),
        UngradedRateTracker(),
    )
    assert batch.rows == ()
    assert batch.drops == (("group-dup", "duplicate"),)


def test_task_swap_leaves_the_mac_invalid(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-swap",
        members=[("signal", "pass", _signal(source, passed=True), source)],
    )
    log = tmp_path / "rows.jsonl"
    _store(log, header, rows)
    swapped = tmp_path / "swapped.jsonl"
    lines = []
    for line in log.read_text(encoding="utf-8").splitlines():
        body = json.loads(line)
        if body.get("type") == "reward_row":
            body["task"]["task_id"] = "task-swapped-linear"
            body["task_digest_full"] = task_digest_full(body["task"])
            body["task_binding_digest"] = task_binding_digest(body["task"])
        lines.append(json.dumps(body, separators=(",", ":"), sort_keys=True))
    swapped.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(RewardRecordError, match="mac does not verify"):
        load_records(swapped, RewardKeyring(secret, run_id=RUN))


def test_stale_harness_pin_is_not_regraded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-stale",
        members=[("signal", "pass", _signal(source, passed=True), source)],
    )
    log = tmp_path / "rows.jsonl"
    _store(log, header, rows)
    calls: list[dict] = []
    real = __import__("faustcoder.reward.records", fromlist=["grade_receipt"]).grade_receipt

    def spy(*args, **kwargs):
        calls.append(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr("faustcoder.reward.records.grade_receipt", spy)
    monkeypatch.setattr(
        "faustcoder.reward.records.current_harness_digest",
        lambda: "sha256:" + "ee" * 32,
    )
    batch = _batch(
        log,
        secret,
        QuarantineQueue(tmp_path / "q.jsonl"),
        ConsumedLog(tmp_path / "consumed.jsonl"),
        UngradedRateTracker(),
    )
    assert calls == []
    assert batch.rows == ()
    assert batch.drops == (("group-stale", "stale_pin"),)
    again = ConsumedLog(tmp_path / "consumed.jsonl")
    assert again.disposition("group-stale") == "dropped:stale_pin"
    with pytest.raises(RewardRecordError, match="already consumed"):
        _batch(
            log,
            secret,
            QuarantineQueue(tmp_path / "q.jsonl"),
            again,
            UngradedRateTracker(),
        )


def test_regrade_does_not_rerun_or_triage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-spy",
        members=[("signal", "pass", _signal(source, passed=True), source)],
    )
    log = tmp_path / "rows.jsonl"
    _store(log, header, rows)
    calls: list[dict] = []
    real = __import__("faustcoder.reward.records", fromlist=["grade_receipt"]).grade_receipt

    def spy(*args, **kwargs):
        calls.append(dict(kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr("faustcoder.reward.records.grade_receipt", spy)
    batch = _batch(
        log,
        secret,
        QuarantineQueue(tmp_path / "q.jsonl"),
        ConsumedLog(tmp_path / "consumed.jsonl"),
        UngradedRateTracker(),
    )
    assert batch.rows[0]["reward"] == 1.0
    assert calls
    for kwargs in calls:
        assert "rerun" not in kwargs
        assert "known_good" not in kwargs
        assert "triage" not in kwargs


def test_quarantine_blocks_a_g1_rewrite_after_restart(tmp_path: Path) -> None:
    key_path = tmp_path / "reward-root.key"
    secret = _write_key(key_path)
    passing = b"process = _;"
    failing = b"process = +;"
    timeout = _compiler(
        failing,
        exit_code=124,
        diagnostic_class="timeout",
        diagnostics="timeout: wall clock limit exceeded\n",
    )
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-q",
        members=[
            ("signal", "pass", _signal(passing, passed=True), passing),
            ("compiler", "ungraded:unattributed", timeout, failing),
        ],
    )
    original = tmp_path / "original.jsonl"
    _store(original, header, rows)
    queue_path = tmp_path / "q.jsonl"
    first = _batch(
        original,
        secret,
        QuarantineQueue(queue_path),
        ConsumedLog(tmp_path / "consumed-a.jsonl"),
        UngradedRateTracker(),
    )
    assert first.rows == ()
    assert first.drops == (("group-q", "quarantined"),)
    held = QuarantineQueue(queue_path)
    assert any(item.group_id == "group-q" and item.row_record_id for item in held.pending())

    slim_header, slim_rows = _members(
        secret,
        run_id=RUN,
        group_id="group-q",
        members=[("signal", "pass", _signal(passing, passed=True), passing)],
    )
    slim = tmp_path / "g1.jsonl"
    _store(slim, slim_header, slim_rows)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.test_reward_records",
            "g1",
            str(slim),
            str(key_path),
            HARNESS,
            str(queue_path),
            str(tmp_path / "consumed-b.jsonl"),
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "rows=0;drop=quarantined"
    assert not _leaked(completed.stdout + completed.stderr, secret)


def test_a1_member_is_kept_at_zero(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    good = b"process = _;"
    bad = b"process = +"
    parse = _compiler(
        bad,
        exit_code=1,
        diagnostic_class="parse_error",
        diagnostics="parse error\n",
    )
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-a1",
        members=[
            ("signal", "pass", _signal(good, passed=True), good),
            ("compiler", "source_attributed", parse, bad),
        ],
    )
    log = tmp_path / "a1.jsonl"
    _store(log, header, rows)
    batch = _batch(
        log,
        secret,
        QuarantineQueue(tmp_path / "q.jsonl"),
        ConsumedLog(tmp_path / "consumed.jsonl"),
        UngradedRateTracker(),
    )
    assert [row["reward"] for row in batch.rows] == [1.0, 0.0]
    assert isinstance(batch.rows[1]["provenance"], SourceAttributedFailure)
    assert batch.drops == ()


def _native_stack_receipt(source_sha256: str, diagnostics: str) -> dict:
    return {
        "source_sha256": source_sha256,
        "faust_version": "2.88.0",
        "command": ["faust", "-lang", "cpp"],
        "exit_code": 1,
        "stdout_digest": "sha256:" + "00" * 32,
        "stderr_digest": "sha256:" + hashlib.sha256(diagnostics.encode("utf-8")).hexdigest(),
        "duration_ms": 1,
        "environment_digest": "sha256:" + "22" * 32,
        "compiler": "faust-cli",
        "lang": "cpp",
        "options": [],
        "diagnostic_class": "parse_error",
    }


def _signed_row(
    secret: bytes,
    *,
    group_id: str,
    source: bytes,
    envelope: dict,
    outcome: str,
    kind: str,
    native_envelope: dict | None = None,
    diagnostics: str = "",
    native_diagnostics: str = "",
):
    run_key = derive_run_key(secret, RUN)
    header = sign_group_header(
        group_id=group_id,
        task_digest_full=task_digest_full(_task()),
        group_size=1,
        run_id=RUN,
        run_key=run_key,
    )
    row = sign_reward_row(
        run_key=run_key,
        run_id=RUN,
        rollout_id=ROLLOUT,
        policy_checkpoint=CHECKPOINT,
        group_id=group_id,
        group_size=1,
        member_index=0,
        source=source,
        task=_task(),
        envelope=envelope,
        outcome=outcome,
        kind=kind,
        graded_at=STAMP,
        native_envelope=native_envelope,
        diagnostics=diagnostics,
        native_diagnostics=native_diagnostics,
    )
    return header, row


def test_regrade_keeps_a_native_stack_source_failure(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = +;"
    diagnostics = "ERROR : stack overflow in eval\n"
    envelope = _compiler(
        source,
        exit_code=126,
        diagnostic_class="internal",
        diagnostics=diagnostics,
    )
    native = _native_stack_receipt(envelope["payload"]["source_sha256"], diagnostics)
    header, row = _signed_row(
        secret,
        group_id="group-stack",
        source=source,
        envelope=envelope,
        outcome="source_attributed",
        kind="compiler",
        native_envelope=native,
        diagnostics=diagnostics,
        native_diagnostics=diagnostics,
    )
    log = tmp_path / "stack.jsonl"
    _store(log, header, [row])
    loaded = load_records(log, RewardKeyring(secret, run_id=RUN))
    assert loaded.checks[0].reason == ""
    assert isinstance(loaded.checks[0].grade, SourceAttributedFailure)
    assert loaded.checks[0].grade.detail == "stack overflow"
    batch = _batch(
        log,
        secret,
        QuarantineQueue(tmp_path / "q.jsonl"),
        ConsumedLog(tmp_path / "consumed.jsonl"),
        UngradedRateTracker(),
    )
    assert batch.drops == ()
    assert [item["reward"] for item in batch.rows] == [0.0]
    assert isinstance(batch.rows[0]["provenance"], SourceAttributedFailure)
    assert not isinstance(batch.rows[0]["provenance"], RewardableSignalReceipt)


def test_regrade_leaves_a_stack_row_ungraded_without_native_evidence(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = +;"
    diagnostics = "ERROR : stack overflow in eval\n"
    envelope = _compiler(
        source,
        exit_code=126,
        diagnostic_class="internal",
        diagnostics=diagnostics,
    )
    header, row = _signed_row(
        secret,
        group_id="group-bare-stack",
        source=source,
        envelope=envelope,
        outcome="source_attributed",
        kind="compiler",
    )
    log = tmp_path / "bare.jsonl"
    _store(log, header, [row])
    loaded = load_records(log, RewardKeyring(secret, run_id=RUN))
    assert loaded.checks[0].reason == "outcome"
    assert isinstance(loaded.checks[0].grade, Ungraded)
    assert not isinstance(loaded.checks[0].grade, RewardableSignalReceipt)
    batch = _batch(
        log,
        secret,
        QuarantineQueue(tmp_path / "q.jsonl"),
        ConsumedLog(tmp_path / "consumed.jsonl"),
        UngradedRateTracker(),
    )
    assert batch.rows == ()
    assert batch.drops == (("group-bare-stack", "outcome"),)


def test_regrade_does_not_flip_a_stored_pass_or_fail(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    good = b"process = _;"
    bad = b"process = +;"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-bits",
        members=[
            ("signal", "pass", _signal(good, passed=True), good),
            ("signal", "fail", _signal(bad, passed=False), bad),
        ],
    )
    honest = tmp_path / "bits.jsonl"
    _store(honest, header, rows)
    batch = _batch(
        honest,
        secret,
        QuarantineQueue(tmp_path / "q.jsonl"),
        ConsumedLog(tmp_path / "consumed.jsonl"),
        UngradedRateTracker(),
    )
    assert [item["reward"] for item in batch.rows] == [1.0, 0.0]
    assert batch.rows[0]["provenance"].passed is True
    assert batch.rows[1]["provenance"].passed is False
    lying_header, lying_row = _signed_row(
        secret,
        group_id="group-flipped",
        source=good,
        envelope=_signal(good, passed=True),
        outcome="fail",
        kind="signal",
    )
    lying = tmp_path / "flipped.jsonl"
    _store(lying, lying_header, [lying_row])
    loaded = load_records(lying, RewardKeyring(secret, run_id=RUN))
    assert loaded.checks[0].reason == "outcome"
    assert isinstance(loaded.checks[0].grade, Ungraded)
    flipped = _batch(
        lying,
        secret,
        QuarantineQueue(tmp_path / "q2.jsonl"),
        ConsumedLog(tmp_path / "consumed-2.jsonl"),
        UngradedRateTracker(),
    )
    assert flipped.rows == ()
    assert flipped.drops == (("group-flipped", "outcome"),)


def test_regrade_leaves_unreconstructed_native_evidence_ungraded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pins the guard after ``_reconstruct_native`` returns None.

    Deleting that guard unpacks None and raises. The stored outcome stays
    ``pass`` and the group does not train.
    """
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-reconstruct",
        members=[("signal", "pass", _signal(source, passed=True), source)],
    )
    record = rows[0]
    monkeypatch.setattr("faustcoder.reward.records._reconstruct_native", lambda _record: None)
    check = regrade_record(record, RewardKeyring(secret, run_id=RUN))
    assert check.reason == "outcome"
    assert isinstance(check.grade, Ungraded)
    assert check.grade.reason is UngradedReason.UNATTRIBUTED
    assert "reconstruct" in check.grade.detail
    assert record.outcome == "pass"
    log = tmp_path / "reconstruct.jsonl"
    _store(log, header, rows)
    batch = _batch(
        log,
        secret,
        QuarantineQueue(tmp_path / "q.jsonl"),
        ConsumedLog(tmp_path / "consumed.jsonl"),
        UngradedRateTracker(),
    )
    assert batch.rows == ()
    assert batch.drops == (("group-reconstruct", "outcome"),)


def test_training_rows_carry_the_signed_record_id(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-example",
        members=[("signal", "pass", _signal(source, passed=True), source)],
    )
    log = tmp_path / "example.jsonl"
    _store(log, header, rows)
    batch = _batch(
        log,
        secret,
        QuarantineQueue(tmp_path / "q.jsonl"),
        ConsumedLog(tmp_path / "consumed.jsonl"),
        UngradedRateTracker(),
    )
    assert len(batch.rows) == 1
    example_id = batch.rows[0]["example_id"]
    assert type(example_id) is str and example_id != ""
    assert example_id == rows[0].record_id
    assert batch.rows[0]["record_id"] == rows[0].record_id


def test_shadow_log_is_not_a_reward_row() -> None:
    from faustcoder.reward.grader import shadow_observe

    source = b"process = _;"
    envelope = _compiler(
        source,
        exit_code=124,
        diagnostic_class="timeout",
        diagnostics="timeout: wall clock limit exceeded\n",
    )
    with pytest.raises(RewardRecordError, match="shadow"):
        outcome_for(shadow_observe(envelope))
    secret = os.urandom(32)
    with pytest.raises(RewardRecordError, match="shadow"):
        sign_reward_row(
            run_key=derive_run_key(secret, RUN),
            run_id=RUN,
            rollout_id=ROLLOUT,
            policy_checkpoint=CHECKPOINT,
            group_id="group-shadow",
            group_size=1,
            member_index=0,
            source=source,
            task=_task(),
            envelope=envelope,
            outcome="shadow",
            kind="compiler",
            graded_at=STAMP,
        )


def test_kill_at_each_write_leaves_no_partial_group(tmp_path: Path) -> None:
    key_path = tmp_path / "reward-root.key"
    secret = _write_key(key_path)
    repo = Path(__file__).resolve().parents[1]
    for count in (0, 1, 2):
        log = tmp_path / f"kill-{count}.jsonl"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.test_reward_records",
                "kill",
                str(count),
                str(log),
                str(key_path),
                HARNESS,
            ],
            check=False,
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == -signal.SIGKILL
        assert not _leaked(completed.stdout + completed.stderr, secret)
        if log.is_file():
            assert not _leaked(log.read_text(encoding="utf-8", errors="replace"), secret)
        batch = _batch(
            log,
            secret,
            QuarantineQueue(tmp_path / f"q-{count}.jsonl"),
            ConsumedLog(tmp_path / f"c-{count}.jsonl"),
            UngradedRateTracker(),
        )
        assert batch.rows == ()
    whole = tmp_path / "kill-3.jsonl"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.test_reward_records",
            "kill",
            "3",
            str(whole),
            str(key_path),
            HARNESS,
        ],
        check=False,
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    batch = _batch(
        whole,
        secret,
        QuarantineQueue(tmp_path / "q-3.jsonl"),
        ConsumedLog(tmp_path / "c-3.jsonl"),
        UngradedRateTracker(),
    )
    assert [row["reward"] for row in batch.rows] == [1.0, 0.0]
    torn = tmp_path / "torn.jsonl"
    torn.write_bytes(whole.read_bytes() + b'{"torn":')
    reloaded = _batch(
        torn,
        secret,
        QuarantineQueue(tmp_path / "q-torn.jsonl"),
        ConsumedLog(tmp_path / "c-torn.jsonl"),
        UngradedRateTracker(),
    )
    assert [row["reward"] for row in reloaded.rows] == [1.0, 0.0]
    corrupt = tmp_path / "corrupt.jsonl"
    lines = whole.read_text(encoding="utf-8").splitlines()
    corrupt.write_text(lines[0] + "\n{not-json\n" + "\n".join(lines[1:]) + "\n", encoding="utf-8")
    with pytest.raises(RewardRecordError, match="corrupt"):
        load_records(corrupt, RewardKeyring(secret, run_id=RUN))


def test_rates_file_keeps_both_writers(tmp_path: Path) -> None:
    directory = tmp_path / "ledger"
    repo = Path(__file__).resolve().parents[1]
    procs = [
        subprocess.Popen(
            [sys.executable, "-m", "tests.test_reward_records", "rates", str(directory)],
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    outputs = [proc.communicate() for proc in procs]
    assert [proc.returncode for proc in procs] == [0, 0], outputs
    ledger = RewardLedger(directory)
    samples = ledger.rates.export_state()["samples"]["p"]
    assert samples == [True, True]
    assert stat.S_IMODE((directory / "rates.json").stat().st_mode) == 0o640


def test_cross_run_replay_and_checkpoint_mismatch_are_refused(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    header, rows = _members(
        secret,
        run_id="run-a",
        group_id="group-replay",
        members=[("signal", "pass", _signal(source, passed=True), source)],
    )
    log = tmp_path / "copied.jsonl"
    _store(log, header, rows)
    ring = RewardKeyring(secret, run_id="run-b")
    with pytest.raises(RewardKeyError, match="keyring"):
        load_records(log, ring)
    from faustcoder.reward.audit import AuditReportLog

    consumed = ConsumedLog(tmp_path / "consumed.jsonl")
    with pytest.raises(RewardRecordError, match="run id"):
        rl_batch_from_records(
            (header,),
            rows,
            keyring=ring,
            expected_run_id="run-b",
            policy_checkpoints=(CHECKPOINT,),
            queue=QuarantineQueue(tmp_path / "q.jsonl"),
            rates=UngradedRateTracker(),
            consumed=consumed,
            reports=AuditReportLog(tmp_path / "audit-reports.jsonl", consumed),
        )
    assert consumed.disposition("group-replay") is None
    retired = derive_run_key(secret, "run-a")
    ring.remember(retired)
    with pytest.raises(RewardKeyError, match="keyring"):
        verify(rows[0], ring)
    other = os.urandom(32)
    same_run = sign_group_header(
        group_id="group-retired",
        task_digest_full=task_digest_full(_task()),
        group_size=1,
        run_id="run-b",
        run_key=other,
    )
    ring.remember(other)
    verify(same_run, ring)
    other_run = sign_group_header(
        group_id="group-retired",
        task_digest_full=task_digest_full(_task()),
        group_size=1,
        run_id="run-a",
        run_key=other,
    )
    with pytest.raises(RewardKeyError, match="keyring"):
        verify(other_run, ring)
    with pytest.raises(RewardRecordError, match="checkpoint"):
        _batch(
            log,
            secret,
            QuarantineQueue(tmp_path / "q2.jsonl"),
            ConsumedLog(tmp_path / "c2.jsonl"),
            UngradedRateTracker(),
            run_id="run-a",
            checkpoints=("sha256:" + "22" * 32,),
        )


def test_consumed_claim_requires_a_run_key(tmp_path: Path) -> None:
    log = ConsumedLog(tmp_path / "consumed.jsonl")
    with pytest.raises(TypeError):
        log.claim("g-new", "used", task_digest_full="", policy_checkpoint="")
    with pytest.raises(RewardKeyError, match="run key"):
        log.claim("g-new", "used", task_digest_full="", policy_checkpoint="", run_key=b"")
    with pytest.raises(RewardKeyError, match="run key"):
        log.claim(
            "g-new",
            "used",
            task_digest_full="",
            policy_checkpoint="",
            run_key=b"\x00" * 31,
        )
    assert not log.path.exists()


def test_consumed_log_past_16_mib_keeps_dropped_groups(tmp_path: Path) -> None:
    path = tmp_path / "consumed.jsonl"
    boundary = 16 * 1024 * 1024

    def line(group_id: str, disposition: str = "used") -> bytes:
        body = {
            "disposition": disposition,
            "group_id": group_id,
            "policy_checkpoint": "",
            "task_digest_full": "",
        }
        return canonical_bytes(body) + b"\n"

    chunks: list[bytes] = []
    size = 0
    index = 0
    while size + 80 < boundary:
        encoded = line(f"g{index}")
        if size + len(encoded) >= boundary - 8:
            break
        chunks.append(encoded)
        size += len(encoded)
        index += 1
    straddle = line("g-boundary" + ("x" * 64), "used")
    assert size < boundary < size + len(straddle)
    chunks.append(straddle)
    size += len(straddle)
    dropped = line("g-dropped", "dropped:quarantined")
    assert size + len(dropped) > boundary
    chunks.append(dropped)
    path.write_bytes(b"".join(chunks))
    consumed = ConsumedLog(path)
    assert consumed.disposition("g-boundary" + ("x" * 64)) == "used"
    assert consumed.disposition("g-dropped") == "dropped:quarantined"
    before = path.stat().st_size
    with pytest.raises(RewardRecordError, match="already consumed"):
        consumed.claim(
            "g-dropped",
            "used",
            task_digest_full="",
            policy_checkpoint="",
            run_key=_CLAIM_KEY,
        )
    assert path.stat().st_size == before
    consumed.claim("g-new", "used", task_digest_full="", policy_checkpoint="", run_key=_CLAIM_KEY)
    assert path.stat().st_size > before
    assert ConsumedLog(path).disposition("g-dropped") == "dropped:quarantined"
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_consumed_log_fsyncs_the_parent_directory_when_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent_inode = tmp_path.stat().st_ino
    directory_syncs = 0
    real_fsync = os.fsync
    real_open = os.open
    opened: list[tuple[str, int, int, bool]] = []

    def spy_fsync(fd: int) -> None:
        nonlocal directory_syncs
        info = os.fstat(fd)
        if stat.S_ISDIR(info.st_mode) and info.st_ino == parent_inode:
            directory_syncs += 1
        real_fsync(fd)

    def spy_open(path: object, flags: int, mode: int = 0o777, *args: object, **kwargs: object) -> int:
        try:
            fd = real_open(path, flags, mode, *args, **kwargs)
        except FileExistsError:
            opened.append((os.fspath(path), flags, mode, False))
            raise
        opened.append((os.fspath(path), flags, mode, True))
        return fd

    monkeypatch.setattr(os, "fsync", spy_fsync)
    monkeypatch.setattr(os, "open", spy_open)
    path = tmp_path / "consumed.jsonl"
    log = ConsumedLog(path)
    log.claim("g-new", "used", task_digest_full="", policy_checkpoint="", run_key=_CLAIM_KEY)
    assert directory_syncs == 1
    creates = [
        (flags, mode)
        for name, flags, mode, ok in opened
        if name == os.fspath(path) and ok and flags & os.O_CREAT and flags & os.O_EXCL
    ]
    assert len(creates) == 1
    assert creates[0][1] == 0o640
    directories = [
        flags
        for name, flags, _mode, ok in opened
        if ok and name == os.fspath(tmp_path) and flags & os.O_DIRECTORY
    ]
    assert len(directories) == 1
    assert directories[0] & (os.O_WRONLY | os.O_RDWR) == 0
    after_create = len(opened)
    log.claim("g-next", "used", task_digest_full="", policy_checkpoint="", run_key=_CLAIM_KEY)
    assert directory_syncs == 1
    later = opened[after_create:]
    assert any(flags & os.O_EXCL and not ok for _name, flags, _mode, ok in later)
    assert not any(flags & os.O_EXCL and ok for _name, flags, _mode, ok in later)
    assert not any(flags & os.O_DIRECTORY for _name, flags, _mode, _ok in later)
    reopened = ConsumedLog(path)
    reopened.claim("g-later", "used", task_digest_full="", policy_checkpoint="", run_key=_CLAIM_KEY)
    assert directory_syncs == 1
    assert sum(1 for _name, flags, _mode, ok in opened if ok and flags & os.O_EXCL) == 1


def test_resolved_hold_still_drops_a_g1_rewrite(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    passing = b"process = _;"
    failing = b"process = +;"
    timeout = _compiler(
        failing,
        exit_code=124,
        diagnostic_class="timeout",
        diagnostics="timeout: wall clock limit exceeded\n",
    )
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-resolved",
        members=[
            ("signal", "pass", _signal(passing, passed=True), passing),
            ("compiler", "ungraded:unattributed", timeout, failing),
        ],
    )
    original = tmp_path / "original.jsonl"
    _store(original, header, rows)
    queue_path = tmp_path / "q.jsonl"
    first = _batch(
        original,
        secret,
        QuarantineQueue(queue_path),
        ConsumedLog(tmp_path / "consumed-a.jsonl"),
        UngradedRateTracker(),
    )
    assert first.drops == (("group-resolved", "quarantined"),)
    queue = QuarantineQueue(queue_path)
    for item in queue.pending():
        queue.resolve(
            item.record_id,
            attribution=TriageAttribution.HARNESS,
            triaged_by="triage",
            evidence="harness",
        )
    assert queue.pending() == ()
    reopened = QuarantineQueue(queue_path)
    assert reopened.pending() == ()
    assert any(item.group_id == "group-resolved" for item in reopened.holds())
    slim_header, slim_rows = _members(
        secret,
        run_id=RUN,
        group_id="group-resolved",
        members=[("signal", "pass", _signal(passing, passed=True), passing)],
    )
    slim = tmp_path / "g1.jsonl"
    _store(slim, slim_header, slim_rows)
    batch = _batch(
        slim,
        secret,
        reopened,
        ConsumedLog(tmp_path / "consumed-fresh.jsonl"),
        UngradedRateTracker(),
    )
    assert batch.rows == ()
    assert batch.drops == (("group-resolved", "quarantined"),)
    assert stat.S_IMODE(original.stat().st_mode) == 0o640
    assert stat.S_IMODE(queue_path.stat().st_mode) == 0o640


def test_reload_does_not_observe_rates(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-rates",
        members=[("signal", "pass", _signal(source, passed=True), source)],
    )
    log = tmp_path / "rows.jsonl"
    _store(log, header, rows)
    rates = UngradedRateTracker()
    ring = RewardKeyring(secret, run_id=RUN)
    load_records(log, ring)
    load_records(log, ring)
    with pytest.raises(TypeError):
        load_records(log, ring, rates=rates)
    assert rates.export_state()["samples"] == {}


def test_parser_refuses_a_coerced_run_id_and_a_surrogate(tmp_path: Path) -> None:
    secret = _write_key(tmp_path / "reward-root.key")
    source = b"process = _;"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-parse",
        members=[("signal", "pass", _signal(source, passed=True), source)],
    )
    log = tmp_path / "rows.jsonl"
    _store(log, header, rows)
    lines = log.read_text(encoding="utf-8").splitlines()
    body = json.loads(lines[1])
    body["run_id"] = 7
    coerced = tmp_path / "coerced.jsonl"
    coerced.write_text(lines[0] + "\n" + json.dumps(body) + "\n", encoding="utf-8")
    with pytest.raises(RewardRecordError, match="not usable"):
        load_records(coerced, RewardKeyring(secret, run_id=RUN))
    body = json.loads(lines[1])
    body["grader_commit"] = "SURROGATE"
    raw = json.dumps(body).replace("SURROGATE", "\\ud800")
    surrogate = tmp_path / "surrogate.jsonl"
    surrogate.write_bytes((lines[0] + "\n" + raw + "\n").encode("ascii"))
    with pytest.raises(RewardRecordError, match="not usable"):
        load_records(surrogate, RewardKeyring(secret, run_id=RUN))


def test_compiler_kind_still_checks_harness_profile_reference_and_stimulus() -> None:
    secret = os.urandom(32)
    source = b"process = _;"
    signal_row = _signal(source, passed=True)
    with pytest.raises(RewardRecordError, match="kind"):
        sign_reward_row(
            run_key=derive_run_key(secret, RUN),
            run_id=RUN,
            rollout_id=ROLLOUT,
            policy_checkpoint=CHECKPOINT,
            group_id="group-kind",
            group_size=1,
            member_index=0,
            source=source,
            task=_task(),
            envelope=signal_row,
            outcome="pass",
            kind="compiler",
            graded_at=STAMP,
        )
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-kind",
        members=[("signal", "pass", signal_row, source)],
    )
    assert _binding_failed(replace(rows[0], kind="compiler"))
    compiler = _compiler(
        source,
        exit_code=1,
        diagnostic_class="parse_error",
        diagnostics="parse error\n",
    )
    payload = dict(compiler["payload"])
    payload["harness_digest"] = "sha256:" + "ee" * 32
    payload["reference_digest"] = "sha256:" + "ab" * 32
    payload["test_suite_digest"] = "sha256:" + "11" * 32
    payload["profile"] = {"sample_rate": 1}
    wrapped = make_envelope(payload, schema_version="0.3.2", producer="faustcoder.compiler")
    with pytest.raises(RewardRecordError, match="profile|harness"):
        sign_reward_row(
            run_key=derive_run_key(secret, RUN),
            run_id=RUN,
            rollout_id=ROLLOUT,
            policy_checkpoint=CHECKPOINT,
            group_id="group-kind",
            group_size=1,
            member_index=0,
            source=source,
            task=_task(),
            envelope=wrapped,
            outcome="source_attributed",
            kind="compiler",
            graded_at=STAMP,
        )
    del header


def test_grader_digest_is_stable_and_covers_canonical_sources() -> None:
    from faustcoder.reward import records as records

    assert records.grader_digest() == records.grader_digest()
    assert "faustcoder/canonical.py" in records._GRADER_SOURCES
    assert "faustcoder/signal_suite.py" in records._GRADER_SOURCES


def _rewrite_envelope(log: Path, envelope: dict) -> Path:
    lines = []
    for line in log.read_text(encoding="utf-8").splitlines():
        body = json.loads(line)
        if body.get("type") == "reward_row":
            body["envelope"] = envelope
        lines.append(json.dumps(body, separators=(",", ":"), sort_keys=True))
    target = log.with_name(log.stem + "-tampered.jsonl")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _child(argv: list[str]) -> int:
    mode = argv[1]
    if mode == "rates":
        RewardLedger(argv[2]).rates.observe("p", ungraded=True)
        return 0
    import faustcoder.reward.records as records

    if mode == "fresh":
        log, key_path, harness = Path(argv[2]), Path(argv[3]), argv[4]
        records.current_harness_digest = lambda: harness
        secret = load_root_key(key_path, grader_uid=os.getuid())
        source = b"process = _;"
        header, rows = _members(
            secret,
            run_id=RUN,
            group_id="group-fresh",
            members=[("signal", "pass", _signal(source, passed=True), source)],
        )
        _store(log, header, rows)
        return 0
    if mode == "kill":
        count = int(argv[2])
        log, key_path, harness = Path(argv[3]), Path(argv[4]), argv[5]
        records.current_harness_digest = lambda: harness
        secret = load_root_key(key_path, grader_uid=os.getuid())
        good = b"process = _;"
        bad = b"process = +;"
        header, rows = _members(
            secret,
            run_id=RUN,
            group_id="group-kill",
            members=[
                ("signal", "pass", _signal(good, passed=True), good),
                ("signal", "fail", _signal(bad, passed=False), bad),
            ],
        )
        actions = [("header", header), ("row", rows[0]), ("row", rows[1])]
        store = RewardRecordStore(log)
        for index, (kind, item) in enumerate(actions):
            if index == count:
                os.kill(os.getpid(), signal.SIGKILL)
            if kind == "header":
                store.append_header(item)
            else:
                store.append_row(item)
        return 0
    if mode == "g1":
        log = Path(argv[2])
        key_path = Path(argv[3])
        harness = argv[4]
        queue_path = Path(argv[5])
        consumed_path = Path(argv[6])
        records.current_harness_digest = lambda: harness
        secret = load_root_key(key_path, grader_uid=os.getuid())
        batch = _batch(
            log,
            secret,
            QuarantineQueue(queue_path),
            ConsumedLog(consumed_path),
            UngradedRateTracker(),
        )
        drop = batch.drops[0][1] if batch.drops else "none"
        sys.stdout.write(f"rows={len(batch.rows)};drop={drop}\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_child(sys.argv))

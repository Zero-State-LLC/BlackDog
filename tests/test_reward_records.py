"""D3 option H: MAC'd reward rows, group drops, and the key file."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from faustcoder import build_envelope
from faustcoder.reward.grader import (
    is_minted,
    task_binding_digest,
    task_digest_full,
)
from faustcoder.reward.ledger import RewardLedger
from faustcoder.reward.records import (
    ConsumedLog,
    RewardKeyError,
    RewardKeyring,
    RewardRecordError,
    RewardRecordStore,
    derive_run_key,
    load_records,
    load_root_key,
    outcome_for,
    rl_batch_from_records,
    sign_group_header,
    sign_reward_row,
)
from faustcoder.reward.types import (
    QuarantineQueue,
    RewardableSignalReceipt,
    SourceAttributedFailure,
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
):
    bound = _task() if task is None else task
    run_key = derive_run_key(root, run_id)
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
            )
        )
    return header, rows


def _store(path: Path, header, rows) -> None:
    store = RewardRecordStore(path)
    store.append_header(header)
    for row in rows:
        store.append_row(row)


def _batch(path: Path, root: bytes, queue: QuarantineQueue, consumed: ConsumedLog, rates):
    ring = RewardKeyring(root)
    loaded = load_records(path, ring)
    return rl_batch_from_records(
        loaded.headers,
        loaded.rows,
        keyring=ring,
        queue=queue,
        rates=rates,
        consumed=consumed,
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
    ring = RewardKeyring(secret)
    assert repr(ring) == "RewardKeyring(redacted)"
    assert not _leaked(repr(ring), secret)
    assert ring.key_id("run-a") == ring.key_id("run-a")
    assert ring.key_id("run-a") != ring.key_id("run-b")


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
        load_records(tampered, RewardKeyring(secret))

    resigned = tmp_path / "resigned.jsonl"
    header, rows = _members(
        secret,
        run_id=RUN,
        group_id="group-resigned",
        members=[("signal", "pass", lying, source)],
    )
    _store(resigned, header, rows)
    batch = _batch(
        resigned,
        secret,
        QuarantineQueue(tmp_path / "q.jsonl"),
        ConsumedLog(tmp_path / "consumed.jsonl"),
        UngradedRateTracker(),
    )
    assert batch.rows == ()
    assert batch.drops == (("group-resigned", "outcome"),)
    assert not _leaked(resigned.read_text(encoding="utf-8"), secret)


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
        load_records(swapped, RewardKeyring(secret))


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
        load_records(corrupt, RewardKeyring(secret))


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

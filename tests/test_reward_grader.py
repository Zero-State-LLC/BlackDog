"""Reward grader: spec §23, N4 typed receipts, N5 provenance, A2 quarantine."""

from __future__ import annotations

from faustcoder.canonical import content_digest_for
from faustcoder.candidate_machine import CandidateState, apply_signal
from faustcoder.compiler import reproducible_receipt_digest
from faustcoder.exclusions import CompilerExclusion, SourceExclusion
from faustcoder.reward import (
    REWARD_PROFILES,
    UNGRADED_WINDOW,
    FixtureOutcome,
    QuarantineQueue,
    QuarantineRecord,
    RerunOutcome,
    RewardProvenanceError,
    RewardableSignalReceipt,
    SourceAttributedFailure,
    TriageAttribution,
    Ungraded,
    UngradedRateTracker,
    UngradedReason,
    dataset_reward_row,
    grade_compiler_exclusion,
    grade_receipt,
    reward_profiles,
    reward_value,
    rl_batch,
)
from faustcoder.schemas import SchemaValidationError, validate
from tests.support import allowlisted_reward_envelope, compiler_failure_envelope, make_envelope


def _rerun(envelope: dict, *, failed: bool = True, digest: str | None = None) -> RerunOutcome:
    payload = envelope["payload"]
    return RerunOutcome(
        failed=failed,
        exit_code=payload["exit_code"],
        diagnostic_class=payload["diagnostic_class"],
        reproducible_digest=digest or reproducible_receipt_digest(payload),
        environment_digest=payload["environment_digest"],
    )


def test_reward_profiles_are_the_frozen_allowlist() -> None:
    assert reward_profiles() == REWARD_PROFILES
    assert set(REWARD_PROFILES.values()) == {"impulse-44100-v1", "impulse-48000-v1"}
    assert (
        "sha256:e38d50f7345453e14c739fbfeccc7f561ec92c6cec71d181a888b250bcd2ddd0"
        in REWARD_PROFILES
    )


def test_valid_reward_receipt_is_accepted_and_apply_signal_rejects_a_bool() -> None:
    graded = grade_receipt(allowlisted_reward_envelope(passed=True))
    assert isinstance(graded, RewardableSignalReceipt)
    assert graded.passed is True
    assert graded.profile_name == "impulse-48000-v1"
    assert reward_value(graded) == 1.0
    assert apply_signal(CandidateState.COMPILE_CHECKED, graded) is CandidateState.SIGNAL_CHECKED
    failed = grade_receipt(allowlisted_reward_envelope(passed=False))
    assert isinstance(failed, RewardableSignalReceipt)
    assert reward_value(failed) == 0.0
    assert apply_signal(CandidateState.COMPILE_CHECKED, failed) is CandidateState.REJECTED
    try:
        RewardableSignalReceipt()
    except TypeError as exc:
        assert "grade_receipt" in str(exc)
    else:
        raise AssertionError("constructor accepted a caller")
    try:
        apply_signal(CandidateState.COMPILE_CHECKED, True)  # type: ignore[arg-type]
    except TypeError as exc:
        assert "RewardableSignalReceipt" in str(exc)
    else:
        raise AssertionError("bool was accepted")


def test_each_ungraded_reason_and_the_listed_rejections() -> None:
    diagnostic = allowlisted_reward_envelope(
        mutate=lambda payload: payload.__setitem__("purpose", "diagnostic")
        or payload["thresholds"].__setitem__("reward_graded", False)
        or payload["metrics"].__setitem__("comparison", "head-exact+coarse")
    )
    non_rg = grade_receipt(diagnostic)
    assert isinstance(non_rg, Ungraded)
    assert non_rg.reason is UngradedReason.NOT_REWARD_GRADED
    assert reward_value(non_rg) is None

    def flip_threshold(payload: dict) -> None:
        payload["thresholds"]["absolute_tolerance_nano"] += 1

    tampered = grade_receipt(allowlisted_reward_envelope(mutate=flip_threshold))
    assert isinstance(tampered, Ungraded)
    assert tampered.reason is UngradedReason.DIGEST_MISMATCH

    def short_profile(payload: dict) -> None:
        payload["profile"] = dict(payload["profile"])
        payload["profile"]["max_frames"] = 4096
        payload["profile"]["frames"] = 4096
        payload["metrics"]["signed_frames"] = 4096
        payload["metrics"]["frame_count"] = 4096
        payload["metrics"]["renders"]["impulse"]["compared_frames"] = 4096

    unknown = grade_receipt(allowlisted_reward_envelope(mutate=short_profile))
    assert isinstance(unknown, Ungraded)
    assert unknown.reason is UngradedReason.PROFILE_NOT_ALLOWLISTED

    version = grade_receipt(allowlisted_reward_envelope(schema_version="9.9.9"))
    assert isinstance(version, Ungraded)
    assert version.reason is UngradedReason.SCHEMA_VERSION_UNSUPPORTED

    def extra(payload: dict) -> None:
        payload["extra"] = True

    extra_fields = grade_receipt(allowlisted_reward_envelope(mutate=extra))
    assert isinstance(extra_fields, Ungraded)
    assert extra_fields.reason is UngradedReason.SCHEMA_INVALID

    def head_only(payload: dict) -> None:
        payload["metrics"]["comparison"] = "reward-graded-signed"
        payload["metrics"]["signed_frames"] = payload["profile"]["head_frames"]

    partial = grade_receipt(allowlisted_reward_envelope(mutate=head_only))
    assert isinstance(partial, Ungraded)
    assert partial.reason is UngradedReason.COMPARISON_NOT_FULL
    assert reward_value(partial) is None


def test_diagnostic_and_reward_schemas_reject_each_other() -> None:
    reward = allowlisted_reward_envelope()["payload"]
    diagnostic = allowlisted_reward_envelope(
        mutate=lambda payload: (
            payload.__setitem__("purpose", "diagnostic"),
            payload["thresholds"].__setitem__("reward_graded", False),
        )
    )["payload"]
    validate(reward, "dsp-reward-receipt.schema.json")
    validate(diagnostic, "dsp-diagnostic-receipt.schema.json")
    try:
        validate(diagnostic, "dsp-reward-receipt.schema.json")
    except SchemaValidationError:
        pass
    else:
        raise AssertionError("diagnostic receipt validated as reward")
    try:
        validate(reward, "dsp-diagnostic-receipt.schema.json")
    except SchemaValidationError:
        pass
    else:
        raise AssertionError("reward receipt validated as diagnostic")


def test_dataset_and_rl_builders_require_rewardable_provenance() -> None:
    graded = grade_receipt(allowlisted_reward_envelope(passed=True))
    row = dataset_reward_row(graded, example_id="e1")
    assert row["reward"] == 1.0
    assert rl_batch([row])[0]["provenance"] is graded
    non_rg = grade_receipt(
        allowlisted_reward_envelope(
            mutate=lambda payload: payload.__setitem__("purpose", "diagnostic")
        )
    )
    try:
        dataset_reward_row(non_rg)
    except RewardProvenanceError as exc:
        assert "RewardableSignalReceipt" in str(exc)
    else:
        raise AssertionError("non-RG row was accepted")
    forged = {"reward": 1.0, "provenance": {"passed": True}}
    try:
        rl_batch([forged])
    except RewardProvenanceError:
        pass
    else:
        raise AssertionError("forged provenance was accepted")


def test_unattributed_exits_stay_queued_until_auto_attribution() -> None:
    cases = (
        (124, "timeout", "timeout: wall clock limit exceeded\n"),
        (125, "resource_limit", "resource limit: memory\n"),
        (126, "internal", "internal: worker failed\n"),
    )
    for exit_code, diagnostic_class, diagnostics in cases:
        envelope = compiler_failure_envelope(
            exit_code=exit_code,
            diagnostic_class=diagnostic_class,
            diagnostics=diagnostics,
        )
        queue = QuarantineQueue()
        pending = grade_receipt(envelope, diagnostics=diagnostics, policy="policy-a", queue=queue)
        assert isinstance(pending, Ungraded)
        assert pending.reason is UngradedReason.UNATTRIBUTED
        assert pending.detail == "quarantined until triage"
        assert reward_value(pending) is None
        assert queue.count("policy-a") == 1
        assert queue.pending("policy-a")[0].reward is None
        assert queue.pending("policy-a")[0].reproducible_digest
        # Exit 126 is internal, not a timeout or a resource kill.
        if exit_code == 126:
            assert diagnostic_class == "internal"


def test_timeout_and_allocate_forever_become_parse_error_after_auto_attribution() -> None:
    cases = (
        (124, "timeout", "timeout: wall clock limit exceeded\n", "timeout-forever"),
        (125, "resource_limit", "resource limit: memory\n", "allocate-forever"),
    )
    for exit_code, diagnostic_class, diagnostics, policy in cases:
        envelope = compiler_failure_envelope(
            exit_code=exit_code,
            diagnostic_class=diagnostic_class,
            diagnostics=diagnostics,
        )
        queue = QuarantineQueue()
        held = grade_receipt(envelope, diagnostics=diagnostics, policy=policy, queue=queue)
        assert isinstance(held, Ungraded)
        assert held.reason is UngradedReason.UNATTRIBUTED
        digest = reproducible_receipt_digest(envelope["payload"])

        def rerun(payload: dict, envelope: dict = envelope) -> RerunOutcome:
            assert payload["reproducible_digest"] == reproducible_receipt_digest(envelope["payload"])
            return _rerun(envelope, failed=True)

        result = grade_receipt(
            envelope,
            diagnostics=diagnostics,
            rerun=rerun,
            known_good=lambda envelope=envelope: FixtureOutcome(
                passed=True,
                environment_digest=envelope["payload"]["environment_digest"],
            ),
            policy=policy,
            queue=queue,
        )
        assert isinstance(result, SourceAttributedFailure)
        assert result.rung == "parse_error"
        assert reward_value(result) == 0.0
        # The earlier quarantine row is retained. The graded failure is not a new drop.
        assert queue.count(policy) == 1
        assert digest


def test_fixture_failure_is_infra_and_harness_triage_is_separate() -> None:
    envelope = compiler_failure_envelope(
        exit_code=126,
        diagnostic_class="internal",
        diagnostics="internal: worker failed\n",
    )
    queue = QuarantineQueue()
    infra = grade_receipt(
        envelope,
        diagnostics="internal: worker failed\n",
        rerun=lambda _payload: _rerun(envelope, failed=True),
        known_good=lambda: FixtureOutcome(
            passed=False,
            environment_digest=envelope["payload"]["environment_digest"],
        ),
        policy="infra",
        queue=queue,
    )
    assert isinstance(infra, Ungraded)
    assert infra.reason is UngradedReason.INFRA_FAULT
    assert reward_value(infra) is None
    assert queue.count("infra") == 1
    harness = grade_receipt(
        envelope,
        diagnostics="internal: worker failed\n",
        triage="harness",
        policy="harness",
        queue=queue,
    )
    assert isinstance(harness, Ungraded)
    assert harness.reason is UngradedReason.HARNESS_DEFECT
    assert queue.count("harness") == 1


def test_remote_import_and_stack_overflow_are_already_source_attributed() -> None:
    remote = "internal: remote import rejected\n"
    envelope = compiler_failure_envelope(
        exit_code=126, diagnostic_class="internal", diagnostics=remote
    )
    called = {"rerun": 0}

    def rerun(_payload: dict) -> RerunOutcome:
        called["rerun"] += 1
        return _rerun(envelope)

    graded = grade_receipt(envelope, diagnostics=remote, rerun=rerun, known_good=lambda: FixtureOutcome(passed=False))
    assert isinstance(graded, SourceAttributedFailure)
    assert graded.detail == "remote import"
    assert called["rerun"] == 0
    stack = "RangeError: Maximum call stack size exceeded\n"
    stack_envelope = compiler_failure_envelope(
        exit_code=126, diagnostic_class="internal", diagnostics=stack
    )
    stacked = grade_receipt(stack_envelope, diagnostics=stack)
    assert isinstance(stacked, SourceAttributedFailure)
    assert stacked.detail == "stack overflow"
    assert reward_value(stacked) == 0.0


def test_worker_crash_is_unattributed_until_the_fixture_stays_healthy() -> None:
    payload = {
        "kind": "worker_crash",
        "exit_code": 126,
        "diagnostic_class": "internal",
        "reproducible_digest": "sha256:" + "ab" * 32,
    }
    envelope = make_envelope(payload, schema_version="0.3.2", producer="faustcoder.signal")
    queue = QuarantineQueue()
    pending = grade_receipt(envelope, policy="crash", queue=queue)
    assert isinstance(pending, Ungraded)
    assert pending.reason is UngradedReason.UNATTRIBUTED
    assert queue.count("crash") == 1
    environment = "sha256:" + "11" * 32
    attributed = grade_receipt(
        envelope,
        rerun=lambda _payload: RerunOutcome(
            failed=True,
            exit_code=126,
            diagnostic_class="internal",
            reproducible_digest=payload["reproducible_digest"],
            environment_digest=environment,
        ),
        known_good=lambda: FixtureOutcome(passed=True, environment_digest=environment),
        policy="crash",
        queue=queue,
    )
    assert isinstance(attributed, SourceAttributedFailure)
    assert attributed.rung == "parse_error"


def test_compiler_exclusion_is_parse_error() -> None:
    exclusion = CompilerExclusion(
        SourceExclusion(
            group="faust-stk",
            path="excluded.dsp",
            sha256="ab" * 32,
            normalized_sha256="cd" * 32,
            reason="ffunction",
        )
    )
    graded = grade_compiler_exclusion(exclusion)
    assert graded.rung == "parse_error"
    assert reward_value(graded) == 0.0


def test_a7_alarm_hook_uses_the_provisional_window_and_baseline() -> None:
    alarms: list[tuple[str, float]] = []
    early = UngradedRateTracker(baseline=0.001, on_alarm=lambda policy, rate: alarms.append((policy, rate)))
    early.observe("early", ungraded=True)
    for _ in range(9):
        early.observe("early", ungraded=False)
    assert early.alarm("early")
    assert alarms and alarms[0][0] == "early"
    window = UngradedRateTracker(on_alarm=lambda policy, rate: alarms.append((policy, rate)))
    for _ in range(495):
        window.observe("window", ungraded=False)
    for _ in range(5):
        window.observe("window", ungraded=True)
    assert not window.alarm("window")
    assert window.rate("window") == 0.01
    window.observe("window", ungraded=True)
    assert window.alarm("window")
    assert alarms[-1][0] == "window"
    assert window.rate("window") > 0.01


def test_stale_suite_digest_is_a_mismatch_even_when_the_envelope_hash_matches() -> None:
    def scramble(payload: dict) -> None:
        payload["profile"] = dict(payload["profile"])
        payload["profile"]["seed"] = 99

    envelope = allowlisted_reward_envelope(mutate=scramble, sync_suite_digest=False)
    assert envelope["content_digest"] == content_digest_for(envelope["payload"])
    graded = grade_receipt(envelope)
    assert isinstance(graded, Ungraded)
    assert graded.reason is UngradedReason.DIGEST_MISMATCH


def test_missing_environment_digest_stays_unattributed() -> None:
    envelope = compiler_failure_envelope(
        exit_code=124,
        diagnostic_class="timeout",
        diagnostics="timeout: wall clock limit exceeded\n",
    )
    queue = QuarantineQueue()
    for rerun_digest, fixture_digest in ((None, None), ("", ""), (None, "sha256:" + "11" * 32)):
        result = grade_receipt(
            envelope,
            diagnostics="timeout: wall clock limit exceeded\n",
            rerun=lambda _payload, digest=rerun_digest: RerunOutcome(
                failed=True,
                exit_code=124,
                diagnostic_class="timeout",
                reproducible_digest=reproducible_receipt_digest(envelope["payload"]),
                environment_digest=digest,
            ),
            known_good=lambda digest=fixture_digest: FixtureOutcome(
                passed=True, environment_digest=digest
            ),
            policy="env",
            queue=queue,
        )
        assert isinstance(result, Ungraded)
        assert result.reason is UngradedReason.UNATTRIBUTED
        assert reward_value(result) is None
    assert queue.count("env") == 3


def test_closed_failures_count_toward_the_ungraded_rate_and_exit_137_is_a_crash() -> None:
    rates = UngradedRateTracker()
    for _ in range(5):
        invalid = grade_receipt({"schema_version": "0.3.4", "extra": True}, rates=rates, policy="closed")
        assert isinstance(invalid, Ungraded)
        assert invalid.reason is UngradedReason.SCHEMA_INVALID
    assert rates.rate("closed") == 1.0
    assert not rates.alarm("closed")
    queue = QuarantineQueue()
    crash = make_envelope(
        {
            "kind": "worker_crash",
            "exit_code": 137,
            "diagnostic_class": "internal",
            "reproducible_digest": "sha256:" + "ab" * 32,
        },
        schema_version="0.3.2",
        producer="faustcoder.signal",
    )
    held = grade_receipt(crash, policy="oom", queue=queue, rates=rates)
    assert isinstance(held, Ungraded)
    assert held.reason is UngradedReason.UNATTRIBUTED
    assert queue.count("oom") == 1
    assert queue.count("closed") == 0


def test_missing_renders_is_comparison_not_full() -> None:
    def drop(payload: dict) -> None:
        del payload["metrics"]["renders"]

    missing = grade_receipt(allowlisted_reward_envelope(mutate=drop))
    assert isinstance(missing, Ungraded)
    assert missing.reason is UngradedReason.COMPARISON_NOT_FULL

    def replace_renders(payload: dict) -> None:
        payload["metrics"]["renders"] = ["not-a-dict"]

    bad = grade_receipt(allowlisted_reward_envelope(mutate=replace_renders))
    assert isinstance(bad, Ungraded)
    assert bad.reason is UngradedReason.COMPARISON_NOT_FULL


def test_rl_batch_rejects_a_positive_reward_on_a_failed_receipt() -> None:
    failed = grade_receipt(allowlisted_reward_envelope(passed=False))
    row = dataset_reward_row(failed, example_id="e1")
    assert row["reward"] == 0.0
    for bad in (True, False, 1, "1.0", float("nan"), float("inf"), float("-inf"), -1.0, 0.5):
        row["reward"] = bad
        try:
            rl_batch([row])
        except RewardProvenanceError as exc:
            assert "reward" in str(exc)
        else:
            raise AssertionError(f"reward {bad!r} was accepted")
    row["reward"] = 0.0
    assert rl_batch([row])[0]["reward"] == 0.0
    passed = grade_receipt(allowlisted_reward_envelope(passed=True))
    ok = dataset_reward_row(passed, example_id="e2")
    assert ok["reward"] == 1.0
    assert rl_batch([ok])[0]["reward"] == 1.0
    for bad in (2.0, -5.0, 0.0, 0.5):
        ok["reward"] = bad
        try:
            rl_batch([ok])
        except RewardProvenanceError as exc:
            assert "1.0" in str(exc)
        else:
            raise AssertionError(f"passed reward {bad!r} was accepted")


def test_unknown_envelope_field_is_schema_invalid() -> None:
    envelope = allowlisted_reward_envelope()
    envelope["notes"] = "extra"
    graded = grade_receipt(envelope)
    assert isinstance(graded, Ungraded)
    assert graded.reason is UngradedReason.SCHEMA_INVALID


def test_a7_window_does_not_alarm_early_and_rearms() -> None:
    alarms: list[str] = []
    early = UngradedRateTracker(on_alarm=lambda policy, _rate: alarms.append(policy))
    for _ in range(6):
        early.observe("early", ungraded=True)
    assert not early.alarm("early")
    assert alarms == []
    window = UngradedRateTracker(on_alarm=lambda policy, _rate: alarms.append("again"))
    for _ in range(495):
        window.observe("back", ungraded=False)
    for _ in range(5):
        window.observe("back", ungraded=True)
    assert not window.alarm("back")
    window.observe("back", ungraded=True)
    assert window.alarm("back")
    assert alarms == ["again"]
    for _ in range(UNGRADED_WINDOW):
        window.observe("back", ungraded=False)
    assert not window.alarm("back")
    for _ in range(6):
        window.observe("back", ungraded=True)
    assert window.alarm("back")
    assert alarms == ["again", "again"]
    zero = UngradedRateTracker(baseline=0.0, on_alarm=lambda policy, _rate: alarms.append(policy))
    zero.observe("zero", ungraded=True)
    assert zero.alarm("zero")


def test_quarantine_log_resolves_and_ages(tmp_path) -> None:
    from datetime import datetime, timezone

    queue = QuarantineQueue(tmp_path / "quarantine.jsonl")
    held = queue.hold(
        QuarantineRecord(
            policy="policy-a",
            reason=UngradedReason.UNATTRIBUTED,
            reproducible_digest="sha256:" + "ab" * 32,
            held_at="2020-01-01T00:00:00Z",
            record_id="row-1",
        )
    )
    assert held.record_id == "row-1"
    assert queue.count() == 1
    stale = queue.age_alarm(now=datetime(2026, 1, 1, tzinfo=timezone.utc), limit_seconds=3600)
    assert [row.record_id for row in stale] == ["row-1"]
    graded = queue.resolve(
        "row-1",
        attribution=TriageAttribution.INFRASTRUCTURE,
        triaged_by="ada",
        triaged_at="2026-10-18T00:00:00Z",
    )
    assert isinstance(graded, Ungraded)
    assert graded.reason is UngradedReason.INFRA_FAULT
    assert reward_value(graded) is None
    assert queue.count() == 0
    assert queue.age_alarm(now=datetime(2026, 1, 1, tzinfo=timezone.utc)) == ()
    reloaded = QuarantineQueue(tmp_path / "quarantine.jsonl")
    assert reloaded.count() == 0
    recorded = reloaded.resolution("row-1")
    assert recorded is not None
    assert recorded.triaged_by == "ada"
    assert recorded.triaged_at == "2026-10-18T00:00:00Z"
    text = (tmp_path / "quarantine.jsonl").read_text(encoding="utf-8")
    assert '"op":"hold"' in text
    assert '"attribution":"infrastructure"' in text
    assert '"triaged_by":"ada"' in text


def test_apply_signal_rejects_a_forged_or_mutated_receipt() -> None:
    forged = object.__new__(RewardableSignalReceipt)
    object.__setattr__(forged, "passed", True)
    object.__setattr__(forged, "profile_name", "impulse-48000-v1")
    object.__setattr__(forged, "test_suite_digest", "sha256:" + "ab" * 32)
    object.__setattr__(forged, "reproducible_digest", "sha256:" + "cd" * 32)
    object.__setattr__(forged, "schema_version", "0.3.4")
    try:
        apply_signal(CandidateState.COMPILE_CHECKED, forged)
    except TypeError as exc:
        assert "RewardableSignalReceipt" in str(exc)
    else:
        raise AssertionError("object.__new__ was accepted")
    try:
        exec(
            "RewardableSignalReceipt._mint(passed=True, profile_name='x',"
            " test_suite_digest='y', reproducible_digest='z', schema_version='0.3.4')",
            {"__name__": "faustcoder.reward.grader", "RewardableSignalReceipt": RewardableSignalReceipt},
        )
    except TypeError as exc:
        assert "grade_receipt" in str(exc)
    else:
        raise AssertionError("a faked module minted a receipt")
    graded = grade_receipt(allowlisted_reward_envelope(passed=False))
    object.__setattr__(graded, "passed", True)
    try:
        apply_signal(CandidateState.COMPILE_CHECKED, graded)
    except TypeError as exc:
        assert "RewardableSignalReceipt" in str(exc)
    else:
        raise AssertionError("a mutated receipt was accepted")


def test_reward_graded_failures_are_held_on_the_ledger_or_refused(monkeypatch, tmp_path) -> None:
    from faustcoder.compiler import Compilation
    from faustcoder.reward import RewardLedger, RewardOutcomeHeld, RewardUseRefused
    from faustcoder.signal import SignalHarnessError, SignalProfile, run_signal

    payload = compiler_failure_envelope(
        exit_code=124,
        diagnostic_class="timeout",
        diagnostics="timeout: wall clock limit exceeded\n",
    )["payload"]
    compilation = Compilation(
        receipt=payload,
        diagnostics="timeout: wall clock limit exceeded\n",
        reproducible_digest=reproducible_receipt_digest(payload),
    )
    monkeypatch.setattr("faustcoder.signal.compile_source", lambda *_args, **_kwargs: compilation)
    profile = SignalProfile(sample_rate=48000, frames=64, block_size=64, stimuli=("impulse",))
    try:
        run_signal("process = _;\n", profile, None, reward_graded=True)
    except RewardUseRefused as exc:
        assert "ledger" in str(exc)
    else:
        raise AssertionError("a reward failure with no ledger was scored")
    ledger = RewardLedger(tmp_path / "ledger")
    try:
        run_signal("process = _;\n", profile, None, reward_graded=True, ledger=ledger)
    except RewardOutcomeHeld as exc:
        assert isinstance(exc.grade, Ungraded)
        assert exc.grade.reason is UngradedReason.UNATTRIBUTED
    else:
        raise AssertionError("timeout was not held")
    assert ledger.queue.count("signal") == 1
    assert RewardLedger(tmp_path / "ledger").queue.count("signal") == 1

    ok = Compilation(
        receipt={"exit_code": 0, "diagnostic_class": "ok"},
        diagnostics="",
        reproducible_digest="sha256:" + "ab" * 32,
    )
    monkeypatch.setattr("faustcoder.signal.compile_source", lambda *_args, **_kwargs: ok)

    def crash(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise SignalHarnessError("renderer stopped: internal")

    monkeypatch.setattr("faustcoder.signal._render", crash)
    try:
        run_signal("process = _;\n", profile, None, reward_graded=True, ledger=ledger)
    except RewardOutcomeHeld as exc:
        assert isinstance(exc.grade, Ungraded)
        assert exc.grade.reason is UngradedReason.UNATTRIBUTED
    else:
        raise AssertionError("renderer crash was not held")
    assert ledger.queue.count("signal") == 2


def test_commit_signal_check_grades_a_timeout_onto_the_store_ledger(store) -> None:
    from faustcoder.compiler import Compilation
    from faustcoder.reward.ledger import ledger_for_store
    from faustcoder.signal import (
        SignalRun,
        SignalSuite,
        commit_signal_check,
        reproducible_signal_digest,
    )

    payload = compiler_failure_envelope(
        exit_code=125,
        diagnostic_class="resource_limit",
        diagnostics="resource limit: memory\n",
    )["payload"]
    signal = allowlisted_reward_envelope(passed=True)["payload"]
    run = SignalRun(
        compilation=Compilation(
            receipt=payload,
            diagnostics="resource limit: memory\n",
            reproducible_digest=reproducible_receipt_digest(payload),
        ),
        receipt=signal,
        reproducible_digest=reproducible_signal_digest(signal),
        failures=(),
        reference_payload=None,
    )
    committed = commit_signal_check(
        store,
        SignalSuite(runs=(run,)),
        state=CandidateState.COMPILE_CHECKED,
        created_at="2026-10-17T00:00:00Z",
    )
    assert committed.state is CandidateState.COMPILE_CHECKED
    assert any(isinstance(item, Ungraded) for item in committed.outcomes)
    ledger = ledger_for_store(store)
    assert ledger.queue.count("signal") == 1
    assert ledger.rates.rate("signal") > 0


def test_rendered_reward_impulse_grades_as_rewardable() -> None:
    from faustcoder.canonical import build_envelope
    from faustcoder.reward.profiles import reward_signal_profile
    from faustcoder.signal import SIGNAL_SCHEMA_VERSION, impulse_reference, run_signal

    profile = reward_signal_profile("impulse-48000-v1")
    reference = impulse_reference(profile, lambda samples: samples)
    run = run_signal("process = _;\n", profile, reference, reward_graded=True)
    assert run.receipt["passed"] is True
    assert run.receipt["purpose"] == "reward"
    envelope = build_envelope(
        schema_version=SIGNAL_SCHEMA_VERSION,
        created_at="2026-10-17T00:00:00Z",
        producer="faustcoder.signal",
        parents=[],
        payload=run.receipt,
    )
    graded = grade_receipt(envelope)
    assert isinstance(graded, RewardableSignalReceipt)
    assert graded.passed is True
    assert graded.profile_name == "impulse-48000-v1"
    assert graded.test_suite_digest == run.receipt["test_suite_digest"]


def test_resolve_without_attribution_leaves_a_stale_timeout_quarantined(tmp_path) -> None:
    from datetime import datetime, timezone

    queue = QuarantineQueue(tmp_path / "quarantine.jsonl")
    queue.hold(
        QuarantineRecord(
            policy="signal",
            reason=UngradedReason.UNATTRIBUTED,
            reproducible_digest="sha256:" + "ab" * 32,
            detail="timeout",
            held_at="2020-01-01T00:00:00Z",
            record_id="timeout-1",
        )
    )
    stale = queue.age_alarm(now=datetime(2026, 10, 18, tzinfo=timezone.utc))
    assert [row.record_id for row in stale] == ["timeout-1"]
    try:
        queue.resolve("timeout-1")
    except TypeError as exc:
        assert "attribution" in str(exc)
    else:
        raise AssertionError("a stale timeout was resolved without attribution")
    assert queue.count() == 1
    assert queue.pending()[0].reward is None
    assert queue.resolution("timeout-1") is None
    text = (tmp_path / "quarantine.jsonl").read_text(encoding="utf-8")
    assert '"op":"resolve"' not in text


def test_source_triage_is_parse_error_and_harness_is_dropped() -> None:
    queue = QuarantineQueue()
    queue.hold(
        QuarantineRecord(
            policy="signal",
            reason=UngradedReason.UNATTRIBUTED,
            reproducible_digest="sha256:" + "cd" * 32,
            record_id="row-source",
            held_at="2026-10-18T00:00:00Z",
        )
    )
    source = queue.resolve(
        "row-source",
        attribution=TriageAttribution.SOURCE,
        triaged_by="danny",
        triaged_at="2026-10-17T00:00:00Z",
        evidence="sha256:" + "ab" * 32,
    )
    assert isinstance(source, SourceAttributedFailure)
    assert source.rung == "parse_error"
    assert reward_value(source) == 0.0
    assert queue.count() == 0
    queue.hold(
        QuarantineRecord(
            policy="signal",
            reason=UngradedReason.UNATTRIBUTED,
            reproducible_digest="sha256:" + "ef" * 32,
            record_id="row-harness",
            held_at="2026-10-18T00:00:00Z",
        )
    )
    dropped = queue.resolve(
        "row-harness",
        attribution="harness",
        triaged_by="ada",
    )
    assert isinstance(dropped, Ungraded)
    assert dropped.reason is UngradedReason.HARNESS_DEFECT
    assert reward_value(dropped) is None


def test_kill_exits_139_and_negative_9_are_queued_crashes() -> None:
    queue = QuarantineQueue()
    for exit_code, digest in ((139, "ab"), (-9, "cd")):
        envelope = make_envelope(
            {
                "kind": "worker_crash",
                "exit_code": exit_code,
                "diagnostic_class": "internal",
                "reproducible_digest": "sha256:" + digest * 32,
            },
            schema_version="0.3.2",
            producer="faustcoder.signal",
        )
        graded = grade_receipt(envelope, policy="kills", queue=queue)
        assert isinstance(graded, Ungraded)
        assert graded.reason is UngradedReason.UNATTRIBUTED
    bare = make_envelope(
        {
            "exit_code": 139,
            "diagnostic_class": "internal",
            "reproducible_digest": "sha256:" + "ef" * 32,
        },
        schema_version="0.3.4",
        producer="faustcoder.signal",
    )
    graded = grade_receipt(bare, policy="kills", queue=queue)
    assert isinstance(graded, Ungraded)
    assert graded.reason is UngradedReason.UNATTRIBUTED
    assert queue.count("kills") == 3


def test_lookalike_receipt_is_not_minted() -> None:
    from faustcoder.reward.grader import is_minted

    graded = grade_receipt(allowlisted_reward_envelope(passed=False))
    assert is_minted(graded)
    lookalike = object.__new__(RewardableSignalReceipt)
    for name in ("passed", "profile_name", "test_suite_digest", "reproducible_digest", "schema_version"):
        object.__setattr__(lookalike, name, getattr(graded, name))
    assert lookalike._snapshot() == graded._snapshot()
    assert not is_minted(lookalike)
    try:
        apply_signal(CandidateState.COMPILE_CHECKED, lookalike)
    except TypeError as exc:
        assert "RewardableSignalReceipt" in str(exc)
    else:
        raise AssertionError("a lookalike receipt was accepted")
    import faustcoder.reward.grader as grader_module

    assert not hasattr(grader_module, "_register_mint")


def test_reward_suite_grades_timeout_and_crash_on_commit(monkeypatch, store, tmp_path) -> None:
    from faustcoder.compiler import Compilation
    from faustcoder.reward import RewardLedger, RewardOutcomeHeld, RewardUseRefused
    from faustcoder.sandbox import SandboxError
    from faustcoder.signal import SignalHarnessError, commit_signal_check, run_signal_suite

    try:
        run_signal_suite(
            "process = _;\n",
            lambda _profile: None,
            sample_rates=(48000,),
            frames=64,
            block_size=64,
            reward_graded=True,
        )
    except RewardUseRefused as exc:
        assert "ledger" in str(exc)
    else:
        raise AssertionError("a reward suite with no ledger was accepted")

    payload = compiler_failure_envelope(
        exit_code=124,
        diagnostic_class="timeout",
        diagnostics="timeout: wall clock limit exceeded\n",
    )["payload"]
    compilation = Compilation(
        receipt=payload,
        diagnostics="timeout: wall clock limit exceeded\n",
        reproducible_digest=reproducible_receipt_digest(payload),
    )
    monkeypatch.setattr("faustcoder.signal.compile_source", lambda *_args, **_kwargs: compilation)
    ledger = RewardLedger(tmp_path / "suite")
    suite = run_signal_suite(
        "process = _;\n",
        lambda _profile: None,
        sample_rates=(48000,),
        frames=64,
        block_size=64,
        reward_graded=True,
        ledger=ledger,
    )
    assert suite.runs[0].receipt is None
    assert suite.runs[0].compilation.receipt["exit_code"] == 124
    committed = commit_signal_check(
        store,
        suite,
        state=CandidateState.COMPILE_CHECKED,
        created_at="2026-10-18T00:00:00Z",
    )
    assert committed.state is CandidateState.COMPILE_CHECKED
    assert len(committed.outcomes) == 1
    assert isinstance(committed.outcomes[0], Ungraded)
    assert committed.outcomes[0].reason is UngradedReason.UNATTRIBUTED
    assert ledger.queue.count("signal") == 1

    ok_payload = compiler_failure_envelope(
        exit_code=0,
        diagnostic_class="ok",
        diagnostics="",
    )["payload"]
    ok = Compilation(
        receipt=ok_payload,
        diagnostics="",
        reproducible_digest=reproducible_receipt_digest(ok_payload),
    )
    monkeypatch.setattr("faustcoder.signal.compile_source", lambda *_args, **_kwargs: ok)

    def crash(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise SignalHarnessError("renderer stopped: internal")

    monkeypatch.setattr("faustcoder.signal._render", crash)
    crashed = run_signal_suite(
        "process = _;\n",
        lambda _profile: None,
        sample_rates=(48000,),
        frames=64,
        block_size=64,
        reward_graded=True,
        ledger=ledger,
    )
    assert crashed.runs[0].reward_failure == "worker_crash"
    commit_signal_check(
        store,
        crashed,
        state=CandidateState.COMPILE_CHECKED,
        created_at="2026-10-18T00:00:00Z",
    )
    assert ledger.queue.count("signal") == 2

    def sandbox(*_args: object, **_kwargs: object) -> Compilation:
        raise SandboxError("worker failed")

    monkeypatch.setattr("faustcoder.signal.compile_source", sandbox)
    try:
        run_signal_suite(
            "process = _;\n",
            lambda _profile: None,
            sample_rates=(48000,),
            frames=64,
            block_size=64,
            reward_graded=True,
            ledger=ledger,
        )
    except RewardOutcomeHeld as exc:
        assert isinstance(exc.grade, Ungraded)
        assert exc.grade.reason is UngradedReason.UNATTRIBUTED
    else:
        raise AssertionError("a suite sandbox failure was not held")
    assert ledger.queue.count("signal") == 3


def _quarantine_log(*lines: dict[str, object]) -> str:
    import json

    return "".join(json.dumps(line, separators=(",", ":"), sort_keys=True) + "\n" for line in lines)


def _held_timeout() -> dict[str, object]:
    return {
        "detail": "timeout",
        "held_at": "2020-01-01T00:00:00Z",
        "op": "hold",
        "policy": "signal",
        "reason": "unattributed",
        "record_id": "row-1",
        "reproducible_digest": "sha256:" + "ab" * 32,
    }


def _resolve_line(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "attribution": "source",
        "evidence": "quiet rerun sha256:" + "cd" * 32,
        "op": "resolve",
        "outcome": "parse_error",
        "record_id": "row-1",
        "triaged_at": "2026-10-17T00:00:00Z",
        "triaged_by": "ada",
    }
    body.update(overrides)
    return body


def test_replay_refuses_a_second_resolve(tmp_path) -> None:
    path = tmp_path / "quarantine.jsonl"
    path.write_text(
        _quarantine_log(_held_timeout(), _resolve_line(), _resolve_line()),
        encoding="utf-8",
    )
    try:
        QuarantineQueue(path)
    except ValueError as exc:
        assert "second time" in str(exc)
    else:
        raise AssertionError("a doubled resolve was replayed")


def test_replay_refuses_a_source_to_harness_flip(tmp_path) -> None:
    path = tmp_path / "quarantine.jsonl"
    path.write_text(
        _quarantine_log(
            _held_timeout(),
            _resolve_line(),
            _resolve_line(attribution="harness", outcome="drop", evidence=""),
        ),
        encoding="utf-8",
    )
    try:
        QuarantineQueue(path)
    except ValueError as exc:
        assert "second time" in str(exc)
    else:
        raise AssertionError("a source triage was flipped to harness")


def test_replay_refuses_a_tampered_outcome(tmp_path) -> None:
    path = tmp_path / "quarantine.jsonl"
    path.write_text(
        _quarantine_log(_held_timeout(), _resolve_line(outcome="drop")),
        encoding="utf-8",
    )
    try:
        QuarantineQueue(path)
    except ValueError as exc:
        assert "outcome" in str(exc)
    else:
        raise AssertionError("a source row with outcome drop was replayed")
    harness = tmp_path / "harness.jsonl"
    harness.write_text(
        _quarantine_log(
            _held_timeout(),
            _resolve_line(attribution="infrastructure", outcome="parse_error", evidence=""),
        ),
        encoding="utf-8",
    )
    try:
        QuarantineQueue(harness)
    except ValueError as exc:
        assert "outcome" in str(exc)
    else:
        raise AssertionError("an infrastructure row with outcome parse_error was replayed")


def test_source_triage_requires_evidence_and_a_past_timestamp() -> None:
    queue = QuarantineQueue()
    queue.hold(
        QuarantineRecord(
            policy="signal",
            reason=UngradedReason.UNATTRIBUTED,
            reproducible_digest="sha256:" + "ab" * 32,
            record_id="row-1",
            held_at="2020-01-01T00:00:00Z",
        )
    )
    for kwargs in (
        {"evidence": "  ", "triaged_at": "2026-10-17T00:00:00Z"},
        {"evidence": "receipt sha256:" + "ab" * 32, "triaged_at": "2099-01-01T00:00:00Z"},
        {"evidence": "receipt sha256:" + "ab" * 32, "triaged_at": "2026-10-17T00:00:00"},
    ):
        try:
            queue.resolve(
                "row-1",
                attribution=TriageAttribution.SOURCE,
                triaged_by="ada",
                **kwargs,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"source triage accepted {kwargs}")
    assert queue.count() == 1


def test_compiler_kill_exits_are_queued_crashes() -> None:
    queue = QuarantineQueue()
    for exit_code in (137, 139, -9):
        envelope = compiler_failure_envelope(
            exit_code=exit_code,
            diagnostic_class="internal",
            diagnostics="worker killed\n",
        )
        graded = grade_receipt(envelope, policy="compiler-kill", queue=queue)
        assert isinstance(graded, Ungraded)
        assert graded.reason is UngradedReason.UNATTRIBUTED
        assert reward_value(graded) is None
    assert queue.count("compiler-kill") == 3


def test_recursive_program_is_parse_error_under_each_outcome(store, tmp_path) -> None:
    import hashlib
    from pathlib import Path

    from faustcoder.compiler import Compilation
    from faustcoder.reward import RewardLedger
    from faustcoder.signal import SignalRun, SignalSuite, commit_signal_check

    source = Path("tests/fixtures/dsp/recurse.dsp").read_text(encoding="utf-8")
    assert "f(n) = f(n - 1)" in source
    source_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
    ledger = RewardLedger(tmp_path / "recursion")

    def commit_compiler(exit_code: int, diagnostic_class: str, diagnostics: str) -> None:
        envelope = compiler_failure_envelope(
            exit_code=exit_code,
            diagnostic_class=diagnostic_class,
            diagnostics=diagnostics,
        )
        payload = dict(envelope["payload"])
        payload["source_sha256"] = source_sha
        payload = make_envelope(
            payload,
            schema_version="0.3.2",
            producer="faustcoder.compiler",
        )["payload"]
        run = SignalRun(
            compilation=Compilation(
                receipt=payload,
                diagnostics=diagnostics,
                reproducible_digest=reproducible_receipt_digest(payload),
            ),
            receipt=None,
            reproducible_digest=reproducible_receipt_digest(payload),
            failures=("compiler",),
            reference_payload=None,
            reward_failure="compiler",
        )
        committed = commit_signal_check(
            store,
            SignalSuite(runs=(run,), ledger=ledger),
            state=CandidateState.COMPILE_CHECKED,
            created_at="2026-10-18T00:00:00Z",
        )
        assert committed.state is CandidateState.REJECTED
        assert len(committed.outcomes) == 1
        outcome = committed.outcomes[0]
        assert isinstance(outcome, SourceAttributedFailure)
        assert outcome.rung == "parse_error"
        assert outcome.detail == "stack overflow"

    commit_compiler(1, "other", "RuntimeError: unreachable\nwasm trap\n")
    commit_compiler(126, "internal", "ERROR : stack overflow in eval\n")

    crashed = compiler_failure_envelope(
        exit_code=0,
        diagnostic_class="ok",
        diagnostics="",
    )
    payload = dict(crashed["payload"])
    payload["source_sha256"] = source_sha
    payload = make_envelope(
        payload,
        schema_version="0.3.2",
        producer="faustcoder.compiler",
    )["payload"]
    digest = reproducible_receipt_digest(payload)
    segfault = SignalRun(
        compilation=Compilation(
            receipt=payload,
            diagnostics="worker segfault\ndeep recursion\n",
            reproducible_digest=digest,
        ),
        receipt=None,
        reproducible_digest=digest,
        failures=("worker_crash",),
        reference_payload=None,
        reward_failure="worker_crash",
    )
    committed = commit_signal_check(
        store,
        SignalSuite(runs=(segfault,), ledger=ledger),
        state=CandidateState.COMPILE_CHECKED,
        created_at="2026-10-18T00:00:00Z",
    )
    assert committed.state is CandidateState.REJECTED
    outcome = committed.outcomes[0]
    assert isinstance(outcome, SourceAttributedFailure)
    assert outcome.rung == "parse_error"
    assert outcome.detail == "stack overflow"
    assert ledger.queue.count() == 0

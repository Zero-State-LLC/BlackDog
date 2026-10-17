"""Reward grader: spec §23, N4 typed receipts, N5 provenance, A2 quarantine."""

from __future__ import annotations

from faustcoder.canonical import content_digest_for
from faustcoder.candidate_machine import CandidateState, apply_signal
from faustcoder.compiler import reproducible_receipt_digest
from faustcoder.exclusions import CompilerExclusion, SourceExclusion
from faustcoder.reward import (
    REWARD_PROFILES,
    FixtureOutcome,
    QuarantineQueue,
    RerunOutcome,
    RewardProvenanceError,
    RewardableSignalReceipt,
    SourceAttributedFailure,
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
    attributed = grade_receipt(
        envelope,
        rerun=lambda _payload: RerunOutcome(
            failed=True,
            exit_code=126,
            diagnostic_class="internal",
            reproducible_digest=payload["reproducible_digest"],
        ),
        known_good=lambda: FixtureOutcome(passed=True),
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
    for _ in range(494):
        window.observe("window", ungraded=False)
    assert not window.alarm("window")
    for _ in range(6):
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

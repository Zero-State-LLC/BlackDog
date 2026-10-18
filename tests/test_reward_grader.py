"""Reward grader: spec §23, N4 typed receipts, N5 provenance, A2 quarantine."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

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
    AutoAttributionRefused,
    RewardProvenanceError,
    RewardableSignalReceipt,
    SourceAttributedFailure,
    TriageAttribution,
    TriageDecision,
    Ungraded,
    UngradedRateTracker,
    UngradedReason,
    dataset_reward_row,
    grade_compiler_exclusion,
    grade_receipt,
    is_minted,
    mint_native_stack_match,
    reward_profiles,
    reward_value,
    rl_batch,
    shadow_observe,
)
from faustcoder.reward.grader import _compile_stack_line
from faustcoder.schemas import SchemaValidationError, validate
from faustcoder.signal import SignalHarnessError
from tests.support import allowlisted_reward_envelope, compiler_failure_envelope, make_envelope

_REPO = Path(__file__).resolve().parents[1]


def _rerun(envelope: dict, *, failed: bool = True, digest: str | None = None) -> RerunOutcome:
    payload = envelope["payload"]
    return RerunOutcome(
        failed=failed,
        exit_code=payload["exit_code"],
        diagnostic_class=payload["diagnostic_class"],
        reproducible_digest=digest or reproducible_receipt_digest(payload),
        environment_digest=payload["environment_digest"],
    )


def _linear_task() -> dict:
    task = json.loads(
        (Path(__file__).resolve().parents[1] / "tests/fixtures/valid/task-spec.json").read_text(
            encoding="utf-8"
        )
    )
    assert task["effect"] == "linear"
    return task


def test_reward_profiles_are_the_frozen_allowlist() -> None:
    assert reward_profiles() == REWARD_PROFILES
    assert set(REWARD_PROFILES.values()) == {"impulse-44100-v1", "impulse-48000-v1"}
    assert (
        "sha256:e38d50f7345453e14c739fbfeccc7f561ec92c6cec71d181a888b250bcd2ddd0"
        in REWARD_PROFILES
    )
    assert (
        "sha256:4b24efe4c30562344e56713da4ec05b3e4e59dfe9b8ddebbcfdeef9f64ac88ee"
        in REWARD_PROFILES
    )
    assert len(REWARD_PROFILES) == 2


def test_valid_reward_receipt_is_accepted_and_apply_signal_rejects_a_bool() -> None:
    task = _linear_task()
    graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    assert isinstance(graded, RewardableSignalReceipt)
    assert graded.passed is True
    assert graded.profile_name == "impulse-48000-v1"
    assert graded.task_digest
    assert reward_value(graded, task) == 1.0
    assert apply_signal(CandidateState.COMPILE_CHECKED, graded) is CandidateState.SIGNAL_CHECKED
    failed = grade_receipt(allowlisted_reward_envelope(passed=False), task=task)
    assert isinstance(failed, RewardableSignalReceipt)
    assert reward_value(failed, task) == 0.0
    assert apply_signal(CandidateState.COMPILE_CHECKED, failed) is CandidateState.REJECTED
    try:
        reward_value(graded)
    except RewardProvenanceError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("reward_value scored a receipt without its task")
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
    task = _linear_task()
    graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    row = dataset_reward_row(graded, task=task, example_id="e1")
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
    from faustcoder.signal import SignalHarnessError

    nonlinear = _linear_task()
    nonlinear["effect"] = "nonlinear"
    try:
        dataset_reward_row(graded, task=nonlinear)
    except SignalHarnessError as exc:
        assert "unrewardable" in str(exc)
    else:
        raise AssertionError("nonlinear task was accepted")
    row["task"] = nonlinear
    try:
        rl_batch([row])
    except SignalHarnessError as exc:
        assert "unrewardable" in str(exc)
    else:
        raise AssertionError("nonlinear task was accepted by rl_batch")


def test_reward_value_refuses_an_unrewardable_task() -> None:
    linear = _linear_task()
    passed = grade_receipt(allowlisted_reward_envelope(passed=True), task=linear)
    assert reward_value(passed, linear) == 1.0
    for effect in ("nonlinear", "time_variant"):
        task = _linear_task()
        task["effect"] = effect
        graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
        failed = grade_receipt(allowlisted_reward_envelope(passed=False), task=task)
        for receipt in (graded, failed):
            try:
                reward_value(receipt, task)
            except SignalHarnessError as exc:
                assert "unrewardable" in str(exc)
            else:
                raise AssertionError(f"reward_value scored {effect}")
        try:
            dataset_reward_row(graded, task=task)
        except SignalHarnessError as exc:
            assert "unrewardable" in str(exc)
        else:
            raise AssertionError(f"dataset_reward_row scored {effect}")
        try:
            rl_batch([{"reward": 1.0, "provenance": graded, "task": task}])
        except SignalHarnessError as exc:
            assert "unrewardable" in str(exc)
        else:
            raise AssertionError(f"rl_batch scored {effect}")
    closed = _linear_task()
    profile = dict(closed["test_profile"])
    profile["rewardable"] = False
    profile["unrewardable_reason"] = "nonlinear"
    closed["test_profile"] = profile
    try:
        reward_value(passed, closed)
    except RewardProvenanceError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("reward_value scored a task the receipt was not minted for")
    closed_receipt = grade_receipt(allowlisted_reward_envelope(passed=True), task=closed)
    try:
        reward_value(closed_receipt, closed)
    except SignalHarnessError as exc:
        assert "unrewardable" in str(exc)
    else:
        raise AssertionError("reward_value scored rewardable false")
    try:
        dataset_reward_row(closed_receipt, task=closed)
    except SignalHarnessError as exc:
        assert "unrewardable" in str(exc)
    else:
        raise AssertionError("dataset_reward_row scored rewardable false")
    row = dataset_reward_row(passed, task=linear, example_id="e")
    row["task"] = closed
    try:
        rl_batch([row])
    except SignalHarnessError as exc:
        assert "unrewardable" in str(exc)
    else:
        raise AssertionError("rl_batch scored rewardable false")


def test_lookalike_and_rebound_receipts_score_nothing() -> None:
    task = _linear_task()
    failed = grade_receipt(allowlisted_reward_envelope(passed=False), task=task)
    lookalike = object.__new__(RewardableSignalReceipt)
    for name in (
        "passed",
        "profile_name",
        "test_suite_digest",
        "reproducible_digest",
        "schema_version",
        "task_digest",
        "task_digest_full",
        "unrewardable",
    ):
        object.__setattr__(lookalike, name, getattr(failed, name))
    object.__setattr__(lookalike, "passed", True)
    assert not is_minted(lookalike)
    try:
        reward_value(lookalike, task)
    except RewardProvenanceError as exc:
        assert "not minted" in str(exc)
    else:
        raise AssertionError("reward_value scored a lookalike")
    try:
        dataset_reward_row(lookalike, task=task)
    except RewardProvenanceError as exc:
        assert "RewardableSignalReceipt" in str(exc)
    else:
        raise AssertionError("dataset_reward_row scored a lookalike")
    try:
        rl_batch([{"reward": 1.0, "provenance": lookalike, "task": task}])
    except RewardProvenanceError as exc:
        assert "RewardableSignalReceipt" in str(exc)
    else:
        raise AssertionError("rl_batch scored a lookalike")
    passed = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    other = _linear_task()
    other["task_id"] = "task-other-linear"
    object.__setattr__(
        passed,
        "task_digest",
        content_digest_for({"effect": other["effect"], "task_id": other["task_id"]}),
    )
    assert not is_minted(passed)
    try:
        reward_value(passed, other)
    except RewardProvenanceError as exc:
        assert "not minted" in str(exc)
    else:
        raise AssertionError("reward_value scored a rebound receipt")
    try:
        rl_batch([{"reward": 1.0, "provenance": passed, "task": other}])
    except RewardProvenanceError as exc:
        assert "RewardableSignalReceipt" in str(exc)
    else:
        raise AssertionError("rl_batch scored a rebound receipt")


def test_linear_row_refuses_a_receipt_minted_for_another_task() -> None:
    minted_for = _linear_task()
    minted_for["task_id"] = "task-other-linear"
    assert minted_for["effect"] == "linear"
    graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=minted_for)
    row_task = _linear_task()
    assert row_task["effect"] == "linear"
    assert row_task["task_id"] != minted_for["task_id"]
    try:
        dataset_reward_row(graded, task=row_task, example_id="e1")
    except RewardProvenanceError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("a receipt minted for another task was accepted")
    try:
        reward_value(graded, row_task)
    except RewardProvenanceError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("reward_value scored a receipt against another task")
    unbound = grade_receipt(allowlisted_reward_envelope(passed=True))
    try:
        dataset_reward_row(unbound, task=row_task, example_id="e2")
    except RewardProvenanceError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("an unbound receipt was accepted")
    built = dataset_reward_row(graded, task=minted_for, example_id="e1")
    assert built["reward"] == 1.0
    built["task"] = row_task
    try:
        rl_batch([built])
    except RewardProvenanceError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("rl_batch accepted a swapped linear task")
    same = dict(minted_for)
    same["prompt"] = "a different prompt with the same id and effect"
    try:
        dataset_reward_row(graded, task=same, example_id="e3")
    except RewardProvenanceError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("a prompt change was accepted")
    shifted = dict(minted_for)
    shifted["effect"] = "time_invariant"
    try:
        dataset_reward_row(graded, task=shifted, example_id="e4")
    except RewardProvenanceError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("a rewardable effect change was accepted")


def test_rl_batch_refuses_a_duplicate_row() -> None:
    task = _linear_task()
    graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    row = dataset_reward_row(graded, task=task, example_id="e1")
    copied = dict(row)
    try:
        rl_batch([row, copied])
    except RewardProvenanceError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("rl_batch accepted a duplicate row")
    other = _linear_task()
    other["task_id"] = "task-other-linear"
    second = grade_receipt(allowlisted_reward_envelope(passed=False), task=other)
    other_row = dataset_reward_row(second, task=other, example_id="e2")
    assert len(rl_batch([row, other_row])) == 2


def test_rl_batch_refuses_an_identity_less_duplicate() -> None:
    task = _linear_task()
    graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    row = dataset_reward_row(graded, task=task)
    try:
        rl_batch([row, dict(row)])
    except RewardProvenanceError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("rl_batch accepted an identity-less duplicate")


def test_rl_batch_refuses_one_receipt_under_two_example_ids() -> None:
    task = _linear_task()
    graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    first = dataset_reward_row(graded, task=task, example_id="e1")
    second = dataset_reward_row(graded, task=task, example_id="e2")
    try:
        rl_batch([first, second])
    except RewardProvenanceError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("rl_batch accepted one receipt under two example ids")


def test_rl_batch_refuses_a_non_string_example_id() -> None:
    task = _linear_task()
    graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    row = dataset_reward_row(graded, task=task, example_id=7)
    try:
        rl_batch([row])
    except RewardProvenanceError as exc:
        assert "example_id" in str(exc)
    else:
        raise AssertionError("rl_batch accepted a non-string example_id")


def test_rl_batch_keeps_two_grades_of_the_same_program() -> None:
    task = _linear_task()
    envelope = allowlisted_reward_envelope(passed=True)
    first = dataset_reward_row(grade_receipt(envelope, task=task), task=task, example_id="e1")
    second = dataset_reward_row(grade_receipt(envelope, task=task), task=task, example_id="e2")
    assert len(rl_batch([first, second])) == 2


def test_rl_batch_keeps_two_grades_of_the_same_program_without_ids() -> None:
    task = _linear_task()
    envelope = allowlisted_reward_envelope(passed=True)
    first = dataset_reward_row(grade_receipt(envelope, task=task), task=task)
    second = dataset_reward_row(grade_receipt(envelope, task=task), task=task)
    assert "example_id" not in first
    assert "example_id" not in second
    assert len(rl_batch([first, second])) == 2


def test_unattributed_exits_stay_queued_until_triage() -> None:
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


def test_rerun_and_fixture_are_refused_and_do_not_score() -> None:
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
        called = {"rerun": 0, "fixture": 0}

        def rerun(_payload: dict, called: dict[str, int] = called) -> RerunOutcome:
            called["rerun"] += 1
            return _rerun(envelope)

        def known_good(called: dict[str, int] = called) -> FixtureOutcome:
            called["fixture"] += 1
            return FixtureOutcome(
                passed=True,
                environment_digest=envelope["payload"]["environment_digest"],
            )

        queue = QuarantineQueue()
        try:
            grade_receipt(
                envelope,
                diagnostics=diagnostics,
                rerun=rerun,
                known_good=known_good,
                policy="refused",
                queue=queue,
            )
        except AutoAttributionRefused as exc:
            assert "not sanctioned" in str(exc)
        else:
            raise AssertionError(f"exit {exit_code} accepted a rerun")
        assert called == {"rerun": 0, "fixture": 0}
        assert queue.count() == 0
        # Either hook alone is enough. The other is not called.
        try:
            grade_receipt(envelope, diagnostics=diagnostics, rerun=rerun, queue=queue)
        except AutoAttributionRefused:
            pass
        else:
            raise AssertionError(f"exit {exit_code} accepted rerun alone")
        assert called["rerun"] == 0


def test_fixture_failure_is_not_scored_and_harness_triage_is_separate() -> None:
    envelope = compiler_failure_envelope(
        exit_code=124,
        diagnostic_class="timeout",
        diagnostics="timeout: wall clock limit exceeded\n",
    )
    queue = QuarantineQueue()
    try:
        grade_receipt(
            envelope,
            diagnostics="timeout: wall clock limit exceeded\n",
            known_good=lambda: FixtureOutcome(
                passed=False,
                environment_digest=envelope["payload"]["environment_digest"],
            ),
            policy="infra",
            queue=queue,
        )
    except AutoAttributionRefused:
        pass
    else:
        raise AssertionError("a failing fixture was supplied to grading")
    assert queue.count("infra") == 0
    held = grade_receipt(
        envelope,
        diagnostics="timeout: wall clock limit exceeded\n",
        policy="infra",
        queue=queue,
    )
    assert isinstance(held, Ungraded)
    assert held.reason is UngradedReason.UNATTRIBUTED
    assert reward_value(held) is None
    assert queue.count("infra") == 1
    harness = grade_receipt(
        envelope,
        diagnostics="timeout: wall clock limit exceeded\n",
        triage="harness",
        policy="harness",
        queue=queue,
    )
    assert isinstance(harness, Ungraded)
    assert harness.reason is UngradedReason.UNATTRIBUTED
    assert reward_value(harness) is None
    assert queue.count("harness") == 1


def test_remote_import_is_source_and_stack_overflow_stays_unattributed() -> None:
    remote = "internal: remote import rejected\n"
    envelope = compiler_failure_envelope(
        exit_code=126, diagnostic_class="internal", diagnostics=remote
    )
    graded = grade_receipt(envelope, diagnostics=remote)
    assert isinstance(graded, SourceAttributedFailure)
    assert graded.detail == "remote import"
    called = {"rerun": 0}

    def rerun(_payload: dict) -> RerunOutcome:
        called["rerun"] += 1
        return _rerun(envelope)

    try:
        grade_receipt(
            envelope,
            diagnostics=remote,
            rerun=rerun,
            known_good=lambda: FixtureOutcome(passed=False),
        )
    except AutoAttributionRefused:
        pass
    else:
        raise AssertionError("a remote import accepted a rerun")
    assert called["rerun"] == 0
    stack_envelope = compiler_failure_envelope(
        exit_code=126,
        diagnostic_class="internal",
        diagnostics="internal: worker failed\n",
    )
    payload = dict(stack_envelope["payload"])
    payload["runtime_stack_overflow"] = True
    stack_envelope = make_envelope(
        payload, schema_version="0.3.2", producer="faustcoder.compiler"
    )
    queue = QuarantineQueue()
    stacked = grade_receipt(
        stack_envelope,
        diagnostics="internal: worker failed\n",
        policy="stack",
        queue=queue,
    )
    assert isinstance(stacked, Ungraded)
    assert stacked.reason is UngradedReason.UNATTRIBUTED
    assert reward_value(stacked) is None
    assert queue.count("stack") == 1
    prose = compiler_failure_envelope(
        exit_code=126,
        diagnostic_class="internal",
        diagnostics="RangeError: Maximum call stack size exceeded\n",
    )
    untagged = grade_receipt(
        prose, diagnostics="RangeError: Maximum call stack size exceeded\n"
    )
    assert isinstance(untagged, Ungraded)
    assert untagged.reason is UngradedReason.UNATTRIBUTED


def test_worker_crash_stays_unattributed_when_a_fixture_would_pass() -> None:
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
    try:
        grade_receipt(
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
    except AutoAttributionRefused:
        pass
    else:
        raise AssertionError("a healthy fixture scored a worker crash")
    assert queue.count("crash") == 1
    assert reward_value(pending) is None


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


def test_missing_environment_digest_is_not_a_grading_input() -> None:
    envelope = compiler_failure_envelope(
        exit_code=124,
        diagnostic_class="timeout",
        diagnostics="timeout: wall clock limit exceeded\n",
    )
    queue = QuarantineQueue()
    for rerun_digest, fixture_digest in ((None, None), ("", ""), (None, "sha256:" + "11" * 32)):
        try:
            grade_receipt(
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
        except AutoAttributionRefused:
            pass
        else:
            raise AssertionError("a rerun with a blank environment digest was graded")
    assert queue.count("env") == 0
    held = grade_receipt(
        envelope,
        diagnostics="timeout: wall clock limit exceeded\n",
        policy="env",
        queue=queue,
    )
    assert isinstance(held, Ungraded)
    assert held.reason is UngradedReason.UNATTRIBUTED
    assert reward_value(held) is None
    assert queue.count("env") == 1


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
    task = _linear_task()
    failed = grade_receipt(allowlisted_reward_envelope(passed=False), task=task)
    row = dataset_reward_row(failed, task=task, example_id="e1")
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
    passed = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    ok = dataset_reward_row(passed, task=task, example_id="e2")
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
    assert graded.test_suite_digest == (
        "sha256:e38d50f7345453e14c739fbfeccc7f561ec92c6cec71d181a888b250bcd2ddd0"
    )
    assert run.receipt["profile"]["version"] == 2
    assert run.receipt["metrics"]["compile_flags"] == ["-ftz", "0"]
    assert run.receipt["metrics"]["comparison"] == "reward-graded-signed-full"


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
            held_at="2026-10-17T00:00:00Z",
        )
    )
    source = queue.resolve(
        "row-source",
        attribution=TriageAttribution.SOURCE,
        triaged_by="danny",
        triaged_at="2026-10-17T12:00:00Z",
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
    for name in (
        "passed",
        "profile_name",
        "test_suite_digest",
        "reproducible_digest",
        "schema_version",
        "task_digest",
        "task_digest_full",
        "unrewardable",
    ):
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


def _native_stack_receipt(
    diagnostics: str,
    *,
    version: str = "2.88.0",
    compiler: str = "faust-cli",
    source: str = "ab" * 32,
    exit_code: int = 1,
    lang: str = "cpp",
    command: list[str] | None = None,
) -> dict:
    """A native CLI receipt. The stderr digest is ``diagnostics``."""
    return {
        "source_sha256": source,
        "faust_version": version,
        "command": ["faust", "-lang", "cpp"] if command is None else command,
        "exit_code": exit_code,
        "stdout_digest": "sha256:" + "00" * 32,
        "stderr_digest": "sha256:" + hashlib.sha256(diagnostics.encode("utf-8")).hexdigest(),
        "duration_ms": 1,
        "environment_digest": "sha256:" + "22" * 32,
        "compiler": compiler,
        "lang": lang,
        "options": [],
        "diagnostic_class": "parse_error" if exit_code == 1 else "internal",
    }


def test_compile_stack_lines_need_a_native_match() -> None:
    exact = "ERROR : stack overflow in eval\n"
    envelope = compiler_failure_envelope(
        exit_code=126, diagnostic_class="internal", diagnostics=exact
    )
    held = grade_receipt(envelope, diagnostics=exact)
    assert isinstance(held, Ungraded)
    assert held.reason is UngradedReason.UNATTRIBUTED
    assert reward_value(held) is None
    sealed = mint_native_stack_match(_native_stack_receipt(exact), exact)
    graded = grade_receipt(envelope, diagnostics=exact, native=sealed)
    assert isinstance(graded, SourceAttributedFailure)
    assert graded.detail == "stack overflow"
    raw = grade_receipt(
        envelope,
        diagnostics=exact,
        native=_native_stack_receipt(exact),
        native_diagnostics=exact,
    )
    assert isinstance(raw, Ungraded)
    assert raw.reason is UngradedReason.UNATTRIBUTED
    plain = "ERROR : stack overflow\n"
    plain_envelope = compiler_failure_envelope(
        exit_code=126, diagnostic_class="internal", diagnostics=plain
    )
    plain_sealed = mint_native_stack_match(_native_stack_receipt(plain), plain)
    plain_graded = grade_receipt(plain_envelope, diagnostics=plain, native=plain_sealed)
    assert isinstance(plain_graded, SourceAttributedFailure)
    assert plain_graded.detail == "stack overflow"
    cpp_command = mint_native_stack_match(
        _native_stack_receipt(exact, command=["faust", "--faust=2.88.0", "-lang", "cpp"]),
        exact,
    )
    cpp_graded = grade_receipt(envelope, diagnostics=exact, native=cpp_command)
    assert isinstance(cpp_graded, SourceAttributedFailure)
    assert cpp_graded.detail == "stack overflow"
    crossed = grade_receipt(envelope, diagnostics=exact, native=plain_sealed)
    assert isinstance(crossed, Ungraded)
    assert crossed.reason is UngradedReason.UNATTRIBUTED
    other = "ERROR : undefined symbol\n"
    other_envelope = compiler_failure_envelope(
        exit_code=126, diagnostic_class="internal", diagnostics=other
    )
    untouched = grade_receipt(other_envelope, diagnostics=other, native=sealed)
    assert isinstance(untouched, Ungraded)
    assert untouched.reason is UngradedReason.UNATTRIBUTED
    timed = compiler_failure_envelope(
        exit_code=124, diagnostic_class="timeout", diagnostics=exact
    )
    timeout_row = grade_receipt(timed, diagnostics=exact, native=sealed)
    assert isinstance(timeout_row, Ungraded)
    assert timeout_row.reason is UngradedReason.UNATTRIBUTED
    overflow = "ERROR : stack overflowing everything\n"
    refused = [
        (_native_stack_receipt(exact, version="2.90.0"), exact),
        (_native_stack_receipt(exact, compiler="libfaust-wasm"), exact),
        (_native_stack_receipt(exact, exit_code=0), exact),
        (_native_stack_receipt(exact, exit_code=124), exact),
        (_native_stack_receipt(exact, exit_code=125), exact),
        (_native_stack_receipt(exact, exit_code=126), exact),
        (_native_stack_receipt(exact, exit_code=137), exact),
        (_native_stack_receipt(exact, exit_code=139), exact),
        (_native_stack_receipt(exact, exit_code=-9), exact),
        (_native_stack_receipt(overflow), overflow),
        (_native_stack_receipt(exact, lang="wasm", command=["libfaust-wasm"]), exact),
        (_native_stack_receipt(exact, command=["faust", "-lang", "wasm"]), exact),
        (_native_stack_receipt(exact, command=["faust", "--faustwasm=1"]), exact),
    ]
    signaled = _native_stack_receipt(exact)
    signaled["termination_signal"] = 11
    refused.append((signaled, exact))
    extra = _native_stack_receipt(exact)
    extra["extra"] = True
    refused.append((extra, exact))
    for native, diagnostics in refused:
        try:
            mint_native_stack_match(native, diagnostics)
        except RewardProvenanceError:
            pass
        else:
            raise AssertionError(f"native receipt was minted: {native}")
        pending = grade_receipt(envelope, diagnostics=exact, native=native)
        assert isinstance(pending, Ungraded)
        assert pending.reason is UngradedReason.UNATTRIBUTED
    other_source = mint_native_stack_match(_native_stack_receipt(exact, source="cd" * 32), exact)
    reused = grade_receipt(envelope, diagnostics=exact, native=other_source)
    assert isinstance(reused, Ungraded)
    assert reused.reason is UngradedReason.UNATTRIBUTED
    for prose in (
        "error : stack overflow in eval\n",
        "note ERROR : stack overflow in eval\n",
        "internal: worker failed\ndeep recursion\n",
        "worker segfault\ndeep recursion\n",
    ):
        buried = compiler_failure_envelope(
            exit_code=126, diagnostic_class="internal", diagnostics=prose
        )
        pending = grade_receipt(buried, diagnostics=prose)
        assert isinstance(pending, Ungraded), prose
        assert pending.reason is UngradedReason.UNATTRIBUTED
    crash = make_envelope(
        {
            "kind": "worker_crash",
            "exit_code": 126,
            "diagnostic_class": "internal",
            "reproducible_digest": "sha256:" + "ab" * 32,
        },
        schema_version="0.3.2",
        producer="faustcoder.signal",
    )
    # A compile warning, even a line-start stack error, does not attribute
    # a later render crash. A native match does not either. A wasm trap
    # on the crash stays unattributed.
    later = grade_receipt(
        crash,
        diagnostics=exact,
        native=_native_stack_receipt(exact),
        native_diagnostics=exact,
    )
    assert isinstance(later, Ungraded)
    assert later.reason is UngradedReason.UNATTRIBUTED
    trap_payload = dict(
        compiler_failure_envelope(
            exit_code=126,
            diagnostic_class="internal",
            diagnostics="internal: worker failed\n",
        )["payload"]
    )
    trap_payload["wasm_trap"] = "unreachable"
    trap = make_envelope(trap_payload, schema_version="0.3.2", producer="faustcoder.compiler")
    queue = QuarantineQueue()
    trapped = grade_receipt(
        trap,
        diagnostics="internal: worker failed\n",
        policy="trap",
        queue=queue,
    )
    assert isinstance(trapped, Ungraded)
    assert trapped.reason is UngradedReason.UNATTRIBUTED
    assert reward_value(trapped) is None
    assert queue.count("trap") == 1


def test_shadow_observe_reruns_and_never_grades() -> None:
    exact = "ERROR : stack overflow in eval\n"
    envelope = compiler_failure_envelope(
        exit_code=126, diagnostic_class="internal", diagnostics=exact
    )
    called = {"rerun": 0, "fixture": 0}

    def rerun(_payload: dict) -> RerunOutcome:
        called["rerun"] += 1
        return _rerun(envelope)

    def fixture() -> FixtureOutcome:
        called["fixture"] += 1
        return FixtureOutcome(passed=True)

    sealed = mint_native_stack_match(_native_stack_receipt(exact), exact)
    log = shadow_observe(
        envelope,
        diagnostics=exact,
        rerun=rerun,
        known_good=fixture,
        native=sealed,
        native_diagnostics=exact,
    )
    assert called == {"rerun": 1, "fixture": 1}
    assert log.signature == "stack_line"
    assert "native Faust 2.88.0 stack match" in log.detail
    raw = shadow_observe(
        envelope,
        diagnostics=exact,
        native=_native_stack_receipt(exact),
        native_diagnostics=exact,
    )
    assert raw.signature == "stack_line"
    assert "native match absent" in raw.detail
    assert "rerun failed=True" in log.detail
    try:
        reward_value(log)
    except TypeError as exc:
        assert "shadow" in str(exc)
    else:
        raise AssertionError("a shadow log was scored")
    try:
        dataset_reward_row(log, task=_linear_task())
    except RewardProvenanceError:
        pass
    else:
        raise AssertionError("a shadow log became a reward row")
    try:
        rl_batch([{"task": _linear_task(), "reward": 0.0, "provenance": log}])
    except RewardProvenanceError:
        pass
    else:
        raise AssertionError("a shadow log entered an RL batch")
    called["rerun"] = 0
    try:
        grade_receipt(envelope, diagnostics=exact, rerun=rerun, known_good=fixture)
    except AutoAttributionRefused:
        pass
    else:
        raise AssertionError("grading accepted a shadow rerun")
    assert called["rerun"] == 0
    bare = shadow_observe(envelope, diagnostics=exact)
    assert bare.signature == "stack_line"
    assert bare.detail == "logged, not graded"
    try:
        reward_value(bare)
    except TypeError as exc:
        assert "shadow" in str(exc)
    else:
        raise AssertionError("an empty shadow log was scored")


def test_compile_stack_line_breaks_on_newline_only() -> None:
    assert _compile_stack_line("ERROR : stack overflow in eval\n")
    assert _compile_stack_line("ok\nERROR : stack overflow\n")
    assert _compile_stack_line("ERROR : stack overflow in eval\r\n")
    for separator in ("\u0085", "\u2028", "\r"):
        forged = f"note{separator}ERROR : stack overflow in eval\n"
        assert not _compile_stack_line(forged), repr(separator)
        buried = compiler_failure_envelope(
            exit_code=126, diagnostic_class="internal", diagnostics=forged
        )
        pending = grade_receipt(buried, diagnostics=forged)
        assert isinstance(pending, Ungraded), repr(separator)
        assert pending.reason is UngradedReason.UNATTRIBUTED


def test_range_error_is_stack_overflow_only_for_the_exact_message() -> None:
    script = r"""
import { terminationFields } from "./faust/worker/termination.mjs";
const exact = "Maximum call stack size exceeded";
const cases = [
  [new RangeError(exact), true, null],
  [new RangeError("Invalid array length"), false, null],
  [new RangeError(exact + " during render"), false, null],
  [new RangeError("maximum call stack size exceeded"), false, null],
  [new RangeError(exact + "\n"), false, null],
  [new TypeError(exact), false, null],
  [new RangeError("\u2028" + exact), false, null],
  [new RangeError(exact + "\u0085"), false, null],
  [new WebAssembly.RuntimeError("unreachable"), false, "unreachable"],
];
const failures = [];
for (const [error, stack, trap] of cases) {
  const fields = terminationFields(error);
  if (fields.runtime_stack_overflow !== stack || fields.wasm_trap !== trap) {
    failures.push(`${error.name} ${JSON.stringify(error.message)} ${JSON.stringify(fields)}`);
  }
}
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_injected_infra_crash_stays_unattributed_without_a_rerun() -> None:
    diagnostics = "internal: worker failed\n"
    envelope = compiler_failure_envelope(
        exit_code=126, diagnostic_class="internal", diagnostics=diagnostics
    )
    payload = dict(envelope["payload"])
    payload["termination_signal"] = 11
    envelope = make_envelope(payload, schema_version="0.3.2", producer="faustcoder.compiler")
    queue = QuarantineQueue()
    environment = envelope["payload"]["environment_digest"]
    try:
        grade_receipt(
            envelope,
            diagnostics=diagnostics,
            rerun=lambda _payload: RerunOutcome(
                failed=False,
                exit_code=0,
                diagnostic_class="ok",
                reproducible_digest=reproducible_receipt_digest(envelope["payload"]),
                environment_digest=environment,
            ),
            known_good=lambda: FixtureOutcome(passed=True, environment_digest=environment),
            policy="infra-crash",
            queue=queue,
        )
    except AutoAttributionRefused:
        pass
    else:
        raise AssertionError("a quiet rerun scored an injected crash")
    failed = grade_receipt(
        envelope,
        diagnostics=diagnostics,
        policy="infra-crash",
        queue=queue,
    )
    assert isinstance(failed, Ungraded)
    assert failed.reason is UngradedReason.UNATTRIBUTED
    assert reward_value(failed) is None
    assert queue.count("infra-crash") == 1


def test_source_over_one_mib_is_parse_error() -> None:
    from faustcoder.compiler import compile_source

    source = "process = _;\n" + (" " * (1024 * 1024))
    compiled = compile_source(source, lang="wasm")
    assert compiled.receipt["exit_code"] == 125
    assert compiled.receipt["diagnostic_class"] == "resource_limit"
    assert compiled.diagnostics == "resource limit: source size\n"
    envelope = make_envelope(
        compiled.receipt, schema_version="0.3.2", producer="faustcoder.compiler"
    )
    graded = grade_receipt(envelope, diagnostics=compiled.diagnostics)
    assert isinstance(graded, SourceAttributedFailure)
    assert graded.rung == "parse_error"
    assert graded.detail == "source size"
    assert reward_value(graded) == 0.0
    try:
        grade_receipt(
            envelope,
            diagnostics=compiled.diagnostics,
            known_good=lambda: FixtureOutcome(passed=False),
        )
    except AutoAttributionRefused:
        pass
    else:
        raise AssertionError("source size accepted a fixture")


def test_triage_refuses_a_timestamp_earlier_than_the_hold(tmp_path) -> None:
    queue = QuarantineQueue()
    queue.hold(
        QuarantineRecord(
            policy="signal",
            reason=UngradedReason.UNATTRIBUTED,
            reproducible_digest="sha256:" + "ab" * 32,
            record_id="row-1",
            held_at="2026-10-17T12:00:00Z",
        )
    )
    try:
        queue.resolve(
            "row-1",
            attribution=TriageAttribution.INFRASTRUCTURE,
            triaged_by="ada",
            triaged_at="2026-10-17T11:00:00Z",
        )
    except ValueError as exc:
        assert "earlier than the quarantine hold" in str(exc)
    else:
        raise AssertionError("a triage earlier than the hold was accepted")
    assert queue.count() == 1
    graded = queue.resolve(
        "row-1",
        attribution=TriageAttribution.INFRASTRUCTURE,
        triaged_by="ada",
        triaged_at="2026-10-17T12:00:00Z",
    )
    assert isinstance(graded, Ungraded)
    assert queue.count() == 0
    path = tmp_path / "early.jsonl"
    path.write_text(
        _quarantine_log(
            _held_timeout(),
            _resolve_line(
                attribution="infrastructure",
                outcome="drop",
                evidence="",
                triaged_at="2019-01-01T00:00:00Z",
            ),
        ),
        encoding="utf-8",
    )
    try:
        QuarantineQueue(path)
    except ValueError as exc:
        assert "earlier than the quarantine hold" in str(exc)
    else:
        raise AssertionError("a replayed triage earlier than the hold was accepted")


def test_plain_stack_overflow_at_exit_1_needs_a_sealed_native_match() -> None:
    plain = "ERROR : stack overflow\n"
    envelope = compiler_failure_envelope(
        exit_code=1, diagnostic_class="other", diagnostics=plain
    )
    queue = QuarantineQueue()
    held = grade_receipt(envelope, diagnostics=plain, policy="plain-stack", queue=queue)
    assert isinstance(held, Ungraded)
    assert held.reason is UngradedReason.UNATTRIBUTED
    assert reward_value(held) is None
    assert queue.count("plain-stack") == 1
    assert queue.pending("plain-stack")[0].reward is None
    raw = grade_receipt(
        envelope,
        diagnostics=plain,
        native=_native_stack_receipt(plain),
        native_diagnostics=plain,
    )
    assert isinstance(raw, Ungraded)
    assert raw.reason is UngradedReason.UNATTRIBUTED
    sealed = mint_native_stack_match(_native_stack_receipt(plain), plain)
    graded = grade_receipt(envelope, diagnostics=plain, native=sealed)
    assert isinstance(graded, SourceAttributedFailure)
    assert graded.detail == "stack overflow"
    assert reward_value(graded) == 0.0
    ordinary = compiler_failure_envelope(
        exit_code=1,
        diagnostic_class="parse_error",
        diagnostics="syntax error\n",
    )
    scored = grade_receipt(ordinary, diagnostics="syntax error\n")
    assert isinstance(scored, SourceAttributedFailure)
    assert scored.detail == "compiler rejection"
    assert reward_value(scored) == 0.0


def test_triage_string_cannot_score_an_unattributed_exit() -> None:
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
        graded = grade_receipt(
            envelope,
            diagnostics=diagnostics,
            triage="source",
            policy="string-triage",
            queue=queue,
        )
        assert isinstance(graded, Ungraded), exit_code
        assert graded.reason is UngradedReason.UNATTRIBUTED
        assert reward_value(graded) is None
        assert queue.count("string-triage") == 1
        decision = TriageDecision(
            attribution=TriageAttribution.SOURCE,
            triaged_by="ada",
            evidence="rerun plus a known-good fixture",
        )
        recorded = grade_receipt(
            envelope,
            diagnostics=diagnostics,
            triage=decision,
            policy="recorded-triage",
            queue=queue,
        )
        assert isinstance(recorded, Ungraded), exit_code
        assert recorded.reason is UngradedReason.UNATTRIBUTED
        assert reward_value(recorded) is None
    crash = make_envelope(
        {
            "kind": "worker_crash",
            "exit_code": 126,
            "diagnostic_class": "internal",
            "reproducible_digest": "sha256:" + "ab" * 32,
        },
        schema_version="0.3.2",
        producer="faustcoder.signal",
    )
    crashed = grade_receipt(crash, triage="source", policy="string-crash", queue=QuarantineQueue())
    assert isinstance(crashed, Ungraded)
    assert crashed.reason is UngradedReason.UNATTRIBUTED
    assert reward_value(crashed) is None


def test_signal_killed_native_compile_stays_ungraded() -> None:
    diagnostics = "compiler returned failure\n"
    envelope = compiler_failure_envelope(
        exit_code=1, diagnostic_class="other", diagnostics=diagnostics
    )
    payload = dict(envelope["payload"])
    payload["compiler"] = "faust-cli"
    payload["lang"] = "cpp"
    payload["faust_version"] = "2.88.0"
    payload["command"] = ["faust", "-lang", "cpp"]
    quiet = make_envelope(payload, schema_version="0.3.2", producer="faustcoder.compiler")
    scored = grade_receipt(quiet, diagnostics=diagnostics)
    assert isinstance(scored, SourceAttributedFailure)
    assert scored.detail == "compiler rejection"
    assert reward_value(scored) == 0.0
    payload["termination_signal"] = 11
    killed = make_envelope(payload, schema_version="0.3.2", producer="faustcoder.compiler")
    queue = QuarantineQueue()
    held = grade_receipt(killed, diagnostics=diagnostics, policy="signal-kill", queue=queue)
    assert isinstance(held, Ungraded)
    assert held.reason is UngradedReason.UNATTRIBUTED
    assert reward_value(held) is None
    assert queue.count("signal-kill") == 1
    plain = "ERROR : stack overflow\n"
    stack_payload = dict(
        compiler_failure_envelope(
            exit_code=1, diagnostic_class="other", diagnostics=plain
        )["payload"]
    )
    stack_payload["termination_signal"] = 11
    stack_payload["compiler"] = "faust-cli"
    stack_payload["lang"] = "cpp"
    stack_payload["command"] = ["faust", "-lang", "cpp"]
    stack_envelope = make_envelope(
        stack_payload, schema_version="0.3.2", producer="faustcoder.compiler"
    )
    sealed = mint_native_stack_match(_native_stack_receipt(plain), plain)
    still = grade_receipt(stack_envelope, diagnostics=plain, native=sealed, queue=queue)
    assert isinstance(still, Ungraded)
    assert still.reason is UngradedReason.UNATTRIBUTED
    assert reward_value(still) is None


def test_native_mint_rejects_exit_codes_that_are_not_exact_ints() -> None:
    class ExitCode(int):
        pass

    exact = "ERROR : stack overflow\n"
    base = _native_stack_receipt(exact)
    for bad in (1.0, True, False, ExitCode(1)):
        forged = dict(base)
        forged["exit_code"] = bad
        try:
            mint_native_stack_match(forged, exact)
        except RewardProvenanceError as exc:
            assert "exit 1" in str(exc)
        else:
            raise AssertionError(f"native match minted exit_code {bad!r}")
    minted = mint_native_stack_match(base, exact)
    assert minted.stack_line == "ERROR : stack overflow"


def test_native_command_checks_every_lang_flag() -> None:
    exact = "ERROR : stack overflow in eval\n"
    slipped = _native_stack_receipt(
        exact, command=["faust", "-lang", "cpp", "-lang", "wasm"]
    )
    repeated = _native_stack_receipt(
        exact, command=["faust", "-lang", "cpp", "-lang", "cpp"]
    )
    omitted = _native_stack_receipt(exact, command=["faust"])
    for native in (slipped, repeated, omitted):
        try:
            mint_native_stack_match(native, exact)
        except RewardProvenanceError as exc:
            assert "cpp" in str(exc)
        else:
            raise AssertionError(f"native match minted command {native['command']}")
    mint_native_stack_match(_native_stack_receipt(exact), exact)
    mint_native_stack_match(
        _native_stack_receipt(exact, command=["faust", "-lang", "cpp"]), exact
    )


def test_apply_signal_refuses_an_unrewardable_mint() -> None:
    linear = _linear_task()
    allowed = grade_receipt(allowlisted_reward_envelope(passed=True), task=linear)
    assert apply_signal(CandidateState.COMPILE_CHECKED, allowed) is CandidateState.SIGNAL_CHECKED
    for effect in ("nonlinear", "time_variant"):
        task = _linear_task()
        task["effect"] = effect
        minted = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
        assert isinstance(minted, RewardableSignalReceipt)
        assert is_minted(minted)
        assert minted.unrewardable is True
        try:
            apply_signal(CandidateState.COMPILE_CHECKED, minted)
        except TypeError as exc:
            assert "unrewardable" in str(exc)
        else:
            raise AssertionError(f"apply_signal accepted {effect}")
    via_tuple = _linear_task()
    profile = dict(via_tuple["test_profile"])
    profile["classes"] = ("nonlinear",)
    via_tuple["test_profile"] = profile
    minted = grade_receipt(allowlisted_reward_envelope(passed=False), task=via_tuple)
    assert minted.unrewardable is True
    try:
        apply_signal(CandidateState.COMPILE_CHECKED, minted)
    except TypeError as exc:
        assert "unrewardable" in str(exc)
    else:
        raise AssertionError("apply_signal accepted a tuple class")


def test_harness_triage_drops_a_remote_import_score() -> None:
    remote = "internal: remote import rejected\n"
    envelope = compiler_failure_envelope(
        exit_code=126, diagnostic_class="internal", diagnostics=remote
    )
    kept = grade_receipt(envelope, diagnostics=remote)
    assert isinstance(kept, SourceAttributedFailure)
    assert kept.detail == "remote import"
    assert reward_value(kept) == 0.0
    bare = grade_receipt(envelope, diagnostics=remote, triage="harness")
    assert isinstance(bare, SourceAttributedFailure)
    assert reward_value(bare) == 0.0
    decision = TriageDecision(
        attribution=TriageAttribution.HARNESS,
        triaged_by="ada",
        evidence="pre-filter false positive on a local import",
    )
    queue = QuarantineQueue()
    dropped = grade_receipt(
        envelope,
        diagnostics=remote,
        triage=decision,
        policy="remote-harness",
        queue=queue,
    )
    assert isinstance(dropped, Ungraded)
    assert dropped.reason is UngradedReason.HARNESS_DEFECT
    assert reward_value(dropped) is None
    assert "ada" in dropped.detail
    assert "local import" in dropped.detail
    assert queue.count("remote-harness") == 1
    assert queue.pending("remote-harness")[0].reward is None
    oversized = "resource limit: source size\n"
    size_envelope = compiler_failure_envelope(
        exit_code=125, diagnostic_class="resource_limit", diagnostics=oversized
    )
    size_decision = TriageDecision(
        attribution=TriageAttribution.INFRASTRUCTURE,
        triaged_by="mina",
        evidence="counter measured the harness copy, not the source",
    )
    size_dropped = grade_receipt(size_envelope, diagnostics=oversized, triage=size_decision)
    assert isinstance(size_dropped, Ungraded)
    assert size_dropped.reason is UngradedReason.INFRA_FAULT
    assert reward_value(size_dropped) is None
    assert "mina" in size_dropped.detail


def test_rate_tracker_reload_keeps_its_baseline() -> None:
    source = UngradedRateTracker(baseline=0.01)
    source.observe("policy", ungraded=True)
    assert source.alarm("policy")
    copy = UngradedRateTracker()
    copy.load_state(source.export_state())
    assert copy.baseline == 0.01
    assert copy.alarm("policy") is True
    assert copy.rate("policy") == source.rate("policy")
    cleared = UngradedRateTracker(baseline=0.2)
    payload = source.export_state()
    payload["baseline"] = None
    cleared.load_state(payload)
    assert cleared.baseline is None
    assert cleared.alarm("policy") is False


def test_provably_dead_grader_helpers_are_gone() -> None:
    import inspect

    import faustcoder.reward.grader as grader

    assert not hasattr(grader, "reward_profile_allowlist")
    assert "stage" not in inspect.signature(grader._source_tag).parameters

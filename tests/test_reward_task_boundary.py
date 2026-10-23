"""Additional regression checks for task-bound reward consumption.

These tests protect the existing grader contract without modifying its API.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from faustcoder.errors import SchemaValidationError
from faustcoder.signal import SignalHarnessError

from faustcoder.reward import (
    RewardProvenanceError,
    RewardableSignalReceipt,
    grade_receipt,
    reward_value,
)
from tests.support import allowlisted_reward_envelope


def _task() -> dict:
    path = Path(__file__).parent / "fixtures/valid/task-spec.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_unbound_low_level_receipt_cannot_be_consumed() -> None:
    graded = grade_receipt(allowlisted_reward_envelope(passed=True))
    assert isinstance(graded, RewardableSignalReceipt)
    with pytest.raises(RewardProvenanceError):
        reward_value(graded, _task())


def test_task_mutation_after_mint_refuses_reward() -> None:
    task = _task()
    graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    changed = copy.deepcopy(task)
    changed["prompt"] = str(changed.get("prompt", "")) + " modified"
    with pytest.raises(RewardProvenanceError):
        reward_value(graded, changed)


def test_task_effect_change_after_mint_refuses_reward() -> None:
    task = _task()
    graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    changed = copy.deepcopy(task)
    changed["effect"] = "nonlinear"
    with pytest.raises(RewardProvenanceError):
        reward_value(graded, changed)


def test_correct_task_can_consume_bound_receipt() -> None:
    task = _task()
    graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    assert reward_value(graded, task) == 1.0



def _suite():
    from faustcoder.compiler import Compilation, reproducible_receipt_digest
    from faustcoder.reward.grader import task_digest_full
    from faustcoder.signal import SignalRun, SignalSuite, reproducible_signal_digest
    from tests.test_reward_grader import compiler_failure_envelope
    payload = compiler_failure_envelope(exit_code=0, diagnostic_class='ok', diagnostics='')['payload']
    signal = allowlisted_reward_envelope(passed=True)['payload']
    return SignalSuite(runs=(SignalRun(
        compilation=Compilation(receipt=payload, diagnostics='',
                                reproducible_digest=reproducible_receipt_digest(payload)),
        receipt=signal, reproducible_digest=reproducible_signal_digest(signal),
        failures=(), reference_payload=None, reward_task_digest=task_digest_full(_task())),))


def _commit(store, suite, task):
    from faustcoder.candidate_machine import CandidateState
    from faustcoder.signal import commit_signal_check
    return commit_signal_check(store, suite, state=CandidateState.COMPILE_CHECKED,
                               created_at='2026-10-23T00:00:00Z', task=task)


@pytest.mark.parametrize('task', [None, {}, {'effect': 'linear'}, 'invalid'])
def test_commit_invalid_task_writes_nothing(store, task):
    with pytest.raises((RewardProvenanceError, SchemaValidationError)): _commit(store, _suite(), task)
    assert list(store.list()) == []


def test_commit_changed_task_writes_nothing(store):
    task = _task()
    task['prompt'] += ' changed'
    with pytest.raises(RewardProvenanceError, match='binding'):
        _commit(store, _suite(), task)
    assert list(store.list()) == []


def test_commit_valid_task_can_consume(store):
    outcome = _commit(store, _suite(), _task()).outcomes[0]
    assert reward_value(outcome, _task()) == 1.0


def test_mixed_suite_refused_before_writes(store):
    from dataclasses import replace
    suite = _suite()
    diagnostic = copy.deepcopy(suite.runs[0].receipt)
    diagnostic['purpose'] = 'diagnostic'
    suite = replace(suite, runs=(*suite.runs, replace(suite.runs[0], receipt=diagnostic)))
    with pytest.raises(SignalHarnessError, match='mix'): _commit(store, suite, _task())
    assert list(store.list()) == []


def test_invalid_reward_provenance_refused_before_writes(store):
    suite = _suite()
    suite.runs[0].receipt['test_suite_digest'] = 'sha256:' + '0'*64
    with pytest.raises(RewardProvenanceError, match='provenance'):
        _commit(store, suite, _task())
    assert list(store.list()) == []


@pytest.mark.parametrize('task', [None, {}, {'effect': 'linear'}, {'effect': 'nonlinear'}])
def test_run_task_validation_precedes_execution(monkeypatch, task):
    from faustcoder.signal import SignalProfile, run_signal
    def forbidden(*a, **k): raise AssertionError('compiler must not run')
    monkeypatch.setattr('faustcoder.signal.compile_source', forbidden)
    with pytest.raises((RewardProvenanceError, SchemaValidationError, SignalHarnessError)) as exc:
        run_signal('process = _;', SignalProfile(sample_rate=48000), reward_graded=True, task=task)
    assert not isinstance(exc.value, AssertionError)


def test_valid_nonlinear_task_refused_before_execution(monkeypatch):
    from faustcoder.signal import SignalProfile, run_signal
    task = _task()
    task['effect'] = 'nonlinear'
    def forbidden(*a, **k): raise AssertionError('compiler must not run')
    monkeypatch.setattr('faustcoder.signal.compile_source', forbidden)
    with pytest.raises((RewardProvenanceError, SchemaValidationError, SignalHarnessError)) as exc:
        run_signal('process = _;', SignalProfile(sample_rate=48000), reward_graded=True, task=task)
    assert not isinstance(exc.value, AssertionError)


@pytest.mark.parametrize('exit_code,diagnostics,diagnostic_class', [
    (124, 'timeout\n', 'timeout'), (125, 'resource limit\n', 'resource_limit'),
    (126, 'internal\n', 'internal'), (126, 'ERROR : stack overflow in eval\n', 'internal'),
])
def test_deferred_failure_task_binding_and_quarantine(store, monkeypatch, tmp_path,
                                                       exit_code, diagnostics, diagnostic_class):
    from faustcoder.compiler import Compilation, reproducible_receipt_digest
    from faustcoder.reward import RewardLedger, Ungraded
    from faustcoder.signal import run_signal_suite
    from tests.support import compiler_failure_envelope
    payload = compiler_failure_envelope(exit_code=exit_code, diagnostic_class=diagnostic_class,
                                       diagnostics=diagnostics)['payload']
    compiled = Compilation(receipt=payload, diagnostics=diagnostics,
                           reproducible_digest=reproducible_receipt_digest(payload))
    monkeypatch.setattr('faustcoder.signal.compile_source', lambda *a, **k: compiled)
    ledger = RewardLedger(tmp_path/'ledger')
    suite = run_signal_suite('process = _;', lambda p: None, sample_rates=(48000,),
                             frames=64, reward_graded=True, task=_task(), ledger=ledger)
    committed = _commit(store, suite, _task())
    assert len(committed.outcomes) == 1 and isinstance(committed.outcomes[0], Ungraded)
    assert ledger.queue.count('signal') == 1


@pytest.mark.parametrize('native_kind', ['sealed', 'raw', 'wrong_source', 'absent'])
def test_native_match_propagated_immediately_and_on_commit(store, monkeypatch, tmp_path, native_kind):
    from faustcoder.compiler import Compilation, reproducible_receipt_digest
    from faustcoder.reward import RewardLedger, RewardOutcomeHeld, SourceAttributedFailure, Ungraded
    from faustcoder.reward.grader import mint_native_stack_match
    from faustcoder.signal import SignalProfile, run_signal, run_signal_suite
    from tests.test_reward_grader import _native_stack_receipt
    from tests.support import compiler_failure_envelope
    diagnostics = 'ERROR : stack overflow in eval\n'
    payload = compiler_failure_envelope(exit_code=126, diagnostic_class='internal', diagnostics=diagnostics)['payload']
    compiled = Compilation(receipt=payload, diagnostics=diagnostics,
                           reproducible_digest=reproducible_receipt_digest(payload))
    monkeypatch.setattr('faustcoder.signal.compile_source', lambda *a, **k: compiled)
    raw = _native_stack_receipt(diagnostics, source='cd'*32 if native_kind == 'wrong_source' else 'ab'*32)
    native = None if native_kind == 'absent' else raw if native_kind == 'raw' else mint_native_stack_match(raw, diagnostics)
    ledger = RewardLedger(tmp_path/'ledger')
    expected = SourceAttributedFailure if native_kind == 'sealed' else Ungraded
    with pytest.raises(RewardOutcomeHeld) as held:
        run_signal('process = _;', SignalProfile(sample_rate=48000), reward_graded=True,
                   task=_task(), native=native, ledger=ledger)
    assert isinstance(held.value.grade, expected)
    suite = run_signal_suite('process = _;', lambda p: None, sample_rates=(48000,),
                            frames=64, reward_graded=True, task=_task(), native=native, ledger=ledger)
    assert isinstance(_commit(store, suite, _task()).outcomes[0], expected)


def test_diagnostic_execution_needs_no_task(monkeypatch):
    from faustcoder.signal import SignalProfile, run_signal
    from dataclasses import replace
    suite = _suite()
    expected = replace(suite.runs[0], reward_task_digest=None)
    monkeypatch.setattr('faustcoder.signal._run_signal', lambda *a, **k: expected)
    assert run_signal('process = _;', SignalProfile(sample_rate=48000)).reward_task_digest is None


def test_invalid_compiler_provenance_refused_before_writes(store):
    suite = _suite()
    suite.runs[0].compilation.receipt['stderr_digest'] = 'sha256:'+'f'*64
    with pytest.raises(RewardProvenanceError, match='compiler provenance'):
        _commit(store, suite, _task())
    assert list(store.list()) == []


def test_signal_compiler_source_mismatch_refused_before_writes(store):
    suite = _suite()
    suite.runs[0].receipt['source_sha256'] = 'cd'*32
    with pytest.raises(RewardProvenanceError, match='source mismatch'):
        _commit(store, suite, _task())
    assert list(store.list()) == []

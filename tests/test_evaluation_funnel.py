"""QR-08 fixture-only fail-early stage and immutable evidence tests."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from faustcoder.canonical import content_digest_for
from faustcoder.compiler import Compilation, reproducible_receipt_digest
from faustcoder.evaluation_funnel import evaluate
from faustcoder.inventory import parse_corpus
from faustcoder.signal import SignalRun, SignalSuite, reproducible_signal_digest
from tests.support import compiler_failure_envelope
from tests.t06support import cleared, inventory_doc, notice_doc, pins_for

SOURCE = b'process = _;\n'
STAMP = '2026-10-23T00:00:00Z'


@pytest.fixture
def inputs():
    entry, notice = cleared('public', SOURCE)
    inventory, notices = inventory_doc([entry]), notice_doc([notice])
    with pins_for(inventory, notices):
        unit = parse_corpus(inventory, notices).units[0]
        yield dict(source=SOURCE, unit_id=unit.unit_id, inventory=inventory, notice=notices,
                   task=json.loads((Path(__file__).parent/'fixtures/valid/task-spec.json').read_text()),
                   reference_for=lambda p: None, reference_digest=content_digest_for({'analytical': 'wire'}),
                   created_at=STAMP)


def compiled(exit_code=0, diagnostic_class='ok'):
    receipt = compiler_failure_envelope(exit_code=exit_code, diagnostic_class=diagnostic_class,
                                        diagnostics='')['payload']
    receipt['source_sha256'] = hashlib.sha256(SOURCE).hexdigest()
    receipt['command'] = ['libfaust-wasm', '--faustwasm=0.19.0']
    return Compilation(receipt=receipt, diagnostics='', reproducible_digest=reproducible_receipt_digest(receipt))


def diagnostic_suite(passed=True):
    fixture = json.loads((Path(__file__).parent/'fixtures/valid/dsp-test-receipt.json').read_text())
    runs = []
    for rate in (44100,48000):
        receipt = copy.deepcopy(fixture)
        receipt.update(sample_rate=rate, source_sha256=hashlib.sha256(SOURCE).hexdigest(), passed=passed)
        runs.append(SignalRun(compilation=compiled(), receipt=receipt,
                              reproducible_digest=reproducible_signal_digest(receipt),
                              failures=() if passed else ('reference_mismatch',), reference_payload=None))
    return SignalSuite(runs=tuple(runs))


def forbid(*a, **k):
    raise AssertionError('later stage must not run')


def test_invalid_task_stops_before_compile(store, inputs, monkeypatch):
    inputs['task'] = {}
    monkeypatch.setattr('faustcoder.evaluation_funnel.compile_source', forbid)
    result = evaluate(store, **inputs)
    assert result['stages'] == [dict(stage='static',status='BLOCKED',receipt=result['stages'][0]['receipt'])]
    assert len(list(store.list())) == 1


@pytest.mark.parametrize('change', ['blob', 'unit', 'rights', 'notice', 'reference'])
def test_source_eligibility_stops_compute(store, inputs, monkeypatch, change):
    if change == 'blob': inputs['source'] += b'//changed'
    if change == 'unit': inputs['unit_id'] = 'unknown'
    if change == 'rights': inputs['inventory']['entries'][0]['decision'] = 'needs_human'
    if change == 'notice': inputs['notice']['entries'] = []
    if change == 'reference': inputs['reference_digest'] = 'PASS'
    monkeypatch.setattr('faustcoder.evaluation_funnel.compile_source', forbid)
    assert evaluate(store, **inputs)['stages'][-1]['stage'] == 'static'
    assert evaluate(store, **inputs)['status'] == 'BLOCKED'


def test_compiler_failure_stops_signal(store, inputs, monkeypatch):
    monkeypatch.setattr('faustcoder.evaluation_funnel.compile_source', lambda *a,**k: compiled(1,'parse_error'))
    monkeypatch.setattr('faustcoder.evaluation_funnel.run_signal_suite', forbid)
    result = evaluate(store, **inputs)
    assert [s['stage'] for s in result['stages']] == ['static','compiler']
    assert result['status'] == 'FAIL'


def test_wrong_compiler_identity_is_blocked(store, inputs, monkeypatch):
    wrong = compiled()
    wrong.receipt['command'] = ['libfaust-wasm','--faustwasm=0.18.0']
    monkeypatch.setattr('faustcoder.evaluation_funnel.compile_source', lambda *a,**k: wrong)
    monkeypatch.setattr('faustcoder.evaluation_funnel.run_signal_suite', forbid)
    result = evaluate(store, **inputs)
    assert result['status'] == 'BLOCKED'
    assert result['stages'][-1]['stage'] == 'compiler'


def test_signal_failure_prevents_independent_stage(store, inputs, monkeypatch):
    monkeypatch.setattr('faustcoder.evaluation_funnel.compile_source', lambda *a,**k: compiled())
    monkeypatch.setattr('faustcoder.evaluation_funnel.run_signal_suite', lambda *a,**k: diagnostic_suite(False))
    result = evaluate(store, **inputs)
    assert [s['stage'] for s in result['stages']] == ['static','compiler','signal']
    assert result['status'] == 'FAIL'


def test_successful_diagnostics_still_need_independent_replay(store, inputs, monkeypatch):
    monkeypatch.setattr('faustcoder.evaluation_funnel.compile_source', lambda *a,**k: compiled())
    def signal(*args, **kwargs):
        assert kwargs['sample_rates'] == (44100,48000)
        assert kwargs['require_reference'] is True
        assert kwargs['head_frames'] == kwargs['frames']
        return diagnostic_suite()
    monkeypatch.setattr('faustcoder.evaluation_funnel.run_signal_suite', signal)
    result = evaluate(store, **inputs)
    assert [s['status'] for s in result['stages']] == ['PASS','PASS','PASS','BLOCKED']
    assert not result['training_authorized'] and not result['promotion_allowed']
    previous = None
    for stage in result['stages']:
        envelope = store.get(stage['receipt'])
        assert envelope['payload']['diagnostic_only']
        if previous is not None: assert previous in envelope['parents']
        previous = stage['receipt']
        for parent in envelope['parents']: store.get(parent)
    static = store.get(result['stages'][0]['receipt'])['payload']
    assert static['source_digest'] == 'sha256:'+hashlib.sha256(SOURCE).hexdigest()
    assert SOURCE.decode() not in json.dumps(static)


def test_compiler_infrastructure_failure_is_not_model_failure(store, inputs, monkeypatch):
    from faustcoder.sandbox import SandboxError
    def broken(*args, **kwargs): raise SandboxError('namespace unavailable')
    monkeypatch.setattr('faustcoder.evaluation_funnel.compile_source', broken)
    monkeypatch.setattr('faustcoder.evaluation_funnel.run_signal_suite', forbid)
    result = evaluate(store, **inputs)
    assert result['status'] == 'BLOCKED'
    assert result['stages'][-1]['stage'] == 'compiler'


def test_missing_signal_rate_is_not_pass(store, inputs, monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr('faustcoder.evaluation_funnel.compile_source', lambda *a,**k: compiled())
    suite = diagnostic_suite()
    monkeypatch.setattr('faustcoder.evaluation_funnel.run_signal_suite',
                        lambda *a,**k: replace(suite, runs=suite.runs[:1]))
    result = evaluate(store, **inputs)
    assert result['status'] == 'BLOCKED'
    assert result['stages'][-1]['stage'] == 'signal'


def test_signal_infrastructure_failure_remains_blocked(store, inputs, monkeypatch):
    from faustcoder.signal import SignalHarnessError
    monkeypatch.setattr('faustcoder.evaluation_funnel.compile_source', lambda *a,**k: compiled())
    def broken(*args, **kwargs): raise SignalHarnessError('worker failed')
    monkeypatch.setattr('faustcoder.evaluation_funnel.run_signal_suite', broken)
    assert evaluate(store, **inputs)['status'] == 'BLOCKED'


def test_retries_have_distinct_attempt_receipts(store, inputs, monkeypatch):
    monkeypatch.setattr('faustcoder.evaluation_funnel.compile_source', lambda *a,**k: compiled(1,'parse_error'))
    first = evaluate(store, **inputs)
    inputs['created_at'] = '2026-10-23T00:01:00Z'
    second = evaluate(store, **inputs)
    assert first['stages'][0]['receipt'] != second['stages'][0]['receipt']
    store.get(first['stages'][0]['receipt'])
    store.get(second['stages'][0]['receipt'])

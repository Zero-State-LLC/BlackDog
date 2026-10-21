"""Diagnostic tooling must never turn partial evidence into production approval."""
from dataclasses import replace
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from diagnostics import span_review as review
from faustcoder.canonical import canonical_bytes, sha256_prefixed
from faustcoder.errors import CanonicalError, InventoryError
from faustcoder.function_spans import VERSION, verify_manifest
from faustcoder.inventory import parse_corpus

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def corpus_base():
    return parse_corpus(review.read_json(ROOT / 'corpus/rights-inventory.v1.json'),
                          review.read_json(ROOT / 'corpus/notice-manifest.v1.json'))


@pytest.fixture
def sample(tmp_path, corpus_base):
    corpus = corpus_base
    raw = b'// UTF-8: \xc3\xa9; comment\r\nalpha(0)=0;\r\nalpha(x)=x;\r\nbeta=alpha;\r\n'
    sha = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    template = next(u for u in corpus.units if u.function)
    units = tuple(replace(template, unit_id=name, function=fn, path='sample.lib', blob_sha=sha)
                  for name, fn in [('u1', 'alpha@2'), ('u2', 'alpha@3'), ('u3', 'beta')])
    corpus = replace(corpus, units=units)
    rows = []
    for unit, literal in zip(units, (b'alpha(0)=0;', b'alpha(x)=x;')):
        row = {k: getattr(unit, k) for k in ('unit_id', 'repo', 'pin', 'path', 'blob_sha', 'function')}
        row.update(start_byte=raw.index(literal), end_byte=raw.index(literal)+len(literal), sha256=sha256_prefixed(literal))
        rows.append(row)
    candidate = dict(schema_version=VERSION, inventory_digest=corpus.inventory_digest,
                     notice_digest=corpus.notice_digest, reviewer='UNAPPROVED', spans=rows)
    file = tmp_path / 'source.lib'
    file.write_bytes(raw)
    return corpus, candidate, {sha: raw}, {sha: str(file)}


def test_packets_deterministic_and_never_approve(sample):
    corpus, candidate, blobs, _ = sample
    a = review.packet_bundle(corpus, candidate, blobs)
    b = review.packet_bundle(replace(corpus, units=tuple(reversed(corpus.units))), candidate, blobs)
    assert canonical_bytes(a) == canonical_bytes(b)
    assert a['counts'] == {'admitted_functions': 3, 'proposed': 2, 'pending': 1}
    assert a['packets'][0]['overload_siblings'] == ['u1', 'u2']
    assert a['packets'][2]['candidate_span'] is None
    assert all(not x['production_approved'] for x in a['packets'])
    assert a['exclusions']  # Existing quarantine dispositions retained.
    with pytest.raises(InventoryError, match='missing function spans'):
        verify_manifest(candidate, sha256_prefixed(canonical_bytes(candidate)), corpus.units,
                        corpus.inventory_digest, corpus.notice_digest)


def test_sources_reject_stale_and_missing(sample):
    corpus, _, blobs, paths = sample
    assert review.load_sources(corpus, paths) == blobs
    with pytest.raises(InventoryError, match='missing local source'):
        review.load_sources(corpus, {})
    Path(next(iter(paths.values()))).write_bytes(b'changed')
    with pytest.raises(InventoryError, match='source blob mismatch'):
        review.load_sources(corpus, paths)


@pytest.mark.parametrize('mutation', ['unknown', 'duplicate', 'stale', 'overlap', 'pin'])
def test_candidate_refuses_invalid_evidence(sample, mutation):
    corpus, candidate, blobs, _ = sample
    if mutation == 'unknown': candidate['spans'][0]['unit_id'] = 'unknown'
    if mutation == 'duplicate': candidate['spans'].append(candidate['spans'][0].copy())
    if mutation == 'stale': candidate['spans'][0]['sha256'] = 'sha256:' + '0'*64
    if mutation == 'overlap': candidate['spans'][1]['start_byte'] = candidate['spans'][0]['start_byte']
    if mutation == 'pin': candidate['notice_digest'] = 'sha256:' + '0'*64
    with pytest.raises(InventoryError):
        review.candidate_rows(corpus, candidate, blobs)


def plan():
    return {'cases': [dict(id='identity', unit_ids=['u1', 'u2'], process='alpha(1)',
                           expected='pass', reference=[{'0': 0.25}], missing_dependency=None)]}


@pytest.mark.parametrize('mutation', ['path', 'unknown', 'duplicate', 'nan', 'frame', 'empty', 'override'])
def test_bad_plans_refused_before_output(sample, tmp_path, mutation):
    corpus, candidate, blobs, _ = sample
    rows = review.candidate_rows(corpus, candidate, blobs)
    p = plan(); c = p['cases'][0]
    if mutation == 'path': c['id'] = '../escape'
    if mutation == 'unknown': c['unit_ids'] = ['excluded']
    if mutation == 'duplicate': p['cases'].append(c.copy())
    if mutation == 'nan': c['reference'] = [{'0': float('nan')}]
    if mutation == 'frame': c['reference'] = [{str(review.FRAMES): 1}]
    if mutation == 'empty': p['cases'] = []
    if mutation == 'override': c['reject_nonfinite'] = False
    out = tmp_path / 'results'
    with pytest.raises(ValueError): review.run_cases(p, rows, blobs, out)
    assert not out.exists()


def test_runner_keeps_defaults_and_does_not_hide_failed_reference(sample, tmp_path, monkeypatch):
    corpus, candidate, blobs, _ = sample
    rows = review.candidate_rows(corpus, candidate, blobs)
    seen = []
    def fake(source, profile, reference, **kwargs):
        seen.append(source)
        assert profile.reject_nonfinite and profile.require_reference
        assert reference.samples['impulse'][0][0] == 0.25
        assert reference.samples['impulse'][0][-1] == 0
        return SimpleNamespace(compilation=SimpleNamespace(receipt={'exit_code': 0}, diagnostics=''),
                               receipt={'passed': False}, failures=('impulse:reference',))
    monkeypatch.setattr(review, 'run_signal', fake)
    out = tmp_path/'results'
    results = review.run_cases(plan(), rows, blobs, out)
    assert len(results) == 2 and not any(x['passed'] for x in results)
    assert seen[0].startswith('alpha(0)=0;\nalpha(x)=x;')
    assert (out/'results.json').exists()
    with pytest.raises(FileExistsError): review.run_cases(plan(), rows, blobs, out)


def test_harness_failure_aborts_and_retains_diagnostic(sample, tmp_path, monkeypatch):
    corpus, candidate, blobs, _ = sample
    rows = review.candidate_rows(corpus, candidate, blobs)
    def fail(*a, **k): raise RuntimeError('sandbox canary refused')
    monkeypatch.setattr(review, 'run_signal', fail)
    out = tmp_path/'results'
    with pytest.raises(RuntimeError, match='canary'):
        review.run_cases(plan(), rows, blobs, out)
    assert review.read_json(out/'aborted.json')['error'] == 'sandbox canary refused'


@pytest.mark.parametrize('exit_code,diagnostic,passed', [(1, 'undefined missing', True), (0, '', False), (1, 'syntax error', False)])
def test_negative_control_needs_expected_compiler_failure(sample, tmp_path, monkeypatch, exit_code, diagnostic, passed):
    corpus, candidate, blobs, _ = sample
    rows = review.candidate_rows(corpus, candidate, blobs)
    monkeypatch.setattr(review, 'compile_source', lambda *a, **k: SimpleNamespace(
        receipt={'exit_code': exit_code}, diagnostics=diagnostic))
    p = plan()
    p['cases'][0].update(expected='compile_refusal', reference=None, missing_dependency='missing')
    results = review.run_cases(p, rows, blobs, tmp_path/'results')
    assert len(results) == 1 and results[0]['passed'] is passed
    assert not review.read_json(tmp_path/'results/span-evidence.json')['production_approved']



def test_receipt_collision_refused_before_execution(sample, tmp_path):
    corpus, candidate, blobs, _ = sample
    rows = review.candidate_rows(corpus, candidate, blobs)
    p = plan()
    p['cases'].append(dict(p['cases'][0], id='identity-44100', expected='compile_refusal',
                           reference=None, missing_dependency='missing'))
    with pytest.raises(ValueError, match='colliding receipt names'):
        review.run_cases(p, rows, blobs, tmp_path/'results')
    assert not (tmp_path/'results').exists()


def test_preflight_retains_sparse_references(sample):
    corpus, candidate, blobs, _ = sample
    rows = review.candidate_rows(corpus, candidate, blobs)
    prepared = review.prepare_cases(plan(), rows, blobs)
    assert prepared[0][2] == [{'0': 0.25}]


@pytest.mark.parametrize('text', [
    '{"spans": [], "spans": [{"start_byte": 5}]}',
    '{"cases": [{"reference": [{"0": 0.25, "0": 0.5}]}]}',
    '{"entries": [], "entries": [1]}',
    '{"blob": "first.lib", "blob": "second.lib"}',
])
def test_json_inputs_reject_duplicate_keys(tmp_path, text):
    path = tmp_path/'input.json'
    path.write_text(text)
    with pytest.raises(CanonicalError):
        review.read_json(path)


@pytest.mark.parametrize('diagnostic', [' ', '\t', '\n  \t'])
def test_blank_dependency_refused_before_output(sample, tmp_path, diagnostic):
    corpus, candidate, blobs, _ = sample
    rows = review.candidate_rows(corpus, candidate, blobs)
    p = plan()
    p['cases'][0].update(expected='compile_refusal', reference=None, missing_dependency=diagnostic)
    with pytest.raises(ValueError, match='dependency diagnostic'):
        review.run_cases(p, rows, blobs, tmp_path/'results')
    assert not (tmp_path/'results').exists()

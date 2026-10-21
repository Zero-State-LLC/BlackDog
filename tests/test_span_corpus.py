"""Corpus proposals are fail-closed; resumptions require identical intact evidence."""
import copy

import pytest

from diagnostics import span_corpus as bulk
from diagnostics import span_review as review
from test_span_review import sample, corpus_base, plan  # shared source fixture


def test_lexer_original_bytes_and_nested_definitions():
    raw = '// é\r\nalpha(x) = x with { z=";/*"; }; // ;\nbeta = _\';'.encode()
    rows = bulk.definitions(raw)
    assert [r['name'] for r in rows] == ['alpha', 'beta']
    assert raw[rows[0]['start_byte']:rows[0]['end_byte']] == b'alpha(x) = x with { z=";/*"; };'
    assert rows[0]['line'] == 2
    assert 'local_definitions' in rows[0]['risks']
    assert 'stateful_or_recursive' in rows[1]['risks']


@pytest.mark.parametrize('raw', [b'a=(1;', b'a=1; /*', b'a="x', b'a="x\\', b'a=1', b'a=];'])
def test_incomplete_source_is_refused(raw):
    with pytest.raises(ValueError): bulk.definitions(raw)


def test_doc_blocks_and_comments_do_not_create_definitions():
    assert [r['name'] for r in bulk.definitions(b'<mdoc>fake=1;</mdoc> /* z=2; */ real=3;')] == ['real']


def test_corpus_accounts_for_all_and_reproduces_existing(sample):
    corpus, candidate, blobs, _ = sample
    document, report = bulk.propose(corpus, candidate, blobs)
    assert report['counts'] == {'proposed_unapproved': 3}
    assert report['existing_matches'] == 2
    assert len(document['spans']) == 3
    assert not report['production_approved'] and not report['t07_frozen']
    assert report['token_floor_status'] == 'provisional'


def test_unqualified_overload_is_blocked(sample):
    from dataclasses import replace
    corpus, candidate, blobs, _ = sample
    corpus = replace(corpus, units=(replace(corpus.units[0], function='alpha'),))
    candidate = dict(candidate, spans=[])
    document, report = bulk.propose(corpus, candidate, blobs)
    assert not document['spans']
    assert report['blocked_by_reason'] == {'ambiguous_definition': 1}


def test_existing_boundary_disagreement_stays_blocked(sample):
    corpus, candidate, blobs, _ = sample
    row = candidate['spans'][0]
    row['end_byte'] -= 1
    row['sha256'] = review.sha256_prefixed(blobs[row['blob_sha']][row['start_byte']:row['end_byte']])
    _, report = bulk.propose(corpus, candidate, blobs)
    assert report['blocked_by_reason'] == {'existing_boundary_disagreement': 1}


def setup_queue(sample, tmp_path, monkeypatch):
    corpus, candidate, blobs, _ = sample
    rows = review.candidate_rows(corpus, candidate, blobs)
    calls = []
    def fake(p, r, b, out):
        calls.append(out)
        out.mkdir()
        result = [dict(passed=True)]
        review.write_json(out/'results.json', result)
        (out/'source.dsp').write_text('source')
        return result
    monkeypatch.setattr(review, 'run_cases', fake)
    return rows, blobs, tmp_path/'queue', calls


def test_queue_resume_and_tampered_receipts(sample, tmp_path, monkeypatch):
    rows, blobs, out, calls = setup_queue(sample, tmp_path, monkeypatch)
    assert bulk.run_queue(plan(), rows, blobs, out, {'tool': 'a'})['reused_cases'] == 0
    assert bulk.run_queue(plan(), rows, blobs, out, {'tool': 'a'})['reused_cases'] == 1
    assert len(calls) == 1
    (calls[0]/'source.dsp').write_text('changed')
    with pytest.raises(ValueError, match='integrity'): bulk.run_queue(plan(), rows, blobs, out, {'tool': 'a'})


@pytest.mark.parametrize('change', ['plan', 'tool', 'blob', 'row'])
def test_queue_binding_changes_refused(sample, tmp_path, monkeypatch, change):
    rows, blobs, out, calls = setup_queue(sample, tmp_path, monkeypatch)
    p, identity = plan(), {'tool': 'a'}
    bulk.run_queue(p, rows, blobs, out, identity)
    if change == 'plan': p['cases'][0]['process'] = 'alpha(2)'
    if change == 'tool': identity['tool'] = 'b'
    if change == 'blob': blobs['extra'] = b'new'
    if change == 'row': rows = copy.deepcopy(rows); rows['u1']['manifest_digest'] = 'changed'
    with pytest.raises(ValueError, match='binding'): bulk.run_queue(p, rows, blobs, out, identity)
    assert len(calls) == 1


def test_incomplete_attempt_preserved(sample, tmp_path, monkeypatch):
    rows, blobs, out, calls = setup_queue(sample, tmp_path, monkeypatch)
    out.mkdir()
    review.write_json(out/'binding.json', dict(plan=plan(), rows=rows, identity={},
        blobs={k: review.sha256_prefixed(v) for k, v in sorted(blobs.items())}))
    abandoned = out/'identity/attempt-000001'
    abandoned.mkdir(parents=True)
    (abandoned/'aborted.json').write_text('{}')
    bulk.run_queue(plan(), rows, blobs, out, {})
    assert calls[0].name == 'attempt-000002'
    assert (abandoned/'aborted.json').exists()


def test_existing_trailing_comment_preserved(sample):
    corpus, candidate, blobs, _ = sample
    row = candidate['spans'][0]
    # Existing range includes CRLF after the semicolon, but no extra tokens.
    row['end_byte'] += 2
    row['sha256'] = review.sha256_prefixed(blobs[row['blob_sha']][row['start_byte']:row['end_byte']])
    document, report = bulk.propose(corpus, candidate, blobs)
    assert report['existing_matches'] == 2
    assert next(r for r in document['spans'] if r['unit_id']=='u1') == row


def test_nested_and_commented_definitions_not_promoted():
    raw = b'outer = environment { inner=1; }; /* example=2; */\n'
    assert [d['name'] for d in bulk.definitions(raw)] == ['outer']


def test_queue_lock_refuses_second_worker(sample, tmp_path, monkeypatch):
    import fcntl
    rows, blobs, out, calls = setup_queue(sample, tmp_path, monkeypatch)
    out.mkdir()
    with (out/'queue.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError): bulk.run_queue(plan(), rows, blobs, out, {})
    assert not calls


def test_completed_failure_is_not_retried(sample, tmp_path, monkeypatch):
    rows, blobs, out, calls = setup_queue(sample, tmp_path, monkeypatch)
    def fail(p, r, b, directory):
        calls.append(directory)
        directory.mkdir()
        result = [{'passed': False}]
        review.write_json(directory/'results.json', result)
        return result
    monkeypatch.setattr(review, 'run_cases', fail)
    assert bulk.run_queue(plan(), rows, blobs, out, {})['passed'] == 0
    assert bulk.run_queue(plan(), rows, blobs, out, {})['passed'] == 0
    assert len(calls) == 1


def test_harness_abort_keeps_attempt_and_stops(sample, tmp_path, monkeypatch):
    rows, blobs, out, calls = setup_queue(sample, tmp_path, monkeypatch)
    def abort(p, r, b, directory):
        directory.mkdir()
        (directory/'aborted.json').write_text('{}')
        raise RuntimeError('sandbox canary refused')
    monkeypatch.setattr(review, 'run_cases', abort)
    with pytest.raises(RuntimeError, match='canary'): bulk.run_queue(plan(), rows, blobs, out, {})
    assert (out/'identity/attempt-000001/aborted.json').exists()
    assert not list(out.rglob('complete.json'))


def test_missing_binding_never_adopts_existing_results(sample, tmp_path, monkeypatch):
    rows, blobs, out, calls = setup_queue(sample, tmp_path, monkeypatch)
    bulk.run_queue(plan(), rows, blobs, out, {})
    (out/'binding.json').unlink()
    changed = plan()
    changed['cases'][0]['process'] = 'alpha(2)'
    with pytest.raises(ValueError, match='missing queue binding'):
        bulk.run_queue(changed, rows, blobs, out, {})
    assert len(calls) == 1


def test_symlinked_evidence_refused(sample, tmp_path, monkeypatch):
    rows, blobs, out, calls = setup_queue(sample, tmp_path, monkeypatch)
    out.mkdir()
    target = tmp_path/'untouched'
    target.write_text('keep')
    (out/'binding.json').symlink_to(target)
    with pytest.raises(ValueError, match='symlinks'):
        bulk.run_queue(plan(), rows, blobs, out, {})
    assert target.read_text() == 'keep'
    assert not calls


def test_partial_trailing_construct_is_blocked(sample):
    corpus, candidate, blobs, _ = sample
    row = candidate['spans'][0]
    candidate['spans'] = [row]
    row['end_byte'] += 4  # CRLF plus the start of the next identifier.
    row['sha256'] = review.sha256_prefixed(blobs[row['blob_sha']][row['start_byte']:row['end_byte']])
    _, report = bulk.propose(corpus, candidate, blobs)
    assert report['blocked_by_reason'] == {'existing_boundary_disagreement': 1}

"""Fail-early evaluation over existing rights, compiler and signal contracts.

This diagnostic evaluator never authorizes training or promotion. It does not
read private holdouts. Independent evaluation requires a separate verified
adapter and currently remains explicitly BLOCKED after successful diagnostics.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import time
from typing import Any, Callable, Mapping

from faustcoder.acquire import git_blob_sha1
from faustcoder.canonical import build_envelope, content_digest_for
from faustcoder.compiler import compile_source, store_compiler_receipt
from faustcoder.inventory import parse_corpus
from faustcoder.schemas import validate
from faustcoder.signal import SignalProfile, SignalReference, run_signal_suite, commit_signal_check
from faustcoder.candidate_machine import CandidateState
from faustcoder.store import ArtifactStore


def evaluate(
    store: ArtifactStore, *, source: bytes, unit_id: str, inventory: Mapping[str, Any],
    notice: Mapping[str, Any], task: Mapping[str, Any],
    reference_for: Callable[[SignalProfile], SignalReference],
    reference_digest: str, created_at: str, frames: int = 256,
) -> dict:
    """Evaluate one whole-file public unit; every executed stage is attributable.

    The reference digest binds the operator's analytical reference specification,
    not a claim of independent review. Corpus parsing enforces the existing
    pinned inventory/notice and rights guards. Compiler/runtime failure is BLOCKED,
    rather than a scored model failure. No reward-grade path is used here.
    """
    stages = []
    parents = []
    source_digest = 'sha256:' + hashlib.sha256(source).hexdigest()
    task_digest = content_digest_for(dict(task))
    runner_digest = 'sha256:' + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def emit(stage, status, *, details=None, evidence=(), started=None):
        payload = {'record_type': 'EvaluationRun', 'schema_version': 1,
                   'stage': stage, 'status': status, 'source_digest': source_digest,
                   'attempt_started_at': created_at, 'input_receipts': list(parents),
                   'task_digest': task_digest, 'reference_digest': reference_digest,
                   'runner_digest': runner_digest, 'unit_id': unit_id,
                   'details': details or {}, 'evidence': list(evidence),
                   'elapsed_ms': max(0, int((time.monotonic() - started)*1000)) if started else 0,
                   'diagnostic_only': True, 'training_authorized': False}
        envelope = build_envelope(schema_version='1.0.0', created_at=created_at,
                                  producer='faustcoder.evaluation_funnel', parents=sorted(set([*parents, *evidence])),
                                  payload=payload)
        store.put(envelope)
        parents[:] = [envelope['content_digest']]
        stages.append({'stage': stage, 'status': status, 'receipt': envelope['content_digest']})

    def result():
        return {'status': stages[-1]['status'], 'stages': stages,
                'training_authorized': False, 'promotion_allowed': False}

    started = time.monotonic()
    static_step = 'task_schema_invalid'
    try:
        validate(dict(task), 'task-spec.schema.json')
        static_step = 'reference_binding_required'
        if (not isinstance(reference_digest, str) or not reference_digest.startswith('sha256:')
                or len(reference_digest) != 71
                or any(c not in '0123456789abcdef' for c in reference_digest[7:])):
            raise ValueError('reference_binding_required')
        static_step = 'canonical_inventory_or_notice_invalid'
        corpus = parse_corpus(inventory, notice)
        static_step = 'source_not_rights_cleared'
        matches = [u for u in corpus.units if u.unit_id == unit_id]
        if len(matches) != 1:
            raise ValueError('source_not_rights_cleared')
        unit = matches[0]
        static_step = 'whole_file_public_eval_eligibility_required'
        if unit.function or unit.holdout or 'eval' not in unit.eligible_for or unit.training_only:
            raise ValueError('whole_file_public_eval_eligibility_required')
        static_step = 'source_blob_mismatch'
        if git_blob_sha1(source) != unit.blob_sha:
            raise ValueError('source_blob_mismatch')
        static_step = 'source_encoding_invalid'
        text = source.decode('utf-8')
    except Exception as exc:
        emit('static', 'BLOCKED', details={'code': static_step, 'error_type': type(exc).__name__}, started=started)
        return result()
    emit('static', 'PASS', details={'inventory_digest': corpus.inventory_digest,
                                   'notice_digest': corpus.notice_digest}, started=started)

    started = time.monotonic()
    try:
        compiled = compile_source(text, lang='wasm', options=('-ftz', '0'))
        validate(compiled.receipt, 'compiler-receipt.schema.json')
        # Identity is checked before persisting a PASS. Runtime pin is verified by
        # compile_source; caller-supplied compiler claims are not an input API.
        if (compiled.receipt.get('compiler') != 'libfaust-wasm'
                or '--faustwasm=0.19.0' not in compiled.receipt.get('command', [])
                or compiled.receipt.get('faust_version') != '2.90.0'
                or compiled.receipt.get('source_sha256') != source_digest[7:]):
            raise ValueError('compiler_identity_mismatch')
        compiler_id = store_compiler_receipt(store, compiled.receipt, created_at=created_at)
    except Exception as exc:
        emit('compiler', 'BLOCKED', details={'code': type(exc).__name__}, started=started)
        return result()
    if compiled.receipt['exit_code'] != 0 or compiled.receipt.get('diagnostic_class') not in {'ok','warning'}:
        emit('compiler', 'FAIL', details={'diagnostic_class': compiled.receipt.get('diagnostic_class')},
             evidence=['sha256:'+compiler_id], started=started)
        return result()
    emit('compiler', 'PASS', evidence=['sha256:'+compiler_id], started=started)

    started = time.monotonic()
    try:
        suite = run_signal_suite(text, reference_for, sample_rates=(44100,48000),
                                 frames=frames, max_frames=frames, require_reference=True, head_frames=frames)
        if len(suite.runs) != 2 or [r.receipt['sample_rate'] for r in suite.runs] != [44100,48000]:
            raise ValueError('both_rate_receipts_required')
        committed = commit_signal_check(store, suite, state=CandidateState.COMPILE_CHECKED,
                                        created_at=created_at)
        signal_ids = ['sha256:' + key for key in committed.artifact_ids]
        details = {'rates': [44100,48000], 'runs': [r.reproducible_digest for r in suite.runs],
                   'failures': [list(r.failures) for r in suite.runs]}
    except Exception as exc:
        emit('signal', 'BLOCKED', details={'code': type(exc).__name__}, started=started)
        return result()
    emit('signal', 'PASS' if suite.passed else 'FAIL', details=details, evidence=signal_ids, started=started)
    if not suite.passed:
        return result()
    emit('independent', 'BLOCKED', details={'code': 'independent_replay_not_verified',
         'next_action': 'Provide independently replayed adversarial, leakage and custody evidence through a verified adapter'})
    return result()

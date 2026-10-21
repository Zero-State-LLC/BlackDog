"""Offline, unapproved review packets and bounded span diagnostics.

This is not a Faust parser or a production manifest approval path. Run with
``python -m diagnostics.span_review --help``. Private sources stay in receipts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import re

from faustcoder.canonical import canonical_bytes, sha256_prefixed
from faustcoder.compiler import ResourceLimits, compile_source
from faustcoder.errors import InventoryError
from faustcoder.function_spans import extract_span, verify_manifest
from faustcoder.inventory import parse_corpus
from faustcoder.signal import SignalProfile, SignalReference, run_signal

FRAMES = 144000
RATES = (44100, 48000)


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    Path(path).write_bytes(canonical_bytes(json.loads(json.dumps(value, allow_nan=False))) + b'\n')


def load_sources(corpus, source_map):
    """Read explicit local mappings, verifying Git blob identity before use."""
    blobs = {}
    for sha in sorted({u.blob_sha for u in corpus.units if u.function}):
        if sha not in source_map:
            raise InventoryError(f'missing local source: {sha}')
        raw = Path(source_map[sha]).read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if actual != sha:
            raise InventoryError(f'source blob mismatch: {sha}')
        raw.decode('utf-8')
        blobs[sha] = raw
    return blobs


def candidate_rows(corpus, candidate, blobs):
    """Check an unapproved subset without changing production coverage rules."""
    functions = {u.unit_id: u for u in corpus.units if u.function}
    ids = [s['unit_id'] for s in candidate['spans']]
    if any(uid not in functions for uid in ids):
        raise InventoryError('unknown candidate unit')
    digest = sha256_prefixed(canonical_bytes(candidate))
    rows = verify_manifest(candidate, digest, [functions[uid] for uid in ids],
                           corpus.inventory_digest, corpus.notice_digest)
    for row in rows.values():
        extract_span(blobs[row['blob_sha']], row)
    # A computed integrity digest is never represented as independent approval.
    return rows


def packet_bundle(corpus, candidate, blobs):
    rows = candidate_rows(corpus, candidate, blobs)
    units = sorted((u for u in corpus.units if u.function), key=lambda u: u.unit_id)
    groups = {}
    for u in units:
        key = (u.repo, u.pin, u.path, re.sub(r'@\d+$', '', u.function))
        groups.setdefault(key, []).append(u.unit_id)
    selections = {s['unit_id']: s for s in candidate['spans']}
    packets = []
    for u in units:
        key = (u.repo, u.pin, u.path, re.sub(r'@\d+$', '', u.function))
        packets.append({
            'unit': json.loads(json.dumps(asdict(u))), 'source_ref': f'sources/{u.blob_sha}.lib',
            'source_sha256': sha256_prefixed(blobs[u.blob_sha]),
            'overload_siblings': sorted(groups[key]),
            'candidate_span': selections.get(u.unit_id),
            'status': 'proposed_unapproved' if u.unit_id in rows else 'boundary_review_pending',
            'boundary_review': 'independent_review_pending',
            'dependency_closure': 'not_assessed', 'compiler_signal': 'not_assessed',
            'production_approved': False,
            'questions': ['Complete original-byte boundaries and overload order?',
                          'Explicit dependency closure and permissible rights?',
                          'Representative task, domain and independent reference?',
                          'Independent review and separately approved digest?'],
        })
    pending = [p for p in packets if p['candidate_span'] is None]
    return {
        'format': 'span-review-packets.v1', 'production_approved': False,
        'inventory_digest': corpus.inventory_digest, 'notice_digest': corpus.notice_digest,
        'candidate_integrity_digest': sha256_prefixed(canonical_bytes(candidate)),
        'counts': {'admitted_functions': len(units), 'proposed': len(rows), 'pending': len(pending)},
        'pending_by_file': dict(sorted(Counter(p['unit']['path'] for p in pending).items())),
        'exclusions': [json.loads(json.dumps(asdict(x))) for x in corpus.excluded],
        'packets': packets,
    }


def prepare_cases(plan, rows, blobs):
    """Preflight every case before any compilation; no executable Python plans."""
    if set(plan) != {'cases'} or not isinstance(plan['cases'], list) or not plan['cases']:
        raise ValueError('a nonempty cases plan is required')
    prepared = []
    names = set()
    stems = set()
    for case in plan['cases']:
        if set(case) != {'id', 'unit_ids', 'process', 'expected', 'reference', 'missing_dependency'}:
            raise ValueError('invalid case fields')
        name = case['id']
        if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', name) or name in names:
            raise ValueError('invalid or duplicate case id')
        names.add(name)
        ids = case['unit_ids']
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in rows for i in ids) or len(ids) != len(set(ids)):
            raise ValueError('invalid case span identities')
        if not isinstance(case['process'], str) or not case['process'].strip():
            raise ValueError('process expression required')
        expected = case['expected']
        if expected not in ('pass', 'compile_refusal', 'reference_refusal'):
            raise ValueError('invalid expected outcome')
        case_stems = {name} if expected == 'compile_refusal' else {f'{name}-{rate}' for rate in RATES}
        if stems & case_stems:
            raise ValueError('colliding receipt names')
        stems.update(case_stems)
        if expected == 'compile_refusal':
            if case['reference'] is not None or not isinstance(case['missing_dependency'], str) or not case['missing_dependency']:
                raise ValueError('compiler refusal requires dependency diagnostic and no reference')
            samples = None
        else:
            if case['missing_dependency'] is not None:
                raise ValueError('unexpected dependency diagnostic')
            reference = case['reference']
            if not isinstance(reference, list) or not 1 <= len(reference) <= 32:
                raise ValueError('1..32 sparse reference channels required')
            samples = []
            for channel in reference:
                if not isinstance(channel, dict):
                    raise ValueError('sparse channel must be an object')
                for frame, value in channel.items():
                    if not isinstance(frame, str) or not frame.isdigit() or str(int(frame)) != frame or not 0 <= int(frame) < FRAMES:
                        raise ValueError('invalid reference frame')
                    if type(value) not in (int, float) or not math.isfinite(value):
                        raise ValueError('nonfinite reference')
                samples.append(dict(channel))
        source = '\n'.join(extract_span(blobs[rows[i]['blob_sha']], rows[i]).decode() for i in ids)
        source += '\nprocess = ' + case['process'] + ';\n'
        prepared.append((case, source, samples))
    return prepared


def run_cases(plan, rows, blobs, out):
    prepared = prepare_cases(plan, rows, blobs)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / 'plan.json', plan)
    write_json(out / 'span-evidence.json', {'spans': rows, 'production_approved': False})
    results = []
    for case, source, sparse in prepared:
        samples = None
        if sparse is not None:
            samples = []
            for channel in sparse:
                values = [0.0] * FRAMES
                for frame, value in channel.items():
                    values[int(frame)] = value
                samples.append(values)
        name = case['id']
        (out / f'{name}.dsp').write_text(source)
        rates = (None,) if samples is None else RATES
        for rate in rates:
            stem = name if rate is None else f'{name}-{rate}'
            try:
                if rate is None:
                    compiled = compile_source(source, limits=ResourceLimits(timeout_s=60))
                    passed = compiled.receipt['exit_code'] == 1 and case['missing_dependency'] in compiled.diagnostics
                    failures = []
                else:
                    profile = SignalProfile(sample_rate=rate, frames=FRAMES, head_frames=FRAMES,
                                            max_frames=FRAMES, stimuli=('impulse',), expected_channels=len(samples))
                    ref = SignalReference(sample_rate=rate, block_size=64, frames=FRAMES, seed=1,
                                          stimuli=('impulse',), channels=len(samples), samples={'impulse': samples})
                    run = run_signal(source, profile, ref, limits=ResourceLimits(timeout_s=60))
                    compiled = run.compilation
                    failures = list(run.failures)
                    passed = compiled.receipt['exit_code'] == 0 and run.receipt is not None and (
                        not failures if case['expected'] == 'pass' else 'impulse:reference' in failures)
                    write_json(out / f'{stem}-signal.json', run.receipt)
                    write_json(out / f'{stem}-profile.json', asdict(profile))
                write_json(out / f'{stem}-compiler.json', compiled.receipt)
                (out / f'{stem}-diagnostics.txt').write_text(compiled.diagnostics)
                results.append({'case': name, 'rate': rate, 'passed': passed,
                                'expected': case['expected'], 'failures': failures})
                write_json(out / 'results.json', results)
            except Exception as exc:
                write_json(out / 'aborted.json', {'case': name, 'rate': rate, 'error': str(exc)})
                raise  # Never continue past a sandbox/harness failure.
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('packets', 'run'))
    for option in ('inventory', 'notice', 'candidate', 'sources', 'output'):
        parser.add_argument('--' + option, required=True, type=Path)
    parser.add_argument('--plan', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if any((p / '.git').exists() for p in (out, *out.parents)):
        parser.error('private receipts must be outside a Git checkout')
    corpus = parse_corpus(read_json(args.inventory), read_json(args.notice))
    candidate = read_json(args.candidate)
    blobs = load_sources(corpus, read_json(args.sources))
    if args.mode == 'packets':
        bundle = packet_bundle(corpus, candidate, blobs)
        out.mkdir(parents=True, exist_ok=False)
        (out / 'sources').mkdir()
        for sha, raw in blobs.items():
            (out / 'sources' / f'{sha}.lib').write_bytes(raw)
        write_json(out / 'packets.json', bundle)
        print(json.dumps(bundle['counts'], sort_keys=True))
    else:
        if args.plan is None:
            parser.error('--plan is required for run')
        rows = candidate_rows(corpus, candidate, blobs)
        results = run_cases(read_json(args.plan), rows, blobs, out)
        print(json.dumps({'runs': len(results), 'passed': sum(r['passed'] for r in results)}))
        return 0 if all(r['passed'] for r in results) else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

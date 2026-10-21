"""Conservative corpus proposals and a serial, integrity-checked diagnostic queue.

No output constitutes independent review, dependency closure, or approval.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import fcntl
import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

from diagnostics import span_review as review
from faustcoder.canonical import sha256_prefixed
from faustcoder.compiler import runtime_pin, worker_directory


def statements(raw):
    """Return top-level token statements with exact byte offsets; fail closed.

Comments and strings cannot introduce delimiters. Faust documentation blocks
are skipped only outside statements. This is a lexer, not a Faust parser.
    """
    raw.decode('utf-8')
    tokens, result, stack = [], [], []
    i = 0
    while i < len(raw):
        if raw[i:i+1].isspace():
            i += 1
            continue
        if raw.startswith(b'//', i):
            end = raw.find(b'\n', i)
            i = len(raw) if end < 0 else end + 1
            continue
        if raw.startswith(b'/*', i):
            end = raw.find(b'*/', i+2)
            if end < 0: raise ValueError('unterminated comment')
            i = end + 2
            continue
        if raw.startswith(b'<mdoc>', i) and not tokens:
            end = raw.find(b'</mdoc>', i+6)
            if end < 0: raise ValueError('unterminated documentation')
            i = end + 7
            continue
        start = i
        c = raw[i:i+1]
        if c == b'"':
            i += 1
            while i < len(raw):
                if raw[i:i+1] == b'\\': i += 2
                elif raw[i:i+1] == b'"':
                    i += 1
                    break
                else: i += 1
            else: raise ValueError('unterminated string')
            if i > len(raw): raise ValueError('unterminated string escape')
        elif re.match(rb'[A-Za-z_]', c):
            i += 1
            while i < len(raw) and re.match(rb'[A-Za-z_0-9]', raw[i:i+1]): i += 1
        else:
            i += 1
        token = raw[start:i]
        if token in (b'(', b'[', b'{'): stack.append(token)
        if token in (b')', b']', b'}'):
            if not stack or stack.pop() != {b')': b'(', b']': b'[', b'}': b'{'}[token]:
                raise ValueError('unbalanced delimiter')
        tokens.append((token, start, i))
        if token == b';' and not stack:
            result.append(tokens)
            tokens = []
    if stack or tokens: raise ValueError('incomplete trailing statement')
    return result


def definitions(raw):
    result = []
    for tokens in statements(raw):
        name = tokens[0][0]
        if not re.fullmatch(rb'[A-Za-z_]\w*', name): continue
        j = 1
        if j < len(tokens) and tokens[j][0] == b'(':
            depth = 0
            while j < len(tokens):
                t = tokens[j][0]
                if t == b'(': depth += 1
                if t == b')': depth -= 1
                j += 1
                if depth == 0: break
        if j >= len(tokens) or tokens[j][0] != b'=': continue
        # Equality expressions and unsupported assignment forms are not definitions.
        if j+1 >= len(tokens) or tokens[j+1][0] == b'=': continue
        start, end = tokens[0][1], tokens[-1][2]
        body = [t[0] for t in tokens[j+1:]]
        risk = []
        if b'with' in body or b'{' in body: risk.append('local_definitions')
        if b'~' in body or b"'" in body: risk.append('stateful_or_recursive')
        if tokens[1][0] == b'(': risk.append('parameterized')
        refs = sorted({t.decode() for t in body if re.fullmatch(rb'[A-Za-z_]\w*', t)})
        result.append(dict(name=name.decode(), start_byte=start, end_byte=end,
                           line=raw[:start].count(b'\n')+1, risks=risk,
                           identifier_hints=refs))
    return result


def propose(corpus, candidate, blobs):
    existing = review.candidate_rows(corpus, candidate, blobs)
    parsed, errors = {}, {}
    for sha, raw in blobs.items():
        try: parsed[sha] = definitions(raw)
        except ValueError as exc:
            parsed[sha] = []
            errors[sha] = str(exc)
    packets, rows = [], []
    for unit in sorted((u for u in corpus.units if u.function), key=lambda u: u.unit_id):
        base, sep, line = unit.function.rpartition('@')
        name = base if sep and line.isdigit() else unit.function
        matches = [d for d in parsed[unit.blob_sha] if d['name'] == name and
                   (not sep or not line.isdigit() or d['line'] == int(line))]
        packet = dict(unit=asdict(unit), production_approved=False,
                      boundary_review='pending', dependency_closure='not_assessed',
                      compiler_signal='not_assessed', proposal=None)
        if len(matches) != 1:
            packet.update(status='blocked', reason=errors.get(unit.blob_sha,
                          'ambiguous_definition' if matches else 'definition_not_found'))
        else:
            d = matches[0]
            raw = blobs[unit.blob_sha]
            row = {k: getattr(unit, k) for k in ('unit_id', 'repo', 'pin', 'path', 'blob_sha', 'function')}
            row.update(start_byte=d['start_byte'], end_byte=d['end_byte'],
                       sha256=sha256_prefixed(raw[d['start_byte']:d['end_byte']]))
            packet.update(status='proposed_unapproved', proposal=row,
                          risks=d['risks'], identifier_hints=d['identifier_hints'])
            old = existing.get(unit.unit_id)
            # Keep previously proposed trailing comments/whitespace byte-for-byte,
            # only when the lexical statement and all non-trivia tokens agree.
            if old and old['start_byte'] == row['start_byte'] and old['end_byte'] >= row['end_byte']:
                try:
                    prior_tokens = statements(raw[old['start_byte']:old['end_byte']])
                except ValueError:
                    prior_tokens = []  # A partial trailing construct is a disagreement.
                current_tokens = statements(raw[row['start_byte']:row['end_byte']])
                if [[t[0] for t in group] for group in prior_tokens] == [[t[0] for t in group] for group in current_tokens]:
                    row.update(end_byte=old['end_byte'], sha256=old['sha256'])
                    packet['existing_trivia_preserved'] = True
            packet['existing_match'] = (all(row[k] == existing[unit.unit_id][k] for k in row)
                                         if unit.unit_id in existing else None)
            if packet['existing_match'] is False:
                packet.update(status='blocked', reason='existing_boundary_disagreement')
            else: rows.append(row)
        packets.append(packet)
    document = dict(candidate, reviewer='UNAPPROVED lexical proposals; independent review pending', spans=rows)
    # Reject identity errors, overlaps and stale source ranges even for proposals.
    review.candidate_rows(corpus, document, blobs)
    for packet in packets:
        if packet['status'] != 'blocked':
            risk = packet['risks']
            packet['review_group'] = (packet['unit']['path'] + ':' +
                                      (','.join(risk) if risk else 'simple'))
    report = dict(format='span-corpus.v1', production_approved=False,
                  token_floor=40, token_floor_status='provisional', t07_frozen=False,
                  counts=dict(Counter(p['status'] for p in packets)),
                  existing_proposals=len(existing),
                  existing_matches=sum(p.get('existing_match') is True for p in packets),
                  blocked_by_reason=dict(Counter(p['reason'] for p in packets if p['status']=='blocked')),
                  review_groups=dict(sorted(Counter(p['review_group'] for p in packets if 'review_group' in p).items())),
                  packets=packets)
    return document, report


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def runtime_identity():
    """Bind resumptions to code, interpreter, tools, platform and execution settings."""
    root = Path(review.__file__).resolve().parents[1]
    code = {str(p.relative_to(root)): file_hash(p) for directory in ('diagnostics', 'faustcoder')
            for p in sorted((root/directory).rglob('*.py'))}
    tools = {}
    for name in ('faust', 'node'):
        path = shutil.which(name)
        if path is None: raise ValueError(f'missing tool: {name}')
        result = subprocess.run([path, '--version'], capture_output=True, check=True, timeout=15)
        tools[name] = dict(path=path, sha256=file_hash(path),
                           version=(result.stdout+result.stderr).decode())
    unshare = os.environ.get('FAUSTCODER_UNSHARE')
    if not unshare: raise ValueError('explicit FAUSTCODER_UNSHARE required')
    worker = worker_directory()
    worker_hashes = {str(p.relative_to(worker)): file_hash(p) for p in sorted(worker.rglob('*')) if p.is_file()}
    return dict(code=code, tools=tools, runtime=asdict(runtime_pin()), workers=worker_hashes, python=sys.version, executable=file_hash(sys.executable),
                platform=platform.platform(), machine=platform.machine(),
                unshare=dict(path=unshare, sha256=file_hash(unshare)),
                settings_sha256={k: sha256_prefixed(v.encode()) for k, v in os.environ.items() if k.startswith('FAUSTCODER_')
                          or k in ('PATH', 'NODE_OPTIONS', 'LD_LIBRARY_PATH', 'PYTHONPATH')})


def receipt_hashes(directory):
    return {str(p.relative_to(directory)): file_hash(p) for p in sorted(directory.rglob('*'))
            if p.is_file() and p.name != 'complete.json'}


def run_queue(plan, rows, blobs, out, identity):
    """One worker, whole-case checkpoints; interrupted attempts retained, not reused."""
    review.prepare_cases(plan, rows, blobs)  # Entire plan preflight before writes.
    binding = dict(plan=plan, rows=rows, identity=identity,
                   blobs={k: sha256_prefixed(v) for k, v in sorted(blobs.items())})
    if out.is_symlink() or any(p.is_symlink() for p in out.rglob('*')):
        raise ValueError('queue must not contain symlinks')
    out.mkdir(parents=True, exist_ok=True)
    with (out/'queue.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        metadata = out/'binding.json'
        if metadata.exists():
            if review.read_json(metadata) != binding: raise ValueError('queue binding changed; use a new output directory')
        else:
            if any(p.name != 'queue.lock' for p in out.iterdir()):
                raise ValueError('missing queue binding for existing evidence')
            review.write_json(metadata, binding)
        results = []
        reused = 0
        for case in plan['cases']:
            case_dir = out/case['id']
            case_dir.mkdir(exist_ok=True)
            attempts = sorted(case_dir.glob('attempt-*'))
            completed = [p for p in attempts if (p/'complete.json').exists()]
            if completed:
                prior = completed[-1]
                record = review.read_json(prior/'complete.json')
                if record['hashes'] != receipt_hashes(prior): raise ValueError('receipt integrity mismatch')
                result = review.read_json(prior/'results.json')
                reused += 1
            else:
                attempt = case_dir/f'attempt-{len(attempts)+1:06d}'
                result = review.run_cases({'cases': [case]}, rows, blobs, attempt)
                review.write_json(attempt/'complete.json', {'hashes': receipt_hashes(attempt)})
            results.extend(result)
        summary = dict(runs=len(results), passed=sum(r['passed'] for r in results),
                       cases=len(plan['cases']), reused_cases=reused, production_approved=False)
        review.write_json(out/'summary.json', summary)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('propose', 'queue'))
    for name in ('inventory', 'notice', 'candidate', 'sources', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--plan', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if any((p/'.git').exists() for p in (out, *out.parents)) or out == Path('/tmp').resolve() or Path('/tmp').resolve() in out.parents:
        parser.error('receipts must be outside Git and /tmp')
    corpus = review.parse_corpus(review.read_json(args.inventory), review.read_json(args.notice))
    candidate = review.read_json(args.candidate)
    blobs = review.load_sources(corpus, review.read_json(args.sources))
    if args.mode == 'propose':
        document, report = propose(corpus, candidate, blobs)
        out.mkdir(parents=True, exist_ok=False)
        review.write_json(out/'candidate.UNAPPROVED.json', document)
        review.write_json(out/'classification.json', report)
        print(report['counts'], 'existing matches:', report['existing_matches'])
    else:
        if args.plan is None: parser.error('--plan required')
        result = run_queue(review.read_json(args.plan), review.candidate_rows(corpus, candidate, blobs),
                           blobs, out, runtime_identity())
        print(result)
        return int(result['passed'] != result['runs'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

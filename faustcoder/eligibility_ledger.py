"""QR-03: replay hash-bound batch accounting without admitting any source.

Run against the preserved external batch directory. No sources are returned,
no approvals are inferred, and no historical dispositions are rewritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from faustcoder.canonical import canonical_bytes, content_digest_for, loads_strict
from faustcoder.readiness_manifest import ManifestError, read_beneath
from faustcoder.errors import ArtifactStoreError

EXPECTED_SCOPE = {'units': 1430, 'packets': 110, 'blobs': 510,
                  'short_groups': 23, 'collective_sets': 19}


def reconcile(ledger: dict, packets: dict[str, dict], comparisons: dict,
              short: dict, matches: dict, *, expected: dict | None = None) -> dict:
    """Reconcile authoritative batch metadata; no source clearance follows."""
    rows = ledger['units']
    ids = [row['unit_id'] for row in rows]
    if not all(isinstance(key, str) and key for key in ids) or len(ids) != len(set(ids)):
        raise ValueError('duplicate or empty unit identity')
    by_id = {row['unit_id']: row for row in rows}
    assignment = {}
    for packet_id, packet in sorted(packets.items()):
        if not packet['unit_ids']:
            raise ValueError('empty packet')
        for key in packet['unit_ids']:
            if key not in by_id or key in assignment:
                raise ValueError('unknown or multiply assigned packet member')
            assignment[key] = packet_id
    if set(assignment) != set(ids):
        raise ValueError('packet coverage mismatch')
    all_rows = [*rows, *comparisons['units']]
    blobs = {row['blob_sha'] for row in all_rows}
    if any(not isinstance(blob, str) or len(blob) != 40
           or any(c not in '0123456789abcdef' for c in blob) for blob in blobs):
        raise ValueError('invalid Git blob identity')
    counts = {'units': len(rows), 'packets': len(packets), 'blobs': len(blobs),
              'short_groups': len(short['groups']),
              'collective_sets': sum(e['reason'] == 'collective_support' for e in matches['edges'])}
    expected = EXPECTED_SCOPE if expected is None else expected
    exceptions = [{'code': 'scope_count_mismatch', 'field': key,
                   'expected': count, 'actual': counts.get(key)}
                  for key, count in expected.items() if counts.get(key) != count]
    output = []
    for key, row in sorted(by_id.items()):
        blockers = list(row.get('blockers', []))
        for field in ('repo', 'pin', 'path', 'source_sha256', 'family'):
            if not row.get(field): blockers.append('missing_' + field)
        blockers.append('eligibility_receipts_not_semantically_verified')
        output.append({'unit_id': key, 'packet_id': assignment[key],
                       'packet_digest': content_digest_for(packets[assignment[key]]),
                       'blob_sha': row['blob_sha'],
                       'source': {f: row.get(f) for f in ('repo', 'pin', 'path', 'function', 'source_sha256')},
                       'family': row.get('family'), 'historical_status': row.get('status'),
                       'status': 'QUARANTINED', 'blockers': sorted(set(blockers))})
    body = {'schema_version': 1, 'counts': counts,
            'families': len({r.get('family') for r in rows if r.get('family')}),
            'sources': len({(r.get('repo'), r.get('pin'), r.get('path')) for r in all_rows}),
            'accounting_pass': not exceptions, 'training_authorized': False,
            'production_admitted': 0, 'units': output, 'exceptions': exceptions,
            'exception_counts': dict(sorted(Counter(b for r in output for b in r['blockers']).items()))}
    return {**body, 'content_digest': content_digest_for(body)}


def assess_batch(root: Path, binding_sha256: str) -> dict:
    """Pin exact input bytes first; verify all binding-indexed outputs safely."""
    binding_bytes = read_beneath(root, 'binding.json')
    if hashlib.sha256(binding_bytes).hexdigest() != binding_sha256:
        raise ValueError('batch binding digest mismatch')
    binding = loads_strict(binding_bytes)
    payloads = {}
    for path, entry in binding['outputs'].items():
        data = read_beneath(root, path)
        if 'sha256:' + hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('batch output digest mismatch')
        if path.endswith('.json'):
            payloads[path] = loads_strict(data)
    required = {'candidate-ledger.json', 'comparison-ledger.json', 'packet-index.json',
                'short-collision-groups.json', 'match-evidence.json'}
    if not required <= payloads.keys():
        raise ValueError('batch binding omits accounting inputs')
    packets = {}
    for entry in payloads['packet-index.json']:
        packet_id = entry['packet_id']
        if packet_id in packets:
            raise ValueError('duplicate packet ID')
        packet = payloads.get('packets/' + packet_id + '.json')
        if packet is None or len(packet['unit_ids']) != entry['members']:
            raise ValueError('packet missing or member count mismatch')
        packets[packet_id] = packet
    indexed = {'packets/' + key + '.json' for key in packets}
    actual = {p for p in payloads if p.startswith('packets/') and p.endswith('.json')}
    if indexed != actual:
        raise ValueError('unindexed packet')
    report = reconcile(payloads['candidate-ledger.json'], packets,
                       payloads['comparison-ledger.json'], payloads['short-collision-groups.json'],
                       payloads['match-evidence.json'])
    return {'binding_sha256': binding_sha256, 'report': report}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-root', required=True, type=Path)
    parser.add_argument('--binding-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        report = assess_batch(args.batch_root, args.binding_sha256)
    except (OSError, ValueError, KeyError, TypeError, ArtifactStoreError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'code': type(exc).__name__,
                          'next_action': 'Supply the original hash-bound batch with all indexed receipts'}))
        return 2
    print(canonical_bytes(report).decode())
    return 0 if report['report']['accounting_pass'] else 2


if __name__ == '__main__':
    raise SystemExit(main())

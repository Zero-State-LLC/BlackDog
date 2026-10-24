"""Bind bounded repair evidence without transferring it to different targets.

This produces a diagnostic review, never a signed readiness receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

SOURCE = 'd4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e'
CASES = set(itertools.product(('boundary-holds', 'chirped-sweep'),
                             (44100, 48000, 96000, 192000),
                             ('noise', 'impulse', 'sine')))


def bind_review(rights, family, wasm, modular, contracts):
    """Require matching complete evidence, preserving every admission blocker."""
    for report in (family, wasm, modular):
        if report.get('source_sha256') != SOURCE:
            raise ValueError('repair source binding mismatch')
    for report, ratio in ((wasm, 'max_tolerance_ratio'), (modular, 'ratio')):
        rows = report['rows']
        keys = [(r['schedule'], r['rate'], r['stimulus']) for r in rows]
        if len(keys) != 24 or set(keys) != CASES:
            raise ValueError('incomplete or duplicate case matrix')
        if any(r['frames'] != 720000 or not r['passed'] or not 0 <= r[ratio] <= 1 for r in rows):
            raise ValueError('bounded numerical qualification failed')
    if (wasm['bounded_jobs'] != 149 or wasm['reset_rejections'] != 24
            or not wasm['split_full_audio_exact']
            or any(not r['reset_rejected'] or not r['reset_ratio'] > 1 for r in wasm['rows'])):
        raise ValueError('checkpoint negative or split evidence incomplete')
    closures = rights['closures']
    if len(closures) != 4 or {r['name'] for r in closures} != {'analyzer', 'spectral', 'lowpass', 'highpass'}:
        raise ValueError('closure rights coverage mismatch')
    if any(r['unresolved'] or r['eligible_for'] != ['train'] or not r['training_only_members'] for r in closures):
        raise ValueError('expected exact training-only closure policy review')
    expected_units = {'module:an.mth_octave_analyzer6e_tpt_df', 'module:an.mth_octave_spectral_level6e', 'module:fi.lowpass6e_tpt_df', 'module:fi.highpass6e_tpt_df'}
    if len(contracts['rows']) != 4 or {r['unit_id'] for r in contracts['rows']} != expected_units:
        raise ValueError('modular target coverage mismatch')
    pairs = []
    for row in contracts['rows']:
        if row['target_sha256'] == SOURCE:
            raise ValueError('original target must not masquerade as complete repaired source')
        pairs.append(dict(unit_id=row['unit_id'], target_sha256=row['target_sha256'],
                          qualified=False, numerical_evidence_transferred=False,
                          reason='Repaired source differs from this original modular target/context'))
    return dict(status='BOUNDED_REPAIR_VERIFIED_NOT_ADMITTED', source_sha256=SOURCE,
                numerical_scope='three bands, M=3, tau=.01, offset=0, 2–6kHz, four rates, two retained schedules',
                wasm_cases=24, modular_cases=24, bounded_wasm_jobs=149,
                original_closure_rights=closures, original_modular_pairs=pairs,
                comparison_connected=family['comparison_connected'],
                family=family['family'], family_graph=family['graph'],
                remaining=['canonical repaired-source and prompt/context admission',
                           'training-only dependency policy prevents evaluation eligibility',
                           'independent evaluation families', 'authenticated signed split and trusted key binding',
                           'scoped baseline, reward, environment and pilot evidence'],
                admission='NOT_GRANTED', pilot_ready=False, training_authorized=False,
                authority='LOCAL_DIAGNOSTIC_BINDING_NOT_CRYPTOGRAPHIC_AUTHENTICATION')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('rights', 'family', 'wasm', 'modular', 'contracts', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    names = ('rights', 'family', 'wasm', 'modular', 'contracts')
    raw = {n: getattr(args, n).read_bytes() for n in names}
    result = bind_review(**{n: json.loads(b) for n, b in raw.items()})
    result['input_sha256'] = {n: hashlib.sha256(b).hexdigest() for n, b in raw.items()}
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()

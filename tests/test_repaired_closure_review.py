"""Repaired numerical evidence must not qualify another target or a signed gate."""
import copy
import json
from pathlib import Path
import pytest
from diagnostics.repaired_closure_review import bind_review

ROOT = Path(__file__).resolve().parents[1] / 'docs/analysis'

@pytest.fixture
def evidence():
    names = dict(rights='repaired-closure-rights', family='presplit-closure-family',
                 wasm='presplit-wasm-verification', modular='presplit-modular-verification',
                 contracts='original-modular-target-bindings')
    return {k: json.loads((ROOT / (v+'-2026-10-24.json')).read_text()) for k,v in names.items()}


def test_bound_success_preserves_admission_and_target_boundaries(evidence):
    result = bind_review(**evidence)
    assert result['wasm_cases'] == result['modular_cases'] == 24
    assert result['comparison_connected']
    assert not result['pilot_ready'] and not result['training_authorized']
    assert result['admission'] == 'NOT_GRANTED'
    assert all(not x['qualified'] and not x['numerical_evidence_transferred'] for x in result['original_modular_pairs'])


@pytest.mark.parametrize('mutation', ['source','missing','duplicate','numerical','nan','negative','split','rights','targets'])
def test_incomplete_or_cross_source_evidence_is_refused(evidence, mutation):
    e = copy.deepcopy(evidence)
    if mutation == 'source': e['family']['source_sha256'] = '0'*64
    if mutation == 'missing': e['wasm']['rows'].pop()
    if mutation == 'duplicate': e['modular']['rows'][-1] = e['modular']['rows'][0]
    if mutation == 'numerical': e['modular']['rows'][0]['ratio'] = 1.01
    if mutation == 'nan': e['wasm']['rows'][0]['max_tolerance_ratio'] = float('nan')
    if mutation == 'negative': e['wasm']['rows'][0]['reset_ratio'] = .9
    if mutation == 'split': e['wasm']['split_full_audio_exact'] = False
    if mutation == 'rights': e['rights']['closures'][0]['eligible_for'].append('eval')
    if mutation == 'targets': e['contracts']['rows'][-1] = e['contracts']['rows'][0]
    with pytest.raises(ValueError): bind_review(**e)

import copy
import json
from pathlib import Path
import pytest
from diagnostics.exact_pair_review import bind_exact_pair
ROOT=Path(__file__).resolve().parents[1]/'docs/analysis'
@pytest.fixture
def evidence():
    names={'contract':'exact-pair-contract','products':'mulk-constant-verification','closure':'repaired-closure-binding'}
    return {k:json.loads((ROOT/(v+'-2026-10-24.json')).read_text()) for k,v in names.items()}

def test_exact_packet_is_not_admission(evidence):
    r=bind_exact_pair(**evidence)
    assert r['products_verified']==41328 and r['full_history_source_bound'] and r['comparison_connected']
    assert not any(r[k] for k in ('independent_semantic_approval','canonical_admission','signed_partition_membership','training_authorized','pilot_ready'))

@pytest.mark.parametrize('case',['prompt','context','promotion','encoding','token_count','source','history','duplicate','missing','control_coefficients','coefficient_coverage','negative','nan','samples'])
def test_mismatched_evidence_rejects(evidence,case):
    e=copy.deepcopy(evidence);c,p,h=e['contract'],e['products'],e['closure']
    if case=='prompt':c['prompt_sha256']='0'*64
    if case=='context':c['dependency_context_sha256']='0'*64
    if case=='promotion':c['qualified']=True
    if case=='encoding':c['tokenizer']['rows'][0]['pair_digest']='sha256:'+'0'*64
    if case=='token_count':c['tokenizer']['rows'][0]['total_tokens_with_eos']=513
    if case=='source':p['source_sha256']='0'*64
    if case=='history':h['bounded_wasm_jobs']=148
    if case=='duplicate':p['rows'][-1]=p['rows'][0]
    if case=='missing':p['rows'].pop()
    if case=='control_coefficients':p['rows'][1]['coefficients'][0][0]=123
    if case=='coefficient_coverage':
        for row in p['rows']:row['coefficients']=[row['coefficients'][0]]*7
    if case=='negative':p['rows'][1]['decimal80_ratio']=.5
    if case=='nan':p['rows'][0]['decimal80_ratio']=float('nan')
    if case=='samples':p['rows'][0]['samples']=983
    with pytest.raises(ValueError):bind_exact_pair(**e)

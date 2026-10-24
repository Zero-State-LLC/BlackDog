"""Synthetic saved-sample evidence must not become admission or training permission."""
import copy
import json
import struct

import pytest

from faustcoder.errors import ArtifactStoreError
from faustcoder.pair_signal import coefficients, replay, replay_samples
from faustcoder.public_pairs import digest
from faustcoder.readiness import assess
from faustcoder.readiness_manifest import ManifestError
from tests.test_public_pairs import SCOPE, bundle, change


@pytest.fixture
def signal(bundle):
    root, pairs, put = bundle
    contract = json.loads((root/'contract.json').read_bytes())
    contract['reference_formula'] = 'y[0,n] = x[0,n]'
    cref = put('contract.json', contract)
    pairs['units'][0]['contract'] = cref
    change(bundle, 'behavior', lambda x: x['contracts'][0].update(contract_sha256=cref['sha256']))
    change(bundle, 'local_closures', lambda x: x[0].update(
        original_approved_contract_sha256=cref['sha256'], executed_corrected_contract_sha256=cref['sha256']))
    pair_ref = put('pairs.json', pairs)
    inp = put('input.f32', struct.pack('<4096f', *([0.125, -0.125] * 2048)))
    bad = put('mutant.f32', struct.pack('<4096f', *([0.0] * 4096)))
    wasm = put('module.wasm', b'synthetic inert wasm bytes')
    mutant = put('mutant.dsp', b'process = 0;\n')
    cases = []
    for rate in (44100, 48000):
        for mode in ('sweep', 'default', 'mutant'):
            for probe in (('alternating',) if mode == 'mutant' else ('impulse', 'alternating', 'multitone')):
                plan = {'uid':'one','inputs':1,'outputs':1,'rate':rate,'probe':probe,
                        'states':[{'controls':{},'weights':[1]}],
                        'contract_sha256':cref['sha256'], 'wasm_sha256':wasm['sha256'],
                        'source_sha256':contract['identity']['source_sha256'],
                        'initializeOnly':mode == 'default', 'expectReject':mode == 'mutant'}
                if mode == 'mutant':
                    plan.update(original_source_sha256=plan['source_sha256'],mutant_source_sha256=mutant['sha256'])
                row = {'plan':put(f'{rate}-{mode}-{probe}.json',plan),'contract':cref,
                       'wasm':wasm,'input':inp,'output':bad if mode=='mutant' else inp}
                if mode=='mutant':row['mutant_source']=mutant
                cases.append(row)
    value = {'schema_version':1,'kind':'public-pair-signal.v1','scope_digest':SCOPE,
             'public_pairs':pair_ref,'cases':cases}
    return root,value,put


def run(signal):
    return replay(json.dumps(signal[1]).encode(), signal[0], scope_digest=SCOPE)


def edit_plan(signal, edit, index=0):
    root,value,put=signal
    ref=value['cases'][index]['plan']
    plan=json.loads((root/ref['path']).read_bytes())
    edit(plan)
    value['cases'][index]['plan']=put(ref['path'],plan)


def test_complete_saved_replay_preserves_blockers(signal):
    result=run(signal)
    assert result == run(signal)
    assert result['signal_replay']['cases_replayed']==14
    assert result['signal_replay']['states_replayed']==14
    assert result['signal_replay']['mutants_rejected']==2
    assert result['qualified_pairs']==0 and result['clears_readiness_gates']==[]
    assert 'compiler_signal_replay' in result['remaining']
    assert 'canonical_example_admission' in result['remaining']
    assert 'process = ' not in json.dumps(result)


@pytest.mark.parametrize('field,value', [('uid','absent'),('rate',96000),('probe','noise'),
    ('inputs',2),('contract_sha256','f'*64),('wasm_sha256','f'*64),
    ('source_sha256','sha256:'+'f'*64),('expectReject','false'),('initializeOnly',1)])
def test_plan_bindings(signal,field,value):
    edit_plan(signal, lambda p:p.update({field:value}))
    with pytest.raises(ManifestError):run(signal)


@pytest.mark.parametrize('field',['input','output','wasm','contract','plan'])
def test_tampered_payload(signal,field):
    root,value,_=signal
    (root/value['cases'][0][field]['path']).write_bytes(b'changed')
    with pytest.raises(ManifestError):run(signal)


def test_mutant_must_differ_from_original(signal):
    edit_plan(signal,lambda p:p.update(mutant_source_sha256='f'*64),6)
    with pytest.raises(ManifestError,match='mutant source'):run(signal)


def test_mutant_must_fail_reference(signal):
    signal[1]['cases'][6]['output']=signal[1]['cases'][6]['input']
    with pytest.raises(ManifestError,match='unexpected signal'):run(signal)


def test_positive_mismatch_even_when_rehashed(signal):
    signal[1]['cases'][0]['output']=signal[1]['cases'][6]['output']
    with pytest.raises(ManifestError,match='unexpected signal'):run(signal)


def test_changed_executed_contract_even_with_rebound_plan(signal):
    root,value,put=signal
    c=json.loads((root/'contract.json').read_bytes());c['reference_formula']='y[0,n]=0'
    value['cases'][0]['contract']=put('changed.json',c)
    edit_plan(signal,lambda p:p.update(contract_sha256=value['cases'][0]['contract']['sha256']))
    with pytest.raises(ManifestError,match='contract binding'):run(signal)


def test_duplicate_cannot_replace_missing_coverage(signal):
    signal[1]['cases'][-1]=copy.deepcopy(signal[1]['cases'][0])
    with pytest.raises(ManifestError,match='duplicate signal'):run(signal)


def test_missing_case(signal):
    signal[1]['cases'].pop()
    with pytest.raises(ArtifactStoreError):run(signal)


def test_case_mode_cannot_be_relabeled(signal):
    edit_plan(signal,lambda p:p.update(initializeOnly=True))
    with pytest.raises(ManifestError):run(signal)


def test_states_must_agree_across_probes(signal):
    edit_plan(signal,lambda p:p['states'][0].update(weights=[0.5]),1)
    with pytest.raises(ManifestError,match='state plan differs'):run(signal)


@pytest.mark.parametrize('value',[float('nan'),float('inf'),0.25])
def test_bad_input_samples_even_when_rehashed(signal,value):
    signal[1]['cases'][0]['input']=signal[2]('bad-input.f32',struct.pack('<4096f',*([value]*4096)))
    with pytest.raises(ManifestError):run(signal)


def test_bad_sample_length(signal):
    signal[1]['cases'][0]['input']=signal[2]('short.f32',b'\0'*4)
    with pytest.raises(ManifestError,match='sample length'):run(signal)


@pytest.mark.parametrize('formula', ['y[0,n]=__import__("os")','y[0,n]=x[0,n]*x[0,n]',
    'y[0,n]=x[0,n]/0','y[0,n]=x[0,n]**2','y[0,n]=x[True,n]',
    'y[0,n]=x[0,n+1]','y[0,n]=x[0,n];y[0,n]=0','y[1,n]=0',
    'y[0,n]=True','y[0,n]=1e999','import os','y[0,n]=x[0,n].real'])
def test_unsafe_or_nonaffine_formula(formula):
    with pytest.raises(ManifestError):coefficients(formula,{},1,1)


def test_affine_multichannel_reference():
    assert coefficients('y[0,n]=gain*x[0,n]-x[1,n]/2; y[1,n]=-x[0,n]+0.1',
                        {'gain':0.25},2,2)==[(0.0,[0.25,-0.5]),(0.1,[-1.0,0.0])]


@pytest.mark.parametrize('path',['../input.f32','/tmp/input.f32','private/samples.f32'])
def test_unsafe_path(signal,path):
    signal[1]['cases'][0]['input']['path']=path
    with pytest.raises((ManifestError,OSError)):run(signal)


def test_symlink(signal):
    root,_,_=signal
    (root/'input.f32').rename(root/'real.f32');(root/'input.f32').symlink_to(root/'real.f32')
    with pytest.raises(OSError):run(signal)


def test_wrong_scope(signal):
    signal[1]['scope_digest']='b'*64
    with pytest.raises(ManifestError,match='scope'):run(signal)


def test_unknown_descriptor_field(signal):
    signal[1]['tolerance']=1.0
    with pytest.raises(ArtifactStoreError):run(signal)


def test_readiness_replays_and_preserves_authorization(signal):
    root,value,put=signal
    ref=put('signal.json',value)
    put('manifest.json',{'schema_version':1,'mode':'pilot','scope_digest':SCOPE,'receipts':[
        {'receipt_id':'samples','gate':'public_instruction_pair_signal',**ref,
         'scope_digest':SCOPE,'outcome':'PASS'}]})
    result=assess(root,manifest_path=root/'manifest.json',evidence_root=root,scope_digest=SCOPE)
    assert result['training_authorized'] is False and result['pilot_ready'] is False
    assert result['receipt_verification']['public_pair_reviews'][0]['signal_replay']['cases_replayed']==14
    (root/'input.f32').write_bytes(b'bad')
    result=assess(root,manifest_path=root/'manifest.json',evidence_root=root,scope_digest=SCOPE)
    assert any(b['code']=='invalid_saved_signal' for b in result['receipt_verification']['blockers'])


def test_nonfinite_output(signal):
    signal[1]['cases'][0]['output']=signal[2]('nan-output.f32',struct.pack('<4096f',*([float('nan')]*4096)))
    with pytest.raises(ManifestError,match='nonfinite'):run(signal)


def test_fixed_tolerance_accepts_roundoff_rejects_larger_error(signal):
    root,value,_=signal
    plan=json.loads((root/value['cases'][0]['plan']['path']).read_bytes())
    contract=json.loads((root/'contract.json').read_bytes())
    raw=struct.pack('<4096f',*([0.125]*4096))
    near=struct.pack('<4096f',*([0.125+2e-6]*4096))
    far=struct.pack('<4096f',*([0.125+5e-6]*4096))
    assert replay_samples(plan,contract,raw,near)['mismatch_samples']==0
    with pytest.raises(ManifestError,match='unexpected signal'):replay_samples(plan,contract,raw,far)


def test_wrong_reference_must_also_be_rejected(signal):
    root,value,_=signal
    plan=json.loads((root/value['cases'][6]['plan']['path']).read_bytes())
    contract=json.loads((root/'contract.json').read_bytes())
    raw=struct.pack('<4096f',*([0.125]*4096))
    wrong=struct.pack('<4096f',*([0.15625]*4096))
    with pytest.raises(ManifestError,match='wrong reference'):replay_samples(plan,contract,raw,wrong)


def test_rebound_closure_cannot_change_approved_formula(signal):
    root,value,put=signal
    pairs=json.loads((root/'pairs.json').read_bytes())
    c=json.loads((root/'contract.json').read_bytes());c['reference_formula']='y[0,n]=0'
    ref=put('changed-contract.json',c);value['cases'][0]['contract']=ref
    edit_plan(signal,lambda p:p.update(contract_sha256=ref['sha256']))
    local=json.loads((root/'closures.json').read_bytes());local[0]['executed_corrected_contract_sha256']=ref['sha256']
    pairs['receipts']['local_closures']=put('closures.json',local)
    value['public_pairs']=put('pairs.json',pairs)
    with pytest.raises(ManifestError,match='approved contract changed'):run(signal)


def test_import_scope_must_match_even_with_rebound_closure(signal):
    root,value,put=signal
    pairs=json.loads((root/'pairs.json').read_bytes())
    c=json.loads((root/'contract.json').read_bytes());c['declared_import_scope']='other.lib'
    ref=put('changed-contract.json',c);value['cases'][0]['contract']=ref
    edit_plan(signal,lambda p:p.update(contract_sha256=ref['sha256']))
    local=json.loads((root/'closures.json').read_bytes());local[0]['executed_corrected_contract_sha256']=ref['sha256']
    pairs['receipts']['local_closures']=put('closures.json',local)
    value['public_pairs']=put('pairs.json',pairs)
    with pytest.raises(ManifestError,match='executed import mismatch'):run(signal)

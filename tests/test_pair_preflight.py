"""Synthetic tokenizer tests; real Qwen assets are never committed."""
import builtins
import copy
import json
from pathlib import Path

import pytest
from tokenizers import Tokenizer, models, pre_tokenizers

from faustcoder.errors import ArtifactStoreError
from faustcoder import pair_preflight as module
from faustcoder.pair_preflight import LocalTokenizer, inspect_encodings, preflight, main
from faustcoder.public_pairs import digest
from faustcoder.readiness import assess
from faustcoder.readiness_manifest import ManifestError
from tests.test_public_pairs import bundle, SCOPE


def assets():
    t=Tokenizer(models.WordLevel({'<eos>':0,'<pad>':1,'<unk>':2,'x':3},unk_token='<unk>'))
    t.pre_tokenizer=pre_tokenizers.WhitespaceSplit()
    return {'tokenizer.json':t.to_str().encode(),
            'tokenizer_config.json':json.dumps({'tokenizer_class':'Qwen2Tokenizer','eos_token':'<eos>',
                                              'pad_token':'<pad>','bos_token':None}).encode(),
            'vocab.json':b'{"fixture":true}', 'merges.txt':b'fixture merge table'}


@pytest.fixture
def ready(bundle,monkeypatch):
    root,value,put=bundle
    data=assets()
    monkeypatch.setattr(module,'TOKENIZER_HASHES',{name:digest(raw) for name,raw in data.items()})
    files={name:put(name,raw) for name,raw in data.items()}
    descriptor={'schema_version':1,'kind':'public-pair-tokenizer.v1','scope_digest':SCOPE,
                'public_pairs':put('pairs.json',value),
                'tokenizer':{'model':module.MODEL,'revision':module.REVISION,'files':files}}
    return root,descriptor,put


def run(ready):return preflight(json.dumps(ready[1]).encode(),ready[0],scope_digest=SCOPE)


def test_replays_pinned_assets_and_never_qualifies(ready):
    result=run(ready)
    assert result==run(ready)
    assert result['tokenizer']['accepted_encodings']==1
    assert result['qualified_pairs']==0 and result['clears_readiness_gates']==[]
    assert 'tokenizer_sequence_bound' not in result['remaining']
    assert 'compiler_signal_replay' in result['remaining']
    assert 'signed_partition_membership' in result['remaining']
    assert 'prompt_semantic_validation' in result['remaining']
    assert 'process = _' not in json.dumps(result)
    assert 'input_ids' not in json.dumps(result)


@pytest.mark.parametrize('name',list(module.TOKENIZER_HASHES))
def test_rehashed_asset_cannot_enroll_new_tokenizer(ready,name):
    root,value,put=ready
    value['tokenizer']['files'][name]=put(name,b'tampered')
    with pytest.raises(ManifestError,match='unapproved'):run(ready)


@pytest.mark.parametrize('field,value',[('revision','a'*40),('model','other/model')])
def test_unknown_model_or_revision(ready,field,value):
    ready[1]['tokenizer'][field]=value
    with pytest.raises(ArtifactStoreError):run(ready)


def test_scope_mismatch(ready):
    ready[1]['scope_digest']='b'*64
    with pytest.raises(ManifestError,match='scope'):run(ready)


def test_pair_receipt_tampering(ready):
    (ready[0]/'source.dsp').write_text('process = 0;')
    with pytest.raises(ManifestError):run(ready)


@pytest.mark.parametrize('path',['../tokenizer.json','private/tokenizer.json','/etc/passwd'])
def test_unsafe_paths(ready,path):
    ready[1]['tokenizer']['files']['tokenizer.json']['path']=path
    with pytest.raises((ManifestError,OSError)):run(ready)


def test_symlink_refused(ready):
    root,_,_=ready
    (root/'tokenizer.json').rename(root/'actual.json')
    (root/'tokenizer.json').symlink_to(root/'actual.json')
    with pytest.raises(OSError):run(ready)


@pytest.mark.parametrize('feature',['truncation','padding'])
def test_backend_hidden_transformations_refused(feature):
    data=assets();t=Tokenizer.from_str(data['tokenizer.json'].decode())
    if feature=='truncation':t.enable_truncation(3)
    else:t.enable_padding(length=10)
    data['tokenizer.json']=t.to_str().encode()
    with pytest.raises(ManifestError,match='truncation or padding'):LocalTokenizer(data)


def pair(prompt='x',target='x'):
    return {'example_id':'one','prompt':prompt,'target':target,'pair_digest':'a'*64,
            'prompt_digest':'sha256:'+digest(prompt.encode()),'target_digest':'sha256:'+digest(target.encode())}


def test_exact_bound_and_oversize_no_truncation():
    t=LocalTokenizer(assets())
    accepted=inspect_encodings((pair(' '.join(['x']*510)),),t)
    assert accepted['rows'][0]['total_tokens_with_eos']==512
    assert accepted['accepted_encodings']==1
    rejected=inspect_encodings((pair(' '.join(['x']*511)),),t)
    assert rejected['rows'][0]['total_tokens_with_eos']==513
    assert rejected['accepted_encodings']==0 and rejected['rejected_encodings']==1
    assert 'encoding_digest' not in rejected['rows'][0]


@pytest.mark.parametrize('which',['prompt','target'])
def test_pair_content_hash_binding(which):
    p=pair();p[which]='changed'
    with pytest.raises(ManifestError,match='content changed'):inspect_encodings((p,),LocalTokenizer(assets()))


def test_changing_tokenizer_cannot_return_misleading_counts():
    class Changing:
        eos_token_id=0;pad_token_id=1;runtime_version='fixture'
        n=0
        def __len__(self):return 100
        def encode(self,text,*,add_special_tokens):
            self.n+=1
            return [3+self.n]
    with pytest.raises(ManifestError,match='changed during'):inspect_encodings((pair(),),Changing())


def test_missing_runtime_is_not_a_pass(ready,monkeypatch,capsys):
    original=builtins.__import__
    def blocked(name,*args,**kwargs):
        if name=='tokenizers':raise ImportError('unavailable')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',blocked)
    root,value,put=ready
    ref=put('preflight.json',value)
    assert main(['--bundle',str(root/ref['path']),'--bundle-sha256',ref['sha256'],
                 '--evidence-root',str(root),'--scope-digest',SCOPE])==2
    assert json.loads(capsys.readouterr().out)['code']=='tokenizer_runtime_required'


def test_readiness_replays_instead_of_trusting_pass(ready):
    root,value,put=ready
    ref=put('preflight.json',value)
    put('manifest.json',{'schema_version':1,'mode':'pilot','scope_digest':SCOPE,'receipts':[
        {'receipt_id':'encoding','gate':'public_instruction_pair_tokenizer',**ref,
         'scope_digest':SCOPE,'outcome':'PASS'}]})
    result=assess(root,manifest_path=root/'manifest.json',evidence_root=root,scope_digest=SCOPE)
    assert result['receipt_verification']['public_pair_reviews'][0]['tokenizer']['accepted_encodings']==1
    assert result['verified_gates']==[] and not result['training_authorized']
    assert {'instruction_pair_contract','source_rights','t07_signed_split','pilot_training_authorization'} <= {b['gate'] for b in result['blockers']}
    (root/'tokenizer.json').write_text('{}')
    result=assess(root,manifest_path=root/'manifest.json',evidence_root=root,scope_digest=SCOPE)
    assert any(b['code']=='invalid_pair_preflight' for b in result['blockers'])


def test_cli_pins_descriptor_bytes(ready,capsys):
    root,value,put=ready
    ref=put('preflight.json',value)
    assert main(['--bundle',str(root/ref['path']),'--bundle-sha256','f'*64,
                 '--evidence-root',str(root),'--scope-digest',SCOPE])==2
    assert json.loads(capsys.readouterr().out)['code']=='invalid_pair_preflight'


@pytest.mark.parametrize('change',['extra','missing','duplicate_path'])
def test_strict_preflight_descriptor(ready,change):
    _,value,_=ready
    if change=='extra':value['training_authorized']=True
    if change=='missing':del value['tokenizer']['files']['merges.txt']
    if change=='duplicate_path':value['tokenizer']['files']['merges.txt']['path']='vocab.json'
    with pytest.raises((ManifestError,ArtifactStoreError)):run(ready)


def test_cli_success_is_not_training_qualification(ready,capsys):
    root,value,put=ready
    ref=put('preflight.json',value)
    assert main(['--bundle',str(root/ref['path']),'--bundle-sha256',ref['sha256'],
                 '--evidence-root',str(root),'--scope-digest',SCOPE])==0
    result=json.loads(capsys.readouterr().out)
    assert result['qualified_pairs']==0 and not result['clears_readiness_gates']


def test_empty_and_duplicate_candidates_refused():
    for pairs in [(),(pair(),pair())]:
        with pytest.raises(ManifestError):inspect_encodings(pairs,LocalTokenizer(assets()))


def test_wellformed_new_tokenizer_cannot_be_enrolled(ready):
    root,value,put=ready
    content=json.loads((root/'tokenizer.json').read_text())
    content['model']['vocab']['another']=4
    value['tokenizer']['files']['tokenizer.json']=put('tokenizer.json',content)
    with pytest.raises(ManifestError,match='unapproved tokenizer'):run(ready)


def test_wellformed_asset_byte_change_cannot_bypass_digest(ready):
    root,_,_=ready
    content=json.loads((root/'tokenizer.json').read_text())
    content['model']['vocab']['another']=4
    (root/'tokenizer.json').write_text(json.dumps(content))
    with pytest.raises(ManifestError,match='digest mismatch'):run(ready)

"""Public fixtures only: receipt joins must never imply training qualification."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from faustcoder.errors import ArtifactStoreError
from faustcoder.public_pairs import digest, review_bundle
from faustcoder.readiness import assess
from faustcoder.readiness_manifest import ManifestError

SCOPE = 'a' * 64


@pytest.fixture
def bundle(tmp_path):
    def put(name, value):
        raw = value if isinstance(value, bytes) else json.dumps(value).encode()
        (tmp_path / name).write_bytes(raw)
        return {'path': name, 'sha256': digest(raw)}
    source = b'process = _;\n'
    dossier = put('dossier.json', {'synthetic': True})
    notice = put('notice.txt', b'Synthetic MIT notice fixture')
    r = {'unit_id': 'one', 'path': 'example.dsp', 'source_sha256': 'sha256:' + digest(source),
         'dossier_sha256': dossier['sha256'], 'commit': '1'*40,
         'source_git_blob': hashlib.sha1(b'blob ' + str(len(source)).encode() + b'\0' + source).hexdigest(),
         'copy_decision': 'NOT_COPY', 'notice_scope_decision': 'APPROVED_REPOSITORY_LEVEL_MIT',
         'production_admission': 'NOT_GRANTED'}
    contract = {'unit_id': 'one', 'identity': {k:r[k] for k in ('unit_id','path','source_sha256','dossier_sha256')},
                'pin': r['commit'], 'source_blob': r['source_git_blob'], 'inputs': 1, 'outputs': 1,
                'control_values': {}, 'reference_formula': 'y=x', 'sample_rates': [44100,48000],
                'input_domain': 'bounded deterministic signals', 'cases': ['identity'],
                'declared_import_scope': 'none'}
    cref = put('contract.json', contract)
    b = {**r, 'pin': r['commit'], 'source_blob': r['source_git_blob'],
         'contract_sha256': cref['sha256'], 'decision': 'APPROVE_BEHAVIORAL_CONTRACT',
         'correction_required': False}
    local = {**r, 'git_blob': r['source_git_blob'], 'original_approved_contract_sha256': cref['sha256'],
             'decision':'CLOSURE_ACCEPTED_SOURCE_LOCAL_ONLY', 'production_admission':False,
             'authority_status':'OWNER_CONFIRMED_DELEGATED_AGENT_REVIEW', 'human_review':False,
             'reviewer':'synthetic agent'}
    receipts = {'rights':put('rights.json', {'units':[r], 'notice_sha256':notice['sha256']}),
                'behavior':put('behavior.json', {'contracts':[b]}),
                'local_closures':put('closures.json', [local]),
                'owner_confirmation':put('confirmation.json', {
                    'review_type':'DELEGATED_AGENT_REVIEW_NOT_HUMAN_REVIEW',
                    'independence_status':'WAIVED_BY_OWNER_NOT_INDEPENDENT',
                    'production_admission':False, 'delegated_reviewer':'synthetic agent'}),
                'imported_closures':put('imports.json', {'rows':[], 'production_admission':False}),
                'imported_header':put('header.txt', b'Synthetic LGPL header and exception'),
                'imported_notice':put('import-notice.json', {
                    'decision':'APPROVED_SCOPED_IMPORTED_NOTICE_HANDLING','units':[],
                    'preserved_notice_sha256':{'GRAME-header.txt':digest(b'Synthetic LGPL header and exception')}}),
                'notice':notice}
    value = {'schema_version':1,'kind':'public-pair-review.v1','scope_digest':SCOPE,
             'receipts':receipts, 'units':[{'unit_id':'one','source':put('source.dsp',source),
                                         'contract':cref,'dossier':dossier}]}
    return tmp_path, value, put


def run(bundle):
    root, value, _ = bundle
    return review_bundle(json.dumps(value).encode(), root, scope_digest=SCOPE)


def change(bundle, receipt, edit):
    root, value, put = bundle
    ref = value['receipts'][receipt]
    content = json.loads((root/ref['path']).read_bytes())
    edit(content)
    value['receipts'][receipt] = put(ref['path'], content)


def test_deterministic_bound_candidates_not_qualified(bundle):
    report, pairs = run(bundle)
    assert run(bundle) == (report, pairs)
    assert report['candidate_pairs'] == 1 and report['qualified_pairs'] == 0
    assert report['clears_readiness_gates'] == []
    assert pairs[0]['target'] == 'process = _;\n'
    assert pairs[0]['prompt_digest'] == 'sha256:' + digest(pairs[0]['prompt'].encode())
    assert pairs[0]['notice'] == 'Synthetic MIT notice fixture'
    assert 'process = _' not in json.dumps(report)
    assert 'signed_partition_membership' in pairs[0]['qualification_blockers']


@pytest.mark.parametrize('field,value', [('source_sha256','sha256:'+'f'*64),
    ('dossier_sha256','f'*64),('pin','2'*40),('source_blob','f'*40),
    ('decision','REJECT'),('contract_sha256','f'*64)])
def test_behavior_binding_drift(bundle, field, value):
    change(bundle,'behavior',lambda x:x['contracts'][0].update({field:value}))
    with pytest.raises(ManifestError): run(bundle)


@pytest.mark.parametrize('receipt', ['rights','behavior','local_closures','owner_confirmation',
                                     'imported_closures','notice'])
def test_tampered_receipts(bundle, receipt):
    root, value, _ = bundle
    (root/value['receipts'][receipt]['path']).write_bytes(b'tampered')
    with pytest.raises(ManifestError): run(bundle)


@pytest.mark.parametrize('field', ['source','contract','dossier'])
def test_payload_tamper_even_with_rehashed_descriptor(bundle, field):
    root,value,put=bundle
    ref=value['units'][0][field]
    value['units'][0][field]=put(ref['path'], b'{}')
    with pytest.raises(ManifestError): run(bundle)


@pytest.mark.parametrize('field,value', [('decision','UNRESOLVED'),('human_review',True),
    ('reviewer','different'),('production_admission',True),('git_blob','f'*40),
    ('original_approved_contract_sha256','f'*64)])
def test_missing_or_conflicting_closure(bundle, field, value):
    change(bundle,'local_closures',lambda x:x[0].update({field:value}))
    with pytest.raises(ManifestError): run(bundle)


def test_duplicate_unit(bundle):
    bundle[1]['units'].append(copy.deepcopy(bundle[1]['units'][0]))
    with pytest.raises(ManifestError): run(bundle)


def test_duplicate_receipt_rows(bundle):
    change(bundle,'behavior',lambda x:x['contracts'].append(copy.deepcopy(x['contracts'][0])))
    with pytest.raises(ManifestError): run(bundle)


@pytest.mark.parametrize('path', ['../source.dsp','/etc/passwd','private/source.dsp','holdout.txt'])
def test_unsafe_or_nonpublic_paths(bundle,path):
    bundle[1]['units'][0]['source']['path']=path
    with pytest.raises((ManifestError,OSError)): run(bundle)


def test_symlink(bundle):
    root, _, _ = bundle
    (root/'source.dsp').rename(root/'actual.dsp')
    (root/'source.dsp').symlink_to(root/'actual.dsp')
    with pytest.raises(OSError): run(bundle)


@pytest.mark.parametrize('field,value', [('schema_version',True),('extra',True),('scope_digest','b'*64)])
def test_schema_and_scope(bundle,field,value):
    bundle[1][field]=value
    with pytest.raises((ManifestError,ArtifactStoreError)): run(bundle)


def test_required_correction_cannot_be_ignored(bundle):
    change(bundle,'behavior',lambda x:x['contracts'][0].update(correction_required=True))
    with pytest.raises(ManifestError,match='correction'): run(bundle)


def test_readiness_integration_never_clears_rights_or_authorization(bundle):
    root,value,put=bundle
    descriptor=put('pairs.json',value)
    put('manifest.json',{'schema_version':1,'mode':'pilot','scope_digest':SCOPE,'receipts':[
        {'receipt_id':'pairs','gate':'public_instruction_pairs',**descriptor,
         'scope_digest':SCOPE,'outcome':'PASS'}]})
    report=assess(root,manifest_path=root/'manifest.json',evidence_root=root,scope_digest=SCOPE)
    assert report['receipt_verification']['public_pair_reviews'][0]['candidate_pairs']==1
    assert not report['verified_gates'] and not report['training_authorized']
    gates={b['gate'] for b in report['blockers']}
    assert {'source_rights','instruction_pair_contract','t07_signed_split','pilot_training_authorization'} <= gates
    assert 'process = _' not in json.dumps(report)
    (root/'source.dsp').write_text('changed')
    report=assess(root,manifest_path=root/'manifest.json',evidence_root=root,scope_digest=SCOPE)
    assert any(b['code']=='public_pair_binding_failed' for b in report['blockers'])


def imported(bundle):
    root,value,put=bundle
    source=b'import("stdfaust.lib");\nprocess = _;\n'
    sha='sha256:'+digest(source)
    blob=hashlib.sha1(b'blob '+str(len(source)).encode()+b'\0'+source).hexdigest()
    value['units'][0]['source']=put('source.dsp',source)
    contract=json.loads((root/'contract.json').read_bytes())
    contract['identity']['source_sha256']=sha
    contract['source_blob']=blob
    cref=put('contract.json',contract)
    value['units'][0]['contract']=cref
    def rights(x):x['units'][0].update(source_sha256=sha,source_git_blob=blob)
    change(bundle,'rights',rights)
    def behavior(x):
        x['contracts'][0].update(source_sha256=sha,source_blob=blob,contract_sha256=cref['sha256'],correction_required=True)
        x['approved_import_correction']={'paths':['example.dsp'],'declared_import':'import("stdfaust.lib")'}
    change(bundle,'behavior',behavior)
    def local(x):x[0].update(source_sha256=sha,git_blob=blob,original_approved_contract_sha256=cref['sha256'],decision='UNRESOLVED')
    change(bundle,'local_closures',local)
    r=json.loads((root/'rights.json').read_bytes())['units'][0]
    row={**r,'pin':r['commit'],'git_blob':blob,'production_admission':False,
         'decision':'ACCEPT_BOUNDED_SOURCE_AND_COMPILER_IMPORT_CLOSURE','decision_status':'OWNER_APPROVED',
         'native_resolution':{'library_sha256':'b'*64}}
    change(bundle,'imported_closures',lambda x:x['rows'].append(row))
    def notice(x):
        x['units']=[{**r,'resolved_library_binding':{'path':'stdfaust.lib','sha256':'b'*64}}]
        x['preserved_notice_sha256'].update({'stdfaust.lib':'b'*64,
            'LICENSE.MIT.Pierre-Guillot.txt':value['receipts']['notice']['sha256']})
    change(bundle,'imported_notice',notice)
    return bundle


def test_import_overlay_preserves_original_and_has_separate_provenance(bundle):
    imported(bundle)
    original=(bundle[0]/'contract.json').read_bytes()
    report,pairs=run(bundle)
    assert pairs[0]['import_correction_applied']
    assert 'stdfaust.lib' in pairs[0]['prompt']
    assert pairs[0]['contract_digest']==digest(original)
    assert (bundle[0]/'contract.json').read_bytes()==original
    assert report['units'][0]['closure_scope']=='RECORDED_OWNER_BOUNDED_IMPORT'
    assert report['qualified_pairs']==0
    assert pairs[0]['imported_notice']=='Synthetic LGPL header and exception'
    assert pairs[0]['library_source_redistribution']=='NOT_PREPARED_OR_AUTHORIZED'


@pytest.mark.parametrize('field,value',[('source_sha256','sha256:'+'f'*64),('pin','f'*40),
    ('git_blob','f'*40),('decision_status','PENDING'),('production_admission',True),('decision','REJECT')])
def test_import_receipt_conflicts(bundle,field,value):
    imported(bundle)
    change(bundle,'imported_closures',lambda x:x['rows'][0].update({field:value}))
    with pytest.raises(ManifestError):run(bundle)


def test_duplicate_reference_and_unknown_schema_fields(bundle):
    bundle[1]['units'][0]['dossier']=bundle[1]['units'][0]['source'].copy()
    with pytest.raises(ManifestError):run(bundle)


def test_duplicate_json_keys(bundle):
    raw=json.dumps(bundle[1]).replace('"schema_version": 1','"schema_version": 1, "schema_version": 1')
    with pytest.raises(ArtifactStoreError):review_bundle(raw.encode(),bundle[0],scope_digest=SCOPE)


def test_no_empty_selection_or_extra_training_claim(bundle):
    root,value,_=bundle
    value['training_authorized']=True
    with pytest.raises(ArtifactStoreError):run(bundle)
    value.pop('training_authorized')
    value['units']=[]
    with pytest.raises(ArtifactStoreError):run(bundle)


def test_rehashed_valid_contract_cannot_change_approved_formula(bundle):
    root,value,put=bundle
    contract=json.loads((root/'contract.json').read_bytes())
    contract['reference_formula']='y=2*x'
    value['units'][0]['contract']=put('contract.json',contract)
    with pytest.raises(ManifestError,match='unapproved contract bytes'):run(bundle)


def test_rehashed_notice_cannot_replace_approved_attribution(bundle):
    root,value,put=bundle
    value['receipts']['notice']=put('notice.txt',b'Different copyright owner')
    with pytest.raises(ManifestError,match='notice binding mismatch'):run(bundle)


@pytest.mark.parametrize('name,malformed',[('rights',[]),('behavior',None),('imported_closures',42),
                                         ('owner_confirmation',{})])
def test_malformed_legacy_objects_fail_closed(bundle,name,malformed):
    root,value,put=bundle
    ref=value['receipts'][name]
    value['receipts'][name]=put(ref['path'],malformed)
    with pytest.raises((ManifestError,TypeError,ArtifactStoreError)):run(bundle)


def test_imported_notice_binding_required(bundle):
    imported(bundle)
    change(bundle,'imported_notice',lambda x:x['units'][0].update(source_sha256='sha256:'+'f'*64))
    with pytest.raises(ManifestError,match='notice source'):run(bundle)


def test_imported_header_rehash_does_not_change_approved_notice(bundle):
    root,value,put=imported(bundle)
    value['receipts']['imported_header']=put('header.txt',b'Missing exception')
    with pytest.raises(ManifestError,match='header binding'):run(bundle)

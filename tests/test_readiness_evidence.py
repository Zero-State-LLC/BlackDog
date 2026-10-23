"""QR-09 semantic replay uses disposable signed public fixtures, no real keys."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from faustcoder.canonical import canonical_bytes, content_digest_for
from faustcoder.readiness import assess, main
from faustcoder.readiness_evidence import PublicEvidenceStore, load_scope, verify_split_evidence
from faustcoder.readiness_manifest import ManifestError, load_manifest, verify_manifest
from faustcoder.snapshot import commit_snapshot
from faustcoder.split import freeze_signed_split
from faustcoder.store import ArtifactStore
from tests.test_slice2 import signed_fixture


def dump(path, value):
    path.write_bytes(canonical_bytes(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def descriptor(root, store, snapshot, scope_digest, gate='t07_signed_split'):
    rows = []
    for artifact_id in store.list():
        obj = store.path_for(artifact_id)
        witness = store.envelope_digest_path_for(artifact_id)
        rows.append({'artifact_id':artifact_id,'path':str(obj.relative_to(root)),
                     'sha256':hashlib.sha256(obj.read_bytes()).hexdigest(),
                     'witness_path':str(witness.relative_to(root))})
    return {'schema_version':1,'kind':'signed_snapshot_verification','gate':gate,
            'scope_digest':scope_digest,'snapshot_digest':snapshot,'objects':rows}


@pytest.fixture
def evidence(tmp_path, signed_fixture):
    compiled, candidate, signature, public = signed_fixture
    root = tmp_path/'evidence-inputs'
    root.mkdir()
    store = ArtifactStore(root/'public-store')
    dedup = commit_snapshot(store, compiled)
    snapshot = freeze_signed_split(store, dedup, candidate, signature, public,
                                   created_at='2026-10-21T00:00:00Z')
    scope = {'schema_version':1,'mode':'pilot','dataset_snapshot_digest':snapshot,
             'code_revision':'b'*40,'model_digest':None,'recipe_digest':None}
    scope_path = root/'scope.json'
    scope_digest = dump(scope_path, scope)
    bundle = descriptor(root, store, snapshot, scope_digest)
    bundle_path = root/'bundle.json'
    receipt_hash = dump(bundle_path,bundle)
    index = {'schema_version':1,'mode':'pilot','scope_digest':scope_digest,'receipts':[
        {'receipt_id':'signed-split','gate':'t07_signed_split','path':'bundle.json',
         'sha256':receipt_hash,'scope_digest':scope_digest,'outcome':'PASS'}]}
    index_path = root/'index.json'
    dump(index_path,index)
    return dict(root=root,store=store,snapshot=snapshot,scope=scope,scope_path=scope_path,
                scope_digest=scope_digest,bundle=bundle,bundle_path=bundle_path,
                index=index,index_path=index_path,public=public)


def replay(e, gate='t07_signed_split', public=None, scope=None, bundle=None):
    return verify_split_evidence(canonical_bytes(e['bundle'] if bundle is None else bundle),
                                e['root'],gate=gate,scope_digest=e['scope_digest'],
                                scope=e['scope'] if scope is None else scope,
                                trusted_public_key=public or e['public'])


def test_canonical_signed_freeze_replayed_without_authorizing_training(evidence):
    result = replay(evidence)
    assert result['status'] == 'SEMANTICALLY_VERIFIED'
    assert result['token_floor_status'] == 'provisional'
    assert result['training_authorized'] is False
    assert result['p3_holdout_exit_allowed'] is False


def test_family_adapter_uses_same_signed_snapshot(evidence):
    b = copy.deepcopy(evidence['bundle'])
    b['gate'] = 'family_disjoint_split'
    assert replay(evidence,gate=b['gate'],bundle=b)['status'] == 'SEMANTICALLY_VERIFIED'


def test_readiness_removes_only_verified_gate(evidence):
    e = evidence
    result = assess(e['root'],manifest_path=e['index_path'],evidence_root=e['root'],
                    scope_digest=e['scope_digest'],scope_path=e['scope_path'],
                    trusted_split_public_key=e['public'])
    assert result['verified_gates'] == ['t07_signed_split']
    gates = {b['gate'] for b in result['blockers']}
    assert 't07_signed_split' not in gates
    assert 'family_disjoint_split' in gates and 'source_rights' in gates
    assert 'pilot_training_authorization' in gates and 'approved_pilot_dataset' in gates
    assert not result['training_authorized'] and not result['pilot_ready']


def test_missing_out_of_band_key_stays_unverified(evidence):
    e = evidence
    result = verify_manifest(load_manifest(e['index_path']),e['root'],mode='pilot',
                             scope_digest=e['scope_digest'],scope=e['scope'])
    assert not result['verified_gates']
    assert result['blockers'][0]['code'] == 'semantic_inputs_required'


def test_wrong_key_fails(evidence):
    wrong = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhY'
    with pytest.raises(ValueError): replay(evidence,public=wrong)


def test_key_cannot_be_declared_in_bundle(evidence):
    b = copy.deepcopy(evidence['bundle'])
    b['trusted_public_key'] = evidence['public']
    from faustcoder.errors import SchemaValidationError
    with pytest.raises(SchemaValidationError): replay(evidence,bundle=b)


@pytest.mark.parametrize('field', ['scope_digest','snapshot_digest','gate'])
def test_wrong_bundle_binding_fails(evidence, field):
    b = copy.deepcopy(evidence['bundle'])
    b[field] = ('family_disjoint_split' if field=='gate' else
                'c'*64 if field=='scope_digest' else 'sha256:'+'c'*64)
    with pytest.raises(ManifestError,match='scope'): replay(evidence,bundle=b)


def test_wrong_scope_snapshot_fails(evidence):
    scope = {**evidence['scope'],'dataset_snapshot_digest':'sha256:'+'f'*64}
    with pytest.raises(ManifestError): replay(evidence,scope=scope)


def test_expired_recheck_fails(evidence, monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setattr('faustcoder.split._utc_now',lambda:datetime(2028,1,1,tzinfo=timezone.utc))
    with pytest.raises(ValueError,match='recheck'): replay(evidence)


def test_missing_transition_prevents_freeze_verification(evidence):
    b = copy.deepcopy(evidence['bundle'])
    remove = next(row['artifact_id'] for row in b['objects']
                  if evidence['store'].get(row['artifact_id'])['payload'].get('event') == 'split_frozen')
    b['objects'] = [row for row in b['objects'] if row['artifact_id'] != remove]
    with pytest.raises(ValueError,match='incomplete freeze'): replay(evidence,bundle=b)


def test_missing_parent_fails(evidence):
    b = copy.deepcopy(evidence['bundle'])
    parent = evidence['store'].get(evidence['snapshot'])['parents'][0].split(':')[1]
    b['objects'] = [row for row in b['objects'] if row['artifact_id'] != parent]
    from faustcoder.errors import MissingParentError
    with pytest.raises(MissingParentError): replay(evidence,bundle=b)


def test_tampering_and_symlink_refused(evidence):
    row = evidence['bundle']['objects'][0]
    path = evidence['root']/row['path']
    original = path.read_bytes()
    path.write_bytes(original+b' ')
    with pytest.raises(ManifestError): replay(evidence)
    path.write_bytes(original)
    actual = path.with_name('actual')
    path.rename(actual)
    path.symlink_to(actual)
    with pytest.raises(OSError): replay(evidence)


@pytest.mark.parametrize('kind', ['id','path','witness'])
def test_duplicate_object_references_refused(evidence, kind):
    b = copy.deepcopy(evidence['bundle'])
    if kind=='id': b['objects'].append(copy.deepcopy(b['objects'][0]))
    if kind=='path': b['objects'][1]['path'] = b['objects'][0]['path']
    if kind=='witness': b['objects'][1]['witness_path'] = b['objects'][0]['witness_path']
    with pytest.raises(ManifestError): replay(evidence,bundle=b)


def test_witness_tampering_fails(evidence):
    row = evidence['bundle']['objects'][0]
    (evidence['root']/row['witness_path']).write_bytes(b'sha256:'+b'0'*64)
    with pytest.raises(ManifestError,match='witness'): replay(evidence)


def test_store_view_cannot_write(evidence):
    view = PublicEvidenceStore(evidence['root'], evidence['bundle']['objects'])
    with pytest.raises(ManifestError,match='read-only'): view.put({})


def test_scope_hash_and_schema_fail_closed(evidence):
    e = evidence
    assert load_scope(e['scope_path'],e['scope_digest'],'pilot') == e['scope']
    with pytest.raises(ManifestError): load_scope(e['scope_path'],'0'*64,'pilot')
    with pytest.raises(ManifestError): load_scope(e['scope_path'],e['scope_digest'],'full')
    e['scope_path'].write_bytes(b'{}')
    with pytest.raises(ManifestError): load_scope(e['scope_path'],hashlib.sha256(b'{}').hexdigest(),'pilot')


def test_public_key_cli_and_authorization_refusal(evidence, capsys):
    e = evidence
    key = e['root'].parent/'custodian.pub'
    key.write_text(e['public']+' fixture-comment\n')
    assert main(['--repo-root',str(e['root']),'--manifest',str(e['index_path']),
                 '--evidence-root',str(e['root']),'--scope-digest',e['scope_digest'],
                 '--scope-file',str(e['scope_path']),'--trusted-split-public-key',str(key),'--json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['verified_gates'] == ['t07_signed_split']
    assert result['training_authorized'] is False
    key.write_text('not a public key')
    assert main(['--trusted-split-public-key',str(key),'--json']) == 2
    assert json.loads(capsys.readouterr().out)['blockers'][0]['code'] == 'invalid_public_key_input'


def test_signed_split_does_not_clear_owner_authorization_gate(evidence):
    e = evidence
    index = copy.deepcopy(e['index'])
    index['receipts'][0]['gate'] = 'pilot_training_authorization'
    dump(e['index_path'],index)
    result = assess(e['root'],manifest_path=e['index_path'],evidence_root=e['root'],
                    scope_digest=e['scope_digest'],scope_path=e['scope_path'],
                    trusted_split_public_key=e['public'])
    assert result['verified_gates'] == []
    assert result['training_authorized'] is False
    assert any(b['gate']=='pilot_training_authorization' for b in result['blockers'])


def test_duplicate_gate_with_invalid_evidence_cannot_mask_blocker(evidence):
    e = evidence
    index = copy.deepcopy(e['index'])
    index['receipts'].append({**index['receipts'][0],'receipt_id':'invalid-split',
                              'path':'missing.json','sha256':'e'*64})
    dump(e['index_path'],index)
    result = assess(e['root'],manifest_path=e['index_path'],evidence_root=e['root'],
                    scope_digest=e['scope_digest'],scope_path=e['scope_path'],
                    trusted_split_public_key=e['public'])
    assert result['verified_gates'] == []
    assert any(b['gate']=='t07_signed_split' and b['status']=='INVALID' for b in result['blockers'])


def test_cycles_are_rejected_before_signed_replay(evidence):
    from faustcoder.canonical import build_envelope, content_digest_for
    from faustcoder.errors import CycleError
    e = evidence
    a = {'record_type':'SourceRecord','label':'a'}
    b = {'record_type':'SourceRecord','label':'b'}
    rows = []
    for payload,parent in ((a,content_digest_for(b)),(b,content_digest_for(a))):
        envelope = build_envelope(schema_version='1.0.0',created_at='2026-10-21T00:00:00Z',
                                  producer='synthetic-cycle-fixture',parents=[parent],payload=payload)
        artifact_id = envelope['artifact_id']
        obj = e['root']/(artifact_id+'.json')
        obj.write_bytes(canonical_bytes(envelope))
        witness = e['root']/(artifact_id+'.envelope_digest')
        witness.write_text('sha256:'+hashlib.sha256(obj.read_bytes()).hexdigest())
        rows.append({'artifact_id':artifact_id,'path':obj.name,'witness_path':witness.name,
                     'sha256':hashlib.sha256(obj.read_bytes()).hexdigest()})
    with pytest.raises(CycleError): PublicEvidenceStore(e['root'],rows)


def test_task_payload_rejected_even_when_hashes_are_valid(evidence):
    from faustcoder.canonical import build_envelope
    from faustcoder.errors import SchemaValidationError
    e = evidence
    envelope = build_envelope(schema_version='1.0.0',created_at='2026-10-21T00:00:00Z',
                              producer='synthetic-task-fixture',parents=[],
                              payload={'record_type':'TaskSpec','prompt':'Synthetic fixture only'})
    e['store'].put(envelope)
    b = descriptor(e['root'],e['store'],e['snapshot'],e['scope_digest'])
    with pytest.raises(SchemaValidationError): replay(e,bundle=b)


def test_scope_duplicate_keys_fail_as_machine_readable_blocker(evidence):
    e = evidence
    e['scope_path'].write_bytes(b'{"mode":"pilot","mode":"pilot"}')
    changed = hashlib.sha256(e['scope_path'].read_bytes()).hexdigest()
    result = assess(e['root'],manifest_path=e['index_path'],evidence_root=e['root'],
                    scope_digest=changed,scope_path=e['scope_path'],trusted_split_public_key=e['public'])
    assert not result['training_authorized']
    assert any(b['status']=='INVALID' for b in result['blockers'])


def test_bundle_size_bound(evidence, monkeypatch):
    monkeypatch.setattr('faustcoder.readiness_evidence.MAX_BUNDLE_BYTES',1)
    with pytest.raises(ManifestError,match='bounded'): replay(evidence)


def test_one_command_export_is_not_approval_and_replays_both_gates(evidence):
    from faustcoder.readiness_evidence import export_public_bundle
    e = evidence
    output = e['root']/'export'
    exported = export_public_bundle(e['store'].root,e['scope_path'],output,e['public'])
    assert exported['status'] == 'EXPORTED_REPLAY_REQUIRED'
    assert not exported['training_authorized']
    result = assess(e['root'],manifest_path=output/'readiness-manifest.json',evidence_root=output,
                    scope_digest=e['scope_digest'],scope_path=output/'scope.json',
                    trusted_split_public_key=e['public'])
    assert result['verified_gates'] == ['family_disjoint_split','t07_signed_split']
    assert not result['training_authorized'] and not result['pilot_ready']
    with pytest.raises(FileExistsError): export_public_bundle(e['store'].root,e['scope_path'],output,e['public'])


def test_export_preflight_refuses_tampered_input_before_writes(evidence):
    from faustcoder.readiness_evidence import export_public_bundle
    e = evidence
    row = e['bundle']['objects'][0]
    (e['root']/row['witness_path']).write_bytes(b'changed')
    target = e['root']/'no-output'
    with pytest.raises(ManifestError): export_public_bundle(e['store'].root,e['scope_path'],target,e['public'])
    assert not target.exists()


def test_export_refuses_source_directory_symlink(evidence):
    from faustcoder.readiness_evidence import export_public_bundle
    e = evidence
    alias = e['root']/'alias'
    alias.symlink_to(e['store'].root,target_is_directory=True)
    with pytest.raises(OSError): export_public_bundle(alias,e['scope_path'],e['root']/'no-output',e['public'])


def test_export_cli_machine_readable_missing_input(tmp_path, capsys):
    from faustcoder.readiness_evidence import main as export_main
    assert export_main(['--public-store',str(tmp_path/'missing'),'--scope-file',str(tmp_path/'scope'),
                        '--output',str(tmp_path/'output'),'--trusted-split-public-key',str(tmp_path/'custodian.pub')]) == 2
    assert json.loads(capsys.readouterr().out)['code'] == 'public_evidence_export_failed'


def test_export_wrong_signer_and_incomplete_freeze_write_nothing(evidence):
    from faustcoder.readiness_evidence import export_public_bundle
    e = evidence
    target = e['root']/'no-output'
    wrong = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhY'
    with pytest.raises(ValueError): export_public_bundle(e['store'].root,e['scope_path'],target,wrong)
    assert not target.exists()
    missing = next(r for r in e['bundle']['objects']
                   if e['store'].get(r['artifact_id'])['payload'].get('event') == 'split_frozen')
    (e['root']/missing['path']).unlink()
    (e['root']/missing['witness_path']).unlink()
    with pytest.raises(ValueError,match='incomplete freeze'):
        export_public_bundle(e['store'].root,e['scope_path'],target,e['public'])
    assert not target.exists()


def test_export_orphan_witness_refused(evidence):
    from faustcoder.readiness_evidence import export_public_bundle
    e = evidence
    (e['store'].root/'sha256'/('f'*64+'.envelope_digest')).write_text('sha256:'+'a'*64)
    with pytest.raises(ManifestError,match='orphan'):
        export_public_bundle(e['store'].root,e['scope_path'],e['root']/'no-output',e['public'])


def test_export_cli_suggests_an_executable_replay_command(evidence, capsys):
    from faustcoder.readiness_evidence import main as export_main
    e = evidence
    key = e['root'].parent/'custodian.pub'
    key.write_text(e['public']+'\n')
    assert export_main(['--public-store',str(e['store'].root),'--scope-file',str(e['scope_path']),
                        '--output',str(e['root']/'command-export'),
                        '--trusted-split-public-key',str(key)]) == 0
    exported = json.loads(capsys.readouterr().out)
    assert exported['next_command'][:3] == ['python','-m','faustcoder.readiness']
    assert main(exported['next_command'][3:]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['verified_gates'] == ['family_disjoint_split','t07_signed_split']
    assert not result['training_authorized']


def test_key_shipped_inside_bundle_cannot_enroll_itself(evidence, capsys):
    e = evidence
    key = e['root']/'untrusted-bundled-key.pub'
    key.write_text(e['public']+'\n')
    assert main(['--manifest',str(e['index_path']),'--evidence-root',str(e['root']),
                 '--scope-digest',e['scope_digest'],'--scope-file',str(e['scope_path']),
                 '--trusted-split-public-key',str(key),'--json']) == 2
    result = json.loads(capsys.readouterr().out)
    assert result['blockers'][0]['code'] == 'invalid_public_key_input'
    assert not result['training_authorized']


def test_verified_graph_is_reused_without_exposing_mutable_cache(evidence, monkeypatch):
    e = evidence
    calls = []
    original = ArtifactStore._assert_acyclic
    def counted(self, origin, parents):
        calls.append(origin)
        return original(self,origin,parents)
    monkeypatch.setattr(ArtifactStore,'_assert_acyclic',counted)
    view = PublicEvidenceStore(e['root'],e['bundle']['objects'])
    assert len(calls) == 1
    envelope = view.get(e['snapshot'])
    envelope['payload']['split_frozen'] = False
    assert view.get(e['snapshot'])['payload']['split_frozen'] is True
    for key in view.list(): view.get(key)
    assert len(calls) == 1

"""Recorded-family feasibility does not authorize graph edits or dataset admission."""
import json
import pytest
from faustcoder.pair_family import review, reconstruct
from faustcoder.readiness_manifest import ManifestError
from faustcoder.errors import ArtifactStoreError
from faustcoder.readiness import assess
from tests.test_public_pairs import bundle,SCOPE

F='sha256:'+'1'*64
G='sha256:'+'2'*64

@pytest.fixture
def family(bundle):
    root,pairs,put=bundle
    h=pairs['units'][0]['source']['sha256']
    data={'schema_version':1,'kind':'public-pair-family.v1','scope_digest':SCOPE,
          'public_pairs':put('pairs.json',pairs),
          'binding':put('binding.json',{'source_hashes':{'one':h,'comparison:c':'b'*64}}),
          'families':put('families.json',{'one':F,'comparison:c':F}),
          'ledger':put('ledger.json',[{'unit_id':'one','source_sha256':h,'family':F,'admission':'NOT_GRANTED'}]),
          'edges':put('edges.json',[{'left':'one','right':'comparison:c','reason':'exact','stream':'raw','floor':40}])}
    return root,data,put


def run(f):return review(json.dumps(f[1]).encode(),f[0],scope_digest=SCOPE)


def edit(f,key,change):
    root,v,put=f;ref=v[key];d=json.loads((root/ref['path']).read_bytes());change(d);v[key]=put(ref['path'],d)


def test_recorded_connected_family_blocks_partition(family):
    r=run(family)
    assert r==run(family) and r['status']=='PARTITION_INFEASIBLE'
    assert r['family_review']['selected_families']==1
    assert r['qualified_pairs']==0 and r['clears_readiness_gates']==[]
    assert not r['partition_assigned']


def test_rehashed_split_cannot_break_existing_edges(family):
    edit(family,'families',lambda d:d.update(one=G))
    edit(family,'ledger',lambda d:d[0].update(family=G))
    with pytest.raises(ManifestError,match='connected identities split'):run(family)


def test_removed_edges_cannot_preserve_false_same_family(family):
    edit(family,'edges',lambda d:d.clear())
    with pytest.raises(ManifestError,match='disconnected identities'):run(family)


@pytest.mark.parametrize('key',['public_pairs','binding','families','ledger','edges'])
def test_tampered_file(family,key):
    root,v,_=family;(root/v[key]['path']).write_text('{}')
    with pytest.raises((ManifestError,ArtifactStoreError)):run(family)


def test_population_missing(family):
    edit(family,'binding',lambda d:d['source_hashes'].pop('comparison:c'))
    with pytest.raises(ManifestError,match='population'):run(family)


def test_duplicate_ledger(family):
    edit(family,'ledger',lambda d:d.append(dict(d[0])))
    with pytest.raises(ManifestError,match='duplicate'):run(family)


def test_source_drift_even_when_ledger_and_binding_agree(family):
    edit(family,'binding',lambda d:d['source_hashes'].update(one='f'*64))
    edit(family,'ledger',lambda d:d[0].update(source_sha256='f'*64))
    with pytest.raises(ManifestError,match='selected source'):run(family)


def test_no_admission_claim(family):
    edit(family,'ledger',lambda d:d[0].update(admission='APPROVED'))
    with pytest.raises(ManifestError,match='unsupported recorded admission'):run(family)


def test_collective_hyperedge_joins_all_members():
    f={x:F for x in ['a','b','c','comparison:x']}
    e=[{'reason':'collective_support','comparison':'comparison:x','contributors':['a','b','c'],'floor':40,'stream':'canonical'}]
    assert reconstruct(f,e)['components']==1
    f['b']=G
    with pytest.raises(ManifestError,match='connected'):reconstruct(f,e)


@pytest.mark.parametrize('change',[
    lambda e:e.update(right='unknown'),lambda e:e.update(floor=20),lambda e:e.update(floor=True),
    lambda e:e.update(stream='other'),lambda e:e.update(reason='owner_waiver'),
    lambda e:e.update(contributors=['one'])])
def test_graph_policy_and_endpoints(family,change):
    edit(family,'edges',lambda d:change(d[0]))
    with pytest.raises(ManifestError):run(family)


def test_graph_bound():
    with pytest.raises(ManifestError,match='graph size'):reconstruct({'a':F},[{}]*50001)


def test_multiple_components_do_not_imply_qualification():
    assert reconstruct({'a':F,'b':G},[])['components']==2


@pytest.mark.parametrize('path',['../x.json','/tmp/x.json','private/graph.json'])
def test_unsafe_path(family,path):
    family[1]['edges']['path']=path
    with pytest.raises((ManifestError,OSError)):run(family)


def test_symlink(family):
    root,_,_=family;(root/'edges.json').rename(root/'real.json');(root/'edges.json').symlink_to(root/'real.json')
    with pytest.raises(OSError):run(family)


def test_wrong_scope(family):
    family[1]['scope_digest']='f'*64
    with pytest.raises(ManifestError,match='scope'):run(family)


def test_readiness_has_specific_blocker(family):
    root,v,put=family;ref=put('family-review.json',v)
    put('manifest.json',{'schema_version':1,'mode':'pilot','scope_digest':SCOPE,'receipts':[
        {'receipt_id':'family','gate':'public_instruction_pair_family',**ref,'scope_digest':SCOPE,'outcome':'PASS'}]})
    r=assess(root,manifest_path=root/'manifest.json',evidence_root=root,scope_digest=SCOPE)
    assert not r['training_authorized'] and not r['pilot_ready']
    assert any(b['code']=='single_recorded_family' for b in r['receipt_verification']['blockers'])
    (root/'edges.json').write_text('[]')
    r=assess(root,manifest_path=root/'manifest.json',evidence_root=root,scope_digest=SCOPE)
    assert any(b['code']=='invalid_recorded_family_graph' for b in r['receipt_verification']['blockers'])

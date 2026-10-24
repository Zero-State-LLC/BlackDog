"""Qualification must preserve coverage, provenance and non-approval gates."""
import copy
from pathlib import Path

import pytest

from diagnostics import span_qualification as q
from diagnostics import span_review as review
from faustcoder.errors import InventoryError
from test_span_review import sample, corpus_base


def fixture(sample):
    corpus,candidate,blobs,_=sample
    rows=review.candidate_rows(corpus,candidate,blobs)
    groups=[{'unit_ids':list(rows)}]
    closures=[dict(unit={'unit_id':uid},span=candidate['spans'][i],qualified_references=[],
                   unadmitted_local_names=[],local_candidates=[],includes_self_cycle=False,special_forms=[])
              for i,uid in enumerate(rows)]
    contracts=[dict(case='check',target='u1')]
    plan={'cases':[dict(id='check',expected='pass'),dict(id='check-wrong',expected='reference_refusal')]}
    results=[dict(case=c['id'],rate=rate,passed=True) for c in plan['cases'] for rate in review.RATES]
    return rows,groups,closures,contracts,plan,results


def test_bounded_pass_is_never_production_approval(sample):
    report=q.ledger(*fixture(sample))
    assert report['counts']=={'bounded_contract_pass':1,'blocked':1}
    assert not report['production_approved'] and not report['t07_frozen']
    assert report['token_floor']==40 and report['token_floor_status']=='provisional'
    assert all(u['admission_blockers'] and not u['production_approved'] for u in report['units'])


@pytest.mark.parametrize('mutation',['missing','duplicate','foreign','stale','empty_span'])
def test_coverage_and_stale_evidence_fail_closed(sample,mutation):
    args=list(fixture(sample))
    if mutation=='missing':args[1][0]['unit_ids'].pop()
    if mutation=='duplicate':args[1][0]['unit_ids'].append('u1')
    if mutation=='foreign':args[2][0]['unit']['unit_id']='foreign'
    if mutation=='stale':args[2][0]['span']=dict(args[2][0]['span'],sha256='sha256:'+'0'*64)
    if mutation=='empty_span':args[2][0]['span']={}
    with pytest.raises(ValueError):q.ledger(*args)


@pytest.mark.parametrize('mutation',['missing_rate','duplicate','unknown'])
def test_result_matrix_requires_exact_complete_coverage(sample,mutation):
    args=list(fixture(sample))
    if mutation=='missing_rate':args[-1].pop()
    if mutation=='duplicate':args[-1].append(args[-1][0])
    if mutation=='unknown':args[-1][0]['case']='other'
    with pytest.raises(ValueError,match='result matrix'):q.ledger(*args)


def test_failed_control_blocks_target(sample):
    args=list(fixture(sample));args[-1][-1]['passed']=False
    report=q.ledger(*args)
    assert report['counts']=={'blocked':2}
    assert report['units'][0]['blockers']==['behavioral_contract_failed']


def test_helper_presence_does_not_promote_untested_unit(sample):
    args=list(fixture(sample));args[3][0]['closure_unit_ids']=['u1','u2']
    report=q.ledger(*args)
    assert report['units'][1]['status']=='blocked'


def test_corrected_inventory_excludes_comment_examples_and_bare_nested_member(corpus_base):
    removed={'s1','sample1','sample2','sample3','play'}
    assert sum(bool(u.function) for u in corpus_base.units)==960
    assert not any(u.path=='soundfiles.lib' and u.function in removed for u in corpus_base.units)
    assert any(u.path=='soundfiles.lib' and u.function=='sound' for u in corpus_base.units)
    notice=review.read_json(Path('corpus/notice-manifest.v1.json'))
    assert not any(e['path']=='soundfiles.lib' and e.get('function') in removed for e in notice['entries'])


def test_corrected_pins_still_reject_unreviewed_inventory(corpus_base):
    inv=review.read_json('corpus/rights-inventory.v1.json');notice=review.read_json('corpus/notice-manifest.v1.json')
    inv['entries'][0]['file_count']+=1
    with pytest.raises(InventoryError,match='T05 pin'):review.parse_corpus(inv,notice)


def test_batching_preserves_every_reference_and_channel_range():
    cases=[dict(id=str(i),unit_ids=['u0'],process='*(.25)',expected='pass',reference=[{'0':.25}]*n,missing_dependency=None)
           for i,n in enumerate([2,3,2])]
    contracts=[dict(case=str(i),target='u'+str(i)) for i in range(3)]
    batches,mapped=q.batch_contracts(cases,contracts,max_channels=5)
    assert [len(b['reference']) for b in batches]==[5,2]
    assert [(c['channel_start'],c['channel_end']) for c in mapped]==[(0,2),(2,5),(0,2)]
    assert [v for b in batches for v in b['reference']]==[v for c in cases for v in c['reference']]
    assert batches[0]['unit_ids']==['u0']
    assert [c['original_case'] for c in mapped]==['0','1','2']
    assert all(c['control_scope']=='batch-wide corrupted reference' for c in mapped)


@pytest.mark.parametrize('bound',[0,33])
def test_batching_cannot_expand_signal_channel_limit(bound):
    with pytest.raises(ValueError,match='bound'):q.batch_contracts([],[],bound)


def test_outer_binding_rejects_changes_before_receipt_writes(tmp_path):
    out=tmp_path/'receipts'
    with q.qualification_output(out,{'plan':'original'}):
        (out/'plan.json').write_text('original receipt')
    with pytest.raises(ValueError,match='binding changed'):
        with q.qualification_output(out,{'plan':'changed'}):
            (out/'plan.json').write_text('overwritten')
    assert (out/'plan.json').read_text()=='original receipt'
    with q.qualification_output(out,{'plan':'original'}):pass


def test_outer_binding_refuses_unbound_existing_evidence(tmp_path):
    (tmp_path/'plan.json').write_text('old')
    with pytest.raises(ValueError,match='missing qualification binding'):
        with q.qualification_output(tmp_path,{}):pass
    assert (tmp_path/'plan.json').read_text()=='old'


def test_outer_lock_refuses_concurrent_reports(tmp_path):
    with q.qualification_output(tmp_path,{}):
        with pytest.raises(BlockingIOError):
            with q.qualification_output(tmp_path,{}):pass


@pytest.mark.parametrize('nested',[False,True])
def test_outer_output_refuses_symlinks(tmp_path,nested):
    real=tmp_path/'real';real.mkdir();out=tmp_path/'out'
    if nested:
        out.mkdir();(out/'plan.json').symlink_to(real/'plan.json')
    else:out.symlink_to(real,target_is_directory=True)
    with pytest.raises(ValueError,match='symlinks'):
        with q.qualification_output(out,{}):pass
    assert not list(real.iterdir())


def test_neighbor_cannot_supply_missing_closure(sample):
    from diagnostics import span_corpus as bulk
    corpus,candidate,blobs,_=sample
    candidate,_=bulk.propose(corpus,candidate,blobs)
    rows=review.candidate_rows(corpus,candidate,blobs)
    cases=[dict(id='missing',unit_ids=['u3'],process='beta(1)',expected='pass',reference=[{'0':.25}],missing_dependency=None),
           dict(id='neighbor',unit_ids=['u1','u2'],process='alpha(1)',expected='pass',reference=[{'0':.25}],missing_dependency=None)]
    contracts=[dict(case='missing',target='u3'),dict(case='neighbor',target='u1')]
    batches,mapped=q.batch_contracts(cases,contracts)
    assert [b['unit_ids'] for b in batches]==[['u3'],['u1','u2']]
    prepared=review.prepare_cases({'cases':batches},rows,blobs)
    assert 'beta=alpha;' in prepared[0][1]
    assert 'alpha(0)=' not in prepared[0][1] and 'alpha(x)=' not in prepared[0][1]
    assert mapped[0]['case']!=mapped[1]['case']


def test_overload_order_is_part_of_batch_closure():
    cases=[dict(id=str(i),unit_ids=ids,process='*(.25)',expected='pass',reference=[{'0':.25}],missing_dependency=None)
           for i,ids in enumerate([['u1','u2'],['u2','u1']])]
    batches,_=q.batch_contracts(cases,[dict(case=str(i),target='u1') for i in range(2)])
    assert [b['unit_ids'] for b in batches]==[['u1','u2'],['u2','u1']]


def test_helper_license_confirmation_does_not_clear_mixed_blob(corpus_base):
    """Exact MIT notices do not admit the surrounding mixed-rights filters blob."""
    helpers = {'_tanhalf', '_tpt_df'}
    row = 'faustlibraries-author-confirmed-helpers-mit'
    assert not [u for u in corpus_base.units if u.entry_id == row]
    excluded = [u for u in corpus_base.excluded if u.entry_id == row]
    assert {u.function for u in excluded} == helpers
    assert {u.reason for u in excluded} == {'needs-human'}

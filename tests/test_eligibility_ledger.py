"""Metadata-only accounting tests, no source admission or approval fixtures."""
import copy
import hashlib
import json

import pytest

from faustcoder.eligibility_ledger import reconcile, assess_batch, main


@pytest.fixture
def batch():
    rows = [{'unit_id': 'u1', 'blob_sha': 'a'*40, 'repo': 'org/repo', 'pin': 'b'*40,
             'path': 'one.dsp', 'source_sha256': 'sha256:'+'a'*64, 'family': 'f1',
             'status': 'historical', 'blockers': ['notice_review']}]
    return ({'units': rows}, {'p1': {'unit_ids': ['u1']}}, {'units': []},
            {'groups': []}, {'edges': []})


def expected():
    return dict(units=1, packets=1, blobs=1, short_groups=0, collective_sets=0)


def test_exact_accounting_is_not_eligibility(batch):
    result = reconcile(*batch, expected=expected())
    assert result['accounting_pass']
    assert result['production_admitted'] == 0
    assert not result['training_authorized']
    assert result['units'][0]['historical_status'] == 'historical'
    assert result['units'][0]['status'] == 'QUARANTINED'
    assert 'eligibility_receipts_not_semantically_verified' in result['exception_counts']
    assert result == reconcile(*copy.deepcopy(batch), expected=expected())


def test_full_scope_is_not_inferred_from_small_batch(batch):
    result = reconcile(*batch)
    assert not result['accounting_pass']
    assert result['exceptions'][0]['actual'] == 1
    assert result['exceptions'][0]['expected'] == 1430


@pytest.mark.parametrize('field', ['units', 'packets', 'blobs', 'short_groups', 'collective_sets'])
def test_wrong_counts_block(batch, field):
    scope = expected()
    scope[field] += 1
    assert reconcile(*batch, expected=scope)['exceptions'][0]['field'] == field


def test_duplicate_units_refused(batch):
    batch[0]['units'].append(copy.deepcopy(batch[0]['units'][0]))
    with pytest.raises(ValueError, match='duplicate'): reconcile(*batch)


def test_duplicate_or_unknown_members_refused(batch):
    batch[1]['p1']['unit_ids'].append('u1')
    with pytest.raises(ValueError, match='multiply'): reconcile(*batch)
    batch[1]['p1']['unit_ids'] = ['unknown']
    with pytest.raises(ValueError, match='unknown'): reconcile(*batch)


def test_missing_packet_refused(batch):
    batch[1].clear()
    with pytest.raises(ValueError, match='coverage'): reconcile(*batch)


def write_batch(tmp_path, batch):
    ledger, packets, comparisons, short, matches = batch
    payloads = {'candidate-ledger.json': ledger, 'comparison-ledger.json': comparisons,
                'short-collision-groups.json': short, 'match-evidence.json': matches,
                'packet-index.json': [{'packet_id': key, 'members': len(p['unit_ids'])}
                                      for key, p in packets.items()]}
    payloads.update({'packets/'+k+'.json': p for k,p in packets.items()})
    outputs = {}
    for name, value in payloads.items():
        p = tmp_path/name
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(value))
        outputs[name] = {'sha256': 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()}
    binding = tmp_path/'binding.json'
    binding.write_text(json.dumps({'outputs': outputs}))
    return hashlib.sha256(binding.read_bytes()).hexdigest()


def test_bound_batch_replay(tmp_path, batch):
    digest = write_batch(tmp_path, batch)
    result = assess_batch(tmp_path, digest)
    assert result['binding_sha256'] == digest
    assert result['report']['counts']['units'] == 1
    assert not result['report']['accounting_pass']


def test_binding_tampering(tmp_path, batch):
    write_batch(tmp_path, batch)
    with pytest.raises(ValueError, match='binding'): assess_batch(tmp_path, '0'*64)


def test_payload_tampering(tmp_path, batch):
    digest = write_batch(tmp_path, batch)
    (tmp_path/'candidate-ledger.json').write_text('{}')
    with pytest.raises(ValueError, match='output'): assess_batch(tmp_path, digest)


def test_binding_traversal(tmp_path, batch):
    write_batch(tmp_path, batch)
    p = tmp_path/'binding.json'
    data = json.loads(p.read_text())
    data['outputs']['../private.json'] = {'sha256': 'sha256:'+'0'*64}
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='unsafe'):
        assess_batch(tmp_path, hashlib.sha256(p.read_bytes()).hexdigest())


def test_missing_batch_is_machine_readable(tmp_path, capsys):
    assert main(['--batch-root',str(tmp_path),'--binding-sha256','0'*64]) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'BLOCKED'

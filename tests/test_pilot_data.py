"""QR-10 preparation contracts use generated public fixtures, never real data."""
import copy
import hashlib
import json
import stat

import pytest

from faustcoder.pilot_data import _partitions, main, prepare
from faustcoder.readiness_manifest import ManifestError
from tests.test_readiness_evidence import evidence
from tests.test_slice2 import signed_fixture


def run(e, output, **changes):
    args = dict(root=e['root'], bundle_path='bundle.json',
                bundle_sha256=hashlib.sha256(e['bundle_path'].read_bytes()).hexdigest(),
                scope_path=e['scope_path'], scope_digest=e['scope_digest'],
                trusted_public_key=e['public'], output=output)
    args.update(changes)
    return prepare(**args)


def test_reproducible_complete_partitions_without_holdout(evidence, tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    first = run(evidence, a)
    assert first == run(evidence, b)
    assert first['status'] == 'PREPARED_NOT_QUALIFIED'
    assert not first['training_authorized']
    assert 'pilot_training_authorization' in first['blockers']
    assert set(p.name for p in a.iterdir()) == {'train.jsonl', 'development.jsonl', 'preparation.json'}
    assert stat.S_IMODE(a.stat().st_mode) == 0o700
    frozen = evidence['store'].get(evidence['snapshot'])['payload']
    signed = evidence['store'].get(frozen['split_manifest_digest'])['payload']['candidate']
    ids = set()
    for name in ('train', 'development'):
        raw = (a/(name+'.jsonl')).read_bytes()
        assert raw == (b/(name+'.jsonl')).read_bytes()
        assert first['files'][name+'.jsonl']['sha256'] == hashlib.sha256(raw).hexdigest()
        row = json.loads(raw)
        assert signed['assignments'][row['unit_id']] == name
        assert 'notice' in row['provenance'] and 'license' in row['provenance']
        assert stat.S_IMODE((a/(name+'.jsonl')).stat().st_mode) == 0o600
        ids.add(row['unit_id'])
    holdout = {k for k,v in signed['assignments'].items() if v == 'holdout'}
    assert not ids & holdout
    assert len(ids) == 2


@pytest.mark.parametrize('change', [
    {'bundle_sha256': '0'*64}, {'scope_digest': '0'*64},
    {'bundle_path': '../bundle.json'},
    {'trusted_public_key': 'ssh-ed25519 invalid'},
])
def test_invalid_input_writes_nothing(evidence, tmp_path, change):
    output = tmp_path/'out'
    with pytest.raises((ValueError, OSError)):
        run(evidence, output, **change)
    assert not output.exists()


def test_no_overwrite_or_evidence_pollution(evidence, tmp_path):
    output = tmp_path/'out'
    run(evidence, output)
    before = (output/'preparation.json').read_bytes()
    with pytest.raises(FileExistsError): run(evidence, output)
    assert (output/'preparation.json').read_bytes() == before
    with pytest.raises(ManifestError): run(evidence, evidence['root']/'out')


def test_symlink_output_parent_refused(evidence, tmp_path):
    real = tmp_path/'real'
    real.mkdir()
    link = tmp_path/'link'
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(OSError): run(evidence, link/'out')
    assert not (real/'out').exists()


def test_input_tampering_refused(evidence, tmp_path):
    row = evidence['bundle']['objects'][0]
    (evidence['root']/row['path']).write_bytes(b'{}')
    with pytest.raises(ManifestError): run(evidence, tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_expired_split_refused_before_output(evidence, tmp_path, monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setattr('faustcoder.split._utc_now', lambda: datetime(2028, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match='recheck'): run(evidence, tmp_path/'out')
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('raw', [b'{}', b'{"gate":1,"gate":2}', b'null', b'[]'])
def test_malformed_descriptor_refused(evidence, tmp_path, raw):
    evidence['bundle_path'].write_bytes(raw)
    from faustcoder.errors import ArtifactStoreError
    with pytest.raises((ValueError, ArtifactStoreError)): run(evidence, tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_symlink_descriptor_refused(evidence, tmp_path):
    path = evidence['bundle_path']
    actual = path.with_name('actual.json')
    path.rename(actual)
    path.symlink_to(actual)
    with pytest.raises(OSError): run(evidence, tmp_path/'out')


@pytest.mark.parametrize('field,value', [('scope_digest', 'f'*64),
                                       ('gate', 'family_disjoint_split'),
                                       ('snapshot_digest', 'sha256:'+'f'*64)])
def test_hash_valid_descriptor_still_requires_exact_scope(evidence, tmp_path, field, value):
    from faustcoder.canonical import canonical_bytes
    descriptor = {**evidence['bundle'], field: value}
    evidence['bundle_path'].write_bytes(canonical_bytes(descriptor))
    with pytest.raises(ManifestError, match='scope'): run(evidence, tmp_path/'out')
    assert not (tmp_path/'out').exists()


class MutableView:
    def __init__(self, e):
        self.objects = {i: copy.deepcopy(e['store'].get(i)) for i in e['store'].list()}

    def get(self, digest):
        return self.objects[digest.removeprefix('sha256:')]


@pytest.mark.parametrize('change', ['text', 'digest', 'family', 'duplicate', 'empty', 'cap', 'development_cap', 'rights'])
def test_export_rechecks_text_bindings_and_never_truncates(evidence, change):
    view = MutableView(evidence)
    frozen = view.get(evidence['snapshot'])['payload']
    dedup = view.get(frozen['dedup_digest'])['payload']
    signed = view.get(frozen['split_manifest_digest'])['payload']['candidate']
    example = next(view.get(d)['payload'] for d in dedup['example_digests']
                   if signed['assignments'][view.get(d)['payload']['unit_id']] == 'train')
    unit = next(u for u in dedup['units'] if u['unit_id'] == example['unit_id'])
    if change == 'text': example['faust_source'] += 'tampered'
    if change == 'digest': example['normalized_sha256'] = 'sha256:'+'0'*64
    if change == 'family': example['duplicate_family'] = 'sha256:'+'0'*64
    if change == 'rights': unit['eligible_for'] = ['eval']
    if change == 'duplicate': dedup['example_digests'].append(dedup['example_digests'][0])
    if change == 'empty': signed['assignments'][example['unit_id']] = 'holdout'
    if change in {'cap', 'development_cap'}:
        partition = 'train' if change == 'cap' else 'development'
        for i in range(28):
            new_id = 'extra'+str(i)
            row = {**unit, 'unit_id': new_id}
            dedup['units'].append(row)
            view.objects[new_id] = {'payload': {**example, 'unit_id': new_id}}
            dedup['example_digests'].append(new_id)
            signed['assignments'][new_id] = partition
    with pytest.raises(ManifestError): _partitions(view, evidence['snapshot'])


def test_cli_reports_only_hashes_counts_and_blockers(evidence, tmp_path, capsys):
    key = tmp_path/'custodian.pub'
    key.write_text(evidence['public'])
    args = ['--evidence-root', str(evidence['root']), '--bundle', 'bundle.json',
            '--bundle-sha256', hashlib.sha256(evidence['bundle_path'].read_bytes()).hexdigest(),
            '--scope-file', str(evidence['scope_path']), '--scope-digest', evidence['scope_digest'],
            '--trusted-split-public-key', str(key), '--output', str(tmp_path/'out')]
    assert main(args) == 0
    report = capsys.readouterr().out
    assert 'faust_source' not in report and 'lib0.member' not in report
    assert json.loads(report)['files']['train.jsonl']['examples'] == 1
    assert main(args) == 2
    assert json.loads(capsys.readouterr().out)['code'] == 'pilot_data_preparation_failed'

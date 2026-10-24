"""QR-09: integrity, hostile paths, scope and authority boundaries."""
import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from faustcoder.readiness import assess, main
from faustcoder.readiness_manifest import ManifestError, load_manifest, read_beneath, verify_manifest

SCOPE = 'a' * 64


@pytest.fixture
def indexed(tmp_path):
    receipt = tmp_path / 'receipt.json'
    receipt.write_text('{"status":"PASS","training_authorized":true}')
    value = {'schema_version': 1, 'mode': 'pilot', 'scope_digest': SCOPE, 'receipts': [{
        'receipt_id': 'r1', 'gate': 'pilot_training_authorization', 'path': receipt.name,
        'sha256': hashlib.sha256(receipt.read_bytes()).hexdigest(),
        'scope_digest': SCOPE, 'outcome': 'PASS'}]}
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(value))
    return path, receipt, value


def check(indexed, **kwargs):
    path, _, _ = indexed
    return verify_manifest(load_manifest(path), path.parent, mode=kwargs.get('mode', 'pilot'),
                           scope_digest=kwargs.get('scope_digest', SCOPE))


def test_verified_hash_does_not_authorize(indexed):
    result = check(indexed)
    assert result['verified'][0]['status'] == 'INTEGRITY_VERIFIED'
    assert result['blockers'][0]['code'] == 'receipt_outcome_not_verified'
    path, _, _ = indexed
    result = assess(path.parent, manifest_path=path, evidence_root=path.parent, scope_digest=SCOPE)
    assert not result['training_authorized'] and not result['pilot_ready']
    assert 'training_authorized' not in str(result['receipt_verification'])


@pytest.mark.parametrize('text', ['{', '[]', 'null', '{"schema_version":1,"schema_version":1}',
                                '{"schema_version":NaN}', '{"schema_version":true}'])
def test_malformed_input(indexed, text):
    path, _, _ = indexed
    path.write_text(text)
    with pytest.raises(ManifestError):
        load_manifest(path)


@pytest.mark.parametrize('field', ['receipt_id', 'path', 'sha256'])
def test_duplicate_identity(indexed, field):
    path, _, value = indexed
    second = copy.deepcopy(value['receipts'][0])
    second.update(receipt_id='r2', path='other', sha256='b'*64)
    second[field] = value['receipts'][0][field]
    value['receipts'].append(second)
    path.write_text(json.dumps(value))
    with pytest.raises(ManifestError):
        load_manifest(path)


@pytest.mark.parametrize('change', ['extra', 'hash', 'version', 'outcome', 'type'])
def test_strict_schema(indexed, change):
    path, _, value = indexed
    if change == 'extra': value['training_authorized'] = True
    if change == 'hash': value['receipts'][0]['sha256'] = 'z'*64
    if change == 'version': value['schema_version'] = 2
    if change == 'outcome': value['receipts'][0]['outcome'] = 'AUTHORIZED'
    if change == 'type': value['receipts'] = {}
    path.write_text(json.dumps(value))
    with pytest.raises(ManifestError): load_manifest(path)


@pytest.mark.parametrize('relative', ['../receipt.json', '/etc/passwd', 'a/../receipt.json',
                                   './receipt.json', 'a//b', 'a\\b', '', 'x\x00y'])
def test_path_traversal(indexed, relative):
    path, _, value = indexed
    value['receipts'][0]['path'] = relative
    if not relative:
        with pytest.raises(ManifestError): read_beneath(path.parent, relative)
        return
    path.write_text(json.dumps(value))
    assert check(indexed)['blockers'][0]['code'] == 'unsafe_or_unreadable_receipt'


def test_leaf_symlink(indexed):
    _, receipt, _ = indexed
    content = receipt.read_bytes()
    receipt.unlink()
    actual = receipt.with_name('actual')
    actual.write_bytes(content)
    receipt.symlink_to(actual)
    assert check(indexed)['verified'] == []


def test_parent_and_root_symlink(indexed):
    path, _, value = indexed
    (path.parent/'linked').symlink_to(path.parent, target_is_directory=True)
    value['receipts'][0]['path'] = 'linked/receipt.json'
    path.write_text(json.dumps(value))
    assert check(indexed)['verified'] == []
    with pytest.raises(OSError): read_beneath(path.parent/'linked', 'receipt.json')


def test_manifest_symlink(indexed):
    path, _, _ = indexed
    link = path.with_name('link.json')
    link.symlink_to(path)
    with pytest.raises(ManifestError): load_manifest(link)


def test_fifo_never_blocks(indexed):
    _, receipt, _ = indexed
    receipt.unlink()
    os.mkfifo(receipt)
    assert check(indexed)['verified'] == []


def test_tampering(indexed):
    _, receipt, _ = indexed
    receipt.write_text('changed')
    assert check(indexed)['blockers'][0]['code'] == 'digest_mismatch'


def test_missing_receipt(indexed):
    _, receipt, _ = indexed
    receipt.unlink()
    assert check(indexed)['blockers'][0]['code'] == 'unsafe_or_unreadable_receipt'


@pytest.mark.parametrize('kwargs', [{'mode': 'full'}, {'scope_digest': 'b'*64}])
def test_manifest_scope(indexed, kwargs):
    assert check(indexed, **kwargs)['blockers'][0]['code'] == 'scope_mismatch'


def test_receipt_scope(indexed):
    path, _, value = indexed
    value['receipts'][0]['scope_digest'] = 'b'*64
    path.write_text(json.dumps(value))
    assert check(indexed)['verified'] == []
    assert check(indexed)['blockers'][0]['code'] == 'scope_mismatch'


def test_cli_invalid_is_machine_readable(indexed, capsys):
    path, _, _ = indexed
    path.write_text('{}')
    assert main(['--manifest', str(path), '--evidence-root', str(path.parent),
                 '--scope-digest', SCOPE, '--json']) == 2
    result = json.loads(capsys.readouterr().out)
    assert result['blockers'][-1]['code'] == 'invalid_manifest'


def test_explicit_scope_required(indexed):
    path, _, _ = indexed
    result = assess(path.parent, manifest_path=path)
    assert result['blockers'][-1]['code'] == 'explicit_scope_required'


def test_receipt_size_limit(indexed, monkeypatch):
    import faustcoder.readiness_manifest as module
    monkeypatch.setattr(module, 'MAX_BYTES', 1)
    with pytest.raises(ManifestError): load_manifest(indexed[0])

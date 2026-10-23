import json

import pytest

from faustcoder.modular_pairs import review
from faustcoder.public_pairs import digest
from faustcoder.readiness_manifest import ManifestError


def fixture(tmp_path):
    parts = {'prompt': 'Define f using helper(x). Return only f.', 'target': 'f(x) = helper(x);',
             'prefix': 'helper(x) = x * 2;\n', 'suffix': '\nprocess = f;\n'}
    value = {'kind': 'modular-public-pair.v1', 'unit_id': 'unit', 'target_symbol': 'f',
             'dependency_interfaces': ['helper(x)']}
    for key, text in parts.items():
        (tmp_path / key).write_text(text)
        value[key] = {'path': key, 'sha256': digest(text.encode())}
    return value, digest((parts['prefix'] + parts['target'] + parts['suffix']).encode())


def test_identity_replay_does_not_grant_qualification(tmp_path):
    value, expected = fixture(tmp_path)
    result = review(json.dumps(value).encode(), tmp_path, expected_harness_sha256=expected)
    assert result['assembled_sha256'] == expected
    assert not result['qualified'] and not result['training_authorized']
    assert 'full_closure_family_review' in result['remaining']


@pytest.mark.parametrize('mutation', ['digest', 'rebind_context', 'omit_interface', 'symbol', 'leak', 'path', 'extra'])
def test_reject_mutations(tmp_path, mutation):
    value, expected = fixture(tmp_path)
    if mutation == 'digest': value['target']['sha256'] = '0' * 64
    if mutation == 'rebind_context':
        (tmp_path / 'prefix').write_text('helper(x) = x * 3;\n')
        value['prefix']['sha256'] = digest((tmp_path / 'prefix').read_bytes())
    if mutation == 'omit_interface': value['dependency_interfaces'] = ['other(x)']
    if mutation == 'symbol': value['target_symbol'] = 'g'
    if mutation == 'leak':
        (tmp_path / 'prompt').write_text('helper(x) f(x) = helper(x);')
        value['prompt']['sha256'] = digest((tmp_path / 'prompt').read_bytes())
    if mutation == 'path': value['prefix']['path'] = '../outside'
    if mutation == 'extra': value['admitted'] = True
    with pytest.raises((ManifestError, ValueError)):
        review(json.dumps(value).encode(), tmp_path, expected_harness_sha256=expected)

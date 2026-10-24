"""Structural checks for dependency-supplied pairs; never admission authority."""
from pathlib import Path
import re

from faustcoder.canonical import loads_strict
from faustcoder.public_pairs import digest, require
from faustcoder.readiness_manifest import read_beneath


def review(data: bytes, root: Path, *, expected_harness_sha256: str) -> dict:
    """Expected digest comes from separately verified compiler evidence.

    A matching hash establishes source identity, not semantics or permission.
    """
    require(len(data) <= 65536, 'modular contract exceeds size bound')
    value = loads_strict(data)
    require(isinstance(value, dict) and set(value) == {
        'kind', 'unit_id', 'target_symbol', 'prompt', 'target', 'prefix', 'suffix',
        'dependency_interfaces',
    }, 'invalid modular contract fields')
    require(value['kind'] == 'modular-public-pair.v1', 'unsupported modular contract')
    require(isinstance(value['unit_id'], str) and 1 <= len(value['unit_id']) <= 256,
            'invalid modular identity')
    symbol = value['target_symbol']
    require(isinstance(symbol, str) and re.fullmatch(r'[A-Za-z_]\w*', symbol),
            'invalid target symbol')
    require(isinstance(expected_harness_sha256, str) and
            re.fullmatch(r'[0-9a-f]{64}', expected_harness_sha256),
            'invalid expected harness digest')
    interfaces = value['dependency_interfaces']
    require(isinstance(interfaces, list) and 1 <= len(interfaces) <= 32 and
            all(isinstance(x, str) and 1 <= len(x) <= 256 for x in interfaces) and
            len(set(interfaces)) == len(interfaces), 'invalid dependency interfaces')
    parts, paths = {}, set()
    total = 0
    for key in ('prompt', 'target', 'prefix', 'suffix'):
        ref = value[key]
        require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'},
                'invalid modular source reference')
        path = ref['path']
        require(isinstance(path, str) and path not in paths, 'duplicate modular path')
        paths.add(path)
        raw = read_beneath(root, path)
        total += len(raw)
        require(total <= 1024 * 1024, 'modular sources exceed size bound')
        require(digest(raw) == ref['sha256'], 'modular source digest mismatch')
        parts[key] = raw.decode('utf-8')
    target = parts['target']
    require(bool(target.strip()) and bool(parts['prompt'].strip()), 'empty modular pair')
    require(re.match(r'\s*' + re.escape(symbol) + r'\s*(?:\(|=)', target),
            'target definition does not match symbol')
    require(target not in parts['prompt'] and target not in parts['prefix'] + parts['suffix'],
            'target leaked into context or prompt')
    require(all(x in parts['prompt'] for x in interfaces), 'prompt omits dependency interface')
    assembled = (parts['prefix'] + target + parts['suffix']).encode('utf-8')
    require(digest(assembled) == expected_harness_sha256, 'assembled harness differs from verified source')
    return {
        'status': 'STRUCTURALLY_VERIFIED_NOT_QUALIFIED', 'unit_id': value['unit_id'],
        'target_sha256': digest(target.encode()), 'prompt_sha256': digest(parts['prompt'].encode()),
        'dependency_context_sha256': digest((parts['prefix'] + parts['suffix']).encode()),
        'assembled_sha256': digest(assembled), 'target_insertion_byte': len(parts['prefix'].encode()),
        'dependency_interfaces': interfaces, 'qualified': False, 'admission': 'NOT_GRANTED',
        'training_authorized': False,
        'remaining': ['modular_contract_review', 'independent_prompt_semantics',
                      'canonical_source_rights', 'full_closure_family_review',
                      'signed_partition_membership', 'tokenizer_sequence_bound'],
    }

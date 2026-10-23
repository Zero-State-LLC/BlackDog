"""CPU-only exact-tokenizer preflight. No model loading or training authorization."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path

from faustcoder.canonical import loads_strict
from faustcoder.errors import ArtifactStoreError
from faustcoder.public_pairs import digest, require, review_bundle
from faustcoder.readiness_manifest import read_beneath
from faustcoder.schemas import validate
from faustcoder.sft_batch import SupervisedExample, encode_batch

MODEL = 'Qwen/Qwen2.5-Coder-1.5B'
REVISION = 'df3ce67c0e24480f20468b6ef2894622d69eb73b'
# Approved local model-download receipt, independently checked before this adapter.
# These are tokenizer assets only, never model weights or executable Python.
TOKENIZER_HASHES = {
    'tokenizer.json': 'c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539',
    'tokenizer_config.json': '4a917e4772d9b246ef600e1c5d7d81e3a81ae9f3f2d10d78ccb02c86e5fb184a',
    'vocab.json': 'ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910',
    'merges.txt': '599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3',
}


class TokenizerRuntimeUnavailable(RuntimeError):
    """Optional CPU tokenizer dependency is not installed."""


class LocalTokenizer:
    """Protocol adapter without implicit formatting, padding or truncation."""

    def __init__(self, assets: dict[str, bytes]):
        try:
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise TokenizerRuntimeUnavailable('install the tokenizer extra in an isolated environment') from exc
        config = loads_strict(assets['tokenizer_config.json'])
        require(isinstance(config, dict) and config.get('tokenizer_class') == 'Qwen2Tokenizer',
                'unsupported tokenizer class')
        require(config.get('bos_token') is None and config.get('add_bos_token', False) is False,
                'implicit BOS refused')
        backend = Tokenizer.from_str(assets['tokenizer.json'].decode('utf-8'))
        require(backend.truncation is None and backend.padding is None,
                'implicit truncation or padding refused')
        self.eos_token_id = backend.token_to_id(config['eos_token'])
        self.pad_token_id = backend.token_to_id(config['pad_token'])
        require(type(self.eos_token_id) is int and type(self.pad_token_id) is int,
                'unresolved special tokens')
        self.backend = backend
        self.runtime_version = importlib.metadata.version('tokenizers')

    def __len__(self) -> int:
        return self.backend.get_vocab_size(with_added_tokens=True)

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        require(add_special_tokens is False, 'implicit special tokens refused')
        return self.backend.encode(text, add_special_tokens=False).ids


def inspect_encodings(pairs: tuple[dict, ...], tokenizer) -> dict:
    """Measure every row, including rejected rows; never emit a training batch."""
    rows = []
    require(1 <= len(pairs) <= 35, 'invalid candidate count')
    ids = [p['example_id'] for p in pairs]
    require(len(ids) == len(set(ids)), 'duplicate candidate identity')
    for pair in pairs:
        prompt, target = pair['prompt'], pair['target']
        require(isinstance(prompt, str) and isinstance(target, str) and
                max(len(prompt.encode()), len(target.encode())) <= 1024 * 1024,
                'invalid bounded pair text')
        require(pair['prompt_digest'] == 'sha256:' + digest(prompt.encode()) and
                pair['target_digest'] == 'sha256:' + digest(target.encode()), 'pair content changed')
        prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
        target_ids = tokenizer.encode(target, add_special_tokens=False)
        row = {'unit_id': pair['example_id'], 'pair_digest': pair['pair_digest'],
               'prompt_digest': pair['prompt_digest'], 'target_digest': pair['target_digest'],
               'prompt_tokens': len(prompt_ids), 'target_tokens': len(target_ids),
               'total_tokens_with_eos': len(prompt_ids) + len(target_ids) + 1}
        try:
            encoded = encode_batch([SupervisedExample(pair['example_id'], prompt, target,
                                                      pair['target_digest'])], tokenizer)
        except ValueError:
            row.update(status='TOKENIZER_REJECTED', code='invalid_or_oversize_encoding')
        else:
            # A changing tokenizer cannot report counts for different encoded bytes.
            require(encoded.input_ids[0] == tuple(prompt_ids + target_ids + [tokenizer.eos_token_id]),
                    'tokenizer output changed during preflight')
            require(encoded.prompt_lengths == (len(prompt_ids),) and
                    encoded.target_lengths == (len(target_ids),), 'token count mismatch')
            row.update(status='TOKENIZER_VERIFIED_NOT_QUALIFIED', encoding_digest=encoded.encoding_digest)
        rows.append(row)
    accepted = sum(row['status'] == 'TOKENIZER_VERIFIED_NOT_QUALIFIED' for row in rows)
    return {'status': 'TOKENIZER_VERIFIED_NOT_QUALIFIED' if accepted == len(rows) else 'TOKENIZER_REJECTED',
            'accepted_encodings': accepted, 'rejected_encodings': len(rows) - accepted,
            'max_sequence_length': 512, 'encoding': 'completion-only.v1',
            'runtime_version': tokenizer.runtime_version, 'eos_token_id': tokenizer.eos_token_id,
            'pad_token_id': tokenizer.pad_token_id, 'vocabulary_size': len(tokenizer), 'rows': rows}


def preflight(data: bytes, root: Path, *, scope_digest: str) -> dict:
    """Replay pinned public pairs and tokenizer assets instead of trusting PASS."""
    value = loads_strict(data)
    validate(value, 'public-pair-tokenizer.schema.json')
    require(value['scope_digest'] == scope_digest, 'preflight scope mismatch')
    paths = set()

    def read(ref):
        require(ref['path'] not in paths, 'duplicate preflight path')
        paths.add(ref['path'])
        require(not any(word in ref['path'].lower() for word in
                        ('private', 'holdout', 'credential', 'secret', 'answer')), 'nonpublic input refused')
        raw = read_beneath(root, ref['path'])
        require(digest(raw) == ref['sha256'], 'preflight digest mismatch')
        return raw

    pair_data = read(value['public_pairs'])
    public, pairs = review_bundle(pair_data, root, scope_digest=scope_digest)
    assets = {}
    for name, expected in TOKENIZER_HASHES.items():
        ref = value['tokenizer']['files'][name]
        require(ref['sha256'] == expected, 'unapproved tokenizer asset')
        assets[name] = read(ref)
    tokenizer = LocalTokenizer(assets)
    encoding = inspect_encodings(pairs, tokenizer)
    result = {**public, 'kind': 'public-pair-tokenizer.v1',
              'public_pair_descriptor_sha256': public['descriptor_sha256'],
              'descriptor_sha256': digest(data), 'status': encoding['status'],
              'tokenizer': {'model': MODEL, 'revision': REVISION,
                            'asset_sha256': dict(TOKENIZER_HASHES), **encoding}}
    if encoding['rejected_encodings'] == 0:
        result['remaining'] = [x for x in public['remaining'] if x != 'tokenizer_sequence_bound']
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--bundle-sha256', required=True)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--scope-digest', required=True)
    args = parser.parse_args(argv)
    try:
        data = read_beneath(args.bundle.parent, args.bundle.name)
        require(digest(data) == args.bundle_sha256, 'descriptor digest mismatch')
        report = preflight(data, args.evidence_root, scope_digest=args.scope_digest)
    except TokenizerRuntimeUnavailable:
        report = {'status': 'NOT_VERIFIED', 'code': 'tokenizer_runtime_required', 'qualified_pairs': 0}
    except (ArtifactStoreError, OSError, ValueError, TypeError, KeyError, RecursionError):
        report = {'status': 'INVALID', 'code': 'invalid_pair_preflight', 'qualified_pairs': 0}
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report['status'] == 'TOKENIZER_VERIFIED_NOT_QUALIFIED' else 2


if __name__ == '__main__':
    raise SystemExit(main())

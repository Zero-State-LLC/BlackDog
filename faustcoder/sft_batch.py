"""Bounded completion-only causal-model batches, without model or data loading.

Input is explicit prompt/target pairs. This module does not generate targets,
qualify pairs, select data partitions, authorize training or import Torch. The
caller must verify dataset, tokenizer/model provenance and authorization before
passing its output to a training loop. No chat template is applied implicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Protocol

from faustcoder.canonical import canonical_bytes, sha256_prefixed

IGNORE_INDEX = -100
MAX_SEQUENCE_LENGTH = 512
MAX_BATCH_SIZE = 28


class Tokenizer(Protocol):
    eos_token_id: int
    pad_token_id: int

    def __len__(self) -> int: ...

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]: ...


@dataclass(frozen=True)
class SupervisedExample:
    example_id: str
    prompt: str
    target: str
    target_digest: str


@dataclass(frozen=True)
class EncodedBatch:
    """Immutable rows; labels are unshifted for a causal LM's built-in loss."""
    example_ids: tuple[str, ...]
    input_ids: tuple[tuple[int, ...], ...]
    attention_mask: tuple[tuple[int, ...], ...]
    labels: tuple[tuple[int, ...], ...]
    prompt_lengths: tuple[int, ...]
    target_lengths: tuple[int, ...]
    pair_digests: tuple[str, ...]
    encoding_digest: str


def _integer(value, lower: int, upper: int, name: str) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError('invalid ' + name)
    return value


def encode_batch(examples: list[SupervisedExample], tokenizer: Tokenizer, *,
                 max_sequence_length: int = MAX_SEQUENCE_LENGTH) -> EncodedBatch:
    """Encode complete examples atomically, refusing any truncation or packing.

    Prompt and target are tokenized separately. Their concatenated token IDs,
    rather than tokenization of concatenated strings, define the boundary. A
    caller needing a chat format must supply the explicit formatted prompt.
    Tokenizer identity is an external model-manifest input, not inferred here.
    """
    limit = _integer(max_sequence_length, 3, MAX_SEQUENCE_LENGTH, 'sequence bound')
    if type(examples) is not list or not 1 <= len(examples) <= MAX_BATCH_SIZE:
        raise ValueError('invalid batch size')
    vocab = _integer(len(tokenizer), 2, 2**31 - 1, 'vocabulary size')
    eos = _integer(tokenizer.eos_token_id, 0, vocab - 1, 'EOS token')
    pad = _integer(tokenizer.pad_token_id, 0, vocab - 1, 'padding token')
    rows, prompts, targets, ids, bindings = [], [], [], [], []
    for example in examples:
        if type(example) is not SupervisedExample:
            raise ValueError('explicit supervised example required')
        if (not isinstance(example.example_id, str) or not example.example_id.strip()
                or example.example_id in ids):
            raise ValueError('empty or duplicate example identity')
        if any(not isinstance(text, str) or not text.strip()
               for text in (example.prompt, example.target)):
            raise ValueError('empty prompt or target')
        # Bound raw inputs before tokenizer execution, independently of tokens.
        if any(len(text.encode('utf-8')) > 1024 * 1024
               for text in (example.prompt, example.target)):
            raise ValueError('pair text exceeds bounded input size')
        if sha256_prefixed(example.target.encode('utf-8')) != example.target_digest:
            raise ValueError('target digest mismatch')
        encoded = []
        for text in (example.prompt, example.target):
            tokens = tokenizer.encode(text, add_special_tokens=False)
            if type(tokens) is not list or not tokens or len(tokens) >= limit:
                raise ValueError('empty or oversized encoded content')
            for token in tokens:
                _integer(token, 0, vocab - 1, 'content token')
                if token in {eos, pad}:
                    raise ValueError('special token inside content')
            encoded.append(list(tokens))
        prompt, target = encoded
        row = prompt + target + [eos]
        if len(row) > limit:
            raise ValueError('complete example exceeds sequence bound')
        rows.append(row)
        ids.append(example.example_id)
        prompts.append(len(prompt))
        targets.append(len(target))
        bindings.append(sha256_prefixed(canonical_bytes({
            'example_id': example.example_id, 'prompt': example.prompt,
            'target_digest': example.target_digest,
        })))
    width = max(map(len, rows))
    inputs, masks, labels = [], [], []
    for row, prompt_length in zip(rows, prompts):
        padding = width - len(row)
        inputs.append(tuple(row + [pad] * padding))
        masks.append(tuple([1] * len(row) + [0] * padding))
        labels.append(tuple([IGNORE_INDEX] * prompt_length + row[prompt_length:]
                            + [IGNORE_INDEX] * padding))
    encoding_digest = 'sha256:' + hashlib.sha256(canonical_bytes({
        'version': 'completion-only.v1', 'input_ids': [list(row) for row in inputs],
        'attention_mask': [list(row) for row in masks],
        'labels': [list(row) for row in labels], 'pair_digests': bindings,
        'max_sequence_length': limit,
        'eos_token_id': eos, 'pad_token_id': pad, 'vocabulary_size': vocab,
    })).hexdigest()
    return EncodedBatch(tuple(ids), tuple(inputs), tuple(masks), tuple(labels),
                        tuple(prompts), tuple(targets), tuple(bindings), encoding_digest)

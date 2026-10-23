"""QR-10 synthetic representation checks, not production training evidence."""
from dataclasses import FrozenInstanceError, replace

import pytest

from faustcoder.canonical import sha256_prefixed
from faustcoder.sft_batch import SupervisedExample, encode_batch


class CharacterTokenizer:
    eos_token_id = 1
    pad_token_id = 0

    def __len__(self): return 256

    def encode(self, text, *, add_special_tokens):
        assert add_special_tokens is False
        return [ord(character) + 2 for character in text]


def example(name='one', prompt='abc', target='de'):
    return SupervisedExample(name, prompt, target, sha256_prefixed(target.encode()))


def test_actual_shifted_loss_supervises_target_and_eos_only():
    encoded = encode_batch([example()], CharacterTokenizer())
    assert encoded.prompt_lengths == (3,) and encoded.target_lengths == (2,)
    assert encoded.labels == ((-100, -100, -100, 102, 103, 1),)
    # Causal LM loss compares logits[..., :-1, :] against labels[..., 1:].
    # These are the precise context->label edges that contribute to loss.
    edges = [(position, label) for position, label in enumerate(encoded.labels[0][1:])
             if label != -100]
    assert edges == [(2, 102), (3, 103), (4, 1)]
    assert encoded.input_ids[0][2] == ord('c') + 2
    assert encoded.attention_mask == ((1, 1, 1, 1, 1, 1),)


@pytest.mark.parametrize('pad', [0, 1])
def test_padding_masks_by_position_even_when_padding_equals_eos(pad):
    tokenizer = CharacterTokenizer()
    tokenizer.pad_token_id = pad
    batch = encode_batch([example(), example('two', 'a', 'b')], tokenizer)
    assert batch.input_ids[1] == (99, 100, 1, pad, pad, pad)
    assert batch.attention_mask[1] == (1, 1, 1, 0, 0, 0)
    assert batch.labels[1] == (-100, 100, 1, -100, -100, -100)
    assert batch.labels[1].count(1) == 1


def test_examples_remain_independent_deterministic_and_immutable():
    examples = [example(), example('two', 'f', 'g')]
    batch = encode_batch(examples, CharacterTokenizer())
    assert batch == encode_batch(examples, CharacterTokenizer())
    for index, item in enumerate(examples):
        single = encode_batch([item], CharacterTokenizer())
        width = len(single.input_ids[0])
        assert batch.input_ids[index][:width] == single.input_ids[0]
        assert batch.labels[index][:width] == single.labels[0]
        assert batch.pair_digests[index] == single.pair_digests[0]
    with pytest.raises(FrozenInstanceError): batch.encoding_digest = 'modified'
    with pytest.raises(TypeError): batch.labels[0][0] = 0


def test_exact_limit_accepted_but_never_silently_truncates():
    assert len(encode_batch([example()], CharacterTokenizer(), max_sequence_length=6).input_ids[0]) == 6
    with pytest.raises(ValueError, match='sequence bound'):
        encode_batch([example()], CharacterTokenizer(), max_sequence_length=5)
    with pytest.raises(ValueError):
        encode_batch([example(prompt='x'*512)], CharacterTokenizer())


@pytest.mark.parametrize('limit', [True, None, '512', 2, 513, 3.5])
def test_invalid_sequence_bounds_refused(limit):
    with pytest.raises(ValueError): encode_batch([example()], CharacterTokenizer(), max_sequence_length=limit)


@pytest.mark.parametrize('field,value', [
    ('example_id', ''), ('example_id', ' '), ('example_id', None),
    ('prompt', ''), ('prompt', ' '), ('prompt', None),
    ('target', ''), ('target', ' '), ('target', None),
    ('target_digest', 'sha256:'+'0'*64), ('target', 'tampered'),
])
def test_malformed_or_tampered_example_refused(field, value):
    with pytest.raises(ValueError):
        encode_batch([replace(example(), **{field: value})], CharacterTokenizer())


def test_oversized_raw_prompt_refused_before_tokenizer():
    class NeverTokenize(CharacterTokenizer):
        def encode(self, *args, **kwargs): pytest.fail('oversized input reached tokenizer')
    with pytest.raises(ValueError, match='bounded input'):
        encode_batch([example(prompt='x'*(1024*1024+1))], NeverTokenize())


@pytest.mark.parametrize('bad', [[], (), [True], [-1], [256], [1.0], [None], [1], [0]])
def test_invalid_or_special_content_tokens_refused(bad):
    class BadTokenizer(CharacterTokenizer):
        def encode(self, text, *, add_special_tokens): return bad
    with pytest.raises(ValueError): encode_batch([example()], BadTokenizer())


@pytest.mark.parametrize('field,value', [('eos_token_id', None), ('eos_token_id', True),
                                       ('eos_token_id', 256), ('pad_token_id', -1)])
def test_invalid_special_tokens_refused(field, value):
    tokenizer = CharacterTokenizer()
    setattr(tokenizer, field, value)
    with pytest.raises(ValueError): encode_batch([example()], tokenizer)


@pytest.mark.parametrize('examples', [[], [example()]*2, [example()]*29, [None], ({},)])
def test_invalid_duplicate_or_oversized_batch_refused(examples):
    with pytest.raises(ValueError): encode_batch(examples, CharacterTokenizer())


def test_boundary_is_defined_by_separate_tokenization():
    class BoundaryTokenizer(CharacterTokenizer):
        def encode(self, text, *, add_special_tokens):
            assert not add_special_tokens
            return {'prompt': [10, 11], 'target': [12], 'prompttarget': [99]}[text]
    batch = encode_batch([example(prompt='prompt', target='target')], BoundaryTokenizer())
    assert batch.input_ids == ((10, 11, 12, 1),)
    assert batch.labels == ((-100, -100, 12, 1),)


def test_tokenizer_reused_buffer_cannot_rewrite_prompt_tokens():
    class ReusingTokenizer(CharacterTokenizer):
        buffer = []

        def encode(self, text, *, add_special_tokens):
            self.buffer[:] = super().encode(text, add_special_tokens=add_special_tokens)
            return self.buffer
    assert encode_batch([example()], ReusingTokenizer()) == encode_batch([example()], CharacterTokenizer())


def test_encoding_identity_changes_with_pair_or_tokenizer_output():
    first = encode_batch([example()], CharacterTokenizer())
    changed = encode_batch([example(prompt='abf')], CharacterTokenizer())
    assert first.pair_digests != changed.pair_digests
    assert first.encoding_digest != changed.encoding_digest
    class OtherTokenizer(CharacterTokenizer):
        def encode(self, text, *, add_special_tokens):
            return [token+1 for token in super().encode(text, add_special_tokens=add_special_tokens)]
    changed_tokens = encode_batch([example()], OtherTokenizer())
    assert first.pair_digests == changed_tokens.pair_digests
    assert first.encoding_digest != changed_tokens.encoding_digest


def test_complete_28_example_batch_is_supported():
    batch = encode_batch([example(str(i)) for i in range(28)], CharacterTokenizer())
    assert len(batch.input_ids) == 28

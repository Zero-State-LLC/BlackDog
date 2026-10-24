"""Join exact-pair diagnostics for semantic review; never an admission receipt."""
from __future__ import annotations
import math

SOURCE = 'd4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e'
TARGET = 'e53eb44125c66681b6d413aa7578d83cd4d3c15e81eef1ca68d8a7a5632e11da'
PROMPT = 'cd5fdfd76bddb0c8ea91616833191c26e8db4c9c144ffec0a283ff7bc3e01e1e'
CONTEXT = '43fab3a0e66bb720813467a32320798c86dce63d00c6e67223429359d26f0db3'
PAIR = 'sha256:5604a3dd5bb97a94728437cc8667e03dd46bc62dcf0137105c788d16ee7a08b6'


def bind_exact_pair(contract, products, closure):
    """Check report consistency without treating report hashes as authentication.

    Caller must independently replay the structural contract, product captures,
    tokenizer and full-history binder. This function checks their shared scope.
    """
    expected = {'assembled_sha256': SOURCE, 'target_sha256': TARGET,
                'prompt_sha256': PROMPT, 'dependency_context_sha256': CONTEXT}
    if any(contract.get(k) != v for k, v in expected.items()):
        raise ValueError('exact pair or dependency context mismatch')
    if (contract.get('qualified') is not False
            or contract.get('training_authorized') is not False
            or contract.get('admission') != 'NOT_GRANTED'):
        raise ValueError('structural diagnostics cannot grant admission')
    tokenizer = contract['tokenizer']
    encodings = tokenizer['rows']
    if (tokenizer['accepted_encodings'] != 1 or tokenizer['rejected_encodings'] != 0
            or len(encodings) != 1 or encodings[0]['pair_digest'] != PAIR
            or encodings[0]['prompt_digest'] != 'sha256:' + PROMPT
            or encodings[0]['target_digest'] != 'sha256:' + TARGET
            or encodings[0]['total_tokens_with_eos'] != 363
            or tokenizer['max_sequence_length'] != 512):
        raise ValueError('tokenizer binding mismatch')
    if products['source_sha256'] != SOURCE or closure['source_sha256'] != SOURCE:
        raise ValueError('cross-source numerical evidence')
    if (closure['status'] != 'BOUNDED_REPAIR_VERIFIED_NOT_ADMITTED'
            or closure['wasm_cases'] != 24 or closure['modular_cases'] != 24
            or closure['bounded_wasm_jobs'] != 149
            or closure['admission'] != 'NOT_GRANTED'
            or closure['pilot_ready'] is not False
            or closure['training_authorized'] is not False):
        raise ValueError('full-history diagnostic binding mismatch')
    rows = products['rows']
    keys = [(r['batch'], r['variant']) for r in rows]
    variants = ('exact', 'bad-split', 'omit-cross')
    if len(keys) != 18 or set(keys) != {(b, v) for b in range(6) for v in variants}:
        raise ValueError('incomplete or duplicate product matrix')
    coefficients = []
    for batch in range(6):
        group = [r for r in rows if r['batch'] == batch]
        if any(r['coefficients'] != group[0]['coefficients'] for r in group):
            raise ValueError('negative control coefficient binding mismatch')
        coefficients.extend(tuple(c) for c in group[0]['coefficients'])
    if (len(coefficients) != 42 or len(set(coefficients)) != 42
            or any(len(c) != 4 or not all(math.isfinite(v) for v in c) for c in coefficients)
            or set(coefficients) != {tuple(-v for v in c) for c in coefficients}):
        raise ValueError('coefficient coverage mismatch')
    for row in rows:
        positive = row['variant'] == 'exact'
        if row['samples'] != 984 or row['passed'] is not positive:
            raise ValueError('product case failed or incomplete')
        for key in ('ratio', 'decimal80_ratio'):
            value = row[key]
            if not math.isfinite(value) or value < 0 or (value <= 1) != positive:
                raise ValueError('product reference or negative control failed')
    return {
        'status': 'EXACT_PAIR_REVIEW_PACKET_NOT_ADMITTED', **expected,
        'pair_digest': PAIR, 'products_verified': 41328, 'sequence_tokens': 363,
        'full_history_source_bound': True,
        'comparison_connected': closure['comparison_connected'],
        'independent_semantic_approval': False, 'canonical_admission': False,
        'signed_partition_membership': False, 'admission': 'NOT_GRANTED',
        'pilot_ready': False, 'training_authorized': False,
        'authority': 'LOCAL_DIAGNOSTIC_CONSISTENCY_NOT_AUTHENTICATION',
        'review_questions': [
            'Does the exact prompt specify the desired operation order and supplied helper behavior?',
            'Is the pinned-coefficient and bounded analyzer domain appropriate, without claiming arbitrary-range multiplication?',
            'Do canonical rights cover this exact target, prompt and complete supplied dependency context?',
            'Does the full family replay prevent this comparison-connected closure from entering evaluation?',
            'Does an authenticated signed partition bind this exact pair and context?'
        ],
    }

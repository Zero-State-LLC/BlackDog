"""Bounded replay of saved public samples; never execute code or grant admission."""
from __future__ import annotations

import array
import ast
import json
import math
import sys
from pathlib import Path

from faustcoder.canonical import loads_strict
from faustcoder.public_pairs import digest, require, review_bundle, unique_rows
from faustcoder.readiness_manifest import read_beneath
from faustcoder.schemas import validate

FRAMES = 4096
PROBES = ('impulse', 'alternating', 'multitone')


def number(value):
    require(type(value) in (int, float) and math.isfinite(value) and abs(value) <= 1e9,
            'invalid finite bounded number')
    return float(value)


def coefficients(formula: str, controls: dict, inputs: int, outputs: int) -> list:
    """Parse a small affine grammar, with no eval, calls or executable expressions."""
    require(isinstance(formula, str) and len(formula) <= 4096, 'invalid formula')
    tree = ast.parse(formula)
    require(len(list(ast.walk(tree))) <= 256, 'formula exceeds node bound')

    def channel(node, name, bound):
        require(isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id == name and isinstance(node.slice, ast.Tuple)
                and len(node.slice.elts) == 2, 'invalid channel expression')
        index, frame = node.slice.elts
        require(isinstance(index, ast.Constant) and type(index.value) is int
                and 0 <= index.value < bound and isinstance(frame, ast.Name)
                and frame.id == 'n', 'invalid channel index')
        return index.value

    def affine(node):
        zero = [0.0] * inputs
        if isinstance(node, ast.Constant):
            return number(node.value), zero
        if isinstance(node, ast.Name) and node.id in controls:
            return number(controls[node.id]), zero
        if isinstance(node, ast.Subscript):
            zero[channel(node, 'x', inputs)] = 1.0
            return 0.0, zero
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            b, c = affine(node.operand)
            return -b, [-v for v in c]
        require(isinstance(node, ast.BinOp), 'unsupported formula expression')
        a, ac = affine(node.left)
        b, bc = affine(node.right)
        if isinstance(node.op, ast.Add):
            return a + b, [x + y for x, y in zip(ac, bc)]
        if isinstance(node.op, ast.Sub):
            return a - b, [x - y for x, y in zip(ac, bc)]
        if isinstance(node.op, ast.Mult):
            require(not (any(ac) and any(bc)), 'nonlinear formula refused')
            return a * b, [a * y + b * x for x, y in zip(ac, bc)]
        require(isinstance(node.op, ast.Div) and not any(bc) and b != 0,
                'unsupported formula division')
        return a / b, [v / b for v in ac]

    result = {}
    for node in tree.body:
        require(isinstance(node, ast.Assign) and len(node.targets) == 1, 'invalid formula assignment')
        index = channel(node.targets[0], 'y', outputs)
        require(index not in result, 'duplicate formula output')
        result[index] = affine(node.value)
        bias, coeff = result[index]
        for value in [bias, *coeff]:
            number(value)
    require(set(result) == set(range(outputs)), 'missing formula output')
    return [result[i] for i in range(outputs)]


def replay_samples(plan: dict, contract: dict, input_raw: bytes, output_raw: bytes) -> dict:
    """Check saved interleaved little-endian float32 data with fixed tolerances."""
    ni, no = contract['inputs'], contract['outputs']
    require(all(type(n) is int and 1 <= n <= 8 for n in (ni, no)), 'unsupported arity')
    states = plan['states']
    require(isinstance(states, list) and 1 <= len(states) <= 64, 'invalid states')
    arrays = []
    for raw, channels in ((input_raw, ni), (output_raw, no)):
        require(len(raw) == len(states) * FRAMES * channels * 4, 'sample length mismatch')
        values = array.array('f')
        values.frombytes(raw)
        if sys.byteorder != 'little':
            values.byteswap()
        require(all(math.isfinite(v) for v in values), 'nonfinite samples')
        arrays.append(values)
    inp, out = arrays
    require(max(map(abs, inp)) <= 0.125 + 1e-8, 'input domain exceeded')
    mutant = plan.get('expectReject', False)
    require(type(mutant) is bool, 'invalid rejection flag')
    errors = 0
    peak = 0.0
    for si, state in enumerate(states):
        require(isinstance(state, dict) and set(state) == {'controls', 'weights'}, 'invalid state')
        controls = state['controls']
        require(isinstance(controls, dict) and set(controls) == set(contract['control_values']),
                'control names mismatch')
        require(isinstance(state['weights'], list) and len(state['weights']) == ni, 'invalid weights')
        for value in [*controls.values(), *state['weights']]:
            number(value)
        forms = coefficients(contract['reference_formula'], controls, ni, no)
        state_errors = 0
        offset_errors = 0
        for frame in range(si * FRAMES, (si + 1) * FRAMES):
            xs = inp[frame * ni:(frame + 1) * ni]
            for ch, (bias, coeff) in enumerate(forms):
                expected = bias + sum(c * x for c, x in zip(coeff, xs))
                actual = out[frame * no + ch]
                require(math.isfinite(expected), 'nonfinite reference')
                error = abs(actual - expected)
                peak = max(peak, error)
                state_errors += error > 2e-6 + 1e-5 * abs(expected)
                wrong = expected + 0.03125
                offset_errors += abs(actual - wrong) > 2e-6 + 1e-5 * abs(wrong)
        require(state_errors > 0 if mutant else state_errors == 0, 'unexpected signal result')
        require(offset_errors > 0, 'wrong reference not rejected')
        errors += state_errors
    return {'states_replayed': len(states), 'mismatch_samples': errors,
            'max_abs_error': peak, 'mutant_rejected': mutant,
            'wrong_reference_states_rejected': len(states)}


def replay(data: bytes, root: Path, *, scope_digest: str) -> dict:
    """Replay explicit evidence; coverage means recorded cases, not authenticated runs."""
    value = loads_strict(data)
    validate(value, 'public-pair-signal.schema.json')
    require(value['scope_digest'] == scope_digest, 'signal scope mismatch')
    total = 0
    cache = {}

    def read(ref):
        nonlocal total
        path = ref['path']
        require(not any(word in path.lower() for word in
                        ('private', 'holdout', 'credential', 'secret', 'answer')), 'nonpublic path refused')
        if path not in cache:
            raw = read_beneath(root, path)
            total += len(raw)
            require(total <= 128 * 1024 * 1024, 'signal bundle exceeds size bound')
            cache[path] = raw
        raw = cache[path]
        require(digest(raw) == ref['sha256'], 'signal digest mismatch')
        return raw

    pair_raw = read(value['public_pairs'])
    public, pairs = review_bundle(pair_raw, root, scope_digest=scope_digest)
    bundle = loads_strict(pair_raw)
    units = {u['unit_id']: u for u in bundle['units']}
    candidates = {p['example_id']: p for p in pairs}
    closures = unique_rows(loads_strict(read(bundle['receipts']['local_closures'])))
    original = {uid: loads_strict(read(u['contract'])) for uid, u in units.items()}
    seen = set()
    state_bindings = {}
    rows = []
    samples = 0
    for case in value['cases']:
        plan_raw = read(case['plan'])
        plan = loads_strict(plan_raw)
        require(isinstance(plan, dict) and plan.get('uid') in units, 'unknown signal unit')
        uid = plan['uid']
        contract_raw = read(case['contract'])
        contract = loads_strict(contract_raw)
        require(isinstance(contract, dict), 'invalid executed contract')
        require(digest(contract_raw) == plan['contract_sha256'] ==
                closures[uid]['executed_corrected_contract_sha256'], 'executed contract binding mismatch')
        for field in ('unit_id', 'identity', 'pin', 'source_blob', 'inputs', 'outputs',
                      'control_values', 'reference_formula', 'sample_rates', 'input_domain', 'cases'):
            require(contract[field] == original[uid][field], 'approved contract changed')
        expected_import = ('stdfaust.lib declared; no member referenced in target; import-removal equivalence required'
                           if candidates[uid]['import_correction_applied']
                           else original[uid]['declared_import_scope'])
        require(contract['declared_import_scope'] == expected_import, 'executed import mismatch')
        require(type(plan['rate']) is int and plan['rate'] in contract['sample_rates'], 'unapproved rate')
        require(type(plan['inputs']) is int and type(plan['outputs']) is int and
                plan['inputs'] == contract['inputs'] and plan['outputs'] == contract['outputs'],
                'plan arity mismatch')
        require(plan['probe'] in PROBES, 'unsupported probe')
        mutant, initial = plan.get('expectReject', False), plan.get('initializeOnly', False)
        require(type(mutant) is bool and type(initial) is bool, 'invalid plan flags')
        require(not (mutant and initial), 'conflicting plan flags')
        mode = 'mutant' if mutant else 'default' if initial else 'sweep'
        key = (uid, plan['rate'], mode, plan['probe'])
        require(key not in seen, 'duplicate signal case')
        seen.add(key)
        if mode != 'sweep':
            require(len(plan['states']) == 1, 'invalid single-state case')
        state_key = (uid, mode)
        state_digest = digest(json.dumps(plan['states'], sort_keys=True).encode())
        require(state_bindings.setdefault(state_key, state_digest) == state_digest,
                'state plan differs across rates or probes')
        target = candidates[uid]['target_digest']
        if mutant:
            require('mutant_source' in case and plan['original_source_sha256'] == target,
                    'mutant original binding mismatch')
            mutant_hash = digest(read(case['mutant_source']))
            require(mutant_hash == plan['mutant_source_sha256'] and 'sha256:' + mutant_hash != target,
                    'mutant source binding mismatch')
        else:
            require('mutant_source' not in case and plan['source_sha256'] == target,
                    'positive source binding mismatch')
        require(digest(read(case['wasm'])) == plan['wasm_sha256'], 'WASM binding mismatch')
        input_raw, output_raw = read(case['input']), read(case['output'])
        samples += (len(input_raw) + len(output_raw)) // 4
        require(samples <= 16 * 1024 * 1024, 'sample work bound exceeded')
        measured = replay_samples(plan, contract, input_raw, output_raw)
        rows.append({'unit_id': uid, 'rate': plan['rate'], 'mode': mode, 'probe': plan['probe'],
                     'pair_digest': candidates[uid]['pair_digest'],
                     'plan_sha256': digest(plan_raw), 'contract_sha256': digest(contract_raw),
                     'input_sha256': case['input']['sha256'], 'output_sha256': case['output']['sha256'],
                     'wasm_sha256': plan['wasm_sha256'], **measured})
    required = {(uid, rate, mode, probe) for uid in units for rate in (44100, 48000)
                for mode in ('sweep', 'default', 'mutant')
                for probe in (('alternating',) if mode == 'mutant' else PROBES)}
    require(seen == required, 'incomplete signal coverage')
    return {**public, 'kind': 'public-pair-signal.v1', 'descriptor_sha256': digest(data),
            'public_pair_descriptor_sha256': digest(pair_raw),
            'status': 'SAVED_SIGNAL_VERIFIED_NOT_QUALIFIED',
            'signal_replay': {'cases_replayed': len(rows),
                              'states_replayed': sum(r['states_replayed'] for r in rows),
                              'mutants_rejected': sum(r['mutant_rejected'] for r in rows),
                              'verified_payloads': len(cache), 'cases': rows},
            'limitations': ['Saved samples only; no compiler or WASM execution',
                            'Probe/default/control labels are recorded claims, not authenticated execution',
                            'No independent semantic approval or dataset admission']}

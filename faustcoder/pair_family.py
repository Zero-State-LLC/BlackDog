"""Structural replay of recorded family joins; no admission or split assignment."""
from __future__ import annotations

import re
from pathlib import Path

from faustcoder.canonical import loads_strict
from faustcoder.public_pairs import digest, require, review_bundle, unique_rows
from faustcoder.readiness_manifest import read_beneath
from faustcoder.schemas import validate


def reconstruct(families: dict, edges: list) -> dict:
    """Reconstruct components, checking a bijection with recorded family labels."""
    require(isinstance(families, dict) and 1 <= len(families) <= 10000, 'invalid family population')
    require(isinstance(edges, list) and len(edges) <= 50000, 'invalid graph size')
    require(all(isinstance(k, str) and 1 <= len(k) <= 256 and isinstance(v, str)
                and re.fullmatch(r'sha256:[0-9a-f]{64}', v) for k, v in families.items()),
            'invalid family identity')
    parent = {k: k for k in families}

    def find(k):
        require(k in parent, 'unknown graph endpoint')
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def join(a, b):
        require(isinstance(a, str) and isinstance(b, str), 'invalid graph endpoint')
        ra, rb = find(a), find(b)
        parent[max(ra, rb)] = min(ra, rb)

    joins = 0
    for edge in edges:
        require(isinstance(edge, dict) and edge.get('floor') == 40
                and type(edge.get('floor')) is int
                and edge.get('stream') in ('raw', 'canonical'), 'invalid recorded graph policy')
        if 'left' in edge or 'right' in edge:
            require(edge.get('reason') in ('exact', 'token_jaccard', 'short_character_match',
                    'reverse_containment', 'forward_containment', 'verbatim_run', 'collective_union'),
                    'unsupported pairwise edge')
            require('contributors' not in edge, 'ambiguous graph edge')
            join(edge['left'], edge['right'])
            joins += 1
        else:
            require(edge.get('reason') == 'collective_support', 'unsupported graph record')
            members = edge['contributors']
            require(isinstance(members, list) and 3 <= len(members) <= 10000
                    and all(isinstance(x, str) for x in members)
                    and len(set(members)) == len(members), 'invalid collective membership')
            require(isinstance(edge['comparison'], str) and edge['comparison'].startswith('comparison:'),
                    'invalid comparison endpoint')
            require(all(not x.startswith('comparison:') for x in members), 'comparison contributor refused')
            for member in members:
                join(member, edge['comparison'])
            joins += len(members)
        require(joins <= 250000, 'graph work bound exceeded')
    forward, reverse = {}, {}
    for key, family in families.items():
        component = find(key)
        require(forward.setdefault(component, family) == family, 'connected identities split across families')
        require(reverse.setdefault(family, component) == component, 'disconnected identities share family')
    return {'identities': len(families), 'components': len(forward), 'joining_operations': joins}


def review(data: bytes, root: Path, *, scope_digest: str) -> dict:
    value = loads_strict(data)
    validate(value, 'public-pair-family.schema.json')
    require(value['scope_digest'] == scope_digest, 'family scope mismatch')
    seen = set()
    total = 0

    def read(ref):
        nonlocal total
        path = ref['path']
        require(path not in seen, 'duplicate family evidence path')
        seen.add(path)
        require(not any(w in path.lower() for w in ('private','holdout','credential','secret','answer')),
                'nonpublic family input refused')
        raw = read_beneath(root, path)
        total += len(raw)
        require(total <= 32 * 1024 * 1024, 'family bundle exceeds size bound')
        require(digest(raw) == ref['sha256'], 'family evidence digest mismatch')
        return raw

    pair_raw = read(value['public_pairs'])
    public, pairs = review_bundle(pair_raw, root, scope_digest=scope_digest)
    binding = loads_strict(read(value['binding']))
    families = loads_strict(read(value['families']))
    ledger = unique_rows(loads_strict(read(value['ledger'])))
    edges = loads_strict(read(value['edges']))
    counts = reconstruct(families, edges)
    require(isinstance(binding, dict) and isinstance(binding.get('source_hashes'), dict), 'missing source bindings')
    hashes = binding['source_hashes']
    require(set(hashes) == set(families), 'graph population differs from binding')
    require(all(isinstance(h, str) and re.fullmatch(r'[0-9a-f]{64}', h) for h in hashes.values()),
            'invalid recorded source hash')
    require(set(ledger) == {k for k in families if not k.startswith('comparison:')},
            'ledger population differs from graph')
    for uid, row in ledger.items():
        require(row.get('family') == families[uid] and row.get('source_sha256') == hashes[uid],
                'ledger identity mismatch')
        require(row.get('admission') == 'NOT_GRANTED', 'unsupported recorded admission')
    selected = {}
    for pair in pairs:
        uid = pair['example_id']
        require(uid in ledger and 'sha256:' + hashes[uid] == pair['target_digest'], 'selected source mismatch')
        selected.setdefault(families[uid], []).append(uid)
    outside = sum(row['family'] not in selected for row in ledger.values())
    infeasible = len(selected) < 2
    return {**public, 'kind': 'public-pair-family.v1', 'descriptor_sha256': digest(data),
            'public_pair_descriptor_sha256': digest(pair_raw),
            'status': 'PARTITION_INFEASIBLE' if infeasible else 'PARTITION_UNRESOLVED',
            'family_review': {**counts, 'ledger_units': len(ledger),
                              'selected_families': len(selected),
                              'groups': [{'family': f, 'unit_ids': sorted(ids)} for f, ids in sorted(selected.items())],
                              'outside_selected_family_inventory_units': outside,
                              'graph_sha256': value['edges']['sha256'],
                              'family_map_sha256': value['families']['sha256'],
                              'binding_sha256': value['binding']['sha256']},
            'partition_assigned': False,
            'limitations': ['Recorded graph reconstruction only; similarity measurements not rerun',
                            'Collective membership is not a COPY adjudication',
                            'Outside-family inventory is not qualified data',
                            'Project/lineage separation, admission and signed membership remain required']}

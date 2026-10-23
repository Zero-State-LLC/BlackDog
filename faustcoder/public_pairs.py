"""Replay bounded public receipt bindings; never admit a source or authorize training.

Legacy receipts are preserved, not re-signed or treated as independent authority.
Only explicitly referenced public files are read. Reports contain no source text.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from faustcoder.canonical import loads_strict
from faustcoder.readiness_manifest import ManifestError, read_beneath
from faustcoder.schemas import validate

KIND = 'public-pair-review.v1'
PENDING = ('canonical_example_admission', 'signed_partition_membership',
           'prompt_semantic_validation', 'compiler_signal_replay', 'tokenizer_sequence_bound')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def unique_rows(value: object) -> dict:
    require(isinstance(value, list) and len(value) <= 10000, 'invalid receipt rows')
    rows = {}
    for row in value:
        require(isinstance(row, dict) and isinstance(row.get('unit_id'), str), 'invalid unit')
        require(row['unit_id'] not in rows, 'duplicate receipt unit')
        rows[row['unit_id']] = row
    return rows


def _identity(row: dict, baseline: dict, *, commit: str, blob: str) -> None:
    for key in ('unit_id', 'path', 'dossier_sha256'):
        require(row.get(key) == baseline[key], 'receipt identity mismatch')
    source = row.get('source_sha256', '')
    require(isinstance(source, str) and source.removeprefix('sha256:') ==
            baseline['source_sha256'].removeprefix('sha256:'), 'source binding mismatch')
    require(row.get(commit) == baseline['commit'], 'revision binding mismatch')
    require(row.get(blob) == baseline['source_git_blob'], 'blob binding mismatch')


def _prompt(contract: dict, approval: dict, behavior: dict) -> tuple[str, bool]:
    fields = ('inputs', 'outputs', 'control_values', 'reference_formula',
              'sample_rates', 'input_domain', 'cases', 'declared_import_scope')
    require(all(field in contract for field in fields), 'incomplete behavior contract')
    require(all(type(contract[k]) is int and 0 <= contract[k] <= 64
                for k in ('inputs', 'outputs')), 'invalid arity')
    require(contract['sample_rates'] == [44100, 48000], 'invalid sample rates')
    require(isinstance(contract['control_values'], dict), 'invalid controls')
    require(isinstance(contract['cases'], list) and contract['cases'] and
            all(isinstance(x, str) and x.strip() for x in contract['cases']), 'invalid cases')
    for key in ('reference_formula', 'input_domain', 'declared_import_scope'):
        require(isinstance(contract[key], str) and contract[key].strip(), 'invalid behavior text')
    effective = {k: contract[k] for k in fields}
    correction = approval.get('correction_required')
    require(type(correction) is bool, 'missing correction decision')
    if correction:
        overlay = behavior.get('approved_import_correction', {})
        require(isinstance(overlay, dict) and isinstance(overlay.get('paths'), list),
                'approved import correction missing')
        require(approval['path'] in overlay.get('paths', []) and
                overlay.get('declared_import') == 'import("stdfaust.lib")',
                'approved import correction missing')
        effective['declared_import_scope'] = overlay['declared_import']
    # This template is derived, not a claim that its wording was human-reviewed.
    prompt = ('Write a complete Faust DSP program satisfying this behavioral contract.\n'
              'Return only the Faust source.\n' +
              json.dumps(effective, sort_keys=True, ensure_ascii=False, separators=(',', ':')))
    return prompt, correction


def review_bundle(data: bytes, root: Path, *, scope_digest: str) -> tuple[dict, tuple[dict, ...]]:
    """Return advisory summary and candidate pairs. Zero pairs become qualified.

    The caller must pin descriptor bytes separately (readiness does this through
    its manifest). The descriptor's scope must equal the requested scope.
    """
    bundle = loads_strict(data)
    validate(bundle, 'public-pair-review.schema.json')
    require(bundle['scope_digest'] == scope_digest, 'pair bundle scope mismatch')
    total_bytes = 0
    seen_paths: set[str] = set()
    seen_hashes: set[str] = set()

    def read(ref: dict) -> bytes:
        nonlocal total_bytes
        require(ref['path'] not in seen_paths, 'duplicate reference path')
        require(ref['sha256'] not in seen_hashes, 'duplicate reference digest')
        seen_paths.add(ref['path'])
        seen_hashes.add(ref['sha256'])
        # A public-only bundle must be selected by the operator. Defensive name
        # checks are additional guards, not a substitute for that selection.
        parts = Path(ref['path']).parts
        require(not any(any(word in part.lower() for word in
                    ('holdout', 'private', 'credential', 'answer', 'secret')) for part in parts),
                'nonpublic evidence path refused')
        raw = read_beneath(root, ref['path'])
        total_bytes += len(raw)
        require(total_bytes <= 16 * 1024 * 1024, 'public bundle exceeds size bound')
        require(digest(raw) == ref['sha256'], 'public evidence digest mismatch')
        return raw

    raw_receipts = {key: read(ref) for key, ref in bundle['receipts'].items()}
    rights = loads_strict(raw_receipts['rights'])
    behavior = loads_strict(raw_receipts['behavior'])
    imports = loads_strict(raw_receipts['imported_closures'])
    imported_notice = loads_strict(raw_receipts['imported_notice'])
    confirmation = loads_strict(raw_receipts['owner_confirmation'])
    require(isinstance(confirmation, dict) and
            confirmation.get('review_type') == 'DELEGATED_AGENT_REVIEW_NOT_HUMAN_REVIEW' and
            confirmation.get('independence_status') == 'WAIVED_BY_OWNER_NOT_INDEPENDENT' and
            confirmation.get('production_admission') is False, 'missing owner confirmation')
    require(all(isinstance(x, dict) for x in (rights, behavior, imports, imported_notice)), 'invalid receipt object')
    source_rows = unique_rows(rights['units'])
    behavior_rows = unique_rows(behavior['contracts'])
    local_rows = unique_rows(loads_strict(raw_receipts['local_closures']))
    imported_rows = unique_rows(imports['rows'])
    notice_rows = unique_rows(imported_notice['units'])
    require(imported_notice.get('decision') == 'APPROVED_SCOPED_IMPORTED_NOTICE_HANDLING',
            'imported notice handling not recorded')
    require(imported_notice['preserved_notice_sha256']['GRAME-header.txt'] ==
            digest(raw_receipts['imported_header']), 'imported header binding mismatch')
    imported_header = raw_receipts['imported_header'].decode('utf-8')
    require(bool(imported_header.strip()), 'empty imported header')
    require(rights['notice_sha256'] == digest(raw_receipts['notice']), 'notice binding mismatch')
    notice = raw_receipts['notice'].decode('utf-8')
    require(notice.strip() != '', 'empty notice')
    require(imports.get('production_admission') is False, 'unsupported admission claim')
    candidates = []
    checks = []
    ids: set[str] = set()
    for unit in bundle['units']:
        uid = unit['unit_id']
        require(uid not in ids, 'duplicate selected unit')
        ids.add(uid)
        r, b = source_rows[uid], behavior_rows[uid]
        for field, pattern in (('source_sha256', r'sha256:[0-9a-f]{64}'),
                               ('dossier_sha256', r'[0-9a-f]{64}'),
                               ('commit', r'[0-9a-f]{40}'), ('source_git_blob', r'[0-9a-f]{40}')):
            require(isinstance(r.get(field), str) and re.fullmatch(pattern, r[field]) is not None,
                    'invalid source identity field')
        require(r.get('copy_decision') == 'NOT_COPY' and
                r.get('notice_scope_decision') == 'APPROVED_REPOSITORY_LEVEL_MIT' and
                r.get('production_admission') == 'NOT_GRANTED', 'unsupported rights decision')
        require(b.get('decision') == 'APPROVE_BEHAVIORAL_CONTRACT', 'behavior not approved')
        _identity(b, r, commit='pin', blob='source_blob')
        source = read(unit['source'])
        contract_raw = read(unit['contract'])
        dossier = read(unit['dossier'])
        require('sha256:' + digest(source) == r['source_sha256'], 'target differs from approved source')
        blob = hashlib.sha1(b'blob ' + str(len(source)).encode() + b'\0' + source).hexdigest()
        require(blob == r['source_git_blob'], 'source git blob mismatch')
        require(digest(dossier) == r['dossier_sha256'], 'dossier binding mismatch')
        require(digest(contract_raw) == b['contract_sha256'], 'unapproved contract bytes')
        contract = loads_strict(contract_raw)
        require(isinstance(contract, dict), 'invalid behavior object')
        require(contract.get('unit_id') == uid and contract.get('pin') == r['commit'] and
                contract.get('source_blob') == blob, 'contract identity mismatch')
        identity = contract['identity']
        require(isinstance(identity, dict), 'invalid contract identity')
        for key in ('unit_id', 'path', 'source_sha256', 'dossier_sha256'):
            require(identity.get(key) == r[key], 'contract source identity mismatch')
        local = local_rows[uid]
        # Imported approvals supersede only UNRESOLVED, never a conflicting denial.
        require(local.get('decision') in ('UNRESOLVED', 'CLOSURE_ACCEPTED_SOURCE_LOCAL_ONLY'),
                'unsupported or conflicting local closure')
        require(local.get('source_sha256') == r['source_sha256'] and
                local.get('dossier_sha256') == r['dossier_sha256'] and
                local.get('path') == r['path'] and local.get('git_blob') == blob and
                local.get('original_approved_contract_sha256') == b['contract_sha256'],
                'local closure binding mismatch')
        require(local.get('production_admission') is False, 'unsupported local admission')
        if uid in imported_rows:
            closure = imported_rows[uid]
            _identity(closure, r, commit='pin', blob='git_blob')
            require(local['decision'] == 'UNRESOLVED' and
                    closure.get('decision') == 'ACCEPT_BOUNDED_SOURCE_AND_COMPILER_IMPORT_CLOSURE' and
                    closure.get('decision_status') == 'OWNER_APPROVED' and
                    closure.get('production_admission') is False, 'unsupported imported closure')
            notice_row = notice_rows[uid]
            for key in ('unit_id', 'path', 'source_sha256', 'dossier_sha256'):
                require(notice_row.get(key) == r[key], 'imported notice source mismatch')
            library = notice_row['resolved_library_binding']
            require(isinstance(library, dict) and library.get('path') == 'stdfaust.lib' and
                    library.get('sha256') == closure['native_resolution']['library_sha256'] and
                    library.get('sha256') == imported_notice['preserved_notice_sha256']['stdfaust.lib'],
                    'imported library binding mismatch')
            require(imported_notice['preserved_notice_sha256']['LICENSE.MIT.Pierre-Guillot.txt'] ==
                    rights['notice_sha256'], 'imported MIT binding mismatch')
            closure_scope = 'RECORDED_OWNER_BOUNDED_IMPORT'
        else:
            require(local['decision'] == 'CLOSURE_ACCEPTED_SOURCE_LOCAL_ONLY' and
                    local.get('authority_status') == 'OWNER_CONFIRMED_DELEGATED_AGENT_REVIEW' and
                    local.get('human_review') is False and
                    local.get('reviewer') == confirmation.get('delegated_reviewer') and
                    isinstance(local.get('reviewer'), str), 'source-local closure not established')
            closure_scope = 'RECORDED_DELEGATED_SOURCE_LOCAL'
        prompt, corrected = _prompt(contract, b, behavior)
        target = source.decode('utf-8')
        require(target.strip() != '' and len(source) <= 1024 * 1024, 'invalid target')
        if corrected:
            require('import("stdfaust.lib")' in target, 'correction inconsistent with source')
        provenance = {key: ref['sha256'] for key, ref in bundle['receipts'].items()}
        pair = {'example_id': uid, 'prompt': prompt, 'target': target,
                'target_digest': 'sha256:' + digest(source),
                'prompt_digest': 'sha256:' + digest(prompt.encode()),
                'contract_digest': b['contract_sha256'], 'dossier_digest': r['dossier_sha256'],
                'source_revision': r['commit'], 'source_git_blob': blob,
                'notice': notice, 'notice_digest': rights['notice_sha256'],
                'receipt_digests': provenance, 'import_correction_applied': corrected,
                'status': 'CANDIDATE_NOT_QUALIFIED', 'qualification_blockers': list(PENDING)}
        if uid in imported_rows:
            pair['imported_notice'] = imported_header
            pair['imported_notice_digest'] = digest(raw_receipts['imported_header'])
            pair['imported_library_binding'] = notice_rows[uid]['resolved_library_binding']
            pair['library_source_redistribution'] = 'NOT_PREPARED_OR_AUTHORIZED'
        pair['pair_digest'] = digest(json.dumps(pair, sort_keys=True, ensure_ascii=False,
                                              separators=(',', ':')).encode())
        candidates.append(pair)
        checks.append({'unit_id': uid, 'target_digest': pair['target_digest'],
                       'prompt_digest': pair['prompt_digest'], 'pair_digest': pair['pair_digest'],
                       'closure_scope': closure_scope, 'import_correction_applied': corrected,
                       'status': 'PUBLIC_BINDINGS_VERIFIED'})
    return {'kind': KIND, 'scope_digest': scope_digest, 'descriptor_sha256': digest(data),
            'status': 'QUALIFICATION_PENDING', 'candidate_pairs': len(candidates),
            'qualified_pairs': 0, 'verified_files': len(seen_paths), 'units': checks,
            'remaining': list(PENDING), 'clears_readiness_gates': [],
            'authority': 'RECORDED_DECISIONS_ONLY_NOT_INDEPENDENT_AUTHENTICATION'}, tuple(candidates)

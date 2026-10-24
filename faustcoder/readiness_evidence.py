"""Semantic readiness replay over explicitly indexed public evidence only.

Replay reads only indexed public artifacts. Export indexes an explicitly selected
public-only store and writes a new bundle, without modifying its inputs. Neither
operation enrolls a signer or authorizes training. Signer trust is supplied out
of band, never read from a receipt or evidence bundle.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from faustcoder.canonical import canonical_bytes, content_digest_for, loads_strict, parse_reference
from faustcoder.errors import ArtifactNotFoundError, ArtifactStoreError
from faustcoder.readiness_manifest import ManifestError, read_beneath
from faustcoder.schemas import validate
from faustcoder.store import ArtifactStore
from faustcoder.split import verify_frozen_snapshot

SEMANTIC_GATES = frozenset({'t07_signed_split', 'family_disjoint_split'})
MAX_BUNDLE_BYTES = 64 * 1024 * 1024
_PUBLIC_TYPES = frozenset({'SourceRecord', 'LicenseEvidence', 'RightsRecord', 'Example',
                           'DedupManifest', 'DatasetSnapshot', 'SplitManifest'})


def load_scope(path: Path, expected_digest: str, mode: str) -> dict:
    raw = read_beneath(path.parent, path.name)
    if hashlib.sha256(raw).hexdigest() != expected_digest:
        raise ManifestError('run scope digest mismatch')
    scope = loads_strict(raw)
    try:
        validate(scope, 'readiness-scope.schema.json')
    except ArtifactStoreError as exc:
        raise ManifestError('invalid run scope schema') from exc
    if scope['mode'] != mode:
        raise ManifestError('run scope mode mismatch')
    return scope


def load_public_key(path: Path, *, excluded_roots: tuple[Path, ...] = ()) -> str:
    """Load one explicitly supplied custodian public key, with optional comment."""
    if any(path.resolve().is_relative_to(root.resolve()) for root in excluded_roots):
        raise ManifestError('custodian trust key must be outside the evidence inputs and output bundle')
    raw = read_beneath(path.parent, path.name)
    parts = raw.decode('ascii').strip().split()
    if len(parts) < 2 or parts[0] != 'ssh-ed25519' or b'\n' in raw.strip():
        raise ManifestError('not a single custodian public key')
    return ' '.join(parts[:2])


class PublicEvidenceStore(ArtifactStore):
    """Read-only indexed view; inherited get() verifies canonical DAG rules.

    Every object is loaded through the no-follow reader before replay. There is
    no directory scan and the canonical split verifier sees only this bundle.
    """
    def __init__(self, root: Path, objects: list[dict]):
        self._objects = {}
        self._graph_verified = False
        seen_paths = set()
        total = 0
        for row in objects:
            artifact_id = row['artifact_id']
            if artifact_id in self._objects:
                raise ManifestError('duplicate artifact identity')
            for path in (row['path'], row['witness_path']):
                if path in seen_paths:
                    raise ManifestError('duplicate evidence path')
                seen_paths.add(path)
            if (Path(row['path']).name != artifact_id + '.json'
                    or Path(row['witness_path']).name != artifact_id + '.envelope_digest'):
                raise ManifestError('artifact filename binding mismatch')
            raw = read_beneath(root, row['path'])
            witness = read_beneath(root, row['witness_path'])
            total += len(raw) + len(witness)
            if total > MAX_BUNDLE_BYTES:
                raise ManifestError('evidence bundle exceeds bounded replay size')
            if hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ManifestError('artifact bytes changed')
            if witness != ('sha256:' + hashlib.sha256(raw).hexdigest()).encode('ascii'):
                raise ManifestError('artifact witness mismatch')
            envelope = loads_strict(raw)
            validate(envelope, 'artifact-envelope.schema.json')
            if raw != canonical_bytes(envelope):
                raise ManifestError('noncanonical artifact bytes')
            if (envelope['artifact_id'] != artifact_id
                    or envelope['content_digest'] != 'sha256:' + artifact_id
                    or content_digest_for(envelope['payload']) != envelope['content_digest']):
                raise ManifestError('artifact payload digest mismatch')
            payload = envelope['payload']
            if payload.get('record_type') not in _PUBLIC_TYPES:
                # Only canonical transition records are accepted without a type.
                validate(payload, 'transition-receipt.schema.json')
            if 'prompt' in payload or 'task_id' in payload:
                raise ManifestError('task payloads are forbidden in public readiness evidence')
            self._objects[artifact_id] = envelope
        # One canonical walk covers the entire immutable in-memory graph.
        # Repeating every ancestor walk for every get() would multiply replay
        # cost on large bundles. No public API can write or expose cached dicts.
        super()._assert_acyclic('_public_readiness_root',
                               ['sha256:' + key for key in sorted(self._objects)])
        self._graph_verified = True

    def _read_envelope(self, artifact_id):
        try:
            return self._objects[artifact_id]
        except KeyError as exc:
            raise ArtifactNotFoundError(artifact_id) from exc

    def _assert_acyclic(self, origin, parents):
        if not self._graph_verified:
            super()._assert_acyclic(origin, parents)

    def list(self):
        return sorted(self._objects)

    def exists(self, reference):
        return parse_reference(reference) in self._objects

    def put(self, envelope):
        raise ManifestError('readiness evidence is read-only')


def verify_split_evidence(raw: bytes, root: Path, *, gate: str, scope_digest: str,
                          scope: dict, trusted_public_key: str) -> dict:
    bundle = loads_strict(raw)
    validate(bundle, 'readiness-verification.schema.json')
    if (bundle['gate'] != gate or bundle['scope_digest'] != scope_digest
            or bundle['snapshot_digest'] != scope['dataset_snapshot_digest']):
        raise ManifestError('snapshot evidence does not match run scope')
    store = PublicEvidenceStore(root, bundle['objects'])
    snapshot = verify_frozen_snapshot(store, bundle['snapshot_digest'], trusted_public_key)
    import faustcoder.split as split_module
    verifier_hashes = {
        'readiness_evidence': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'canonical_split_verifier': hashlib.sha256(Path(split_module.__file__).read_bytes()).hexdigest(),
    }
    return {'gate': gate, 'status': 'SEMANTICALLY_VERIFIED',
            'verification_method': 'canonical_frozen_snapshot', 'verifier_code_sha256': verifier_hashes,
            'snapshot_digest': bundle['snapshot_digest'],
            'token_floor_status': snapshot['token_floor_status'],
            'p3_holdout_exit_allowed': False,
            'training_authorized': False}


def export_public_bundle(public_store: Path, scope_path: Path, output: Path,
                         trusted_public_key: str) -> dict:
    """Generate both semantic descriptors and the index, with no approvals.

    The operator must select a public-only snapshot store. No home-directory or
    private holdout discovery occurs. All input objects pass preflight before
    any output directory is created. Existing output directories are refused.
    """
    import os
    import re

    scope_raw = read_beneath(scope_path.parent, scope_path.name)
    scope_digest = hashlib.sha256(scope_raw).hexdigest()
    scope = loads_strict(scope_raw)
    validate(scope, 'readiness-scope.schema.json')
    snapshot = scope['dataset_snapshot_digest']
    if snapshot is None:
        raise ManifestError('scope requires the exact signed snapshot digest')
    # Refuse symlinks throughout the explicitly selected public object directory.
    object_directory = Path(os.path.abspath(public_store)) / 'sha256'
    fd = os.open(object_directory.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in object_directory.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        names = os.listdir(fd)
    finally:
        os.close(fd)
    ids = []
    witnesses = set()
    for name in names:
        if name.startswith('.tmp-'):
            continue
        match = re.fullmatch(r'([0-9a-f]{64})\.(json|envelope_digest)', name)
        if match is None:
            raise ManifestError('unexpected entry in public evidence store')
        if match[2] == 'json':
            ids.append(match[1])
        else:
            witnesses.add(match[1])
    if witnesses != set(ids):
        raise ManifestError('missing object or orphan envelope witness')
    if not 1 <= len(ids) <= 10000:
        raise ManifestError('public evidence object count outside bounded index')
    rows = []
    for artifact_id in sorted(ids):
        path = 'sha256/' + artifact_id + '.json'
        rows.append({'artifact_id': artifact_id, 'path': path,
                     'sha256': hashlib.sha256(read_beneath(public_store, path)).hexdigest(),
                     'witness_path': 'sha256/' + artifact_id + '.envelope_digest'})
    view = PublicEvidenceStore(public_store, rows)
    verify_frozen_snapshot(view, snapshot, trusted_public_key)
    target = output.absolute()
    repo = Path(__file__).resolve().parent.parent
    if target.resolve().is_relative_to(repo):
        raise ManifestError('generated evidence must remain outside the source checkout')
    # No overwrite or repair-in-place. A retry uses a new directory.
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    (target/'public'/'sha256').mkdir(mode=0o700, parents=True)
    for row in rows:
        raw = canonical_bytes(view.get(row['artifact_id']))
        with (target/'public'/row['path']).open('xb') as handle:
            handle.write(raw)
        with (target/'public'/row['witness_path']).open('xb') as handle:
            handle.write(('sha256:' + hashlib.sha256(raw).hexdigest()).encode('ascii'))
    (target/'scope.json').write_bytes(scope_raw)
    exported_rows = [{**r, 'path': 'public/'+r['path'],
                      'witness_path': 'public/'+r['witness_path']} for r in rows]
    receipts = []
    for gate in sorted(SEMANTIC_GATES):
        bundle = {'schema_version': 1, 'kind': 'signed_snapshot_verification',
                  'gate': gate, 'scope_digest': scope_digest,
                  'snapshot_digest': snapshot, 'objects': exported_rows}
        raw = canonical_bytes(bundle)
        validate(bundle, 'readiness-verification.schema.json')
        path = gate + '.json'
        (target/path).write_bytes(raw)
        receipts.append({'receipt_id': gate, 'gate': gate, 'path': path,
                         'sha256': hashlib.sha256(raw).hexdigest(),
                         'scope_digest': scope_digest, 'outcome': 'PASS'})
    # The source split was canonically replayed with external signer trust.
    # Consumers still repeat verification; this is never training approval.
    index = {'schema_version': 1, 'mode': scope['mode'], 'scope_digest': scope_digest,
             'receipts': receipts}
    validate(index, 'readiness-manifest.schema.json')
    (target/'readiness-manifest.json').write_bytes(canonical_bytes(index))
    return {'status': 'EXPORTED_REPLAY_REQUIRED', 'objects': len(rows), 'mode': scope['mode'],
            'scope_digest': scope_digest, 'training_authorized': False,
            'next_action': 'Run readiness with this scope and an out-of-band trusted custodian public key'}


def main(argv=None) -> int:
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-store', type=Path, required=True)
    parser.add_argument('--scope-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--trusted-split-public-key', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = export_public_bundle(args.public_store, args.scope_file, args.output,
                                      load_public_key(args.trusted_split_public_key,
                                                      excluded_roots=(args.public_store, args.output)))
    except (ArtifactStoreError, OSError, ValueError, TypeError, KeyError):
        print(json.dumps({'status': 'BLOCKED', 'code': 'public_evidence_export_failed',
                          'training_authorized': False,
                          'next_action': 'Use a complete public-only store, valid scope and fresh output directory'}))
        return 2
    output = args.output.absolute()
    result['next_command'] = [
        'python', '-m', 'faustcoder.readiness', '--repo-root', str(Path(__file__).resolve().parent.parent),
        '--mode', result['mode'], '--manifest', str(output/'readiness-manifest.json'),
        '--evidence-root', str(output), '--scope-file', str(output/'scope.json'),
        '--scope-digest', result['scope_digest'], '--trusted-split-public-key',
        str(args.trusted_split_public_key.absolute()), '--json',
    ]
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

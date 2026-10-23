"""Prepare bounded public train/development data; never launch or authorize training.

Consumes an explicitly indexed public signed-snapshot bundle. Private holdout
stores and tasks are not inputs. The output is source text plus provenance, not
fabricated instruction pairs or evidence of complete source qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from faustcoder.canonical import canonical_bytes, loads_strict, sha256_prefixed
from faustcoder.errors import ArtifactStoreError
from faustcoder.readiness import MODE_GATES
from faustcoder.readiness_evidence import PublicEvidenceStore, load_public_key, load_scope
from faustcoder.readiness_manifest import ManifestError, read_beneath
from faustcoder.schemas import validate
from faustcoder.split import verify_frozen_snapshot


def _partitions(store, snapshot: str) -> dict[str, bytes]:
    frozen = store.get(snapshot)['payload']
    dedup = store.get(frozen['dedup_digest'])['payload']
    assignments = store.get(frozen['split_manifest_digest'])['payload']['candidate']['assignments']
    units = {row['unit_id']: row for row in dedup['units']}
    if len(units) != len(dedup['units']):
        raise ManifestError('duplicate manifest unit')
    rows = {'train': [], 'development': []}
    seen = set()
    for digest in dedup['example_digests']:
        example = store.get(digest)['payload']
        unit_id = example['unit_id']
        if unit_id in seen or unit_id not in units:
            raise ManifestError('ambiguous example coverage')
        seen.add(unit_id)
        partition = assignments[unit_id]
        if partition == 'holdout':
            continue
        if partition not in rows:
            raise ManifestError('invalid partition')
        unit = units[unit_id]
        text = example['faust_source']
        if not isinstance(text, str) or not text or sha256_prefixed(text.encode()) != example['normalized_sha256']:
            raise ManifestError('normalized source integrity mismatch')
        for field in ('normalized_sha256', 'original_sha256', 'blob_sha', 'duplicate_family'):
            if example[field] != unit[field]:
                raise ManifestError('example differs from signed manifest unit')
        required = 'train' if partition == 'train' else 'eval'
        if required not in unit['eligible_for']:
            raise ManifestError('partition rights mismatch')
        rows[partition].append({
            'unit_id': unit_id, 'example_digest': digest,
            'source_digest': example['source_digest'], 'faust_source': text,
            'normalized_sha256': example['normalized_sha256'],
            'provenance': unit,
        })
    if seen != set(units):
        raise ManifestError('incomplete example coverage')
    for partition, cap in (('train', 28), ('development', 7)):
        if not 1 <= len(rows[partition]) <= cap:
            raise ManifestError('pilot partition outside bounded size: ' + partition)
    # Export whole partitions. Never truncate families or dependency closures to
    # fit a cap; a smaller candidate needs its own reviewed signed snapshot.
    return {name: b''.join(canonical_bytes(row) + b'\n'
                           for row in sorted(items, key=lambda r: r['unit_id']))
            for name, items in rows.items()}


def _write_new(output: Path, files: dict[str, bytes]) -> None:
    """Write through directory fds, refusing symlink parents and overwrites."""
    target = Path(os.path.abspath(output))
    fd = os.open(target.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in target.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        os.mkdir(target.name, mode=0o700, dir_fd=fd)
        child = os.open(target.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
        os.close(fd)
        fd = child
        for name, raw in files.items():
            leaf = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                           mode=0o600, dir_fd=fd)
            with os.fdopen(leaf, 'wb') as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        os.fsync(fd)
    finally:
        os.close(fd)


def prepare(root: Path, bundle_path: str, bundle_sha256: str, scope_path: Path,
            scope_digest: str, trusted_public_key: str, output: Path) -> dict:
    """Reverify a pilot-scoped signed snapshot, then stage complete partitions."""
    scope = load_scope(scope_path, scope_digest, 'pilot')
    raw = read_beneath(root, bundle_path)
    if hashlib.sha256(raw).hexdigest() != bundle_sha256:
        raise ManifestError('bundle digest mismatch')
    bundle = loads_strict(raw)
    validate(bundle, 'readiness-verification.schema.json')
    if (bundle['gate'] != 't07_signed_split' or bundle['scope_digest'] != scope_digest
            or bundle['snapshot_digest'] != scope['dataset_snapshot_digest']):
        raise ManifestError('bundle scope mismatch')
    store = PublicEvidenceStore(root, bundle['objects'])
    verify_frozen_snapshot(store, bundle['snapshot_digest'], trusted_public_key)
    partitions = _partitions(store, bundle['snapshot_digest'])
    target = output.resolve()
    if any(target.is_relative_to(path.resolve()) for path in
           (Path(__file__).parent.parent, root)):
        raise ManifestError('output must be outside checkout and evidence inputs')
    files = {name + '.jsonl': raw for name, raw in partitions.items()}
    report = {
        'schema_version': 1, 'kind': 'pilot_data_preparation',
        'status': 'PREPARED_NOT_QUALIFIED', 'training_authorized': False,
        'scope_digest': scope_digest, 'snapshot_digest': bundle['snapshot_digest'],
        'bundle_sha256': bundle_sha256,
        'signer_key_sha256': hashlib.sha256(trusted_public_key.encode()).hexdigest(),
        'exporter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'files': {name: {'sha256': hashlib.sha256(raw).hexdigest(),
                         'examples': len(raw.splitlines())} for name, raw in files.items()},
        'blockers': [gate for gate in MODE_GATES['pilot']
                     if gate not in {'t07_signed_split', 'family_disjoint_split'}]
                    + ['compiler_signal_qualification', 'instruction_pair_contract'],
    }
    # Completion marker is written last. A partial output is never reusable;
    # retries need a fresh directory and independently verified file hashes.
    files['preparation.json'] = canonical_bytes(report)
    _write_new(output, files)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', required=True, type=Path)
    parser.add_argument('--bundle', required=True, help='Relative T07 descriptor path')
    parser.add_argument('--bundle-sha256', required=True)
    parser.add_argument('--scope-file', required=True, type=Path)
    parser.add_argument('--scope-digest', required=True)
    parser.add_argument('--trusted-split-public-key', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        key = load_public_key(args.trusted_split_public_key,
                              excluded_roots=(args.evidence_root, args.output))
        result = prepare(args.evidence_root, args.bundle, args.bundle_sha256,
                         args.scope_file, args.scope_digest, key, args.output)
    except (OSError, ValueError, KeyError, TypeError, RecursionError, ArtifactStoreError):
        print(json.dumps({'status': 'BLOCKED', 'code': 'pilot_data_preparation_failed',
                          'training_authorized': False}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

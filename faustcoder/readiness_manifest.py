"""Strict, read-only evidence indexing. Integrity is never authorization.

All paths are relative to an explicitly selected evidence root. Opening each
component with O_NOFOLLOW prevents symlink swaps between check and read.
Private receipt contents are hashed in memory and never returned in reports.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Literal

from faustcoder.canonical import loads_strict
from faustcoder.schemas import validate
from faustcoder.errors import ArtifactStoreError

Mode = Literal['synthetic', 'pilot', 'full']
MAX_BYTES = 8 * 1024 * 1024


class ManifestError(ValueError):
    """Invalid or unsafe evidence input."""


@dataclass(frozen=True)
class EvidenceReference:
    receipt_id: str
    gate: str
    path: str
    sha256: str
    scope_digest: str
    outcome: str


@dataclass(frozen=True)
class EvidenceManifest:
    mode: Mode
    scope_digest: str
    receipts: tuple[EvidenceReference, ...]
    sha256: str


def read_beneath(root: Path, relative: str) -> bytes:
    """Bounded read of a regular file, without following any symlink."""
    parts = PurePosixPath(relative).parts
    if (not parts or relative != '/'.join(parts) or relative.startswith('/')
            or any(p in {'.', '..'} for p in parts) or '\\' in relative
            or '\x00' in relative):
        raise ManifestError('unsafe relative path')
    # Walk the root too: resolve() would silently accept a symlink root.
    anchor = Path(os.path.abspath(root))
    fd = os.open(anchor.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in (*anchor.parts[1:], *parts[:-1]):
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(leaf)
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
                raise ManifestError('receipt must be a bounded regular file')
            chunks = []
            size = 0
            while chunk := os.read(leaf, min(65536, MAX_BYTES + 1 - size)):
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ManifestError('receipt exceeds size limit')
            after = os.fstat(leaf)
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ManifestError('receipt changed while reading')
            return b''.join(chunks)
        finally:
            os.close(leaf)
    finally:
        os.close(fd)


def load_manifest(path: Path) -> EvidenceManifest:
    """Parse exact schema; reject duplicate keys and duplicate references."""
    try:
        data = read_beneath(path.parent, path.name)
        value = loads_strict(data)
        validate(value, 'readiness-manifest.schema.json')
        rows = tuple(EvidenceReference(**row) for row in value['receipts'])
        for key in ('receipt_id', 'path', 'sha256'):
            values = [getattr(row, key) for row in rows]
            if len(values) != len(set(values)):
                raise ManifestError(f'duplicate receipt {key}')
        return EvidenceManifest(value['mode'], value['scope_digest'], rows,
                                hashlib.sha256(data).hexdigest())
    except (OSError, ValueError, TypeError, RecursionError, ArtifactStoreError) as exc:
        raise ManifestError('invalid or unreadable evidence manifest') from exc


def verify_manifest(manifest: EvidenceManifest, root: Path, *, mode: Mode,
                    scope_digest: str, scope: dict | None = None,
                    trusted_split_public_key: str | None = None) -> dict:
    """Verify immutable references, returning only exceptions and digests.

    A PASS assertion is insufficient to clear a gate. Only an explicit semantic
    replay adapter can verify a technical gate; authorization remains separate.
    """
    blockers = []
    verified = []
    semantic = []
    public_reviews = []
    if manifest.mode != mode or manifest.scope_digest != scope_digest:
        return {'verified': [], 'blockers': [{
            'gate': 'manifest_scope', 'status': 'INVALID', 'code': 'scope_mismatch',
            'next_action': 'Regenerate manifest for the exact requested mode and scope digest'}]}
    for ref in manifest.receipts:
        code = None
        if ref.scope_digest != scope_digest:
            code = 'scope_mismatch'
        else:
            try:
                data = read_beneath(root, ref.path)
                if hashlib.sha256(data).hexdigest() != ref.sha256:
                    code = 'digest_mismatch'
            except (OSError, ManifestError):
                code = 'unsafe_or_unreadable_receipt'
        if code:
            blockers.append({'gate': ref.gate, 'receipt_id': ref.receipt_id,
                             'status': 'INVALID', 'code': code,
                             'next_action': 'Restore the exact immutable receipt or create a new scoped reference'})
            continue
        verified.append({'receipt_id': ref.receipt_id, 'gate': ref.gate,
                         'sha256': ref.sha256, 'scope_digest': ref.scope_digest,
                         'status': 'INTEGRITY_VERIFIED'})
        if ref.gate == 'public_instruction_pairs':
            from faustcoder.public_pairs import review_bundle
            try:
                report, _ = review_bundle(data, root, scope_digest=scope_digest)
            except (ArtifactStoreError, OSError, ValueError, TypeError, KeyError, RecursionError):
                blockers.append({'gate': 'instruction_pair_contract', 'receipt_id': ref.receipt_id,
                                 'status': 'INVALID', 'code': 'public_pair_binding_failed',
                                 'next_action': 'Restore exact public receipts and resolve conflicting bindings'})
                continue
            public_reviews.append({**report, 'receipt_id': ref.receipt_id})
            blockers.append({'gate': 'instruction_pair_contract', 'receipt_id': ref.receipt_id,
                             'status': 'REVIEW_REQUIRED', 'code': 'public_pairs_not_qualified',
                             'next_action': 'Replay compiler/signal and prompt semantics, then bind admitted Examples to signed partitions'})
            continue
        if ref.outcome == 'PASS' and ref.gate in {'t07_signed_split', 'family_disjoint_split'}:
            if scope is None or trusted_split_public_key is None:
                blockers.append({'gate': ref.gate, 'receipt_id': ref.receipt_id,
                                 'status': 'REVIEW_REQUIRED', 'code': 'semantic_inputs_required',
                                 'next_action': 'Supply the hash-bound scope file and out-of-band custodian public key'})
                continue
            from faustcoder.readiness_evidence import verify_split_evidence
            try:
                decision = verify_split_evidence(data, root, gate=ref.gate,
                    scope_digest=scope_digest, scope=scope, trusted_public_key=trusted_split_public_key)
            except (ArtifactStoreError, OSError, ValueError, TypeError, KeyError, RecursionError):
                blockers.append({'gate': ref.gate, 'receipt_id': ref.receipt_id,
                                 'status': 'INVALID', 'code': 'semantic_verification_failed',
                                 'next_action': 'Restore complete scope-bound public evidence and verify the trusted signer and recheck date'})
                continue
            semantic.append({**decision, 'receipt_id': ref.receipt_id, 'sha256': ref.sha256})
            continue
        blockers.append({'gate': ref.gate, 'receipt_id': ref.receipt_id,
                         'status': 'REVIEW_REQUIRED',
                         'code': 'receipt_outcome_not_verified' if ref.outcome == 'PASS' else 'receipt_reports_blocker',
                         'next_action': 'Validate receipt semantics and required authority with the gate-specific verifier'})
    blocked_gates = {row['gate'] for row in blockers}
    return {'verified': verified, 'semantic_verification': semantic,
            'public_pair_reviews': public_reviews,
            'verified_gates': sorted({row['gate'] for row in semantic} - blocked_gates),
            'blockers': blockers}

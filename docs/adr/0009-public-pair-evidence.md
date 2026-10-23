# ADR-0009: Public receipt and instruction-pair binding

Status: Proposed implementation; no admission or governance change.

## Decision

Reuse immutable public R3b approval receipts via an explicit hash-bound descriptor.
Keep recorded source/behavior/closure decisions separate from full source rights,
canonical dataset admission, runtime qualification and training permission.
Derive candidate instructions deterministically from approved behavior fields;
use unchanged source bytes as targets and retain the original MIT notice.
Apply only the import overlay explicitly named by the behavior approval.

Readiness exposes binding checks and remaining blockers, never raw source,
prompt text or personal receipt contents. The adapter clears no readiness gates.
The instruction-pair contract is a separate supervised-pilot blocker so encoding or a
signed snapshot alone cannot imply that supervised examples are qualified.

## Alternatives and consequences

Copying legacy PASS flags into readiness would conflate review scope with
admission. Rewriting the original draft would destroy its approval hash.
Instead every candidate retains source, contract, approval and prompt digests.
Tests use generated fixtures; real sources and receipts remain outside Git.

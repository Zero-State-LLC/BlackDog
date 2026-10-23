# ADR-0009: Readiness evidence index

Status: Implementation proposed for review under QR-09.

The recovery reporter accepts a strict version-1 external index. Each immutable
reference binds a receipt ID, exact-byte SHA-256, relative path, gate, outcome
claim and scope digest. The manifest binds its operating mode and exact scope.
References with duplicate IDs, paths or hashes are refused. Files are opened
relative to a caller-selected evidence root using no-follow directory handles;
symlinks, traversal, special files and oversized input fail closed.

An intact receipt proves its bytes, not its contents or authority. PASS claims
remain REVIEW_REQUIRED until gate-specific semantic and authority verifiers
exist. This implementation cannot grant training permission, corpus admission,
FLOOR acceptance, stack pinning or human custody. Existing signed-artifact and
reward verification contracts remain authoritative. No private bytes are emitted.

The index is advisory, not a new admission artifact. It uses the existing schema
loader and strict canonical JSON decoder. Missing receipts remain NOT_VERIFIED;
invalid supplied evidence is INVALID and produces CLI exit 2. A valid but blocked
report exits 0, meaning the report ran, never that training is permitted.

Tests cover integrity, malformed/schema input, duplicate identities, tampering,
symlinks at root/parent/leaf, traversal, FIFO, size limits, exact scope/mode and
self-declared authorization refusal. Additional semantic receipt adapters remain QR-09 work.

## Semantic replay extension

The reporter may clear only `t07_signed_split` and `family_disjoint_split` after
replaying the existing canonical signed-freeze verifier. A separately supplied
scope file binds exact dataset/model/recipe/code inputs; its exact-byte SHA-256
must match the manifest scope. The bundle enumerates canonical public artifacts
and their envelope witnesses. A no-follow, bounded, read-only store view checks
hashes, parents and cycles without discovering or opening unlisted files.
Private tasks and benchmark entities are refused. A custodian public key must be
supplied outside the bundle, which cannot enroll a signer or carry a trust key.

A verified provisional split is not FLOOR acceptance, P3 exit, model approval,
source qualification, checkpoint qualification or training permission. Those
gates remain independent. Missing trust leaves review required; invalid signed
or scope evidence fails closed. Existing receipt types without semantic adapters
remain unverified. This extends advisory reporting, not canonical training policy.

The public replay view verifies the complete indexed DAG once, then reuses its
validated in-memory graph. Its get method returns copies and put is refused,
so later canonical verifier reads cannot mutate the checked graph. No unlisted
file is discovered by semantic replay.

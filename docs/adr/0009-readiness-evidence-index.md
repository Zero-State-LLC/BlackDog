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
self-declared authorization refusal. Semantic receipt adapters remain QR-09 work.

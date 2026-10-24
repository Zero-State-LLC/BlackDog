# ADR-0012: Recorded family feasibility

Status: Proposed implementation under QR-03/QR-10; no admission policy change.

## Decision

Replay explicit, hash-bound public accounting files before assessing whether the
selected candidates can occupy disjoint families. Reconstruct pairwise and
collective joins and require a bijection between components and recorded family
labels. Bind the complete ledger population and selected unchanged source hashes.
Report a specific blocked state when fewer than two selected families exist.

## Consequences

Structural replay verifies consistency of the supplied graph, not the original
similarity measurements or canonical family digest derivation. Collective joins
remain intact and do not imply COPY adjudication. Outside-family inventory is
not qualified data. Multiple components alone do not establish project/lineage
separation, admission or signed partition membership. No readiness gate clears.

## Outside-family inventory follow-through

An optional descriptor extension binds the complete candidate ledger to its
original accounting hash, with exact source references for every outside-family
unit. Inventory bytes may be supplied as at most four ordered bounded parts;
the concatenated bytes must match the original hash. Individual file limits
remain unchanged. Replay verifies all candidate identities and source hashes,
then reports definition categories and recorded eligibility. Proposed dependency
memberships are flagged without promoting them into verified closure or new
family edges. `frac` is not in the narrow primitive allowlist: its standalone
native diagnostic produced `unbound_symbol`, consistent with a library helper.

Recorded member permission intersections are conservative inventory observations, not closure or admission proofs. Unknown metadata remains explicit and dependency_closure_verified stays false. See [external checks](../analysis/external-dependency-readiness-2026-10-23.md).

Stream-family wrapper joins must be emitted explicitly as stream_component records, including equal digest-set identities that have no underlying stream edge. Structural replay validates their identity syntax; this does not adjudicate canonical equivalence. Active assignments remain unchanged. See [resolution](../analysis/goertzel-family-resolution-2026-10-23.md).

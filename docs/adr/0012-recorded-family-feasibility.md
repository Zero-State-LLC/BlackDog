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

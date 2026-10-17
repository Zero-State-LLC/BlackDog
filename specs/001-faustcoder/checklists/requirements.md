# Requirements quality checklist: spec 001

Purpose: check that the spec is complete, clear and consistent before
implementation. Checked items reflect the state of the spec on 2026-10-16.

## Completeness

- [x] Scope and out-of-scope are stated (§2).
- [x] Every user journey maps to tasks (J-01 to J-03: T13, T14; J-04: T05 to T12).
- [x] Every stateful lifecycle has an explicit state machine (§7.1 to §7.4).
- [x] Governing workflows are named (§16).
- [x] Contracts list their fields (§8).
- [ ] Every requirement has a measurable acceptance criterion. Open: R-007, R-008 and the quality gates depend on D-002 and D-005.
- [ ] Repair attempt bound (`max_repair_attempts`) has a value. Open (§7.2).

## Clarity

- [x] Compile success is never treated as acceptance (§1, §7.2, §9).
- [x] The two graphs are defined separately (§4, ADR-0001).
- [x] The V0.2 compile@1 target is labeled provisional (§9).

## Consistency

- [x] Task IDs match KANBAN.md and §13.
- [x] State names in §7 match the original lifecycle lines.
- [x] Release gate in §15 matches the guard on `evidence_assembled` (§7.4).

## Governance

- [x] Data rights, holdout sealing and sandboxing appear as requirements (R-003, R-013, R-014).
- [ ] Open decisions D-001 to D-006 have owners. Partly: D-003 (sample rates), D-004 and D-006r2 ACCEPTED 2026-10-16 (spec §18); D-002, D-005 and D-003 runtimes open.

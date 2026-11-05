# Collaborator handoff (2026-10-29)

This page is for a collaborator joining BlackDog (Python package `faustcoder`).
It records the state of the project on 2026-10-29 PT. Read
[CONTRIBUTING.md](../CONTRIBUTING.md) for workflow, licensing and required
checks; this page does not repeat it.

## Current main

- `main` is at `a7e945c` (2026-10-27 23:57 PT), "ci(secret-scan): ignore 3
  reviewed generic-api-key false positives (#117)".
- The canonical spec is [specs/001-faustcoder](../specs/001-faustcoder/);
  decisions are in [docs/adr](adr/) and [docs/decisions](decisions/). Task
  status is in [KANBAN.md](../KANBAN.md).
- Slice 1 qualification is merged. Slice 2 readiness is **blocked**:
  `TOKEN_FLOOR=40` is provisional and production T07 is unfrozen. See
  [Remaining exit gates](runbooks/slice2-readiness.md#remaining-exit-gates).
- The team Spark checkout was fast-forwarded to `a7e945c` on 2026-10-29. Its
  local branches all match merged PR heads (no unpushed commits); its two
  stashes are backed up on the Spark and left in place.

## In flight: avoid overlapping work

Talk to the owner before touching any of these.

| Item | What it is | Status |
|---|---|---|
| [#115](https://github.com/Zero-State-LLC/BlackDog/pull/115) | Qualification recovery integration and scoped readiness evidence (`spec/qualification-recovery-20261023`) | Draft PR |
| [#113](https://github.com/Zero-State-LLC/BlackDog/pull/113) | Bounded diagnostic controls, input routing and guarded zero cases (`feat/diagnostic-control-cases`) | Open PR; implements [#108](https://github.com/Zero-State-LLC/BlackDog/issues/108) |
| [#108](https://github.com/Zero-State-LLC/BlackDog/issues/108) | Slice 2 harness: per-block control values, per-input stimuli, explicit expected-zero cases | Issue; covered by #113 |
| [#76](https://github.com/Zero-State-LLC/BlackDog/pull/76) | Bind TaskSpec at the committed signal reward boundary (`fix/reward-commit-task-binding`) | Draft PR |
| [#73](https://github.com/Zero-State-LLC/BlackDog/pull/73) | Model-quality hardening and implementation audit plan (`spec/002-model-quality-hardening`) | Open PR |
| [#10](https://github.com/Zero-State-LLC/BlackDog/issues/10) T07 split freeze, [#13](https://github.com/Zero-State-LLC/BlackDog/issues/13) T10 training path | Blocked on the pending Slice 2 gates below | Do not start |

The pending Slice 2 gates that block #10 and #13 (details in the
[slice2-readiness runbook](runbooks/slice2-readiness.md#remaining-exit-gates)):

1. Independent approval of a source/task/dependency subset, and adjudication of
   the quarantine set. All 174 R2 dependency decisions are still pending.
2. FLOOR qualification: two-project cleared hosts, real rejected windows,
   ratified plants and false-positive adjudication, then a floor decision.
3. Project-disjoint development tasks with semantic references.
4. Private-task custody: independent author arrangement, private storage and
   human-only access. Private holdout tasks are never stored in this repo or on
   shared machines; do not ask for them.
5. Signing review and trusted public verification, only after gates 1-4 close.

Also open: [#116](https://github.com/Zero-State-LLC/BlackDog/pull/116)
(Dependabot), [#33](https://github.com/Zero-State-LLC/BlackDog/pull/33) and
[#32](https://github.com/Zero-State-LLC/BlackDog/pull/32) (older spec/docs PRs).

## Where the Slice 2 evidence lives

Evidence stays out of Git. The 2026-10-22 Slice 2 evidence the runbooks cite is
collected in one read-only bundle **on the team Spark, at the path given in the
private manifest**. Ask the owner for access. The bundle contains:

- the 174 R2 dependency-closure drafts (v3),
- the verified Forge R2 packet,
- the R3 consolidated packet and R3b notice receipts,
- the seven-unit contract, dependency, behavior, negative-control, admission
  and source-approval folders,
- the FLOOR and gate audit folders.

Each folder has its own `SHA256SUMS`, and the bundle has a top-level
`SHA256SUMS` and `MANIFEST.md`. The manifest maps each folder to its source,
purpose and the doc here that cites it. Holdout custody files are excluded.

The generators for the two cited folders are in
[scripts/slice2](../scripts/slice2/README.md), with host paths replaced by
environment variables.

## Good first areas

These open issues are unassigned and do not overlap the work above:

- Fail-closed review follow-ups:
  [#62](https://github.com/Zero-State-LLC/BlackDog/issues/62),
  [#68](https://github.com/Zero-State-LLC/BlackDog/issues/68),
  [#69](https://github.com/Zero-State-LLC/BlackDog/issues/69),
  [#72](https://github.com/Zero-State-LLC/BlackDog/issues/72). These are small,
  well-scoped and the best place to start.
- Product surface, not blocked by Slice 2:
  [#16](https://github.com/Zero-State-LLC/BlackDog/issues/16) T13 local serving
  API, [#17](https://github.com/Zero-State-LLC/BlackDog/issues/17) T14 IDE
  integration.
- Target lanes (v0.3):
  [#25](https://github.com/Zero-State-LLC/BlackDog/issues/25) T17 language
  backend, [#26](https://github.com/Zero-State-LLC/BlackDog/issues/26) T18
  plugin lane, [#27](https://github.com/Zero-State-LLC/BlackDog/issues/27) T19
  embedded, [#29](https://github.com/Zero-State-LLC/BlackDog/issues/29) T21
  real-time safety. Read ADR-0004 first.

Leave the model-path issues to the owner for now:
[#11](https://github.com/Zero-State-LLC/BlackDog/issues/11) T08 baselines,
[#12](https://github.com/Zero-State-LLC/BlackDog/issues/12) T09,
[#14](https://github.com/Zero-State-LLC/BlackDog/issues/14) T11 and
[#15](https://github.com/Zero-State-LLC/BlackDog/issues/15) T12 depend on T07
and T10.

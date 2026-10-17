# Tasks: FaustCoder (spec 001)

- Input: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [contracts/](contracts/)
- Mirror: [KANBAN.md](../../KANBAN.md) and the GitHub Project "FaustCoder". Task IDs match KANBAN.

Format: `- [ ] Txx [P?] [Story] Description`. `[P]` means it can run in parallel
with other `[P]` tasks once its dependencies are met. Every task lists
dependencies, acceptance evidence (OBSERVED from KANBAN), governing workflows
(copied from spec §16) and an evidence path (INFERRED). Every task also needs an
owner, inputs, outputs, failure disposition and evidence path before it starts
(spec §13).

Governing workflows for all implementation tasks: anti-slop-code,
production-systems, google-developer-style. State-machine tasks also follow
spec-kit; security-relevant tasks add ADVERSARY review.

## Phase 1: Setup

- [ ] T01 [Setup] Constitution and ADRs.
  - Depends on: none. Milestone: v0.1.
  - Acceptance: reviewed architectural decisions; ADR-0001 moves from PROPOSED to ACCEPTED.
  - Workflows: spec-kit, google-developer-style. Owner: FORGE, SCRIBE.
  - Evidence: `docs/adr/`, `.specify/memory/constitution.md`.

## Phase 2: Foundational (blocks every user story)

- [ ] T02 [Found] JSON schemas and immutable artifact store.
  - Depends on: T01. Milestone: v0.1.
  - Acceptance: schema validation and digest tests; store rejects payload mutation and parent cycles (constitution II).
  - Implements: [contracts/](contracts/), [data-model.md](data-model.md).
  - Workflows: anti-slop-code, production-systems. Evidence: `receipts/T02/` (INFERRED).
- [ ] T03 [Found] Sandboxed Faust compiler harness.
  - Depends on: T02. Milestone: v0.1.
  - Acceptance: reproducible compiler receipts (R-005); no network, bounded resources (R-013).
  - Amended 0.3.0 (ADR-0004): wrap libfaust from faustwasm 0.19.0 in a Node.js worker; cross-check with the native Faust 2.88.0 CLI; classify diagnostics.
  - Workflows: production-systems, ADVERSARY review. Evidence: `receipts/T03/` (INFERRED).
- [ ] T04 [Found] DSP signal test harness.
  - Depends on: T03. Milestone: v0.1.
  - Acceptance: known-good and known-bad fixtures; legal delayed feedback passes (ADR-0001, V0.3).
  - Amended 0.3.0 (ADR-0004): offline render with faustwasm at 44.1 and 48 kHz; reference comparison in the style of Faust `tests/impulse-tests`; CPU only on promotion candidates.
  - Workflows: anti-slop-code, production-systems. Evidence: `receipts/T04/` (INFERRED).

## Phase 3: User story J-04, maintainer ingests examples through to a release decision

Implements the dataset machine (spec §7.1) and training machine (spec §7.3).

- [ ] T05 [P] [J-04] Source rights inventory.
  - Depends on: T01. Milestone: v0.1.
  - Acceptance: provenance and exclusion receipts; implements `rights_cleared` and `rights_rejected` transitions.
  - Workflows: production-systems, ADVERSARY review (poisoning, licensing). Evidence: `corpus/` records, receipts.
- [ ] T06 [J-04] Normalization and dedup.
  - Depends on: T05, T02. Milestone: v0.2.
  - Acceptance: deterministic snapshot; implements `normalized` and `dedup_passed` transitions.
  - Workflows: anti-slop-code, production-systems.
- [ ] T07 [J-04] Split freeze.
  - Depends on: T06. Milestone: v0.2.
  - Acceptance: leakage checks and signed split manifest; implements `split_frozen` (R-003).
  - Workflows: production-systems.
- [ ] T08 [J-04] Baseline models.
  - Depends on: T04, T07. Milestone: v0.2.
  - Acceptance: frozen baseline measurements (R-007); input to D-002 and D-005.
  - Workflows: production-systems.
- [ ] T09 [P] [J-04] DGX Spark feasibility study.
  - Depends on: T01. Milestone: v0.2.
  - Acceptance: ARM64/Blackwell throughput and memory receipts (R-001); implements `env_verified`.
  - Workflows: production-systems.
- [ ] T10 [J-04] Training path P1 to P3 (ADR-0002).
  - Depends on: T08, T09. Milestone: v0.2 (P1, P2) and v0.3 (P3).
  - Acceptance: one pinned, reproducible `TrainingRun` per phase with its exit-gate result (R-008, R-009, R-015); P1 may be a recorded skip; implements `run_started` to `COMPLETED`.
  - Sub-steps: P1 continued pretraining or skip; P2 SFT on validated pairs; P3 compiler-feedback RL (R-016).
  - Workflows: anti-slop-code, production-systems.
- [ ] T11 [J-04] Independent DSP evaluation.
  - Depends on: T10, T04. Milestone: v0.3.
  - Acceptance: paired metrics and regression results with confidence intervals (§9, R-011).
  - Workflows: production-systems.
- [ ] T12 [J-04] Promotion decision.
  - Depends on: T11. Milestone: v0.3.
  - Acceptance: human review and DecisionRecord; implements `admit` and `reject`.
  - Workflows: spec-kit, google-developer-style.

## Phase 3b: Target lanes (ADD 0.3.0, ADR-0004)

Each lane emits a `TargetReceipt` and has known-good and known-bad fixtures.
Lanes run in parallel with T10.

- [ ] T17 [P] [Lane] Language-backend lane (R-024).
  - Depends on: T03. Milestone: v0.3.
  - Acceptance: `-lang cpp`, `c`, `rust` and `cmajor` output compiles in pinned toolchains, and compiled runs match the host render.
  - Workflows: anti-slop-code, production-systems.
- [ ] T18 [P] [Lane] Plugin lane (R-023, D-012).
  - Depends on: T04. Milestone: v0.3.
  - Acceptance: CLAP (`faust2clap`), VST3 (clap-wrapper) and LV2 (`faust2lv2`) build in a Linux container; `clap-validator`, `pluginval` and `lv2lint` pass on known-good fixtures and fail on known-bad ones; parameter-map check passes. AU deferred to macOS CI.
  - Workflows: anti-slop-code, production-systems, ADVERSARY review (container and SDK supply chain).
- [ ] T19 [P] [Lane] Embedded lane (R-019, D-008).
  - Depends on: T04. Milestone: v0.3.
  - Acceptance: `faust2daisy` and `faust2teensy` builds with pinned SDKs; flash and RAM budgets from linker maps; CPU proxy budget; real-time checks (R-021). No board purchase.
  - Workflows: anti-slop-code, production-systems.
- [ ] T20 [Lane] Remix tasks and novelty metric (R-020, D-010).
  - Depends on: T08. Milestone: v0.3.
  - Acceptance: remix tasks in the dev suite with two or more source demos; novelty reported as a dev metric; correctness uses the normal gates.
  - Workflows: anti-slop-code.
- [ ] T21 [P] [Lane] Real-time safety checks (R-021).
  - Depends on: T04. Milestone: v0.3.
  - Acceptance: fixtures with NaN, denormals, unbounded delay memory and allocation in the callback are rejected on every lane.
  - Workflows: anti-slop-code, production-systems.
- [ ] T22 [P] [Lane] FPGA F0 spike (R-022, D-009).
  - Depends on: T04. Milestone: v0.5-fpga. Timebox: 1 week.
  - Acceptance: DecisionRecord comparing three lowerings for a one-pole low-pass and a sine oscillator: Verilator sim vs Faust render, Yosys and nextpnr results for iCE40 and ECP5, audio-rate throughput.
  - Workflows: production-systems, spec-kit (DecisionRecord).

## Phase 4: User stories J-01, J-02, J-03 (generate, repair, optimize)

Implements the candidate machine (spec §7.2).

- [ ] T13 [J-01, J-02, J-03] Local serving API.
  - Depends on: T12. Milestone: v0.4.
  - Acceptance: contract tests against [contracts/inference-api.md](contracts/inference-api.md); bounded repair (R-012).
  - Workflows: anti-slop-code, production-systems, ADVERSARY review.
- [ ] T14 [J-01, J-02, J-03] IDE integration.
  - Depends on: T13. Milestone: v0.4.
  - Acceptance: end-to-end journey tests for J-01 to J-03 on Spark with reproducible receipts.
  - Workflows: anti-slop-code, production-systems.

## Phase 5: Polish and release

Implements the release machine (spec §7.4).

- [ ] T15 Security and quality review.
  - Depends on: T14. Milestone: v1.0.
  - Acceptance: independent audit.
  - Workflows: ADVERSARY, production-systems.
- [ ] T16 Release.
  - Depends on: T15. Milestone: v1.0.
  - Acceptance: signed release manifest and rollback test; full §15 gate.
  - Workflows: production-systems, google-developer-style (model and data cards).

## Dependency graph

```mermaid
graph LR
    T01 --> T02 --> T03 --> T04
    T01 --> T05 --> T06
    T02 --> T06 --> T07 --> T08
    T04 --> T08
    T01 --> T09
    T08 --> T10
    T09 --> T10 --> T11
    T04 --> T11 --> T12 --> T13 --> T14 --> T15 --> T16
    T03 --> T17
    T04 --> T18
    T04 --> T19
    T08 --> T20
    T04 --> T21
    T04 --> T22
```

Parallel starts after T01: T02, T05 and T09. Lanes T17 to T19, T21 and T22 run in parallel with T10.

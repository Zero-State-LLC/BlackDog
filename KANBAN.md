# BlackDog implementation backlog

Formerly FaustCoder; renamed 2026-10-17 PT.

All tasks are **TODO**. Dependency arrows are mandatory promotion gates.

| ID | Milestone | Task | Depends on | Acceptance evidence |
|---|---|---|---|---|
| T01 | v0.1 | Constitution and ADRs | none | Reviewed architectural decisions |
| T02 | v0.1 | JSON schemas and immutable artifact store | T01 | Schema validation and digest tests |
| T03 | v0.1 | Sandboxed Faust compiler harness | T02 | Reproducible compiler receipts |
| T04 | v0.1 | DSP signal test harness | T03 | Known-good/known-bad fixtures |
| T05 | v0.1 | Source rights inventory | T01 | Provenance and exclusion receipts |
| T06 | v0.2 | Normalization and dedup | T05,T02 | Deterministic snapshot |
| T07 | v0.2 | Split freeze | T06 | Leakage checks and signed split manifest |
| T08 | v0.2 | Baseline models | T04,T07 | Frozen baseline measurements |
| T09 | v0.2 | DGX Spark feasibility study | T01 | Fingerprint receipt per machine (R-001, amended 0.3.1); throughput deferred to T10 |
| T10 | v0.2 | Training path P1-P3 (ADR-0002) | T08,T09 | One pinned run and exit-gate result per phase |
| T11 | v0.3 | Independent DSP evaluation | T10,T04 | Paired metrics and regression results |
| T12 | v0.3 | Promotion decision | T11 | Human review and decision record |
| T13 | v0.4 | Local serving API | T12 | Contract tests |
| T14 | v0.4 | IDE integration | T13 | End-to-end journey tests |
| T15 | v1.0 | Security and quality review | T14 | Independent audit |
| T16 | v1.0 | Release | T15 | Signed release manifest and rollback test |
| T17 | v0.3 | Language-backend lane (ADR-0004) | T03 | cpp, c, rust, cmajor output compiles and matches host render |
| T18 | v0.3 | Plugin lane: CLAP, VST3, LV2 (ADR-0004) | T04 | Validators and parameter-map check on good and bad fixtures |
| T19 | v0.3 | Embedded lane: Daisy, Teensy 4.x (ADR-0004) | T04 | Builds, memory and CPU budgets, real-time checks |
| T20 | v0.3 | Remix tasks and novelty metric | T08 | Remix dev tasks; novelty reported, not gated |
| T21 | v0.3 | Real-time safety checks | T04 | Bad fixtures rejected on every lane |
| T22 | v0.5-fpga | FPGA F0 spike | T04 | DecisionRecord on the lowering path |

Proposed T06/T07 requirement (D-013, Danny yes 2026-10-17 1:04 PM PT): an n-gram or AST near-duplicate filter on generated `.dsp` against the training-only set. The threshold is not set. Impulse-test paths already cannot take `eval`.

Lane issues (ADR-0004): T17 #25, T18 #26, T19 #27, T20 #28, T21 #29, T22 #30.

## Decisions

Mirrors the decision items on the [project board](https://github.com/orgs/Zero-State-LLC/projects/29). Log: [spec §18](specs/001-faustcoder/spec.md#18-decision-log).

| ID | Decision | Status | Record |
|---|---|---|---|
| LIC-001 | Split license: Apache-2.0 for specs/ and docs/, Zero State proprietary for the rest | Done (ACCEPTED 2026-10-16) | ADR-0003, #20 |
| D-003 | Sample rates 44.1 and 48 kHz (runtime clause superseded by D-003r2) | ACCEPTED 2026-10-16 | spec §14 |
| D-004 | Corpus allowlist; GPL training-only; unlicensed excluded | ACCEPTED 2026-10-16 | ADR-0003 |
| D-006 | Teacher: Opus via OpenRouter, per-run spend cap | SUPERSEDED 2026-10-16 22:25 PT | ADR-0002 |
| D-006r2 | Teacher: open-weight deepseek-v4.1-flash via OpenRouter, per-run cap; Opus for review and judging only | ACCEPTED 2026-10-16 | ADR-0002, ADR-0003 |
| ORG-001 | Repo moved to Zero-State-LLC; repo and board public for now (revisitable) | Done 2026-10-16 22:32 PT | spec §18 |
| D-003r2 | Runtimes: wasm for eval, native C++ 2.88.0 cross-check, target lanes | ACCEPTED 2026-10-16 23:39 PT | spec §14, ADR-0004 |
| D-007 | Per-function licensing; header-less files inherit repo license; AGPL excluded | ACCEPTED 2026-10-16 23:39 PT | ADR-0003 |
| D-008 | First boards Daisy and Teensy 4.x; no purchase yet | ACCEPTED 2026-10-16 23:39 PT | ADR-0004 |
| D-009 | FPGA path after F0 spike; iCE40 and ECP5; audio-rate throughput | ACCEPTED 2026-10-16 23:39 PT | ADR-0004 |
| D-010 | Remix novelty is a dev metric; faust-rs primitives out | ACCEPTED 2026-10-16 23:39 PT | ADR-0004 |
| D-011 | Upstream Faust fixes under LGPL allowed | ACCEPTED 2026-10-16 23:39 PT | ADR-0003 |
| D-012 | Plugin formats CLAP, VST3 (clap-wrapper), LV2; AU deferred | ACCEPTED 2026-10-16 23:39 PT | ADR-0004 |
| ORG-002 | Board moved to org project 29; user board 8 kept, marked superseded | Done 2026-10-16 | spec §18 |
| R-001 | v0.2 evidence: cited external Spark benchmarks plus a per-machine fingerprint; throughput is T10 on the cleared dedicated Spark | ACCEPTED 2026-10-17 12:54 PM PT | spec §20 |
| D-013 | STK-4.3 permissive with notice; bare BSD not redistributed; notice required; vendored copies deduped; per-function slicing; strictest license; copyleft near-duplicate gate proposed for T06/T07 | ACCEPTED 2026-10-17 1:04 PM PT | spec §22, ADR-0003 |
| ADR-0006 | Source-attributable failures graded at parse_error; env/harness errors (reproducible infra failures and deterministic harness defects) ungraded + quarantined; A1–A7 (A7 numbers provisional). A2 extended 2026-10-17 4:28 PM PT (Danny): untraced timeouts/crashes quarantined | ACCEPTED 2026-10-17 4:11 PM PT (Danny) | docs/adr/0006 |

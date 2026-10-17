# FaustCoder implementation backlog

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
| T09 | v0.2 | DGX Spark feasibility study | T01 | ARM64/Blackwell throughput and memory receipts |
| T10 | v0.2 | Training path P1-P3 (ADR-0002) | T08,T09 | One pinned run and exit-gate result per phase |
| T11 | v0.3 | Independent DSP evaluation | T10,T04 | Paired metrics and regression results |
| T12 | v0.3 | Promotion decision | T11 | Human review and decision record |
| T13 | v0.4 | Local serving API | T12 | Contract tests |
| T14 | v0.4 | IDE integration | T13 | End-to-end journey tests |
| T15 | v1.0 | Security and quality review | T14 | Independent audit |
| T16 | v1.0 | Release | T15 | Signed release manifest and rollback test |

## Decisions

Mirrors the decision items on the [project board](https://github.com/users/scrimshawlife-ctrl/projects/8). Log: [spec §18](specs/001-faustcoder/spec.md#18-decision-log).

| ID | Decision | Status | Record |
|---|---|---|---|
| LIC-001 | Split license: Apache-2.0 for specs/ and docs/, Zero State proprietary for the rest | Done (ACCEPTED 2026-10-16) | ADR-0003, #20 |
| D-003 | Sample rates 44.1 and 48 kHz | ACCEPTED 2026-10-16 | spec §14 |
| D-004 | Corpus allowlist; GPL training-only; unlicensed excluded | ACCEPTED 2026-10-16 | ADR-0003 |
| D-006 | Teacher: Opus via OpenRouter, per-run spend cap | SUPERSEDED 2026-10-16 22:25 PT | ADR-0002 |
| D-006r2 | Teacher: open-weight deepseek-v4.1-flash via OpenRouter, per-run cap; Opus for review and judging only | ACCEPTED 2026-10-16 | ADR-0002, ADR-0003 |
| ORG-001 | Repo moved to Zero-State-LLC, stays public (public versus private open) | Done 2026-10-16 | spec §18 |

# Docs index

Index of the documents in this repository at main `a414dfd` (spec 001 version 0.3.11). `docs/adr` and `docs/decisions` have no index files of their own. The Python package name is `faustcoder`. The repository is `Zero-State-LLC/BlackDog`.

## Architecture decision records

| Record | Description |
|---|---|
| [ADR-0001](adr/0001-dag-evidence.md) | PROPOSED. Evidence is an acyclic content-addressed graph; Faust DSP is a typed signal-flow graph that may contain feedback |
| [ADR-0002](adr/0002-training-path.md) | ACCEPTED 2026-10-17 7:40 PM PT. Continued pretraining, SFT, then compiler-feedback RL, with the Q1–Q4 gates |
| [ADR-0003](adr/0003-licensing-and-data-rights.md) | ACCEPTED. Split license, and the corpus allowlist (GPL training-only, unlicensed excluded) |
| [ADR-0004](adr/0004-target-lanes-and-faust-tooling.md) | ACCEPTED. Reuse Faust tooling and add language, plugin, embedded and FPGA target lanes |
| [ADR-0005](adr/0005-compiler-diagnostic-classes.md) | ACCEPTED. CompilerReceipt classes for an unbound name, a resource limit and an internal harness failure |
| [ADR-0006](adr/0006-source-attributable-failures.md) | ACCEPTED. Grade source-attributable failures at `parse_error`; quarantine environment and harness errors (A1–A7) |

## Decision records

| Record | Description |
|---|---|
| [danny-d3h2-audit-2026-10-18.md](decisions/danny-d3h2-audit-2026-10-18.md) | Danny, 2026-10-18 8:10 AM PT: "Approve the §26 0.3.9 amendment as recommended" (sampled rerun audit) |
| [danny-d3h2-option-c-2026-10-18.md](decisions/danny-d3h2-option-c-2026-10-18.md) | Danny, 2026-10-18 5:11 PM PT: the §26 0.3.10 human triage credential. A 5:45 PM PT note records that a software key is fine for his key |
| [danny-floor-bounds-2026-10-18.md](decisions/danny-floor-bounds-2026-10-18.md) | Danny, 2026-10-18 12:34 AM PT: FLOOR acceptance bounds (D6) ratified, 5% FP budget |
| [FLOOR-ruling-b-recommendation-2026-10-18.md](decisions/FLOOR-ruling-b-recommendation-2026-10-18.md) | Recommendation Danny accepted at 2:27 AM PT ("continue as recommended"): a lower-floor-only copy counts through item 4(a) |
| [jev-output-2026-10-17.txt](decisions/jev-output-2026-10-17.txt) | Jev's Q1–Q4 text from 2026-10-17, quoted by spec §24 |

## Runbooks

| Runbook | Description |
|---|---|
| [spark-local-setup.md](runbooks/spark-local-setup.md) | Completed T04 validation, original and repaired-candidate T09 receipts, validated cuSPARSELt repair, synthetic and Qwen training/checkpoint smokes, merged library rendering, receipt locations and remaining T10 gates |
| [compiler-harness.md](runbooks/compiler-harness.md) | Sandboxed faustwasm compiler (T03) and how reward grading reads its receipts |
| [signal-harness.md](runbooks/signal-harness.md) | Offline DSP signal harness (T04), reward grading, and the D3-H2 audit gate |
| [function-spans.md](runbooks/function-spans.md) | Digest-pinned reviewed function byte spans, extraction trust boundary and regression acceptance |
| [t07-candidate-audit.md](runbooks/t07-candidate-audit.md) | Offline Spark corpus audit, unsigned project/family split proposal, receipt locations and blockers before T07 freeze |
| [t06-normalize-dedup.md](runbooks/t06-normalize-dedup.md) | Normalize pinned sources and write a deterministic dedup manifest without clearing rights |
| [dgx-spark-env-verified.md](runbooks/dgx-spark-env-verified.md) | Record the R-001 environment fingerprint on a cleared DGX Spark |

## State machines

| Machine | Description |
|---|---|
| [candidate.md](state-machines/candidate.md) | Candidate lifecycle (spec §7.2), including `signal_passed` and `signal_failed` |
| [training.md](state-machines/training.md) | Training-machine lifecycle (spec §7.3). T09 persists `env_verified` only |

## Analysis

| Note | Description |
|---|---|
| [t06-short-kernel-floor.md](analysis/t06-short-kernel-floor.md) | Short rejected kernels at floors 40, 30, 20 and 15. `TOKEN_FLOOR=40` is not accepted clearance policy |

## Other docs

| Doc | Description |
|---|---|
| [dataset-lifecycle.md](dataset-lifecycle.md) | T05 rights edges of the dataset machine (spec §7.1) |
| [dgx-spark-feasibility.md](dgx-spark-feasibility.md) | Whether a training phase fits one DGX Spark. Published facts are separated from estimates |
| [rights-inventory.md](rights-inventory.md) | How T05 records corpus rights metadata. No program text is stored in this repo |
| [VERSIONING.md](VERSIONING.md) | Semantic versioning. There is no release tag until the V0.1 acceptance is met |
| [LICENSE](LICENSE) | Apache-2.0 text that covers `docs/` and `specs/` |

## Spec 001

| Doc | Description |
|---|---|
| [spec.md](../specs/001-faustcoder/spec.md) | Canonical specification, version 0.3.11 |
| [plan.md](../specs/001-faustcoder/plan.md) | Implementation plan. Stack and layout come from spec §10 |
| [tasks.md](../specs/001-faustcoder/tasks.md) | Task list mirrored by [KANBAN.md](../KANBAN.md), including D3-H1, D3-H2 and D3-H2-C |
| [data-model.md](../specs/001-faustcoder/data-model.md) | Entities and fields from spec §3 and §8 |
| [research.md](../specs/001-faustcoder/research.md) | Training-path research behind ADR-0002: continued pretraining, SFT, then compiler-feedback RL |
| [contracts/README.md](../specs/001-faustcoder/contracts/README.md) | Index of the JSON Schemas for spec §3, §7 and §8 |
| [inference-api.md](../specs/001-faustcoder/contracts/inference-api.md) | Draft local inference API (R-010) for task T13 |
| [checklists/requirements.md](../specs/001-faustcoder/checklists/requirements.md) | Requirements checklist against the spec as it stood on 2026-10-16 |
| [checklists/state-machines.md](../specs/001-faustcoder/checklists/state-machines.md) | Checklist that spec §7.1–§7.4 list states, events and transitions |
| [constitution](../.specify/memory/constitution.md) | Repository constitution, version 1.0.0, ratified 2026-10-16 |

Schema copies and the note that `$id` still names the former FaustCoder repository are in [schemas/README.md](../schemas/README.md). The backlog is [KANBAN.md](../KANBAN.md). The changelog is [CHANGELOG.md](../CHANGELOG.md).

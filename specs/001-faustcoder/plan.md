# Implementation plan: FaustCoder (spec 001)

- Spec: [spec.md](spec.md)
- Constitution: [.specify/memory/constitution.md](../../.specify/memory/constitution.md)
- Status: DRAFT
- Date: 2026-10-16

This plan carries the spec forward. Stack and layout come from spec §10;
anything not stated there is labeled INFERRED.

## Summary

Build a compiler-verified Faust coding model in milestone order V0.1 to V1.0
(spec §12). V0.1 is infrastructure, contracts, provenance and baseline
evaluation, not a trained model (README). Training is LoRA-first on DGX Spark
(R-008), gated by measured baselines (R-007).

## Technical context

| Item | Value | Source |
|---|---|---|
| Language | Python | OBSERVED §10 |
| ML stack | PyTorch, Transformers, PEFT/TRL | OBSERVED §10 |
| DSP toolchain | Faust CLI, pinned version recorded in every CompilerReceipt | OBSERVED §10, R-005 |
| Testing | pytest; signal tests per §9 test classes | OBSERVED §9, §10 |
| Storage | Parquet datasets; content-addressed artifact store; immutable manifests authoritative | OBSERVED §3, §10 |
| Tracking | MLflow, tracking only | OBSERVED §10 |
| Isolation | OCI containers, no network, bounded CPU, memory and time | OBSERVED §10, §11 |
| Target hardware | NVIDIA DGX Spark, 128 GB unified memory, ARM64/Blackwell | OBSERVED header, §10 |
| Schema language | JSON Schema or Pydantic, with validation tests | OBSERVED §8 |
| Serving | Local model server with generate, repair, explain, optimize | OBSERVED R-010 |
| Performance goals | Not set until baseline (D-005); V0.2 aspiration >=90% compile@1 is provisional | OBSERVED §9 |

Unknowns: student model (D-002), sample rates and runtimes (D-003),
redistribution rights (D-004), quality gates (D-005), hosted teacher policy
(D-006). See [research.md](research.md).

## Constitution check

| Principle | How the plan satisfies it |
|---|---|
| I. Evidence over confidence | Candidate machine (spec §7.2) requires CompilerReceipt, DSPTestReceipt and independent review |
| II. Immutable, acyclic lineage | Artifact store rejects writes that mutate payloads or add cycles (T02) |
| III. Two graphs | DSP graph analysis lives in `faust/` as a derived artifact; compiler authoritative (T03, T04) |
| IV. Sealed evaluation | Split freeze before any training (T07 before T10); holdout access is not available to training code |
| V. Data rights first | Rights inventory (T05) gates normalization (T06); `.gitignore` and secret scanning block data and credentials |
| VI. Sandboxed execution | Compiler and test workers run in restricted containers (T03) |
| VII. Bounded loops | `max_repair_attempts` enforced by the candidate machine |
| VIII. Human-approved release | Release machine (spec §7.4) needs signed approval |

Gate: PASS. No principle violations planned.

## Project structure

Source layout (OBSERVED §10):

```text
corpus/      provenance and rights records
datasets/    transforms and split manifests
faust/       compiler harness and DSP graph analysis
eval/        signal tests and benchmarks
train/       DGX Spark configs and launchers
serve/       local inference API
schemas/     JSON Schema contracts (seeded from specs/001-faustcoder/contracts/)
receipts/    immutable evidence (local receipts are git-ignored)
docs/        architecture, runbooks, ADRs
specs/       versioned specifications
```

Spec artifacts:

```text
specs/001-faustcoder/
  spec.md         what and why, state machines (§7)
  plan.md         this file
  research.md     open decisions and options
  data-model.md   entities, fields, relationships, states
  contracts/      JSON Schemas and API contract
  checklists/     requirement and state-machine quality checks
  tasks.md        dependency-ordered tasks
```

## Architecture

1. **Artifact store** (T02): content-addressed by SHA-256; every record has the
   common envelope in [data-model.md](data-model.md). Writes are append-only.
   INFERRED: a local filesystem store is enough for V0.1.
2. **Compiler sandbox** (T03): runs the pinned Faust CLI in a container with no
   network and resource limits, and emits a CompilerReceipt.
3. **Signal harness** (T04): renders compiled DSP at fixed sample rate, block
   size and seed, and emits a DSPTestReceipt.
4. **Data pipeline** (T05 to T07): implements the dataset machine (spec §7.1).
5. **Baseline and training** (T08 to T10): implements the training machine
   (spec §7.3). Throughput and memory study (T09) precedes pinning the stack.
6. **Evaluation and decision** (T11, T12): paired comparisons with confidence
   intervals; DecisionRecord.
7. **Serving and IDE** (T13, T14): implements the candidate machine (spec §7.2)
   behind the API in [contracts/inference-api.md](contracts/inference-api.md).
8. **Release** (T15, T16): implements the release machine (spec §7.4).

State machines from spec §7 are the contract. Each machine gets one module that
owns its transition table and rejects the illegal transitions listed there.
(INFERRED.)

## Governing workflows

Copied from spec §16: anti-slop-code, production-systems,
google-developer-style, spec-kit; owners cloud agent, FORGE, SCRIBE, ADVERSARY.
CI reuses `.github/workflows/spec-check.yml` and the hygiene workflows.

## Complexity tracking

None.

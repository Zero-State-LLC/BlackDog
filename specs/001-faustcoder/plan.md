# Implementation plan: BlackDog (spec 001)

- Spec: [spec.md](spec.md)
- Constitution: [.specify/memory/constitution.md](../../.specify/memory/constitution.md)
- Status: DRAFT
- Date: 2026-10-16

This plan carries the spec forward. Stack and layout come from spec §10;
anything not stated there is labeled INFERRED.

## Summary

Build a compiler-verified Faust coding model in milestone order V0.1 to V1.0
(spec §12). V0.1 is infrastructure, contracts, provenance and baseline
evaluation, not a trained model (README). Training adapts an open base
code model in phases P0 to P3 (R-015, [ADR-0002](../../docs/adr/0002-training-path.md)),
with the method per phase in R-008 and the student chosen by the bake-off in R-007.

## Technical context

| Item | Value | Source |
|---|---|---|
| Language | Python | OBSERVED §10 |
| ML stack | PyTorch, Transformers, PEFT/TRL | OBSERVED §10 |
| DSP toolchain | libfaust wasm (faustwasm 0.19.0) primary; native Faust 2.88.0 cross-check; version recorded in every CompilerReceipt | OBSERVED §10, R-005 (amended 0.3.0, D-003r2) |
| Target lanes | Language, plugin (CLAP, VST3, LV2), embedded (Daisy, Teensy 4.x); FPGA spike only | ADR-0004 |
| Testing | pytest; signal tests per §9 test classes | OBSERVED §9, §10 |
| Storage | Parquet datasets; content-addressed artifact store; immutable manifests authoritative | OBSERVED §3, §10 |
| Tracking | JSONL digest manifest; MLflow optional until V0.3 | OBSERVED §10; amended A-06 |
| Isolation | OCI containers, no network, bounded CPU, memory and time | OBSERVED §10, §11 |
| Target hardware | NVIDIA DGX Spark, 128 GB unified memory, ARM64/Blackwell | OBSERVED header, §10 |
| Schema language | JSON Schema or Pydantic, with validation tests | OBSERVED §8 |
| Serving | Local model server with generate, repair, explain, optimize | OBSERVED R-010 |
| Performance goals | Not set until baseline (D-005); V0.2 aspiration >=90% compile@1 is provisional | OBSERVED §9 |

Unknowns: student model (D-002), quality gates (D-005), FPGA lowering path
(after the F0 spike, D-009). Runtimes resolved by D-003r2 and target classes by
ADR-0004 (Danny yes 2026-10-16 23:39 PT). Accepted 2026-10-16: sample rates 44.1 and 48 kHz (D-003), corpus
rights (D-004, ADR-0003). Teacher (D-006r2, 2026-10-16 22:25 PT): open-weight
`deepseek/deepseek-v4.1-flash` via OpenRouter with a per-run spend cap; Opus for
review and judging only. See [spec §18](spec.md#18-decision-log) and [research.md](research.md).

## Constitution check

| Principle | How the plan satisfies it |
|---|---|
| I. Evidence over confidence | Candidate machine (spec §7.2) requires CompilerReceipt, DSPTestReceipt and independent review |
| II. Immutable, acyclic lineage | Artifact store rejects writes that mutate payloads or add cycles (T02) |
| III. Two graphs | DSP graph views come from compiler outputs (`-json`, `-svg`); no custom parser (spec §4.2, 0.3.0) |
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
faust/       thin wrappers around faustwasm and the Faust CLI
targets/     one container recipe and checker per lane (ADR-0004)
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
  research.md     training-path research, base-model shortlist, open decisions
  data-model.md   entities, fields, relationships, states
  contracts/      JSON Schemas and API contract
  checklists/     requirement and state-machine quality checks
  tasks.md        dependency-ordered tasks
```

## Architecture

1. **Artifact store** (T02): content-addressed by SHA-256; every record has the
   common envelope in [data-model.md](data-model.md). Writes are append-only.
   INFERRED: a local filesystem store is enough for V0.1.
2. **Compiler sandbox** (T03): runs libfaust from faustwasm in a Node.js worker
   with no network and resource limits, cross-checks with the native Faust
   2.88.0 CLI, and emits a CompilerReceipt with classified diagnostics.
   The R-005 reward ladder is amended 0.3.4 (ADR-0006, A1–A7); reward code
   keeps ADR-0005 behavior until the grader PR lands.
3. **Signal harness** (T04): renders with faustwasm at fixed sample rate, block
   size and seed, compares against stored references in the style of Faust's
   impulse tests, and emits a DSPTestReceipt. INFERRED: metric numbers live in
   the open `metrics` object (1e-9 grid, NaN/Inf/denormal counts, spectral
   bands, coarse block RMS and band energies). The head is an exact compare;
   the render follows an impulse tail up to 144000 frames. CPU wall time is
   recorded only for a promotion candidate and is not a reward term.
4. **Target lanes** (T17 to T22, ADR-0004): language, plugin and embedded
   lanes in pinned containers emit TargetReceipts; the FPGA F0 spike decides
   the FPGA path.
5. **Data pipeline** (T05 to T07): implements the dataset machine (spec §7.1).
6. **Baseline and training** (T08 to T10): implements the training machine
   (spec §7.3). Throughput and memory study (T09) precedes pinning the stack.
7. **Evaluation and decision** (T11, T12): paired comparisons with confidence
   intervals; DecisionRecord.
8. **Serving and IDE** (T13, T14): implements the candidate machine (spec §7.2)
   behind the API in [contracts/inference-api.md](contracts/inference-api.md).
9. **Release** (T15, T16): implements the release machine (spec §7.4).

State machines from spec §7 are the contract. Each machine gets one module that
owns its transition table and rejects the illegal transitions listed there.
(INFERRED.)

## Governing workflows

Copied from spec §16: anti-slop-code, production-systems,
google-developer-style, spec-kit; owners cloud agent, FORGE, SCRIBE, ADVERSARY.
CI reuses `.github/workflows/spec-check.yml` and the hygiene workflows.

## Complexity tracking

None.

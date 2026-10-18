# BlackDog: DAG-Compliant DSP Coding Model

Formerly FaustCoder; renamed 2026-10-17 PT.

- Status: DRAFT / refinement-ready
- Version: 0.3.6 (FLOOR bounds ratified, Danny 2026-10-18 12:34 AM PT; see §25). 0.3.5 (Jev Q1–Q4, 2026-10-17 7:40 PM PT; Danny "use jev to make decisions" 7:37 PM PT; see §24). 0.3.4 (ADR-0006 reward ladder, Danny 2026-10-17 4:11 PM PT, A2 extended 4:28 PM PT; see §23). 0.3.3: D-013 rights defaults, Danny yes 2026-10-17 1:04 PM PT; see §22. 0.3.2: CompilerReceipt diagnostic classes, ADR-0005, Danny yes 2026-10-17 1:13 PM PT; see §21. 0.3.1: R-001 v0.2 evidence, Danny yes 2026-10-17 12:54 PM PT; see §20. 0.3.0: Faust-tooling assimilation and target lanes, ADR-0004; see §19. 0.2.0 training path: ADR-0002, §17
- Target: NVIDIA DGX Spark (128 GB unified memory)

## 1. Constitution

BlackDog is a locally deployable model specialized in generating, repairing, explaining and optimizing Faust DSP programs. Correctness is evidence-based, not inferred from model confidence. No candidate may be promoted without independent compiler and signal-behavior evaluation. Preserve dataset licensing, reproducibility and explicit human approval for release. Do not treat a successful compilation as proof of audio correctness.

## 2. Scope

In scope: Faust source generation, repair, DSP design, optimization, documentation, benchmark harness, dataset pipeline, model adapters, local serving and IDE-facing API.

Out of scope (v1): general-purpose coding, autonomous plugin publishing, unrestricted internet ingestion, production audio mastering and claims of formal DSP verification.

Target classes (ADD 0.3.0, ADR-0004, Danny yes 2026-10-16 23:39 PT): the model writes Faust; Faust's own backends and `faust2*` scripts lower it to each target, and a verification lane per target class checks the result.

| Target class | Lane | First targets | Milestone |
|---|---|---|---|
| Host | wasm render (primary), native C++ cross-check | libfaust wasm, `-lang cpp` | V0.1 |
| Language backends | Compile the generated code in that language | `cpp`, `c`, `rust`, `cmajor` first | V0.3 |
| Plugins | `faust2*` build in a container, format validator, parameter-map check | CLAP, VST3, LV2 (Linux); AU deferred to macOS CI | V0.3 |
| Embedded | Per-board cross-compile, resource budget, real-time safety | Daisy, Teensy 4.x (D-008) | V0.3 |
| FPGA | Spike first; vendor-neutral Verilog via open toolchain | iCE40, ECP5 (D-009) | V0.5-FPGA |

Plugin distribution, code signing, notarization and store submission stay out of scope.

## 3. Domain model

Entities: SourceRecord, RightsRecord, Example, DatasetSnapshot, SplitManifest, TaskSpec, CandidateProgram, CompilerReceipt, DSPTestReceipt, BenchmarkSuite, BaseModel, Adapter, TrainingRun, EvaluationRun, DecisionRecord, ReleaseManifest.

All durable entities have schema_version, artifact_id, content_digest, created_at, producer, parents and immutable payload. Store lineage in a content-addressed artifact graph; model names and mutable aliases are not evidence.

## 4. Two DAGs

### 4.1 Evidence and execution DAG

source acquisition -> rights check -> normalization -> deduplication -> split freeze -> baseline -> training -> evaluation -> independent review -> release.

Each node references immutable parents. The graph must be acyclic; a new revision creates a new node, never rewrites ancestors. Invalidated ancestors invalidate dependent attestations until rerun. Execution orchestration may retry tasks, but retries create separate attempts and do not overwrite receipts.

### 4.2 DSP graph (REPLACED 0.3.0, ADR-0004 item 2)

The Faust compiler is the only parser. Graph and interface views come from its
own outputs: `-json` (UI, inputs, outputs, metadata), `-svg` block diagrams and
the compiler's signal-level output. BlackDog does not build its own Faust
parser or typed signal-flow model. Feedback legality is whatever the compiler
accepts; a program is never rejected because its raw signal graph has cycles.
The superseded 0.2.0 text (custom typed signal-flow representation) is kept in
§19 for history.

## 5. Requirements

- R-001 (MODIFIED 0.3.0; amended 0.3.1, Danny yes 2026-10-17 12:54 PM PT): Reproducible DGX Spark environment, pinned dependencies and hardware diagnostics. Toolchain pins follow the version set in ADR-0004 (Faust 2.88.0, a faustlibraries commit, faustwasm, target SDKs and validators); every receipt records the pin it used. For v0.2, cited external DGX Spark benchmarks plus a per-machine environment fingerprint receipt satisfy this requirement. On-hardware throughput measurements are deferred to T10, on the dedicated Spark cleared of other workloads before training.
- R-002 (MODIFIED 0.3.0, D-007; amended 0.3.3, D-013): Curated, license-traceable Faust corpus with source attribution and exclusion policy. License is resolved per function where a library file declares licenses per function, and per file otherwise; header-less example files inherit their repository's license. A `rights_cleared` transition also requires a notice row (path, blob id, copyright, license) for every cleared file or function, and an inferred clearance names a reviewer. Mixed licenses in one file take the strictest. Vendored copies are not cleared on their own.
- R-003: Contamination-resistant splits by project, near-duplicate family and provenance.
- R-004 (REPLACED 0.3.0): Task taxonomy has three axes: DSP category (the faustlibraries library split: oscillators, filters, envelopes, delays, reverbs, compressors and dynamics, noises, physical models, spatialization, analyzers, routing, misc effects and synths), task type (generate, repair, explain, optimize, remix) and target (host, language backend, plugin, embedded board, FPGA). Dev tasks are seeded from faustlibraries `#### Usage` blocks and tests; the sealed holdout is newly written (§9).
- R-005 (MODIFIED 0.3.0; amended 0.3.4, ADR-0006; amended 0.3.5, Q1): The compiler harness runs libfaust from faustwasm in a sandboxed worker as the primary compiler and the native Faust 2.88.0 CLI for cross-checks (D-003r2). Receipts record backend, Faust version, options, exit status, classified diagnostics and source digest. The reward ladder is: parse error < type or arity error < compiles with warnings < compiles clean. A1–A7 in [ADR-0006](../../docs/adr/0006-source-attributable-failures.md) and §23 amend that ladder. ADR-0006 is in force in reward code: `grade_receipt` implements A1–A7. Stored compiler classes stay the ADR-0005 enum. A7's 1%, 500-sample and 2× numbers are provisional. Amended 0.3.5 (Jev, Q1 and Q2, §24): the fenced Q1 ruling is normative. The R-005 ladder is a logged diagnostic only. A graded reward may enter only via the pre-registered binary-vs-ladder ablation. P3 reward is binary: 1.0 on full pass, 0.0 on every graded failure including A1's lowest rung. Ungraded samples get no value. Any GRPO group containing a quarantined member is dropped whole from the gradient update, not masked. Until A2-T leaves shadow mode, no receipt is auto-attributed to the source.
- R-006 (REPLACED 0.3.0): Signal tests render offline with faustwasm at fixed sample rate, block size and seed and compare against references in the style of Faust's impulse tests (`tests/impulse-tests`), plus finite-output, channel-count, silence, DC and clipping checks. CPU cost is measured only on promotion candidates and target lanes, not on every candidate.
- R-007 (amended 0.2.0, ADR-0002): Adapt an existing open base code model; never train from scratch. Baseline a 0.5B to 8B shortlist of Apache-2.0 base models (research.md) zero-shot and few-shot; choose the student by measured quality and Spark throughput, preferring the smallest model within the confidence interval of the best.
- R-008 (amended 0.2.0, ADR-0002): Method per phase: full-parameter continued pretraining for students up to about 4B, LoRA rank 64 to 256 (alpha = 2r) for SFT and for larger students. QLoRA is not needed at or below 8B on 128 GB.
- R-009: Immutable dataset/model/evaluation lineage and reproducible release manifest.
- R-010: Local inference API supports generate, repair, explain and optimize with structured responses.
- R-011: Independent evaluation cannot be satisfied by self-reported model judgments.
- R-012: Explicit abstention and bounded repair attempts; no unbounded compiler-agent loop.
- R-013 (MODIFIED 0.3.0): Security: sandboxed compiler and render workers (the wasm worker needs no host compiler or shell), containerized target toolchains with no network, resource limits, no arbitrary shell execution from generated code, and artifact integrity checks.
- R-014: Training/evaluation data governance includes license eligibility, attribution, retention and removal procedure.
- R-015 (amended 0.2.0, ADR-0002; amended 0.3.5, Q4): Phase-gated training path P0 corpus and evaluation harness, P1 continued pretraining (skipped by rule when the cleared corpus is too small), P2 SFT, P3 compiler-feedback RL. Each phase has a timebox and an exit gate defined in ADR-0002. Amended 0.3.5 (§24): ADR-0002 is accepted in full, which is Jev's default; Danny may still choose P3 PROPOSED. The P0 Spark throughput smoke test is replaced by R-001 0.3.1. P0 exits only with TOKEN_FLOOR accepted by the Q3 protocol or marked provisional with a recorded leakage caveat. The ~5M-token CPT-skip threshold is ratified as written. No other INFERRED number is ratified.
- R-016 (amended 0.2.0, ADR-0002; amended 0.3.5, Q1, A2-T): Synthetic training data and RL rewards come only from the sandboxed compiler and signal tests (R-005, R-006, R-011). Signal tests must reject silence, DC, NaN/Inf and trivial programs so rewards cannot be gamed. (0.3.0) Target-lane results (R-019 to R-024) may also be rewards once their lane is in place. Amended 0.3.5 (§24): P3's reward is the ADR-0006 grader with the Q1 binary ruling, whole-group drop of quarantined groups, and A2-T as the only auto-attribution path. The P3 exit gate requires the graded/ungraded split, the A7 quarantine rate and the group-drop rate within their pre-registered limits, and no frozen auto-attribution signature at exit.
- R-017 (ADD 0.3.0): SFT targets follow Faust house style: `import("stdfaust.lib");` and library prefixes (`os.`, `fi.`, `en.`), `declare` metadata (name, author, license, version), labeled UI primitives with units and ranges (`hslider`, `vslider`, `nentry`, `button`, `checkbox`, groups), and `process` as the entry point. A style check flags deviations; it is advisory, not a gate.
- R-018 (ADD 0.3.0): Upstream-validated pairs: faustlibraries `#### Usage` blocks and tests and the Faust examples become SFT pairs only after they compile and render in the harness. License follows R-002.
- R-019 (ADD 0.3.0, V0.3 gate, D-008): Embedded lane. A candidate for a board is reliable when it (1) builds with that board's `faust2*` script or SDK at the pinned version, (2) fits the board's flash and RAM budget from the linker map, (3) meets a CPU budget at the board's block size, measured in a cycle-accurate or host proxy until hardware exists, and (4) is real-time safe: no NaN/Inf or denormals in the render, no allocation in the audio callback, and memory placement declared with `-mem` where the board needs it. First boards: Daisy and Teensy 4.x.
- R-020 (ADD 0.3.0, V0.3 gate, D-010): Remix tasks combine techniques from two or more existing demos with one experimental idea. Correctness uses the normal gates; novelty (distance from the source demos in code and in rendered output features) is a dev metric, not a gate. faust-rs experimental primitives are out of scope.
- R-021 (ADD 0.3.0, V0.3 gate): Real-time safety checks apply on every target lane: finite output, no denormals (flush-to-zero honored), bounded delay-line memory and no allocation after init.
- R-022 (ADD 0.3.0, V0.5-FPGA, D-009): FPGA lane. Goal: synthesizable, pipelined Verilog for generic FPGAs. The model writes Faust; a vendor-neutral lowering produces Verilog. The path is chosen after the F0 spike (ADR-0004). Evidence: Verilator simulation matches the Faust reference render within a fixed-point tolerance, and Yosys plus nextpnr synthesize for iCE40 and ECP5 within resource limits. "Pipelined" means the design sustains one sample per channel at 48 kHz at the achieved clock.
- R-023 (ADD 0.3.0, D-012): Plugin lane. Build the candidate as a plugin in a container with the pinned `faust2*` script and SDK, run the format's validator (`clap-validator` for CLAP, `pluginval` for VST3, `lv2lint` for LV2; `auval` on macOS CI later) and check that every Faust UI parameter appears in the plugin with the same name, range, default and unit.
- R-024 (ADD 0.3.0): Language-backend lane. For a task targeting a language, generate code with `faust -lang <lang>` and compile it with that language's pinned toolchain; a run of the compiled code must match the host reference render. First languages: `cpp`, `c`, `rust`, `cmajor`.

## 6. User journeys

- J-01: Producer describes a synthesizer -> model generates Faust -> compile -> signal tests -> deliver source and evidence.
- J-02: Developer submits failing Faust -> diagnostics -> bounded repair -> recompile -> show diff and receipts.
- J-03: DSP engineer requests optimization -> baseline measurement -> candidate -> semantic and signal comparison -> performance report; reject unproven equivalence.
- J-04: Maintainer ingests new examples -> rights and dedup checks -> new snapshot -> frozen split -> benchmark comparison -> release decision.

## 7. Workflows and states

OBSERVED (original text, unchanged):

- Dataset: DISCOVERED -> RIGHTS_CLEARED -> NORMALIZED -> DEDUPED -> FROZEN; rejected items go to QUARANTINED.
- Candidate: DRAFT -> COMPILE_CHECKED -> SIGNAL_CHECKED -> REVIEWED -> ACCEPTED or REJECTED.
- Training: PLANNED -> ENV_VERIFIED -> RUNNING -> COMPLETED -> EVALUATED -> ADMITTED or REJECTED.
- Release: CANDIDATE -> EVIDENCE_COMPLETE -> APPROVED -> PUBLISHED -> DEPRECATED.
- All transitions emit append-only receipts with actor, timestamp, input hashes and disposition.

The state machines below make those lifecycles explicit. Each is derived from
§3, §4.1, §5, §6, §9, §11, §15 and ADR-0001. States, events, guards or effects
that the original text does not state are labeled **INFERRED**. Implementers
treat each transition table as the contract.

### 7.0 Rules common to every machine

- Every transition appends one receipt `{actor, timestamp, input_hashes, from, event, to, disposition}`. Receipts are never edited. (OBSERVED: §7.)
- A state change never mutates an artifact payload. Any change to content creates a new artifact node with the old one as a parent and the machine restarts at its initial state for the new node. (OBSERVED: §4.1, ADR-0001.)
- `upstream_invalidated`: when an ancestor is invalidated, attestations of dependants are invalid until rerun. (OBSERVED: §4.1.) Modeled as the INFERRED state `INVALIDATED` where it applies.
- A retry is a new attempt with its own receipt; it never overwrites the previous one. (OBSERVED: §4.1.)

### 7.1 Dataset item lifecycle

Subject: a `SourceRecord` or `Example` on its way into a `DatasetSnapshot`.

- Initial state: `DISCOVERED`.
- Final states: `FROZEN` (included in a frozen snapshot and split), `QUARANTINED` (excluded).
- States: `DISCOVERED`, `RIGHTS_CLEARED`, `NORMALIZED`, `DEDUPED`, `FROZEN`, `QUARANTINED`.
- Events: `rights_cleared`, `rights_rejected`, `normalized`, `normalize_failed` (INFERRED), `dedup_passed`, `duplicate_or_leak_found`, `split_frozen`.

| From | Event | Guard | To | Effect |
|---|---|---|---|---|
| DISCOVERED | rights_cleared | RightsRecord shows license eligibility, attribution, and a notice row (R-002, R-014, D-013) | RIGHTS_CLEARED | Write RightsRecord; append receipt |
| DISCOVERED | rights_rejected | License ineligible, unknown or restricted (R-014) | QUARANTINED | Write exclusion receipt with reason; content not copied into any snapshot |
| RIGHTS_CLEARED | normalized | Deterministic transform succeeded | NORMALIZED | Write normalized Example as new node, parent = source; append receipt |
| RIGHTS_CLEARED | normalize_failed | Transform error (INFERRED) | QUARANTINED | Append receipt with diagnostics (INFERRED) |
| NORMALIZED | dedup_passed | No exact or near-duplicate family conflict; not in holdout family (R-003) | DEDUPED | Record duplicate-family id; append receipt |
| NORMALIZED | duplicate_or_leak_found | Duplicate or holdout-contamination match (R-003) | QUARANTINED | Append exclusion receipt naming the conflicting family |
| DEDUPED | split_frozen | SplitManifest assigns the item by project, near-duplicate family and provenance (R-003) | FROZEN | Write DatasetSnapshot and signed SplitManifest digests (KANBAN T07); append receipt |

Illegal transitions:

- `DISCOVERED` -> `NORMALIZED`, `DEDUPED` or `FROZEN`: the rights check is never skipped (R-002, R-014).
- Any transition out of `FROZEN`: a frozen snapshot is immutable. A removal request (R-014) produces a new snapshot without the item, with the old snapshot as parent. (INFERRED.)
- `QUARANTINED` -> any state: re-admission needs a new `DISCOVERED` node with a new RightsRecord. (INFERRED.)
- A holdout item moving into a training or development split (§9).

```mermaid
stateDiagram-v2
    [*] --> DISCOVERED
    DISCOVERED --> RIGHTS_CLEARED: rights_cleared
    DISCOVERED --> QUARANTINED: rights_rejected
    RIGHTS_CLEARED --> NORMALIZED: normalized
    RIGHTS_CLEARED --> QUARANTINED: normalize_failed (INFERRED)
    NORMALIZED --> DEDUPED: dedup_passed
    NORMALIZED --> QUARANTINED: duplicate_or_leak_found
    DEDUPED --> FROZEN: split_frozen
    FROZEN --> [*]
    QUARANTINED --> [*]
```

### 7.2 Candidate program lifecycle

Subject: a `CandidateProgram` produced for a `TaskSpec` (J-01), a repair request (J-02) or an optimization request (J-03).

- Initial state: `DRAFT`.
- Final states: `ACCEPTED`, `REJECTED`.
- States: `DRAFT`, `COMPILE_CHECKED`, `SIGNAL_CHECKED`, `TARGET_CHECKED` (ADD 0.3.0, ADR-0004), `REVIEWED`, `ACCEPTED`, `REJECTED`, `REPAIRING` (INFERRED from J-02 and R-012).
- Events: `compile_passed`, `compile_failed`, `repair_produced` (INFERRED), `abstain` (R-012), `signal_passed`, `signal_failed`, `lanes_passed`, `lane_failed` (ADD 0.3.0), `review_recorded`, `accept`, `reject`.
- Lanes (ADD 0.3.0): the TaskSpec `target` names zero or more lanes (R-019, R-022 to R-024). A host-only task has no lanes and passes `lanes_passed` with an empty TargetReceipt set.
- Context: `repair_attempts` (count), `max_repair_attempts` (declared bound, value open: INFERRED, see D-005).

| From | Event | Guard | To | Effect |
|---|---|---|---|---|
| DRAFT | compile_passed | Sandboxed pinned compiler exit code 0 (R-005, R-013) | COMPILE_CHECKED | Write CompilerReceipt |
| DRAFT | compile_failed | `repair_attempts < max_repair_attempts` | REPAIRING | Write CompilerReceipt with diagnostics; increment `repair_attempts` |
| DRAFT | compile_failed | `repair_attempts >= max_repair_attempts` | REJECTED | Write CompilerReceipt; record abstention disposition (R-012) |
| DRAFT | abstain | Model or policy declines (R-012) | REJECTED | Record abstention disposition |
| REPAIRING | repair_produced | Repair output is a new CandidateProgram whose parent is the failed one (INFERRED) | DRAFT | New node; diff recorded for J-02 (INFERRED) |
| REPAIRING | abstain | Repair declined or produced no change (INFERRED) | REJECTED | Record abstention disposition |
| COMPILE_CHECKED | signal_passed | All signal tests in the TaskSpec `test_profile` pass: reference comparison, finite output, channel count, silence, DC and clipping (R-006, amended 0.3.0) | SIGNAL_CHECKED | Write DSPTestReceipt |
| COMPILE_CHECKED | signal_failed | Any required signal test fails | REJECTED | Write DSPTestReceipt with failing metrics |
| SIGNAL_CHECKED | lanes_passed | Every lane the TaskSpec `target` names passes (R-019, R-021 to R-024); none named for host-only tasks (ADD 0.3.0) | TARGET_CHECKED | Write one TargetReceipt per lane |
| SIGNAL_CHECKED | lane_failed | Any named lane fails (ADD 0.3.0) | REJECTED | Write the failing TargetReceipt |
| TARGET_CHECKED | review_recorded | Reviewer is independent of the generating model (R-011) | REVIEWED | Record review against gate results |
| REVIEWED | accept | All gates pass; for J-03, semantic and signal comparison against the baseline shows no regression and equivalence is evidenced | ACCEPTED | Write DecisionRecord (disposition = accepted) |
| REVIEWED | reject | Any gate fails, or J-03 equivalence is unproven | REJECTED | Write DecisionRecord (disposition = rejected, rationale) |

Illegal transitions:

- `DRAFT` -> `SIGNAL_CHECKED`, `REVIEWED` or `ACCEPTED`: signal tests and review need a successful compile.
- `COMPILE_CHECKED` -> `ACCEPTED`: compilation alone is never acceptance (§1, §9, ADR-0001).
- `SIGNAL_CHECKED` -> `REVIEWED` or `ACCEPTED`: target lanes come first, even when the set is empty (ADD 0.3.0).
- `SIGNAL_CHECKED` or `TARGET_CHECKED` -> `ACCEPTED` without `REVIEWED`.
- `review_recorded` or `accept` driven by the generating model's self-assessment (R-011).
- `compile_failed` -> `REPAIRING` when the bound is reached; no unbounded loop (R-012).
- Any transition out of `ACCEPTED` or `REJECTED`; a new attempt is a new node.
- Rejecting a program only because its raw signal graph contains legal, delayed feedback (§4.2, ADR-0001).

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> COMPILE_CHECKED: compile_passed
    DRAFT --> REPAIRING: compile_failed [attempts < max]
    DRAFT --> REJECTED: compile_failed [attempts >= max] / abstain
    REPAIRING --> DRAFT: repair_produced (new node)
    REPAIRING --> REJECTED: abstain
    COMPILE_CHECKED --> SIGNAL_CHECKED: signal_passed
    COMPILE_CHECKED --> REJECTED: signal_failed
    SIGNAL_CHECKED --> TARGET_CHECKED: lanes_passed
    SIGNAL_CHECKED --> REJECTED: lane_failed
    TARGET_CHECKED --> REVIEWED: review_recorded [independent]
    REVIEWED --> ACCEPTED: accept [all gates pass]
    REVIEWED --> REJECTED: reject
    ACCEPTED --> [*]
    REJECTED --> [*]
```

### 7.3 Training run lifecycle

Subject: a `TrainingRun` producing an `Adapter` or full weights (R-008), for one phase P1, P2 or P3 (R-015).

- Initial state: `PLANNED`.
- Final states: `ADMITTED`, `REJECTED`, `FAILED` (INFERRED), `INVALIDATED` (INFERRED).
- States: `PLANNED`, `ENV_VERIFIED`, `RUNNING`, `COMPLETED`, `EVALUATED`, `ADMITTED`, `REJECTED`, `FAILED` (INFERRED), `INVALIDATED` (INFERRED).
- Events: `env_verified`, `run_started`, `run_finished`, `run_failed` (INFERRED), `evaluation_recorded`, `admit`, `reject`, `upstream_invalidated` (INFERRED from §4.1).

| From | Event | Guard | To | Effect |
|---|---|---|---|---|
| PLANNED | env_verified | Pinned dependencies and hardware diagnostics recorded on DGX Spark (R-001) | ENV_VERIFIED | Record environment digest |
| ENV_VERIFIED | run_started | Dataset snapshot is `FROZEN`; split, config and code revision digests pinned (R-009) | RUNNING | Write TrainingRun with parents |
| RUNNING | run_finished | Training exited cleanly | COMPLETED | Record `checkpoint_digests` |
| RUNNING | run_failed | Crash, OOM or timeout (INFERRED) | FAILED | Append failure receipt; a retry is a new TrainingRun (§4.1) |
| COMPLETED | evaluation_recorded | Independent EvaluationRun on the development suite and sealed holdout (§9, R-011) | EVALUATED | Write EvaluationRun with paired comparison and confidence intervals |
| EVALUATED | admit | Gates met against the frozen baseline (D-005) | ADMITTED | Write DecisionRecord (admitted) |
| EVALUATED | reject | Gates not met | REJECTED | Write DecisionRecord (rejected) |
| COMPLETED, EVALUATED, ADMITTED | upstream_invalidated | An ancestor (dataset, split, base model, code) was invalidated | INVALIDATED | Mark dependent attestations invalid until rerun (INFERRED) |

Illegal transitions:

- `PLANNED` -> `RUNNING`: the environment is verified first (R-001).
- `run_started` on a dataset that is not `FROZEN`, or with any holdout item in the training data (§9).
- `COMPLETED` -> `ADMITTED`: admission needs an independent evaluation.
- Overwriting a failed run's receipts on retry (§4.1).
- Any transition out of `REJECTED`, `FAILED` or `INVALIDATED`.

```mermaid
stateDiagram-v2
    [*] --> PLANNED
    PLANNED --> ENV_VERIFIED: env_verified
    ENV_VERIFIED --> RUNNING: run_started [snapshot FROZEN]
    RUNNING --> COMPLETED: run_finished
    RUNNING --> FAILED: run_failed (INFERRED)
    COMPLETED --> EVALUATED: evaluation_recorded [independent]
    EVALUATED --> ADMITTED: admit [gates met]
    EVALUATED --> REJECTED: reject
    COMPLETED --> INVALIDATED: upstream_invalidated
    EVALUATED --> INVALIDATED: upstream_invalidated
    ADMITTED --> INVALIDATED: upstream_invalidated
    ADMITTED --> [*]
    REJECTED --> [*]
    FAILED --> [*]
    INVALIDATED --> [*]
```

### 7.4 Release lifecycle

Subject: a `ReleaseManifest`.

- Initial state: `CANDIDATE`.
- Final states: `DEPRECATED`, `WITHDRAWN` (INFERRED).
- States: `CANDIDATE`, `EVIDENCE_COMPLETE`, `APPROVED`, `PUBLISHED`, `DEPRECATED`, `WITHDRAWN` (INFERRED).
- Events: `evidence_assembled`, `approval_signed`, `approval_denied` (INFERRED), `publish`, `deprecate`, `rollback` (INFERRED from §15 rollback artifact).

| From | Event | Guard | To | Effect |
|---|---|---|---|---|
| CANDIDATE | evidence_assembled | Every §15 item present: immutable parent graph, rights-cleared dataset, frozen evaluation receipts, compiler and signal results, regression comparison, security review, model card, rollback artifact | EVIDENCE_COMPLETE | Write ReleaseManifest draft with all digests |
| EVIDENCE_COMPLETE | approval_signed | Independent human approver signs (§15, V1.0) | APPROVED | Record signed approval |
| EVIDENCE_COMPLETE | approval_denied | Approver declines (INFERRED) | WITHDRAWN | Record rationale |
| APPROVED | publish | Manifest signed; model card and data provenance statement attached (§11) | PUBLISHED | Publish signed release manifest |
| PUBLISHED | deprecate | Superseded or retired | DEPRECATED | Record deprecation notice |
| PUBLISHED | rollback | Post-release defect; rollback artifact verified (INFERRED) | DEPRECATED | Restore previous release from rollback artifact; record receipt |

Illegal transitions:

- `CANDIDATE` -> `APPROVED` or `PUBLISHED`: evidence first (§15).
- `EVIDENCE_COMPLETE` -> `PUBLISHED`: human approval is mandatory; autonomous publishing is out of scope (§2).
- `DEPRECATED` or `WITHDRAWN` -> any state; a re-release is a new ReleaseManifest.

```mermaid
stateDiagram-v2
    [*] --> CANDIDATE
    CANDIDATE --> EVIDENCE_COMPLETE: evidence_assembled [section 15 complete]
    EVIDENCE_COMPLETE --> APPROVED: approval_signed [independent human]
    EVIDENCE_COMPLETE --> WITHDRAWN: approval_denied (INFERRED)
    APPROVED --> PUBLISHED: publish
    PUBLISHED --> DEPRECATED: deprecate / rollback
    DEPRECATED --> [*]
    WITHDRAWN --> [*]
```

## 8. Contracts

### TaskSpec

`{task_id, task_type, prompt, constraints, expected_io, test_profile, schema_version}`

MODIFIED 0.3.0 (R-004): adds `category` (faustlibraries library name), `target` (lanes, R-019 to R-024) and, for `task_type = remix`, `remix_sources` (two or more demo digests).

### CompilerReceipt

`{source_sha256, faust_version, command, exit_code, stdout_digest, stderr_digest, duration_ms, environment_digest}`

MODIFIED 0.3.0 (R-005): adds `compiler` (`libfaust-wasm` or `faust-cli`), `lang` (output backend), `options` and `diagnostic_class` (`ok`, `warning`, `type_error`, `arity_error`, `parse_error`, `timeout`, `other`).

MODIFIED 0.3.2 (ADR-0005, Danny yes 2026-10-17 1:13 PM PT): `diagnostic_class` adds `unbound_symbol`, `resource_limit` and `internal`. Optional `termination_signal`, `runtime_stack_overflow` and `wasm_trap` record a worker signal, a RangeError whose message is exactly `Maximum call stack size exceeded`, and a wasm trap kind.

### DSPTestReceipt

`{source_sha256, test_suite_digest, sample_rate, block_size, seed, metrics, thresholds, passed, harness_digest}`

MODIFIED 0.3.0 (R-006): adds `renderer` (`faustwasm` or `native`) and `reference_digest`.

MODIFIED 0.3.4 (§23): `purpose` is `reward` or `diagnostic`. A reward receipt carries the canonical `profile` object. `test_suite_digest` is that object's digest. Diagnostic receipts are not rewards.

### TargetReceipt (ADD 0.3.0, ADR-0004)

`{source_sha256, target_class, target, toolchain_pins, build_command, exit_code, resource_report, validator, validator_version, validator_result, parameter_map_check, realtime_checks, passed, environment_digest}`

`target_class` is `language`, `plugin`, `embedded` or `fpga`. `resource_report` holds flash, RAM and CPU for boards, and LUT, FF, DSP, BRAM and Fmax for FPGAs.

### TrainingRun

`{run_id, base_model_revision, dataset_digest, split_digest, config_digest, code_revision, hardware_profile, checkpoint_digests, metrics}`

### DecisionRecord

`{candidate_digest, baseline_digest, suite_digest, gate_results, reviewer, disposition, rationale, timestamp}`

Schemas must be implemented in JSON Schema or Pydantic with validation tests before production use.

## 9. Evaluation

Metrics: compile@1, compile@k, task pass@1, DSP correctness pass rate, repair success, semantic regression rate, median/p95 generation latency, tokens/sec, peak memory, and test CPU cost.

Test classes: syntax, arity, routing, recursion/delay, deterministic numerical response, frequency response, envelope shape, NaN/Inf, clipping, silence, boundary inputs, and performance.

Frozen holdout is never used for training, prompt tuning or candidate selection. Use a separate development suite. (amended 0.2.0, ADR-0002): Estimate compile@k and pass@k with the unbiased estimator from n >= k samples. Holdout tasks are newly written, not mined from faustlibraries or faust examples, which base models have likely seen. Report confidence intervals for aggregate rates and paired comparisons against the baseline. Amended 0.3.5 (Q3, Q4, §24): a T07 freeze on the provisional floor records a leakage caveat and a scheduled re-check. Leaked items found later are removed and the removal is logged. No P3 exit claim may rest on the holdout until the holdout novelty re-check under the accepted floor has run.

Provisional V0.2 aspiration: >=90% compile@1 on held-out tasks, subject to baseline measurement and task-mix calibration. No release based on compilation alone.

Per-target metrics (ADD 0.3.0, ADR-0004): for each lane, target-build@k, validator pass rate, parameter-map pass rate and, for boards and FPGAs, fits-budget rate. Remix tasks also report novelty as a dev metric (D-010). Sample rates follow D-003 (44.1 and 48 kHz) for every lane that renders audio.

## 10. Architecture

`corpus/` provenance + rights; `datasets/` transforms and split manifests; `faust/` thin wrappers around libfaust (wasm) and the Faust CLI (MODIFIED 0.3.0: no custom graph analysis); `eval/` signal tests and benchmarks; `targets/` (ADD 0.3.0) one container recipe and checker per lane: language, plugin, embedded, fpga; `train/` Spark configs and launchers; `serve/` inference API; `schemas/` contracts; `receipts/` immutable evidence; `docs/` architecture, runbooks, decisions; `specs/` versioned specifications.

Recommended stack: Python, PyTorch, Transformers, PEFT/TRL, Faust CLI, faustwasm on Node.js (ADD 0.3.0), pytest, Parquet, MLflow (tracking only, immutable manifest authoritative), OCI containers, local model server. (amended 0.2.0, ADR-0002): until V0.3, a content-digested JSONL manifest is the artifact store and MLflow is optional. Verify ARM64/Blackwell compatibility on DGX Spark before pinning any training stack.

## 11. Security, privacy and governance

Execute compiler/test workers in restricted containers with no network, bounded CPU/RAM/time, read-only inputs and isolated output directories. Treat retrieved examples, prompts and generated code as untrusted. Prevent dataset poisoning, benchmark leakage and unauthorized copyrighted redistribution. Publish a model card and data provenance statement with every release.

## 12. Versioned roadmap and acceptance

- V0.1 FOUNDATION: environment lock, compiler harness (faustwasm worker plus native 2.88.0 cross-check, amended 0.3.0), schemas, corpus policy, frozen baseline suite. PASS when another operator can reproduce compiler receipts and baseline metrics from a clean checkout.
- V0.2 SPECIALIST (amended 0.2.0, ADR-0002): rights-cleared corpus, split freeze, base-model bake-off, P1 continued pretraining or recorded skip, P2 SFT. PASS when improvement is statistically supported on development tasks and holdout remains sealed.
- V0.3 DSP VERIFIER (amended 0.2.0, ADR-0002; 0.3.0, ADR-0004): P3 compiler-feedback RL, bounded repair, optimization comparisons, plus the language, plugin (CLAP, VST3, LV2) and embedded (Daisy, Teensy 4.x) lanes, real-time safety checks and remix tasks. PASS when known-bad DSP programs fail gates, legal delayed feedback passes, and each lane rejects its known-bad fixtures.
- V0.4 PRODUCT: local serving, API, IDE integration, telemetry and failure handling. (0.3.0: typed feedback graph semantics REMOVED; §4.2 uses compiler outputs.) PASS when end-to-end user journeys run on Spark with reproducible receipts.
- V0.5-FPGA (ADD 0.3.0, D-009): F0 spike only is scheduled: one filter and one oscillator lowered to Verilog through a vendor-neutral path, simulated in Verilator against the Faust render and synthesized with Yosys and nextpnr for iCE40 and ECP5. The full FPGA lane is planned only after the spike's DecisionRecord. Off the V1.0 critical path.
- V1.0 RELEASE: independent review, security assessment, model/data cards, immutable manifest, rollback procedure. PASS only with signed approval and complete evidence.

## 13. Dependency-ordered implementation tasks

T01 constitution + ADRs -> T02 schemas + artifact store -> T03 compiler sandbox (faustwasm worker, 0.3.0) -> T04 DSP test harness (wasm offline render, 0.3.0) -> T05 corpus rights inventory -> T06 normalization/dedup -> T07 split freeze -> T08 baseline models -> T09 Spark environment fingerprint (R-001, amended 0.3.1) -> T10 training path P1-P3 per ADR-0002 (amended 0.2.0) -> T11 evaluation and paired comparisons -> T12 decision gate -> T13 local serving -> T14 IDE integration -> T15 independent security/quality review -> T16 release.

Added 0.3.0 (ADR-0004): T17 language-backend lane (after T03, V0.3), T18 plugin lane (after T04, V0.3), T19 embedded lane (after T04, V0.3), T20 remix tasks and novelty metric (after T08, V0.3), T21 real-time safety checks (after T04, V0.3), T22 FPGA F0 spike (after T04, V0.5-FPGA). T17 to T19 and T22 run in parallel with T10.

Parallelism permitted only where declared dependencies allow it. Every task requires owner, inputs, outputs, acceptance test, failure disposition and evidence path.

## 14. Open decisions

- D-001: Confirm Faust DSP language (assumed).
- D-002 (amended 0.2.0, ADR-0002): Select student model after the P0 bake-off from the 0.5B to 8B Apache-2.0 shortlist in research.md. Larger models are teacher or reference candidates only (D-006).
- D-003 ACCEPTED, runtime part SUPERSEDED by D-003r2: Sample rates 44.1 kHz and 48 kHz. Signal tests and task suites run at both rates. Provenance: Danny yes 2026-10-16 22:20 PT. DSP target runtimes remain open (superseded).
- D-003r2 ACCEPTED: Runtimes. Evaluation runs on libfaust wasm (faustwasm); the native C++ backend from Faust 2.88.0 cross-checks it; target lanes (ADR-0004) verify other runtimes. Sample rates from D-003 stand. Provenance: Danny yes 2026-10-16 23:39 PT. Supersedes the runtime part of D-003.
- D-004 ACCEPTED: Training-corpus allowlist is MIT, BSD, Apache and other permissive licenses. GPL code is allowed for training only and is never redistributed in this repository or in released data. Unlicensed code is excluded. Provenance: Danny yes 2026-10-16 22:20 PT. See ADR-0003.
- D-005: Set quality gates using observed baseline and task severity.
- D-007 ACCEPTED: Licensing is per function where a library declares it and per file otherwise. Header-less example files inherit their repository's license; for the Faust repository that is LGPL, so they are training-only. AGPL stays excluded. Provenance: Danny yes 2026-10-16 23:39 PT. Refines D-004; see ADR-0003.
- D-008 ACCEPTED: First embedded boards are Daisy (Electrosmith, STM32H7) and Teensy 4.x (i.MX RT1062). No board purchase yet; lanes run on cross-compile, linker maps and host proxies. Provenance: Danny yes 2026-10-16 23:39 PT.
- D-009 ACCEPTED: The FPGA lowering path is decided after the F0 spike. Targets are iCE40 and ECP5 with the open toolchain. "Pipelined" means the design meets audio-rate throughput (one sample per channel per sample period at 48 kHz). Provenance: Danny yes 2026-10-16 23:39 PT.
- D-010 ACCEPTED: Remix novelty is a dev metric, not a gate. faust-rs experimental primitives are out of scope. Provenance: Danny yes 2026-10-16 23:39 PT.
- D-011 ACCEPTED: Fixes to the upstream Faust compiler or libraries may be contributed upstream under their LGPL license. Provenance: Danny yes 2026-10-16 23:39 PT.
- D-012 ACCEPTED: First plugin formats: CLAP (`faust2clap`) and VST3, both built on Linux in a container, plus LV2 (`faust2lv2`) on Linux. AU is deferred to a macOS CI runner. VST3 is built from the CLAP build with `clap-wrapper` (MIT) by default; `faust2juce` is the fallback and needs a JUCE license decision first, because JUCE is AGPLv3 or commercial (ADR-0004, INFERRED choice within Danny's "JUCE or native scripts"). Provenance: Danny yes 2026-10-16 23:39 PT.
- D-013 ACCEPTED: Rights defaults for the T05 inventory. STK-4.3 is other-permissive and clears with a notice. Bare BSD may train and eval and may not be redistributed. A notice manifest is required before `rights_cleared`. Vendored copies are rejected as sources and deduped by content hash to the upstream pin. faustlibraries is cleared per function: a declare wins, else the section header, else reject. Mixed-license files take the strictest license. Ungranted CCA4I "TODO: if/when Romain agrees" comments are stripped from cleared slices. GPL and LGPL stay training-only, and generated Faust must pass a near-duplicate filter against that set (proposed for T06/T07; the threshold is not set). Header-less means no license or copyright in the leading comment and no prefixed `declare` of license or copyright. An inferred clearance needs a named reviewer. Impulse tests are training only and cannot enter eval or holdout. Provenance: Danny yes 2026-10-17 1:04 PM PT ("get us where we need to go however you gotta do it"). Refines D-004 and D-007. See ADR-0003 and §21.
- D-006 SUPERSEDED by D-006r2 (Danny yes 2026-10-16 22:25 PT). Original: Teacher model is Opus via OpenRouter, with a per-run spend cap approved for each run before it starts. Provenance: Danny yes 2026-10-16 22:20 PT. See ADR-0002.
- D-006r2 ACCEPTED: Training-data teacher is an open-weight model: default `deepseek/deepseek-v4.1-flash` (DeepSeek-V4.1-Flash, MIT license) via OpenRouter with high reasoning effort, under a per-run spend cap approved for each run. Opus via OpenRouter is used only for review, grading and eval judging, never as a source of training targets, because Anthropic's usage terms restrict using outputs to train competing models. Provenance: Danny yes 2026-10-16 22:25 PT. Supersedes D-006. See ADR-0002 and ADR-0003.

## 15. Non-negotiable release gate

No model release without: immutable parent graph, rights-cleared dataset, frozen evaluation receipts, compiler and signal test results, regression comparison, security review, model card, rollback artifact and independent approval.

## 16. Governing workflows

INFERRED: added for Spec Kit compliance. The skills and CI files below govern
this spec; plan, tasks and agent briefs copy this list rather than inventing
another.

| Workflow | Applies to | Owner |
|---|---|---|
| anti-slop-code | All product code (harness, pipeline, eval, serve) | Cloud agent implements |
| production-systems | Sandboxed workers, artifact store, serving, release | Cloud agent implements; FORGE decomposes |
| google-developer-style | All docs, specs, ADRs, model and data cards | SCRIBE |
| spec-kit | Constitution, spec, plan, tasks, state machines | FORGE |
| Threat model (R-013, §11) | Sandbox, dataset poisoning, benchmark leakage | ADVERSARY |

CI workflows (`.github/workflows/`): `spec-check.yml` (required docs and Spec
Kit structure) is the existing path. Repository hygiene adds lint, link-check,
secret-scan and actionlint workflows; implementation tasks reuse those rather
than adding new CI paths.

## 17. Amendments 0.2.0 (ADR-0002, PROPOSED)

Acceptance of ADR-0002, and the 2026-10-17 7:40 PM PT rulings, are §24. This section is the 0.2.0 proposal as written.

Owner brief (OBSERVED): FaustCoder is a small specialist; build it by adapting
an open base code model (continued pretraining, SFT, compiler-feedback RL),
never from scratch, in weeks rather than months. Evidence is in
[research.md](research.md).

| ID | Change | Was | Label | Reason |
|---|---|---|---|---|
| A-01 | R-007 and D-002: 0.5B to 8B Apache-2.0 shortlist, adapt only | 7B/14B dense plus larger reference; Qwen3-14B vs 30B MoE | INFERRED | Small-model goal (OBSERVED brief); fine-tuning gains shrink with size on scarce data (research F3) |
| A-02 | R-008: full-parameter CPT up to about 4B; LoRA for SFT and larger models; no QLoRA | LoRA-first; QLoRA contingent | INFERRED | LoRA underperforms in CPT (research F4); 128 GB fits full fine-tuning of small models |
| A-03 | R-015: phases P0 to P3 with timeboxes and exit gates | Single T10 "training configs" | INFERRED | Gives a fast, auditable path (ADR-0002) |
| A-04 | R-016: compiler and signal tests are the only validators and rewards | Implied by R-005, R-006, R-011 | INFERRED | Validated synthetic data drives low-resource gains (research F1) |
| A-05 | §9: unbiased pass@k; newly written holdout | Not specified | INFERRED | Base models have likely seen public Faust code (research I6) |
| A-06 | §10: JSONL digest manifest; MLflow optional until V0.3 | MLflow plus full artifact store | INFERRED | Same immutability guarantees, less setup |
| A-07 | §12: V0.2 = P1 and P2; V0.3 = P3; typed graph semantics to V0.4 | V0.2 7B/14B LoRA; V0.3 graph semantics | INFERRED | Removes non-blocking work from the critical path |
| A-08 | §7.3 TrainingRun covers P1, P2 and P3 | Adapter only | INFERRED | Full-parameter CPT produces weights, not an adapter |

### Items that slow the path (flagged, not yet changed)

| # | Item in the current spec | Effect | Recommendation | Label |
|---|---|---|---|---|
| S-1 | §4.2 typed signal-flow DAG analysis | Large compiler-analysis effort; not needed for compile and signal-test rewards | Defer to V0.4 (A-07) | INFERRED |
| S-2 | §7.2 human `REVIEWED` step per candidate | Impossible at RL and synthetic-data volume | In training and evaluation loops, use automated independent gates (R-011); human review at promotion only | INFERRED |
| S-3 | R-010 four API verbs and V0.4 IDE integration | Product scope before the model is proven | Keep after P3; T13 and T14 stay off the critical path | INFERRED |
| S-4 | R-006 latency and CPU checks on every candidate | Slows data validation | Run on promotion candidates only | INFERRED |
| S-5 | D-003, D-004, D-006 open (resolved 2026-10-16: ACCEPTED in §14, ADR-0002, ADR-0003) | Block corpus clearing, harness and synthetic data | Defaults: 48 kHz, C++ backend; training-only use with a permissive allowlist; local Apache-2.0 teacher. Owner to confirm | INFERRED; not legal advice |
| S-6 | T09 as a full study | Delays T10 | One-day smoke test that records throughput and memory receipts | INFERRED |

## 18. Decision log

| ID | Decision | Status | Provenance | Record |
|---|---|---|---|---|
| LIC-001 | Split license: Apache-2.0 for `specs/` and `docs/` (including ADRs); Zero State Proprietary License 1.0 for code, model weights and data | ACCEPTED | Danny yes 2026-10-16 22:20 PT | ADR-0003, issue #20 |
| D-003 | Sample rates 44.1 kHz and 48 kHz (runtimes left open) | ACCEPTED; runtime part SUPERSEDED by D-003r2 | Danny yes 2026-10-16 22:20 PT | §14, ADR-0002 |
| D-004 | Permissive allowlist; GPL for training only, never redistributed; unlicensed excluded | ACCEPTED | Danny yes 2026-10-16 22:20 PT | ADR-0003 |
| D-006 | Teacher: Opus via OpenRouter; per-run spend cap approved per run | SUPERSEDED by D-006r2 | Danny yes 2026-10-16 22:20 PT | ADR-0002 |
| D-006r2 | Training-data teacher: open-weight `deepseek/deepseek-v4.1-flash` via OpenRouter, high reasoning, per-run spend cap. Opus only for review, grading and eval judging, never for training targets | ACCEPTED | Danny yes 2026-10-16 22:25 PT | ADR-0002, ADR-0003 |
| ORG-001 | Repository transferred to Zero-State-LLC (Danny yes 2026-10-16 22:25 PT). Visibility RESOLVED: public for now, revisitable later; applies to the repository and the org project board | ACCEPTED | Danny 2026-10-16 22:32 PT | KANBAN.md |
| ORG-002 | Project board moved to the org ([project 29](https://github.com/orgs/Zero-State-LLC/projects/29)), linked to this repository. User board scrimshawlife-ctrl #8 kept and marked superseded | ACCEPTED | Danny 2026-10-16 22:31 PT | KANBAN.md |
| D-003r2 | Runtimes: wasm (faustwasm) for evaluation, native C++ from Faust 2.88.0 for cross-checks, target lanes for the rest | ACCEPTED; supersedes D-003 runtime part | Danny yes 2026-10-16 23:39 PT | §14, ADR-0004 |
| D-007 | Per-function and per-file licensing; header-less example files inherit the repository license (Faust repo: LGPL, training-only); AGPL excluded | ACCEPTED; refines D-004 | Danny yes 2026-10-16 23:39 PT | ADR-0003 |
| D-008 | First boards Daisy and Teensy 4.x; no board purchase yet | ACCEPTED | Danny yes 2026-10-16 23:39 PT | ADR-0004 |
| D-009 | FPGA path chosen after the F0 spike; iCE40 and ECP5; pipelined = audio-rate throughput | ACCEPTED | Danny yes 2026-10-16 23:39 PT | ADR-0004 |
| D-010 | Remix novelty is a dev metric, not a gate; faust-rs experimental primitives out | ACCEPTED | Danny yes 2026-10-16 23:39 PT | ADR-0004 |
| D-011 | Upstream Faust compiler and library fixes under LGPL are allowed | ACCEPTED | Danny yes 2026-10-16 23:39 PT | ADR-0003 |
| D-012 | First plugin formats CLAP, VST3 (via clap-wrapper), LV2 on Linux; AU deferred to macOS CI | ACCEPTED | Danny yes 2026-10-16 23:39 PT | ADR-0004 |
| D-013 | STK-4.3 permissive with notice; bare BSD not redistributed; notice manifest required; vendored copies deduped and not cleared; per-function library slicing; strictest license wins; CC-TODO stripped; copyleft training-only plus a proposed near-duplicate output gate; header-less definition; inferred clearance needs a reviewer; impulse tests stay out of eval | ACCEPTED; refines D-004 and D-007 | Danny yes 2026-10-17 1:04 PM PT | ADR-0003, §22 |
| Q1 | Binary P3 reward, whole-group drop, R-005 ladder diagnostic only, binary-vs-ladder ablation. CONDITIONS in §24, including C1, per-checkpoint halt, and ladder-arm failure on a quarantine rise | ACCEPTED | Jev 2026-10-17 7:40 PM PT; Danny "use jev to make decisions" 7:37 PM PT | ADR-0006, §24 verbatim |
| Q2 | Auto-attribution only as A2-T after shadow. §23 rerun-plus-fixture path is not sanctioned. Below ~0.1% keeps auto-attribution off. Gold canary must be clean. L3 is rerun hooks for 124 and 125. A7-S 20% share, 2× rise, 500-sample window, provisional | ACCEPTED | Jev 2026-10-17 7:40 PM PT; Danny "use jev to make decisions" 7:37 PM PT | ADR-0006, §24 verbatim |
| Q3 | TOKEN_FLOOR stays 40 and provisional. Protocol after H2 (brief: canonical ID/NUM stream) and H3 (brief: NFKC and drop Cf/Cc). `lib.fn`, the 1/2 rule and the `STR` collapse are an ADVERSARY r6 addition; not ruled by Jev. Wilson CIs, Danny sets the numbers before the run, exact hash on the ID/NUM stream under 15 tokens with idioms allowlisted. T07 freeze needs a leakage caveat and a scheduled re-check | ACCEPTED; bounds ratified 2026-10-18 (§25); floor value still provisional | Jev 2026-10-17 7:40 PM PT; Danny "use jev to make decisions" 7:37 PM PT | ADR-0002, §24 verbatim |
| Q4 | ADR-0002 accepted in full (Jev's default; Danny may still choose P3 PROPOSED, the partial P0–P2 acceptance). P3 exit gates in §24. Only the ~5M-token CPT-skip threshold is ratified as written | ACCEPTED | Jev 2026-10-17 7:40 PM PT; Danny "use jev to make decisions" 7:37 PM PT | ADR-0002, §24 verbatim |

## 19. Amendments 0.3.0 (ADR-0004, ACCEPTED)

Owner brief (OBSERVED): assimilate the Faust reference
(<https://faust.grame.fr>) instead of stacking on the current design; add
reliable embedded code generation with remix tasks, synthesizable pipelined
Verilog for generic FPGAs, and plugin and language generators as target
classes. Approval: Danny yes 2026-10-16 23:39 PT ("apply the FaustCoder rework with the recommended
defaults"). Evidence: [research.md](research.md) F15 to F27.

Item numbers match the proposal Danny approved and ADR-0004.

| # | Type | Before | After | Where | Label |
|---|---|---|---|---|---|
| 1 | REPLACE | Pinned Faust CLI in a container is the compiler sandbox | libfaust wasm (faustwasm) worker is the primary compiler; native 2.88.0 CLI cross-checks | R-005, R-013, §12 V0.1, T03 | INFERRED design; OBSERVED tooling (F15) |
| 2 | REPLACE | Custom parser into a typed signal-flow representation (§4.2) | Compiler outputs (`-json`, `-svg`, signal output) are the graph views | §4.2, §10, V0.4 | INFERRED |
| 3 | REPLACE | Custom signal harness incl. CPU on every candidate | faustwasm offline render plus impulse-test-style references; CPU on promotion and lanes only | R-006, T04 | OBSERVED (F15, F16) |
| 4 | ADD | No embedded target | Embedded lane, V0.3 gate (Daisy, Teensy 4.x) | R-019, T19 | OBSERVED scripts (F19); INFERRED budgets |
| 5 | ADD | No remix tasks | Remix task type, V0.3 gate; novelty is a dev metric | R-004, R-020, T20 | INFERRED |
| 6 | MODIFY | Receipt: exit code and raw diagnostics | Classified diagnostics, compiler and backend fields; reward ladder | R-005, §8 | INFERRED |
| 7 | ADD | NaN/Inf only | Real-time safety checks on every lane, V0.3 gate | R-021, T21 | INFERRED |
| 8 | ADD | No FPGA target | V0.5-FPGA milestone; only the F0 spike scheduled | R-022, §12, T22 | OBSERVED backend state (F24, F25) |
| 9 | REPLACE | R-004 hand list of task kinds | Three axes: faustlibraries category x task type x target | R-004, §8 TaskSpec | OBSERVED library split (F17) |
| 10 | MODIFY | License per repository or file | Per function where declared, else per file; header-less files inherit the repo license | R-002, D-007, ADR-0003 | OBSERVED (F10, F18) |
| 11 | ADD | SFT pairs from usage blocks, unvalidated | Upstream pairs enter SFT only after compiling and rendering | R-018 | INFERRED |
| 12 | ADD | No style rules | Faust house style for SFT targets, advisory check | R-017 | OBSERVED conventions (F17) |
| 13 | ADD | "Pinned dependencies" | Explicit version pin set | R-001, ADR-0004 | OBSERVED versions (F26) |
| 14 | MODIFY | D-003 runtimes open | D-003r2 | §14 | OBSERVED (decision) |
| 15 | DEFERRED | T14 custom IDE integration | Reuse faustlsp or the Faust IDE; decide at V0.4 | — | INFERRED; not applied |
| 16 | DEFERRED | Custom CPU benchmarking | Reuse `faustbench` and `faust2bench`; decide when CPU gates are set | — | INFERRED; not applied |
| 17 | ADD | No plugin target | Plugin lane: CLAP, VST3, LV2; validators and parameter-map check | R-023, T18 | OBSERVED tooling (F20 to F23) |
| 18 | ADD | No language-backend target | Language lane: compile `-lang` output in that language | R-024, T17 | OBSERVED backends (F19) |
| 19 | MODIFY | Candidate machine: signal check then review | `TARGET_CHECKED` state between them | §7.2 | INFERRED |

Resolved from §17: S-1 (typed graph analysis) is removed by item 2; S-4
(CPU on every candidate) is resolved by item 3.

### Superseded text kept for history

§4.2 as of 0.2.0 (SUPERSEDED by item 2, Danny yes 2026-10-16 23:39 PT):

> Parse Faust programs into a typed signal-flow representation. Validate sequential, parallel, split, merge, and recursive composition against Faust's compiler semantics. Feedback is permitted only when semantically legal and appropriately delayed/stateful; never reject all recursive programs merely because their raw signal graph contains cycles. For DAG-based optimization and inspection, represent legal feedback as state-transition edges or collapsed strongly connected components with explicit delay boundaries. The graph view is a derived analysis artifact; the Faust compiler remains authoritative for language validity.

## 20. Amendments 0.3.1 (R-001, ACCEPTED)

Approval: Danny yes 2026-10-17 12:54 PM PT. Training runs on a dedicated DGX Spark that is cleared of other workloads before training (OBSERVED, Danny 2026-10-17). Cited benchmarks are in [the feasibility study](../../docs/dgx-spark-feasibility.md).

| ID | Change | Was | Label |
|---|---|---|---|
| A-09 | For v0.2, R-001 is satisfied by cited external DGX Spark benchmarks plus one environment-fingerprint receipt per machine. On-hardware throughput is T10, on that cleared Spark | T09 acceptance required ARM64/Blackwell throughput and memory receipts before T10 | OBSERVED (approval) |

This supersedes, for the v0.2 R-001 gate only, the §17 S-6 recommendation that T09 record throughput receipts before T10. S-6's row is left as written. The `env_verified` guard in §7.3 is unchanged: it still requires pinned dependencies and hardware diagnostics, not a token rate.

## 21. Amendments 0.3.2 (CompilerReceipt diagnostics, ACCEPTED)

Approval: Danny yes 2026-10-17 1:13 PM PT. This is the next spec version after 0.3.1 (§20). Decision: [ADR-0005](../../docs/adr/0005-compiler-diagnostic-classes.md).

| ID | Change | Was | Label |
|---|---|---|---|
| A-10 | CompilerReceipt `diagnostic_class` adds `unbound_symbol`, `resource_limit` and `internal` | Enum ended at `ok`, `warning`, `type_error`, `arity_error`, `parse_error`, `timeout`, `other` | OBSERVED (approval) |

## 22. Amendments 0.3.3 (D-013, ACCEPTED)

Approval: Danny yes 2026-10-17 1:04 PM PT ("get us where we need to go however you gotta do it"). Danny delegated the per-row rights calls. This section is the rights-policy amendment. It does not change R-001, §20, or §21.

| # | Default |
|---|---|
| 1 | STK-4.3 is other-permissive. The upstream-changes clause in `faustlibraries/licenses/stk-4.3.0.md` is not a binding provision. Clear with a notice that records the copyright and the STK text. |
| 2 | Bare "BSD" with no license text may be used for training and eval. It is not redistributed. The notice records the copyright string. |
| 3 | `rights_cleared` requires a notice row: path, blob id, copyright, and license, per file or per function. |
| 4 | Vendored copies (faustide, faustlive, faustwasm tests, faustgen-supercollider, pd-faustgen `mixer.dsp`) are not cleared on their own. Dedupe them by content hash to the upstream pin. |
| 5 | faustlibraries is sliced per function. `declare <fn> license` wins. Otherwise the section header applies. No header means reject. |
| 6 | A file that mixes licenses takes the strictest one. |
| 7 | Ungranted CCA4I comments ("TODO: if/when Romain agrees") are stripped from a cleared slice. Keeping the comment makes the slice training-only. |
| 8 | GPL and LGPL stay training-only (D-004, D-007). Generated `.dsp` must pass a near-duplicate filter against that set. The filter is a proposed T06/T07 requirement. The threshold is not set here. |
| 9 | Header-less means the leading comment has no license or copyright text, and the file has no `declare` of license or copyright under any prefix. |
| 10 | A clearance that rests only on inferred evidence needs a named human reviewer. Without one it stays unsigned. |
| 11 | Impulse tests are training only. The machine rejects eval and holdout for those paths. |

The inventory that applies these calls is [docs/rights-inventory.md](../../docs/rights-inventory.md). Boof, under this delegation, signed `faust-examples-headerless` and `faust-impulse-headerless` against observed license text at commit `8c00913e`. Those rows are training-only. Their attribution is incomplete, and the field stays false. `faust-examples-copyright-only` and `faustlibraries-attribution-gap` stay unsigned.

## 23. Amendments 0.3.4 (ADR-0006, ACCEPTED)

Approval: Danny 2026-10-17 4:11 PM PT. A2 extended 2026-10-17 4:28 PM PT. Decision: [ADR-0006](../../docs/adr/0006-source-attributable-failures.md). This amends the R-005 reward ladder. A1–A7 are that record. ADR-0006 is in force in reward code. `grade_receipt` (N4) mints a `RewardableSignalReceipt` only for an allowlisted reward profile, recomputes both digests, and drops every other sample from reward. A2 rows are retained in the quarantine queue. Auto-attribution reruns an unattributed exit 124, 125 or 126, or a worker or harness crash, on a quiet worker with the same digest and a known-good fixture. If the fixture passes and the candidate fails again, the rung is `parse_error`. An untagged exit 126 whose fixture also fails, or whose failure does not reproduce, stays `unattributed`. A remote import, a source over 1 MiB, a `runtime_stack_overflow` flag, a `wasm_trap` kind, or a line-start Faust `ERROR : stack overflow` on the compile stage that failed is already that rung. Harness prose is not a marker, and a compile warning does not attribute a later render crash. A7's 1%, 500-sample and 2× numbers are provisional starting values. The signal runbook records the reward-graded comparison.

A1. A failure the source caused gets the `parse_error` rung, the lowest graded rung. That covers: a remote import, library or component; recursion or any other stack overflow caused by the source; a timeout or resource kill the source ran into; any `CompilerExclusion` matched by model output; and any non-finite (NaN/Inf), silent, DC or trivial render in a reward-graded run. A timeout or resource kill counts as source-attributable only once triage attributes it to the source.

A2 (extended 2026-10-17 4:28 PM PT). The grader never penalizes the model for an error attributable to the evaluation environment or the harness. It distinguishes two such cases, and both are ungraded and quarantined for fixing: (a) a reproducible infrastructure failure, i.e. a worker crash or an `internal` receipt reproduced on a known-good fixture under the same harness and environment digest within the same batch; (b) a deterministic harness defect, i.e. the harness or environment, not the source, deterministically produces the error for a given input (for example a pre-filter false positive or a crash in harness code), as established by triage. Any receipt whose cause has not been attributed yet (an `internal` receipt, a timeout or resource kill with exit 124/125/126, or a worker or harness crash) is ungraded and quarantined until triage attributes it. It is graded under A1 only once it is attributed to the source.

A5. A grader accepts a receipt only when it carries `thresholds.reward_graded` and the canonical profile digest. `apply_signal` takes the receipt.

A3, A4, A6 and A7 are in ADR-0006 and are not restated here.

## 24. Amendments 0.3.5 (Jev Q1-Q4, ACCEPTED)

Jev output sha256 `d9a4632ed29786182ee61e67b7c3a6b1df92c8468f011b8e1331b54e794264df`, run 2026-10-17 7:40 PM PT, authorized by Danny's instruction "use jev to make decisions" (2026-10-17 7:37 PM PT). Record: [jev-output-2026-10-17.txt](../../docs/decisions/jev-output-2026-10-17.txt). The fenced blocks are the ruling, copied verbatim from that file. A paraphrase of them is non-normative. The application sentences restate gates from those blocks and do not loosen them. If an application sentence and a fenced block ever diverge, the fenced block wins. This record does not change code.

Decisions: the amendment at the end of [ADR-0006](../../docs/adr/0006-source-attributable-failures.md) (Q1, Q2) and the amendment at the end of [ADR-0002](../../docs/adr/0002-training-path.md) (Q1–Q4 verbatim, Q3 and Q4 application). Q4 accepts ADR-0002 in full. The sections above are not rewritten. The auto-attribution paragraph in §23 is the path Q2 replaces. It is not sanctioned, and it is not the description of accepted reward behavior.

### Q1 Jev ruling (verbatim)

```text
DECISION: MODIFIED: "P3 reward is binary: 1.0 on full pass, 0.0 on every graded failure including A1's lowest rung. Ungraded samples get no value. Any GRPO group containing a quarantined member is dropped whole from the gradient update, not masked. Its rows are held only for triage and receipts and never re-enter training later. Group-drop rate is tracked per prompt and overall with a halt threshold. The R-005 ladder is a logged diagnostic only, and R-005's wording is amended to say so. A graded reward may enter only via the pre-registered binary-vs-ladder ablation."
```

```text
CONDITIONS:
- C1 is preserved: no ungraded or quarantined row ever contributes a reward value or an advantage, including through group normalization.
- Log group-drop rate per checkpoint and per prompt. If the overall rate exceeds an agreed limit, pause P3 for triage instead of resampling indefinitely. Any prompt dropped repeatedly goes to human triage.
- Log the zero-variance (all-0 or all-1) group rate after SFT. The ε two-level variant is tested only through the ablation, and only if that rate approaches the brief's ~70% trigger.
- Pre-register the ablation's margin, seeds and dev metric before P3 starts. Treat any rise in quarantine or ungraded rate under the ladder arm as a failure of that arm.
- Amend R-005 in the same change set that records this ruling. This also clears ADR-0002 B1, together with Q4.
```

### Q1 application

Q1 CONDITIONS in the fenced block are binding. That includes C1 through group normalization; group-drop logged per checkpoint and per prompt; a halt that pauses P3 for triage instead of resampling indefinitely; human triage for a prompt dropped repeatedly; rows of a dropped group held only for triage and receipts; the zero-variance (all-0 or all-1) group rate logged after SFT; the ε two-level variant only through the ablation, and only if that rate approaches the brief's ~70% trigger; the ablation's margin, seeds and dev metric pre-registered before P3 starts; and any rise in quarantine or ungraded rate under the ladder arm as a failure of that arm.

OBSERVED: `reward_value` in `faustcoder/reward/grader.py` already returns 1.0 for a graded pass, 0.0 for a graded failure including an A1 source failure, and no value for an ungraded sample. This record does not change that function.

### Q2 Jev ruling (verbatim)

```text
DECISION: MODIFIED: "Auto-attribution under A2 is allowed only as A2-T, and only after a shadow period. A2-T requires all of the following:
- ≥2 reruns on a quiet worker reproducing the same crash signature;
- both the trivial and a path-matched known-good fixture passing;
- for stack, wasm_trap, timeout and other harness-limit signatures, a matching native Faust 2.88.0 failure (source-class list alone suffices only for inherently source-side signatures: line-start Faust ERROR, >1 MiB source, remote import);
- the signature not frozen by A7-S.

Every auto-attribution is stored with resolved_by=auto and its evidence. Anything else stays ungraded and quarantined."
```

```text
CONDITIONS:
- Shadow mode first: A2-T computes and logs attributions, but humans triage until A2-T agrees with them on an agreed sample and the gold canary is clean.
- If shadow data shows crash rows below ~0.1% of samples, keep auto-attribution off entirely, following the brief's own fallback.
- If native cross-check is unavailable in the loop, harness-limit signatures stay ungraded. The source-class-only fallback is narrowed to the inherently source-side signatures.
- Exit 124 is attributed only with a native or independent-runner timeout at the same limit, not on fixture evidence alone.
- Gold canary (dev-suite references, cleared-corpus sample, SFT targets) runs on a schedule. Any crash there freezes its signature.
- Land the r5 L1 fix (RangeError restricted to stack overflow), the L2 fix (line-start matching on the failing stage) and the L3 fix (rerun hooks for 124 and 125) before A2-T leaves shadow.
- A7-S thresholds (20% share, 2× rise, 500-sample window) are provisional. They are reviewed against shadow data before going live.
```

### Q2 application

Until A2-T leaves shadow mode, no receipt is auto-attributed to the source. The §23 rerun-plus-trivial-fixture path is not sanctioned by Q2 and must not be supplied (`rerun`/`known_good`) by any training caller. A `runtime_stack_overflow` flag or `wasm_trap` kind attributes to the source only with a matching native Faust 2.88.0 failure. Until then those rows are ungraded and quarantined. The source-class list alone suffices only for a line-start Faust `ERROR` other than `ERROR : stack overflow` (plain or `in eval`; see EVAL-SO), a source over 1 MiB, and a remote import. Shadow mode runs on a separate path that never grades: it may rerun and log attributions, but its output never reaches `reward_value` or a receipt. That path is not a training caller, so needing reruns in shadow does not conflict with A2-PATH. Code follow-up: A2-PATH.

A2-T requires all of: (1) at least 2 reruns on a quiet worker with matching environment digests reproducing the same crash signature; (2) both the trivial known-good fixture and a path-matched known-good fixture (same stage and limit) passing in that environment; (3) for stack, wasm_trap, timeout and every other harness-limit signature, a matching native Faust 2.88.0 failure. If that cross-check is unavailable, the row stays ungraded. (4) The signature is not frozen by A7-S. Exit 124 is attributed only with a native or independent-runner timeout at the same limit, never on fixture evidence alone. Anything else stays ungraded and quarantined.

A2-T leaves shadow only when all hold: L1–L3 have landed; A2-T agrees with human triage on a sample size and agreement level fixed before shadow starts; the scheduled gold canary (dev-suite references, cleared-corpus sample, SFT targets) is clean, and any crash there freezes its signature; the A7-S thresholds have been reviewed against shadow data; and Danny (or the delegated decision process) records the go-live. If shadow data shows crash rows below about 0.1% of samples, auto-attribution stays off entirely. That rate is a reason to stay off, never a reason to go live.

L3. Rerun hooks for exits 124 and 125 on the compile and render stages (r5 L3), feeding A2-T in shadow only.

L1 and L2 have landed in #49 (`f0fcdf9`), on main that also includes #46 (`42ee1e4`). L1 is the r5 fix Jev cited: a RangeError counts as stack overflow only when its message is exactly `Maximum call stack size exceeded`. L2 is the r5 fix Jev cited as line-start matching on the failing stage: `_compile_stack_line` splits on `\n` only. L3 has not landed.

A7-S thresholds (20% share, 2× rise, 500-sample window) are provisional. They are reviewed against shadow data before going live. These numbers are not A7's 1%, 500-sample and 2× ungraded-rate alarm.

After #46, the compiler stores a line that is exactly `ERROR : stack overflow in eval` as exit 126 `internal`. The grader's `_COMPILE_STACK_LINES` still tags that line as source, with no native check. EVAL-SO's acceptance is the A2-PATH requirement: the grader no longer tags either line as source without the Faust 2.88.0 native match. That covers `ERROR : stack overflow in eval` and the plain line-start `ERROR : stack overflow`.

### Q3 Jev ruling (verbatim)

```text
DECISION: MODIFIED: "TOKEN_FLOOR stays 40 and provisional. It is accepted or changed only by the measured protocol in Q3, extended as follows:
- the protocol uses the real slicer and real cleared hosts, with mutation operators that include H1-style splitting of one rejected file across 3+ cleared files;
- it reports per-bucket recall with Wilson CIs and hand-labelled FP cost;
- it runs after H2/H3 land;
- spans under 15 tokens remain checked by exact hash on the canonical stream, with their reject-class count reported.

The containment and allowlist preconditions are confirmed by ADVERSARY against the shipping slicer path, not only whole-file code. T07 does not freeze its split on the provisional floor without a recorded leakage caveat and a scheduled re-check."
```

```text
CONDITIONS:
- C2 is binding: no acceptance of 40, or any other value, until containment and allowlist-bypass fixes are confirmed on the slicing path and the measured analysis passes.
- Danny sets the acceptance numbers before the run: recall lower bound, zero reject-class copies left in cleared, and FP blob budget.
- If only the 20–39 bucket fails at 40, a function-unit-only lower floor is allowed. Whole files keep 40.
- Use SemDeDup-style semantic similarity only as an advisory T07 leakage signal, never as a clearance criterion.
- If T07 freezes on the provisional floor, holdout novelty is re-checked when the floor is accepted. Any leaked items are removed and the removal is logged.
```

### Q3 application

The protocol runs only after H2 and H3 land. H2 (brief: canonical ID/NUM shingle stream; ADVERSARY PR39 r6 adds: keep `lib.fn` qualified names, same 1/2 rule). H3 (brief: NFKC and drop Cf/Cc; ADVERSARY PR39 r6 adds: string literals collapse to one `STR` token on the canonical stream). The r6 additions are ADVERSARY recommendations, not Jev rulings. ADVERSARY r6 addition; not ruled by Jev: `lib.fn`, the 1/2 rule, the `STR` collapse, and the literal-insertion probe. The `STR` collapse applies only on the H2 canonical stream. That stream is an extra stream combined with the raw stream by OR and never replaces the raw stream. The shipped dedup must use the same streams the FLOOR protocol measures. Before the run, Danny sets the recall lower bound, requires zero reject-class copies left in cleared, and sets the FP blob budget. Recall is per bucket with Wilson intervals, with hand-labelled FP cost. Sub-15-token spans are exact-hash checked on the ID/NUM stream, and that check needs the brief's idioms allowlisted pairing, or short idioms will be over-flagged. A T07 freeze on the provisional floor records a leakage caveat and a scheduled re-check. Leaked items found later are removed and the removal is logged. SemDeDup-style similarity is advisory for T07 only and never a clearance criterion.

If only the 20–39 bucket fails at 40, a function-unit-only lower floor is allowed. Whole files keep 40.

### Q4 Jev ruling (verbatim)

```text
DECISION: MODIFIED: "Accept ADR-0002 with an amendment block that:
- (a) makes P3's reward the ADR-0006 grader with the Q1 binary ruling, whole-group drop of quarantined groups, and A2-T (Q2) as the only auto-attribution path;
- (b) replaces the P0 Spark throughput smoke test with R-001 0.3.1 (fingerprint receipt; throughput at T10);
- (c) requires P0 to exit with TOKEN_FLOOR either accepted by the Q3 protocol or marked provisional with a leakage caveat, and requires holdout novelty to be re-checked once the floor is accepted, before any P3 exit claim rests on the holdout;
- (d) adds graded/ungraded split, A7 quarantine and group-drop rates within limits, and no frozen auto-attribution signature at exit to the P3 audit;
- (e) defines compile@10 'does not drop beyond noise' and the 2-point general-code loss as paired-CI tests.

The ~5M-token CPT-skip threshold is ratified as written. Spec §17, the CHANGELOG and the P0 inline note are updated on acceptance."
```

```text
CONDITIONS:
- The amendment block cites the Q1–Q3 rulings verbatim so later readers cannot reinterpret them.
- If Danny prefers, P0–P2 may be accepted now with P3 marked PROPOSED pending A2-T leaving shadow mode. Both paths are acceptable.
- No ADR text may imply TOKEN_FLOOR is accepted (C2).
- P0 completion items (T07/T08, base-model shortlist) are not acceptance blockers but remain exit-gate items.
```

### Q4 application

Full acceptance of ADR-0002, including P3, is Jev's default; Danny may still choose P3 PROPOSED. Jev's Q4 CONDITIONS say that if Danny prefers, P0–P2 may be accepted now with P3 marked PROPOSED pending A2-T leaving shadow mode, and that both paths are acceptable. This record takes full acceptance.

P3's reward is the ADR-0006 grader with the Q1 binary ruling, whole-group drop of quarantined groups, and A2-T (Q2) as the only auto-attribution path. The P0 Spark throughput smoke test is replaced by R-001 0.3.1 (fingerprint receipt; throughput at T10).

The P3 exit gate also requires: the graded/ungraded split reported; the A7 quarantine rate and the group-drop rate within their pre-registered limits; and no frozen auto-attribution signature at exit. P0 exits only with `TOKEN_FLOOR` accepted by the Q3 protocol or marked provisional with a recorded leakage caveat. No P3 exit claim may rest on the holdout until the holdout novelty re-check under the accepted floor has run.

The ~5M-token threshold in the P1 skip rule is ratified as written. No other INFERRED number is ratified.

compile@10 "does not drop beyond noise" and the 2-point general-code loss are paired-CI tests.

## 25. Amendments 0.3.6 (FLOOR bounds, RATIFIED)

Approval: Danny 2026-10-18 12:34 AM PT. Exact words: "continue as recommended". He chose the 5% FP budget. Record: [danny-floor-bounds-2026-10-18.md](../../docs/decisions/danny-floor-bounds-2026-10-18.md). Constants: [`faustcoder/floor_protocol.py`](../../faustcoder/floor_protocol.py). This ratifies the acceptance bounds. It does not ratify a value for the length constant. The value stays 40 and provisional until the FLOOR run applies these bounds. This discharges the Q3 condition that the recall lower bound, the zero reject-class rule, and the FP blob budget are set before the run. The fenced Jev blocks in §24 are unchanged.

> FLOOR acceptance bounds (ratified by Danny 2026-10-18 12:34 AM PT, "continue as recommended", 5% FP budget):
>
> 1. Recall: in each of 8 gated cells, which are 4 buckets (15-19, 20-29, 30-39 and 40+ tokens) times verbatim on the raw stream and consistent rename on the canonical stream, the 95% Wilson lower bound must be at least 0.90. Other operators are reported, not gated.
> 2. n = 100 planted items per cell, from at least 50 distinct real reject-class span windows, each planted in 2 cleared hosts in different repos. That tolerates at most 4 misses per cell. Every planted miss is inspected, and a miss with a recurring mechanism blocks until fixed.
> 3. FP budget B = ceil(0.05 × N_cleared), which is 25 at N_cleared = 491. It counts hand-confirmed non-copy blobs (idiom, boilerplate, header, import, numeric table) added beyond the floor-40 set, after declare-stripping and the idioms allowlist. Label every candidate if a floor adds 100 or fewer. Otherwise use a seeded sample of at least 50 and require Wilson-upper(FP share) × added ≤ B.
> 4. At the chosen floor, three counts must be zero: detected reject-class matches left unquarantined in cleared, unresolved sub-15 exact-hash hits on the ID/NUM stream, and H1 split-file union-coverage hits at 1/2 or more.
> 5. Choose the highest TOKEN_FLOOR in {40, 30, 20} that passes 1, 3 and 4. If only the 20-29 and 30-39 cells fail at 40, use a function-unit-only lower floor, and whole files keep 40.
>
> TOKEN_FLOOR stays 40 and provisional until the FLOOR run applies these bounds.

The figure of at most 4 misses at n = 100 depends on a two-sided Wilson interval with z = 1.96 and no continuity correction.

Separate recorded rights ruling, not part of D6 and not Danny's ratified text: needs_human sources count as reject-class until a human clears them (fail closed). Boof (orchestrator), rights call under Danny's 2026-10-17 BlackDog rights/licensing delegation ([rights-inventory.md](../../docs/rights-inventory.md) lines 21-22), 2026-10-18 ~12:57 AM PT.

Open question for Danny, not a rule: whether a hit that shows up only when the floor is lowered is scored as a miss in a higher floor's recall cell. The ratified D6 cells govern until he decides.

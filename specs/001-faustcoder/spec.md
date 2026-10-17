# FaustCoder: DAG-Compliant DSP Coding Model

Status: DRAFT / refinement-ready
Version: 0.1.0
Target: NVIDIA DGX Spark (128 GB unified memory)

## 1. Constitution
FaustCoder is a locally deployable model specialized in generating, repairing, explaining and optimizing Faust DSP programs. Correctness is evidence-based, not inferred from model confidence. No candidate may be promoted without independent compiler and signal-behavior evaluation. Preserve dataset licensing, reproducibility and explicit human approval for release. Do not treat a successful compilation as proof of audio correctness.

## 2. Scope
In scope: Faust source generation, repair, DSP design, optimization, documentation, benchmark harness, dataset pipeline, model adapters, local serving and IDE-facing API.
Out of scope (v1): general-purpose coding, autonomous plugin publishing, unrestricted internet ingestion, production audio mastering and claims of formal DSP verification.

## 3. Domain model
Entities: SourceRecord, RightsRecord, Example, DatasetSnapshot, SplitManifest, TaskSpec, CandidateProgram, CompilerReceipt, DSPTestReceipt, BenchmarkSuite, BaseModel, Adapter, TrainingRun, EvaluationRun, DecisionRecord, ReleaseManifest.
All durable entities have schema_version, artifact_id, content_digest, created_at, producer, parents and immutable payload. Store lineage in a content-addressed artifact graph; model names and mutable aliases are not evidence.

## 4. Two DAGs
### 4.1 Evidence and execution DAG
source acquisition -> rights check -> normalization -> deduplication -> split freeze -> baseline -> training -> evaluation -> independent review -> release.
Each node references immutable parents. The graph must be acyclic; a new revision creates a new node, never rewrites ancestors. Invalidated ancestors invalidate dependent attestations until rerun. Execution orchestration may retry tasks, but retries create separate attempts and do not overwrite receipts.

### 4.2 DSP graph
Parse Faust programs into a typed signal-flow representation. Validate sequential, parallel, split, merge, and recursive composition against Faust's compiler semantics. Feedback is permitted only when semantically legal and appropriately delayed/stateful; never reject all recursive programs merely because their raw signal graph contains cycles. For DAG-based optimization and inspection, represent legal feedback as state-transition edges or collapsed strongly connected components with explicit delay boundaries. The graph view is a derived analysis artifact; the Faust compiler remains authoritative for language validity.

## 5. Requirements
R-001: Reproducible DGX Spark environment, pinned dependencies and hardware diagnostics.
R-002: Curated, license-traceable Faust corpus with source attribution and exclusion policy.
R-003: Contamination-resistant splits by project, near-duplicate family and provenance.
R-004: Frozen task suite including oscillators, filters, envelopes, routing, effects, modulation and stateful DSP.
R-005: Compiler harness records exact Faust version, flags, exit code, diagnostics and source digest.
R-006: Signal tests evaluate finite output, channel count, stability, spectral behavior, latency and CPU use where relevant.
R-007: Baseline at least one 7B/14B dense candidate and one larger reference model; choose student based on measured quality and Spark throughput.
R-008: LoRA-first training; QLoRA contingent on verified compatibility and throughput.
R-009: Immutable dataset/model/evaluation lineage and reproducible release manifest.
R-010: Local inference API supports generate, repair, explain and optimize with structured responses.
R-011: Independent evaluation cannot be satisfied by self-reported model judgments.
R-012: Explicit abstention and bounded repair attempts; no unbounded compiler-agent loop.
R-013: Security: sandbox compiler execution, resource limits, no arbitrary shell execution from generated code, and artifact integrity checks.
R-014: Training/evaluation data governance includes license eligibility, attribution, retention and removal procedure.

## 6. User journeys
J-01: Producer describes a synthesizer -> model generates Faust -> compile -> signal tests -> deliver source and evidence.
J-02: Developer submits failing Faust -> diagnostics -> bounded repair -> recompile -> show diff and receipts.
J-03: DSP engineer requests optimization -> baseline measurement -> candidate -> semantic and signal comparison -> performance report; reject unproven equivalence.
J-04: Maintainer ingests new examples -> rights and dedup checks -> new snapshot -> frozen split -> benchmark comparison -> release decision.

## 7. Workflows and states
Dataset: DISCOVERED -> RIGHTS_CLEARED -> NORMALIZED -> DEDUPED -> FROZEN; rejected items go to QUARANTINED.
Candidate: DRAFT -> COMPILE_CHECKED -> SIGNAL_CHECKED -> REVIEWED -> ACCEPTED or REJECTED.
Training: PLANNED -> ENV_VERIFIED -> RUNNING -> COMPLETED -> EVALUATED -> ADMITTED or REJECTED.
Release: CANDIDATE -> EVIDENCE_COMPLETE -> APPROVED -> PUBLISHED -> DEPRECATED.
All transitions emit append-only receipts with actor, timestamp, input hashes and disposition.

## 8. Contracts
### TaskSpec
`{task_id, task_type, prompt, constraints, expected_io, test_profile, schema_version}`
### CompilerReceipt
`{source_sha256, faust_version, command, exit_code, stdout_digest, stderr_digest, duration_ms, environment_digest}`
### DSPTestReceipt
`{source_sha256, test_suite_digest, sample_rate, block_size, seed, metrics, thresholds, passed, harness_digest}`
### TrainingRun
`{run_id, base_model_revision, dataset_digest, split_digest, config_digest, code_revision, hardware_profile, checkpoint_digests, metrics}`
### DecisionRecord
`{candidate_digest, baseline_digest, suite_digest, gate_results, reviewer, disposition, rationale, timestamp}`
Schemas must be implemented in JSON Schema or Pydantic with validation tests before production use.

## 9. Evaluation
Metrics: compile@1, compile@k, task pass@1, DSP correctness pass rate, repair success, semantic regression rate, median/p95 generation latency, tokens/sec, peak memory, and test CPU cost.
Test classes: syntax, arity, routing, recursion/delay, deterministic numerical response, frequency response, envelope shape, NaN/Inf, clipping, silence, boundary inputs, and performance.
Frozen holdout is never used for training, prompt tuning or candidate selection. Use a separate development suite. Report confidence intervals for aggregate rates and paired comparisons against the baseline.
Provisional V0.2 aspiration: >=90% compile@1 on held-out tasks, subject to baseline measurement and task-mix calibration. No release based on compilation alone.

## 10. Architecture
`corpus/` provenance + rights; `datasets/` transforms and split manifests; `faust/` compiler harness and graph analysis; `eval/` signal tests and benchmarks; `train/` Spark configs and launchers; `serve/` inference API; `schemas/` contracts; `receipts/` immutable evidence; `docs/` architecture, runbooks, decisions; `specs/` versioned specifications.
Recommended stack: Python, PyTorch, Transformers, PEFT/TRL, Faust CLI, pytest, Parquet, MLflow (tracking only, immutable manifest authoritative), OCI containers, local model server. Verify ARM64/Blackwell compatibility on DGX Spark before pinning any training stack.

## 11. Security, privacy and governance
Execute compiler/test workers in restricted containers with no network, bounded CPU/RAM/time, read-only inputs and isolated output directories. Treat retrieved examples, prompts and generated code as untrusted. Prevent dataset poisoning, benchmark leakage and unauthorized copyrighted redistribution. Publish a model card and data provenance statement with every release.

## 12. Versioned roadmap and acceptance
V0.1 FOUNDATION: environment lock, compiler harness, schemas, corpus policy, frozen baseline suite. PASS when another operator can reproduce compiler receipts and baseline metrics from a clean checkout.
V0.2 SPECIALIST: rights-cleared corpus, split freeze, 7B/14B benchmark, LoRA experiment. PASS when improvement is statistically supported on development tasks and holdout remains sealed.
V0.3 DSP VERIFIER: signal tests, feedback graph semantics, bounded repair, optimization comparisons. PASS when known-bad DSP programs fail gates and legal delayed feedback passes.
V0.4 PRODUCT: local serving, API, IDE integration, telemetry and failure handling. PASS when end-to-end user journeys run on Spark with reproducible receipts.
V1.0 RELEASE: independent review, security assessment, model/data cards, immutable manifest, rollback procedure. PASS only with signed approval and complete evidence.

## 13. Dependency-ordered implementation tasks
T01 constitution + ADRs -> T02 schemas + artifact store -> T03 compiler sandbox -> T04 DSP test harness -> T05 corpus rights inventory -> T06 normalization/dedup -> T07 split freeze -> T08 baseline models -> T09 Spark throughput/memory study -> T10 training configs -> T11 evaluation and paired comparisons -> T12 decision gate -> T13 local serving -> T14 IDE integration -> T15 independent security/quality review -> T16 release.
Parallelism permitted only where declared dependencies allow it. Every task requires owner, inputs, outputs, acceptance test, failure disposition and evidence path.

## 14. Open decisions
D-001: Confirm Faust DSP language (assumed).
D-002: Select student model after baseline: Qwen3-14B vs 7B or 30B MoE alternative.
D-003: Choose initial sample rates and DSP target runtimes.
D-004: Determine corpus redistribution versus training-only rights.
D-005: Set quality gates using observed baseline and task severity.
D-006: Decide local-only versus optional hosted teacher usage and data boundaries.

## 15. Non-negotiable release gate
No model release without: immutable parent graph, rights-cleared dataset, frozen evaluation receipts, compiler and signal test results, regression comparison, security review, model card, rollback artifact and independent approval.

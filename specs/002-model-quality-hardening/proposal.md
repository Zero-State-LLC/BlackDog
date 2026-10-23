# BlackDog Model-Quality Hardening Amendment (proposal)

Status: PROPOSED, non-normative until reviewed and accepted.
Scope: extends spec 001 and existing T04, T07–T14. Does not supersede ADR-0002, ADR-0004, ADR-0006, or the existing KANBAN. No training or promotion is authorized by this document.

## Purpose and constitution

Build a compact Faust coding model whose generated DSP is compiler-valid, behaviorally correct, reproducible, rights-cleared, and portable through Faust's own backends. Keep compiler/signal evidence authoritative, independent of LLM judges. Preserve immutable evidence DAG, rights gates, holdout isolation, human promotion, and explicit failure attribution.

## Gap classification

- VERIFIED: README reports T03b library staging and T04 signal harness are not complete; no model-quality claim; Spark throughput not measured.

- DOCUMENTED PENDING: T07 split freeze, T08 baseline, T10 training, T11 independent evaluation, T12 promotion; RL trust-boundary integration remains in backlog.

- PROPOSED EXTENSIONS, NOT VERIFIED BUGS: behavioral-invariant suites, retrieval baseline, detailed contamination certification, realistic on-device throughput, and semantic task-family reporting.

- AUDIT REQUIRED: source-to-contract traceability, CI execution, actual sandbox isolation, grader wiring, reward-signature verification, artifact invalidation, and end-to-end test execution.

## Journey -> workflow -> state transition -> contract -> acceptance test -> task

### J-Q1: Model candidate evaluation

User asks for a Faust program -> fixed prompt and generation policy -> sandbox compilation -> offline rendering at 44.1/48 kHz -> task-specific invariants -> native cross-check -> paired score -> human-reviewed decision.
States: PLANNED -> GENERATED -> COMPILED | COMPILATION_FAILED -> RENDERED | RENDER_FAILED -> BEHAVIOR_VERIFIED | BEHAVIOR_FAILED -> RECORDED. Infrastructure ambiguity transitions to QUARANTINED, never a model failure without ADR-0006 attribution.
Contracts: EvaluationTask(task_digest, rights_digest, family, prompt, expected_io, allowed_imports, sample_rates, parameter_cases, input_signals, invariant_spec, tolerance_policy); EvaluationReceipt(model_digest, task_digest, generation_config_digest, compiler_digest, library_digest, environment_digest, outcome, measurements, failure_class, parent_digests).
Acceptance: reproducible fixtures for oscillator frequency, filter cutoff/response, compressor threshold/ratio/envelope, delay/feedback stability, routing/channel count, and parameter extremes; deterministic impulse, sine, step, silence, noise; detect NaN/Inf, unintended silence/DC, trivial bypass, unbounded gain; known-bad fixtures fail. No generic signal tolerance substituted for task-specific numerical tolerance.

### J-Q2: Corpus and holdout admission

Rights-cleared source -> normalization -> raw and canonical shingles -> dedup and near-duplicate audit -> leakage report -> freeze.
States: INVENTORIED -> RIGHTS_CLEARED -> NORMALIZED -> DEDUP_AUDITED -> SPLIT_FROZEN or QUARANTINED.
Contracts: CorpusAdmissionReceipt(source_digest, license_decision, normalization_version, shingle_versions, near_duplicate_findings, human_disposition, split_digest, parent_digests).
Acceptance: execute the existing H2/H3/FLOOR requirements, including adversarial probes and measured false-positive cost; report cross-split overlap and leakage before T07, preserving the canonical provisional-floor route with a leakage caveat and scheduled recheck. Full FLOOR certification is required before P3 exit or promotion. No absent evidence treated as zero contamination.

### J-Q3: Student selection and training

Fixed base shortlist -> base and retrieval-augmented baseline -> paired evaluation -> optional P1 under ADR-0002 skip rule -> P2 verified SFT -> conditional P3.
States: BASELINED -> TRAINING_ELIGIBLE -> TRAINED -> EVALUATED -> ADMITTED | REJECTED | INVALIDATED.
Contracts: BaselineReceipt(base_revision, prompt_template_digest, retrieval_index_digest_or_null, decoding_policy, task_suite_digest, compiler_digest, paired_metrics, confidence_intervals); TrainingPerformanceReceipt(machine_fingerprint_digest, base_revision, optimizer, adapter_config, seq_len, batch, gradient_accumulation, token_count, tokens_per_second, peak_memory_bytes, checkpoint_recovery_result).
Acceptance: paired compile@1, functional pass@1, bounded repair success, task-family performance, inference latency, and general-code regression for base, retrieval and trained candidates; use fixed decoding budgets and pre-registered CIs. No model selected on holdout. Spark measurements at representative training sequence lengths before stack/model pinning. No fabricated rate from external benchmarks.

### J-Q4: Promotion

Independent suite execution -> provenance verification -> audit -> human decision.
States: EVALUATED -> PROMOTION_REVIEW -> ADMITTED | REJECTED; invalid ancestors -> INVALIDATED.
Contracts: PromotionDecisionRecord(candidate_digest, baseline_digest, suite_digest, per_family_metrics, paired_intervals, provenance_check, security_check, regression_check, human_approver, rationale).
Acceptance: pre-registered improvement over strongest eligible baseline, no unresolved reward/harness ambiguity, no leakage, no unapproved rights, and no missing provenance. Frozen holdout is used only under existing one-shot policy. A failure to demonstrate improvement is a valid rejection.

## Engineering audit checklist (read-only before changes)

1. Trace each spec requirement to implementation, tests, CI job, and evidence receipt; classify missing, partial, complete, or unverified.

2. Inspect faustwasm worker filesystem/import restrictions, process limits, timeouts, native parity, library staging, and malicious fixtures.

3. Check reward HMAC validation, grader identity, no quarantine-to-gradient path, whole-group GRPO drops, signature freezes, canary scheduling, and manual halt release.

4. Verify artifact content hashes, parent links, invalidation propagation, split freeze, source licensing, and accidental inclusion of weights or restricted data.

5. Execute existing unit, contract, integration, and adversarial suites on a clean checkout; distinguish skipped tests and unavailable hardware from passes.

6. Reconcile findings with KANBAN, tasks.md, ADRs, and CI without duplicating canonical requirements.

## Proposed implementation order

P0: T03b -> T04 plus semantic fixtures -> T06/FLOOR -> T07 -> T08 with retrieval baseline.
P1: T09 real Spark fingerprint -> representative T10 performance probe -> P2 SFT, preserving P1 skip rule.
P2: T11 paired functional evaluation -> T12 decision. P3 only when existing GD-1/A2/D3 gates are satisfied and an approved experiment warrants it.
P3: T13/T14 serving and IDE integration after admission, with repair-loop and diagnostic contracts.
Each task must specify owner, dependencies, executable acceptance tests, evidence digest, rollback, and a clear DONE definition.

## Non-goals

Do not train from scratch; do not generate native C++/Rust/plugin code directly; do not weaken licensing or quarantine gates; do not silently expand FPGA scope; do not treat compilation as functional success.

## External engineering references

Faust compiler: <https://faustdoc.grame.fr/manual/compiler/>
Faust LLM guidance: <https://faustdoc.grame.fr/manual/llm/>
Faust benchmark tooling: <https://github.com/grame-cncm/faust/blob/master-dev/tools/benchmark/README.md>
Faust library test conventions: <https://faustlibraries.grame.fr/contributing/>

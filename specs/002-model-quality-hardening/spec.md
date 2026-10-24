# Spec 002: Model-quality hardening

Status: PROPOSED. This extension does not supersede spec 001, ADR-0002, ADR-0004 or ADR-0006. No training or promotion is authorized.

## Constitution

Generated Faust must be compiler-valid, behaviorally correct, reproducible and rights-cleared. Compilation alone does not establish DSP correctness. Keep the existing immutable evidence DAG, conservative quarantine rules, sealed holdout and human promotion gate.

## Domain model

Reuse canonical TaskSpec, CandidateProgram, CompilerReceipt, DSPTestReceipt, EvaluationRun, TrainingRun and DecisionRecord. New reporting fields remain advisory until schema-reviewed and versioned. Do not introduce parallel durable entity types.

## Requirements

- QH-R01: Report task-family functional pass@1 independently of compile@1.
- QH-R02: Compare base, retrieval-assisted and SFT candidates on identical development tasks and decoding budgets.
- QH-R03: Certify split leakage using the accepted H2/H3/FLOOR shipping path before P3 exit or promotion. Preserve spec 001 R-015: T07 may use a provisional floor with a recorded leakage caveat and scheduled recheck; this proposal adds no stronger freeze prerequisite.
- QH-R04: Measure BlackDog throughput and peak memory on the dedicated DGX Spark before final student pinning.
- QH-R05: Bind production rewards to validated TaskSpec and sanctioned native evidence, without weakening ADR-0006.
- QH-R06: Preserve diagnostic-only nonlinear suite exclusion from REWARD_PROFILES.
- QH-R07: Produce independent evaluation and human DecisionRecord before promotion.

## Journeys

J-Q1: An engineer requests Faust DSP and receives generated source plus compiler and signal evidence.

J-Q2: A maintainer admits rights-cleared corpus items, checks near-duplicates and freezes splits.

J-Q3: A model developer compares baselines, runs gated training and receives reproducible measurements.

J-Q4: An independent reviewer accepts or rejects a model based on verified evidence.

## Workflows

- Generation: prompt -> candidate -> compile -> render -> task-specific behavioral checks -> record.
- Data: rights inventory -> normalize -> dedup -> contamination audit -> split freeze.
- Training: baseline -> optional CPT -> verified SFT -> conditional GRPO -> independent evaluation.
- Promotion: provenance checks -> paired comparison -> human review -> decision.

## State transitions

Use the canonical candidate, dataset and training state machines from spec 001. This proposal adds no state or transition. A future transition change requires its own accepted ADR and an updated transition table and diagram in spec 001.

## Contracts

Reuse the versioned canonical artifact envelope and existing contracts. Proposed additional fields are task_family, semantic_invariants, retrieval_index_digest, measured_tokens_per_second, peak_memory_bytes and per_family_metrics. No field becomes normative until schema validation and contract tests pass.

## Acceptance tests

- Oscillator, filter, dynamics, delay and routing fixtures include known-good and known-bad outputs.
- Test 44.1 and 48 kHz with task-specific numerical tolerances.
- Reject NaN/Inf, unintended silence/DC, trivial bypass and unstable feedback.
- Verify retrieval excludes holdout and rights-rejected material.
- Test reward refusal for malformed, mismatched and unrewardable tasks.
- Verify quarantined GRPO members drop their whole group.
- Require actual Spark performance receipts, not extrapolated benchmarks.
- Report paired confidence intervals and signed provenance for promotion.

## Implementation tasks

See [tasks.md](tasks.md), [reconciliation.md](reconciliation.md) and [audit-pass4.md](audit-pass4.md). QH-01 through QH-07 extend existing T04/T07-T15 work; they are not a second release track.

## Security and governance

No training on unapproved sources. No untrusted code runs outside the pinned sandbox. No reward for ambiguous infrastructure failures. No automatic promotion. No model or hardware readiness claim without executed evidence.

## Non-goals

Training from scratch, direct C++/Rust/plugin code generation, weakening existing licensing rules, widening FPGA scope, or treating compiler success as functional success.

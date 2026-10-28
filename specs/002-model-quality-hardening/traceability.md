# Spec 002: Acceptance and traceability matrix

Status: PROPOSED. Canonical spec 001 version 0.3.11 remains authoritative until an explicit acceptance decision.

| Requirement | Journey | Workflow | State authority | Contract authority | Acceptance | Existing task | Evidence status |
|---|---|---|---|---|---|---|---|
| QH-R01 semantic correctness | J-Q1 | generate/compile/render/check | candidate machine spec 001 §7.2 | TaskSpec, DSPTestReceipt, EvaluationRun | positive/negative DSP families at both sample rates | T04,T11,QH-01 | PROPOSED extension |
| QH-R02 baseline comparison | J-Q3 | baseline/evaluate | training machine §7.3 | BenchmarkSuite, EvaluationRun | paired base vs retrieval vs SFT, fixed decoding | T08,QH-03,QH-05 | NOT MEASURED |
| QH-R03 leakage | J-Q2 | rights/dedup/freeze | dataset machine §7.1 | RightsRecord, SplitManifest | H2/H3/FLOOR evidence, signed freeze | T06,T07,QH-02 | BLOCKED by follow-ups |
| QH-R04 Spark measurement | J-Q3 | fingerprint/benchmark | training machine §7.3 | TrainingRun, environment receipt | measured throughput, peak and restart | T09,T10,QH-04 | NOT MEASURED |
| QH-R05 reward binding | J-Q3 | grade/quarantine/train | training machine §7.3, ADR-0006 | TaskSpec, CompilerReceipt, signed reward records | fail closed on invalid task, native mismatch, whole-group drop | A2-PATH,EVAL-SO,GD-1,QH-07 | IMPLEMENTATION PR #76 DRAFT |
| QH-R06 nonlinear diagnostic exclusion | J-Q1 | signal diagnostics | candidate machine §7.2 | DSPTestReceipt | no nonlinear suite in REWARD_PROFILES | T04,QH-01 | Existing rule, preserve |
| QH-R07 promotion | J-Q4 | independent review/decision | training machine §7.3 | EvaluationRun, DecisionRecord | holdout one-shot, paired CI, human decision | T11,T12,QH-06 | NOT MEASURED |

## Acceptance gate for Spec 002 itself

- The new spec, plan and tasks are present and Spec Kit structural validation passes.
- Every requirement maps to an existing authority and executable future test.
- No accepted spec 001 decision is silently superseded.
- All open implementation and hardware gaps remain explicitly open.
- Canonical KANBAN synchronization is done only after this proposal is accepted.
- Independent review and passing CI are required before merge.

## Decision record proposal

Decision ID: QH-D001. Proposed disposition: ACCEPT SPEC 002 AS A NON-BREAKING EXTENSION TO SPEC 001, subject to review. Keep its proposed fields advisory until contract schema amendments are separately approved. Keep QH-07 and A2-PATH/EVAL-SO open. This text records a recommendation, not approval.

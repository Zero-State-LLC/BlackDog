# Spec 002 reconciliation against canonical spec 001

Status: PROPOSED. Read-only comparison of main at cf319f376161f7c5867aed1080d86d171372a785. This document is not an implementation receipt or authorization to train.

## Corrections to initial proposal

1. T04 is **implemented** (#41, #45), not incomplete. The ARM DGX Spark golden comparison remains pending. T03 is implemented; the README's corpus compile limitation requires verification of pinned faustlibraries staging. Do not call T03b a canonical numbered task until the current backlog confirms it.

2. T06 normalization/dedup is implemented (#39); H2, H3 and FLOOR are open follow-ups. Do not reset T06 to incomplete.

3. Spec 001 is version 0.3.11 on main, not 0.3.10 as README says. Update README separately after review; do not alter the accepted decision log.

4. P3 is not a blanket dependency of P1/P2: D3-H2 and D3-H2-C gate P3, while existing T10 wording and task graph need phase-specific reconciliation.

5. Existing TaskSpec, CompilerReceipt, DSPTestReceipt, EvaluationRun, TrainingRun, DecisionRecord and artifact envelope remain canonical. Names proposed in spec 002 (EvaluationTask, EvaluationReceipt, CorpusAdmissionReceipt, BaselineReceipt, TrainingPerformanceReceipt, PromotionDecisionRecord) are **candidate views/extensions**, not new durable entity types until schema review.

6. The nonlinear suite already has eight float32 stimuli, 144000-frame floor and signed-sample gate. THD+N, IMD and Farina inverse filter are diagnostics; nonlinear-suite-v1 is **not** in REWARD_PROFILES. Do not accidentally turn these diagnostics into reward signals.

7. TaskSpec effect is a closed enum, and only linear/time_invariant tasks are currently rewardable. Semantic behavioral tasks must be evaluated independently, not silently added to P3 reward.

8. The original proposal's language saying T04 incomplete is superseded by this reconciliation.

## Change map

| Spec 002 objective | Existing authority | Delta | Acceptance |

|---|---|---|---|
| DSP behavioral evaluation | T04, T11, R-011, ADR-0004 | Add task-family evaluation fixtures as *non-reward* development metrics first | Oscillator/filter/dynamics/routing known-good and known-bad fixtures; deterministic sample rates; cross-architecture evidence |

| Data leakage certification | T06 H2/H3/FLOOR, T07, spec §25 | Add signed leakage summary derived from existing dedup decisions, without overriding provisional floor rules | Same shipping slicer and frozen gold used; no reject-class copies left in cleared set; signed split manifest |
| Retrieval baseline | T08, ADR-0002 P0 | Add retrieval-assisted untuned comparator, keeping retrieval index restricted to cleared training split | Same task suite, sampling budget, model revision and no holdout retrieval |

| Spark measurements | T09, T10, R-001 0.3.1 | Measure realistic P1/P2 configurations on dedicated Spark, not external projections | fingerprint + representative throughput/peak memory/checkpoint recovery receipt |
| SFT and GRPO comparison | T10, ADR-0002, ADR-0006 | Make phase-specific readiness explicit; P3 remains conditional | P2 quality gates first; P3 only after GD-1, A2-PATH, EVAL-SO, D3-H2-C and other accepted gates |

| Independent promotion | T11/T12, spec §7.3 and §9 | Per-family reporting and cost/latency diagnostics, without replacing D-005 | paired CI, sealed holdout discipline, human DecisionRecord |
| Source audit | T15, security policy | Perform contract-to-code and test/CI traceability before claiming hardening done | recorded evidence with pass/fail/blocked/untested, exact commit and commands |

## Spec-kit acceptance chain

Journey: user requests Faust DSP -> Workflow: candidate generation, compile, render, semantic checks, repair -> States: reuse canonical candidate/evaluation and training state machines; do not introduce a parallel state machine without ADR -> Contracts: extend TaskSpec/DSPTestReceipt/EvaluationRun if schema gaps are verified -> Acceptance tests: fixture pairs and independent signal checks -> Implementation tasks: T04/T08/T11/T12 with explicitly named subtask IDs after board reconciliation.

## Review questions resolved by current architecture

- Does the model directly generate target-specific C++ or plugins? No; Faust remains sole model output, and Faust tooling lowers to targets.

- Is compilation alone promotion evidence? No; independent signal behavior already required.

- Should nonlinear diagnostics feed RL rewards? No, not under existing reward profile.

- Can P3 start before human credential verification? No.

- Can external Spark performance figures justify model pinning? No; T10 measures BlackDog.

- Can a provisional dedup floor be silently treated as clean? No; §25 caveats and recheck apply.

## Implementation-level audit plan, pending execution

Audit T03/T04 sandbox and render code, T05/T06 rights and slicer, T07/T08 baseline paths, T10 grader and RL batch, artifact store and CI. Record exact source revision, command, observed output, failing fixture and proposed minimal fix. Never equate code presence or a green mocked test with on-hardware validation.

## Spec acceptance conditions

- Proposal and reconciliation agree with main and latest PRs.

- New fields have versioned schema migrations and contract tests, or remain explicitly advisory.

- Any new subtask appears once in KANBAN and tasks.md with the same ID, dependency, evidence and done criteria.

- Existing accepted ADRs and §25/§26 decisions remain unchanged unless a new decision record explicitly supersedes them.

- No merge or training without separate review.

## Documentation index reconciliation

The current `docs/INDEX.md` header describes main `665d73b` and spec 001 version 0.3.10. Main has since advanced to spec 001 version 0.3.11 through PR #71. After Spec 002 is accepted, update the index to list its canonical spec, plan, tasks, traceability, and audit evidence, and replace the stale version claim. Do not present Spec 002 as accepted until its merge and review gates pass.

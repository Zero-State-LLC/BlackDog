# Spec 002: Technical plan

Status: PROPOSED. Implementation is gated by spec 001 and existing ADRs.

## Architecture

Retain the Faust-only model output, faustwasm sandbox, native Faust cross-check, content-addressed store, canonical state machines and signed reward ledger. Extend independent evaluation reports rather than creating a second grader.

## Phase A: Read-only verification

Complete QH-07 by mapping source functions to contract tests and CI jobs. Capture base SHA, exact commands, results, blocked checks and hardware limitations. Verify D3-H2-C implementation already merged via #71.

## Phase B: Evaluation evidence

Extend T04/T11 with non-reward semantic fixtures. Keep nonlinear diagnostic suites out of the reward allowlist. Finish H2/H3/FLOOR and T07 split freeze. Build T08 base and retrieval baselines using only rights-cleared training material.

## Phase C: Training evidence

Run T09 fingerprint and representative T10 throughput measurements on the dedicated Spark. Apply ADR-0002 P1 skip rule. Evaluate P2 SFT before authorizing P3. Implement A2-PATH/EVAL-SO evidence propagation in a separate code PR with negative tests. D3-H2-C, GD-1 and other P3 gates remain mandatory.

## Phase D: Independent decision

Run paired development evaluation, then sealed holdout only under the canonical one-shot rule. Produce human-reviewed T12 DecisionRecord with regressions and per-family outcomes.

## Rollback and failure handling

Every change is reversible through a new commit or artifact revision. Failed tests block the affected gate; ambiguous compiler/harness outcomes remain ungraded. Never rewrite immutable evidence or reclassify a failed gate as success.

## Dependencies

QH-07 can proceed immediately. QH-01 depends on T04; QH-02 on H2/H3/FLOOR; QH-03 on T07/T08; QH-04 on T09; QH-05 on baseline and training receipts; QH-06 on T11 and independent review. See [tasks.md](tasks.md).

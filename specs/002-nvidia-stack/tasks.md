# Tasks: NVIDIA Stack Integration (spec 002)

- Input: [spec.md](spec.md), [plan.md](plan.md)

Format: `- [ ] Nxx [P?] [Story] Description`. `[P]` means it can run in parallel
with other `[P]` tasks once its dependencies are met. Evidence paths are
INFERRED until a task starts.

Governing workflows for all tasks: anti-slop-code, production-systems,
google-developer-style (spec 002 section 8).

## Phase 1: Foundational

- [ ] N01 [Found] Receipt schemas for ContainerPinReceipt, NeMoTrainingAttempt and NIMDeploymentReceipt.
  - Depends on: spec 001 T02. Implements: R-N004.
  - Acceptance: schema validation tests; every new receipt carries schema_version, artifact_id, content_digest, created_at, producer and parents.
  - Evidence: `receipts/N01/` (INFERRED).
- [ ] N02 [Found] Static acyclicity check on the receipt graph.
  - Depends on: N01. Implements: R-N004.
  - Acceptance: zero cycles on a completed run graph; every TrainingRun has a ContainerPinReceipt ancestor.
  - Evidence: `receipts/N02/` (INFERRED).

## Phase 2: Container pin

- [ ] N03 [Maintainer] Capture NGC container digest, tag and source into a ContainerPinReceipt.
  - Depends on: N01. Implements: R-N001.
  - Acceptance: T10-style smoke on Spark; digest matches the running container; replay on a second machine gives identical loss for the first 20 steps of a fixed Qwen 1.5B LoRA recipe.
  - Evidence: `receipts/N03/` (INFERRED).

## Phase 3: Training

- [ ] N04 [Trainer] NeMo AutoModel LoRA run on the cleared Spark.
  - Depends on: N03, spec 001 T03. Implements: R-N002.
  - Acceptance: the T03 harness loads and grades the exported checkpoint; peak memory under the R-001 120 GiB cap; TrainingRun parents include the ContainerPinReceipt and the DatasetSnapshot.
  - Evidence: `receipts/N04/` (INFERRED).
- [ ] N05 [P] [Trainer] Head-to-head T10 comparison, NeMo AutoModel versus PEFT/TRL.
  - Depends on: N04. Resolves: D-N001.
  - Evidence: `receipts/N05/` (INFERRED).

## Phase 4: Serving

- [ ] N06 [Operator] Local model-free NIM endpoint with generate, repair, explain and optimize.
  - Depends on: N04. Implements: R-N003.
  - Acceptance: valid generate response for a frozen task within the existing latency budget; NIMDeploymentReceipt is a parent of any EvaluationRun that used the endpoint; R-021 checks still apply.
  - Workflows: add ADVERSARY review. Evidence: `receipts/N06/` (INFERRED).

## Phase 5: External capacity

- [ ] N07 [P] [Auditor] Attach Inception credit usage as an optional metadata parent.
  - Depends on: N01. Implements: R-N005.
  - Acceptance: a credit-backed H100 run attaches as an optional parent; the canonical EvaluationRun still traces to a local Spark fingerprint and the same DatasetSnapshot.
  - Evidence: `receipts/N07/` (INFERRED).

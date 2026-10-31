# Feature Specification: NVIDIA Stack Integration for BlackDog

**Version:** 0.1.0  
**Status:** draft  
**Parents:** specs/001-faustcoder/spec.md@0.3.11, ADR-0002, ADR-0001  
**Producer:** human (Danny)  
**Created:** 2026-10-30 23:55 PT

## 1. Summary

BlackDog already trains and evaluates on DGX Spark. This feature pins official NVIDIA containers and recipes (NeMo AutoModel, NGC PyTorch, NIM) so training runs and inference endpoints remain reproducible, Blackwell-aware, and content-addressed. Compiler and signal verification stay outside the NVIDIA training loop. The evidence DAG gains new receipt types; it does not gain cycles.

## 2. User stories

- As a maintainer I can pin an NGC container digest and record it as a parent of every TrainingRun so a later machine can replay the exact environment.
- As a trainer I can run a Qwen LoRA or full SFT recipe from NeMo AutoModel on Spark, export a Hugging Face checkpoint, and feed verified (prompt, completion, reward) pairs into the existing faustwasm harness without changing R-015 phase gates.
- As a serving operator I can package a cleared adapter or merged model as a model-free NIM endpoint that exposes the four R-010 verbs with structured responses and records a deployment receipt.
- As an auditor I can walk from any EvaluationRun back through its NeMo or NIM parent receipts to the container digest, hardware fingerprint, and dataset snapshot without encountering a cycle.

## 3. Requirements

### R-N001. NGC container pin

Every training or inference process that uses an NVIDIA container records the image digest (sha256), tag, and source (nvcr.io) in a ContainerPinReceipt. The receipt is an immutable parent of the TrainingRun or NIMDeploymentReceipt. Host CUDA installs remain disallowed for pinned runs.

**Acceptance:** A T10-style smoke on Spark produces a ContainerPinReceipt whose digest matches the running container. Replay on a second machine with the same digest yields identical loss trajectory for the first 20 steps of a fixed Qwen 1.5B LoRA recipe.

### R-N002. NeMo AutoModel path

When a training run elects the NeMo path, it uses an official NeMo AutoModel recipe (or a minimal derivative) that consumes Hugging Face Qwen checkpoints. The recipe must emit a standard Hugging Face adapter or merged checkpoint. The faustwasm compiler harness and signal tests remain the sole source of rewards and pass/fail labels. No NeMo-internal metric may substitute for a CompilerReceipt or DSPTestReceipt.

**Acceptance:** A NeMo LoRA run on the Spark-cleared machine produces a checkpoint that the existing T03 harness can load and grade. Peak memory stays inside the R-001 120 GiB cap. The TrainingRun parents include both the ContainerPinReceipt and the DatasetSnapshot.

### R-N003. NIM serving path

A cleared model may be served via a model-free NIM container. The endpoint implements the four R-010 verbs (generate, repair, explain, optimize) and returns schema-compliant responses. Each deployment produces a NIMDeploymentReceipt that records the model artifact digest, container digest, GPU type, and observed latency percentiles. Real-time safety checks from R-021 continue to apply to any generated Faust that leaves the endpoint.

**Acceptance:** A local NIM container on Spark returns a valid generate response for a frozen task within the existing latency budget. The receipt is an immutable parent of any EvaluationRun that used the endpoint.

### R-N004. Evidence DAG compatibility

New receipt types (ContainerPinReceipt, NeMoTrainingAttempt, NIMDeploymentReceipt) carry schema_version, artifact_id, content_digest, created_at, producer, and parents. They reference only prior immutable nodes. Invalidating a ContainerPinReceipt invalidates dependent TrainingRuns until they are rerun. No edge points from a later node to an earlier one.

**Acceptance:** A static check on the receipt graph for a completed NeMo run confirms zero cycles and that every TrainingRun has a ContainerPinReceipt ancestor.

### R-N005. Inception-sourced resources

Cloud credits or preferred-pricing hardware obtained through NVIDIA Inception are recorded as external capacity. They do not alter R-001 fingerprints or the requirement that primary qualification runs occur on a cleared local Spark. Credit usage receipts are optional metadata parents; they never replace dataset or model digests.

**Acceptance:** A credit-backed H100 run can be attached as an optional parent, but the canonical EvaluationRun still traces to a local Spark fingerprint and the same DatasetSnapshot.

## 4. Non-functional constraints

- All new receipts are append-only and content-addressed.
- Sandbox rules from R-013 continue to apply to any generated Faust, regardless of serving path.
- Stack pins remain provisional until a repeated T10-style qualification on the cleared Spark reports positive rates and memory under the R-001 cap.
- No proprietary NVIDIA model weights enter the training corpus.

## 5. Out of scope

- Replacing the faustwasm harness with a NeMo-native evaluator.
- Automatic credit procurement or portal automation.
- Multi-node training beyond what a single NeMo recipe already supports on Spark.
- Changes to the Faust language or DSP graph (section 4.2).

## 6. Mapping to existing DAG

New nodes insert after the existing “training” and “evaluation” stages:

```text
... -> DatasetSnapshot -> ContainerPinReceipt -> NeMoTrainingAttempt -> TrainingRun
                                                              |
                                                              v
                                                       EvaluationRun
                                                              |
                                                              v
                                                    NIMDeploymentReceipt (optional)
```

All edges point forward. A revision of a container or recipe creates a new receipt; it does not mutate prior nodes.

## 7. Open decisions

- D-N001: Default to NeMo AutoModel recipes versus continued PEFT/TRL for the first qualified student model. Resolve after one head-to-head T10 comparison on the cleared Spark.
- D-N002: Whether NIM becomes the sole production serving path or remains one of several R-010 implementations.

## 8. Governing workflows

### Workflows

INFERRED: added for Spec Kit compliance. This list copies spec 001 section 16;
plan, tasks and agent briefs reuse it rather than inventing another.

| Workflow | Applies to | Owner |
|---|---|---|
| anti-slop-code | Receipt schemas, container pin tooling, NeMo and NIM glue code | Cloud agent implements |
| production-systems | NGC container pins, NIM serving, receipt store | Cloud agent implements; FORGE decomposes |
| google-developer-style | This spec, plan, tasks and any ADR it spawns | SCRIBE |
| spec-kit | Spec, plan and tasks for 002 | FORGE |
| Threat model (R-013, R-021) | Generated Faust leaving a NIM endpoint; container supply chain | ADVERSARY |

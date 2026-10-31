# Implementation plan: NVIDIA Stack Integration (spec 002)

- Spec: [spec.md](spec.md)
- Parent spec: [specs/001-faustcoder/spec.md](../001-faustcoder/spec.md) at 0.3.11
- Constitution: [.specify/memory/constitution.md](../../.specify/memory/constitution.md)
- Status: DRAFT
- Date: 2026-10-31

This plan carries spec 002 forward. Anything not stated in spec 002 or spec 001
is labeled INFERRED.

## Summary

Pin official NVIDIA containers (NGC PyTorch, NeMo AutoModel, NIM) as
content-addressed receipts so training and serving on DGX Spark replay exactly.
The faustwasm harness and signal tests stay the only source of rewards and
pass/fail labels (R-N002). New receipts extend the evidence DAG without cycles
(R-N004).

## Technical context

| Item | Value | Source |
|---|---|---|
| Containers | NGC images from nvcr.io, pinned by sha256 digest | R-N001 |
| Training path | NeMo AutoModel recipe or minimal derivative; Hugging Face Qwen checkpoints in and out | R-N002 |
| Serving path | Model-free NIM container exposing the four R-010 verbs | R-N003 |
| Hardware | Cleared local DGX Spark; 120 GiB peak memory cap | R-001, R-N002 |
| Rewards and labels | faustwasm compiler harness (T03) and signal tests only | R-N002 |
| New receipts | ContainerPinReceipt, NeMoTrainingAttempt, NIMDeploymentReceipt | R-N004 |
| External capacity | Inception credits as optional metadata parents only | R-N005 |

Unknowns: D-N001 (NeMo AutoModel versus PEFT/TRL default) and D-N002 (NIM as
sole serving path). Both stay open until the T10-style comparison on the
cleared Spark.

## Constitution check

- Append-only, content-addressed receipts: satisfied by R-N004 and section 4.
- No host CUDA installs for pinned runs: R-N001.
- Sandbox rules (R-013) and real-time safety checks (R-021) unchanged: section 4, R-N003.

## Phases

1. Receipt schemas for the three new node types and a static acyclicity check (R-N004).
2. Container pin capture and a T10-style smoke on Spark (R-N001).
3. NeMo AutoModel LoRA run graded by the existing T03 harness (R-N002).
4. Local NIM endpoint with the four R-010 verbs and a deployment receipt (R-N003).
5. Optional Inception-capacity parent wiring (R-N005).

## Workflows

Copied from spec 002 section 8: anti-slop-code, production-systems,
google-developer-style, spec-kit, and ADVERSARY review for the threat model.

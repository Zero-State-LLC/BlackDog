# ADR-0008: Receipts and glue for the NVIDIA stack

Status: PROPOSED. Code for spec 002 tasks N01 to N04, N06 and N07 is on
branch `spec/002-nvidia-stack` (draft PR
[#121](https://github.com/Zero-State-LLC/BlackDog/pull/121)). No hardware
acceptance has run. This ADR records the contract shape, not a stack pin.

## Context

[Spec 002](../../specs/002-nvidia-stack/spec.md) adds an NGC container pin,
an optional NeMo AutoModel training path, a model-free NIM serving path and
Inception-sourced capacity. The constitution requires contract changes to ship
with schema tests and an ADR, and requires the evidence graph to stay
immutable and acyclic.

## Decision

- Add four receipt payload schemas and one response schema under
  [specs/002-nvidia-stack/contracts](../../specs/002-nvidia-stack/contracts/README.md),
  copied byte for byte to `schemas/`. Each receipt is the `payload` of an
  ordinary ArtifactEnvelope, so it reuses the existing canonical encoding,
  content digest and write-once store. The payload `kind` names the type.
- `faustcoder/nvidia/receipts.py` checks, before a store write, that each
  declared parent digest is listed in `parents`, is stored, has the expected
  kind and is not newer than the child.
- `faustcoder/nvidia/graph.py` re-checks a stored graph: no cycles, no missing
  or later parents, and every TrainingRun has a ContainerPinReceipt ancestor.
  Invalidating a node moves dependent TrainingRuns through the existing
  `upstream_invalidated` training-machine edge and writes a TransitionReceipt.
- NeMoTrainingAttempt has no reward, pass/fail or metric field and sets
  `grading_authority` to `faustwasm`. A TrainingRun built from it has empty
  `metrics`. The NIM client copies verdicts from the harness `Verifier` and
  returns source only when both a CompilerReceipt and a DSPTestReceipt exist
  and the harness passed.
- Memory caps reuse `spark_probe.MAX_MEMORY_CAP_BYTES` (120 GiB, R-001).
- ExternalCapacityReceipt is an optional parent. The canonical EvaluationRun
  must reach a Spark fingerprint that passes the R-001 guard, and the same
  DatasetSnapshot, without passing through an ExternalCapacityReceipt.

## Consequences

- DatasetSnapshot and EvaluationRun still have no schema. The graph checks
  take their digests from the caller. TrainingRun is recognized by its schema.
- AutoModel CLI flags, the `BLACKDOG_CONTAINER_IMAGE` variable and NIM launch
  options are INFERRED from public documentation and must be confirmed on the
  cleared Spark.
- Hardware acceptance for N03 to N07 remains open: the Spark smoke, the
  20-step loss replay, a NeMo LoRA run graded by T03, the NIM latency
  measurement and a credit-backed run.

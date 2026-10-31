# Contracts: spec 002

DRAFT JSON Schemas (2020-12) for the spec 002 receipts (R-N001 to R-N005).
Each schema describes the `payload` of an ordinary
[ArtifactEnvelope](../../001-faustcoder/contracts/artifact-envelope.schema.json),
so every receipt carries `schema_version`, `artifact_id`, `content_digest`,
`created_at`, `producer` and `parents` and is stored write-once by the
existing content-addressed store. The payload `kind` names the receipt type.
Field sets are INFERRED from the spec unless it states them. They are copied
to `schemas/` and are decided in ADR-0008.

| File | Spec source |
|---|---|
| [container-pin-receipt.schema.json](container-pin-receipt.schema.json) | R-N001 ContainerPinReceipt |
| [nemo-training-attempt.schema.json](nemo-training-attempt.schema.json) | R-N002 NeMoTrainingAttempt |
| [nim-deployment-receipt.schema.json](nim-deployment-receipt.schema.json) | R-N003 NIMDeploymentReceipt |
| [nim-verb-response.schema.json](nim-verb-response.schema.json) | R-N003 and spec 001 R-010 verb responses |
| [external-capacity-receipt.schema.json](external-capacity-receipt.schema.json) | R-N005 credit usage |

Rules the schemas cannot express are enforced in
`faustcoder/nvidia/receipts.py` before a store write:

- Every payload digest field that names a parent is also listed in the
  envelope `parents`, is already stored, has the expected kind and is not
  newer than the child.
- A completed NeMoTrainingAttempt records a peak memory at or under its cap
  and at least one exported checkpoint.
- A NIMDeploymentReceipt's `container_image_digest` equals the image digest
  of its ContainerPinReceipt.

NeMoTrainingAttempt has no reward, pass/fail or metric field, and
`additionalProperties` is false. CompilerReceipt and DSPTestReceipt from the
faustwasm harness stay the only grading evidence (R-N002). An
ExternalCapacityReceipt is an optional metadata parent only; it never stands
in for an environment fingerprint, a dataset or a model (R-N005).

# Contracts: spec 001

DRAFT JSON Schemas (2020-12) for the contracts in spec §8, plus the common
envelope (§3) and the transition receipt (§7). Field names are OBSERVED from
the spec; types, formats and enums are INFERRED unless the spec states them.
Per spec §8, these become authoritative only once implemented with validation
tests (task T02) and copied to `schemas/`.

| File | Spec source |
|---|---|
| [artifact-envelope.schema.json](artifact-envelope.schema.json) | §3 |
| [task-spec.schema.json](task-spec.schema.json) | §8 TaskSpec |
| [compiler-receipt.schema.json](compiler-receipt.schema.json) | §8 CompilerReceipt |
| [dsp-test-receipt.schema.json](dsp-test-receipt.schema.json) | §8 DSPTestReceipt |
| [dsp-reward-receipt.schema.json](dsp-reward-receipt.schema.json) | §23 reward receipt |
| [dsp-diagnostic-receipt.schema.json](dsp-diagnostic-receipt.schema.json) | §23 diagnostic receipt |
| [training-run.schema.json](training-run.schema.json) | §8 TrainingRun |
| [decision-record.schema.json](decision-record.schema.json) | §8 DecisionRecord |
| [target-receipt.schema.json](target-receipt.schema.json) | §8 TargetReceipt (0.3.0) |
| [transition-receipt.schema.json](transition-receipt.schema.json) | §7 |
| [inference-api.md](inference-api.md) | R-010 |

- [function-spans.schema.json](function-spans.schema.json): reviewed byte ranges
  bound to inventory/notice digests (ADR-0007). Schema validation is structural;
  runtime also verifies the independent manifest pin, identity, coverage,
  non-overlap, bounds, UTF-8 boundaries and extracted content hashes.

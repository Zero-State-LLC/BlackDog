# BlackDog

Formerly FaustCoder. Renamed 2026-10-17 PT.

Compiler-verified Faust DSP coding model, developed on NVIDIA DGX Spark.

**Status:** specification-first. The V0.1 content-addressed artifact store (T02), sandboxed Faust compiler harness (T03, faustwasm 0.19.0), dataset rights transitions (T05), and the T06 normalization and dedup snapshot are implemented. T06 admits units from the pinned T05 rights inventory through T05's guard and does not clear rights itself. Compiler and signal rendering share pinned-library staging after PR #86. No model-quality claim is established. For v0.2, R-001 (amended 0.3.1) uses cited external DGX Spark benchmarks plus a per-machine fingerprint; the [Qwen T10 smoke](docs/runbooks/spark-local-setup.md#qwen-t10-smoke-and-merged-library-rendering) records bounded training, prefill and decode throughput on spark-af42, with exact checkpoint/resume checks. Repeated representative throughput/memory qualification, formal data/split/baseline gates and stack-pin review remain pending.

## Start here

- [Canonical specification](specs/001-faustcoder/spec.md) (0.3.11)
- [Docs index](docs/INDEX.md): ADRs, decision records, runbooks, state machines, analysis and spec 001
- [Source rights inventory](docs/rights-inventory.md)
- [Implementation backlog](KANBAN.md)
- Architecture decisions: [ADR-0001](docs/adr/0001-dag-evidence.md), [ADR-0002](docs/adr/0002-training-path.md), [ADR-0003](docs/adr/0003-licensing-and-data-rights.md), [ADR-0004](docs/adr/0004-target-lanes-and-faust-tooling.md), [ADR-0005](docs/adr/0005-compiler-diagnostic-classes.md), [ADR-0006](docs/adr/0006-source-attributable-failures.md)
- [Constitution](.specify/memory/constitution.md)
- [Contribution guidelines](CONTRIBUTING.md) and [security policy](SECURITY.md)
- [Changelog](CHANGELOG.md) and [versioning](docs/VERSIONING.md)
- [DGX Spark feasibility study](docs/dgx-spark-feasibility.md) and the [env_verified runbook](docs/runbooks/dgx-spark-env-verified.md)
- [T06 normalize and dedup runbook](docs/runbooks/t06-normalize-dedup.md)
- [Verified Spark setup and next steps](docs/runbooks/spark-local-setup.md)

## Principles

1. Validate generated Faust through a pinned compiler and independent signal tests.
2. Track all datasets, runs, receipts and releases with immutable content digests and parent references.
3. Separate an acyclic evidence DAG from stateful/recursive Faust DSP semantics.
4. Keep frozen evaluation holdouts isolated from training and model selection.
5. Benchmark model quality and training throughput before choosing a student model.

## Scope

The v0.1 milestone is infrastructure, contracts, provenance and baseline evaluation, not a trained model.

## License

This repository is split-licensed (ADR-0003):

| Path | License |
|---|---|
| `specs/` and `docs/` (including ADRs) | [Apache-2.0](LICENSE-APACHE) |
| Everything else: code, scripts, CI, model weights, adapters, checkpoints, datasets and evaluation data | [Zero State Proprietary License 1.0](LICENSE) |

The proprietary license is the default for any path not listed above. See
[NOTICE](NOTICE). Third-party material keeps its own license; GPL code used for
training is never stored in this repository or in released data.

# FaustCoder

Compiler-verified Faust DSP coding model, developed on NVIDIA DGX Spark.

**Status:** specification-first, pre-implementation. No model quality or hardware compatibility claims are established yet.

## Start here

- [Canonical specification](specs/001-faustcoder/spec.md)
- [Implementation backlog](KANBAN.md)
- Architecture decisions: [ADR-0001](docs/adr/0001-dag-evidence.md), [ADR-0002](docs/adr/0002-training-path.md), [ADR-0003](docs/adr/0003-licensing-and-data-rights.md), [ADR-0004](docs/adr/0004-target-lanes-and-faust-tooling.md)
- [Constitution](.specify/memory/constitution.md)
- [Contribution guidelines](CONTRIBUTING.md) and [security policy](SECURITY.md)
- [Changelog](CHANGELOG.md) and [versioning](docs/VERSIONING.md)

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

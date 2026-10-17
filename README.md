# FaustCoder

Compiler-verified Faust DSP coding model, developed on NVIDIA DGX Spark.

**Status:** specification-first, pre-implementation. No model quality or hardware compatibility claims are established yet.

## Start here

- [Canonical specification](specs/001-faustcoder/spec.md)
- [Implementation backlog](KANBAN.md)
- [Architecture decision](docs/adr/0001-dag-evidence.md)
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

No license has been chosen yet. Until one is added, default copyright applies and no reuse rights are granted.

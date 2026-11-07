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

- DatasetSnapshot and EvaluationRun still have no schema. Spec 001
  [data-model.md](../../specs/001-faustcoder/data-model.md) labels their
  payload fields INFERRED and has no contract for them, and
  `faustcoder/snapshot.py` writes a `DedupManifest`, not a frozen
  DatasetSnapshot. Spec 002 does not invent one. The graph checks take
  their digests from the caller. TrainingRun is recognized by its schema.
- Launch options were checked against primary sources on 2026-10-31
  (see below). Whether they behave as documented on the cleared Spark is
  NOT_COMPUTABLE until that hardware runs them.
- `BLACKDOG_CONTAINER_IMAGE` is a BlackDog convention, not an NGC one.
  Inside a container it is a claim. `verify_container` checks the run on
  the host from `container inspect` and `image inspect`.
- Hardware acceptance for N03 to N07 remains open: the Spark smoke, the
  running-digest match, the 20-step loss replay, a NeMo LoRA run graded by
  T03, the NIM latency measurement and a credit-backed run.

## Sources

OBSERVED 2026-10-31.

- NeMo AutoModel, [NVIDIA-NeMo/Automodel](https://github.com/NVIDIA-NeMo/Automodel)
  at commit `16670959b86f61dc662605c0df8e7de774b71aac`:
  - `nemo_automodel/cli/app.py`: `automodel <config.yaml>
    [--nproc-per-node N] [--key.subkey=value]`.
  - `nemo_automodel/components/config/_arg_parser.py`: a value that starts
    with `--` is misread in `--key value` form, so overrides use
    `--key=value`.
  - `docs/guides/checkpointing.mdx`: `save_consolidated: final` is the
    recommended value and `true` is the legacy form of `every`. PEFT
    writes `adapter_config.json` and `adapter_model.safetensors` under
    `model/`; full SFT writes HF weights under `model/consolidated/`.
  - `tools/merge_lora.py` merges an adapter as a separate step.
  - `docker/Dockerfile`: WORKDIR `/opt/Automodel`. Recipes ending in
    `_spark.yaml` target GB10.
  - Image `nvcr.io/nvidia/nemo-automodel:26.10.00`, linux/amd64 and
    linux/arm64
    ([NGC API](https://api.ngc.nvidia.com/v2/repos/nvidia/nemo-automodel)).
- NIM for LLMs 2.1.4
  ([docs](https://docs.nvidia.com/nim/large-language-models/latest/)):
  - environment-variables: `NIM_MODEL_PATH` (local directory),
    `NIM_SERVED_MODEL_NAME`, `NIM_MODEL_PROFILE`, `NIM_PEFT_SOURCE`, and
    `NIM_HEALTH_PORT` serving `/v1/health/ready`.
  - 1.x-migration-guide: `NIM_MODEL_NAME` is the 1.x name.
  - air-gap-deployment: with a local path no download occurs; do not set
    `NGC_API_KEY` or `HF_TOKEN`; `--shm-size=16GB`; port 8000.
  - finetune-lora: adapter layout, a `-feat_lora` profile, and the request
    `model` naming the adapter on vLLM.
  - support-matrix: `vllm-model-free-nim` is verified on NVIDIA-GB10.
  - The quickstart names `nvcr.io/nim/nvidia/model-free-nim:2.1.4`, but the
    [NGC API](https://api.ngc.nvidia.com/v2/repos/nim/nvidia/model-free-nim)
    lists 2.0.13 as its latest tag, and
    [vllm-model-free-nim](https://api.ngc.nvidia.com/v2/repos/nim/nvidia/vllm-model-free-nim)
    lists 2.1.x tags.
- Digests (moby commit `9aa9edfa787e08bb2da31694cd8a402876f32232`,
  containers/podman commit `d727bf2fc6a9c4e4993c6b7562f9553309395bb7`):
  - [moby image_inspect.go](https://github.com/moby/moby/blob/9aa9edfa787e08bb2da31694cd8a402876f32232/api/types/image/image_inspect.go):
    `Id` is the config digest, and `RepoDigests` is set after a pull or push.
  - moby `api/swagger.yaml`: container `Image` is the image ID, and
    `Config.Image` is the reference as given.
  - Podman `podman-image-inspect.1`: `Digest` and several `RepoDigests`.
  - Podman `podman-container-inspect.1`: `Image` and `ImageName`.
  - Podman `podman-run.1`: `/run/.containerenv` holds image data only with
    `--privileged`.

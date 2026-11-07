"""NeMo AutoModel glue: config, launch argv and attempt receipts (R-N002).

This module builds a run configuration, checks it against R-001, turns
it into a ``docker run ... automodel`` argv for a digest-pinned NGC
image, and records what happened as a ``NeMoTrainingAttempt``. It does
not launch anything itself and has no grading function: the exported
Hugging Face checkpoint is graded only by the faustwasm harness, so a
TrainingRun built here carries empty ``metrics``.

Sources (OBSERVED 2026-10-31, NVIDIA-NeMo/Automodel at commit
16670959b86f61dc662605c0df8e7de774b71aac):

- ``automodel <config.yaml> [--nproc-per-node N] [--key.subkey=override]``
  is the CLI (nemo_automodel/cli/app.py). Overrides are parsed by
  nemo_automodel/components/config/_arg_parser.py; this module always
  uses the ``--key=value`` form so a value is never read as a flag.
- The image is ``nvcr.io/nvidia/nemo-automodel`` (README, docs/guides/
  installation.mdx; tag 26.10.00 at that commit). Its WORKDIR is
  /opt/Automodel and it runs as root by default (docker/Dockerfile).
  The NGC repository is multi-architecture (amd64 and arm64).
- LoRA runs write a Hugging Face PEFT adapter (adapter_config.json and
  adapter_model.safetensors) under ``<checkpoint>/model/``; full SFT
  with ``checkpoint.save_consolidated: final`` writes HF weights under
  ``<checkpoint>/model/consolidated/`` (docs/guides/checkpointing.mdx).
  Merging an adapter into the base model is a separate step
  (tools/merge_lora.py) that this module does not launch.
- GB10 (DGX Spark) recipes exist, for example
  examples/llm_finetune/qwen/qwen3_8b_squad_spark.yaml with
  ``ci.cluster_tag: gb10`` and one process per node.

NOT_COMPUTABLE here: that these flags and keys behave as documented on
the cleared Spark, and the peak memory of a real run (N04).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from faustcoder.canonical import content_digest_for
from faustcoder.nvidia.container_pin import IMAGE_ENV, ImagePin
from faustcoder.nvidia.receipts import (
    ReceiptKind,
    ReceiptRuleError,
    build_receipt,
    object_field,
    put_receipt,
    string_list,
    validate_receipt_payload,
)
from faustcoder.schemas import validate
from faustcoder.spark_probe import MAX_MEMORY_CAP_BYTES
from faustcoder.store import ArtifactStore

METHODS = ("lora", "full_sft")
EXPORT_FORMATS = ("hf_adapter", "hf_merged")
MAX_STEPS_LIMIT = 100_000
_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_PATH_RE = re.compile(r"^/[A-Za-z0-9_][A-Za-z0-9_./-]*$")
_RECIPE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]*\.ya?ml$")
CONTAINER_DATA = "/data"
CONTAINER_MODEL = "/model"
CONTAINER_OUTPUT = "/output"
CONTAINER_RECIPES = "/recipes"
SHM_SIZE = "8g"
# Images known to ship the ``automodel`` CLI. Extend only from a source.
AUTOMODEL_REPOSITORIES = frozenset({"nvidia/nemo-automodel"})
# Export format each method produces inside one AutoModel run.
EXPORT_FOR_METHOD = {"lora": "hf_adapter", "full_sft": "hf_merged"}
# Where the exported Hugging Face files land under a checkpoint directory.
EXPORT_SUBDIR = {"hf_adapter": "model", "hf_merged": "model/consolidated"}


class NeMoConfigError(ValueError):
    """A NeMo run configuration breaks an R-001 or R-N002 rule."""


@dataclass(frozen=True)
class NeMoRunConfig:
    """Inputs of one AutoModel run. Paths are host paths, mounted read-only
    except ``output_dir``. ``recipe_path`` is relative to ``recipe_dir``,
    so ``recipe_digest`` covers a file the host can hash."""

    pin: ImagePin
    dataset_snapshot_digest: str
    base_model_repository: str
    base_model_revision: str
    recipe_path: str
    recipe_digest: str
    recipe_dir: str
    model_dir: str
    data_dir: str
    output_dir: str
    method: str = "lora"
    max_steps: int = 20
    seed: int = 0
    memory_cap_bytes: int = MAX_MEMORY_CAP_BYTES
    export_format: str = "hf_adapter"
    extra_overrides: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class NeMoOutcome:
    """What the launcher observed after the container exited."""

    status: str
    peak_memory_bytes: int | None
    checkpoint_digests: tuple[str, ...]
    loss_log_digest: str | None


def validate_config(config: NeMoRunConfig) -> None:
    """Raise NeMoConfigError unless ``config`` is safe to launch."""
    problems = _config_problems(config)
    if problems:
        raise NeMoConfigError("; ".join(problems))


def config_payload(config: NeMoRunConfig) -> dict[str, object]:
    """Return the canonical, host-path-free description of ``config``."""
    validate_config(config)
    return {
        "image": config.pin.reference,
        "dataset_snapshot_digest": config.dataset_snapshot_digest,
        "base_model": f"{config.base_model_repository}@{config.base_model_revision}",
        "recipe": {"path": config.recipe_path, "digest": config.recipe_digest},
        "method": config.method,
        "max_steps": config.max_steps,
        "seed": config.seed,
        "memory_cap_bytes": config.memory_cap_bytes,
        "export_format": config.export_format,
        "overrides": dict(sorted(config.extra_overrides.items())),
    }


def export_dir(step_dir: str, export_format: str) -> str:
    """Return where AutoModel writes ``export_format`` files under one
    ``epoch_E_step_S`` checkpoint directory (checkpointing.mdx)."""
    if export_format not in EXPORT_SUBDIR:
        raise NeMoConfigError(f"export_format must be one of {EXPORT_FORMATS}")
    return f"{step_dir.rstrip('/')}/{EXPORT_SUBDIR[export_format]}"


def config_digest(config: NeMoRunConfig) -> str:
    """Return the content digest of ``config_payload(config)``."""
    return content_digest_for(config_payload(config))


def launch_argv(config: NeMoRunConfig) -> list[str]:
    """Return a ``docker run`` argv for one offline, capped AutoModel run.

    The container has no network, the R-001 memory cap with no swap,
    read-only model and data mounts, and runs the pinned digest.
    """
    validate_config(config)
    overrides = {
        "model.pretrained_model_name_or_path": CONTAINER_MODEL,
        "step_scheduler.max_steps": str(config.max_steps),
        "rng.seed": str(config.seed),
        "checkpoint.enabled": "true",
        "checkpoint.checkpoint_dir": CONTAINER_OUTPUT,
        "checkpoint.save_consolidated": "final",
        "checkpoint.model_save_format": "safetensors",
        **config.extra_overrides,
    }
    argv = [
        "docker",
        "run",
        "--rm",
        "--gpus",
        "all",
        "--network",
        "none",
        "--memory",
        str(config.memory_cap_bytes),
        "--memory-swap",
        str(config.memory_cap_bytes),
        "--shm-size",
        SHM_SIZE,
        "-e",
        "HF_HUB_OFFLINE=1",
        "-e",
        "TRANSFORMERS_OFFLINE=1",
        "-e",
        f"{IMAGE_ENV}={config.pin.tagged_reference}",
        "-v",
        f"{config.model_dir}:{CONTAINER_MODEL}:ro",
        "-v",
        f"{config.data_dir}:{CONTAINER_DATA}:ro",
        "-v",
        f"{config.recipe_dir}:{CONTAINER_RECIPES}:ro",
        "-v",
        f"{config.output_dir}:{CONTAINER_OUTPUT}",
        config.pin.reference,
        "automodel",
        f"{CONTAINER_RECIPES}/{config.recipe_path}",
        "--nproc-per-node",
        "1",
    ]
    argv.extend(f"--{key}={value}" for key, value in sorted(overrides.items()))
    return argv


def attempt_payload(
    config: NeMoRunConfig,
    outcome: NeMoOutcome,
    *,
    container_pin_digest: str,
    external_capacity_digest: str | None = None,
) -> dict[str, object]:
    """Return a validated NeMoTrainingAttempt payload.

    Only configuration, resource use and artifacts are recorded. The
    schema forbids reward, pass/fail or metric fields.
    """
    payload: dict[str, object] = {
        "kind": ReceiptKind.NEMO_ATTEMPT.value,
        "container_pin_digest": container_pin_digest,
        "dataset_snapshot_digest": config.dataset_snapshot_digest,
        "external_capacity_digest": external_capacity_digest,
        "base_model": {
            "repository": config.base_model_repository,
            "revision": config.base_model_revision,
        },
        "recipe": {"path": config.recipe_path, "digest": config.recipe_digest},
        "config_digest": config_digest(config),
        "method": config.method,
        "max_steps": config.max_steps,
        "seed": config.seed,
        "memory_cap_bytes": config.memory_cap_bytes,
        "peak_memory_bytes": outcome.peak_memory_bytes,
        "status": outcome.status,
        "export": {
            "format": config.export_format,
            "checkpoint_digests": list(outcome.checkpoint_digests),
        },
        "loss_log_digest": outcome.loss_log_digest,
        "grading_authority": "faustwasm",
    }
    validate_receipt_payload(payload)
    return payload


def record_attempt(
    store: ArtifactStore,
    payload: Mapping[str, object],
    *,
    created_at: str,
    producer: str = "faustcoder.nvidia.nemo",
) -> str:
    """Store a NeMoTrainingAttempt and return its artifact id."""
    return put_receipt(store, build_receipt(payload, created_at=created_at, producer=producer))


def training_run_payload(
    attempt: Mapping[str, object],
    *,
    run_id: str,
    split_digest: str,
    code_revision: str,
    hardware_profile: Mapping[str, object],
) -> dict[str, object]:
    """Return a TrainingRun payload for a completed attempt.

    ``metrics`` is empty: evaluation numbers come later from the
    faustwasm harness, never from NeMo.
    """
    if validate_receipt_payload(attempt) is not ReceiptKind.NEMO_ATTEMPT:
        raise ReceiptRuleError("training_run_payload needs a NeMoTrainingAttempt")
    if attempt["status"] != "completed":
        raise ReceiptRuleError("only a completed attempt becomes a TrainingRun")
    base = object_field(attempt, "base_model")
    export = object_field(attempt, "export")
    payload: dict[str, object] = {
        "run_id": run_id,
        "base_model_revision": f"{base['repository']}@{base['revision']}",
        "dataset_digest": attempt["dataset_snapshot_digest"],
        "split_digest": split_digest,
        "config_digest": attempt["config_digest"],
        "code_revision": code_revision,
        "hardware_profile": dict(hardware_profile),
        "checkpoint_digests": string_list(export, "checkpoint_digests"),
        "metrics": {},
    }
    validate(payload, "training-run.schema.json")
    return payload


def training_run_parents(attempt_digest: str, attempt: Mapping[str, object]) -> list[str]:
    """Return TrainingRun parents: the attempt, its pin and its dataset (N04)."""
    validate_receipt_payload(attempt)
    return [
        attempt_digest,
        str(attempt["container_pin_digest"]),
        str(attempt["dataset_snapshot_digest"]),
    ]


def _config_problems(config: NeMoRunConfig) -> list[str]:
    checks = (
        (config.method in METHODS, f"method must be one of {METHODS}"),
        (config.export_format in EXPORT_FORMATS, f"export_format must be one of {EXPORT_FORMATS}"),
        (
            EXPORT_FOR_METHOD.get(config.method, config.export_format) == config.export_format,
            "export_format must match the method: lora -> hf_adapter, full_sft -> hf_merged",
        ),
        (
            config.pin.repository in AUTOMODEL_REPOSITORIES,
            f"pin must be one of {sorted(AUTOMODEL_REPOSITORIES)}",
        ),
        (1 <= config.max_steps <= MAX_STEPS_LIMIT, f"max_steps must be in 1..{MAX_STEPS_LIMIT}"),
        (config.seed >= 0, "seed must be non-negative"),
        (
            1 <= config.memory_cap_bytes <= MAX_MEMORY_CAP_BYTES,
            f"memory_cap_bytes must be in 1..{MAX_MEMORY_CAP_BYTES} (R-001 120 GiB)",
        ),
        (
            _REVISION_RE.fullmatch(config.base_model_revision) is not None,
            "base_model_revision must be a 40-hex commit",
        ),
        (
            _DIGEST_RE.fullmatch(config.dataset_snapshot_digest) is not None,
            "dataset_snapshot_digest must be sha256:<hex>",
        ),
        (
            _DIGEST_RE.fullmatch(config.recipe_digest) is not None,
            "recipe_digest must be sha256:<hex>",
        ),
        (
            _RECIPE_RE.fullmatch(config.recipe_path) is not None
            and ".." not in config.recipe_path,
            "recipe_path must be a relative .yaml path",
        ),
        (
            all(
                _SAFE_PATH_RE.fullmatch(p) and ".." not in p
                for p in (config.model_dir, config.data_dir, config.output_dir, config.recipe_dir)
            ),
            "model_dir, data_dir, output_dir and recipe_dir must be absolute paths"
            " without '..' or ':'",
        ),
        (
            all(re.fullmatch(r"[a-z_][a-z0-9_.]*", key) for key in config.extra_overrides),
            "override keys must be dotted lowercase names",
        ),
        (
            not set(config.extra_overrides) & _RESERVED_OVERRIDES,
            "overrides may not change steps, seed or checkpoint export",
        ),
    )
    return [message for ok, message in checks if not ok]


_RESERVED_OVERRIDES = frozenset(
    {
        "model.pretrained_model_name_or_path",
        "step_scheduler.max_steps",
        "rng.seed",
        "checkpoint.enabled",
        "checkpoint.checkpoint_dir",
        "checkpoint.save_consolidated",
        "checkpoint.model_save_format",
    }
)

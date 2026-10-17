"""DGX Spark environment fingerprint and bounded throughput probe.

The probe records hardware diagnostics and, when a local model path
is passed, a short inference forward and a tiny LoRA step. It then
attempts the training machine's ``env_verified`` transition (spec
§7.3, R-001).

There is no environment-diagnostics schema under ``contracts/``. The
diagnostics object is stored as an artifact envelope payload only.
That shape is SPECULATIVE. The transition receipt payload is the
existing TransitionReceipt schema.

Safety (shared machines):

- Duration is capped at ``MAX_PROBE_SECONDS``.
- The process memory cap defaults to 4 GiB and cannot exceed 96 GiB.
- Model weights are loaded only from an existing local directory.
- Offline mode is forced. There is no flag that turns the network on.
- Payloads omit absolute paths, environment variables and command output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from faustcoder.canonical import build_envelope
from faustcoder.schemas import validate
from faustcoder.store import ArtifactStore
from faustcoder.training_machine import (
    INITIAL_STATE,
    GuardRejected,
    IllegalTransition,
    TrainingEvent,
    TrainingState,
    transition_row,
)

SCHEMA_VERSION = "0.3.0"
PRODUCER = "faustcoder.spark_probe"
TRANSITION_SCHEMA = "transition-receipt.schema.json"
DIAGNOSTICS_KIND = "environment_diagnostics"
CONTRACT_NOTE = (
    "SPECULATIVE: contracts/ has TransitionReceipt and no "
    "environment-diagnostics schema. This payload is an envelope "
    "object only."
)

# ADR-0004 version pin set. Copied, not probed. A receipt that names
# a different pin does not pass the R-001 guard.
ADR0004_PINS: dict[str, str] = {
    "faust_native": "2.88.0",
    "faustlibraries_commit": "2edec0537f53",
    "faustwasm": "0.19.0",
    "clap_wrapper": "0.16.0",
    "clap_validator": "0.4.1",
    "pluginval": "1.0.4",
    "lv2lint": "0.16.2",
    "yosys": "0.70",
    "nextpnr": "0.11.1",
}

MIN_UNIFIED_MEMORY_BYTES = 100 * 1024**3
MAX_MEMORY_CAP_BYTES = 96 * 1024**3
DEFAULT_MEMORY_CAP_BYTES = 4 * 1024**3
MAX_PROBE_SECONDS = 600
DEFAULT_PROBE_SECONDS = 60
MAX_SEQ_LEN = 128
DEFAULT_SEQ_LEN = 32
MAX_NEW_TOKENS = 64
DEFAULT_NEW_TOKENS = 16
MAX_LORA_RANK = 8
DEFAULT_LORA_RANK = 4
MAX_LORA_STEPS = 2
DEFAULT_LORA_STEPS = 1
WEIGHT_ESTIMATE_FACTOR = 1.15

_SPARK_GPU_RE = re.compile(r"(?:GB10|Grace Blackwell|DGX Spark)\b", re.IGNORECASE)
_ACTOR_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_TIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_PACKAGE_NAMES = (
    "torch",
    "transformers",
    "peft",
    "trl",
    "vllm",
    "bitsandbytes",
    "unsloth",
)


class ProbeUsageError(Exception):
    """The operator's arguments cannot be run safely."""


@dataclass(frozen=True)
class ProbeRequest:
    """Inputs for one pair of probes. No absolute model path is kept."""

    model_path: Path | None
    cuda_available: bool
    memory_cap_bytes: int
    available_bytes: int | None
    max_seconds: int
    seq_len: int
    max_new_tokens: int
    lora_rank: int
    lora_steps: int
    deadline: float


@dataclass(frozen=True)
class EnvVerifiedRecord:
    """Digests written by a successful ``env_verified`` transition."""

    state: TrainingState
    diagnostics_id: str
    diagnostics_digest: str
    receipt_id: str
    receipt_digest: str


def force_offline_env() -> None:
    """Refuse hub and dataset network access for this process."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


def measure_packages(names: Sequence[str] = _PACKAGE_NAMES) -> dict[str, dict[str, Any]]:
    """Record installed distribution versions without importing them.

    Metadata does not prove the native extension loads on this GPU.
    """
    found: dict[str, dict[str, Any]] = {}
    for name in names:
        try:
            found[name] = {"status": "installed", "version": version(name)}
        except PackageNotFoundError:
            found[name] = {"status": "not_installed", "version": None}
    return found


def collect_fingerprint(
    *,
    platform_info: Mapping[str, str] | None = None,
    meminfo_text: str | None = None,
    nvidia_smi: Any | None = None,
    torch_info: Any | None = None,
) -> dict[str, Any]:
    """Read arch, memory, driver and torch facts. Never reads ``os.environ``."""
    info = dict(platform_info) if platform_info is not None else _platform_info()
    memory = _parse_meminfo(meminfo_text if meminfo_text is not None else _read_meminfo())
    smi = nvidia_smi() if nvidia_smi is not None else _nvidia_smi()
    torch_facts = torch_info() if torch_info is not None else _torch_fingerprint()
    gpu_name = smi.get("gpu_name") or torch_facts.get("gpu_name") or ""
    driver = smi.get("driver_version")
    return {
        "arch": info.get("arch", ""),
        "system": info.get("system", ""),
        "kernel": info.get("kernel", ""),
        "python": info.get("python", ""),
        "node": info.get("node", ""),
        "gpu_name": gpu_name,
        "gpu_count": int(torch_facts.get("gpu_count") or 0),
        "cuda_available": bool(torch_facts.get("cuda_available")),
        "cuda_version": torch_facts.get("cuda_version"),
        "torch_version": torch_facts.get("torch_version") or torch_facts.get("version"),
        "torch_imported": bool(torch_facts.get("imported")),
        "torch_error_type": torch_facts.get("error_type"),
        "driver_version": driver,
        "nvidia_smi": smi.get("status", "unavailable"),
        "memory_total_bytes": memory.get("total_bytes"),
        "memory_available_bytes": memory.get("available_bytes"),
        "memory_source": "meminfo" if memory.get("total_bytes") is not None else "absent",
    }


def estimate_decoder_weight_bytes(config: Mapping[str, Any]) -> int | None:
    """Conservative bf16 weight-byte estimate for a decoder config.

    Returns ``None`` when the config does not have the integer fields
    the formula needs. Missing ``tie_word_embeddings`` counts the
    output embedding again so the estimate is high, not low.
    """
    required = (
        "hidden_size",
        "num_hidden_layers",
        "vocab_size",
        "intermediate_size",
        "num_attention_heads",
        "num_key_value_heads",
    )
    values: dict[str, int] = {}
    for key in required:
        raw = config.get(key)
        if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
            return None
        values[key] = raw
    if values["hidden_size"] % values["num_attention_heads"] != 0:
        return None
    head_dim = values["hidden_size"] // values["num_attention_heads"]
    kv_dim = values["num_key_value_heads"] * head_dim
    hidden = values["hidden_size"]
    attn = hidden * hidden + 2 * hidden * kv_dim + hidden * hidden
    mlp = 3 * hidden * values["intermediate_size"]
    embed = values["vocab_size"] * hidden
    params = embed + values["num_hidden_layers"] * (attn + mlp)
    tied = config.get("tie_word_embeddings")
    if tied is not True:
        params += embed
    return math.ceil(params * 2 * WEIGHT_ESTIMATE_FACTOR)


def load_model_config(model_path: Path) -> dict[str, Any] | None:
    """Read ``config.json`` integers only. Refuses files over 1 MiB."""
    path = model_path / "config.json"
    if not path.is_file():
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) > 1_000_000:
        return None
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def config_sha256(model_path: Path) -> str | None:
    """Return ``sha256:<hex>`` of ``config.json`` bytes, or ``None``."""
    path = model_path / "config.json"
    if not path.is_file():
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) > 1_000_000:
        return None
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def local_model_record(model_path: Path | None) -> dict[str, str] | None:
    """Basename and config digest. Absolute paths are not recorded."""
    if model_path is None:
        return None
    record = {"basename": model_path.name}
    digest = config_sha256(model_path)
    if digest is not None:
        record["config_sha256"] = digest
    return record


def _skipped(reason: str) -> dict[str, Any]:
    return {
        "status": "skipped",
        "reason": reason,
        "tokens_per_second": None,
        "peak_memory_bytes": None,
    }


def _check_probe_bounds(request: ProbeRequest) -> None:
    if not 1 <= request.max_seconds <= MAX_PROBE_SECONDS:
        raise ProbeUsageError(
            f"max_seconds must be 1..{MAX_PROBE_SECONDS}"
        )
    if not 1 <= request.memory_cap_bytes <= MAX_MEMORY_CAP_BYTES:
        raise ProbeUsageError("memory cap must be 1 byte..96 GiB")
    if not 1 <= request.seq_len <= MAX_SEQ_LEN:
        raise ProbeUsageError(f"seq_len must be 1..{MAX_SEQ_LEN}")
    if not 1 <= request.max_new_tokens <= MAX_NEW_TOKENS:
        raise ProbeUsageError(f"max_new_tokens must be 1..{MAX_NEW_TOKENS}")
    if not 1 <= request.lora_rank <= MAX_LORA_RANK:
        raise ProbeUsageError(f"lora_rank must be 1..{MAX_LORA_RANK}")
    if not 1 <= request.lora_steps <= MAX_LORA_STEPS:
        raise ProbeUsageError(f"lora_steps must be 1..{MAX_LORA_STEPS}")


def run_probes(
    request: ProbeRequest,
    *,
    backend: Any | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run or skip the inference and LoRA probes.

    ``backend`` is a test double with ``inference`` and ``lora_step``
    methods. The default backend is ``faustcoder.spark_torch``, imported
    only when a probe actually runs.
    """
    _check_probe_bounds(request)
    if not request.cuda_available:
        return {"inference": _skipped("no_cuda"), "lora_step": _skipped("no_cuda")}
    if request.model_path is None:
        return {
            "inference": _skipped("no_local_model"),
            "lora_step": _skipped("no_local_model"),
        }
    if (
        request.available_bytes is not None
        and request.available_bytes < request.memory_cap_bytes
    ):
        reason = "available_memory_below_cap"
        return {"inference": _skipped(reason), "lora_step": _skipped(reason)}
    if time.monotonic() >= request.deadline:
        return {"inference": _skipped("deadline"), "lora_step": _skipped("deadline")}
    model_config = config if config is not None else load_model_config(request.model_path)
    if model_config is None:
        reason = "config_incomplete"
        return {"inference": _skipped(reason), "lora_step": _skipped(reason)}
    estimate = estimate_decoder_weight_bytes(model_config)
    if estimate is None:
        return {
            "inference": _skipped("config_incomplete"),
            "lora_step": _skipped("config_incomplete"),
        }
    if estimate > request.memory_cap_bytes:
        return {
            "inference": _skipped("estimated_weights_exceed_memory_cap"),
            "lora_step": _skipped("estimated_weights_exceed_memory_cap"),
        }
    active = backend if backend is not None else _default_backend()
    inference = _call_backend(active.inference, request)
    if time.monotonic() >= request.deadline:
        return {"inference": inference, "lora_step": _skipped("deadline")}
    return {"inference": inference, "lora_step": _call_backend(active.lora_step, request)}


def _call_backend(method: Any, request: ProbeRequest) -> dict[str, Any]:
    try:
        result = method(request)
    except Exception as exc:
        return {
            "status": "error",
            "reason": type(exc).__name__,
            "tokens_per_second": None,
            "peak_memory_bytes": None,
        }
    if not isinstance(result, dict):
        return _skipped("backend_result")
    status = result.get("status")
    if status not in {"completed", "skipped", "error"}:
        return _skipped("backend_result")
    return {
        "status": status,
        "reason": result.get("reason"),
        "tokens_per_second": result.get("tokens_per_second"),
        "peak_memory_bytes": result.get("peak_memory_bytes"),
        "detail": result.get("detail") if isinstance(result.get("detail"), dict) else {},
    }


def _default_backend() -> Any:
    """One backend object so both probes share a single model load."""
    from faustcoder.spark_torch import TorchBackend

    return TorchBackend()


def stack_pin_allowed(diagnostics: Mapping[str, Any]) -> bool:
    """True only when both probes finished inside the memory cap."""
    probes = diagnostics.get("probes")
    limits = diagnostics.get("limits")
    if not isinstance(probes, Mapping) or not isinstance(limits, Mapping):
        return False
    cap = limits.get("memory_cap_bytes")
    if isinstance(cap, bool) or not isinstance(cap, int):
        return False
    for name in ("inference", "lora_step"):
        probe = probes.get(name)
        if not isinstance(probe, Mapping) or probe.get("status") != "completed":
            return False
        rate = probe.get("tokens_per_second")
        peak = probe.get("peak_memory_bytes")
        if isinstance(rate, bool) or not isinstance(rate, (int, float)):
            return False
        if isinstance(peak, bool) or not isinstance(peak, int):
            return False
        if rate <= 0 or peak < 0 or peak > cap:
            return False
    return True


def assemble_diagnostics(
    *,
    captured_at: str,
    fingerprint: Mapping[str, Any],
    measured_packages: Mapping[str, Any],
    probes: Mapping[str, Any],
    limits: Mapping[str, Any],
    local_model: Mapping[str, str] | None,
) -> dict[str, Any]:
    """Build the SPECULATIVE diagnostics payload."""
    payload: dict[str, Any] = {
        "kind": DIAGNOSTICS_KIND,
        "contract": None,
        "contract_note": CONTRACT_NOTE,
        "captured_at": captured_at,
        "declared_pins": dict(ADR0004_PINS),
        "fingerprint": dict(fingerprint),
        "measured_packages": dict(measured_packages),
        "probes": dict(probes),
        "limits": dict(limits),
        "local_model": dict(local_model) if local_model is not None else None,
        "stack_pin_allowed": False,
    }
    payload["stack_pin_allowed"] = stack_pin_allowed(payload)
    return payload


def environment_guard(diagnostics: Mapping[str, Any]) -> list[str]:
    """Return R-001 guard failures. An empty list means the guard passed."""
    reasons: list[str] = []
    if diagnostics.get("kind") != DIAGNOSTICS_KIND:
        reasons.append("diagnostics kind is not environment_diagnostics")
    if diagnostics.get("contract") is not None:
        reasons.append("diagnostics contract must stay unset until a schema exists")
    fingerprint = diagnostics.get("fingerprint")
    if not isinstance(fingerprint, Mapping):
        return reasons + ["fingerprint is missing"]
    arch = fingerprint.get("arch")
    if arch not in {"aarch64", "arm64"}:
        reasons.append("arch is not aarch64")
    gpu_name = fingerprint.get("gpu_name")
    if not isinstance(gpu_name, str) or _SPARK_GPU_RE.search(gpu_name) is None:
        reasons.append("gpu name is not DGX Spark, GB10, or Grace Blackwell")
    if fingerprint.get("cuda_available") is not True:
        reasons.append("cuda is not available")
    if not _nonempty_str(fingerprint.get("cuda_version")):
        reasons.append("cuda version is not recorded")
    if not _nonempty_str(fingerprint.get("torch_version")):
        reasons.append("torch version is not recorded")
    if not _nonempty_str(fingerprint.get("python")):
        reasons.append("python version is not recorded")
    memory = fingerprint.get("memory_total_bytes")
    if isinstance(memory, bool) or not isinstance(memory, int):
        reasons.append("memory total is not a byte count")
    elif memory < MIN_UNIFIED_MEMORY_BYTES:
        reasons.append("unified memory is below 100 GiB")
    if fingerprint.get("nvidia_smi") == "ok":
        if not _nonempty_str(fingerprint.get("driver_version")):
            reasons.append("driver version is not recorded")
    elif fingerprint.get("memory_source") != "meminfo":
        reasons.append("memory source is not meminfo when nvidia-smi is unavailable")
    if diagnostics.get("declared_pins") != ADR0004_PINS:
        reasons.append("declared pins do not match ADR-0004")
    limits = diagnostics.get("limits")
    if not isinstance(limits, Mapping):
        reasons.append("limits are missing")
    else:
        if limits.get("network") is not False:
            reasons.append("network is enabled")
        seconds = limits.get("max_seconds")
        if isinstance(seconds, bool) or not isinstance(seconds, int):
            reasons.append("probe duration is outside 1..600 seconds")
        elif not 1 <= seconds <= MAX_PROBE_SECONDS:
            reasons.append("probe duration is outside 1..600 seconds")
        cap = limits.get("memory_cap_bytes")
        if isinstance(cap, bool) or not isinstance(cap, int):
            reasons.append("memory cap is outside 1 byte..96 GiB")
        elif not 1 <= cap <= MAX_MEMORY_CAP_BYTES:
            reasons.append("memory cap is outside 1 byte..96 GiB")
    probes = diagnostics.get("probes")
    if not isinstance(probes, Mapping) or not {"inference", "lora_step"} <= set(probes):
        reasons.append("probes are incomplete")
    if diagnostics.get("stack_pin_allowed") is not stack_pin_allowed(diagnostics):
        reasons.append("stack_pin_allowed does not match probe results")
    packages = diagnostics.get("measured_packages")
    torch_pkg = packages.get("torch") if isinstance(packages, Mapping) else None
    if (
        isinstance(torch_pkg, Mapping)
        and torch_pkg.get("status") == "installed"
        and torch_pkg.get("version") != fingerprint.get("torch_version")
    ):
        reasons.append("torch distribution version does not match the import")
    return reasons


def build_transition_receipt(
    *,
    actor: str,
    timestamp: str,
    diagnostics_digest: str,
) -> dict[str, Any]:
    """Return a TransitionReceipt payload for ``env_verified``."""
    return {
        "actor": actor,
        "timestamp": timestamp,
        "input_hashes": [diagnostics_digest],
        "machine": "training",
        "from": TrainingState.PLANNED.value,
        "event": TrainingEvent.ENV_VERIFIED.value,
        "to": TrainingState.ENV_VERIFIED.value,
        "disposition": "Record environment digest",
    }


def record_env_verified(
    store: ArtifactStore,
    diagnostics: Mapping[str, Any],
    *,
    actor: str,
    created_at: str,
    state: TrainingState = INITIAL_STATE,
) -> EnvVerifiedRecord:
    """Store diagnostics and, when the guard passes, the transition receipt.

    Each call is a new training-machine subject that starts at
    ``PLANNED``, unless ``state`` says otherwise. A repeat with the
    same payload is the store's idempotent put. A guard failure still
    keeps the diagnostics artifact and raises ``GuardRejected``.
    """
    if not _ACTOR_RE.fullmatch(actor):
        raise ProbeUsageError("actor must be 1..80 letters, digits, or _.:-")
    if _TIME_RE.fullmatch(created_at) is None:
        raise ProbeUsageError("created_at must be an RFC3339 timestamp")
    if transition_row(state, TrainingEvent.ENV_VERIFIED) is None:
        raise IllegalTransition(state, TrainingEvent.ENV_VERIFIED)
    payload = dict(diagnostics)
    envelope = build_envelope(
        schema_version=SCHEMA_VERSION,
        created_at=created_at,
        producer=PRODUCER,
        parents=[],
        payload=payload,
    )
    diagnostics_id = store.put(envelope)
    reasons = environment_guard(payload)
    if reasons:
        raise GuardRejected(
            reasons,
            diagnostics_digest=envelope["content_digest"],
            diagnostics_id=diagnostics_id,
        )
    receipt_payload = build_transition_receipt(
        actor=actor,
        timestamp=created_at,
        diagnostics_digest=envelope["content_digest"],
    )
    validate(receipt_payload, TRANSITION_SCHEMA)
    receipt = build_envelope(
        schema_version=SCHEMA_VERSION,
        created_at=created_at,
        producer=PRODUCER,
        parents=[envelope["content_digest"]],
        payload=receipt_payload,
    )
    receipt_id = store.put(receipt)
    return EnvVerifiedRecord(
        state=TrainingState.ENV_VERIFIED,
        diagnostics_id=diagnostics_id,
        diagnostics_digest=envelope["content_digest"],
        receipt_id=receipt_id,
        receipt_digest=receipt["content_digest"],
    )


def assert_store_location(path: Path, *, cwd: Path | None = None) -> None:
    """Keep machine receipts out of git unless they are under ``receipts/local``."""
    resolved = path.resolve()
    root = _git_root(cwd or Path.cwd())
    if root is None:
        return
    try:
        resolved.relative_to(root)
    except ValueError:
        return
    allowed = (root / "receipts" / "local").resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ProbeUsageError(
            "store path inside the git work tree must be under receipts/local/"
        ) from exc


def assert_local_model_path(raw: str) -> Path:
    """Accept an existing directory. Reject URLs and missing paths."""
    if "://" in raw or raw.startswith("hf:") or raw.startswith("http"):
        raise ProbeUsageError("model path must be a local directory, not a URL")
    path = Path(raw)
    if not path.is_dir():
        raise ProbeUsageError("model path must be an existing local directory")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry. Returns 0 on ``env_verified``, 2 when the guard fails, 1 on misuse."""
    force_offline_env()
    parser = _parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
        store_path = Path(args.store)
        assert_store_location(store_path)
        model_path = (
            assert_local_model_path(args.model_path) if args.model_path else None
        )
        _check_probe_bounds(
            ProbeRequest(
                model_path=model_path,
                cuda_available=False,
                memory_cap_bytes=args.memory_cap_mib * 1024**2,
                available_bytes=None,
                max_seconds=args.max_seconds,
                seq_len=args.seq_len,
                max_new_tokens=args.max_new_tokens,
                lora_rank=args.lora_rank,
                lora_steps=args.lora_steps,
                deadline=time.monotonic() + args.max_seconds,
            )
        )
    except ProbeUsageError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    created_at = args.created_at or _utc_now()
    fingerprint = collect_fingerprint()
    packages = measure_packages()
    deadline = time.monotonic() + args.max_seconds
    request = ProbeRequest(
        model_path=model_path,
        cuda_available=bool(fingerprint.get("cuda_available")),
        memory_cap_bytes=args.memory_cap_mib * 1024**2,
        available_bytes=fingerprint.get("memory_available_bytes"),
        max_seconds=args.max_seconds,
        seq_len=args.seq_len,
        max_new_tokens=args.max_new_tokens,
        lora_rank=args.lora_rank,
        lora_steps=args.lora_steps,
        deadline=deadline,
    )
    probes = run_probes(request)
    diagnostics = assemble_diagnostics(
        captured_at=created_at,
        fingerprint=fingerprint,
        measured_packages=packages,
        probes=probes,
        limits={
            "max_seconds": args.max_seconds,
            "memory_cap_bytes": args.memory_cap_mib * 1024**2,
            "network": False,
        },
        local_model=local_model_record(model_path),
    )
    store = ArtifactStore(store_path)
    try:
        record = record_env_verified(
            store,
            diagnostics,
            actor=args.actor,
            created_at=created_at,
        )
    except GuardRejected as exc:
        _emit_result(
            status="guard_rejected",
            reasons=exc.reasons,
            diagnostics_digest=exc.diagnostics_digest,
            receipt_digest=None,
        )
        return 2
    except (IllegalTransition, ProbeUsageError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    _emit_result(
        status="env_verified",
        reasons=[],
        diagnostics_digest=record.diagnostics_digest,
        receipt_digest=record.receipt_digest,
    )
    return 0


def _emit_result(
    *,
    status: str,
    reasons: list[str],
    diagnostics_digest: str | None,
    receipt_digest: str | None,
) -> None:
    json.dump(
        {
            "status": status,
            "reasons": reasons,
            "diagnostics_digest": diagnostics_digest,
            "receipt_digest": receipt_digest,
        },
        sys.stdout,
        indent=2,
        sort_keys=True,
    )
    sys.stdout.write("\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="faustcoder.spark_probe",
        description=(
            "Record a DGX Spark environment digest and, when the R-001 "
            "guard passes, an env_verified transition receipt."
        ),
    )
    parser.add_argument(
        "--store",
        default="receipts/local/T09",
        help="artifact store directory (default: receipts/local/T09)",
    )
    parser.add_argument("--actor", default=PRODUCER)
    parser.add_argument("--created-at", default=None)
    parser.add_argument("--max-seconds", type=int, default=DEFAULT_PROBE_SECONDS)
    parser.add_argument(
        "--memory-cap-mib",
        type=int,
        default=DEFAULT_MEMORY_CAP_BYTES // 1024**2,
    )
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--seq-len", type=int, default=DEFAULT_SEQ_LEN)
    parser.add_argument("--max-new-tokens", type=int, default=DEFAULT_NEW_TOKENS)
    parser.add_argument("--lora-rank", type=int, default=DEFAULT_LORA_RANK)
    parser.add_argument("--lora-steps", type=int, default=DEFAULT_LORA_STEPS)
    return parser


def _nonempty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _platform_info() -> dict[str, str]:
    return {
        "arch": platform.machine(),
        "system": platform.system(),
        "kernel": platform.release(),
        "python": platform.python_version(),
        "node": platform.node(),
    }


def _read_meminfo() -> str:
    path = Path("/proc/meminfo")
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _parse_meminfo(text: str) -> dict[str, int | None]:
    found: dict[str, int] = {}
    for line in text.splitlines():
        key, sep, rest = line.partition(":")
        if sep != ":":
            continue
        parts = rest.split()
        if len(parts) < 2 or parts[1] != "kB":
            continue
        try:
            found[key] = int(parts[0]) * 1024
        except ValueError:
            continue
    return {
        "total_bytes": found.get("MemTotal"),
        "available_bytes": found.get("MemAvailable"),
    }


def _nvidia_smi() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version",
                "--format=csv,noheader",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {"status": "unavailable", "gpu_name": None, "driver_version": None}
    if completed.returncode != 0:
        return {"status": "unavailable", "gpu_name": None, "driver_version": None}
    line = completed.stdout.splitlines()[0] if completed.stdout.splitlines() else ""
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return {"status": "unavailable", "gpu_name": None, "driver_version": None}
    return {"status": "ok", "gpu_name": parts[0], "driver_version": parts[1]}


def _torch_fingerprint() -> dict[str, Any]:
    try:
        import torch
    except ImportError:
        return _empty_torch()
    except Exception as exc:
        facts = _empty_torch()
        facts["error_type"] = type(exc).__name__
        return facts
    cuda = bool(torch.cuda.is_available())
    name = None
    count = 0
    if cuda:
        count = int(torch.cuda.device_count())
        if count:
            name = str(torch.cuda.get_device_name(0))
    cuda_version = torch.version.cuda
    return {
        "imported": True,
        "error_type": None,
        "version": str(torch.__version__),
        "cuda_available": cuda,
        "cuda_version": str(cuda_version) if cuda_version else None,
        "gpu_name": name,
        "gpu_count": count,
    }


def _empty_torch() -> dict[str, Any]:
    return {
        "imported": False,
        "error_type": None,
        "version": None,
        "cuda_available": False,
        "cuda_version": None,
        "gpu_name": None,
        "gpu_count": 0,
    }


def _git_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


if __name__ == "__main__":
    raise SystemExit(main())

"""Shared builders for the spec 002 NVIDIA tests. Not a test module."""

from __future__ import annotations

from faustcoder import ArtifactStore, build_envelope
from faustcoder.nvidia.container_pin import ImagePin, record_container_pin
from faustcoder.spark_probe import assemble_diagnostics
from tests.support import DIGEST_A, DIGEST_B

GIB = 1024**3
T0 = "2026-10-01T00:00:00Z"
T1 = "2026-10-02T00:00:00Z"
T2 = "2026-10-03T00:00:00Z"
T3 = "2026-10-04T00:00:00Z"
T4 = "2026-10-05T00:00:00Z"
T5 = "2026-10-06T00:00:00Z"
REVISION = "0123456789abcdef0123456789abcdef01234567"
PIN = ImagePin("nvidia/pytorch", "25.09-py3", DIGEST_A, "image_inspect")
OTHER_PIN = ImagePin("nvidia/pytorch", "25.10-py3", DIGEST_B, "image_inspect")
# Repositories and tags as published on NGC; the digests are test values.
AUTOMODEL_PIN = ImagePin("nvidia/nemo-automodel", "26.10.00", DIGEST_A, "image_inspect")
NIM_PIN = ImagePin("nim/nvidia/vllm-model-free-nim", "2.1.4", DIGEST_B, "image_inspect")


def put_plain(
    store: ArtifactStore, payload: dict[str, object], parents: list[str], created_at: str
) -> str:
    """Store a non-receipt envelope and return its content digest."""
    envelope = build_envelope(
        schema_version="0.1.0",
        created_at=created_at,
        producer="nvidia-test",
        parents=parents,
        payload=payload,
    )
    return "sha256:" + store.put(envelope)


def spark_diagnostics(gpu_name: str = "NVIDIA GB10", arch: str = "aarch64") -> dict[str, object]:
    """Return environment diagnostics that pass the R-001 guard on a Spark."""
    skipped = {
        "status": "skipped",
        "reason": "no_local_model",
        "tokens_per_second": None,
        "peak_memory_bytes": None,
    }
    packages: dict[str, object] = {
        name: {"status": "not_installed", "version": None}
        for name in ("transformers", "peft", "trl", "vllm", "bitsandbytes", "unsloth")
    }
    packages["torch"] = {"status": "installed", "version": "2.7.0"}
    fingerprint = {
        "arch": arch,
        "system": "Linux",
        "kernel": "6.11.0",
        "python": "3.12.3",
        "node": "spark-a",
        "gpu_name": gpu_name,
        "gpu_count": 1,
        "cuda_available": True,
        "cuda_version": "13.0",
        "torch_version": "2.7.0",
        "torch_imported": True,
        "torch_error_type": None,
        "driver_version": "570.00",
        "nvidia_smi": "ok",
        "memory_total_bytes": 128 * GIB,
        "memory_available_bytes": 96 * GIB,
        "memory_source": "meminfo",
    }
    return assemble_diagnostics(
        captured_at=T0,
        fingerprint=fingerprint,
        measured_packages=packages,
        probes={"inference": skipped, "lora_step": skipped},
        limits={"max_seconds": 60, "memory_cap_bytes": 4 * GIB, "network": False},
        local_model=None,
    )


def training_run(dataset: str, tag: str = "run-1") -> dict[str, object]:
    """Return a TrainingRun payload with empty metrics."""
    return {
        "run_id": tag,
        "base_model_revision": f"Qwen/Qwen2.5-Coder-1.5B@{REVISION}",
        "dataset_digest": dataset,
        "split_digest": DIGEST_B,
        "config_digest": DIGEST_A,
        "code_revision": "0000000",
        "hardware_profile": {"name": "spark"},
        "checkpoint_digests": [DIGEST_B],
        "metrics": {},
    }


def stored_pin(store: ArtifactStore, *, host: str | None = None, pin: ImagePin = PIN) -> str:
    """Store a ContainerPinReceipt at T1 and return its digest."""
    return "sha256:" + record_container_pin(
        store, pin, host_fingerprint_digest=host, created_at=T1
    )

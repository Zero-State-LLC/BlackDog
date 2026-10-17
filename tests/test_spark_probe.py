"""CPU tests for the Spark probe, R-001 guard, and env_verified receipt."""

from __future__ import annotations

import json
import platform
import socket
import time
from pathlib import Path

import pytest

from faustcoder import ArtifactStore, SchemaValidationError, validate
from faustcoder.spark_probe import (
    ADR0004_PINS,
    MAX_MEMORY_CAP_BYTES,
    MAX_PROBE_SECONDS,
    MIN_UNIFIED_MEMORY_BYTES,
    NOMINAL_UNIFIED_BYTES,
    OS_HEADROOM_BYTES,
    ProbeRequest,
    ProbeUsageError,
    assemble_diagnostics,
    assert_local_model_path,
    collect_fingerprint,
    config_sha256,
    default_memory_cap_bytes,
    environment_guard,
    estimate_decoder_weight_bytes,
    local_model_record,
    main,
    measure_packages,
    record_env_verified,
    run_probes,
)
from faustcoder.training_machine import (
    GuardRejected,
    IllegalTransition,
    TrainingState,
)

TS = "2026-10-17T00:00:00Z"
ACTOR = "ci-operator"
GIB = 1024**3


def _fingerprint(**overrides: object) -> dict:
    base = {
        "arch": "aarch64",
        "system": "Linux",
        "kernel": "6.11.0",
        "python": "3.12.3",
        "node": "spark-a",
        "gpu_name": "NVIDIA GB10",
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
    base.update(overrides)
    return base


def _packages() -> dict:
    packages = {
        name: {"status": "not_installed", "version": None}
        for name in (
            "torch",
            "transformers",
            "peft",
            "trl",
            "vllm",
            "bitsandbytes",
            "unsloth",
        )
    }
    packages["torch"] = {"status": "installed", "version": "2.7.0"}
    return packages


def _limits(**overrides: object) -> dict:
    base = {
        "max_seconds": 60,
        "memory_cap_bytes": 4 * GIB,
        "network": False,
    }
    base.update(overrides)
    return base


def _skipped(reason: str) -> dict:
    return {
        "status": "skipped",
        "reason": reason,
        "tokens_per_second": None,
        "peak_memory_bytes": None,
    }


def _completed(rate: float = 12.5, peak: int = 1024) -> dict:
    return {
        "status": "completed",
        "reason": None,
        "tokens_per_second": rate,
        "peak_memory_bytes": peak,
        "detail": {"method": "test"},
    }


def _diagnostics(**overrides: object) -> dict:
    payload = assemble_diagnostics(
        captured_at=TS,
        fingerprint=_fingerprint(),
        measured_packages=_packages(),
        probes={"inference": _skipped("no_local_model"), "lora_step": _skipped("no_local_model")},
        limits=_limits(),
        local_model=None,
    )
    payload.update(overrides)
    return payload


def _request(tmp_path: Path, **overrides: object) -> ProbeRequest:
    fields: dict = {
        "model_path": tmp_path,
        "cuda_available": True,
        "memory_cap_bytes": 4 * GIB,
        "available_bytes": 64 * GIB,
        "max_seconds": 60,
        "seq_len": 32,
        "max_new_tokens": 16,
        "lora_rank": 4,
        "lora_steps": 1,
        "deadline": time.monotonic() + 30,
    }
    fields.update(overrides)
    return ProbeRequest(**fields)


class _Backend:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def inference(self, _request: ProbeRequest) -> dict:
        self.calls.append("inference")
        return _completed()

    def lora_step(self, _request: ProbeRequest) -> dict:
        self.calls.append("lora_step")
        return _completed(9.0, 2048)


def test_weight_estimate_matches_the_decoder_formula() -> None:
    config = {
        "hidden_size": 32,
        "num_hidden_layers": 1,
        "vocab_size": 16,
        "intermediate_size": 64,
        "num_attention_heads": 4,
        "num_key_value_heads": 2,
        "tie_word_embeddings": True,
    }
    # attn = 32*32 + 2*32*16 + 32*32 = 3072; mlp = 3*32*64 = 6144
    # embed = 16*32 = 512; params = 512 + 9216 = 9728; bf16 * 1.15
    assert estimate_decoder_weight_bytes(config) == 22375
    untied = dict(config)
    untied["tie_word_embeddings"] = False
    assert estimate_decoder_weight_bytes(untied) == 23552
    assert estimate_decoder_weight_bytes({"hidden_size": 32}) is None


def test_guard_accepts_a_mocked_spark_fingerprint() -> None:
    assert environment_guard(_diagnostics()) == []
    assert MIN_UNIFIED_MEMORY_BYTES == 100 * GIB
    assert NOMINAL_UNIFIED_BYTES == 128 * GIB
    assert OS_HEADROOM_BYTES == 8 * GIB
    assert MAX_MEMORY_CAP_BYTES == 120 * GIB
    assert MAX_PROBE_SECONDS == 600
    assert environment_guard(_diagnostics(limits=_limits(memory_cap_bytes=120 * GIB))) == []
    over = _diagnostics(limits=_limits(memory_cap_bytes=120 * GIB + 1))
    assert any("memory cap is outside" in item for item in environment_guard(over))


def test_default_memory_cap_leaves_os_headroom() -> None:
    assert default_memory_cap_bytes(128 * GIB) == 120 * GIB
    assert default_memory_cap_bytes(121 * GIB) == 113 * GIB
    assert default_memory_cap_bytes(16 * GIB) == 8 * GIB
    assert default_memory_cap_bytes(256 * GIB) == 120 * GIB
    assert default_memory_cap_bytes(None) == 120 * GIB
    assert default_memory_cap_bytes(OS_HEADROOM_BYTES) == 120 * GIB


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("arch", "x86_64", "arch is not aarch64"),
        ("gpu_name", "NVIDIA GB100", "gpu name is not DGX Spark"),
        ("gpu_name", "NVIDIA H100", "gpu name is not DGX Spark"),
        ("cuda_available", False, "cuda is not available"),
        ("cuda_version", "", "cuda version is not recorded"),
        ("torch_version", None, "torch version is not recorded"),
        ("memory_total_bytes", 64 * GIB, "unified memory is below 100 GiB"),
    ],
)
def test_guard_rejects_a_non_spark_fingerprint(field: str, value: object, reason: str) -> None:
    diagnostics = _diagnostics()
    diagnostics["fingerprint"] = {**diagnostics["fingerprint"], field: value}
    reasons = environment_guard(diagnostics)
    assert any(reason in item for item in reasons)


def test_grace_blackwell_name_passes_and_pins_are_exact() -> None:
    diagnostics = _diagnostics()
    diagnostics["fingerprint"] = {
        **diagnostics["fingerprint"],
        "gpu_name": "NVIDIA Grace Blackwell Superchip",
    }
    assert environment_guard(diagnostics) == []
    diagnostics["declared_pins"] = {**ADR0004_PINS, "faust_native": "2.81.0"}
    assert "declared pins do not match ADR-0004" in environment_guard(diagnostics)


def test_network_and_inconsistent_stack_flag_fail_the_guard() -> None:
    networked = _diagnostics(limits=_limits(network=True))
    assert "network is enabled" in environment_guard(networked)
    forged = _diagnostics()
    forged["stack_pin_allowed"] = True
    assert "stack_pin_allowed does not match probe results" in environment_guard(forged)


def test_completed_probes_under_the_cap_allow_a_stack_pin() -> None:
    diagnostics = assemble_diagnostics(
        captured_at=TS,
        fingerprint=_fingerprint(),
        measured_packages=_packages(),
        probes={"inference": _completed(), "lora_step": _completed()},
        limits=_limits(),
        local_model={"basename": "Qwen2.5-Coder-1.5B"},
    )
    assert diagnostics["stack_pin_allowed"] is True
    assert environment_guard(diagnostics) == []
    over = assemble_diagnostics(
        captured_at=TS,
        fingerprint=_fingerprint(),
        measured_packages=_packages(),
        probes={
            "inference": _completed(peak=8 * GIB),
            "lora_step": _completed(),
        },
        limits=_limits(memory_cap_bytes=4 * GIB),
        local_model=None,
    )
    assert over["stack_pin_allowed"] is False


def test_record_env_verified_stores_a_transition_receipt(store: ArtifactStore) -> None:
    record = record_env_verified(
        store, _diagnostics(), actor=ACTOR, created_at=TS
    )
    assert record.state is TrainingState.ENV_VERIFIED
    assert store.list() == sorted([record.diagnostics_id, record.receipt_id])
    receipt = store.get(record.receipt_id)
    assert receipt["parents"] == [record.diagnostics_digest]
    assert receipt["payload"]["from"] == "PLANNED"
    assert receipt["payload"]["event"] == "env_verified"
    assert receipt["payload"]["to"] == "ENV_VERIFIED"
    assert receipt["payload"]["machine"] == "training"
    assert receipt["payload"]["disposition"] == "Record environment digest"
    assert receipt["payload"]["input_hashes"] == [record.diagnostics_digest]
    validate(receipt["payload"], "transition-receipt.schema.json")
    diagnostics = store.get(record.diagnostics_id)["payload"]
    assert diagnostics["contract"] is None
    assert "SPECULATIVE" in diagnostics["contract_note"]
    with pytest.raises(SchemaValidationError):
        validate(diagnostics, "transition-receipt.schema.json")
    again = record_env_verified(store, _diagnostics(), actor=ACTOR, created_at=TS)
    assert again.receipt_id == record.receipt_id
    assert len(store.list()) == 2


def test_guard_failure_keeps_diagnostics_and_skips_the_receipt(
    store: ArtifactStore,
) -> None:
    diagnostics = _diagnostics()
    diagnostics["fingerprint"] = {**diagnostics["fingerprint"], "arch": "x86_64"}
    with pytest.raises(GuardRejected) as caught:
        record_env_verified(store, diagnostics, actor=ACTOR, created_at=TS)
    assert store.list() == [caught.value.diagnostics_id]
    assert caught.value.diagnostics_digest is not None
    assert store.get(caught.value.diagnostics_id)["payload"]["kind"] == (
        "environment_diagnostics"
    )


def test_env_verified_from_a_later_state_writes_nothing(store: ArtifactStore) -> None:
    with pytest.raises(IllegalTransition):
        record_env_verified(
            store,
            _diagnostics(),
            actor=ACTOR,
            created_at=TS,
            state=TrainingState.RUNNING,
        )
    assert store.list() == []


def test_fingerprint_uses_meminfo_when_nvidia_smi_is_unavailable() -> None:
    fingerprint = collect_fingerprint(
        platform_info={
            "arch": "aarch64",
            "system": "Linux",
            "kernel": "k",
            "python": "3.12.3",
            "node": "spark-a",
        },
        meminfo_text="MemTotal: 134217728 kB\nMemAvailable: 100000000 kB\n",
        nvidia_smi=lambda: {
            "status": "unavailable",
            "gpu_name": None,
            "driver_version": None,
        },
        torch_info=lambda: {
            "imported": True,
            "torch_version": "2.7.0",
            "cuda_available": True,
            "cuda_version": "13.0",
            "gpu_name": "NVIDIA GB10",
            "gpu_count": 1,
        },
    )
    assert fingerprint["memory_source"] == "meminfo"
    assert fingerprint["memory_total_bytes"] == 128 * GIB
    assert fingerprint["gpu_name"] == "NVIDIA GB10"
    assert fingerprint["nvidia_smi"] == "unavailable"
    assert fingerprint["driver_version"] is None


def test_fingerprint_does_not_copy_secrets_or_open_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "scrub-check-token")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "scrub-check-secret")

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("socket opened")

    monkeypatch.setattr(socket, "socket", boom)
    fingerprint = collect_fingerprint(
        platform_info={
            "arch": "x86_64",
            "system": "Linux",
            "kernel": "k",
            "python": "3.12.3",
            "node": "ci",
        },
        meminfo_text="MemTotal: 1024 kB\nMemAvailable: 512 kB\n",
        nvidia_smi=lambda: {
            "status": "unavailable",
            "gpu_name": None,
            "driver_version": None,
        },
        torch_info=lambda: {"imported": False, "cuda_available": False, "gpu_count": 0},
    )
    blob = json.dumps(fingerprint)
    assert "scrub-check-token" not in blob
    assert "scrub-check-secret" not in blob


def test_local_model_record_keeps_the_basename_and_config_digest(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text('{"hidden_size": 32}\n', encoding="utf-8")
    record = local_model_record(tmp_path)
    assert record is not None
    assert record["basename"] == tmp_path.name
    assert record["config_sha256"] == config_sha256(tmp_path)
    assert str(tmp_path) not in json.dumps(record)
    with pytest.raises(ProbeUsageError):
        assert_local_model_path("https://example.com/weights")
    with pytest.raises(ProbeUsageError):
        assert_local_model_path(str(tmp_path / "missing"))


def test_probes_skip_without_cuda_or_a_fitting_model(tmp_path: Path) -> None:
    backend = _Backend()
    skipped = run_probes(
        _request(tmp_path, cuda_available=False, model_path=None),
        backend=backend,
    )
    assert skipped["inference"]["reason"] == "no_cuda"
    assert backend.calls == []
    no_model = run_probes(
        _request(tmp_path, model_path=None),
        backend=backend,
    )
    assert no_model["inference"]["reason"] == "no_local_model"
    assert backend.calls == []
    low_memory = run_probes(
        _request(tmp_path, available_bytes=1024),
        backend=backend,
    )
    assert low_memory["lora_step"]["reason"] == "available_memory_below_cap"
    assert backend.calls == []
    too_big = run_probes(
        _request(tmp_path, memory_cap_bytes=1000),
        backend=backend,
        config={
            "hidden_size": 32,
            "num_hidden_layers": 1,
            "vocab_size": 16,
            "intermediate_size": 64,
            "num_attention_heads": 4,
            "num_key_value_heads": 2,
            "tie_word_embeddings": True,
        },
    )
    assert too_big["inference"]["reason"] == "estimated_weights_exceed_memory_cap"
    assert backend.calls == []
    late = run_probes(
        _request(tmp_path, deadline=time.monotonic() - 1),
        backend=backend,
        config={"hidden_size": 1},
    )
    assert late["inference"]["reason"] == "deadline"
    assert backend.calls == []


def test_probes_call_the_backend_only_after_the_gates_pass(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "hidden_size": 32,
                "num_hidden_layers": 1,
                "vocab_size": 16,
                "intermediate_size": 64,
                "num_attention_heads": 4,
                "num_key_value_heads": 2,
                "tie_word_embeddings": True,
            }
        ),
        encoding="utf-8",
    )
    backend = _Backend()
    result = run_probes(
        _request(tmp_path, memory_cap_bytes=1 * GIB),
        backend=backend,
    )
    assert backend.calls == ["inference", "lora_step"]
    assert result["inference"]["status"] == "completed"
    assert result["lora_step"]["tokens_per_second"] == 9.0


def test_importing_the_torch_backend_does_not_import_torch() -> None:
    import sys

    sys.modules.pop("torch", None)
    import faustcoder.spark_torch as spark_torch

    assert spark_torch.TorchBackend is not None
    assert "torch" not in sys.modules


def test_cli_records_env_verified_from_a_canned_fingerprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "faustcoder.spark_probe.collect_fingerprint", lambda **_kwargs: _fingerprint()
    )
    monkeypatch.setattr(
        "faustcoder.spark_probe.measure_packages", lambda names=None: _packages()
    )
    code = main(
        [
            "--store",
            str(tmp_path / "store"),
            "--actor",
            ACTOR,
            "--created-at",
            TS,
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "env_verified"
    assert payload["receipt_digest"].startswith("sha256:")
    stored = ArtifactStore(tmp_path / "store")
    assert len(stored.list()) == 2
    again = main(
        [
            "--store",
            str(tmp_path / "store"),
            "--actor",
            ACTOR,
            "--created-at",
            TS,
        ]
    )
    assert again == 0
    assert len(stored.list()) == 2


def test_cli_on_this_host_does_not_pretend_to_be_a_spark(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--store", str(tmp_path / "store"), "--actor", ACTOR])
    if platform.machine() in {"aarch64", "arm64"}:
        pytest.skip("host architecture can satisfy part of the Spark guard")
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "guard_rejected"
    assert payload["receipt_digest"] is None
    assert "arch is not aarch64" in payload["reasons"]
    stored = ArtifactStore(tmp_path / "store")
    assert len(stored.list()) == 1


def test_cli_rejects_unsafe_arguments(tmp_path: Path) -> None:
    assert main(["--store", str(tmp_path / "store"), "--memory-cap-mib", "0"]) == 1
    assert main(["--store", str(tmp_path / "store"), "--memory-cap-mib", "200000"]) == 1
    assert main(["--store", str(tmp_path / "store"), "--max-seconds", "0"]) == 1
    assert main(["--store", str(tmp_path / "store"), "--max-seconds", "601"]) == 1
    assert (
        main(
            [
                "--store",
                str(tmp_path / "store"),
                "--model-path",
                "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B",
            ]
        )
        == 1
    )
    assert main(["--store", "receipts/T09", "--actor", ACTOR]) == 1
    assert measure_packages(("definitely-not-a-real-distribution",))[
        "definitely-not-a-real-distribution"
    ]["status"] == "not_installed"

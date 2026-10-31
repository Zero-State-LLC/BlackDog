"""N04 glue: NeMo AutoModel config, argv, attempt and TrainingRun lineage."""

from __future__ import annotations

from dataclasses import replace

import pytest

from faustcoder import ArtifactStore, SchemaValidationError
from faustcoder.nvidia.container_pin import IMAGE_ENV, pin_from_environment
from faustcoder.nvidia.graph import check_receipt_graph, load_nodes
from faustcoder.nvidia.nemo import (
    NeMoConfigError,
    NeMoOutcome,
    NeMoRunConfig,
    attempt_payload,
    config_digest,
    config_payload,
    launch_argv,
    record_attempt,
    training_run_parents,
    training_run_payload,
    validate_config,
)
from faustcoder.nvidia.receipts import ReceiptRuleError
from faustcoder.spark_probe import MAX_MEMORY_CAP_BYTES
from tests.nvidia_support import PIN, REVISION, T0, T2, T3, put_plain, stored_pin
from tests.support import DIGEST_A, DIGEST_B

GIB = 1024**3


def _config(dataset: str = DIGEST_B, **overrides: object) -> NeMoRunConfig:
    config = NeMoRunConfig(
        pin=PIN,
        dataset_snapshot_digest=dataset,
        base_model_repository="Qwen/Qwen2.5-Coder-1.5B",
        base_model_revision=REVISION,
        recipe_path="examples/llm_finetune/qwen/lora.yaml",
        recipe_digest=DIGEST_A,
        model_dir="/srv/models/qwen",
        data_dir="/srv/data/snapshot",
        output_dir="/srv/out/run-1",
    )
    return replace(config, **overrides)


DONE = NeMoOutcome("completed", 40 * GIB, (DIGEST_B,), DIGEST_A)


def test_default_cap_is_r001() -> None:
    assert _config().memory_cap_bytes == MAX_MEMORY_CAP_BYTES == 120 * GIB
    validate_config(_config())


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"memory_cap_bytes": 121 * GIB}, "120 GiB"),
        ({"memory_cap_bytes": 0}, "120 GiB"),
        ({"method": "dpo"}, "method"),
        ({"export_format": "nemo"}, "export_format"),
        ({"max_steps": 0}, "max_steps"),
        ({"seed": -1}, "seed"),
        ({"base_model_revision": "main"}, "40-hex"),
        ({"dataset_snapshot_digest": "latest"}, "dataset_snapshot_digest"),
        ({"recipe_digest": "x"}, "recipe_digest"),
        ({"recipe_path": "../etc/recipe.yaml"}, "recipe_path"),
        ({"model_dir": "relative"}, "absolute"),
        ({"output_dir": "/srv/a:/b"}, "absolute"),
        ({"data_dir": "/srv/../etc"}, "absolute"),
        ({"extra_overrides": {"Bad Key": "1"}}, "dotted"),
        ({"extra_overrides": {"rng.seed": "7"}}, "may not change"),
    ],
)
def test_config_rules(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(NeMoConfigError, match=message):
        validate_config(_config(**overrides))


def test_config_digest_is_stable_and_host_path_free() -> None:
    payload = config_payload(_config())
    assert "/srv" not in str(payload)
    assert config_digest(_config()) == config_digest(_config(model_dir="/other/model"))
    assert config_digest(_config()) != config_digest(_config(seed=1))


def test_launch_argv_is_offline_capped_and_pinned() -> None:
    argv = launch_argv(_config(extra_overrides={"peft.dim": "8"}))
    assert argv[:9] == [
        "docker",
        "run",
        "--rm",
        "--gpus",
        "all",
        "--network",
        "none",
        "--memory",
        str(120 * GIB),
    ]
    assert argv[argv.index("--memory-swap") + 1] == str(120 * GIB)
    assert "HF_HUB_OFFLINE=1" in argv and "TRANSFORMERS_OFFLINE=1" in argv
    assert "/srv/models/qwen:/model:ro" in argv and "/srv/data/snapshot:/data:ro" in argv
    image = argv.index(PIN.reference)
    assert argv[image + 1 : image + 5] == [
        "automodel",
        "examples/llm_finetune/qwen/lora.yaml",
        "--nproc-per-node",
        "1",
    ]
    tail = argv[image + 5 :]
    assert dict(zip(tail[::2], tail[1::2], strict=True))["--step_scheduler.max_steps"] == "20"
    assert dict(zip(tail[::2], tail[1::2], strict=True))["--peft.dim"] == "8"
    env = next(item for item in argv if item.startswith(IMAGE_ENV + "="))
    assert pin_from_environment({IMAGE_ENV: env.split("=", 1)[1]}) is not None


def test_attempt_records_no_grade() -> None:
    payload = attempt_payload(_config(), DONE, container_pin_digest=DIGEST_A)
    assert payload["grading_authority"] == "faustwasm"
    assert not {"reward", "passed", "metrics", "score"} & set(payload)
    with pytest.raises(ReceiptRuleError, match="cannot exceed"):
        attempt_payload(
            _config(), replace(DONE, peak_memory_bytes=121 * GIB), container_pin_digest=DIGEST_A
        )


def test_training_run_parents_include_pin_and_dataset(store: ArtifactStore) -> None:
    dataset = put_plain(store, {"snapshot": "frozen"}, [], T0)
    pin = stored_pin(store)
    payload = attempt_payload(_config(dataset), DONE, container_pin_digest=pin)
    attempt = "sha256:" + record_attempt(store, payload, created_at=T2)
    parents = training_run_parents(attempt, payload)
    assert parents == [attempt, pin, dataset]
    run_payload = training_run_payload(
        payload,
        run_id="run-1",
        split_digest=DIGEST_B,
        code_revision="0000000",
        hardware_profile={"name": "spark"},
    )
    assert run_payload["metrics"] == {}
    assert run_payload["dataset_digest"] == dataset
    assert run_payload["checkpoint_digests"] == [DIGEST_B]
    put_plain(store, run_payload, parents, T3)
    assert check_receipt_graph(load_nodes(store)).ok


def test_only_completed_attempts_become_runs() -> None:
    failed = attempt_payload(
        _config(), NeMoOutcome("failed", None, (), None), container_pin_digest=DIGEST_A
    )
    with pytest.raises(ReceiptRuleError, match="only a completed attempt"):
        training_run_payload(
            failed, run_id="r", split_digest=DIGEST_B, code_revision="0", hardware_profile={}
        )
    with pytest.raises(ReceiptRuleError, match="needs a NeMoTrainingAttempt"):
        training_run_payload(
            {
                "kind": "ExternalCapacityReceipt",
                "program": "nvidia-inception",
                "resource": "cloud_credits",
                "provider": "p",
                "gpu_type": "H100",
                "gpu_hours": 1,
                "statement_digest": None,
            },
            run_id="r",
            split_digest=DIGEST_B,
            code_revision="0",
            hardware_profile={},
        )
    with pytest.raises(SchemaValidationError):
        training_run_payload(
            attempt_payload(_config(), DONE, container_pin_digest=DIGEST_A),
            run_id="r",
            split_digest="bad",
            code_revision="0",
            hardware_profile={},
        )

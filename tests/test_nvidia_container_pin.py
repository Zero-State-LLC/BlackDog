"""N03: container pin capture from inspect output or the environment."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from faustcoder import ArtifactStore
from faustcoder.nvidia.container_pin import (
    IMAGE_ENV,
    ContainerPinError,
    ImagePin,
    UnpinnedRuntimeError,
    container_pin_payload,
    image_id,
    in_container,
    inspect_container,
    inspect_image,
    parse_image_reference,
    pin_from_environment,
    pin_from_image_inspect,
    record_container_pin,
    require_pinned_runtime,
    verify_container,
    verify_running_digest,
)
from faustcoder.nvidia.receipts import validate_receipt_payload
from tests.nvidia_support import PIN, T0, T1, put_plain
from tests.support import DIGEST_A, DIGEST_B

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "nvidia"
DOCKER = (FIXTURES / "docker-image-inspect.json").read_text(encoding="utf-8")
PODMAN = (FIXTURES / "podman-image-inspect.json").read_text(encoding="utf-8")
DOCKER_RUN = (FIXTURES / "docker-container-inspect.json").read_text(encoding="utf-8")
PODMAN_RUN = (FIXTURES / "podman-container-inspect.json").read_text(encoding="utf-8")
PINNED = f"nvcr.io/nvidia/pytorch:25.09-py3@{DIGEST_A}"
INDEX_DIGEST = "sha256:" + "1" * 64


def test_parse_reference() -> None:
    assert parse_image_reference(PINNED) == ("nvidia/pytorch", "25.09-py3", DIGEST_A)
    assert parse_image_reference("nvcr.io/nvidia/nemo-automodel:25.11") == (
        "nvidia/nemo-automodel",
        "25.11",
        None,
    )
    with pytest.raises(ContainerPinError, match="registry must be nvcr.io"):
        parse_image_reference("docker.io/library/python:3.12")
    with pytest.raises(ContainerPinError, match="not an image reference"):
        parse_image_reference("pytorch")


def test_docker_inspect_uses_repo_digest_not_id() -> None:
    pin = pin_from_image_inspect(DOCKER)
    assert pin == ImagePin("nvidia/pytorch", "25.09-py3", DIGEST_A, "image_inspect")
    assert pin.reference == f"nvcr.io/nvidia/pytorch@{DIGEST_A}"
    assert pin.tagged_reference == PINNED


def test_podman_inspect_with_several_tags_needs_a_tag() -> None:
    with pytest.raises(ContainerPinError, match="expected one nvcr.io tag, found 2"):
        pin_from_image_inspect(PODMAN)
    assert pin_from_image_inspect(PODMAN, tag="25.09-py3").image_digest == DIGEST_A


def test_several_repo_digests_need_the_digest_that_was_run() -> None:
    both = json.loads(PODMAN)
    pin = pin_from_image_inspect(PODMAN, tag="25.09-py3", digest=INDEX_DIGEST)
    assert pin.image_digest == INDEX_DIGEST
    with pytest.raises(ContainerPinError, match="not among the RepoDigests"):
        pin_from_image_inspect(PODMAN, tag="25.09-py3", digest=DIGEST_B)
    del both[0]["Digest"]
    with pytest.raises(ContainerPinError, match="2 RepoDigests"):
        pin_from_image_inspect(json.dumps(both), tag="25.09-py3")


def test_image_id_is_normalized_across_runtimes() -> None:
    assert image_id(DOCKER) == image_id(PODMAN) == DIGEST_B
    with pytest.raises(ContainerPinError, match="image ID"):
        image_id(json.dumps([{"Id": "abc"}]))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("not json", "not JSON"),
        ("[]", "exactly one image"),
        ("[1]", "exactly one image"),
        (
            json.dumps([{"RepoTags": ["nvcr.io/nvidia/pytorch:25.09-py3"], "RepoDigests": None}]),
            "local-only image",
        ),
        (
            json.dumps(
                [
                    {
                        "RepoTags": ["nvcr.io/nvidia/pytorch"],
                        "RepoDigests": [f"nvcr.io/nvidia/pytorch@{DIGEST_A}"],
                    }
                ]
            ),
            "lacks a tag",
        ),
    ],
)
def test_bad_inspect_output(text: str, message: str) -> None:
    with pytest.raises(ContainerPinError, match=message):
        pin_from_image_inspect(text)


def test_environment_pin() -> None:
    assert pin_from_environment({}) is None
    pin = pin_from_environment({IMAGE_ENV: PINNED})
    assert pin is not None and pin.capture_method == "environment"
    with pytest.raises(ContainerPinError, match="needs nvcr.io"):
        pin_from_environment({IMAGE_ENV: "nvcr.io/nvidia/pytorch:25.09-py3"})


def test_host_cuda_run_is_refused_when_a_pin_is_required() -> None:
    with pytest.raises(UnpinnedRuntimeError, match="host CUDA"):
        require_pinned_runtime({IMAGE_ENV: PINNED}, containerized=False)
    with pytest.raises(UnpinnedRuntimeError, match="is not set"):
        require_pinned_runtime({}, containerized=True)
    assert require_pinned_runtime({IMAGE_ENV: PINNED}, containerized=True) == pin_from_environment(
        {IMAGE_ENV: PINNED}
    )
    assert require_pinned_runtime({}, containerized=False, pin_required=False) is None


def test_container_markers(tmp_path: Path) -> None:
    marker = tmp_path / ".dockerenv"
    assert not in_container((marker,))
    marker.write_text("", encoding="utf-8")
    assert in_container((marker,))


def test_running_digest_must_match_the_pin() -> None:
    verify_running_digest(PIN, pin_from_image_inspect(DOCKER))
    other = ImagePin("nvidia/pytorch", "25.09-py3", DIGEST_B, "environment")
    with pytest.raises(ContainerPinError, match="does not match pin"):
        verify_running_digest(PIN, other)


@pytest.mark.parametrize("container_json", [DOCKER_RUN, PODMAN_RUN])
def test_container_must_run_the_pinned_image(container_json: str) -> None:
    observed = verify_container(PIN, container_json, DOCKER)
    assert observed == ImagePin("nvidia/pytorch", "25.09-py3", DIGEST_A, "container_inspect")
    validate_receipt_payload(container_pin_payload(observed, host_fingerprint_digest=None))


def _run(**changes: object) -> str:
    record = json.loads(DOCKER_RUN)[0]
    record.update(changes)
    return json.dumps([record])


@pytest.mark.parametrize(
    ("container_json", "image_json", "message"),
    [
        (_run(Config={"Image": "nvcr.io/nvidia/pytorch:25.09-py3"}), DOCKER, "not a digest"),
        (_run(Config={"Image": f"nvcr.io/nvidia/pytorch@{DIGEST_B}"}), DOCKER, "does not match"),
        (_run(Config={}), DOCKER, "no image reference"),
        (_run(Image=DIGEST_A), DOCKER, "image ID differs"),
        (DOCKER_RUN, json.dumps([{**json.loads(DOCKER)[0], "RepoDigests": []}]), "local-only"),
        ("[]", DOCKER, "exactly one container"),
    ],
)
def test_container_mismatch_is_refused(container_json: str, image_json: str, message: str) -> None:
    with pytest.raises(ContainerPinError, match=message):
        verify_container(PIN, container_json, image_json)


def test_inspect_container_runs_two_fixed_commands() -> None:
    calls: list[list[str]] = []

    def fake(argv: Sequence[str], timeout: float) -> str:
        calls.append(list(argv))
        return PODMAN_RUN if argv[1] == "container" else PODMAN

    pinned = ImagePin("nvidia/pytorch", "25.09-py3", DIGEST_A, "image_inspect")
    assert inspect_container("blackdog-run", pinned, runtime="podman", run=fake).image_digest == (
        DIGEST_A
    )
    assert calls == [
        ["podman", "container", "inspect", "blackdog-run"],
        ["podman", "image", "inspect", f"nvcr.io/nvidia/pytorch@{DIGEST_A}"],
    ]
    with pytest.raises(ContainerPinError, match="not a container"):
        inspect_container("--all", pinned, run=fake)
    with pytest.raises(ContainerPinError, match="runtime must be"):
        inspect_container("blackdog-run", pinned, runtime="sh", run=fake)


def test_inspect_image_uses_a_fixed_argv_and_timeout() -> None:
    calls: list[tuple[list[str], float]] = []

    def fake(argv: Sequence[str], timeout: float) -> str:
        calls.append((list(argv), timeout))
        return PODMAN

    pin = inspect_image("nvcr.io/nvidia/pytorch:25.09-py3", runtime="podman", run=fake)
    assert pin.image_digest == DIGEST_A
    assert calls == [(["podman", "image", "inspect", "nvcr.io/nvidia/pytorch:25.09-py3"], 30.0)]
    with pytest.raises(ContainerPinError, match="runtime must be"):
        inspect_image(PINNED, runtime="sh", run=fake)


class _Completed:
    def __init__(self, returncode: int, stdout: str) -> None:
        self.returncode = returncode
        self.stdout = stdout


def test_default_runner_handles_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    results: list[object] = [
        _Completed(0, DOCKER),
        _Completed(1, ""),
        OSError("missing"),
        subprocess.TimeoutExpired("docker", 1),
    ]

    def fake_run(argv: list[str], **kwargs: object) -> object:
        assert kwargs["timeout"] == 30.0 and kwargs["check"] is False
        result = results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr("subprocess.run", fake_run)
    assert inspect_image("nvcr.io/nvidia/pytorch:25.09-py3").image_digest == DIGEST_A
    for message in ("exited 1", "missing", "timed out"):
        with pytest.raises(ContainerPinError, match=message):
            inspect_image("nvcr.io/nvidia/pytorch:25.09-py3")


def test_record_pin_with_host_fingerprint(store: ArtifactStore) -> None:
    host = put_plain(store, {"kind": "environment_diagnostics"}, [], T0)
    payload = container_pin_payload(PIN, host_fingerprint_digest=host)
    validate_receipt_payload(payload)
    digest = record_container_pin(store, PIN, host_fingerprint_digest=host, created_at=T1)
    envelope = store.get(digest)
    assert envelope["parents"] == [host]
    assert envelope["payload"]["source"] == "nvcr.io"
    assert envelope["payload"]["image_digest"] == DIGEST_A

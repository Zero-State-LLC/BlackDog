"""Capture the NGC container a run uses as a ContainerPinReceipt (R-N001).

The parsing functions are pure so fixtures can test them without a
container runtime. ``inspect_image`` is the only function that runs a
process (``docker`` or ``podman image inspect``); it never pulls.

A run that requires a pin and finds itself on the host CUDA stack
(no container marker, no recorded image digest) is refused with
``UnpinnedRuntimeError`` instead of being recorded as pinned.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from faustcoder.nvidia.receipts import ReceiptKind, build_receipt, put_receipt
from faustcoder.store import ArtifactStore

NGC_REGISTRY = "nvcr.io"
IMAGE_ENV = "BLACKDOG_CONTAINER_IMAGE"
CONTAINER_MARKERS = (Path("/.dockerenv"), Path("/run/.containerenv"))
RUNTIMES = ("docker", "podman")
INSPECT_TIMEOUT_SECONDS = 30.0
_REFERENCE_RE = re.compile(
    r"^(?P<registry>[a-z0-9.-]+(?::[0-9]+)?)/(?P<repository>[a-z0-9][a-z0-9._/-]*?)"
    r"(?::(?P<tag>[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}))?"
    r"(?:@(?P<digest>sha256:[0-9a-f]{64}))?$"
)

Runner = Callable[[Sequence[str], float], str]


class ContainerPinError(ValueError):
    """An image reference or inspect record cannot yield an NGC pin."""


class UnpinnedRuntimeError(RuntimeError):
    """A pin is required but the process is not in a pinned container."""


@dataclass(frozen=True)
class ImagePin:
    """An NGC image identified by digest. The tag is a label only."""

    repository: str
    tag: str
    image_digest: str
    capture_method: str

    @property
    def reference(self) -> str:
        """Return ``nvcr.io/<repository>@<digest>``, the reference to run."""
        return f"{NGC_REGISTRY}/{self.repository}@{self.image_digest}"

    @property
    def tagged_reference(self) -> str:
        """Return ``nvcr.io/<repository>:<tag>@<digest>`` for ``BLACKDOG_CONTAINER_IMAGE``."""
        return f"{NGC_REGISTRY}/{self.repository}:{self.tag}@{self.image_digest}"


def parse_image_reference(reference: str) -> tuple[str, str | None, str | None]:
    """Split an nvcr.io reference into repository, tag and digest.

    Raise ContainerPinError for any other registry or a malformed value.
    """
    match = _REFERENCE_RE.fullmatch(reference.strip())
    if match is None:
        raise ContainerPinError(f"not an image reference: {reference!r}")
    if match.group("registry") != NGC_REGISTRY:
        raise ContainerPinError(f"registry must be {NGC_REGISTRY}, got {match.group('registry')}")
    return match.group("repository"), match.group("tag"), match.group("digest")


def pin_from_reference(reference: str, *, capture_method: str) -> ImagePin:
    """Return a pin from a reference that carries both a tag and a digest."""
    repository, tag, digest = parse_image_reference(reference)
    if tag is None or digest is None:
        raise ContainerPinError("a pinned reference needs nvcr.io/<repo>:<tag>@sha256:<hex>")
    return ImagePin(repository, tag, digest, capture_method)


def pin_from_image_inspect(inspect_json: str, *, tag: str | None = None) -> ImagePin:
    """Return the pin from ``docker|podman image inspect`` JSON output.

    The digest comes from ``RepoDigests`` (the registry manifest), not
    ``Id`` (the local config digest). ``tag`` selects one of several
    ``RepoTags``; with one nvcr.io tag it may be omitted.
    """
    try:
        records = json.loads(inspect_json)
    except json.JSONDecodeError as exc:
        raise ContainerPinError("image inspect output is not JSON") from exc
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        raise ContainerPinError("image inspect output must describe exactly one image")
    tags = _ngc_refs(records[0].get("RepoTags"))
    digests = _ngc_refs(records[0].get("RepoDigests"))
    if tag is not None:
        tags = [ref for ref in tags if ref.rsplit(":", 1)[-1] == tag]
    if len(tags) != 1:
        raise ContainerPinError(f"expected one nvcr.io tag, found {len(tags)}")
    repository, found_tag, _ = parse_image_reference(tags[0])
    matching = [ref for ref in digests if parse_image_reference(ref)[0] == repository]
    if len(matching) != 1:
        raise ContainerPinError(f"expected one RepoDigest for {repository}, found {len(matching)}")
    digest = parse_image_reference(matching[0])[2]
    if found_tag is None or digest is None:
        raise ContainerPinError("inspect record lacks a tag or a digest")
    return ImagePin(repository, found_tag, digest, "image_inspect")


def pin_from_environment(env: Mapping[str, str]) -> ImagePin | None:
    """Return the pin recorded in ``BLACKDOG_CONTAINER_IMAGE``, if set.

    INFERRED convention: the launcher sets the variable to the full
    ``nvcr.io/<repo>:<tag>@sha256:<hex>`` reference it ran.
    """
    value = env.get(IMAGE_ENV)
    if not value:
        return None
    return pin_from_reference(value, capture_method="environment")


def in_container(markers: Sequence[Path] = CONTAINER_MARKERS) -> bool:
    """Return True when a docker or podman marker file exists."""
    return any(marker.exists() for marker in markers)


def require_pinned_runtime(
    env: Mapping[str, str], *, containerized: bool, pin_required: bool = True
) -> ImagePin | None:
    """Return the runtime pin, or refuse a host-CUDA run that needs one.

    A missing pin is allowed only when ``pin_required`` is False, and
    then the caller must not record a ContainerPinReceipt.
    """
    pin = pin_from_environment(env)
    if not pin_required:
        return pin
    if not containerized:
        raise UnpinnedRuntimeError("pin required: refusing a host CUDA run outside a container")
    if pin is None:
        raise UnpinnedRuntimeError(f"pin required: {IMAGE_ENV} is not set in the container")
    return pin


def verify_running_digest(expected: ImagePin, observed: ImagePin) -> None:
    """Raise unless the running container's digest matches the pin."""
    if (expected.repository, expected.image_digest) != (
        observed.repository,
        observed.image_digest,
    ):
        raise ContainerPinError(
            f"running image {observed.reference} does not match pin {expected.reference}"
        )


def inspect_image(
    reference: str,
    *,
    runtime: str = "docker",
    timeout: float = INSPECT_TIMEOUT_SECONDS,
    run: Runner | None = None,
) -> ImagePin:
    """Inspect a local image and return its pin. Never pulls."""
    if runtime not in RUNTIMES:
        raise ContainerPinError(f"runtime must be one of {RUNTIMES}")
    _, tag, _ = parse_image_reference(reference)
    runner = run if run is not None else _run_process
    output = runner([runtime, "image", "inspect", reference], timeout)
    return pin_from_image_inspect(output, tag=tag)


def container_pin_payload(
    pin: ImagePin, *, host_fingerprint_digest: str | None
) -> dict[str, object]:
    """Return the ContainerPinReceipt payload for ``pin``."""
    return {
        "kind": ReceiptKind.CONTAINER_PIN.value,
        "source": NGC_REGISTRY,
        "repository": pin.repository,
        "tag": pin.tag,
        "image_digest": pin.image_digest,
        "capture_method": pin.capture_method,
        "host_fingerprint_digest": host_fingerprint_digest,
    }


def record_container_pin(
    store: ArtifactStore,
    pin: ImagePin,
    *,
    host_fingerprint_digest: str | None,
    created_at: str,
    producer: str = "faustcoder.nvidia.container_pin",
) -> str:
    """Store a ContainerPinReceipt and return its artifact id."""
    payload = container_pin_payload(pin, host_fingerprint_digest=host_fingerprint_digest)
    envelope = build_receipt(payload, created_at=created_at, producer=producer)
    return put_receipt(store, envelope)


def _ngc_refs(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        item for item in value if isinstance(item, str) and item.startswith(NGC_REGISTRY + "/")
    ]


def _run_process(argv: Sequence[str], timeout: float) -> str:
    try:
        completed = subprocess.run(
            list(argv), capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContainerPinError(f"{argv[0]} image inspect failed: {exc}") from exc
    if completed.returncode != 0:
        raise ContainerPinError(f"{argv[0]} image inspect exited {completed.returncode}")
    return completed.stdout

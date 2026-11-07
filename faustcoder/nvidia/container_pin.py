"""Capture the NGC container a run uses as a ContainerPinReceipt (R-N001).

The parsing functions are pure so fixtures can test them without a
container runtime. ``inspect_image`` is the only function that runs a
process (``docker`` or ``podman image inspect``); it never pulls.

A run that requires a pin and finds itself on the host CUDA stack
(no container marker, no recorded image digest) is refused with
``UnpinnedRuntimeError`` instead of being recorded as pinned.

Digest sources (OBSERVED 2026-10-31):

- Docker: image ``Id`` is the local config digest; ``RepoDigests`` lists
  registry manifest digests and is filled only after a pull or push
  (moby api/types/image/image_inspect.go). ``docker container inspect``
  reports ``Image`` (the image ID) and ``Config.Image`` (the reference
  as given to ``docker run``) (moby api/swagger.yaml).
- Podman: ``image inspect`` has ``Id`` without the ``sha256:`` prefix, a
  ``Digest`` field and possibly several ``RepoDigests`` for one
  repository (manifest list and per-arch instance); ``container
  inspect`` reports ``Image`` and ``ImageName`` (podman docs,
  podman-image-inspect.1 and podman-container-inspect.1).
- A multi-arch NGC image has one index digest and one digest per
  architecture, so a pin must say which one it records. Pin the digest
  you pass to ``docker run``.
- Inside a container no runtime exposes the image digest by default:
  Podman writes image name and ID to /run/.containerenv only with
  ``--privileged`` (podman-run.1), and Docker documents nothing. So
  ``BLACKDOG_CONTAINER_IMAGE`` is a BlackDog convention the launcher
  sets; it is a claim, and only ``verify_container`` on the host checks
  it. That check on the cleared Spark is NOT_COMPUTABLE here.
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
_CONTAINER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_IMAGE_ID_RE = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")
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


def pin_from_image_inspect(
    inspect_json: str, *, tag: str | None = None, digest: str | None = None
) -> ImagePin:
    """Return the pin from ``docker|podman image inspect`` JSON output.

    The digest comes from ``RepoDigests`` (registry manifests), never
    from ``Id`` (the local config digest). ``tag`` selects one of several
    ``RepoTags``. ``digest`` selects one of several RepoDigests for the
    repository and must be among them. Without it, a single RepoDigest is
    used, then Podman's ``Digest`` field; anything else is ambiguous.
    """
    record = _single_record(inspect_json, "image")
    tags = _ngc_refs(record.get("RepoTags"))
    if tag is not None:
        tags = [ref for ref in tags if ref.rsplit(":", 1)[-1] == tag]
    if len(tags) != 1:
        raise ContainerPinError(f"expected one nvcr.io tag, found {len(tags)}")
    repository, found_tag, _ = parse_image_reference(tags[0])
    if found_tag is None:
        raise ContainerPinError("inspect record lacks a tag")
    candidates = sorted(
        {
            found
            for ref in _ngc_refs(record.get("RepoDigests"))
            for repo, _, found in [parse_image_reference(ref)]
            if repo == repository and found is not None
        }
    )
    if not candidates:
        raise ContainerPinError(
            f"no RepoDigest for {repository}: a local-only image has no registry digest"
        )
    chosen = _choose_digest(candidates, digest, record)
    return ImagePin(repository, found_tag, chosen, "image_inspect")


def image_id(inspect_json: str) -> str:
    """Return the local image ID from image inspect output as ``sha256:<hex>``."""
    return _normal_image_id(_single_record(inspect_json, "image").get("Id"))


def pin_from_environment(env: Mapping[str, str]) -> ImagePin | None:
    """Return the pin recorded in ``BLACKDOG_CONTAINER_IMAGE``, if set.

    BlackDog convention, not an NGC one: the launcher sets the variable
    to the ``nvcr.io/<repo>:<tag>@sha256:<hex>`` reference it ran. The
    value is a claim until ``verify_container`` checks it on the host.
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


def verify_container(
    expected: ImagePin, container_inspect_json: str, image_inspect_json: str
) -> ImagePin:
    """Check on the host that a container runs the pinned image.

    ``container_inspect_json`` is ``container inspect`` output for the
    run; ``image_inspect_json`` is ``image inspect`` output for
    ``expected.reference``. The container must have been started from a
    reference with the pinned repository and digest, and its image ID
    must be the ID of the local image carrying that RepoDigest. Return
    the observed pin.
    """
    record = _single_record(container_inspect_json, "container")
    config = record.get("Config")
    name = record.get("ImageName")
    if isinstance(config, dict) and isinstance(config.get("Image"), str):
        name = config["Image"]
    if not isinstance(name, str):
        raise ContainerPinError("container inspect output has no image reference")
    repository, tag, digest = parse_image_reference(name)
    if digest is None:
        raise ContainerPinError(f"container was started from {name!r}, not a digest reference")
    observed = ImagePin(repository, tag or expected.tag, digest, "container_inspect")
    verify_running_digest(expected, observed)
    pinned = pin_from_image_inspect(
        image_inspect_json, tag=expected.tag, digest=expected.image_digest
    )
    verify_running_digest(expected, pinned)
    if _normal_image_id(record.get("Image")) != image_id(image_inspect_json):
        raise ContainerPinError("container image ID differs from the pinned image ID")
    return observed


def inspect_container(
    container: str,
    expected: ImagePin,
    *,
    runtime: str = "docker",
    timeout: float = INSPECT_TIMEOUT_SECONDS,
    run: Runner | None = None,
) -> ImagePin:
    """Inspect a running container and its image, then ``verify_container``."""
    if runtime not in RUNTIMES:
        raise ContainerPinError(f"runtime must be one of {RUNTIMES}")
    if _CONTAINER_ID_RE.fullmatch(container) is None:
        raise ContainerPinError(f"not a container name or ID: {container!r}")
    runner = run if run is not None else _run_process
    container_json = runner([runtime, "container", "inspect", container], timeout)
    image_json = runner([runtime, "image", "inspect", expected.reference], timeout)
    return verify_container(expected, container_json, image_json)


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
    _, tag, digest = parse_image_reference(reference)
    runner = run if run is not None else _run_process
    output = runner([runtime, "image", "inspect", reference], timeout)
    return pin_from_image_inspect(output, tag=tag, digest=digest)


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


def _single_record(inspect_json: str, what: str) -> dict[str, object]:
    try:
        records = json.loads(inspect_json)
    except json.JSONDecodeError as exc:
        raise ContainerPinError(f"{what} inspect output is not JSON") from exc
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        raise ContainerPinError(f"{what} inspect output must describe exactly one {what}")
    return records[0]


def _choose_digest(candidates: list[str], hint: str | None, record: Mapping[str, object]) -> str:
    if hint is not None:
        if hint not in candidates:
            raise ContainerPinError(f"digest {hint} is not among the RepoDigests")
        return hint
    if len(candidates) == 1:
        return candidates[0]
    podman_digest = record.get("Digest")
    if isinstance(podman_digest, str) and podman_digest in candidates:
        return podman_digest
    raise ContainerPinError(
        f"{len(candidates)} RepoDigests for one repository: pass the digest that was run"
    )


def _normal_image_id(value: object) -> str:
    match = _IMAGE_ID_RE.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ContainerPinError("inspect output has no valid image ID")
    return "sha256:" + match.group(1)


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
        raise ContainerPinError(f"{' '.join(argv[:3])} failed: {exc}") from exc
    if completed.returncode != 0:
        raise ContainerPinError(f"{' '.join(argv[:3])} exited {completed.returncode}")
    return completed.stdout

"""Receipt types for the NVIDIA stack (spec 002 R-N001 to R-N005).

Each receipt is the payload of an ordinary ``ArtifactEnvelope``: it
gets ``schema_version``, ``artifact_id``, ``content_digest``,
``created_at``, ``producer`` and ``parents`` from
``faustcoder.canonical.build_envelope`` and is stored write-once by
``ArtifactStore``. The payload ``kind`` names the receipt type.

Every digest a payload declares as a parent (for example
``container_pin_digest``) must also be in the envelope ``parents``,
must already be stored, must have the expected kind, and must not be
newer than the child. ``put_receipt`` checks all of that before the
store write, so a stored receipt only points at earlier, existing
nodes (R-N004).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from faustcoder.canonical import build_envelope
from faustcoder.errors import ArtifactStoreError
from faustcoder.schemas import validate
from faustcoder.store import ArtifactStore

RECEIPT_SCHEMA_VERSION = "0.1.0"
JsonObject = dict[str, object]


class ReceiptKind(StrEnum):
    """Payload ``kind`` of each spec 002 receipt."""

    CONTAINER_PIN = "ContainerPinReceipt"
    NEMO_ATTEMPT = "NeMoTrainingAttempt"
    NIM_DEPLOYMENT = "NIMDeploymentReceipt"
    EXTERNAL_CAPACITY = "ExternalCapacityReceipt"


SCHEMA_FOR: Mapping[ReceiptKind, str] = {
    ReceiptKind.CONTAINER_PIN: "container-pin-receipt.schema.json",
    ReceiptKind.NEMO_ATTEMPT: "nemo-training-attempt.schema.json",
    ReceiptKind.NIM_DEPLOYMENT: "nim-deployment-receipt.schema.json",
    ReceiptKind.EXTERNAL_CAPACITY: "external-capacity-receipt.schema.json",
}


class ReceiptRuleError(ArtifactStoreError):
    """A receipt breaks a spec 002 parent, kind or ordering rule."""


@dataclass(frozen=True)
class ParentRule:
    """One payload field that names a parent, and the kind it must have.

    ``kind`` None means any stored artifact (a DatasetSnapshot or a
    model artifact has no spec 002 kind). ``optional`` fields may be
    null.
    """

    field: str
    kind: ReceiptKind | None
    optional: bool = False


PARENT_RULES: Mapping[ReceiptKind, tuple[ParentRule, ...]] = {
    ReceiptKind.CONTAINER_PIN: (ParentRule("host_fingerprint_digest", None, optional=True),),
    ReceiptKind.NEMO_ATTEMPT: (
        ParentRule("container_pin_digest", ReceiptKind.CONTAINER_PIN),
        ParentRule("dataset_snapshot_digest", None),
        ParentRule("external_capacity_digest", ReceiptKind.EXTERNAL_CAPACITY, optional=True),
    ),
    ReceiptKind.NIM_DEPLOYMENT: (
        ParentRule("container_pin_digest", ReceiptKind.CONTAINER_PIN),
        ParentRule("model_artifact_digest", None),
    ),
    ReceiptKind.EXTERNAL_CAPACITY: (),
}


def receipt_kind(payload: Mapping[str, object]) -> ReceiptKind | None:
    """Return the spec 002 kind of ``payload``, or None for other artifacts."""
    kind = payload.get("kind")
    if not isinstance(kind, str):
        return None
    try:
        return ReceiptKind(kind)
    except ValueError:
        return None


def validate_receipt_payload(payload: Mapping[str, object]) -> ReceiptKind:
    """Validate ``payload`` against its kind's schema and cross-field rules."""
    kind = receipt_kind(payload)
    if kind is None:
        raise ReceiptRuleError(f"payload kind is not one of {[k.value for k in ReceiptKind]}")
    validate(dict(payload), SCHEMA_FOR[kind])
    if kind is ReceiptKind.NEMO_ATTEMPT:
        _check_attempt_outcome(payload)
    return kind


def declared_parents(payload: Mapping[str, object]) -> dict[str, str]:
    """Return ``{field: digest}`` for every non-null parent field."""
    kind = validate_receipt_payload(payload)
    found: dict[str, str] = {}
    for rule in PARENT_RULES[kind]:
        value = payload.get(rule.field)
        if isinstance(value, str):
            found[rule.field] = value
    return found


def build_receipt(
    payload: Mapping[str, object],
    *,
    created_at: str,
    producer: str,
    extra_parents: Sequence[str] = (),
) -> JsonObject:
    """Return an envelope whose parents are the declared ones, then extras.

    The order is the payload's rule order followed by ``extra_parents``
    with duplicates removed, so the same inputs always build the same
    bytes.
    """
    parents = list(declared_parents(payload).values())
    for parent in extra_parents:
        if parent not in parents:
            parents.append(parent)
    return build_envelope(
        schema_version=RECEIPT_SCHEMA_VERSION,
        created_at=created_at,
        producer=producer,
        parents=parents,
        payload=dict(payload),
    )


def parent_violations(
    envelope: Mapping[str, object],
    lookup: Callable[[str], Mapping[str, object] | None],
) -> list[str]:
    """Return every ordering and spec 002 rule ``envelope`` breaks.

    ``lookup`` returns a stored envelope by content digest, or None when
    it is not stored. Every parent must exist and must not be newer
    than the child; see ``rule_violations`` for the rest.
    """
    try:
        child_time = parse_rfc3339(envelope.get("created_at"))
    except ReceiptRuleError as exc:
        return [str(exc)]
    reasons: list[str] = []
    for parent in parents_of(envelope):
        reasons.extend(_ordering_violations(parent, lookup, child_time))
    return reasons + rule_violations(envelope, lookup)


def rule_violations(
    envelope: Mapping[str, object],
    lookup: Callable[[str], Mapping[str, object] | None],
) -> list[str]:
    """Return the spec 002 receipt rules ``envelope`` breaks.

    The payload validates; each declared parent field is listed in
    ``parents`` and, when stored, has the expected kind; a NIM
    deployment names the image its pin recorded.
    """
    payload = _payload_of(envelope)
    parents = parents_of(envelope)
    try:
        kind = validate_receipt_payload(payload)
    except ArtifactStoreError as exc:
        return [str(exc)]
    reasons: list[str] = []
    for rule in PARENT_RULES[kind]:
        value = payload.get(rule.field)
        if value is None:
            continue
        if value not in parents:
            reasons.append(f"{rule.field} is not listed in parents")
            continue
        found = lookup(str(value))
        if found is not None and rule.kind is not None and _kind_of(found) is not rule.kind:
            reasons.append(f"{rule.field} must name a {rule.kind.value}")
    if kind is ReceiptKind.NIM_DEPLOYMENT and not reasons:
        pin = lookup(str(payload["container_pin_digest"]))
        if pin is not None and _payload_of(pin).get("image_digest") != payload.get(
            "container_image_digest"
        ):
            reasons.append("container_image_digest does not match the ContainerPinReceipt")
    return reasons


def put_receipt(store: ArtifactStore, envelope: Mapping[str, object]) -> str:
    """Check the spec 002 rules for ``envelope`` and store it write-once."""

    def lookup(digest: str) -> Mapping[str, object] | None:
        return store.get(digest) if store.exists(digest) else None

    reasons = parent_violations(envelope, lookup)
    if reasons:
        raise ReceiptRuleError("; ".join(reasons))
    return store.put(dict(envelope))


def object_field(payload: Mapping[str, object], name: str) -> Mapping[str, object]:
    """Return ``payload[name]`` narrowed to an object, or raise ReceiptRuleError."""
    value = payload.get(name)
    if not isinstance(value, Mapping):
        raise ReceiptRuleError(f"{name} must be an object")
    return value


def string_list(payload: Mapping[str, object], name: str) -> list[str]:
    """Return ``payload[name]`` narrowed to a list of strings, or raise ReceiptRuleError."""
    value = payload.get(name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ReceiptRuleError(f"{name} must be a list of strings")
    return [str(item) for item in value]


def parse_rfc3339(value: object) -> datetime:
    """Parse an RFC 3339 timestamp. Raise ReceiptRuleError otherwise."""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    raise ReceiptRuleError(f"created_at is not an RFC 3339 timestamp: {value!r}")


def _ordering_violations(
    digest: str,
    lookup: Callable[[str], Mapping[str, object] | None],
    child_time: datetime,
) -> list[str]:
    parent = lookup(digest)
    if parent is None:
        return [f"parent {digest} is not stored"]
    try:
        parent_time = parse_rfc3339(parent.get("created_at"))
    except ReceiptRuleError as exc:
        return [f"parent {digest}: {exc}"]
    if parent_time > child_time:
        return [f"parent {digest} is newer than the receipt"]
    return []


def _payload_of(envelope: Mapping[str, object]) -> Mapping[str, object]:
    payload = envelope.get("payload")
    return payload if isinstance(payload, Mapping) else {}


def parents_of(envelope: Mapping[str, object]) -> tuple[str, ...]:
    """Return the ``parents`` list of one envelope, or () when malformed."""
    parents = envelope.get("parents")
    return tuple(str(item) for item in parents) if isinstance(parents, list) else ()


def _kind_of(envelope: Mapping[str, object]) -> ReceiptKind | None:
    return receipt_kind(_payload_of(envelope))


def _check_attempt_outcome(payload: Mapping[str, object]) -> None:
    if payload.get("status") != "completed":
        return
    peak = payload.get("peak_memory_bytes")
    cap = payload.get("memory_cap_bytes")
    if not isinstance(peak, int) or not isinstance(cap, int):
        raise ReceiptRuleError("a completed attempt records peak_memory_bytes")
    if peak > cap:
        raise ReceiptRuleError("a completed attempt cannot exceed memory_cap_bytes")
    export = payload.get("export")
    if not isinstance(export, Mapping) or not export.get("checkpoint_digests"):
        raise ReceiptRuleError("a completed attempt exports at least one checkpoint")

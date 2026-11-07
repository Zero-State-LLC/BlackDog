"""N01: spec 002 receipt payloads, envelopes and parent rules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from faustcoder import ArtifactStore, SchemaValidationError, build_envelope
from faustcoder.errors import MutationError
from faustcoder.nvidia.receipts import (
    RECEIPT_SCHEMA_VERSION,
    ReceiptKind,
    ReceiptRuleError,
    build_receipt,
    declared_parents,
    object_field,
    parent_violations,
    parents_of,
    parse_rfc3339,
    put_receipt,
    receipt_kind,
    string_list,
    validate_receipt_payload,
)
from tests.nvidia_support import T0, T1, T2, T3, put_plain, stored_pin
from tests.support import DIGEST_A, DIGEST_B

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "valid"
ENVELOPE_FIELDS = {
    "schema_version",
    "artifact_id",
    "content_digest",
    "created_at",
    "producer",
    "parents",
}


def _fixture(stem: str) -> dict[str, object]:
    value = json.loads((FIXTURES / f"{stem}.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _attempt(pin: str, dataset: str, **overrides: object) -> dict[str, object]:
    payload = _fixture("nemo-training-attempt")
    payload.update(container_pin_digest=pin, dataset_snapshot_digest=dataset)
    payload.update(overrides)
    return payload


def _completed(pin: str, dataset: str, **overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "status": "completed",
        "peak_memory_bytes": 1024,
        "export": {"format": "hf_adapter", "checkpoint_digests": [DIGEST_B]},
    }
    fields.update(overrides)
    return _attempt(pin, dataset, **fields)


def test_kind_of_each_fixture() -> None:
    for kind in ReceiptKind:
        stem = {
            ReceiptKind.CONTAINER_PIN: "container-pin-receipt",
            ReceiptKind.NEMO_ATTEMPT: "nemo-training-attempt",
            ReceiptKind.NIM_DEPLOYMENT: "nim-deployment-receipt",
            ReceiptKind.EXTERNAL_CAPACITY: "external-capacity-receipt",
        }[kind]
        assert validate_receipt_payload(_fixture(stem)) is kind
    assert receipt_kind({"kind": 3}) is None
    assert receipt_kind({"kind": "TrainingRun"}) is None


def test_unknown_kind_is_refused() -> None:
    with pytest.raises(ReceiptRuleError, match="payload kind"):
        validate_receipt_payload({"kind": "Reward"})


def test_every_receipt_carries_the_envelope_fields(store: ArtifactStore) -> None:
    pin = stored_pin(store)
    envelope = store.get(pin)
    assert set(envelope) >= ENVELOPE_FIELDS
    assert envelope["schema_version"] == RECEIPT_SCHEMA_VERSION
    assert envelope["content_digest"] == "sha256:" + envelope["artifact_id"]
    assert envelope["parents"] == []


def test_receipt_is_content_addressed_and_append_only(store: ArtifactStore) -> None:
    first = stored_pin(store)
    assert stored_pin(store) == first
    payload = store.get(first)["payload"]
    rewritten = build_envelope(
        schema_version=RECEIPT_SCHEMA_VERSION,
        created_at=T2,
        producer="other",
        parents=[],
        payload=payload,
    )
    with pytest.raises(MutationError):
        put_receipt(store, rewritten)


def test_attempt_rejects_reward_and_metric_fields() -> None:
    for field in ("reward", "passed", "metrics", "eval_loss"):
        payload = _attempt(DIGEST_A, DIGEST_B, **{field: 1})
        with pytest.raises(SchemaValidationError):
            validate_receipt_payload(payload)
    with pytest.raises(SchemaValidationError, match="grading_authority"):
        validate_receipt_payload(_attempt(DIGEST_A, DIGEST_B, grading_authority="nemo"))


def test_attempt_memory_cap_is_r001() -> None:
    with pytest.raises(SchemaValidationError, match="memory_cap_bytes"):
        validate_receipt_payload(_attempt(DIGEST_A, DIGEST_B, memory_cap_bytes=121 * 1024**3))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"peak_memory_bytes": None}, "records peak_memory_bytes"),
        ({"peak_memory_bytes": 200 * 1024**3}, "cannot exceed"),
        (
            {"export": {"format": "hf_adapter", "checkpoint_digests": []}},
            "at least one checkpoint",
        ),
    ],
)
def test_completed_attempt_cross_checks(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ReceiptRuleError, match=message):
        validate_receipt_payload(_completed(DIGEST_A, DIGEST_B, **overrides))


def test_pin_rejects_other_registries_and_tag_only_pins() -> None:
    payload = _fixture("container-pin-receipt")
    with pytest.raises(SchemaValidationError, match="source"):
        validate_receipt_payload(dict(payload, source="docker.io"))
    with pytest.raises(SchemaValidationError, match="image_digest"):
        validate_receipt_payload(dict(payload, image_digest="latest"))


def test_build_receipt_orders_and_dedupes_parents() -> None:
    payload = _attempt(DIGEST_A, DIGEST_B)
    envelope = build_receipt(
        payload, created_at=T3, producer="p", extra_parents=[DIGEST_B, DIGEST_A]
    )
    assert envelope["parents"] == [DIGEST_A, DIGEST_B]
    extra = "sha256:" + "ab" * 32
    envelope = build_receipt(payload, created_at=T3, producer="p", extra_parents=[extra])
    assert envelope["parents"] == [DIGEST_A, DIGEST_B, extra]
    assert declared_parents(payload) == {
        "container_pin_digest": DIGEST_A,
        "dataset_snapshot_digest": DIGEST_B,
    }


def test_attempt_with_stored_parents_is_accepted(store: ArtifactStore) -> None:
    pin = stored_pin(store)
    dataset = put_plain(store, {"snapshot": "s"}, [], T0)
    envelope = build_receipt(_completed(pin, dataset), created_at=T2, producer="p")
    digest = put_receipt(store, envelope)
    assert store.get(digest)["parents"] == [pin, dataset]


def test_missing_and_newer_parents_are_refused(store: ArtifactStore) -> None:
    pin = stored_pin(store)
    envelope = build_receipt(_attempt(pin, DIGEST_B), created_at=T2, producer="p")
    with pytest.raises(ReceiptRuleError, match="is not stored"):
        put_receipt(store, envelope)
    late = put_plain(store, {"snapshot": "late"}, [], T3)
    envelope = build_receipt(_attempt(pin, late), created_at=T2, producer="p")
    with pytest.raises(ReceiptRuleError, match="newer than the receipt"):
        put_receipt(store, envelope)


def test_declared_parent_must_be_listed_and_of_the_right_kind(store: ArtifactStore) -> None:
    dataset = put_plain(store, {"snapshot": "s"}, [], T0)
    payload = _attempt(dataset, dataset)
    envelope = build_receipt(payload, created_at=T2, producer="p")
    with pytest.raises(ReceiptRuleError, match="must name a ContainerPinReceipt"):
        put_receipt(store, envelope)
    pin = stored_pin(store)
    unlisted = build_envelope(
        schema_version=RECEIPT_SCHEMA_VERSION,
        created_at=T2,
        producer="p",
        parents=[dataset],
        payload=_attempt(pin, dataset),
    )
    with pytest.raises(ReceiptRuleError, match="container_pin_digest is not listed"):
        put_receipt(store, unlisted)


def test_nim_image_must_match_its_pin(store: ArtifactStore) -> None:
    pin = stored_pin(store)
    model = put_plain(store, {"model": "m"}, [], T0)
    payload = _fixture("nim-deployment-receipt")
    payload.update(
        container_pin_digest=pin, model_artifact_digest=model, container_image_digest=DIGEST_B
    )
    with pytest.raises(ReceiptRuleError, match="does not match"):
        put_receipt(store, build_receipt(payload, created_at=T2, producer="p"))
    payload["container_image_digest"] = DIGEST_A
    assert put_receipt(store, build_receipt(payload, created_at=T2, producer="p"))


def test_credit_receipt_is_an_optional_parent(store: ArtifactStore) -> None:
    pin = stored_pin(store)
    dataset = put_plain(store, {"snapshot": "s"}, [], T0)
    credit = put_receipt(
        store, build_receipt(_fixture("external-capacity-receipt"), created_at=T1, producer="p")
    )
    payload = _completed(pin, dataset, external_capacity_digest="sha256:" + credit)
    digest = put_receipt(store, build_receipt(payload, created_at=T2, producer="p"))
    assert store.get(digest)["parents"] == [pin, dataset, "sha256:" + credit]
    wrong = _completed(pin, dataset, external_capacity_digest=dataset)
    with pytest.raises(ReceiptRuleError, match="must name a ExternalCapacityReceipt"):
        put_receipt(store, build_receipt(wrong, created_at=T2, producer="p"))


def test_malformed_envelopes_are_refused() -> None:
    reasons = parent_violations({"created_at": T1, "payload": [], "parents": "x"}, lambda _d: None)
    assert len(reasons) == 1 and "payload kind" in reasons[0]
    assert "RFC 3339" in parent_violations({"payload": {}, "parents": []}, lambda _d: None)[0]
    bad_parent = {"created_at": "nope"}
    reasons = parent_violations(
        {"created_at": T1, "payload": {"kind": "Nope"}, "parents": [DIGEST_A]},
        lambda _d: bad_parent,
    )
    assert any("RFC 3339" in reason for reason in reasons)
    assert any("payload kind" in reason for reason in reasons)
    assert parents_of({"parents": "x"}) == ()


def test_parse_rfc3339() -> None:
    assert parse_rfc3339(T1).year == 2026
    for value in (None, "yesterday"):
        with pytest.raises(ReceiptRuleError, match="RFC 3339"):
            parse_rfc3339(value)


def test_object_field() -> None:
    assert object_field({"a": {"b": 1}}, "a") == {"b": 1}
    with pytest.raises(ReceiptRuleError, match="a must be an object"):
        object_field({"a": [1]}, "a")
    assert string_list({"a": ["x"]}, "a") == ["x"]
    with pytest.raises(ReceiptRuleError, match="a must be a list of strings"):
        string_list({"a": [1]}, "a")

"""Filesystem store: immutability, tamper detection, missing parents, cycles."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from faustcoder import (
    ArtifactNotFoundError,
    ArtifactStore,
    CanonicalError,
    CycleError,
    DigestMismatchError,
    InvalidReferenceError,
    MissingParentError,
    MutationError,
    SchemaValidationError,
    TamperError,
    canonical_bytes,
    envelope_digest_for,
)
from faustcoder import store as store_module
from tests.support import DIGEST_A, make_envelope


def _write_raw(store: ArtifactStore, envelope: dict) -> None:
    path = store.path_for(envelope["artifact_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(envelope)
    path.write_bytes(data)
    store.envelope_digest_path_for(envelope["artifact_id"]).write_bytes(
        envelope_digest_for(data).encode("ascii")
    )


def test_put_get_exists_and_list_round_trip(store: ArtifactStore, tmp_path: Path) -> None:
    root = make_envelope({"n": 1})
    child = make_envelope({"n": 2}, parents=[root["content_digest"]])
    assert store.put(root) == root["artifact_id"]
    assert store.put(child) == child["artifact_id"]
    assert store.exists(root["artifact_id"])
    assert store.exists(root["content_digest"])
    assert store.get(child["content_digest"])["payload"] == {"n": 2}
    assert store.get(child["artifact_id"])["parents"] == [root["content_digest"]]
    assert store.list() == sorted([root["artifact_id"], child["artifact_id"]])
    stored = store.path_for(root["artifact_id"]).read_bytes()
    assert stored == canonical_bytes(store.get(root["artifact_id"]))
    assert not stored.endswith(b"\n")
    assert b" " not in stored
    assert store.path_for(root["artifact_id"]) == (
        tmp_path / "sha256" / f"{root['artifact_id']}.json"
    )


def test_hash_is_independent_of_key_order(store: ArtifactStore) -> None:
    first = make_envelope({"b": 1, "a": 2})
    second = make_envelope({"a": 2, "b": 1})
    assert first["artifact_id"] == second["artifact_id"]
    assert store.put(first) == store.put(second)
    assert store.list() == [first["artifact_id"]]


def test_re_put_of_different_bytes_is_rejected(store: ArtifactStore) -> None:
    original = make_envelope({"n": 1}, producer="first")
    conflict = make_envelope({"n": 1}, producer="second")
    assert original["artifact_id"] == conflict["artifact_id"]
    store.put(original)
    before = store.path_for(original["artifact_id"]).read_bytes()
    with pytest.raises(MutationError) as caught:
        store.put(conflict)
    assert caught.value.artifact_id == original["artifact_id"]
    assert store.path_for(original["artifact_id"]).read_bytes() == before
    assert store.get(original["artifact_id"])["producer"] == "first"


def test_digest_mismatch_is_rejected_and_writes_nothing(
    store: ArtifactStore, tmp_path: Path
) -> None:
    envelope = make_envelope({"n": 1})
    envelope["artifact_id"] = "0" * 64
    with pytest.raises(DigestMismatchError):
        store.put(envelope)
    envelope = make_envelope({"n": 1})
    envelope["content_digest"] = "sha256:" + ("ab" * 32)
    with pytest.raises(DigestMismatchError):
        store.put(envelope)
    assert list(tmp_path.iterdir()) == []


def test_schema_invalid_envelope_writes_nothing(
    store: ArtifactStore, tmp_path: Path
) -> None:
    envelope = make_envelope({"n": 1}, created_at="yesterday")
    with pytest.raises(SchemaValidationError, match="created_at"):
        store.put(envelope)
    assert list(tmp_path.iterdir()) == []


def test_caller_mutation_after_build_does_not_match(store: ArtifactStore) -> None:
    payload = {"n": 1}
    envelope = make_envelope(payload)
    payload["n"] = 2
    with pytest.raises(DigestMismatchError):
        store.put(envelope)


def test_get_returns_an_independent_copy(store: ArtifactStore) -> None:
    envelope = make_envelope({"n": 1})
    store.put(envelope)
    loaded = store.get(envelope["artifact_id"])
    loaded["payload"]["n"] = 9
    assert store.get(envelope["artifact_id"])["payload"] == {"n": 1}


def test_missing_parent_is_rejected(store: ArtifactStore, tmp_path: Path) -> None:
    child = make_envelope({"n": 2}, parents=[DIGEST_A])
    with pytest.raises(MissingParentError) as caught:
        store.put(child)
    assert caught.value.content_digest == DIGEST_A
    assert list(tmp_path.iterdir()) == []


def test_self_parent_cycle_is_rejected(store: ArtifactStore, tmp_path: Path) -> None:
    envelope = make_envelope({"n": 1})
    envelope["parents"] = [envelope["content_digest"]]
    with pytest.raises(CycleError, match="cycle"):
        store.put(envelope)
    assert list(tmp_path.iterdir()) == []


def test_diamond_is_not_a_cycle(store: ArtifactStore) -> None:
    root = make_envelope({"role": "root"})
    left = make_envelope({"role": "left"}, parents=[root["content_digest"]])
    right = make_envelope({"role": "right"}, parents=[root["content_digest"]])
    child = make_envelope(
        {"role": "child"},
        parents=[left["content_digest"], right["content_digest"]],
    )
    for envelope in (root, left, right, child):
        store.put(envelope)
    assert store.get(child["artifact_id"])["payload"] == {"role": "child"}
    assert len(store.list()) == 4


def test_mutual_cycle_is_rejected_on_read_and_on_extension(store: ArtifactStore) -> None:
    first = make_envelope({"n": "a"})
    second = make_envelope({"n": "b"})
    first["parents"] = [second["content_digest"]]
    second["parents"] = [first["content_digest"]]
    _write_raw(store, first)
    _write_raw(store, second)
    with pytest.raises(CycleError):
        store.get(first["artifact_id"])
    with pytest.raises(CycleError):
        store.list()
    extension = make_envelope({"n": "c"}, parents=[first["content_digest"]])
    with pytest.raises(CycleError):
        store.put(extension)
    assert not store.exists(extension["artifact_id"])


def test_three_node_cycle_is_rejected_on_read(store: ArtifactStore) -> None:
    nodes = [make_envelope({"n": name}) for name in ("a", "b", "c")]
    for index, node in enumerate(nodes):
        node["parents"] = [nodes[(index + 1) % len(nodes)]["content_digest"]]
        _write_raw(store, node)
    with pytest.raises(CycleError):
        store.get(nodes[0]["artifact_id"])


def test_payload_edit_is_detected_on_read(store: ArtifactStore) -> None:
    envelope = make_envelope({"n": 1})
    store.put(envelope)
    path = store.path_for(envelope["artifact_id"])
    path.write_bytes(path.read_bytes().replace(b'"n":1', b'"n":2', 1))
    with pytest.raises(TamperError) as caught:
        store.get(envelope["artifact_id"])
    assert caught.value.artifact_id == envelope["artifact_id"]
    assert store.exists(envelope["artifact_id"])
    with pytest.raises(TamperError):
        store.list()


def test_non_canonical_bytes_are_detected_on_read(store: ArtifactStore) -> None:
    envelope = make_envelope({"n": 1})
    store.put(envelope)
    path = store.path_for(envelope["artifact_id"])
    path.write_bytes(path.read_bytes().replace(b"{", b"{ ", 1))
    with pytest.raises(TamperError, match="not canonical"):
        store.get(envelope["artifact_id"])


def test_re_put_does_not_repair_a_tampered_file(store: ArtifactStore) -> None:
    envelope = make_envelope({"n": 1})
    store.put(envelope)
    path = store.path_for(envelope["artifact_id"])
    path.write_bytes(b"not-json")
    with pytest.raises(MutationError):
        store.put(envelope)
    assert path.read_bytes() == b"not-json"
    with pytest.raises(TamperError):
        store.get(envelope["artifact_id"])


def test_symlink_object_is_rejected(store: ArtifactStore) -> None:
    envelope = make_envelope({"n": 1})
    store.put(envelope)
    path = store.path_for(envelope["artifact_id"])
    path.unlink()
    path.symlink_to("/etc/hostname")
    assert store.exists(envelope["artifact_id"])
    with pytest.raises(TamperError, match="symlink"):
        store.get(envelope["artifact_id"])


def test_unexpected_directory_entry_is_rejected(store: ArtifactStore) -> None:
    envelope = make_envelope({"n": 1})
    store.put(envelope)
    notes = store.path_for(envelope["artifact_id"]).parent / "notes.txt"
    notes.write_text("nope\n", encoding="utf-8")
    with pytest.raises(TamperError, match="unexpected"):
        store.list()
    assert store.get(envelope["artifact_id"])["payload"] == {"n": 1}


def test_missing_artifact_and_bad_reference(store: ArtifactStore) -> None:
    with pytest.raises(ArtifactNotFoundError):
        store.get("ab" * 32)
    assert store.exists("ab" * 32) is False
    assert store.list() == []
    for reference in ("../" + ("a" * 64), "sha256:../etc/passwd", "AB" * 32, "nope"):
        with pytest.raises(InvalidReferenceError):
            store.get(reference)


def test_bare_hex_parent_is_rejected() -> None:
    with pytest.raises(InvalidReferenceError):
        make_envelope({"n": 1}, parents=["ab" * 32])


def test_duplicate_parents_are_rejected(store: ArtifactStore) -> None:
    root = make_envelope({"n": 1})
    store.put(root)
    child = make_envelope(
        {"n": 2},
        parents=[root["content_digest"], root["content_digest"]],
    )
    with pytest.raises(SchemaValidationError, match="parents"):
        store.put(child)


def test_parent_chain_must_resolve(store: ArtifactStore) -> None:
    root = make_envelope({"n": 1})
    store.put(root)
    missing = make_envelope({"n": 2}, parents=[DIGEST_A])
    _write_raw(store, missing)
    child = make_envelope({"n": 3}, parents=[missing["content_digest"]])
    with pytest.raises(MissingParentError) as caught:
        store.put(child)
    assert caught.value.content_digest == DIGEST_A


def test_failed_publish_leaves_no_object(
    store: ArtifactStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated link failure")

    monkeypatch.setattr(store_module.os, "link", boom)
    envelope = make_envelope({"n": 1})
    with pytest.raises(OSError, match="simulated link failure"):
        store.put(envelope)
    directory = store.root / "sha256"
    names = sorted(path.name for path in directory.iterdir())
    assert names == []
    assert store.exists(envelope["artifact_id"]) is False


def test_put_leaves_no_temp_files(store: ArtifactStore) -> None:
    envelope = make_envelope({"n": 1})
    store.put(envelope)
    names = sorted(path.name for path in (store.root / "sha256").iterdir())
    artifact_id = envelope["artifact_id"]
    assert names == [
        f"{artifact_id}.envelope_digest",
        f"{artifact_id}.json",
    ]


def _replacement(field: str) -> object:
    if field == "schema_version":
        return "9.9.9"
    if field == "artifact_id":
        return "ab" * 32
    if field == "content_digest":
        return "sha256:" + ("ab" * 32)
    if field == "created_at":
        return "2026-10-18T00:00:00Z"
    if field == "producer":
        return "tampered"
    if field == "parents":
        return [DIGEST_A]
    if field == "payload":
        return {"n": 2}
    raise AssertionError(field)


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "artifact_id",
        "content_digest",
        "created_at",
        "producer",
        "parents",
        "payload",
    ],
)
def test_tamper_of_each_envelope_field_is_detected(
    store: ArtifactStore, field: str
) -> None:
    envelope = make_envelope({"n": 1})
    store.put(envelope)
    path = store.path_for(envelope["artifact_id"])
    parsed = json.loads(path.read_text(encoding="utf-8"))
    parsed[field] = _replacement(field)
    path.write_bytes(canonical_bytes(parsed))
    with pytest.raises(TamperError, match="envelope digest mismatch"):
        store.get(envelope["artifact_id"])
    with pytest.raises(TamperError, match="envelope digest mismatch"):
        store.list()


def test_sidecar_matches_the_canonical_envelope_bytes(store: ArtifactStore) -> None:
    envelope = make_envelope({"n": 1, "label": "é"})
    store.put(envelope)
    raw = store.path_for(envelope["artifact_id"]).read_bytes()
    sidecar = store.envelope_digest_path_for(envelope["artifact_id"]).read_bytes()
    assert sidecar == b"sha256:" + hashlib.sha256(raw).hexdigest().encode("ascii")
    assert envelope["artifact_id"] == hashlib.sha256(
        canonical_bytes(envelope["payload"])
    ).hexdigest()
    assert store.get(envelope["artifact_id"])["producer"] == "t02-test"


def test_sidecar_tamper_and_deletion_are_detected(store: ArtifactStore) -> None:
    envelope = make_envelope({"n": 1})
    store.put(envelope)
    sidecar = store.envelope_digest_path_for(envelope["artifact_id"])
    original = sidecar.read_bytes()
    sidecar.write_bytes(b"sha256:" + b"cd" * 32)
    with pytest.raises(TamperError, match="envelope digest mismatch"):
        store.get(envelope["artifact_id"])
    with pytest.raises(TamperError, match="envelope digest mismatch"):
        store.put(envelope)
    assert sidecar.read_bytes() == b"sha256:" + b"cd" * 32
    sidecar.unlink()
    with pytest.raises(TamperError, match="missing envelope digest"):
        store.get(envelope["artifact_id"])
    store.put(envelope)
    assert sidecar.read_bytes() == original
    assert store.get(envelope["artifact_id"])["payload"] == {"n": 1}


def test_orphan_sidecar_is_rejected(store: ArtifactStore) -> None:
    envelope = make_envelope({"n": 1})
    store.put(envelope)
    orphan = store.root / "sha256" / f"{'ab' * 32}.envelope_digest"
    orphan.write_bytes(b"sha256:" + b"ab" * 32)
    with pytest.raises(TamperError, match="without an object"):
        store.list()
    assert store.get(envelope["artifact_id"])["payload"] == {"n": 1}


def test_non_object_envelope_is_rejected(store: ArtifactStore) -> None:
    with pytest.raises(CanonicalError):
        store.put(["nope"])  # type: ignore[arg-type]


def test_store_source_does_not_import_network_clients() -> None:
    """The store does not fetch. acquire.py is the pinned-blob transport."""
    root = Path(__file__).resolve().parents[1] / "faustcoder"
    banned = ("urllib", "requests", "http.client", "httpx", "socket")
    for path in root.glob("*.py"):
        if path.name == "acquire.py":
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                for name in banned:
                    assert name not in stripped, path.name
    acquire = (root / "acquire.py").read_text(encoding="utf-8")
    assert "import urllib" in acquire
    for name in ("requests", "httpx"):
        assert name not in acquire


def test_stored_file_is_utf8_json(store: ArtifactStore) -> None:
    envelope = make_envelope({"label": "é"})
    store.put(envelope)
    parsed = json.loads(store.path_for(envelope["artifact_id"]).read_text("utf-8"))
    assert parsed["payload"] == {"label": "é"}
    assert os.access(store.path_for(envelope["artifact_id"]), os.R_OK)

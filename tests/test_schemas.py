"""Schema copies stay in sync and accept one valid and one invalid fixture each."""

from __future__ import annotations

import filecmp
import json
from pathlib import Path

import pytest

from faustcoder import (
    SchemaError,
    SchemaValidationError,
    digest_hex,
    schema_directory,
    schema_names,
    validate,
)
from tests.support import DIGEST_A

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "specs"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SOURCE_COMMIT = "fcc391e5b4360f594309f1e99cc1b8ac9baeaf9c"


def _stem(schema_name: str) -> str:
    return schema_name.removesuffix(".schema.json")


def _load(kind: str, schema_name: str) -> object:
    path = FIXTURES / kind / f"{_stem(schema_name)}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_copies_match_contracts_byte_for_byte() -> None:
    copied = sorted(schema_directory().glob("*.schema.json"))
    sources = sorted(SPECS.glob("*/contracts/*.schema.json"), key=lambda path: path.name)
    assert [path.name for path in copied] == [path.name for path in sources]
    assert copied, "expected copied schemas"
    for copy, source in zip(copied, sources, strict=True):
        assert filecmp.cmp(copy, source, shallow=False)


def test_provenance_records_the_source_commit() -> None:
    text = (schema_directory() / "README.md").read_text(encoding="utf-8")
    assert "specs/001-faustcoder/contracts/" in text
    assert SOURCE_COMMIT in text
    assert "faustcoder/canonical.py" in text
    assert "specs/002-nvidia-stack/contracts/" in text


def test_every_schema_has_a_valid_and_invalid_fixture() -> None:
    stems = {_stem(name) for name in schema_names()}
    valid = {path.stem for path in (FIXTURES / "valid").glob("*.json")}
    invalid = {path.stem for path in (FIXTURES / "invalid").glob("*.json")}
    assert stems == valid == invalid


@pytest.mark.parametrize("schema_name", schema_names())
def test_valid_fixture_passes(schema_name: str) -> None:
    validate(_load("valid", schema_name), schema_name)


@pytest.mark.parametrize("schema_name", schema_names())
def test_invalid_fixture_fails(schema_name: str) -> None:
    with pytest.raises(SchemaValidationError) as caught:
        validate(_load("invalid", schema_name), schema_name)
    assert caught.value.schema_name == schema_name
    assert caught.value.detail


def test_envelope_schema_does_not_bind_the_digest() -> None:
    envelope = _load("valid", "artifact-envelope.schema.json")
    assert isinstance(envelope, dict)
    validate(envelope, "artifact-envelope.schema.json")
    assert envelope["artifact_id"] != digest_hex(envelope["payload"])


def test_envelope_rejects_a_bad_digest_pattern() -> None:
    envelope = _load("valid", "artifact-envelope.schema.json")
    assert isinstance(envelope, dict)
    envelope["content_digest"] = "sha256:not-a-digest"
    with pytest.raises(SchemaValidationError, match="content_digest"):
        validate(envelope, "artifact-envelope.schema.json")


def test_envelope_rejects_duplicate_parents() -> None:
    envelope = _load("valid", "artifact-envelope.schema.json")
    assert isinstance(envelope, dict)
    envelope["parents"] = [DIGEST_A, DIGEST_A]
    with pytest.raises(SchemaValidationError, match="parents"):
        validate(envelope, "artifact-envelope.schema.json")


def test_unknown_schema_and_missing_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SchemaError, match="unknown schema"):
        validate({}, "nope.schema.json")
    monkeypatch.setenv("FAUSTCODER_SCHEMA_DIR", str(tmp_path))
    with pytest.raises(SchemaError, match="not found"):
        schema_directory()


def test_schemas_do_not_use_refs() -> None:
    for path in schema_directory().glob("*.schema.json"):
        assert "$ref" not in path.read_text(encoding="utf-8")

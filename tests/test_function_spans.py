"""Reviewed spans must never silently fall back to the full source blob."""

import copy
import json

import pytest

from faustcoder.canonical import canonical_bytes, sha256_prefixed
from faustcoder.errors import InventoryError, AcquireError
from faustcoder.function_spans import extract_span
from faustcoder.snapshot import compile_snapshot
from tests.t06support import (
    ACTOR,
    CREATED_AT,
    PIN,
    REPO,
    entry,
    notice_row,
    inventory_doc,
    notice_doc,
    pins_for,
    span_manifest,
)

RAW = (
    b'// header\r\ngain(x) = x * 0.5\r\n with { label = "a; }"; };\r\nother = 123;\r\n'
)
START = RAW.index(b"gain(")
END = RAW.index(b"other")


def setup_case():
    inv = inventory_doc([entry("gain", RAW, path="a.lib", function="gain")])
    notices = notice_doc([notice_row(RAW, path="a.lib", function="gain")])
    spans, digest = span_manifest(inv, notices, {"gain": (RAW, START, END)})
    return inv, notices, spans, digest


def run_case(inv, notices, spans, digest, raw=RAW, sealed=()):
    class Fetcher:
        def fetch(self, *args):
            return raw

    with pins_for(inv, notices):
        return compile_snapshot(
            inv,
            notices,
            Fetcher(),
            actor=ACTOR,
            created_at=CREATED_AT,
            function_spans=spans,
            function_spans_digest=digest,
            sealed=sealed,
        )


def test_exact_multiline_range_binds_provenance_and_is_repeatable():
    args = setup_case()
    result = run_case(*args)
    assert result.manifest_digest == run_case(*args).manifest_digest
    example = next(
        e["payload"]
        for e in result.envelopes
        if e["payload"].get("record_type") == "Example"
    )
    assert example["faust_source"] == RAW[START:END].decode().replace("\r\n", "\n")
    assert (
        "other" not in example["faust_source"]
        and "// header" not in example["faust_source"]
    )
    assert example["original_sha256"] == sha256_prefixed(RAW)
    assert example["function_span"]["sha256"] == sha256_prefixed(RAW[START:END])
    assert example["function_span"]["manifest_digest"] == args[3]
    manifest = result.envelopes[-1]["payload"]
    assert manifest["units"][0]["function_span"] == example["function_span"]
    assert manifest["near_duplicate"]["token_floor"] == 40
    assert manifest["near_duplicate"]["token_floor_status"] == "provisional"
    assert manifest["split_frozen"] is False


def test_missing_manifest_refuses_before_fetch():
    inv, notices, _, _ = setup_case()

    class NoFetch:
        def fetch(self, *args):
            pytest.fail("unverified function must not be fetched")

    with pins_for(inv, notices), pytest.raises(InventoryError, match="required"):
        compile_snapshot(inv, notices, NoFetch(), actor=ACTOR, created_at=CREATED_AT)


@pytest.mark.parametrize(
    "kind",
    [
        "pin",
        "notice",
        "inventory",
        "function",
        "duplicate",
        "missing",
        "unknown",
        "negative",
        "bool",
        "empty",
        "out_of_bounds",
        "hash",
        "reviewer",
        "extra",
    ],
)
def test_invalid_reviewed_manifest_refuses(kind):
    inv, notices, spans, _ = setup_case()
    row = spans["spans"][0]
    if kind == "pin":
        row["pin"] = "b" * 40
    elif kind == "notice":
        spans["notice_digest"] = "sha256:" + "0" * 64
    elif kind == "inventory":
        spans["inventory_digest"] = "sha256:" + "0" * 64
    elif kind == "function":
        row["function"] = "gain@2"
    elif kind == "duplicate":
        spans["spans"].append(copy.deepcopy(row))
    elif kind == "missing":
        spans["spans"] = []
    elif kind == "unknown":
        row["unit_id"] = "unknown"
    elif kind == "negative":
        row["start_byte"] = -1
    elif kind == "bool":
        row["start_byte"] = True
    elif kind == "empty":
        row["end_byte"] = row["start_byte"]
    elif kind == "out_of_bounds":
        row["end_byte"] = len(RAW) + 1
    elif kind == "hash":
        row["sha256"] = "sha256:" + "0" * 64
    elif kind == "reviewer":
        spans["reviewer"] = ""
    elif kind == "extra":
        row["ignored_range"] = [0, 1000]
    # Even a newly pinned document must pass structural, identity and content checks.
    digest = sha256_prefixed(canonical_bytes(spans))
    with pytest.raises(InventoryError):
        run_case(inv, notices, spans, digest)


def test_altered_document_and_blob_refused():
    inv, notices, spans, digest = setup_case()
    with pytest.raises(AcquireError):
        run_case(inv, notices, spans, digest, RAW + b"changed")
    spans["reviewer"] = "changed"
    with pytest.raises(InventoryError, match="digest mismatch"):
        run_case(inv, notices, spans, digest)


def test_utf8_boundary_and_whitespace_refused():
    raw = "é".encode()
    with pytest.raises(InventoryError, match="UTF-8"):
        extract_span(
            raw, {"start_byte": 1, "end_byte": 2, "sha256": sha256_prefixed(raw[1:])}
        )
    with pytest.raises(InventoryError, match="empty"):
        extract_span(
            b" \n", {"start_byte": 0, "end_byte": 2, "sha256": sha256_prefixed(b" \n")}
        )


def test_overloads_and_overlap():
    raw = b"f(0) = 0;\nf(x) = x + 1;\n"
    names = ["f@1", "f@2"]
    inv = inventory_doc([entry(n, raw, path="a.lib", function=n) for n in names])
    notices = notice_doc([notice_row(raw, path="a.lib", function=n) for n in names])
    spans, digest = span_manifest(
        inv, notices, {"f@1": (raw, 0, 10), "f@2": (raw, 10, len(raw))}
    )
    result = run_case(inv, notices, spans, digest, raw)
    assert result.unit_count == 2
    assert {
        e["payload"]["faust_source"]
        for e in result.envelopes
        if e["payload"].get("record_type") == "Example"
    } == {"f(0) = 0;\n", "f(x) = x + 1;\n"}
    spans["spans"][1]["start_byte"] = 9
    with pytest.raises(InventoryError, match="overlapping"):
        run_case(inv, notices, spans, sha256_prefixed(canonical_bytes(spans)), raw)


def test_sealed_function_text_not_emitted():
    inv, notices, spans, digest = setup_case()
    result = run_case(
        inv,
        notices,
        spans,
        digest,
        sealed=[{"repo": REPO, "commit": PIN, "path": "a.lib", "function": "gain"}],
    )
    assert not any(
        e["payload"].get("record_type") == "Example" for e in result.envelopes
    )
    assert result.envelopes[-1]["payload"]["function_spans_digest"] == digest
    assert b"gain(x)" not in canonical_bytes(list(result.envelopes))


def test_cli_verified_spans_and_missing_digest(tmp_path, capsys):
    from faustcoder.cli import main
    from tests.t06support import stage

    inv, notices, spans, digest = setup_case()
    for name, doc in [("inventory", inv), ("notice", notices), ("spans", spans)]:
        (tmp_path / (name + ".json")).write_text(json.dumps(doc))
    stage(tmp_path / "fixtures", REPO, PIN, "a.lib", RAW)
    args = [
        "--inventory",
        str(tmp_path / "inventory.json"),
        "--notice",
        str(tmp_path / "notice.json"),
        "--store",
        str(tmp_path / "store"),
        "--created-at",
        CREATED_AT,
        "--fetcher",
        "fixture",
        "--fixture-root",
        str(tmp_path / "fixtures"),
        "--function-spans",
        str(tmp_path / "spans.json"),
    ]
    with pins_for(inv, notices):
        assert main(args) == 2
        assert not (tmp_path / "store").exists()
        assert main(args + ["--function-spans-digest", digest]) == 0
    assert list((tmp_path / "store").rglob("*.json"))


def test_runtime_manifest_matches_schema():
    from faustcoder import validate

    _, _, spans, _ = setup_case()
    validate(spans, "function-spans.schema.json")


def test_span_cannot_override_rejected_neighbor():
    inv, notices, spans, digest = setup_case()
    inv["entries"].append(
        entry(
            "other",
            RAW,
            path="a.lib",
            function="other",
            decision="rights_rejected",
            license_name="AGPL-3.0-only",
            eligible_for=[],
            reviewer="",
            reason="rejected neighbor",
        )
    )
    # Updating document pins still cannot restore a unit quarantined by T05.
    from faustcoder.inventory import content_digest

    spans["inventory_digest"] = content_digest(inv)
    with pytest.raises(InventoryError, match="unknown"):
        run_case(inv, notices, spans, sha256_prefixed(canonical_bytes(spans)))
    result = run_case(inv, notices, None, None)
    assert result.unit_count == 0
    assert not any(
        e["payload"].get("record_type") == "Example" for e in result.envelopes
    )


def test_same_line_span_and_review_change_affect_evidence():
    raw = b"gain(x) = x; other(x) = 2*x;"
    inv = inventory_doc([entry("gain", raw, path="a.lib", function="gain")])
    notices = notice_doc([notice_row(raw, path="a.lib", function="gain")])
    spans, digest = span_manifest(inv, notices, {"gain": (raw, 0, 12)})
    first = run_case(inv, notices, spans, digest, raw)
    text = next(
        e["payload"]["faust_source"]
        for e in first.envelopes
        if e["payload"].get("record_type") == "Example"
    )
    assert text == "gain(x) = x;"
    spans["reviewer"] = "second review"
    second = run_case(inv, notices, spans, sha256_prefixed(canonical_bytes(spans)), raw)
    assert first.manifest_digest != second.manifest_digest

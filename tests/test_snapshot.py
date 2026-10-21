"""Deterministic dedup manifest. Fixture fetcher only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from faustcoder.acquire import git_blob_sha1, git_blob_sha256
from faustcoder.canonical import canonical_bytes
from faustcoder.dataset import PRODUCER, current_state
from faustcoder.errors import AcquireError, InventoryError, MutationError
from faustcoder.inventory import content_digest, parse_corpus
from faustcoder.libraries import library_root
from faustcoder.neardup import (
    containment_at_least,
    has_verbatim_run,
    is_excerpt,
    is_near_duplicate,
    shingles,
    tokens,
)
from faustcoder.snapshot import commit_snapshot, compile_snapshot
from faustcoder.store import ArtifactStore

from faustcoder.upstream import UPSTREAM_ORIGINALS, UpstreamOriginal

from tests.t06support import (
    ACTOR,
    CREATED_AT,
    PIN,
    REPO,
    REVIEWER,
    cleared,
    entry,
    inventory_doc,
    long_text,
    notice_doc,
    notice_row,
    parse_pinned,
    pins_for,
    stage,
)


def _compile(
    root: Path,
    entries: list[dict[str, object]],
    notices: list[dict[str, object]],
    *,
    created_at: str = CREATED_AT,
    actor: str = ACTOR,
    inventory_at: str | None = None,
    notice_at: str | None = None,
    sealed: list[dict[str, str]] | None = None,
    function_spans=None,
    function_spans_digest=None,
):
    from faustcoder.acquire import DirectoryFetcher

    inventory = inventory_doc(entries) if inventory_at is None else inventory_doc(entries, inventory_at)
    notice = notice_doc(notices) if notice_at is None else notice_doc(notices, notice_at)
    with pins_for(inventory, notice):
        return compile_snapshot(
            inventory,
            notice,
            DirectoryFetcher(root),
            actor=actor,
            created_at=created_at,
            sealed=sealed or (),
            function_spans=function_spans,
            function_spans_digest=function_spans_digest,
        )


def _manifest(compiled) -> dict[str, object]:
    return compiled.envelopes[-1]["payload"]


def _by_entry(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row["entry_id"]): row for row in rows}


def test_same_clock_is_byte_identical_and_shuffle_does_not_matter(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    entries, notices = _two(root)
    first = _compile(root, entries, notices)
    second = _compile(root, list(reversed(entries)), list(reversed(notices)))
    near = _manifest(first)["near_duplicate"]
    assert near["token_floor"] == 40  # type: ignore[index]
    assert near["token_floor_status"] == "provisional"  # type: ignore[index]
    assert near["min_tokens"] == near["verbatim_run"] == near["token_floor"]  # type: ignore[index]
    assert first.manifest_digest == second.manifest_digest
    assert content_digest(inventory_doc(entries)) == content_digest(
        inventory_doc(list(reversed(entries)))
    )
    assert [canonical_bytes(item) for item in first.envelopes] == [
        canonical_bytes(item) for item in second.envelopes
    ]
    left = ArtifactStore(tmp_path / "left")
    right = ArtifactStore(tmp_path / "right")
    assert commit_snapshot(left, first) == commit_snapshot(right, second)
    left_files = sorted(path.read_bytes() for path in (tmp_path / "left").rglob("*.json"))
    right_files = sorted(path.read_bytes() for path in (tmp_path / "right").rglob("*.json"))
    assert left_files == right_files


def test_created_at_changes_envelope_bytes_and_not_the_manifest_digest(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    entries, notices = _two(root)
    first = _compile(root, entries, notices, created_at=CREATED_AT)
    second = _compile(root, entries, notices, created_at="2026-10-17T20:00:01Z")
    assert first.manifest_digest == second.manifest_digest
    assert canonical_bytes(first.envelopes[-1]) != canonical_bytes(second.envelopes[-1])
    store = ArtifactStore(tmp_path / "store")
    digest = commit_snapshot(store, first)
    before = store.path_for(digest).read_bytes()
    with pytest.raises(MutationError):
        commit_snapshot(store, second)
    assert store.path_for(digest).read_bytes() == before


def test_generated_at_does_not_change_the_manifest_digest(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    entries, notices = _two(root)
    first = _compile(root, entries, notices)
    second = _compile(
        root,
        entries,
        notices,
        inventory_at="2026-10-17T13:05:00Z",
        notice_at="2026-10-18T00:00:00Z",
    )
    assert first.manifest_digest == second.manifest_digest
    assert _manifest(first)["inventory_digest"] == _manifest(second)["inventory_digest"]
    assert _manifest(first)["notice_digest"] == _manifest(second)["notice_digest"]
    assert content_digest(inventory_doc(entries)) == content_digest(
        inventory_doc(entries, "2026-10-17T13:05:00Z")
    )
    stored = b"".join(canonical_bytes(item) for item in first.envelopes)
    assert b"retrieved_at" not in stored


def test_actor_is_never_the_reviewer(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    data = b"process = 1;\n"
    stage(root, REPO, PIN, "osc.dsp", data)
    row, notice = cleared("osc", data, path="osc.dsp")
    actor = "faustcoder-snapshot"
    compiled = _compile(root, [row], [notice], actor=actor)
    payload = _manifest(compiled)
    assert payload["units"][0]["reviewer"] == REVIEWER  # type: ignore[index]
    for envelope in compiled.envelopes:
        body = envelope["payload"]
        assert body.get("record_type") != "RightsRecord"
        assert body.get("reviewer") != actor
        assert envelope["producer"] == PRODUCER
        assert body.get("event") != "rights_cleared"
    bare_data = b"process = 2;\n"
    stage(root, REPO, PIN, "bare.dsp", bare_data)
    bare = entry("bare", bare_data, path="bare.dsp", reviewer="")
    bare_notice = notice_row(bare_data, path="bare.dsp")
    compiled = _compile(root, [bare], [bare_notice], actor=actor)
    excluded = _manifest(compiled)["excluded"][0]  # type: ignore[index]
    assert excluded["reason"] == "needs-human"
    assert excluded["entry_id"] == "bare"
    assert _manifest(compiled)["units"] == []
    for envelope in compiled.envelopes:
        assert envelope["payload"].get("reviewer") != actor


def test_training_only_impulse_path_is_carried(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    data = b"process = 1;\n"
    path = "tests/impulse-tests/osc.dsp"
    stage(root, REPO, PIN, path, data)
    row, notice = cleared(
        "faust-impulse-osc",
        data,
        path=path,
        license_name="GPL-3.0-only",
        eligible_for=["train"],
    )
    compiled = _compile(root, [row], [notice])
    unit = _manifest(compiled)["units"][0]  # type: ignore[index]
    assert unit["training_only"] is True
    assert unit["impulse"] is True
    assert unit["eligible_for"] == ["train"]


def test_impulse_substring_does_not_drop_eval(tmp_path: Path) -> None:
    """A path that merely contains the letters impulse is not an impulse test."""
    root = tmp_path / "fixtures"
    data = b"process = 1;\n"
    path = "examples/impulseResponse.dsp"
    stage(root, REPO, PIN, path, data)
    row, notice = cleared("faust-examples-mit", data, path=path)
    compiled = _compile(root, [row], [notice])
    unit = _manifest(compiled)["units"][0]  # type: ignore[index]
    assert unit["impulse"] is False
    assert unit["eligible_for"] == ["train", "eval", "redistribute"]


def test_impulse_entry_id_with_eval_is_refused(tmp_path: Path) -> None:
    """Entry id faust-impulse-* refuses eval even when the path is not impulse-tests."""
    root = tmp_path / "fixtures"
    data = b"process = 1;\n"
    path = "examples/readme-only.dsp"
    stage(root, REPO, PIN, path, data)
    row, notice = cleared(
        "faust-impulse-readme",
        data,
        path=path,
        eligible_for=["train", "eval", "redistribute"],
    )
    compiled = _compile(root, [row], [notice])
    payload = _manifest(compiled)
    assert payload["units"] == []
    excluded = payload["excluded"][0]  # type: ignore[index]
    assert excluded["reason"] == "impulse-eval"
    assert excluded["entry_id"] == "faust-impulse-readme"
    assert "eval" not in (excluded.get("eligible_for") or [])


def test_manifest_has_no_program_text(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    sentinel = "UNIQUE_SENTINEL_OSC"
    data = f"process = {sentinel};\n".encode()
    stage(root, REPO, PIN, "osc.dsp", data)
    row, notice = cleared("osc", data, path="osc.dsp")
    compiled = _compile(root, [row], [notice])
    payload = _manifest(compiled)
    assert payload["record_type"] == "DedupManifest"
    assert payload["lifecycle"] == "DEDUPED"
    assert payload["split_frozen"] is False
    rendered = canonical_bytes(payload).decode()
    assert "faust_source" not in rendered
    assert sentinel not in rendered
    store = ArtifactStore(tmp_path / "store")
    commit_snapshot(store, compiled)
    examples = [
        store.get(artifact_id)["payload"]["faust_source"]
        for artifact_id in store.list()
        if store.get(artifact_id)["payload"].get("record_type") == "Example"
    ]
    assert sentinel in examples[0]
    source = next(
        store.get(artifact_id)
        for artifact_id in store.list()
        if store.get(artifact_id)["payload"].get("record_type") == "SourceRecord"
    )
    assert "retrieved_at" not in source["payload"]
    assert current_state(store, source["content_digest"]) == "DEDUPED"


def test_same_license_family_intersects_flags(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    left = long_text("beta").encode()
    right = long_text("beta", replacement="renamed").encode()
    assert is_near_duplicate(left.decode(), right.decode()) is True
    stage(root, REPO, PIN, "full.dsp", left)
    stage(root, REPO, PIN, "train.dsp", right)
    full, full_notice = cleared("full", left, path="full.dsp")
    narrow, narrow_notice = cleared(
        "trainonly",
        right,
        path="train.dsp",
        eligible_for=["train"],
    )
    compiled = _compile(root, [full, narrow], [full_notice, narrow_notice])
    rows = _by_entry(_manifest(compiled)["units"])  # type: ignore[arg-type]
    assert rows["full"]["eligible_for"] == ["train"]
    assert rows["trainonly"]["eligible_for"] == ["train"]
    assert rows["full"]["rights_narrowed"] is True
    assert rows["trainonly"]["rights_narrowed"] is False
    assert rows["full"]["duplicate_family"] == rows["trainonly"]["duplicate_family"]
    assert "eval" not in rows["full"]["eligible_for"]
    assert "redistribute" not in rows["full"]["eligible_for"]


def test_mixed_license_near_duplicate_is_quarantined(tmp_path: Path) -> None:
    """A one-token MIT copy of a GPL training-only unit keeps neither eval nor redistribute."""
    root = tmp_path / "fixtures"
    original = long_text("alpha").encode()
    edited = long_text("alpha", replacement="renamed").encode()
    assert is_near_duplicate(original.decode(), edited.decode()) is True
    stage(root, REPO, PIN, "gpl.dsp", original)
    stage(root, REPO, PIN, "mit.dsp", edited)
    gpl, gpl_notice = cleared(
        "gpl",
        original,
        path="gpl.dsp",
        license_name="GPL-2.0-or-later",
        eligible_for=["train"],
    )
    mit, mit_notice = cleared("mit", edited, path="mit.dsp", license_name="MIT")
    compiled = _compile(root, [gpl, mit], [gpl_notice, mit_notice])
    payload = _manifest(compiled)
    assert payload["units"] == []
    assert payload["example_digests"] == []
    excluded = _by_entry(payload["excluded"])  # type: ignore[arg-type]
    assert excluded["gpl"]["reason"] == "needs-human"
    assert excluded["mit"]["reason"] == "needs-human"
    assert excluded["gpl"]["origin"] == "dedup"
    assert excluded["mit"]["origin"] == "dedup"
    assert excluded["gpl"]["duplicate_family"] == excluded["mit"]["duplicate_family"]
    store = ArtifactStore(tmp_path / "store")
    commit_snapshot(store, compiled)
    blob = b"".join(path.read_bytes() for path in store.root.rglob("*") if path.is_file())
    assert b"renamed" not in blob
    assert b"alpha0" not in blob
    for artifact_id in store.list():
        body = store.get(artifact_id)["payload"]
        flags = body.get("eligible_for") or []
        assert "eval" not in flags
        assert "redistribute" not in flags


def test_rejected_row_without_a_blob_is_not_fetched() -> None:
    class _Boom:
        def fetch(self, repo: str, pin: str, path: str, blob_sha: str) -> bytes:
            raise AssertionError("fetched a row that names no blob")

    rejected = {
        "id": "syfala-examples",
        "decision": "rights_rejected",
        "license": "unknown",
        "eligible_for": [],
        "pin": {"repo": REPO, "commit": PIN, "ref": "fixture"},
        "evidence_label": "OBSERVED",
        "attribution": "Acme Example",
        "reviewer": "",
        "reason": "no file list on the row",
    }
    inventory = inventory_doc([rejected])
    notice = notice_doc([])
    with pins_for(inventory, notice):
        compiled = compile_snapshot(
            inventory,
            notice,
            _Boom(),
            actor=ACTOR,
            created_at=CREATED_AT,
        )
    row = _manifest(compiled)["excluded"][0]  # type: ignore[index]
    assert row["entry_id"] == "syfala-examples"
    assert row["origin"] == "inventory"
    assert row["reason"] == "no file list on the row"
    assert _manifest(compiled)["units"] == []


def test_listed_blob_sha_is_sha1_or_sha256(tmp_path: Path) -> None:
    """A listed spec rejects the zero placeholder and any other length."""

    def rejected(blob_sha: str) -> dict[str, object]:
        return {
            "id": "bad-blob",
            "decision": "rights_rejected",
            "license": "unknown",
            "eligible_for": [],
            "pin": {"repo": REPO, "commit": PIN, "ref": "fixture"},
            "evidence_label": "OBSERVED",
            "attribution": "Acme Example",
            "reviewer": "",
            "reason": "bad blob id",
            "file_count": 1,
            "files": [{"path": "bad.dsp", "blob_sha": blob_sha}],
        }

    for blob_sha in ("0" * 40, "0" * 64, "g" * 40, "A" * 40, "ab", "ab" * 20 + "zz"):
        with pytest.raises(InventoryError, match="blob_sha"):
            parse_pinned(inventory_doc([rejected(blob_sha)]), notice_doc([]))
    data = b"process = 1;\n"
    digest = git_blob_sha256(data)
    corpus = parse_pinned(inventory_doc([rejected(digest)]), notice_doc([]))
    assert corpus.comparisons[0].blob_sha == digest
    root = tmp_path / "fixtures"
    stage(root, REPO, PIN, "bad.dsp", data)
    compiled = _compile(root, [rejected(digest)], [])
    assert _manifest(compiled)["units"] == []
    assert _manifest(compiled)["excluded"][0]["origin"] == "inventory"  # type: ignore[index]
    stage(root, REPO, PIN, "bad.dsp", b"process = 2;\n")
    with pytest.raises(AcquireError, match="blob_sha"):
        _compile(root, [rejected(digest)], [])


def test_half_excerpt_of_a_rejected_unit_is_needs_human(tmp_path: Path) -> None:
    """A 50% verbatim excerpt is under Jaccard 4/5 and still needs-human."""
    root = tmp_path / "fixtures"
    whole = long_text("lib", count=80).encode()
    excerpt = (" ".join(whole.decode().split()[:40]) + "\n").encode()
    other = long_text("gamma").encode()
    assert is_near_duplicate(excerpt.decode(), whole.decode()) is False
    assert is_excerpt(excerpt.decode(), whole.decode()) is True
    stage(root, REPO, PIN, "gpl.dsp", whole)
    stage(root, REPO, PIN, "mit.dsp", excerpt)
    stage(root, REPO, PIN, "other.dsp", other)
    refused = entry(
        "gpl",
        whole,
        path="gpl.dsp",
        decision="rights_rejected",
        license_name="GPL-2.0-or-later",
        eligible_for=[],
        reason="GPL source is not cleared",
        reviewer="",
    )
    mit, mit_notice = cleared("mit", excerpt, path="mit.dsp", license_name="MIT")
    kept, kept_notice = cleared("other", other, path="other.dsp")
    compiled = _compile(root, [refused, mit, kept], [mit_notice, kept_notice])
    payload = _manifest(compiled)
    assert [row["entry_id"] for row in payload["units"]] == ["other"]  # type: ignore[index]
    excluded = _by_entry(payload["excluded"])  # type: ignore[arg-type]
    assert excluded["mit"]["reason"] == "needs-human"
    assert excluded["mit"]["origin"] == "dedup"
    assert excluded["gpl"]["origin"] == "inventory"
    assert excluded["gpl"]["duplicate_family"] == excluded["mit"]["duplicate_family"]
    store = ArtifactStore(tmp_path / "store")
    commit_snapshot(store, compiled)
    stored = b"".join(path.read_bytes() for path in store.root.rglob("*") if path.is_file())
    assert b"lib0" not in stored
    assert b"gamma0" in stored


def test_half_excerpt_of_a_holdout_is_a_leak(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    whole = long_text("hold", count=80).encode()
    excerpt = (" ".join(whole.decode().split()[:40]) + "\n").encode()
    other = long_text("gamma").encode()
    assert is_near_duplicate(excerpt.decode(), whole.decode()) is False
    stage(root, REPO, PIN, "sealed.dsp", whole)
    stage(root, REPO, PIN, "excerpt.dsp", excerpt)
    stage(root, REPO, PIN, "other.dsp", other)
    sealed_row, sealed_notice = cleared("sealed", whole, path="sealed.dsp")
    excerpt_row, excerpt_notice = cleared("excerpt", excerpt, path="excerpt.dsp")
    other_row, other_notice = cleared("other", other, path="other.dsp")
    compiled = _compile(
        root,
        [sealed_row, excerpt_row, other_row],
        [sealed_notice, excerpt_notice, other_notice],
        sealed=[{"repo": REPO, "commit": PIN, "path": "sealed.dsp", "function": ""}],
    )
    payload = _manifest(compiled)
    assert [row["entry_id"] for row in payload["units"]] == ["other"]  # type: ignore[index]
    excluded = _by_entry(payload["excluded"])  # type: ignore[arg-type]
    assert excluded["excerpt"]["reason"] == "holdout-family"
    assert excluded["excerpt"]["origin"] == "dedup"


def test_upstream_original_stays_cleared_when_the_copy_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "fixtures"
    original = long_text("birds", count=80).encode()
    copied = long_text("birds", count=80, replacement="copied").encode()
    laundered = long_text("birds", count=80, replacement="laundered").encode()
    other = long_text("gamma").encode()
    assert is_near_duplicate(original.decode(), copied.decode()) is True
    stage(root, REPO, PIN, "Birds.dsp", original)
    stage(root, REPO, PIN, "birds.dsp", copied)
    stage(root, REPO, PIN, "copy.dsp", laundered)
    stage(root, REPO, PIN, "other.dsp", other)
    birds, birds_notice = cleared("birds", original, path="Birds.dsp")
    refused = entry(
        "syfala-examples",
        copied,
        path="birds.dsp",
        decision="rights_rejected",
        license_name="unlicensed",
        eligible_for=[],
        reason="Syfala has no repository license",
        reviewer="",
    )
    extra, extra_notice = cleared("extra", laundered, path="copy.dsp")
    kept, kept_notice = cleared("other", other, path="other.dsp")
    entries = [birds, refused, extra, kept]
    notices = [birds_notice, extra_notice, kept_notice]
    blocked = _compile(root, entries, notices)
    assert "birds" not in _by_entry(_manifest(blocked)["units"])  # type: ignore[arg-type]
    import faustcoder.upstream as upstream

    monkeypatch.setattr(
        upstream,
        "UPSTREAM_ORIGINALS",
        (
            UpstreamOriginal(
                blob_sha=git_blob_sha1(original),
                repo=REPO,
                path="Birds.dsp",
                copy_repo=REPO,
                copy_path="birds.dsp",
                copied_on="2024-02-13",
                evidence="c" * 40,
            ),
        ),
    )
    compiled = _compile(root, entries, notices)
    payload = _manifest(compiled)
    rows = _by_entry(payload["units"])  # type: ignore[arg-type]
    assert rows["birds"]["eligible_for"] == ["train", "eval", "redistribute"]
    assert "extra" not in rows
    excluded = _by_entry(payload["excluded"])  # type: ignore[arg-type]
    assert excluded["extra"]["reason"] == "needs-human"
    assert excluded["extra"]["origin"] == "dedup"
    assert excluded["syfala-examples"]["origin"] == "inventory"


def test_vendored_rejected_file_plus_padding_is_needs_human(tmp_path: Path) -> None:
    """Rejected R plus twice as much of the cleared file's own code is needs-human."""
    root = tmp_path / "fixtures"
    rejected_text = long_text("rejected", count=80)
    cleared_text = rejected_text.strip() + " " + long_text("pad", count=160)
    other = long_text("gamma")
    assert is_near_duplicate(cleared_text, rejected_text) is False
    assert is_excerpt(cleared_text, rejected_text) is True
    rejected_bytes = rejected_text.encode()
    cleared_bytes = cleared_text.encode()
    other_bytes = other.encode()
    stage(root, REPO, PIN, "gpl.dsp", rejected_bytes)
    stage(root, REPO, PIN, "mit.dsp", cleared_bytes)
    stage(root, REPO, PIN, "other.dsp", other_bytes)
    refused = entry(
        "gpl",
        rejected_bytes,
        path="gpl.dsp",
        decision="rights_rejected",
        license_name="GPL-2.0-or-later",
        eligible_for=[],
        reason="GPL source is not cleared",
        reviewer="",
    )
    mit, mit_notice = cleared("mit", cleared_bytes, path="mit.dsp", license_name="MIT")
    kept, kept_notice = cleared("other", other_bytes, path="other.dsp")
    compiled = _compile(root, [refused, mit, kept], [mit_notice, kept_notice])
    payload = _manifest(compiled)
    assert [row["entry_id"] for row in payload["units"]] == ["other"]  # type: ignore[index]
    excluded = _by_entry(payload["excluded"])  # type: ignore[arg-type]
    assert excluded["mit"]["reason"] == "needs-human"
    assert excluded["mit"]["origin"] == "dedup"
    assert excluded["gpl"]["origin"] == "inventory"
    assert excluded["gpl"]["duplicate_family"] == excluded["mit"]["duplicate_family"]
    store = ArtifactStore(tmp_path / "store")
    commit_snapshot(store, compiled)
    stored = b"".join(path.read_bytes() for path in store.root.rglob("*") if path.is_file())
    assert b"rejected0" not in stored
    assert b"gamma0" in stored


def _words(count: int, prefix: str) -> list[str]:
    return [f"{prefix}{index}" for index in range(count)]


def _rejected_347(*, edit: bool) -> str:
    words = _words(347, "w")
    if edit:
        index = 17
        while index < 347:
            words[index] = f"edited{index}"
            index += 34
    return " ".join(words) + "\n"


def _interleave_statements(rejected: str) -> str:
    words = rejected.split()
    parts: list[str] = []
    own = 0
    for start in range(0, len(words), 34):
        parts.append(" ".join(words[start : start + 34]))
        if start + 34 < len(words):
            parts.append(" ".join(_words(40, f"own{own}_")))
            own += 40
    return " ".join(parts) + "\n"


def test_reverse_containment_of_a_rejected_file_is_needs_human(tmp_path: Path) -> None:
    """Edited padding and interleaved statements are needs-human, origin dedup.

    The unpadded edit is the control. It is already a forward excerpt.
    """
    root = tmp_path / "fixtures"
    rejected = _rejected_347(edit=False)
    edited = _rejected_347(edit=True)
    padded = edited.strip() + " " + " ".join(_words(347, "pad"))
    wider = edited.strip() + " " + " ".join(_words((347 * 8) // 5, "wide"))
    interleaved = _interleave_statements(rejected)
    other = long_text("gamma")
    assert len(tokens(rejected)) == 347
    assert has_verbatim_run(tokens(padded), tokens(rejected)) is False
    assert has_verbatim_run(tokens(wider), tokens(rejected)) is False
    assert has_verbatim_run(tokens(interleaved), tokens(rejected)) is False
    for planted in (padded, wider, interleaved):
        assert containment_at_least(shingles(tokens(planted)), shingles(tokens(rejected))) is False
        assert containment_at_least(shingles(tokens(rejected)), shingles(tokens(planted))) is True
        assert is_excerpt(planted, rejected) is True
    assert is_excerpt(edited, rejected) is True
    texts = {
        "gpl.dsp": rejected,
        "control.dsp": edited,
        "pad.dsp": padded,
        "wide.dsp": wider,
        "interleaved.dsp": interleaved,
        "other.dsp": other,
    }
    for path, text in texts.items():
        stage(root, REPO, PIN, path, text.encode())
    refused = entry(
        "gpl",
        rejected.encode(),
        path="gpl.dsp",
        decision="rights_rejected",
        license_name="GPL-2.0-or-later",
        eligible_for=[],
        reason="GPL source is not cleared",
        reviewer="",
    )
    rows = []
    notices = []
    for entry_id, path in (
        ("control", "control.dsp"),
        ("pad", "pad.dsp"),
        ("wide", "wide.dsp"),
        ("interleaved", "interleaved.dsp"),
        ("other", "other.dsp"),
    ):
        built, notice = cleared(entry_id, texts[path].encode(), path=path)
        rows.append(built)
        notices.append(notice)
    compiled = _compile(root, [refused, *rows], notices)
    payload = _manifest(compiled)
    assert [row["entry_id"] for row in payload["units"]] == ["other"]  # type: ignore[index]
    excluded = _by_entry(payload["excluded"])  # type: ignore[arg-type]
    for entry_id in ("control", "pad", "wide", "interleaved"):
        assert excluded[entry_id]["reason"] == "needs-human"
        assert excluded[entry_id]["origin"] == "dedup"
        assert excluded[entry_id]["duplicate_family"] == excluded["gpl"]["duplicate_family"]
    assert excluded["gpl"]["origin"] == "inventory"
    store = ArtifactStore(tmp_path / "store")
    commit_snapshot(store, compiled)
    stored = b"".join(path.read_bytes() for path in store.root.rglob("*") if path.is_file())
    assert b"w0" not in stored
    assert b"gamma0" in stored


def test_allowlist_keeps_reverse_containment_of_the_recorded_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reverse containment does not clear past the recorded copy path."""
    root = tmp_path / "fixtures"
    rejected = _rejected_347(edit=False)
    edited = _rejected_347(edit=True)
    original = (edited.strip() + " " + " ".join(_words(347, "pad"))).encode()
    copied = rejected.encode()
    other = long_text("gamma").encode()
    assert has_verbatim_run(tokens(original.decode()), tokens(rejected)) is False
    assert containment_at_least(
        shingles(tokens(original.decode())), shingles(tokens(rejected))
    ) is False
    assert is_excerpt(original.decode(), rejected) is True
    stage(root, REPO, PIN, "Birds.dsp", original)
    stage(root, REPO, PIN, "birds.dsp", copied)
    stage(root, REPO, PIN, "other.dsp", other)
    birds, birds_notice = cleared("birds", original, path="Birds.dsp")
    refused = entry(
        "syfala-examples",
        copied,
        path="birds.dsp",
        decision="rights_rejected",
        license_name="unlicensed",
        eligible_for=[],
        reason="Syfala has no repository license",
        reviewer="",
    )
    kept, kept_notice = cleared("other", other, path="other.dsp")
    import faustcoder.upstream as upstream

    monkeypatch.setattr(
        upstream,
        "UPSTREAM_ORIGINALS",
        (
            UpstreamOriginal(
                blob_sha=git_blob_sha1(original),
                repo=REPO,
                path="Birds.dsp",
                copy_repo=REPO,
                copy_path="birds.dsp",
                copied_on="2024-02-13",
                evidence="c" * 40,
            ),
        ),
    )
    compiled = _compile(root, [birds, refused, kept], [birds_notice, kept_notice])
    payload = _manifest(compiled)
    rows = _by_entry(payload["units"])  # type: ignore[arg-type]
    assert rows["birds"]["eligible_for"] == ["train", "eval", "redistribute"]
    assert rows["other"]["eligible_for"] == ["train", "eval", "redistribute"]
    excluded = _by_entry(payload["excluded"])  # type: ignore[arg-type]
    assert "birds" not in excluded
    assert excluded["syfala-examples"]["origin"] == "inventory"


def test_allowlisted_original_near_another_repo_is_needs_human(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The allowlist skips a blob only beside that entry's recorded copy."""
    root = tmp_path / "fixtures"
    original = long_text("birds", count=80).encode()
    foreign = long_text("birds", count=80, replacement="foreign").encode()
    copied = long_text("birds", count=80, replacement="copied").encode()
    other = long_text("gamma").encode()
    assert is_near_duplicate(original.decode(), foreign.decode()) is True
    syfala = "inria-emeraude/syfala"
    stage(root, REPO, PIN, "Birds.dsp", original)
    stage(root, REPO, PIN, "stolen.dsp", foreign)
    stage(root, syfala, PIN, "examples/faust/birds.dsp", copied)
    stage(root, REPO, PIN, "other.dsp", other)
    birds, birds_notice = cleared("birds", original, path="Birds.dsp")
    foreign_row = entry(
        "other-rejected",
        foreign,
        path="stolen.dsp",
        decision="rights_rejected",
        license_name="GPL-2.0-or-later",
        eligible_for=[],
        reason="A different repo copied the original",
        reviewer="",
    )
    copy_row = entry(
        "syfala-examples",
        copied,
        path="examples/faust/birds.dsp",
        decision="rights_rejected",
        license_name="unlicensed",
        eligible_for=[],
        reason="Syfala has no repository license",
        reviewer="",
        repo=syfala,
    )
    kept, kept_notice = cleared("other", other, path="other.dsp")
    import faustcoder.upstream as upstream

    monkeypatch.setattr(
        upstream,
        "UPSTREAM_ORIGINALS",
        (
            UpstreamOriginal(
                blob_sha=git_blob_sha1(original),
                repo=REPO,
                path="Birds.dsp",
                copy_repo=syfala,
                copy_path="examples/faust/birds.dsp",
                copied_on="2024-02-13",
                evidence="c" * 40,
            ),
        ),
    )
    compiled = _compile(
        root,
        [birds, foreign_row, copy_row, kept],
        [birds_notice, kept_notice],
    )
    payload = _manifest(compiled)
    assert [row["entry_id"] for row in payload["units"]] == ["other"]  # type: ignore[index]
    excluded = _by_entry(payload["excluded"])  # type: ignore[arg-type]
    assert excluded["birds"]["reason"] == "needs-human"
    assert excluded["birds"]["origin"] == "dedup"
    assert excluded["other-rejected"]["origin"] == "inventory"
    assert excluded["syfala-examples"]["origin"] == "inventory"


def test_upstream_allowlist_matches_cleared_inventory_rows() -> None:
    inventory = json.loads(Path("corpus/rights-inventory.v1.json").read_text(encoding="utf-8"))
    notice = json.loads(Path("corpus/notice-manifest.v1.json").read_text(encoding="utf-8"))
    corpus = parse_corpus(inventory, notice)
    by_blob = {unit.blob_sha: unit for unit in corpus.units}
    assert len(UPSTREAM_ORIGINALS) == 4
    for item in UPSTREAM_ORIGINALS:
        unit = by_blob[item.blob_sha]
        assert unit.repo == item.repo
        assert unit.path == item.path
        assert unit.decision == "rights_cleared"
        assert item.copied_on == "2024-02-13"
        assert item.copy_repo == "inria-emeraude/syfala"


def test_instr_reverb_excerpt_is_needs_human(tmp_path: Path) -> None:
    """Playground InstrReverb.dsp is an excerpt of rejected instrReverb."""
    library = library_root() / "instruments.lib"
    if not library.is_file():
        pytest.fail("pinned instruments.lib is missing; run scripts/fetch-faustlibraries.sh")
    lib = library.read_bytes()
    dsp = Path("tests/fixtures/t06/InstrReverb.dsp").read_bytes()
    lib_blob = "1863cc3c6085f78c9f37ff79d98451f449ab8138"
    dsp_blob = "e38da4010e6abb85eadd02cecb60337798993194"
    assert git_blob_sha1(lib) == lib_blob
    assert git_blob_sha1(dsp) == dsp_blob
    assert is_near_duplicate(dsp.decode(), lib.decode()) is False
    assert is_excerpt(dsp.decode(), lib.decode()) is True
    inventory = json.loads(Path("corpus/rights-inventory.v1.json").read_text(encoding="utf-8"))
    notice = json.loads(Path("corpus/notice-manifest.v1.json").read_text(encoding="utf-8"))
    corpus = parse_corpus(inventory, notice)
    rejected = [
        unit
        for unit in corpus.comparisons
        if unit.path == "instruments.lib" and unit.function == "instrReverb"
    ]
    cleared_rows = [unit for unit in corpus.units if unit.path.endswith("InstrReverb.dsp")]
    assert len(rejected) == 1 and rejected[0].blob_sha == lib_blob
    assert rejected[0].entry_id == "faustlibraries-undeclared"
    assert len(cleared_rows) == 1 and cleared_rows[0].blob_sha == dsp_blob
    assert cleared_rows[0].decision == "rights_cleared"
    root = tmp_path / "fixtures"
    lib_repo = "grame-cncm/faustlibraries"
    lib_pin = "2edec0537f536eaa130d42c354884d7db971663c"
    play_repo = "grame-cncm/faustplayground"
    play_pin = "abf9af4ce9f12fba64fdb2237343bd5d5c8a8047"
    stage(root, lib_repo, lib_pin, "instruments.lib", lib)
    stage(root, play_repo, play_pin, "public/faust-modules/effects/InstrReverb.dsp", dsp)
    other = long_text("gamma").encode()
    stage(root, REPO, PIN, "other.dsp", other)
    refused = entry(
        "faustlibraries-undeclared",
        lib,
        path="instruments.lib",
        function="instrReverb",
        decision="rights_rejected",
        license_name="unlicensed",
        eligible_for=[],
        reason="No declare and no section header",
        reviewer="",
        pin=lib_pin,
        repo=lib_repo,
    )
    play, play_notice = cleared(
        "faustplayground-headerless",
        dsp,
        path="public/faust-modules/effects/InstrReverb.dsp",
        license_name="LGPL-2.1-or-later",
        eligible_for=["train"],
        pin=play_pin,
        repo=play_repo,
    )
    kept, kept_notice = cleared("other", other, path="other.dsp")
    compiled = _compile(root, [refused, play, kept], [play_notice, kept_notice])
    payload = _manifest(compiled)
    assert [row["entry_id"] for row in payload["units"]] == ["other"]  # type: ignore[index]
    excluded = _by_entry(payload["excluded"])  # type: ignore[arg-type]
    assert excluded["faustplayground-headerless"]["reason"] == "needs-human"
    assert excluded["faustplayground-headerless"]["origin"] == "dedup"
    assert excluded["faustlibraries-undeclared"]["origin"] == "inventory"
    assert (
        excluded["faustlibraries-undeclared"]["duplicate_family"]
        == excluded["faustplayground-headerless"]["duplicate_family"]
    )
    store = ArtifactStore(tmp_path / "store")
    commit_snapshot(store, compiled)
    stored = b"".join(path.read_bytes() for path in store.root.rglob("*") if path.is_file())
    assert b"Reverberation Room Size" not in stored
    assert b"gamma0" in stored


def test_rejected_near_copy_launders_nothing(tmp_path: Path) -> None:
    """P3: a rejected GPL file and a one-token MIT copy keep neither eval nor the text."""
    _assert_uncleared_near_copy_is_not_admitted(tmp_path, decision="rights_rejected")


def test_needs_human_near_copy_launders_nothing(tmp_path: Path) -> None:
    """P4: the same attack with the GPL file at needs_human."""
    _assert_uncleared_near_copy_is_not_admitted(tmp_path, decision="needs_human")


def test_ffunction_token_scan_drops_the_unit(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    body = b"ffunction FOREIGN_BODY_ZZ = 1;\nprocess = FOREIGN_BODY_ZZ;\n"
    comment = b"// ffunction only in a comment\nprocess = 1;\n"
    stage(root, REPO, PIN, "foreign.dsp", body)
    stage(root, REPO, PIN, "comment.dsp", comment)
    foreign, foreign_notice = cleared("foreign", body, path="foreign.dsp")
    kept, kept_notice = cleared("comment", comment, path="comment.dsp")
    compiled = _compile(root, [foreign, kept], [foreign_notice, kept_notice])
    payload = _manifest(compiled)
    assert [row["entry_id"] for row in payload["units"]] == ["comment"]  # type: ignore[index]
    excluded = payload["excluded"][0]  # type: ignore[index]
    assert excluded["entry_id"] == "foreign"
    assert excluded["reason"] == "ffunction"
    assert excluded["origin"] == "scan"
    store = ArtifactStore(tmp_path / "store")
    commit_snapshot(store, compiled)
    blob = b"".join(path.read_bytes() for path in store.root.rglob("*") if path.is_file())
    assert b"FOREIGN_BODY_ZZ" not in blob


def test_uncleared_function_blocks_the_shared_blob(tmp_path: Path) -> None:
    data = b"gain = 1;\nagpl = 2;\n"
    fetched: list[str] = []

    class _Record:
        def fetch(self, repo: str, pin: str, path: str, blob_sha: str) -> bytes:
            fetched.append(path)
            return data

    cleared_row = entry(
        "mit-fn",
        data,
        path="vaeffects.lib",
        function="gain",
        license_name="MIT",
    )
    blocked = entry(
        "agpl-fn",
        data,
        path="vaeffects.lib",
        function="secret",
        decision="rights_rejected",
        license_name="AGPL-3.0-only",
        eligible_for=[],
        reason="AGPL function",
        reviewer="",
    )
    notice = notice_row(data, path="vaeffects.lib", function="gain")
    inventory = inventory_doc([cleared_row, blocked])
    notices = notice_doc([notice])
    with pins_for(inventory, notices):
        compiled = compile_snapshot(
            inventory,
            notices,
            _Record(),
            actor=ACTOR,
            created_at=CREATED_AT,
        )
    excluded = _by_entry(_manifest(compiled)["excluded"])  # type: ignore[arg-type]
    assert excluded["mit-fn"]["reason"] == "needs-human"
    assert excluded["mit-fn"]["function"] == "gain"
    assert excluded["agpl-fn"]["origin"] == "inventory"
    assert _manifest(compiled)["units"] == []
    assert fetched == ["vaeffects.lib"]
    store = ArtifactStore(tmp_path / "store")
    commit_snapshot(store, compiled)
    blob = b"".join(path.read_bytes() for path in store.root.rglob("*") if path.is_file())
    assert b"gain = 1" not in blob


def test_function_units_stay_separate(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    data = b"gain = 1;\nclip = 2;\n"
    stage(root, REPO, PIN, "vaeffects.lib", data)
    gain = entry("gain", data, path="vaeffects.lib", function="gain")
    clip = entry("clip", data, path="vaeffects.lib", function="clip")
    notices = [
        notice_row(data, path="vaeffects.lib", function="gain"),
        notice_row(data, path="vaeffects.lib", function="clip"),
    ]
    from tests.t06support import span_manifest

    spans, digest = span_manifest(
        inventory_doc([gain, clip]),
        notice_doc(notices),
        {"gain": (data, 0, 10), "clip": (data, 10, len(data))},
    )
    compiled = _compile(
        root, [gain, clip], notices, function_spans=spans, function_spans_digest=digest
    )
    payload = _manifest(compiled)
    assert compiled.unit_count == 2
    functions = sorted(row["function"] for row in payload["units"])  # type: ignore[index]
    assert functions == ["clip", "gain"]
    examples = {
        e["payload"]["function"]: e["payload"]["faust_source"]
        for e in compiled.envelopes
        if e["payload"].get("record_type") == "Example"
    }
    assert examples == {"gain": "gain = 1;\n", "clip": "clip = 2;\n"}
    assert "gain = 1" not in canonical_bytes(payload).decode()


def test_missing_notice_and_license_mismatch_are_refused(tmp_path: Path) -> None:
    class _Boom:
        def fetch(self, repo: str, pin: str, path: str, blob_sha: str) -> bytes:
            raise AssertionError("fetched a unit with no matching notice")

    data = b"process = 1;\n"
    row = entry("osc", data, path="osc.dsp")
    inventory = inventory_doc([row])
    empty = notice_doc([])
    with pins_for(inventory, empty):
        compiled = compile_snapshot(
            inventory,
            empty,
            _Boom(),
            actor=ACTOR,
            created_at=CREATED_AT,
        )
    assert _manifest(compiled)["excluded"][0]["reason"] == "notice-missing"  # type: ignore[index]

    mismatched = notice_row(data, path="osc.dsp", license_name="BSD")
    mismatched_doc = notice_doc([mismatched])
    with pins_for(inventory, mismatched_doc):
        compiled = compile_snapshot(
            inventory,
            mismatched_doc,
            _Boom(),
            actor=ACTOR,
            created_at=CREATED_AT,
        )
    assert _manifest(compiled)["excluded"][0]["reason"] == "notice-missing"  # type: ignore[index]
    assert _manifest(compiled)["units"] == []


def test_short_holdout_edit_is_a_family_leak(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    sealed_text = b"process = os.osc(440);\n"
    edited = b"process = os.osc(441);\n"
    other = b"process = no.noise;\n"
    assert is_near_duplicate(sealed_text.decode(), edited.decode()) is True
    assert is_near_duplicate(sealed_text.decode(), other.decode()) is False
    stage(root, REPO, PIN, "sealed.dsp", sealed_text)
    stage(root, REPO, PIN, "edited.dsp", edited)
    stage(root, REPO, PIN, "other.dsp", other)
    sealed_row, sealed_notice = cleared("sealed", sealed_text, path="sealed.dsp")
    edited_row, edited_notice = cleared("edited", edited, path="edited.dsp")
    other_row, other_notice = cleared("other", other, path="other.dsp")
    compiled = _compile(
        root,
        [sealed_row, edited_row, other_row],
        [sealed_notice, edited_notice, other_notice],
        sealed=[{"repo": REPO, "commit": PIN, "path": "sealed.dsp", "function": ""}],
    )
    payload = _manifest(compiled)
    assert [row["entry_id"] for row in payload["units"]] == ["other"]  # type: ignore[index]
    excluded = _by_entry(payload["excluded"])  # type: ignore[arg-type]
    assert excluded["edited"]["reason"] == "holdout-family"
    assert excluded["edited"]["origin"] == "dedup"
    assert "sealed" not in excluded
    assert payload["sealed"][0]["entry_id"] == "sealed"  # type: ignore[index]
    rendered = canonical_bytes(payload).decode()
    assert "os.osc" not in rendered


def test_normalize_failure_quarantines_one_unit_and_a_bad_blob_aborts(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    good = b"process = 1;\n"
    bad = b"\x00"
    stage(root, REPO, PIN, "good.dsp", good)
    stage(root, REPO, PIN, "bad.dsp", bad)
    good_row, good_notice = cleared("good", good, path="good.dsp")
    bad_row, bad_notice = cleared("bad", bad, path="bad.dsp")
    compiled = _compile(root, [good_row, bad_row], [good_notice, bad_notice])
    payload = _manifest(compiled)
    assert [row["entry_id"] for row in payload["units"]] == ["good"]  # type: ignore[index]
    assert payload["excluded"][0]["reason"] == "nul-byte"  # type: ignore[index]
    assert payload["excluded"][0]["origin"] == "normalize"  # type: ignore[index]

    stage(root, REPO, PIN, "mismatch.dsp", b"process = 3;\n")
    mismatch, mismatch_notice = cleared("mismatch", b"nope", path="mismatch.dsp")
    with pytest.raises(AcquireError, match="blob_sha"):
        _compile(root, [mismatch], [mismatch_notice])


def test_tampered_text_with_the_claimed_sha_is_refused_before_normalize(
    tmp_path: Path,
) -> None:
    """T05 binds blob_sha, not the text. A changed body with the same claim is refused."""
    from faustcoder.acquire import git_blob_sha1

    original = b"process = 1;\n"
    tampered = b"\x00tampered"
    claimed = git_blob_sha1(original)
    assert claimed != git_blob_sha1(tampered)
    row, notice = cleared("osc", original, path="osc.dsp")
    assert row["files"][0]["blob_sha"] == claimed  # type: ignore[index]

    class _Tamper:
        def fetch(self, repo: str, pin: str, path: str, blob_sha: str) -> bytes:
            assert blob_sha == claimed
            return tampered

    inventory = inventory_doc([row])
    notices = notice_doc([notice])
    with pins_for(inventory, notices):
        with pytest.raises(AcquireError, match="blob_sha"):
            compile_snapshot(
                inventory,
                notices,
                _Tamper(),
                actor=ACTOR,
                created_at=CREATED_AT,
            )


def test_duplicate_identity_and_file_count_are_refused() -> None:
    data = b"process = 1;\n"
    first = entry("one", data, path="osc.dsp")
    second = entry("two", data, path="osc.dsp")
    notice = notice_row(data, path="osc.dsp")
    with pytest.raises(InventoryError, match="already"):
        content = inventory_doc([first, second])
        from tests.t06support import parse_pinned

        parse_pinned(content, notice_doc([notice]))
    broken = entry("one", data, path="osc.dsp")
    broken["file_count"] = 2
    with pytest.raises(InventoryError, match="file_count"):
        from tests.t06support import parse_pinned

        parse_pinned(inventory_doc([broken]), notice_doc([notice]))


def test_production_corpus_is_pinned_and_foreign_units_are_refused() -> None:
    import json

    from faustcoder.inventory import (
        PINNED_INVENTORY_DIGEST,
        PINNED_NOTICE_DIGEST,
        parse_corpus,
    )

    inventory = json.loads(
        Path("corpus/rights-inventory.v1.json").read_text(encoding="utf-8")
    )
    notice = json.loads(
        Path("corpus/notice-manifest.v1.json").read_text(encoding="utf-8")
    )
    assert content_digest(inventory) == PINNED_INVENTORY_DIGEST
    assert content_digest(notice) == PINNED_NOTICE_DIGEST
    resigned = dict(inventory)
    resigned["generated_at"] = "2026-10-18T00:00:00Z"
    assert content_digest(resigned) == PINNED_INVENTORY_DIGEST
    corpus = parse_corpus(resigned, notice)
    assert corpus.inventory_digest == PINNED_INVENTORY_DIGEST
    assert corpus.notice_digest == PINNED_NOTICE_DIGEST
    cleared: set[tuple[str, str, str, str, str]] = set()
    for row in inventory["entries"]:
        if row["decision"] != "rights_cleared":
            continue
        repo = row["pin"]["repo"]
        commit = row["pin"]["commit"]
        specs = list(row.get("files") or []) + list(row.get("functions") or [])
        for spec in specs:
            cleared.add(
                (repo, commit, spec["path"], spec.get("function") or "", spec["blob_sha"])
            )
    admitted = {
        (unit.repo, unit.pin, unit.path, unit.function, unit.blob_sha)
        for unit in corpus.units
    }
    assert admitted
    assert admitted <= cleared
    assert ("other/repo", "c" * 40, "nope.dsp", "", "d" * 40) not in admitted
    for unit in corpus.units:
        assert unit.decision == "rights_cleared"
        if unit.impulse:
            assert "eval" not in unit.eligible_for
    extra = json.loads(json.dumps(inventory))
    extra["entries"].append({"id": "forged-entry"})
    with pytest.raises(InventoryError, match="digest"):
        parse_corpus(extra, notice)
    swapped = json.loads(json.dumps(inventory))
    specs = swapped["entries"][0].get("files") or swapped["entries"][0].get("functions")
    specs[0]["blob_sha"] = "d" * 40
    with pytest.raises(InventoryError, match="digest"):
        parse_corpus(swapped, notice)


def _assert_uncleared_near_copy_is_not_admitted(tmp_path: Path, *, decision: str) -> None:
    root = tmp_path / "fixtures"
    original = long_text("alpha").encode()
    edited = long_text("alpha", replacement="renamed").encode()
    other = long_text("gamma").encode()
    assert is_near_duplicate(original.decode(), edited.decode()) is True
    assert is_near_duplicate(original.decode(), other.decode()) is False
    stage(root, REPO, PIN, "gpl.dsp", original)
    stage(root, REPO, PIN, "mit.dsp", edited)
    stage(root, REPO, PIN, "other.dsp", other)
    refused = entry(
        "gpl",
        original,
        path="gpl.dsp",
        decision=decision,
        license_name="GPL-2.0-or-later",
        eligible_for=[],
        reason="GPL source is not cleared",
        reviewer="",
    )
    mit, mit_notice = cleared("mit", edited, path="mit.dsp", license_name="MIT")
    kept, kept_notice = cleared("other", other, path="other.dsp")
    fetched: list[str] = []

    class _Record:
        def fetch(self, repo: str, pin: str, path: str, blob_sha: str) -> bytes:
            fetched.append(path)
            target = root.joinpath(*repo.split("/"), pin, *path.split("/"))
            return target.read_bytes()

    inventory = inventory_doc([refused, mit, kept])
    notices = notice_doc([mit_notice, kept_notice])
    with pins_for(inventory, notices):
        compiled = compile_snapshot(
            inventory,
            notices,
            _Record(),
            actor=ACTOR,
            created_at=CREATED_AT,
        )
    payload = _manifest(compiled)
    assert [row["entry_id"] for row in payload["units"]] == ["other"]  # type: ignore[index]
    assert payload["units"][0]["eligible_for"] == ["train", "eval", "redistribute"]  # type: ignore[index]
    excluded = _by_entry(payload["excluded"])  # type: ignore[arg-type]
    assert excluded["mit"]["reason"] == "needs-human"
    assert excluded["mit"]["origin"] == "dedup"
    assert excluded["gpl"]["origin"] == "inventory"
    assert excluded["gpl"]["duplicate_family"] == excluded["mit"]["duplicate_family"]
    assert "gpl.dsp" in fetched
    store = ArtifactStore(tmp_path / "store")
    commit_snapshot(store, compiled)
    blob = b"".join(path.read_bytes() for path in store.root.rglob("*") if path.is_file())
    assert b"renamed" not in blob
    assert b"alpha0" not in blob
    assert b"gamma0" in blob


def _two(root: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    first = b"process = 1;\n"
    second = b"process = 2;\n"
    stage(root, REPO, PIN, "one.dsp", first)
    stage(root, REPO, PIN, "two.dsp", second)
    one, one_notice = cleared("one", first, path="one.dsp")
    two, two_notice = cleared("two", second, path="two.dsp")
    return [one, two], [one_notice, two_notice]

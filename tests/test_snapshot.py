"""Deterministic dedup manifest. Fixture fetcher only."""

from __future__ import annotations

from pathlib import Path

import pytest

from faustcoder.canonical import canonical_bytes
from faustcoder.errors import AcquireError, InventoryError, MutationError
from faustcoder.inventory import parse_inventory
from faustcoder.neardup import is_near_duplicate
from faustcoder.normalize import normalize_bytes
from faustcoder.snapshot import commit_snapshot, compile_snapshot
from faustcoder.store import ArtifactStore

from tests.t06support import (
    ACTOR,
    CREATED_AT,
    PIN,
    PIN_B,
    REPO,
    inventory,
    long_text,
    stage,
    stage_notice,
    unit,
)


def _compile(root: Path, document: dict[str, object], created_at: str = CREATED_AT):
    return compile_snapshot(
        document,
        _directory(root),
        actor=ACTOR,
        created_at=created_at,
    )


def _directory(root: Path):
    from faustcoder.acquire import DirectoryFetcher

    return DirectoryFetcher(root)


def _manifest(compiled) -> dict[str, object]:
    return compiled.envelopes[-1]["payload"]


def test_same_clock_is_byte_identical_and_shuffle_does_not_matter(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    document = _two_units(root)
    shuffled = inventory(list(reversed(document["units"])), document["generated_at"])  # type: ignore[arg-type]
    first = _compile(root, document)
    second = _compile(root, shuffled)
    assert first.manifest_digest == second.manifest_digest
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
    document = _two_units(root)
    first = _compile(root, document, CREATED_AT)
    second = _compile(root, document, "2026-10-17T20:00:01Z")
    assert first.manifest_digest == second.manifest_digest
    assert canonical_bytes(first.envelopes[-1]) != canonical_bytes(second.envelopes[-1])
    store = ArtifactStore(tmp_path / "store")
    digest = commit_snapshot(store, first)
    before = store.path_for(digest).read_bytes()
    with pytest.raises(MutationError):
        commit_snapshot(store, second)
    assert store.path_for(digest).read_bytes() == before


def test_generated_at_changes_the_manifest_digest(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    document = _two_units(root)
    later = inventory(document["units"], "2026-10-17T13:05:00Z")  # type: ignore[arg-type]
    assert _compile(root, document).manifest_digest != _compile(root, later).manifest_digest


def test_training_only_impulse_is_carried(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    data = b"process = 1;\n"
    stage_notice(root)
    stage(root, REPO, PIN, "impulse.dsp", data)
    compiled = _compile(
        root,
        inventory(
            [
                unit(
                    "impulse",
                    data,
                    path="impulse.dsp",
                    decision="training_only",
                    eligible_for=["train"],
                    training_only=True,
                    impulse=True,
                )
            ]
        ),
    )
    row = _manifest(compiled)["units"][0]  # type: ignore[index]
    assert row["training_only"] is True
    assert row["impulse"] is True
    assert row["eligible_for"] == ["train"]


def test_manifest_has_no_program_text(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    sentinel = "UNIQUE_SENTINEL_OSC"
    data = f"process = {sentinel};\n".encode()
    stage_notice(root)
    stage(root, REPO, PIN, "osc.dsp", data)
    compiled = _compile(root, inventory([unit("osc", data, path="osc.dsp")]))
    payload = _manifest(compiled)
    assert payload["record_type"] == "DedupManifest"
    assert payload["lifecycle"] == "DEDUPED"
    assert payload["split_frozen"] is False
    assert "faust_source" not in canonical_bytes(payload).decode()
    assert sentinel not in canonical_bytes(payload).decode()
    store = ArtifactStore(tmp_path / "store")
    commit_snapshot(store, compiled)
    examples = [
        store.get(artifact_id)["payload"]["faust_source"]
        for artifact_id in store.list()
        if store.get(artifact_id)["payload"].get("record_type") == "Example"
    ]
    assert sentinel in examples[0]


def test_exact_cluster_narrows_to_the_strictest_flags_and_near_dup_does_not(
    tmp_path: Path,
) -> None:
    root = tmp_path / "fixtures"
    same = b"process = 1;\n"
    stage_notice(root)
    stage(root, REPO, PIN, "mit.dsp", same)
    stage(root, REPO, PIN, "bsd.dsp", same)
    exact = _compile(
        root,
        inventory(
            [
                unit("mit", same, path="mit.dsp"),
                unit(
                    "bsd",
                    same,
                    path="bsd.dsp",
                    license_name="BSD",
                    eligible_for=["train", "eval"],
                ),
            ]
        ),
    )
    rows = {row["unit_id"]: row for row in _manifest(exact)["units"]}  # type: ignore[index]
    assert rows["mit"]["eligible_for"] == ["train", "eval"]
    assert rows["mit"]["rights_narrowed"] is True
    assert rows["bsd"]["rights_narrowed"] is False
    assert rows["mit"]["duplicate_family"] == rows["bsd"]["duplicate_family"]

    left = long_text("alpha").encode()
    right = long_text("alpha", replacement="renamed").encode()
    assert is_near_duplicate(left.decode(), right.decode()) is True
    stage(root, REPO, PIN, "near-mit.dsp", left)
    stage(root, REPO, PIN, "near-bsd.dsp", right)
    near = _compile(
        root,
        inventory(
            [
                unit("nmit", left, path="near-mit.dsp"),
                unit(
                    "nbsd",
                    right,
                    path="near-bsd.dsp",
                    license_name="BSD",
                    eligible_for=["train", "eval"],
                ),
            ]
        ),
    )
    rows = {row["unit_id"]: row for row in _manifest(near)["units"]}  # type: ignore[index]
    assert rows["nmit"]["duplicate_family"] == rows["nbsd"]["duplicate_family"]
    assert rows["nmit"]["rights_narrowed"] is False
    assert rows["nmit"]["eligible_for"] == ["train", "eval", "redistribute"]
    assert rows["nbsd"]["eligible_for"] == ["train", "eval"]


def test_vendored_match_collapses_and_a_stale_copy_is_excluded(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    data = b"process = 1;\n"
    stale = b"process = 9;\n"
    stage_notice(root)
    stage(root, REPO, PIN, "up.dsp", data)
    stage(root, "acme/vendor", PIN_B, "copy.dsp", data)
    stage(root, "acme/vendor", PIN_B, "stale.dsp", stale)
    compiled = _compile(
        root,
        inventory(
            [
                unit("up", data, path="up.dsp"),
                unit(
                    "copy",
                    data,
                    path="copy.dsp",
                    decision="vendored",
                    eligible_for=[],
                    upstream_unit_id="up",
                    repo="acme/vendor",
                    pin=PIN_B,
                ),
                unit(
                    "stale",
                    stale,
                    path="stale.dsp",
                    decision="vendored",
                    eligible_for=[],
                    upstream_unit_id="up",
                    repo="acme/vendor",
                    pin=PIN_B,
                ),
            ]
        ),
    )
    payload = _manifest(compiled)
    units = payload["units"]
    assert [row["unit_id"] for row in units] == ["up"]  # type: ignore[index]
    copies = units[0]["vendored_copies"]  # type: ignore[index]
    assert copies[0]["unit_id"] == "copy"
    excluded = {row["unit_id"]: row for row in payload["excluded"]}  # type: ignore[index]
    assert excluded["stale"]["reason"] == "vendored-stale"
    assert excluded["stale"]["origin"] == "vendored"
    assert "process = 1" not in canonical_bytes(payload).decode()


def test_holdout_family_quarantines_the_acquired_copy(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    data = b"process = HOLDOUT_SENTINEL;\n"
    stage_notice(root)
    stage(root, REPO, PIN, "train.dsp", data)
    stage(root, REPO, PIN, "sealed.dsp", data)
    compiled = _compile(
        root,
        inventory(
            [
                unit("train", data, path="train.dsp"),
                unit("sealed", data, path="sealed.dsp", holdout=True),
            ]
        ),
    )
    payload = _manifest(compiled)
    assert payload["units"] == []
    assert payload["example_digests"] == []
    assert payload["excluded"][0]["reason"] == "holdout-family"  # type: ignore[index]
    assert payload["excluded"][0]["origin"] == "dedup"  # type: ignore[index]
    assert payload["sealed"][0]["unit_id"] == "sealed"  # type: ignore[index]
    assert "HOLDOUT_SENTINEL" not in canonical_bytes(payload).decode()
    store = ArtifactStore(tmp_path / "store")
    commit_snapshot(store, compiled)
    texts = [
        store.get(artifact_id)["payload"].get("faust_source", "")
        for artifact_id in store.list()
    ]
    assert sum("HOLDOUT_SENTINEL" in text for text in texts) == 1


def test_multi_file_source_is_one_unit(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    primary = b'import("helper.lib");\nprocess = 1;\n'
    helper = b"gain = 1;\n"
    stage_notice(root)
    primary_sha = stage(root, REPO, PIN, "dsp/main.dsp", primary)
    helper_sha = stage(root, REPO, PIN, "dsp/helper.lib", helper)
    compiled = _compile(
        root,
        inventory(
            [
                unit(
                    "group",
                    primary,
                    files=[
                        {"path": "dsp/helper.lib", "blob_sha": helper_sha, "role": "import"},
                        {"path": "dsp/main.dsp", "blob_sha": primary_sha, "role": "primary"},
                    ],
                )
            ]
        ),
    )
    payload = _manifest(compiled)
    assert compiled.unit_count == 1
    row = payload["units"][0]  # type: ignore[index]
    assert [item["role"] for item in row["files"]] == ["primary", "import"]
    assert row["normalized_sha256"] != normalize_bytes(primary).normalized_sha256
    assert "gain = 1" not in canonical_bytes(payload).decode()


def test_sibling_and_unreferenced_imports_are_refused(tmp_path: Path) -> None:
    primary_sha = "c" * 40
    helper_sha = "d" * 40
    with pytest.raises(InventoryError, match="siblings"):
        parse_inventory(
            inventory(
                [
                    unit(
                        "group",
                        b"",
                        files=[
                            {"path": "dsp/main.dsp", "blob_sha": primary_sha, "role": "primary"},
                            {"path": "lib/helper.lib", "blob_sha": helper_sha, "role": "import"},
                        ],
                    )
                ]
            )
        )
    root = tmp_path / "fixtures"
    primary = b"process = 1;\n"
    helper = b"gain = 1;\n"
    stage_notice(root)
    primary_sha = stage(root, REPO, PIN, "dsp/main.dsp", primary)
    helper_sha = stage(root, REPO, PIN, "dsp/helper.lib", helper)
    with pytest.raises(InventoryError, match="not named"):
        _compile(
            root,
            inventory(
                [
                    unit(
                        "group",
                        primary,
                        files=[
                            {"path": "dsp/main.dsp", "blob_sha": primary_sha, "role": "primary"},
                            {"path": "dsp/helper.lib", "blob_sha": helper_sha, "role": "import"},
                        ],
                    )
                ]
            ),
        )


def test_ffunction_reject_is_not_fetched_and_the_scan_drops_the_unit(tmp_path: Path) -> None:
    class _Boom:
        def fetch(self, repo: str, pin: str, path: str, blob_sha: str) -> bytes:
            raise AssertionError("fetched a rejected unit")

    rejected = unit(
        "stk",
        b"",
        decision="reject",
        eligible_for=[],
        license_name="unknown",
        reason="ffunction",
    )
    compiled = compile_snapshot(
        inventory([rejected]),
        _Boom(),
        actor=ACTOR,
        created_at=CREATED_AT,
    )
    row = _manifest(compiled)["excluded"][0]  # type: ignore[index]
    assert row["reason"] == "ffunction"
    assert row["origin"] == "inventory"

    root = tmp_path / "fixtures"
    body = b"ffunction FOREIGN_BODY_ZZ = 1;\nprocess = FOREIGN_BODY_ZZ;\n"
    comment = b"// ffunction only in a comment\nprocess = 1;\n"
    stage_notice(root)
    stage(root, REPO, PIN, "foreign.dsp", body)
    stage(root, REPO, PIN, "comment.dsp", comment)
    scanned = _compile(
        root,
        inventory(
            [
                unit("foreign", body, path="foreign.dsp"),
                unit("comment", comment, path="comment.dsp"),
            ]
        ),
    )
    payload = _manifest(scanned)
    assert [row["unit_id"] for row in payload["units"]] == ["comment"]  # type: ignore[index]
    excluded = payload["excluded"][0]  # type: ignore[index]
    assert excluded["unit_id"] == "foreign"
    assert excluded["reason"] == "ffunction"
    assert excluded["origin"] == "scan"
    store = ArtifactStore(tmp_path / "store")
    commit_snapshot(store, scanned)
    blob = b"".join(path.read_bytes() for path in store.root.rglob("*") if path.is_file())
    assert b"FOREIGN_BODY_ZZ" not in blob


def test_normalize_failure_quarantines_one_unit_and_a_bad_blob_aborts(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    good = b"process = 1;\n"
    bad = b"\x00"
    stage_notice(root)
    stage(root, REPO, PIN, "good.dsp", good)
    stage(root, REPO, PIN, "bad.dsp", bad)
    compiled = _compile(
        root,
        inventory(
            [
                unit("good", good, path="good.dsp"),
                unit("bad", bad, path="bad.dsp"),
            ]
        ),
    )
    payload = _manifest(compiled)
    assert [row["unit_id"] for row in payload["units"]] == ["good"]  # type: ignore[index]
    assert payload["excluded"][0]["reason"] == "nul-byte"  # type: ignore[index]
    assert payload["excluded"][0]["origin"] == "normalize"  # type: ignore[index]

    stage(root, REPO, PIN, "mismatch.dsp", b"process = 3;\n")
    with pytest.raises(AcquireError, match="blob_sha"):
        _compile(root, inventory([unit("mismatch", b"nope", path="mismatch.dsp")]))


def _two_units(root: Path) -> dict[str, object]:
    first = b"process = 1;\n"
    second = b"process = 2;\n"
    stage_notice(root)
    stage(root, REPO, PIN, "one.dsp", first)
    stage(root, REPO, PIN, "two.dsp", second)
    return inventory(
        [
            unit("one", first, path="one.dsp"),
            unit("two", second, path="two.dsp"),
        ]
    )

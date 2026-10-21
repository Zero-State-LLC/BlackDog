"""Shipping-path leakage and independent signing rejection regressions."""

import copy
import subprocess
from pathlib import Path
import pytest
from faustcoder.canonical import canonical_bytes, content_digest_for
from faustcoder.neardup import (
    canonical_tokens,
    tokens,
    cluster_families,
    memorization_hits,
    COMPARISON_VERSION,
    TOKEN_FLOOR,
    TOKEN_FLOOR_STATUS,
)
from faustcoder.split import (
    audit_assignments,
    split_candidate,
    verify_signed_candidate,
    require_freeze_ready,
    NAMESPACE,
)
from faustcoder.floor_readiness import assess_plants
from tests.test_snapshot import _compile, _manifest
from tests.t06support import entry, notice_row, stage, REPO, PIN


def program(prefix="a"):
    return "\n".join(f"{prefix}{i}(x) = x * {i + 1} + {i + 2};" for i in range(15))


def test_h2_and_h3_reach_shipping_snapshot(tmp_path):
    original = program()
    renamed = program("renamed")
    for i, changed in enumerate(
        (renamed, original.replace("a", "a\u200b"), original.replace("a", "\uff41"))
    ):
        root = tmp_path / str(i)
        a = changed.encode()
        b = original.encode()
        rows = [
            entry("clear", a),
            entry("reject", b, decision="rights_rejected", eligible_for=[]),
        ]
        for row, data in zip(rows, (a, b)):
            stage(root, REPO, PIN, row["files"][0]["path"], data)
        result = _manifest(_compile(root, rows, [notice_row(a, path="clear.dsp")]))
        assert result["units"] == []
        assert any(r["reason"] == "needs-human" for r in result["excluded"])
        assert result["near_duplicate"]["algorithm"] == COMPARISON_VERSION
        assert result["split_frozen"] is False


def test_canonical_strings_members_and_unicode_boundaries():
    assert canonical_tokens(
        'foo(x)=os.osc(1e-3)+hslider("a\\"b",0,0,1,.1);'
    ) == canonical_tokens('bar(y)=os.osc(2e+3)+hslider("c",1,1,2,.2);')
    assert canonical_tokens("x=aa.one(1);") != canonical_tokens("x=aa.two(1);")
    assert tokens("alpha // ignored\nbeta") == ("alpha", "beta")
    assert tokens("al\u200bpha") == ("alpha",)


def test_or_stream_no_floor_mutation_and_deterministic_replay():
    items = [
        ("a", program()),
        ("b", program("rename")),
        ("c", "process = os.osc(440);"),
    ]
    for floor in (40, 30, 20):
        families = cluster_families(items, ["a"], floor=floor)
        assert families["a"] == families["b"]
        assert families == cluster_families(list(reversed(items)), ["a"], floor=floor)
        assert memorization_hits(program("rename"), [("a", program())], floor=floor)
    assert (TOKEN_FLOOR, TOKEN_FLOOR_STATUS) == (40, "provisional")
    with pytest.raises(ValueError):
        cluster_families(items, floor=True)


def test_h1_split_file_union_reaches_comparison_family():
    # Every fragment is < floor and individually below 1/2; union exceeds 1/2.
    rejected = " ".join(f"lib.fn{i}" for i in range(80))
    fragments = [
        " ".join(f"lib.fn{i}" for i in range(start, start + 25))
        for start in (0, 25, 50)
    ]
    items = [("r", rejected)] + [(str(i), text) for i, text in enumerate(fragments)]
    families = cluster_families(items, ["r"])
    assert len(set(families.values())) == 1


def rows():
    return [
        dict(
            unit_id=str(i),
            repo=f"project{i}",
            duplicate_family=f"family{i}",
            original_sha256="sha256:" + str(i) * 64,
            eligible_for=["train", "eval"],
            impulse=False,
            training_only=False,
        )
        for i in range(3)
    ]


def test_assignment_rejections_and_dependency_transitivity():
    r = rows()
    a = {"0": "train", "1": "development", "2": "holdout"}
    deps = {str(i): [] for i in range(3)}
    assert audit_assignments(r, a, deps) == []
    for field in ("repo", "duplicate_family", "original_sha256"):
        bad = copy.deepcopy(r)
        bad[1][field] = bad[0][field]
        assert any("cross-split " + field in x for x in audit_assignments(bad, a, deps))
    bad = copy.deepcopy(r)
    bad[1]["eligible_for"] = ["train"]
    assert any("forbidden rights" in x for x in audit_assignments(bad, a, deps))
    assert audit_assignments(r, a, {"0": ["1"], "1": ["2"], "2": []})
    assert audit_assignments(r, a, {"0": ["missing"], "1": [], "2": []})
    with pytest.raises(ValueError):
        audit_assignments(r + r[:1], a, deps)


def candidate():
    dedup = {
        "record_type": "DedupManifest",
        "split_frozen": False,
        "units": rows(),
        "near_duplicate": {
            "algorithm": COMPARISON_VERSION,
            "token_floor": 40,
            "measurement_only": False,
        },
    }
    c = split_candidate(
        dedup,
        {"0": "train", "1": "development", "2": "holdout"},
        {str(i): [] for i in range(3)},
        blockers=["independent custody pending"],
    )
    return c, dedup


def test_signed_candidate_integrity_wrong_key_and_no_freeze(tmp_path):
    c, d = candidate()
    key = tmp_path / "disposable-fixture-key"
    msg = tmp_path / "candidate.json"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
        capture_output=True,
    )
    pub = " ".join(key.with_suffix(".pub").read_text().split()[:2])
    msg.write_bytes(canonical_bytes(c))
    subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", NAMESPACE, str(msg)],
        check=True,
        capture_output=True,
    )
    sig = Path(str(msg) + ".sig").read_bytes()
    assert verify_signed_candidate(c, sig, pub, dedup=d) == content_digest_for(c)
    bad = copy.deepcopy(c)
    bad["assignments"]["1"] = "train"
    with pytest.raises(ValueError):
        verify_signed_candidate(bad, sig, pub, dedup=d)
    bad = copy.deepcopy(d)
    bad["units"][0]["repo"] = "changed"
    with pytest.raises(ValueError):
        verify_signed_candidate(c, sig, pub, dedup=bad)
    with pytest.raises(ValueError):
        verify_signed_candidate(c, sig[:-8] + b"bad", pub, dedup=d)
    other = tmp_path / "other"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(other)],
        check=True,
        capture_output=True,
    )
    wrong = " ".join(other.with_suffix(".pub").read_text().split()[:2])
    with pytest.raises(ValueError):
        verify_signed_candidate(c, sig, wrong, dedup=d)
    with pytest.raises(ValueError, match="unfrozen"):
        require_freeze_ready(c)
    assert c["split_frozen"] is False


def plants():
    return [
        dict(
            id=f"{bucket}-{op}-{window}-{host}",
            tokens=size,
            operator=op,
            window_digest=f"window{bucket}-{window}",
            reject_digest="reject",
            host_digest=f"host{host}",
            host_repo=f"repo{host}",
        )
        for bucket, size in enumerate((17, 25, 35, 45))
        for op in ("verbatim_raw", "rename_canonical")
        for window in range(50)
        for host in range(2)
    ]


def test_floor_fixed_denominators_and_fail_closed():
    p = plants()
    outcomes = {str(f): {x["id"]: True for x in p} for f in (40, 30, 20)}
    result = assess_plants(p, outcomes)
    assert all(f["recall_pass"] for f in result["floors"].values())
    assert result["floor_accepted"] is False
    for x in p[:5]:
        outcomes["40"][x["id"]] = False
    result = assess_plants(p, outcomes)
    assert not result["floors"]["40"]["recall_pass"]
    assert result["floors"]["40"]["cells"][0]["n"] == 100
    assert result["floors"]["30"]["recall_pass"]
    with pytest.raises(ValueError):
        assess_plants(p, {"40": outcomes["40"]})
    for x in p:
        x["host_repo"] = "one-repo"
    assert not assess_plants(p, outcomes)["floors"]["20"]["recall_pass"]


@pytest.fixture
def signed_fixture(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setattr(
        "faustcoder.split._utc_now", lambda: datetime(2026, 10, 21, tzinfo=timezone.utc)
    )
    roots = tmp_path / "sources"
    entries = []
    notices = []
    for i in range(3):
        repo = f"acme/project{i}"
        data = (" ".join(f"lib{i}.member{j}" for j in range(80))).encode()
        entries.append(entry(str(i), data, repo=repo))
        notices.append(notice_row(data, path=f"{i}.dsp", repo=repo))
        stage(roots, repo, PIN, f"{i}.dsp", data)
    compiled = _compile(roots, entries, notices)
    d = _manifest(compiled)
    assert len(d["units"]) == 3
    mapping = {
        row["unit_id"]: split
        for row, split in zip(d["units"], ("train", "development", "holdout"))
    }
    ready = {
        k: "sha256:" + "a" * 64
        for k in (
            "source_closure_review_digest",
            "development_review_digest",
            "holdout_review_digest",
            "leakage_review_digest",
            "holdout_content_digest",
        )
    }
    ready.update(
        reviewer="fixture reviewer",
        custodian="fixture custodian",
        holdout_author="fixture author",
        newly_authored_holdout=True,
        floor_route="explicit-provisional",
        leakage_caveat="Fixture only; floor remains provisional",
        recheck_due="2027-01-01T00:00:00Z",
    )
    c = split_candidate(
        d, mapping, {k: [] for k in mapping}, blockers=[], readiness=ready
    )
    assert c["blockers"] == []
    key = tmp_path / "fixture-only-key"
    message = tmp_path / "fixture-message"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
        capture_output=True,
    )
    public = " ".join(key.with_suffix(".pub").read_text().split()[:2])
    message.write_bytes(canonical_bytes(c))
    subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", NAMESPACE, str(message)],
        check=True,
        capture_output=True,
    )
    signature = Path(str(message) + ".sig").read_bytes()
    return compiled, c, signature, public


def test_signed_freeze_runs_only_in_disposable_fixture_store(tmp_path, signed_fixture):
    from faustcoder.split import freeze_signed_split, verify_frozen_snapshot
    from faustcoder.snapshot import commit_snapshot
    from faustcoder.store import ArtifactStore
    from faustcoder.dataset import current_state

    compiled, c, signature, public = signed_fixture
    results = []
    for index in range(2):
        store = ArtifactStore(tmp_path / f"store{index}")
        digest = commit_snapshot(store, compiled)
        result = freeze_signed_split(
            store, digest, c, signature, public, created_at="2026-10-21T00:00:00Z"
        )
        results.append(result)
        assert (
            verify_frozen_snapshot(store, result, public)["p3_holdout_exit_allowed"]
            is False
        )
        # A valid custodian signature must not authorize altered snapshot flags
        # even when the altered artifact itself hashes correctly.
        from faustcoder.canonical import build_envelope

        original_snapshot = store.get(result)
        for payload, parents in (
            (
                dict(original_snapshot["payload"], p3_holdout_exit_allowed=True),
                original_snapshot["parents"],
            ),
            (
                dict(original_snapshot["payload"], split_frozen=False),
                original_snapshot["parents"],
            ),
        ):
            altered = build_envelope(
                schema_version="0.3.0",
                created_at="2026-10-21T00:00:00Z",
                producer="faustcoder.split",
                parents=parents,
                payload=payload,
            )
            altered_digest = store.put(altered)
            with pytest.raises(ValueError, match="snapshot binding mismatch"):
                verify_frozen_snapshot(store, altered_digest, public)
        for e in compiled.envelopes:
            if e["payload"].get("record_type") == "SourceRecord":
                assert current_state(store, e["content_digest"]) == "FROZEN"
        before = store.list()
        assert (
            freeze_signed_split(
                store, digest, c, signature, public, created_at="2026-10-21T00:00:00Z"
            )
            == result
        )
        assert store.list() == before
        with pytest.raises(ValueError, match="does not match"):
            freeze_signed_split(
                store, digest, c, signature, public, created_at="2026-10-22T00:00:00Z"
            )
        assert store.list() == before
    assert results[0] == results[1]


def test_h2_h3_on_verified_function_slicer_path(tmp_path):
    from tests.t06support import span_manifest, inventory_doc, notice_doc

    original = "kernel(x) = " + " + ".join(f"x * {i}" for i in range(1, 20)) + ";\n"
    renamed = original.replace("kernel", "renamed").replace("x", "y\u200b")
    body = renamed.encode()
    prefix = b"// outside selected function\n"
    raw = prefix + body
    entries = [
        entry("function", raw, function="renamed"),
        entry("reject", original.encode(), decision="rights_rejected", eligible_for=[]),
    ]
    notices = [notice_row(raw, path="function.dsp", function="renamed")]
    manifest, digest = span_manifest(
        inventory_doc(entries),
        notice_doc(notices),
        {"renamed": (raw, len(prefix), len(raw))},
    )
    stage(tmp_path, REPO, PIN, "function.dsp", raw)
    stage(tmp_path, REPO, PIN, "reject.dsp", original.encode())
    result = _manifest(
        _compile(
            tmp_path,
            entries,
            notices,
            function_spans=manifest,
            function_spans_digest=digest,
        )
    )
    assert result["units"] == []
    assert any(r["reason"] == "needs-human" for r in result["excluded"])


def test_split_rejects_stale_or_measurement_only_pipeline():
    c, d = candidate()
    for field, value in [
        ("algorithm", "old"),
        ("measurement_only", True),
        ("token_floor", 20),
    ]:
        bad = copy.deepcopy(d)
        bad["near_duplicate"][field] = value
        with pytest.raises(ValueError):
            split_candidate(bad, c["assignments"], c["dependencies"], blockers=[])


def test_canonical_qualified_names_are_one_token_at_floor_boundary():
    # A qualified member counts as one canonical token, not lib/dot/member.
    a = " ".join(f"aa.f{i}" for i in range(14))
    b = (
        " ".join(f"aa.f{i}" for i in range(14))
        + " "
        + " ".join(f"bb.f{i}" for i in range(20))
    )
    assert len(canonical_tokens(a)) == 14
    assert len(canonical_tokens(b)) == 34
    # Raw matching may still find an excerpt; canonical arithmetic is tested
    # separately so that raw behavior is never suppressed by canonical misses.
    from faustcoder.neardup import _raw_cluster_families

    f = _raw_cluster_families([("a", a), ("b", b)], ["a"], floor=40, canonical=True)
    assert f["a"] != f["b"]


def test_signed_freeze_rejects_backdating_and_expired_reads(
    tmp_path, monkeypatch, signed_fixture
):
    from datetime import datetime, timezone
    from faustcoder.split import freeze_signed_split, verify_frozen_snapshot
    from faustcoder.snapshot import commit_snapshot
    from faustcoder.store import ArtifactStore

    compiled, c, sig, pub = signed_fixture
    store = ArtifactStore(tmp_path / "expired")
    digest = commit_snapshot(store, compiled)
    before = store.list()
    monkeypatch.setattr(
        "faustcoder.split._utc_now", lambda: datetime(2027, 1, 1, tzinfo=timezone.utc)
    )
    with pytest.raises(ValueError, match="overdue"):
        freeze_signed_split(
            store, digest, c, sig, pub, created_at="2026-10-21T00:00:00Z"
        )
    assert store.list() == before
    monkeypatch.setattr(
        "faustcoder.split._utc_now", lambda: datetime(2026, 10, 21, tzinfo=timezone.utc)
    )
    snapshot = freeze_signed_split(
        store, digest, c, sig, pub, created_at="2026-10-21T00:00:00Z"
    )
    monkeypatch.setattr(
        "faustcoder.split._utc_now", lambda: datetime(2027, 1, 1, tzinfo=timezone.utc)
    )
    with pytest.raises(ValueError, match="overdue"):
        verify_frozen_snapshot(store, snapshot, pub)


@pytest.mark.parametrize("written_receipts", [0, 1, 2])
def test_snapshot_rejects_interrupted_freeze(
    tmp_path, monkeypatch, signed_fixture, written_receipts
):
    from faustcoder.split import freeze_signed_split, verify_frozen_snapshot
    from faustcoder.snapshot import commit_snapshot
    from faustcoder.store import ArtifactStore

    compiled, c, sig, pub = signed_fixture
    store = ArtifactStore(tmp_path / "interrupted")
    digest = commit_snapshot(store, compiled)
    put = store.put
    written = 0

    def interrupted(envelope):
        nonlocal written
        if envelope["payload"].get("event") == "split_frozen":
            if written == written_receipts:
                raise OSError("simulated interruption")
            written += 1
        return put(envelope)

    monkeypatch.setattr(store, "put", interrupted)
    with pytest.raises(OSError, match="simulated"):
        freeze_signed_split(
            store, digest, c, sig, pub, created_at="2026-10-21T00:00:00Z"
        )
    snapshots = [
        d
        for d in store.list()
        if store.get(d)["payload"].get("record_type") == "DatasetSnapshot"
    ]
    assert len(snapshots) == 1
    with pytest.raises(ValueError, match="incomplete freeze"):
        verify_frozen_snapshot(store, snapshots[0], pub)
    monkeypatch.setattr(store, "put", put)
    recovered = freeze_signed_split(
        store, digest, c, sig, pub, created_at="2026-10-21T00:00:00Z"
    )
    assert recovered == store.get(snapshots[0])["content_digest"]
    assert verify_frozen_snapshot(store, recovered, pub)["split_frozen"] is True
    before = store.list()
    assert (
        freeze_signed_split(
            store, digest, c, sig, pub, created_at="2026-10-21T00:00:00Z"
        )
        == recovered
    )
    assert store.list() == before


def test_snapshot_rejects_wrong_linked_receipt(tmp_path, monkeypatch, signed_fixture):
    from faustcoder.split import freeze_signed_split, verify_frozen_snapshot
    from faustcoder.snapshot import commit_snapshot
    from faustcoder.store import ArtifactStore
    from faustcoder.canonical import build_envelope
    from faustcoder.dataset import current_state

    compiled, c, sig, pub = signed_fixture
    store = ArtifactStore(tmp_path / "wrong-receipt")
    digest = commit_snapshot(store, compiled)
    put = store.put

    def altered_receipt(envelope):
        if envelope["payload"].get("event") == "split_frozen":
            envelope = build_envelope(
                schema_version=envelope["schema_version"],
                created_at=envelope["created_at"],
                producer=envelope["producer"],
                parents=envelope["parents"],
                payload=dict(envelope["payload"], actor="unapproved reviewer"),
            )
        return put(envelope)

    monkeypatch.setattr(store, "put", altered_receipt)
    snapshot = freeze_signed_split(
        store, digest, c, sig, pub, created_at="2026-10-21T00:00:00Z"
    )
    for e in compiled.envelopes:
        if e["payload"].get("record_type") == "SourceRecord":
            assert current_state(store, e["content_digest"]) == "FROZEN"
    with pytest.raises(ValueError, match="incomplete freeze"):
        verify_frozen_snapshot(store, snapshot, pub)
    monkeypatch.setattr(store, "put", put)
    before = store.list()
    with pytest.raises(ValueError, match="does not match"):
        freeze_signed_split(
            store, digest, c, sig, pub, created_at="2026-10-21T00:00:00Z"
        )
    assert store.list() == before

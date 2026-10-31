"""N06 glue: NIM verbs, harness-only verdicts, retries and receipts."""

from __future__ import annotations

import io
import json
import random
import urllib.error
from collections.abc import Iterator

import pytest

from faustcoder import ArtifactStore, validate

from faustcoder.nvidia.graph import check_evaluation_run, check_receipt_graph, load_nodes
from faustcoder.nvidia.nim import (
    MAX_RESPONSE_BYTES,
    NIMClient,
    NIMEndpoint,
    NIMError,
    RetryPolicy,
    Verification,
    Verifier,
    deployment_payload,
    extract_source,
    harness_passed,
    latency_percentiles,
    nim_launch_argv,
    parse_completion,
    record_deployment,
    unified_diff,
    urllib_transport,
)
from tests.nvidia_support import PIN, T0, T2, T3, put_plain, spark_diagnostics, stored_pin
from tests.support import DIGEST_A, DIGEST_B

GOOD = 'import("stdfaust.lib");\nprocess = os.osc(440);\n'
BAD = "process = oops;\n"
ENDPOINT = NIMEndpoint("127.0.0.1", 8000)


def _reply(text: str) -> bytes:
    return json.dumps({"choices": [{"message": {"content": text}}]}).encode()


def _fenced(source: str) -> str:
    return f"Here you go.\n```faust\n{source}```\n"


class _Harness:
    """Stands in for the faustwasm harness: passes exactly GOOD."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def __call__(self, source: str) -> Verification:
        self.seen.append(source)
        if source == GOOD:
            return Verification(DIGEST_A, DIGEST_B, True)
        return Verification(DIGEST_A, None, False, "error: unknown identifier oops")


class _Transport:
    def __init__(self, replies: list[bytes | NIMError]) -> None:
        self.replies = replies
        self.bodies: list[dict[str, object]] = []

    def __call__(self, url: str, body: bytes, timeout: float) -> bytes:
        assert url == "http://127.0.0.1:8000/v1/chat/completions" and timeout == 60.0
        self.bodies.append(json.loads(body))
        reply = self.replies.pop(0)
        if isinstance(reply, NIMError):
            raise reply
        return reply


def _clock() -> Iterator[float]:
    value = 0.0
    while True:
        yield value
        value += 0.25


def _client(
    replies: list[bytes | NIMError],
    harness: Verifier | None = None,
    transport: _Transport | None = None,
) -> NIMClient:
    ticks = _clock()
    return NIMClient(
        ENDPOINT,
        "blackdog-faust",
        harness or _Harness(),
        transport=transport or _Transport(replies),
        sleep=lambda _s: None,
        clock=lambda: next(ticks),
        rng=random.Random(0),
    )


def test_generate_keeps_only_harness_accepted_source() -> None:
    accepted = _client([_reply(_fenced(GOOD))]).generate("sine at 440 Hz")
    assert accepted["disposition"] == "accepted" and accepted["source"] == GOOD
    assert accepted["attempts"][0]["passed"] is True
    assert accepted["latency_ms"] == 250.0
    rejected = _client([_reply(_fenced(BAD))]).generate("sine")
    assert rejected["disposition"] == "rejected" and rejected["source"] is None
    abstained = _client([_reply("I cannot do that.")]).generate("sine")
    assert abstained["disposition"] == "abstained" and abstained["attempts"] == []


def test_a_pass_without_both_receipts_fails_closed() -> None:
    assert not harness_passed(Verification(DIGEST_A, None, True))

    def lying(source: str) -> Verification:
        assert source == GOOD
        return Verification(None, None, True)

    response = _client([_reply(_fenced(GOOD))], harness=lying).generate("sine")
    assert response["disposition"] == "rejected" and response["source"] is None


def test_repair_is_bounded_and_returns_a_diff() -> None:
    transport = _Transport([_reply(_fenced(BAD)), _reply(_fenced(GOOD))])
    response = _client([], transport=transport).repair(BAD + "x\n", "error", max_repair_attempts=3)
    assert response["disposition"] == "accepted" and len(response["attempts"]) == 2
    assert response["diff"] == unified_diff(BAD + "x\n", GOOD)
    assert "unknown identifier" in json.dumps(transport.bodies[1])
    exhausted = _client([_reply(_fenced(BAD))] * 2).repair(BAD, "error", max_repair_attempts=2)
    assert exhausted["disposition"] == "rejected" and len(exhausted["attempts"]) == 2
    assert exhausted["source"] is None and exhausted["diff"] is None
    gave_up = _client([_reply("no idea")]).repair(BAD, "error", max_repair_attempts=2)
    assert gave_up["disposition"] == "abstained"
    for bound in (0, 9):
        with pytest.raises(NIMError, match="max_repair_attempts"):
            _client([]).repair(BAD, "error", max_repair_attempts=bound)


def test_explain_never_claims_correctness() -> None:
    response = _client([_reply("A 440 Hz sine oscillator.")]).explain(GOOD)
    assert response["disposition"] == "accepted" and response["correctness_claim"] is False
    assert response["attempts"] == []
    assert _client([_reply("  ")]).explain(GOOD)["disposition"] == "abstained"


def test_optimize_needs_harness_passes_and_a_proof() -> None:
    proofs: list[tuple[str, str]] = []

    def proven(original: str, candidate: str) -> str:
        proofs.append((original, candidate))
        return DIGEST_B

    accepted = _client([_reply(_fenced(GOOD))]).optimize(GOOD, proven)
    assert accepted["disposition"] == "accepted" and accepted["equivalence_digest"] == DIGEST_B
    assert proofs == [(GOOD, GOOD)]
    unproven = _client([_reply(_fenced(GOOD))]).optimize(GOOD, lambda _a, _b: None)
    assert unproven["disposition"] == "rejected" and unproven["source"] is None
    broken = _client([_reply(_fenced(BAD))]).optimize(GOOD, proven)
    assert broken["disposition"] == "rejected" and len(proofs) == 1
    assert _client([_reply("no")]).optimize(GOOD, proven)["disposition"] == "abstained"


def test_every_response_matches_the_schema() -> None:
    client = _client([_reply(_fenced(GOOD)), _reply("text")])
    for response in (client.generate("t"), client.explain(GOOD)):
        validate(response, "nim-verb-response.schema.json")
    assert client.latencies_ms == [250.0, 250.0]


def test_retries_are_bounded_with_jittered_backoff() -> None:
    sleeps: list[float] = []
    ticks = _clock()
    transport = _Transport([NIMError("down"), NIMError("down"), _reply(_fenced(GOOD))])
    client = NIMClient(
        ENDPOINT,
        "m",
        _Harness(),
        transport=transport,
        sleep=sleeps.append,
        clock=lambda: next(ticks),
        rng=random.Random(0),
    )
    assert client.generate("t")["disposition"] == "accepted"
    assert len(sleeps) == 2 and 0 <= sleeps[0] <= 0.5 and 0 <= sleeps[1] <= 1.0
    failing = _Transport([NIMError("down")] * 3)
    with pytest.raises(NIMError, match="down"):
        _client([], transport=failing).generate("t")
    assert failing.replies == []
    assert RetryPolicy(base_delay=1, max_delay=2).delay(10, random.Random(1)) <= 2


def test_client_and_endpoint_validation() -> None:
    for host in ("10.0.0.5", "nim.example.com", "169.254.169.254"):
        with pytest.raises(NIMError, match="loopback"):
            NIMEndpoint(host, 8000)
    with pytest.raises(NIMError, match="port"):
        NIMEndpoint("localhost", 0)
    with pytest.raises(NIMError, match="served_model_name"):
        NIMClient(ENDPOINT, "bad name", _Harness())
    with pytest.raises(NIMError, match="timeout"):
        NIMClient(ENDPOINT, "m", _Harness(), timeout=0)
    assert NIMClient(ENDPOINT, "m", _Harness()).latencies_ms == []


def test_completion_parsing() -> None:
    assert parse_completion(_reply("hi")) == "hi"
    for raw in (b"not json", b"{}", json.dumps({"choices": []}).encode()):
        with pytest.raises(NIMError, match="not a chat completion"):
            parse_completion(raw)
    with pytest.raises(NIMError, match="not text"):
        parse_completion(json.dumps({"choices": [{"message": {"content": None}}]}).encode())
    assert extract_source("```\n\n```") is None
    assert extract_source("```dsp\nprocess = _;\n```") == "process = _;\n"


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def test_urllib_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[float] = []
    replies: list[object] = [
        _Response(b"ok"),
        _Response(b"x" * (MAX_RESPONSE_BYTES + 1)),
        urllib.error.URLError("refused"),
    ]

    def fake_urlopen(request: object, timeout: float) -> object:
        seen.append(timeout)
        reply = replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    url = "http://127.0.0.1:8000/v1/chat/completions"
    assert urllib_transport(url, b"{}", 5.0) == b"ok"
    with pytest.raises(NIMError, match="size limit"):
        urllib_transport(url, b"{}", 5.0)
    with pytest.raises(NIMError, match="refused"):
        urllib_transport(url, b"{}", 5.0)
    with pytest.raises(NIMError, match="non-loopback"):
        urllib_transport("http://203.0.113.7:8000/v1", b"{}", 5.0)
    assert seen == [5.0, 5.0, 5.0]


def test_latency_percentiles_nearest_rank() -> None:
    samples = [float(n) for n in range(1, 101)]
    assert latency_percentiles(samples) == {"p50": 50.0, "p90": 90.0, "p99": 99.0}
    assert latency_percentiles([7.0]) == {"p50": 7.0, "p90": 7.0, "p99": 7.0}
    with pytest.raises(NIMError, match="at least one"):
        latency_percentiles([])


def test_nim_launch_argv_is_model_free_and_loopback() -> None:
    argv = nim_launch_argv(
        PIN, model_dir="/srv/out/merged", served_model_name="blackdog-faust", port=8000
    )
    assert "NIM_MODEL_PATH=/model-repo" in argv and "/srv/out/merged:/model-repo:ro" in argv
    assert argv[argv.index("-p") + 1] == "127.0.0.1:8000:8000"
    assert argv[-1] == PIN.reference
    assert not any("API_KEY" in item for item in argv)
    with pytest.raises(NIMError, match="120 GiB"):
        nim_launch_argv(
            PIN, model_dir="/m", served_model_name="m", port=8000, memory_cap_bytes=121 * 1024**3
        )
    with pytest.raises(NIMError, match="served_model_name"):
        nim_launch_argv(PIN, model_dir="/m", served_model_name="a b", port=8000)
    with pytest.raises(NIMError, match="absolute"):
        nim_launch_argv(PIN, model_dir="rel/path", served_model_name="m", port=8000)


def test_deployment_receipt_is_a_parent_of_the_evaluation(store: ArtifactStore) -> None:
    spark = put_plain(store, spark_diagnostics(), [], T0)
    dataset = put_plain(store, {"snapshot": "frozen"}, [], T0)
    pin = stored_pin(store, host=spark)
    model = put_plain(store, {"model": "merged"}, [dataset], T0)
    payload = deployment_payload(
        pin=PIN,
        container_pin_digest=pin,
        model_artifact_digest=model,
        gpu_type="NVIDIA GB10",
        endpoint=ENDPOINT,
        served_model_name="blackdog-faust",
        latencies_ms=[120.0, 80.0, 100.0],
    )
    assert payload["latency_ms"] == {"p50": 100.0, "p90": 120.0, "p99": 120.0}
    deployment = "sha256:" + record_deployment(store, payload, created_at=T2)
    assert store.get(deployment)["parents"] == [pin, model]
    evaluation = put_plain(store, {"evaluation": "nim"}, [deployment, spark], T3)
    nodes = load_nodes(store)
    assert check_receipt_graph(nodes).ok
    assert (
        check_evaluation_run(
            nodes, evaluation, dataset_snapshot=dataset, nim_deployment=deployment
        )
        == []
    )

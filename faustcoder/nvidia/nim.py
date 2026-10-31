"""Client and receipts for a local, model-free NIM endpoint (R-N003).

The endpoint serves the fine-tuned checkpoint through the
OpenAI-compatible ``/v1/chat/completions`` route. This client exposes
the four spec 001 R-010 verbs. The model only proposes text: every
candidate source goes through a ``Verifier``, which must be the
existing faustwasm harness (CompilerReceipt and DSPTestReceipt, with
the R-013 sandbox and R-021 real-time checks). The client copies the
harness verdict; it never computes one. Source is returned only when
the harness accepted it.

Production rules: loopback-only endpoints (no SSRF), a timeout on
every request, bounded retries with exponential backoff and jitter,
and fail-closed responses validated against
``nim-verb-response.schema.json``. Response shapes are INFERRED until
spec 001 T13.

Launch options live in ``faustcoder.nvidia.nim_launch``. Readiness and
latency on the cleared Spark are NOT_COMPUTABLE here.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import random
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from faustcoder.nvidia.container_pin import ImagePin
from faustcoder.nvidia.receipts import ReceiptKind, build_receipt, put_receipt
from faustcoder.schemas import validate
from faustcoder.spark_probe import MAX_MEMORY_CAP_BYTES
from faustcoder.store import ArtifactStore

VERBS = ("generate", "repair", "explain", "optimize")
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]"})
READY_PATH = "/v1/health/ready"
MODELS_PATH = "/v1/models"
MAX_REPAIR_ATTEMPTS_LIMIT = 8
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_RETRIES = 2
MAX_RESPONSE_BYTES = 1_048_576
_FENCE_RE = re.compile(r"```(?:faust|dsp)?\s*\n(.*?)```", re.DOTALL)
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./-]{0,127}$")

Transport = Callable[[str, bytes, float], bytes]
GetTransport = Callable[[str, float], bytes]
EquivalenceCheck = Callable[[str, str], str | None]


class NIMError(RuntimeError):
    """The endpoint failed, timed out or returned an unusable body."""


@dataclass(frozen=True)
class Verification:
    """The harness verdict on one candidate, copied from its receipts."""

    compiler_receipt_digest: str | None
    dsp_test_receipt_digest: str | None
    passed: bool
    diagnostics: str = ""


# Runs the faustwasm harness (``compile_source`` then ``run_signal``) on one
# source and returns its receipts. Nothing else may grade a candidate.
Verifier = Callable[[str], Verification]


@dataclass(frozen=True)
class NIMEndpoint:
    """A loopback NIM endpoint. Any other host is refused."""

    host: str
    port: int

    def __post_init__(self) -> None:
        """Refuse non-loopback hosts and invalid ports."""
        if self.host not in LOOPBACK_HOSTS:
            raise NIMError(f"NIM endpoint must be loopback, got {self.host!r}")
        if not 1 <= self.port <= 65535:
            raise NIMError(f"port out of range: {self.port}")

    @property
    def base_url(self) -> str:
        """Return ``http://<host>:<port>``."""
        return f"http://{self.host}:{self.port}"


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded retries with exponential backoff and full jitter."""

    retries: int = DEFAULT_RETRIES
    base_delay: float = 0.5
    max_delay: float = 8.0

    def delay(self, attempt: int, rng: random.Random) -> float:
        """Return the sleep before retry ``attempt`` (0-based)."""
        return rng.uniform(0, min(self.max_delay, self.base_delay * 2**attempt))


class NIMClient:
    """The four R-010 verbs over one NIM endpoint."""

    def __init__(
        self,
        endpoint: NIMEndpoint,
        served_model_name: str,
        verifier: Verifier,
        *,
        transport: Transport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        retry: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        """Bind the endpoint, harness verifier and I/O hooks."""
        if not is_safe_model_name(served_model_name):
            raise NIMError("served_model_name is not a safe model name")
        if not 0 < timeout <= 600:
            raise NIMError("timeout must be in (0, 600] seconds")
        self._endpoint = endpoint
        self._model = served_model_name
        self._verify = verifier
        self._transport = transport if transport is not None else urllib_transport
        self._timeout = timeout
        self._retry = retry if retry is not None else RetryPolicy()
        self._sleep = sleep
        self._clock = clock
        self._rng = rng if rng is not None else random.Random()
        self.latencies_ms: list[float] = []

    def generate(self, task_prompt: str) -> dict[str, object]:
        """Ask for a Faust program and keep it only if the harness passes it."""
        start = self._clock()
        candidate = extract_source(self._complete("generate", task_prompt))
        if candidate is None:
            return self._finish("generate", start, "abstained", [], {"source": None})
        check = self._verify(candidate)
        disposition = "accepted" if harness_passed(check) else "rejected"
        source = candidate if harness_passed(check) else None
        return self._finish(
            "generate", start, disposition, [_attempt(candidate, check)], {"source": source}
        )

    def repair(
        self, source: str, diagnostics: str, *, max_repair_attempts: int
    ) -> dict[str, object]:
        """Repair ``source`` within ``max_repair_attempts`` harness checks (R-012)."""
        if not 1 <= max_repair_attempts <= MAX_REPAIR_ATTEMPTS_LIMIT:
            raise NIMError(f"max_repair_attempts must be in 1..{MAX_REPAIR_ATTEMPTS_LIMIT}")
        start = self._clock()
        attempts: list[dict[str, object]] = []
        current, notes = source, diagnostics
        for _ in range(max_repair_attempts):
            candidate = extract_source(
                self._complete("repair", f"{notes}\n\n```faust\n{current}\n```")
            )
            if candidate is None:
                break
            check = self._verify(candidate)
            attempts.append(_attempt(candidate, check))
            if harness_passed(check):
                extra = {"source": candidate, "diff": unified_diff(source, candidate)}
                return self._finish("repair", start, "accepted", attempts, extra)
            current, notes = candidate, check.diagnostics
        disposition = "rejected" if attempts else "abstained"
        return self._finish("repair", start, disposition, attempts, {"source": None, "diff": None})

    def explain(self, source: str) -> dict[str, object]:
        """Explain ``source``. Never claims correctness and runs no check."""
        start = self._clock()
        text = self._complete("explain", f"```faust\n{source}\n```").strip()
        disposition = "accepted" if text else "abstained"
        extra = {"explanation": text, "correctness_claim": False}
        return self._finish("explain", start, disposition, [], extra)

    def optimize(self, source: str, equivalence: EquivalenceCheck) -> dict[str, object]:
        """Propose a faster equivalent; reject it unless equivalence is proven.

        ``equivalence(original, candidate)`` returns the content digest
        of a stored equivalence proof, or None when unproven.
        """
        start = self._clock()
        baseline = self._verify(source)
        candidate = extract_source(self._complete("optimize", f"```faust\n{source}\n```"))
        extra: dict[str, object] = {
            "baseline": _attempt(source, baseline),
            "source": None,
            "equivalence_digest": None,
        }
        if candidate is None:
            return self._finish("optimize", start, "abstained", [], extra)
        check = self._verify(candidate)
        both_pass = harness_passed(baseline) and harness_passed(check)
        proof = equivalence(source, candidate) if both_pass else None
        if proof is not None:
            extra.update(source=candidate, equivalence_digest=proof)
        disposition = "accepted" if proof is not None else "rejected"
        return self._finish("optimize", start, disposition, [_attempt(candidate, check)], extra)

    def _finish(
        self,
        verb: str,
        start: float,
        disposition: str,
        attempts: list[dict[str, object]],
        extra: Mapping[str, object],
    ) -> dict[str, object]:
        elapsed = max(0.0, (self._clock() - start) * 1000.0)
        response: dict[str, object] = {
            "verb": verb,
            "disposition": disposition,
            "served_model_name": self._model,
            "latency_ms": elapsed,
            "attempts": attempts,
            **extra,
        }
        validate(response, "nim-verb-response.schema.json")
        self.latencies_ms.append(elapsed)
        return response

    def _complete(self, verb: str, prompt: str) -> str:
        body = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPTS[verb]},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
            }
        ).encode("utf-8")
        url = f"{self._endpoint.base_url}/v1/chat/completions"
        raw = self._send_with_retry(url, body)
        return parse_completion(raw)

    def _send_with_retry(self, url: str, body: bytes) -> bytes:
        attempt = 0
        while True:
            try:
                return self._transport(url, body, self._timeout)
            except NIMError:
                if attempt >= self._retry.retries:
                    raise
                self._sleep(self._retry.delay(attempt, self._rng))
                attempt += 1


_FENCED = " Reply with a single ```faust block."
_SYSTEM_PROMPTS: Mapping[str, str] = {
    "generate": "Write one complete Faust program for the task." + _FENCED,
    "repair": "Fix the Faust program using the diagnostics." + _FENCED,
    "explain": "Explain what this Faust program does. Do not claim it is correct.",
    "optimize": "Rewrite this Faust program to be cheaper with identical output." + _FENCED,
}


def urllib_transport(url: str, body: bytes, timeout: float) -> bytes:
    """POST ``body`` to a loopback URL with a timeout. Raise NIMError on failure."""
    return _loopback_request(url, body, timeout)


def urllib_get(url: str, timeout: float) -> bytes:
    """GET a loopback URL with a timeout. Raise NIMError on failure."""
    return _loopback_request(url, None, timeout)


def check_ready(
    endpoint: NIMEndpoint,
    model_name: str,
    *,
    get: GetTransport = urllib_get,
    timeout: float = 10.0,
) -> list[str]:
    """Return the ``/v1/models`` ids once the endpoint is ready.

    Raise NIMError unless ``/v1/health/ready`` answers 2xx and
    ``model_name`` (the served name, or an adapter name on vLLM) is
    listed. One probe; the caller owns any polling.
    """
    get(endpoint.base_url + READY_PATH, timeout)
    try:
        document = json.loads(get(endpoint.base_url + MODELS_PATH, timeout))
        ids = [str(item["id"]) for item in document["data"]]
    except (ValueError, KeyError, TypeError) as exc:
        raise NIMError("NIM /v1/models response is not a model list") from exc
    if model_name not in ids:
        raise NIMError(f"NIM does not serve {model_name!r}")
    return ids


def _loopback_request(url: str, body: bytes | None, timeout: float) -> bytes:
    if not url.startswith(tuple(f"http://{host}:" for host in LOOPBACK_HOSTS)):
        raise NIMError("refusing a non-loopback NIM URL")
    if body is None:
        request = urllib.request.Request(url, method="GET")
    else:
        request = urllib.request.Request(
            url, data=body, method="POST", headers={"Content-Type": "application/json"}
        )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data: bytes = response.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise NIMError(f"NIM request failed: {exc}") from exc
    if len(data) > MAX_RESPONSE_BYTES:
        raise NIMError("NIM response exceeds the size limit")
    return data


def parse_completion(raw: bytes) -> str:
    """Return the first choice's message text from a chat-completions body."""
    try:
        document = json.loads(raw)
        content = document["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise NIMError("NIM response is not a chat completion") from exc
    if not isinstance(content, str):
        raise NIMError("NIM message content is not text")
    return content


def is_safe_model_name(name: str) -> bool:
    """Return True for a served or adapter name this client accepts (no ':')."""
    return _NAME_RE.fullmatch(name) is not None


def extract_source(text: str) -> str | None:
    """Return the first fenced Faust block, or None when there is none."""
    match = _FENCE_RE.search(text)
    if match is None:
        return None
    source = match.group(1).strip()
    return source + "\n" if source else None


def unified_diff(before: str, after: str) -> str:
    """Return a unified diff from ``before`` to ``after``."""
    lines = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        "a/source.dsp",
        "b/source.dsp",
    )
    return "".join(lines)


def latency_percentiles(samples_ms: Sequence[float]) -> dict[str, float]:
    """Return nearest-rank p50, p90 and p99 of observed latencies."""
    if not samples_ms:
        raise NIMError("latency percentiles need at least one sample")
    ordered = sorted(samples_ms)
    return {
        name: ordered[max(1, math.ceil(q * len(ordered))) - 1]
        for name, q in (("p50", 0.50), ("p90", 0.90), ("p99", 0.99))
    }


def deployment_payload(
    *,
    pin: ImagePin,
    container_pin_digest: str,
    model_artifact_digest: str,
    gpu_type: str,
    endpoint: NIMEndpoint,
    served_model_name: str,
    latencies_ms: Sequence[float],
    memory_cap_bytes: int = MAX_MEMORY_CAP_BYTES,
) -> dict[str, object]:
    """Return a NIMDeploymentReceipt payload from observed latencies."""
    return {
        "kind": ReceiptKind.NIM_DEPLOYMENT.value,
        "model_artifact_digest": model_artifact_digest,
        "container_pin_digest": container_pin_digest,
        "container_image_digest": pin.image_digest,
        "gpu_type": gpu_type,
        "served_model_name": served_model_name,
        "endpoint": endpoint.base_url,
        "verbs": list(VERBS),
        "memory_cap_bytes": memory_cap_bytes,
        "latency_ms": latency_percentiles(latencies_ms),
        "latency_sample_count": len(latencies_ms),
    }


def record_deployment(
    store: ArtifactStore,
    payload: Mapping[str, object],
    *,
    created_at: str,
    producer: str = "faustcoder.nvidia.nim",
) -> str:
    """Store a NIMDeploymentReceipt and return its artifact id."""
    return put_receipt(store, build_receipt(payload, created_at=created_at, producer=producer))


def harness_passed(check: Verification) -> bool:
    """Return True only when the harness passed and both receipts exist.

    A pass without a CompilerReceipt and a DSPTestReceipt fails closed.
    """
    return (
        check.passed
        and check.compiler_receipt_digest is not None
        and check.dsp_test_receipt_digest is not None
    )


def _attempt(source: str, check: Verification) -> dict[str, object]:
    return {
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "compiler_receipt_digest": check.compiler_receipt_digest,
        "dsp_test_receipt_digest": check.dsp_test_receipt_digest,
        "passed": harness_passed(check),
    }

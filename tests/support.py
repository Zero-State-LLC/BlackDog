"""Shared builders for artifact-store tests. Not a test module."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from faustcoder import build_envelope
from faustcoder.canonical import content_digest_for

HEX_A = "0123456789abcdef" * 4
HEX_B = "fedcba9876543210" * 4
DIGEST_A = "sha256:" + HEX_A
DIGEST_B = "sha256:" + HEX_B


def make_envelope(
    payload: dict[str, Any],
    parents: list[str] | tuple[str, ...] = (),
    **overrides: Any,
) -> dict[str, Any]:
    """Return an envelope whose id matches ``payload``."""
    fields: dict[str, Any] = {
        "schema_version": "0.3.0",
        "created_at": "2026-10-17T00:00:00Z",
        "producer": "t02-test",
        "parents": list(parents),
        "payload": payload,
    }
    fields.update(overrides)
    return build_envelope(
        schema_version=fields["schema_version"],
        created_at=fields["created_at"],
        producer=fields["producer"],
        parents=fields["parents"],
        payload=fields["payload"],
    )


def allowlisted_reward_envelope(
    *,
    passed: bool = True,
    sample_rate: int = 48000,
    mutate: Callable[[dict[str, Any]], None] | None = None,
    sync_suite_digest: bool = True,
    schema_version: str | None = None,
) -> dict[str, Any]:
    """Return a reward envelope for one frozen impulse profile."""
    from faustcoder.reward.profiles import reward_profile_payloads
    from faustcoder.signal import SIGNAL_SCHEMA_VERSION

    name = "impulse-48000-v1" if sample_rate == 48000 else "impulse-44100-v1"
    body = dict(reward_profile_payloads()[name])
    payload: dict[str, Any] = {
        "source_sha256": "ab" * 32,
        "test_suite_digest": content_digest_for(body),
        "sample_rate": body["sample_rate"],
        "block_size": body["block_size"],
        "seed": body["seed"],
        "metrics": {
            "comparison": "reward-graded-signed-full",
            "signed_frames": body["frames"],
            "frame_count": body["frames"],
            "head_frames": body["head_frames"],
            "renders": {"impulse": {"compared_frames": body["frames"]}},
        },
        "thresholds": {
            "absolute_tolerance_nano": body["absolute_tolerance_nano"],
            "clip_peak_nano": body["clip_peak_nano"],
            "head_frames": body["head_frames"],
            "relative_tolerance_nano": body["relative_tolerance_nano"],
            "silence_rms_nano": body["silence_rms_nano"],
            "tail_threshold_nano": body["tail_threshold_nano"],
            "reward_graded": True,
        },
        "passed": passed,
        "harness_digest": "sha256:" + "cd" * 32,
        "renderer": "faustwasm",
        "purpose": "reward",
        "profile": body,
    }
    if mutate is not None:
        mutate(payload)
    profile = payload.get("profile")
    if sync_suite_digest and isinstance(profile, dict):
        payload["test_suite_digest"] = content_digest_for(profile)
    return make_envelope(
        payload,
        schema_version=SIGNAL_SCHEMA_VERSION if schema_version is None else schema_version,
        producer="faustcoder.signal",
    )


def compiler_failure_envelope(
    *,
    exit_code: int,
    diagnostic_class: str,
    diagnostics: str,
    schema_version: str = "0.3.2",
) -> dict[str, Any]:
    """Return a compiler envelope whose stderr digest matches ``diagnostics``."""
    payload = {
        "source_sha256": "ab" * 32,
        "faust_version": "2.90.0",
        "command": ["libfaust-wasm"],
        "exit_code": exit_code,
        "stdout_digest": "sha256:" + "00" * 32,
        "stderr_digest": "sha256:" + hashlib.sha256(diagnostics.encode("utf-8")).hexdigest(),
        "duration_ms": 1,
        "environment_digest": "sha256:" + "11" * 32,
        "compiler": "libfaust-wasm",
        "lang": "wasm",
        "options": [],
        "diagnostic_class": diagnostic_class,
    }
    return make_envelope(
        payload,
        schema_version=schema_version,
        producer="faustcoder.compiler",
    )

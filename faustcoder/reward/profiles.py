"""Frozen reward profiles.

``REWARD_PROFILES`` maps a ``test_suite_digest`` to a profile name.
The digest is ``content_digest_for(profile_payload(profile))``. A
version or tolerance change produces a new name; old receipts then
fail closed as ``profile_not_allowlisted``. v0.2 rewards the impulse
profile only. Nonlinear stimuli stay unrewardable until that suite
is reviewed.

``head_frames`` is pinned at 2048 and ``max_frames`` at the 144000
block-aligned cap. Both are inside the digest. The reward comparison
still signs every sample out to ``max_frames`` (ADR-0006 A4).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

PROFILE_NAMES = ("impulse-44100-v1", "impulse-48000-v1")

# Digests of the payloads below. A profile edit must change this map
# in the same commit; ``reward_profiles`` refuses a silent drift.
REWARD_PROFILES: dict[str, str] = {
    "sha256:4b24efe4c30562344e56713da4ec05b3e4e59dfe9b8ddebbcfdeef9f64ac88ee": "impulse-44100-v1",
    "sha256:e38d50f7345453e14c739fbfeccc7f561ec92c6cec71d181a888b250bcd2ddd0": "impulse-48000-v1",
}


@lru_cache(maxsize=1)
def reward_profile_payloads() -> dict[str, dict[str, Any]]:
    """Return ``{name: canonical profile payload}``."""
    from faustcoder.signal import (
        DEFAULT_BLOCK_SIZE,
        DEFAULT_FRAMES,
        DEFAULT_SEED,
        MAX_FRAMES,
        SignalProfile,
        profile_payload,
    )

    cap = MAX_FRAMES - (MAX_FRAMES % DEFAULT_BLOCK_SIZE)
    payloads: dict[str, dict[str, Any]] = {}
    for rate, name in ((44100, "impulse-44100-v1"), (48000, "impulse-48000-v1")):
        profile = SignalProfile(
            sample_rate=rate,
            block_size=DEFAULT_BLOCK_SIZE,
            seed=DEFAULT_SEED,
            frames=cap,
            head_frames=DEFAULT_FRAMES,
            max_frames=cap,
            stimuli=("impulse",),
            reject_nonfinite=True,
            require_reference=True,
        )
        payloads[name] = profile_payload(profile)
    return payloads


@lru_cache(maxsize=1)
def reward_profiles() -> dict[str, str]:
    """Return the frozen ``{test_suite_digest: profile name}`` allowlist.

    The map checked into this module is authoritative. It must equal
    the digests of ``reward_profile_payloads``.
    """
    from faustcoder.canonical import content_digest_for

    computed = {
        content_digest_for(payload): name
        for name, payload in reward_profile_payloads().items()
    }
    if computed != REWARD_PROFILES:
        raise RuntimeError("REWARD_PROFILES does not match the canonical profile payloads")
    return dict(REWARD_PROFILES)

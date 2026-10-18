"""Frozen reward profiles.

``REWARD_PROFILES`` is the only allowlist literal. It maps a
``test_suite_digest`` to a profile name. The digest is
``profile_digest`` in ``faustcoder.signal``, the only function that
hashes a signal profile. A ``profile_payload`` version change, or a
pinned compiler flag that lands in that payload, updates this map
and nothing else. Old receipts then fail closed as
``profile_not_allowlisted``. v0.2 rewards the impulse profile only.
Nonlinear stimuli stay unrewardable until that suite is reviewed.

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
def reward_signal_profiles() -> dict[str, Any]:
    """Return ``{name: SignalProfile}`` for the frozen impulse profiles."""
    from faustcoder.signal import (
        DEFAULT_BLOCK_SIZE,
        DEFAULT_FRAMES,
        DEFAULT_SEED,
        MAX_FRAMES,
        SignalProfile,
    )

    cap = MAX_FRAMES - (MAX_FRAMES % DEFAULT_BLOCK_SIZE)
    profiles: dict[str, Any] = {}
    for rate, name in ((44100, "impulse-44100-v1"), (48000, "impulse-48000-v1")):
        profiles[name] = SignalProfile(
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
    return profiles


def reward_signal_profile(name: str) -> Any:
    """Return one frozen impulse profile. ``name`` is the allowlist name."""
    profiles = reward_signal_profiles()
    try:
        return profiles[name]
    except KeyError as exc:
        raise KeyError(name) from exc


@lru_cache(maxsize=1)
def reward_profile_payloads() -> dict[str, dict[str, Any]]:
    """Return ``{name: canonical profile payload}``."""
    from faustcoder.signal import profile_payload

    return {
        name: profile_payload(profile)
        for name, profile in reward_signal_profiles().items()
    }


@lru_cache(maxsize=1)
def reward_profiles() -> dict[str, str]:
    """Return the frozen ``{test_suite_digest: profile name}`` allowlist.

    The map checked into this module is authoritative. It must equal
    ``profile_digest`` of ``reward_signal_profiles``. That function is
    the only digest computation.
    """
    from faustcoder.signal import profile_digest

    computed = {
        profile_digest(profile): name
        for name, profile in reward_signal_profiles().items()
    }
    if computed != REWARD_PROFILES:
        raise RuntimeError("REWARD_PROFILES does not match profile_digest of the frozen profiles")
    return dict(REWARD_PROFILES)

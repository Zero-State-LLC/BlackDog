"""Offline DSP signal harness (T04, R-006, R-013).

The renderer is faustwasm's offline processor, driven through
``faust/worker/render.mjs`` in the same sandbox as the T03 compiler:
``unshare --net``, no Node network permission, bounded time, memory
and output. Library imports are not rendered here. Staging the pinned
faustlibraries tree is T03b.

One run is one sample rate (44.1 or 48 kHz), one block size, one seed
and the stimuli named by the profile (impulse, sine, noise). A suite
runs both rates. Buttons are 1 for the first block and 0 after that,
which is sample 0 when the block size is 1.

Comparison has two parts. The head (default 2048 frames, or the
whole render when that is shorter) is an exact sample check. The
allowed gap on sample ``ref`` is ``atol + rtol * abs(ref)``. Default
``atol`` is 2e-6, the default cited for Faust's ``filesCompare``
tool; this change did not re-read that source, so the citation is
INFERRED. Default ``rtol`` is 1e-5, the relative term in
``numpy.allclose``, and that citation is INFERRED too. The rest of
the render is a coarse check: per-block RMS and spectral band
energies, with the same tolerance. That coarse check is
magnitude-only, and the 2e-6 floor is per sample, so one 1e-5 spike
inside a 64-sample block can hide in the block RMS. A
``reward_graded`` run signs every sample of the render up to the
pinned ``max_frames``, including sign and timing past ``head_frames``
(spec §23 A4, ADR-0006). Coarse magnitude checks are not a reward
pass. An impulse reference whose ``max_frames`` is below the 144000
block-aligned cap raises ``ValueError``; the cap is not raised.
``thresholds.reward_graded`` is stored on every receipt and is part
of the reproducible digest. ``purpose`` is ``reward`` or
``diagnostic``. Diagnostic receipts are not rewards.
``profile_payload`` stays version 2. ``profile_digest`` is the only
profile digest, and the two impulse digests stay the frozen
``REWARD_PROFILES`` entries. ``-fm`` is refused and ``-ftz`` is
pinned to 0 for every signal render, diagnostic or reward, so one
source has one compiler digest. Those flags are not inside
``test_suite_digest``. A named nonlinear suite
(``nonlinear-suite-v1``) renders eight float32 stimuli at the
144000-frame floor and signs every sample. Its stimulus bytes are
recorded on the receipt and are not part of the allowlist digest.
THD+N, IMD and Farina inverse-filter peaks are stored on the receipt
and are not pass gates, and they are left out of the reproducible
digest. The suite digest is not in ``REWARD_PROFILES``. TaskSpec
``effect`` is a closed enum. Only ``linear`` and ``time_invariant``
are rewardable. ``dataset_reward_row`` and ``rl_batch`` call
``require_task_rewardable``. ``nonlinear-suite-fallback-v1`` is the
four-stimulus subset.
``reject_dc`` does not fire when the reference carries the same DC.
An impulse reference is built at
``max_frames`` (144000, three seconds at 48 kHz) and trimmed to the
last sample at or above ``tail_threshold``, plus a margin. The tail
gate scans that whole reference, so a silent gap before a delay or
echo is still late energy. The candidate render covers the reference.
A default impulse length is that reference, or the cap, and is never
left at 2048. Sine and noise are not tail-gated; a profile that names
only those keeps 2048.

Metrics are integers on a 1e-9 grid (RMS, peak, absolute error,
spectral band magnitudes) plus counts of NaN, Inf and float32
denormals. A decaying legal feedback loop may end in denormals.
Denormals are always counted. They fail the run only when the profile
sets ``max_denormal_count``. Silence, DC, clipping, non-finite output
and a channel mismatch fail when the profile says so. CPU wall time
is recorded only for a promotion candidate (R-006) and is the only
field dropped from the reproducible digest.

Receipts validate against ``dsp-test-receipt.schema.json`` and are
stored with the T02 envelope. The compiler receipt and the reference
document are parents. Frames, stimulus names and the metric keys are
not fields of the accepted DSPTestReceipt contract. They live in the
open ``metrics`` and ``thresholds`` objects. That shape is INFERRED
and written down in ``data-model.md``. No accepted spec sentence was
edited.

Harness failures (sandbox, worker crash, compile that disagrees with
the T03 receipt) raise ``SignalHarnessError`` and do not write a
receipt. A failed network canary raises ``SandboxError`` and does not
write a receipt either. The candidate stays in ``COMPILE_CHECKED``.
A rendered program that fails a required check does write a receipt
with ``passed`` false and moves to ``REJECTED``.
"""

from __future__ import annotations

import array
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from faustcoder.candidate_machine import (
    CandidateState,
    apply_diagnostic_signal,
    apply_signal,
)
from faustcoder.canonical import build_envelope, content_digest_for, digest_hex
from faustcoder.compiler import (
    FAUSTWASM_VERSION,
    Compilation,
    compile_source,
    runtime_pin,
    store_compiler_receipt,
    worker_directory,
)
from faustcoder.compiler import _raise_if_canary_failed, _stage_runtime, _validate_options
from faustcoder.sandbox import (
    ResourceLimits,
    SandboxError,
    node_command,
    run_in_sandbox,
    unshare_identity,
)
from faustcoder.schemas import validate
from faustcoder.store import ArtifactStore

NANO = 1_000_000_000
SAMPLE_RATES = (44100, 48000)
DEFAULT_BLOCK_SIZE = 64
DEFAULT_SEED = 1
DEFAULT_FRAMES = 2048
DEFAULT_TOLERANCE = 2e-6
DEFAULT_RELATIVE_TOLERANCE = 1e-5
DEFAULT_TAIL_THRESHOLD = 1e-8
DEFAULT_TAIL_MARGIN = 64
MAX_FRAMES = 144_000
STIMULI = ("impulse", "sine", "noise")
# Names the worker may render. The default profile stays on STIMULI.
KNOWN_STIMULI = (
    "impulse",
    "sine",
    "noise",
    "ess",
    "sine_997_m1",
    "sine_997_m20",
    "smpte",
    "noise_m12",
    "noise_m30",
    "dc_step",
)
# Stimuli that are not the legacy impulse/sine/noise triple. Any of
# these pulls the render onto the 144000-frame floor.
SUITE_STIMULI = frozenset(
    {
        "ess",
        "sine_997_m1",
        "sine_997_m20",
        "smpte",
        "noise_m12",
        "noise_m30",
        "dc_step",
    }
)
NONLINEAR_SUITE_V1 = "nonlinear-suite-v1"
NONLINEAR_SUITE_FALLBACK_V1 = "nonlinear-suite-fallback-v1"
NONLINEAR_SUITE_STIMULI = (
    "impulse",
    "ess",
    "sine_997_m1",
    "sine_997_m20",
    "smpte",
    "noise_m12",
    "noise_m30",
    "dc_step",
)
NONLINEAR_SUITE_FALLBACK_STIMULI = (
    "impulse",
    "sine_997_m1",
    "sine_997_m20",
    "noise_m12",
)
_SUITE_STIMULI_FOR = {
    NONLINEAR_SUITE_V1: NONLINEAR_SUITE_STIMULI,
    NONLINEAR_SUITE_FALLBACK_V1: NONLINEAR_SUITE_FALLBACK_STIMULI,
}
# Faust default. Reward-graded profiles and the nonlinear suite digest this.
PINNED_FTZ = "0"
PINNED_COMPILE_FLAGS = ("-ftz", PINNED_FTZ)
METRIC_VERSION = 2
SIGNAL_SCHEMA_VERSION = "0.3.4"
_SCHEMA = "dsp-test-receipt.schema.json"
_FLOAT32_MIN_NORMAL = 1.1754943508222875e-38
_PI = 3.141592653589793
_TWO_PI = 6.283185307179586
_MASK64 = (1 << 64) - 1
_LIBRARY_IMPORT = re.compile(
    r"""(?ix)\b(?:import|library|component)\s*\(\s*["'](?!https?://)"""
)
_STIMULUS_FILE = re.compile(
    r"^(impulse|sine|noise|ess|sine_997_m1|sine_997_m20|smpte|noise_m12|noise_m30|dc_step)$"
)


class SignalHarnessError(Exception):
    """The harness failed before it could judge the signal.

    ``termination`` is the structured worker report for this stage:
    signal number, JS stack overflow, and wasm trap kind. The message
    is the render exception text and is not a reward marker.
    """

    def __init__(
        self, message: str, *, termination: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        reported = termination or {}
        signal = reported.get("termination_signal")
        trap = reported.get("wasm_trap")
        self.termination = {
            "termination_signal": signal if isinstance(signal, int) else None,
            "runtime_stack_overflow": reported.get("runtime_stack_overflow") is True,
            "wasm_trap": trap if isinstance(trap, str) and trap else None,
        }


class SignalLibrariesUnavailable(SignalHarnessError):
    """The source imports a library and the pinned tree is not staged."""


@dataclass(frozen=True)
class SignalProfile:
    """One offline render and the checks applied to it."""

    sample_rate: int
    block_size: int = DEFAULT_BLOCK_SIZE
    seed: int = DEFAULT_SEED
    frames: int = DEFAULT_FRAMES
    head_frames: int | None = None
    max_frames: int | None = None
    stimuli: tuple[str, ...] = STIMULI
    sine_hz: int = 440
    sine_amplitude: float = 0.5
    noise_amplitude: float = 1.0
    impulse_amplitude: float = 1.0
    expected_channels: int | None = None
    absolute_tolerance: float = DEFAULT_TOLERANCE
    relative_tolerance: float = DEFAULT_RELATIVE_TOLERANCE
    tail_threshold: float = DEFAULT_TAIL_THRESHOLD
    silence_rms: float = 1e-8
    clip_peak: float = 1.0
    reject_silence: bool = True
    reject_dc: bool = True
    reject_clipping: bool = True
    reject_nonfinite: bool = True
    max_denormal_count: int | None = None
    require_reference: bool = True
    press_buttons_first_block: bool = True
    suite: str | None = None

    def __post_init__(self) -> None:
        if self.sample_rate not in SAMPLE_RATES:
            raise ValueError("sample_rate must be 44100 or 48000")
        if self.block_size < 1 or self.block_size > 4096:
            raise ValueError("block_size must be from 1 to 4096")
        cap = self.max_frames
        if cap is None:
            cap = MAX_FRAMES - (MAX_FRAMES % self.block_size)
            object.__setattr__(self, "max_frames", cap)
        if cap < self.block_size or cap > MAX_FRAMES or cap % self.block_size != 0:
            raise ValueError("max_frames must be a block multiple up to 144000")
        if self.frames < self.block_size or self.frames > cap:
            raise ValueError("frames must be from block_size to max_frames")
        if self.frames % self.block_size != 0:
            raise ValueError("frames must be a multiple of block_size")
        head = self.head_frames if self.head_frames is not None else min(DEFAULT_FRAMES, self.frames)
        if not isinstance(head, int) or isinstance(head, bool) or head < 1 or head > self.frames:
            raise ValueError("head_frames must lie inside the render")
        object.__setattr__(self, "head_frames", head)
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        if not self.stimuli:
            raise ValueError("stimuli must name at least one stimulus")
        if len(set(self.stimuli)) != len(self.stimuli):
            raise ValueError("stimuli must not repeat")
        for name in self.stimuli:
            if name not in KNOWN_STIMULI:
                raise ValueError(f"unknown stimulus: {name}")
        if self.sine_hz < 1 or self.sine_hz >= self.sample_rate // 2:
            raise ValueError("sine_hz must be inside the Nyquist limit")
        for label, value in (
            ("sine_amplitude", self.sine_amplitude),
            ("noise_amplitude", self.noise_amplitude),
            ("impulse_amplitude", self.impulse_amplitude),
        ):
            if not math.isfinite(value) or value <= 0 or value > 4:
                raise ValueError(f"{label} must be in (0, 4]")
        if self.expected_channels is not None and self.expected_channels < 1:
            raise ValueError("expected_channels must be positive")
        if not math.isfinite(self.absolute_tolerance) or self.absolute_tolerance < 0:
            raise ValueError("absolute_tolerance must be finite and non-negative")
        if not math.isfinite(self.relative_tolerance) or self.relative_tolerance < 0:
            raise ValueError("relative_tolerance must be finite and non-negative")
        if not math.isfinite(self.tail_threshold) or self.tail_threshold < 0:
            raise ValueError("tail_threshold must be finite and non-negative")
        if not math.isfinite(self.silence_rms) or self.silence_rms < 0:
            raise ValueError("silence_rms must be finite and non-negative")
        if not math.isfinite(self.clip_peak) or self.clip_peak <= 0:
            raise ValueError("clip_peak must be finite and positive")
        if self.max_denormal_count is not None and self.max_denormal_count < 0:
            raise ValueError("max_denormal_count must be non-negative")
        if self.suite is not None:
            expected = _SUITE_STIMULI_FOR.get(self.suite)
            if expected is None:
                raise ValueError(f"unknown signal suite: {self.suite}")
            if tuple(self.stimuli) != expected:
                raise ValueError("suite stimuli do not match the named profile")
            if self.sample_rate != 48000:
                raise ValueError("nonlinear suite sample_rate is 48000")
            if MAX_FRAMES % self.block_size != 0:
                raise ValueError("suite block_size must divide the 144000 frame floor")
            if self.frames != MAX_FRAMES or self.max_frames != MAX_FRAMES:
                raise ValueError(
                    "suite stimulus requires frames and max_frames of at least "
                    "the 144000 block-aligned floor"
                )
            if self.head_frames != self.frames:
                raise ValueError("suite comparison covers every frame")


@dataclass(frozen=True)
class SignalReference:
    """Expected float32 samples for one rate, block, length, seed and stimulus set.

    ``samples`` is channel-major. A non-finite sample is refused here,
    before any comparison. The render that produced the samples is the
    identity below; a profile with a different identity is not compared.
    """

    sample_rate: int
    block_size: int
    frames: int
    seed: int
    stimuli: tuple[str, ...]
    channels: int
    samples: Mapping[str, Sequence[Sequence[float]]]

    def __post_init__(self) -> None:
        if self.sample_rate not in SAMPLE_RATES:
            raise ValueError("sample_rate must be 44100 or 48000")
        if self.block_size < 1 or self.block_size > 4096:
            raise ValueError("block_size must be from 1 to 4096")
        if self.frames < 1:
            raise ValueError("frames must be positive")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        if self.channels < 1:
            raise ValueError("channels must be positive")
        stimuli = self.stimuli
        if not isinstance(stimuli, tuple):
            stimuli = tuple(stimuli)
            object.__setattr__(self, "stimuli", stimuli)
        if not stimuli:
            raise ValueError("stimuli must name at least one stimulus")
        if len(set(stimuli)) != len(stimuli):
            raise ValueError("stimuli must not repeat")
        for name in stimuli:
            if name not in KNOWN_STIMULI:
                raise ValueError(f"unknown stimulus: {name}")
        if set(self.samples) != set(stimuli):
            raise ValueError("reference samples must match the stimulus names")
        for name in stimuli:
            channels = self.samples[name]
            if len(channels) != self.channels:
                raise ValueError(f"reference {name} has the wrong channel count")
            for channel in channels:
                if len(channel) != self.frames:
                    raise ValueError(f"reference {name} has the wrong frame count")
                for sample in channel:
                    if not math.isfinite(float(sample)):
                        raise SignalHarnessError(
                            "non-finite reference samples are refused at load"
                        )


@dataclass(frozen=True)
class SignalRun:
    """One rate's compile, render and DSPTestReceipt.

    ``receipt`` is ``None`` when a reward-graded compile exit 124, 125
    or 126, or a render crash, is deferred to ``commit_signal_check``.
    ``reward_failure`` names that deferral (``compiler``,
    ``worker_crash`` or ``harness_crash``).
    """

    compilation: Compilation
    receipt: dict[str, Any] | None
    reproducible_digest: str
    failures: tuple[str, ...]
    reference_payload: dict[str, Any] | None
    reward_failure: str | None = None
    source: str | None = None
    options: tuple[str, ...] = ()
    limits: ResourceLimits | None = None
    termination_signal: int | None = None
    runtime_stack_overflow: bool = False
    wasm_trap: str | None = None


@dataclass(frozen=True)
class SignalSuite:
    """Both sample rates, or the rates the caller asked for.

    ``ledger`` is the reward ledger a reward-graded suite was given.
    ``commit_signal_check`` uses it when the caller does not pass one.
    """

    runs: tuple[SignalRun, ...]
    ledger: object | None = None

    @property
    def passed(self) -> bool:
        return all(
            run.receipt is not None and run.receipt["passed"] for run in self.runs
        )


@dataclass(frozen=True)
class SignalCommit:
    """Stored receipts and the candidate state after the signal edge."""

    state: CandidateState
    artifact_ids: tuple[str, ...]
    suite: SignalSuite
    outcomes: tuple[object, ...] = ()


def f32(value: float) -> float:
    """Round ``value`` to the nearest float32 and return it as a float."""
    packed = array.array("f", [float(value)])
    if sys.byteorder != "little":
        packed.byteswap()
    raw = packed.tobytes()
    unpacked = array.array("f")
    unpacked.frombytes(raw)
    if sys.byteorder != "little":
        unpacked.byteswap()
    return float(unpacked[0])


def to_nano(value: float) -> int:
    """Quantize ``value`` to the nearest 1e-9, half away from zero."""
    if not math.isfinite(value):
        raise SignalHarnessError("a metric was not finite")
    scaled = value * NANO
    if scaled >= 0:
        return int(math.floor(scaled + 0.5))
    return int(math.ceil(scaled - 0.5))


def impulse_samples(frames: int, amplitude: float = 1.0) -> list[float]:
    """Return an impulse: ``amplitude`` at frame 0, then zeros."""
    samples = [0.0] * frames
    if frames:
        samples[0] = f32(amplitude)
    return samples


def sine_samples(
    frames: int, sample_rate: int, freq_hz: int, amplitude: float = 0.5
) -> list[float]:
    """Return a float32 sine from a fixed Taylor series.

    The phase advance is ``2π freq / sample_rate``. Range reduction and
    the series use IEEE arithmetic in this process, then each sample is
    rounded to float32. The worker does not recompute it.
    """
    if freq_hz < 1 or freq_hz >= sample_rate // 2:
        raise ValueError("sine_hz must be inside the Nyquist limit")
    amp = f32(amplitude)
    step = _TWO_PI * freq_hz / sample_rate
    samples: list[float] = []
    for index in range(frames):
        samples.append(f32(_sin_series(index * step) * amp))
    return samples


def noise_samples(frames: int, seed: int, amplitude: float = 1.0) -> list[float]:
    """Return deterministic float32 noise from xorshift64.

    The state is the seed masked to 64 bits, or the fixed odd constant
    when that mask is 0. Each step is ``x ^= x<<13; x ^= x>>7; x ^=
    x<<17``. The top 24 bits map to ``[-1, 1)`` in steps of 2^-23, so
    the value is an exact float32 before the amplitude multiply.
    """
    state = seed & _MASK64
    if state == 0:
        state = 0x9E3779B97F4A7C15
    amp = f32(amplitude)
    samples: list[float] = []
    for _ in range(frames):
        state = _xorshift64(state)
        unit = ((state >> 40) / float(1 << 24)) * 2.0 - 1.0
        samples.append(f32(unit * amp))
    return samples


def stimuli_for(profile: SignalProfile) -> dict[str, list[float]]:
    """Build the mono stimulus for each name in ``profile``."""
    built: dict[str, list[float]] = {}
    for name in profile.stimuli:
        if name == "impulse":
            built[name] = impulse_samples(profile.frames, profile.impulse_amplitude)
        elif name == "sine":
            built[name] = sine_samples(
                profile.frames, profile.sample_rate, profile.sine_hz, profile.sine_amplitude
            )
        elif name == "noise":
            built[name] = noise_samples(profile.frames, profile.seed, profile.noise_amplitude)
        elif name in SUITE_STIMULI:
            from faustcoder.signal_suite import suite_stimulus

            built[name] = suite_stimulus(name, profile.frames, profile.sample_rate)
        else:
            raise ValueError(f"unknown stimulus: {name}")
    return built


def source_needs_libraries(source: str) -> bool:
    """Return whether ``source`` imports a Faust library or component."""
    return _LIBRARY_IMPORT.search(source) is not None


def profile_digest(profile: SignalProfile) -> str:
    """Return the ``test_suite_digest`` of ``profile``.

    This is the only profile digest computation. Receipts and
    ``REWARD_PROFILES`` both call it. A payload version change belongs
    in ``profile_payload``; the digest follows from there. Compile
    flags are not in this payload. Pinning ``-ftz 0`` does not move
    the frozen impulse digests.
    """
    return content_digest_for(profile_payload(profile))


def profile_payload(profile: SignalProfile) -> dict[str, Any]:
    """Return the canonical object hashed into ``test_suite_digest``.

    Version 2 is the allowlist shape. Stimulus bytes and compile flags
    are recorded on the receipt metrics. They are not fields here.
    """
    return {
        "absolute_tolerance_nano": to_nano(profile.absolute_tolerance),
        "block_size": profile.block_size,
        "clip_peak_nano": to_nano(profile.clip_peak),
        "expected_channels": profile.expected_channels,
        "frames": profile.frames,
        "head_frames": profile.head_frames,
        "max_frames": profile.max_frames,
        "impulse_amplitude_nano": to_nano(profile.impulse_amplitude),
        "max_denormal_count": profile.max_denormal_count,
        "metric_version": METRIC_VERSION,
        "noise_amplitude_nano": to_nano(profile.noise_amplitude),
        "press_buttons_first_block": profile.press_buttons_first_block,
        "reject_clipping": profile.reject_clipping,
        "reject_dc": profile.reject_dc,
        "reject_nonfinite": profile.reject_nonfinite,
        "reject_silence": profile.reject_silence,
        "relative_tolerance_nano": to_nano(profile.relative_tolerance),
        "require_reference": profile.require_reference,
        "sample_rate": profile.sample_rate,
        "seed": profile.seed,
        "silence_rms_nano": to_nano(profile.silence_rms),
        "tail_threshold_nano": to_nano(profile.tail_threshold),
        "sine_amplitude_nano": to_nano(profile.sine_amplitude),
        "sine_hz": profile.sine_hz,
        "stimuli": list(profile.stimuli),
        "version": 2,
    }


def reference_payload(reference: SignalReference) -> dict[str, Any]:
    """Return the integer reference document stored as an artifact.

    The identity is the reference's own rate, block, frame count, seed
    and stimulus names. Samples are the 1e-9 grid the comparison uses.
    """
    stimuli: dict[str, list[list[int]]] = {}
    for name in reference.stimuli:
        stimuli[name] = [
            [to_nano(float(sample)) for sample in channel]
            for channel in reference.samples[name]
        ]
    return {
        "block_size": reference.block_size,
        "channels": reference.channels,
        "frames": reference.frames,
        "kind": "faustcoder.signal-reference",
        "quantization_nano": NANO,
        "sample_rate": reference.sample_rate,
        "seed": reference.seed,
        "stimulus_names": list(reference.stimuli),
        "stimuli": stimuli,
        "version": 2,
    }


def reproducible_signal_digest(receipt: Mapping[str, Any]) -> str:
    """Return ``sha256:`` of the receipt without timing or diagnostics.

    ``cpu_duration_ms`` and ``render_ms`` are timing. Per-stimulus
    ``diagnostics`` (THD+N, IMD, sweep harmonics) are logged and are
    not a pass gate, so they are not part of the reward digest either.
    """
    body = {key: value for key, value in receipt.items()}
    metrics = body.get("metrics")
    if isinstance(metrics, dict):
        body["metrics"] = _metrics_for_digest(metrics)
    return content_digest_for(body)


def _metrics_for_digest(metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Drop timing and diagnostic fields from a metrics object."""
    cleaned = {
        key: value
        for key, value in metrics.items()
        if key not in {"cpu_duration_ms", "render_ms", "toolchain"}
    }
    renders = cleaned.get("renders")
    if not isinstance(renders, dict):
        return cleaned
    stripped: dict[str, Any] = {}
    for name, summary in renders.items():
        if isinstance(summary, dict):
            stripped[name] = {
                key: value for key, value in summary.items() if key != "diagnostics"
            }
        else:
            stripped[name] = summary
    cleaned["renders"] = stripped
    return cleaned


def impulse_decay_frames(
    samples: Sequence[float],
    *,
    threshold: float,
    block_size: int,
    margin: int = DEFAULT_TAIL_MARGIN,
    cap: int = MAX_FRAMES,
) -> int:
    """Return a block-aligned length that includes the last hot sample.

    The length is the last sample at or above ``threshold``, plus
    ``margin``, rounded up to ``block_size`` and clamped to ``cap``.
    A signal that is still hot at the cap stays at the cap.
    """
    if block_size < 1:
        raise ValueError("block_size must be positive")
    if margin < 0:
        raise ValueError("margin must be non-negative")
    last_hot = -1
    for index, sample in enumerate(samples):
        if abs(float(sample)) >= threshold:
            last_hot = index
    if last_hot < 0:
        length = block_size
    else:
        length = last_hot + 1 + margin
    if length % block_size:
        length += block_size - (length % block_size)
    length = max(block_size, length)
    aligned_cap = cap - (cap % block_size)
    return min(length, aligned_cap)


def impulse_reference(
    profile: SignalProfile,
    transform: Callable[[list[float]], Sequence[float]],
    *,
    margin: int = DEFAULT_TAIL_MARGIN,
) -> SignalReference:
    """Build an impulse reference at the cap, then trim it.

    ``transform`` sees the full cap-length impulse and returns the
    same number of samples. The stored reference ends one margin after
    the last sample at or above ``tail_threshold``.
    """
    cap = profile.max_frames
    if not isinstance(cap, int):
        raise SignalHarnessError("max_frames was not resolved")
    impulse = impulse_samples(cap, profile.impulse_amplitude)
    rendered = [float(sample) for sample in transform(impulse)]
    if len(rendered) != cap:
        raise SignalHarnessError("impulse reference transform changed the frame count")
    length = impulse_decay_frames(
        rendered,
        threshold=profile.tail_threshold,
        block_size=profile.block_size,
        margin=margin,
        cap=cap,
    )
    return SignalReference(
        sample_rate=profile.sample_rate,
        block_size=profile.block_size,
        frames=length,
        seed=profile.seed,
        stimuli=("impulse",),
        channels=1,
        samples={"impulse": [rendered[:length]]},
    )


def _reward_created_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_reward_ledger(ledger: object) -> Any:
    if ledger is None or not hasattr(ledger, "queue") or not hasattr(ledger, "rates"):
        from faustcoder.reward.grader import RewardUseRefused

        raise RewardUseRefused(
            "reward-graded compiler and crash outcomes require a reward ledger; "
            "refusing to score or drop them"
        )
    return ledger


def _hold_compiler_for_reward(compiled: Compilation, ledger: object) -> None:
    """Grade a failed compile onto the ledger. Always raises."""
    bound = _require_reward_ledger(ledger)
    from faustcoder.compiler import COMPILER_SCHEMA_VERSION
    from faustcoder.reward.grader import RewardOutcomeHeld, grade_receipt

    envelope = build_envelope(
        schema_version=COMPILER_SCHEMA_VERSION,
        created_at=_reward_created_at(),
        producer="faustcoder.compiler",
        parents=[],
        payload=compiled.receipt,
    )
    grade = grade_receipt(
        envelope,
        diagnostics=compiled.diagnostics,
        policy="signal",
        queue=bound.queue,
        rates=bound.rates,
    )
    raise RewardOutcomeHeld(grade)


def _deferred_reward_run(
    compiled: Compilation,
    kind: str,
    *,
    source: str,
    options: tuple[str, ...] = (),
    limits: ResourceLimits | None = None,
    termination_signal: int | None = None,
    runtime_stack_overflow: bool = False,
    wasm_trap: str | None = None,
) -> SignalRun:
    """Return a suite run whose grade happens in ``commit_signal_check``."""
    return SignalRun(
        compilation=compiled,
        receipt=None,
        reproducible_digest=compiled.reproducible_digest,
        failures=(kind,),
        reference_payload=None,
        reward_failure=kind,
        source=source,
        options=options,
        limits=limits,
        termination_signal=termination_signal,
        runtime_stack_overflow=runtime_stack_overflow,
        wasm_trap=wasm_trap,
    )


def _hold_crash_for_reward(
    reproducible_digest: str,
    ledger: object,
    *,
    kind: str,
    exit_code: int = 126,
) -> None:
    """Grade a worker or harness crash onto the ledger. Always raises."""
    bound = _require_reward_ledger(ledger)
    from faustcoder.reward.grader import RewardOutcomeHeld, grade_receipt

    envelope = build_envelope(
        schema_version=SIGNAL_SCHEMA_VERSION,
        created_at=_reward_created_at(),
        producer="faustcoder.signal",
        parents=[],
        payload={
            "kind": kind,
            "exit_code": exit_code,
            "diagnostic_class": "internal",
            "reproducible_digest": reproducible_digest,
        },
    )
    grade = grade_receipt(
        envelope,
        policy="signal",
        queue=bound.queue,
        rates=bound.rates,
    )
    raise RewardOutcomeHeld(grade)


def run_signal(
    source: str,
    profile: SignalProfile,
    reference: SignalReference | None = None,
    *,
    options: Sequence[str] = (),
    limits: ResourceLimits | None = None,
    promotion_candidate: bool = False,
    reward_graded: bool = False,
    ledger: object | None = None,
    defer_reward_failure: bool = False,
) -> SignalRun:
    """Compile and render ``source``. Return a schema-valid receipt.

    Raises ``SignalLibrariesUnavailable`` when ``source`` imports a
    library. Raises ``SignalHarnessError`` when the sandbox or the
    worker fails. A failed network canary raises ``SandboxError``
    and writes no receipt. The compiler canary runs first; a failure
    there does not start the renderer. A program that renders and
    fails a check returns a receipt with ``passed`` false.
    ``reward_graded`` forces ``reject_nonfinite`` and
    ``require_reference`` on. With an impulse reference it raises
    ``ValueError`` when ``max_frames`` is below the 144000
    block-aligned cap, and it does not raise that cap. The exact
    signed comparison covers the whole render up to that cap,
    including samples past ``head_frames`` (spec §23 A4). Coarse
    magnitude checks are recorded and are not the reward pass. The
    head stays the only exact window when the run is not
    reward-graded. A suite stimulus below the 144000 floor raises
    ``ValueError`` as well and signs every rendered frame. A
    reward-graded compiler failure or worker crash is graded onto
    ``ledger`` (spec §23). With no ledger the call raises
    ``RewardUseRefused`` and does not score the outcome.
    ``defer_reward_failure`` returns a run with no signal receipt for
    a compiler exit 124, 125 or 126 and for a render crash, so
    ``commit_signal_check`` can grade it. A sandbox failure while
    compiling still requires ``ledger`` and is held immediately.
    Every signal render, diagnostic or reward-graded, refuses ``-fm``
    and a ``-ftz`` other than 0 before compile. The pinned flags are
    ``-ftz 0``, so the same source has one compiler digest on both
    paths. Those flags are not part of ``profile_digest``.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    profile, reference = _prepare_render(
        profile, reference, reward_graded=reward_graded
    )
    checked = _pin_compile_flags(options, pin=True)
    if source_needs_libraries(source):
        raise SignalLibrariesUnavailable(
            "pinned faustlibraries are not staged; T03b owns that tree, "
            "and this harness does not render library imports"
        )
    if "-double" in checked:
        raise SignalHarnessError(
            "signal render uses the float32 offline processor; -double is not supported"
        )
    bounds = limits if limits is not None else _limits_for(profile)
    started = time.monotonic()
    try:
        compiled = compile_source(source, lang="wasm", options=checked, limits=bounds)
    except SandboxError:
        if reward_graded:
            _hold_crash_for_reward(
                "sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest(),
                ledger,
                kind="harness_crash",
            )
        raise
    if compiled.receipt["exit_code"] != 0 or compiled.receipt["diagnostic_class"] not in {
        "ok",
        "warning",
    }:
        if reward_graded and defer_reward_failure:
            return _deferred_reward_run(
                compiled, "compiler", source=source, options=checked, limits=bounds
            )
        if reward_graded:
            _hold_compiler_for_reward(compiled, ledger)
        raise SignalHarnessError(
            "signal tests require a successful wasm compile "
            f"({compiled.receipt['diagnostic_class']})"
        )
    try:
        rendered = _render(source, profile, options=checked, limits=bounds)
    except SandboxError:
        if reward_graded and defer_reward_failure:
            return _deferred_reward_run(
                compiled, "harness_crash", source=source, options=checked, limits=bounds
            )
        if reward_graded:
            _hold_crash_for_reward(
                compiled.reproducible_digest, ledger, kind="harness_crash"
            )
        raise
    except SignalHarnessError as exc:
        if reward_graded and defer_reward_failure:
            reported = exc.termination
            return _deferred_reward_run(
                compiled,
                "worker_crash",
                source=source,
                options=checked,
                limits=bounds,
                termination_signal=reported["termination_signal"],
                runtime_stack_overflow=reported["runtime_stack_overflow"],
                wasm_trap=reported["wasm_trap"],
            )
        if reward_graded:
            _hold_crash_for_reward(
                compiled.reproducible_digest, ledger, kind="worker_crash"
            )
        raise
    if rendered["libfaust_version"] != compiled.receipt["faust_version"]:
        raise SignalHarnessError("renderer libfaust version disagrees with the compiler receipt")
    wall_ms = int((time.monotonic() - started) * 1000)
    return _judge(
        source,
        profile,
        reference,
        compiled,
        rendered,
        promotion_candidate=promotion_candidate,
        cpu_duration_ms=wall_ms if promotion_candidate else None,
        reward_graded=reward_graded,
        compile_flags=checked,
    )


def run_signal_suite(
    source: str,
    reference_for: Callable[[SignalProfile], SignalReference | None],
    *,
    sample_rates: Sequence[int] = SAMPLE_RATES,
    block_size: int = DEFAULT_BLOCK_SIZE,
    seed: int = DEFAULT_SEED,
    frames: int = DEFAULT_FRAMES,
    options: Sequence[str] = (),
    limits: ResourceLimits | None = None,
    promotion_candidate: bool = False,
    reward_graded: bool = False,
    ledger: object | None = None,
    **profile_kwargs: Any,
) -> SignalSuite:
    """Run ``source`` at each sample rate. Default rates are 44.1 and 48 kHz.

    A default frame count that includes impulse is raised to the cap
    before ``reference_for`` runs, so the reference is built for the
    window that will actually be rendered. A reward-graded suite
    requires ``ledger``. Compiler exits 124, 125 and 126, and render
    crashes, stay on the returned runs so ``commit_signal_check``
    grades them onto that ledger. A sandbox failure during compile is
    held immediately.
    """
    if not sample_rates:
        raise ValueError("sample_rates must not be empty")
    if reward_graded and (
        ledger is None or not hasattr(ledger, "queue") or not hasattr(ledger, "rates")
    ):
        from faustcoder.reward.grader import RewardUseRefused

        raise RewardUseRefused(
            "reward-graded signal suites require a reward ledger; "
            "refusing to score or drop compile failures and crashes"
        )
    runs: list[SignalRun] = []
    for rate in sample_rates:
        profile = _default_impulse_frames(
            SignalProfile(
                sample_rate=rate,
                block_size=block_size,
                seed=seed,
                frames=frames,
                **profile_kwargs,
            )
        )
        runs.append(
            run_signal(
                source,
                profile,
                reference_for(profile),
                options=options,
                limits=limits,
                promotion_candidate=promotion_candidate,
                reward_graded=reward_graded,
                ledger=ledger,
                defer_reward_failure=reward_graded,
            )
        )
    return SignalSuite(runs=tuple(runs), ledger=ledger)


def commit_signal_check(
    store: ArtifactStore,
    suite: SignalSuite,
    *,
    state: CandidateState,
    created_at: str,
    producer: str = "faustcoder.signal",
    ledger: object | None = None,
    policy: str = "signal",
) -> SignalCommit:
    """Store each DSPTestReceipt and take the signal edge.

    The compiler receipt is stored first and is a parent. A reference
    document, when the run has one, is the other parent. A harness
    exception never reaches this function, so a failed sandbox does
    not move the candidate. A reward run with no signal receipt is a
    compiler failure or a render crash. Those are graded here onto
    ``ledger`` or the suite ledger. Exit 124, 125 and 126, and a
    deferred compiler failure, use the compiler envelope. They stay
    ungraded until triage. This function does not supply a rerun or a
    known-good fixture. A render crash uses a crash envelope. Its
    exception text is not a marker. Structured
    ``runtime_stack_overflow`` and ``wasm_trap`` on that crash stay
    ungraded too.
    """
    if state is not CandidateState.COMPILE_CHECKED:
        raise SignalHarnessError("signal check starts from COMPILE_CHECKED")
    if not suite.runs:
        raise SignalHarnessError("signal suite is empty")
    artifact_ids: list[str] = []
    for run in suite.runs:
        compiler_id = store_compiler_receipt(
            store, run.compilation.receipt, created_at=created_at, producer="faustcoder.compiler"
        )
        parents = [f"sha256:{compiler_id}"]
        if run.reference_payload is not None:
            reference_id = _store_payload(
                store,
                run.reference_payload,
                created_at=created_at,
                producer="faustcoder.signal.reference",
            )
            parents.append(f"sha256:{reference_id}")
        receipt = run.receipt
        if receipt is None:
            if run.reward_failure is None:
                raise SignalHarnessError("signal run has no receipt")
            artifact_ids.append(compiler_id)
            continue
        artifact_ids.append(
            store_signal_receipt(
                store,
                receipt,
                created_at=created_at,
                producer=producer,
                parents=parents,
            )
        )
    purposes = [
        "reward" if run.receipt is None else run.receipt.get("purpose") for run in suite.runs
    ]
    if any(purpose == "reward" for purpose in purposes):
        if any(purpose != "reward" for purpose in purposes):
            raise SignalHarnessError("a reward-graded suite cannot mix diagnostic receipts")
        from faustcoder.candidate_machine import CandidateEvent, next_state
        from faustcoder.reward.grader import (
            SourceAttributedFailure,
            Ungraded,
            grade_receipt,
        )
        from faustcoder.reward.ledger import ledger_for_store

        bound = ledger if ledger is not None else suite.ledger
        if bound is None or not hasattr(bound, "queue") or not hasattr(bound, "rates"):
            bound = ledger_for_store(store)
        outcomes_list: list[object] = []
        for run, artifact_id in zip(suite.runs, artifact_ids, strict=True):
            exit_code = run.compilation.receipt.get("exit_code")
            if exit_code in {124, 125, 126} or run.reward_failure == "compiler":
                compiler_id = store_compiler_receipt(
                    store,
                    run.compilation.receipt,
                    created_at=created_at,
                    producer="faustcoder.compiler",
                )
                outcomes_list.append(
                    grade_receipt(
                        store.get(compiler_id),
                        diagnostics=run.compilation.diagnostics,
                        policy=policy,
                        queue=bound.queue,
                        rates=bound.rates,
                    )
                )
                if run.receipt is None:
                    continue
            if run.receipt is None and run.reward_failure in {"worker_crash", "harness_crash"}:
                crash_payload: dict[str, Any] = {
                    "kind": run.reward_failure,
                    "exit_code": 126,
                    "diagnostic_class": "internal",
                    "reproducible_digest": run.compilation.reproducible_digest,
                }
                if run.termination_signal is not None:
                    crash_payload["termination_signal"] = run.termination_signal
                if run.runtime_stack_overflow:
                    crash_payload["runtime_stack_overflow"] = True
                if run.wasm_trap:
                    crash_payload["wasm_trap"] = run.wasm_trap
                outcomes_list.append(
                    grade_receipt(
                        build_envelope(
                            schema_version=SIGNAL_SCHEMA_VERSION,
                            created_at=created_at,
                            producer=producer,
                            parents=[f"sha256:{artifact_id}"],
                            payload=crash_payload,
                        ),
                        policy=policy,
                        queue=bound.queue,
                        rates=bound.rates,
                    )
                )
                continue
            outcomes_list.append(
                grade_receipt(
                    store.get(artifact_id),
                    policy=policy,
                    queue=bound.queue,
                    rates=bound.rates,
                )
            )
        outcomes = tuple(outcomes_list)
        if any(isinstance(item, Ungraded) for item in outcomes):
            # Dropped from reward. Do not take signal_failed: that would
            # score an ungraded receipt as a model failure (spec §23 A2).
            return SignalCommit(
                state=state,
                artifact_ids=tuple(artifact_ids),
                suite=suite,
                outcomes=outcomes,
            )
        if any(isinstance(item, SourceAttributedFailure) for item in outcomes):
            return SignalCommit(
                state=next_state(state, CandidateEvent.SIGNAL_FAILED, guard_passed=True),
                artifact_ids=tuple(artifact_ids),
                suite=suite,
                outcomes=outcomes,
            )
        rewardable = [item for item in outcomes if hasattr(item, "passed")]
        if not rewardable:
            raise SignalHarnessError("reward commit produced no signal receipt")
        chosen = next((item for item in rewardable if not item.passed), rewardable[0])
        return SignalCommit(
            state=apply_signal(state, chosen),
            artifact_ids=tuple(artifact_ids),
            suite=suite,
            outcomes=outcomes,
        )
    return SignalCommit(
        state=apply_diagnostic_signal(state, passed=suite.passed),
        artifact_ids=tuple(artifact_ids),
        suite=suite,
    )


def store_signal_receipt(
    store: ArtifactStore,
    receipt: Mapping[str, Any],
    *,
    created_at: str,
    producer: str = "faustcoder.signal",
    parents: Sequence[str] = (),
) -> str:
    """Validate ``receipt`` and store it. Return the artifact id.

    A second store of the same reproducible digest returns the first
    artifact id. ``cpu_duration_ms`` is not part of that digest.
    """
    if not isinstance(receipt, dict):
        raise SignalHarnessError("receipt must be a JSON object")
    validate(receipt, _SCHEMA)
    digest = reproducible_signal_digest(receipt)
    existing = lookup_signal_receipt(store, digest)
    if existing is not None:
        return str(existing["artifact_id"])
    envelope = build_envelope(
        schema_version=SIGNAL_SCHEMA_VERSION,
        created_at=created_at,
        producer=producer,
        parents=list(parents),
        payload=receipt,
    )
    artifact_id = store.put(envelope)
    path = _index_path(store, digest)
    path.parent.mkdir(mode=0o755, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        winner = lookup_signal_receipt(store, digest)
        if winner is None:
            raise SignalHarnessError("signal receipt index disappeared during store")
        return str(winner["artifact_id"])
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(artifact_id + "\n")
    return artifact_id


def lookup_signal_receipt(
    store: ArtifactStore, reproducible_digest: str
) -> dict[str, Any] | None:
    """Return the envelope stored for ``reproducible_digest``, or None."""
    path = _index_path(store, reproducible_digest)
    if path.is_symlink():
        raise SignalHarnessError("signal receipt index path is a symlink")
    if not path.is_file():
        return None
    artifact_id = path.read_text(encoding="ascii").strip()
    if re.fullmatch(r"[0-9a-f]{64}", artifact_id) is None:
        raise SignalHarnessError("signal receipt index does not hold an artifact id")
    envelope = store.get(artifact_id)
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise SignalHarnessError("stored signal receipt payload is not an object")
    if reproducible_signal_digest(payload) != _normalize_digest(reproducible_digest):
        raise SignalHarnessError("signal receipt index does not match the stored payload")
    return envelope


def compare_channels(
    candidate: Sequence[Sequence[float]],
    reference: Sequence[Sequence[float]],
    *,
    tolerance: float | None = None,
    atol: float | None = None,
    rtol: float = DEFAULT_RELATIVE_TOLERANCE,
) -> tuple[float, str | None]:
    """Compare ``candidate`` as a prefix of ``reference``.

    A sample passes when ``abs(cand - ref) <= atol + rtol * abs(ref)``.
    ``tolerance`` is the absolute term kept for callers that pass one
    number. A non-finite sample on either side fails the comparison
    and does not stop the scan of the finite samples. The returned
    peak is the largest finite absolute gap.
    """
    if atol is None:
        atol = DEFAULT_TOLERANCE if tolerance is None else tolerance
    elif tolerance is not None:
        raise SignalHarnessError("pass atol or tolerance, not both")
    if len(candidate) != len(reference):
        return 0.0, "channels"
    if not candidate:
        return 0.0, "channels"
    peak = 0.0
    nonfinite = False
    exceeded = False
    for cand_channel, ref_channel in zip(candidate, reference, strict=True):
        if len(ref_channel) < len(cand_channel):
            return peak, "reference_short"
        for cand_sample, ref_sample in zip(cand_channel, ref_channel, strict=False):
            if not math.isfinite(cand_sample) or not math.isfinite(ref_sample):
                nonfinite = True
                continue
            gap = abs(cand_sample - ref_sample)
            if gap > peak:
                peak = gap
            if gap > atol + rtol * abs(ref_sample):
                exceeded = True
    if nonfinite:
        return peak, "nonfinite"
    if exceeded:
        return peak, "reference"
    return peak, None


def _judge(
    source: str,
    profile: SignalProfile,
    reference: SignalReference | None,
    compiled: Compilation,
    rendered: Mapping[str, Any],
    *,
    promotion_candidate: bool,
    cpu_duration_ms: int | None,
    reward_graded: bool,
    compile_flags: Sequence[str] = (),
) -> SignalRun:
    outputs = int(rendered["outputs"])
    failures: list[str] = []
    if profile.expected_channels is not None and outputs != profile.expected_channels:
        failures.append("channels")
    renders: dict[str, Any] = {}
    ref_payload = reference_payload(reference) if reference is not None else None
    for name in sorted(profile.stimuli):
        channels = rendered["samples"][name]
        summary, stimulus_failures, peak_error = _measure_stimulus(
            name, channels, profile, reference, reward_graded=reward_graded
        )
        renders[name] = summary
        failures.extend(stimulus_failures)
        if peak_error is not None and math.isfinite(peak_error):
            summary["max_abs_error_nano"] = to_nano(peak_error)
    failures = sorted(set(failures))
    if reward_graded:
        comparison = "reward-graded-signed-full"
    elif _suite_profile(profile):
        comparison = "suite-signed"
    else:
        comparison = "head-exact+coarse"
    metrics: dict[str, Any] = {
        "comparison": comparison,
        "failures": failures,
        "frame_count": profile.frames,
        "head_frames": profile.head_frames,
        "input_channels": int(rendered["inputs"]),
        "output_channels": outputs,
        "press_buttons_first_block": profile.press_buttons_first_block,
        "quantization_nano": NANO,
        "renders": renders,
        "stimuli": sorted(profile.stimuli),
    }
    if reward_graded:
        metrics["signed_frames"] = profile.frames
    if promotion_candidate and cpu_duration_ms is not None:
        metrics["cpu_duration_ms"] = cpu_duration_ms
    stimulus_ms = rendered.get("stimulus_ms")
    if isinstance(stimulus_ms, dict):
        timing: dict[str, int] = {}
        for name, value in stimulus_ms.items():
            if isinstance(name, str) and isinstance(value, int) and not isinstance(value, bool):
                timing[name] = value
        if timing:
            metrics["render_ms"] = timing
    toolchain = _toolchain_metrics(rendered.get("toolchain"))
    if toolchain:
        metrics["toolchain"] = toolchain
    if profile.suite is not None:
        metrics["suite"] = profile.suite
    metrics["compile_flags"] = list(compile_flags)
    if _suite_profile(profile):
        from faustcoder.signal_suite import stimulus_record

        metrics.update(stimulus_record(profile))
    harness = _harness_preimage()
    metrics["unshare_path"] = harness["unshare_path"]
    metrics["unshare_sha256"] = harness["unshare_sha256"]
    thresholds: dict[str, Any] = {
        "absolute_tolerance_nano": to_nano(profile.absolute_tolerance),
        "clip_peak_nano": to_nano(profile.clip_peak),
        "head_frames": profile.head_frames,
        "relative_tolerance_nano": to_nano(profile.relative_tolerance),
        "silence_rms_nano": to_nano(profile.silence_rms),
        "tail_threshold_nano": to_nano(profile.tail_threshold),
    }
    if profile.expected_channels is not None:
        thresholds["expected_channels"] = profile.expected_channels
    if profile.reject_nonfinite:
        thresholds["max_inf_count"] = 0
        thresholds["max_nan_count"] = 0
    if profile.max_denormal_count is not None:
        thresholds["max_denormal_count"] = profile.max_denormal_count
    if profile.reject_silence:
        thresholds["reject_silence"] = True
    if profile.reject_dc:
        thresholds["reject_dc"] = True
    if profile.reject_clipping:
        thresholds["reject_clipping"] = True
    if profile.require_reference:
        thresholds["require_reference"] = True
    thresholds["reward_graded"] = bool(reward_graded)
    if profile.suite is not None:
        thresholds["reward_allowlisted"] = False
    receipt: dict[str, Any] = {
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "test_suite_digest": profile_digest(profile),
        "sample_rate": profile.sample_rate,
        "block_size": profile.block_size,
        "seed": profile.seed,
        "metrics": metrics,
        "thresholds": thresholds,
        "passed": not failures,
        "harness_digest": content_digest_for(harness),
        "renderer": "faustwasm",
        "purpose": "reward" if reward_graded else "diagnostic",
        "profile": profile_payload(profile),
    }
    if ref_payload is not None:
        receipt["reference_digest"] = content_digest_for(ref_payload)
    if compiled.receipt["source_sha256"] != receipt["source_sha256"]:
        raise SignalHarnessError("compiler receipt hashed a different source")
    validate(receipt, _SCHEMA)
    return SignalRun(
        compilation=compiled,
        receipt=receipt,
        reproducible_digest=reproducible_signal_digest(receipt),
        failures=tuple(failures),
        reference_payload=ref_payload,
    )


def _channels_are_dc(channels: Sequence[Sequence[float]], profile: SignalProfile) -> bool:
    """Return whether ``channels`` are a non-silent constant."""
    flat = [float(sample) for channel in channels for sample in channel]
    if not flat or any(not math.isfinite(sample) for sample in flat):
        return False
    rms = math.sqrt(math.fsum(sample * sample for sample in flat) / len(flat))
    if rms < profile.silence_rms:
        return False
    mean = math.fsum(flat) / len(flat)
    variance = math.fsum((sample - mean) ** 2 for sample in flat) / len(flat)
    return variance == 0.0


def _same_dc(
    candidate: Sequence[Sequence[float]],
    reference: Sequence[Sequence[float]],
    profile: SignalProfile,
) -> bool:
    """Return whether both sides are the same non-silent constant."""
    if not _channels_are_dc(candidate, profile) or not _channels_are_dc(reference, profile):
        return False
    cand_level = float(candidate[0][0])
    ref_level = float(reference[0][0])
    return cand_level == ref_level


def _measure_stimulus(
    name: str,
    channels: Sequence[Sequence[float]],
    profile: SignalProfile,
    reference: SignalReference | None,
    *,
    reward_graded: bool = False,
) -> tuple[dict[str, Any], list[str], float | None]:
    flat = [sample for channel in channels for sample in channel]
    nan_count = sum(1 for sample in flat if math.isnan(sample))
    inf_count = sum(1 for sample in flat if math.isinf(sample))
    denormal_count = sum(1 for sample in flat if _is_denormal(sample))
    finite = nan_count == 0 and inf_count == 0
    failures: list[str] = []
    if profile.reject_nonfinite and nan_count:
        failures.append(f"{name}:nan")
    if profile.reject_nonfinite and inf_count:
        failures.append(f"{name}:inf")
    if profile.max_denormal_count is not None and denormal_count > profile.max_denormal_count:
        failures.append(f"{name}:denormal")
    summary: dict[str, Any] = {
        "denormal_count": denormal_count,
        "finite": finite,
        "inf_count": inf_count,
        "nan_count": nan_count,
        "sample_sha256": _sample_digest(channels),
    }
    peak_error: float | None = None
    if finite and flat:
        rms = math.sqrt(math.fsum(sample * sample for sample in flat) / len(flat))
        peak = max(abs(sample) for sample in flat)
        mean = math.fsum(flat) / len(flat)
        variance = math.fsum((sample - mean) ** 2 for sample in flat) / len(flat)
        silence = rms < profile.silence_rms
        dc = (not silence) and variance == 0.0
        clipping = peak > profile.clip_peak
        summary.update(
            {
                "clipping": clipping,
                "dc": dc,
                "peak_nano": to_nano(peak),
                "rms_nano": to_nano(rms),
                "silence": silence,
                "spectral": _spectral(channels[0], profile.sample_rate),
            }
        )
        if profile.reject_silence and silence:
            failures.append(f"{name}:silence")
        if profile.reject_clipping and clipping:
            failures.append(f"{name}:clipping")
    else:
        dc = False
    if profile.reject_dc and dc and reference is None:
        failures.append(f"{name}:dc")
    if reference is None:
        if profile.require_reference:
            failures.append(f"{name}:reference_missing")
        return summary, failures, peak_error
    expected = reference.samples.get(name)
    if expected is None:
        if profile.require_reference:
            failures.append(f"{name}:reference_missing")
        return summary, failures, peak_error
    if len(channels) != len(expected):
        failures.append(f"{name}:channels")
        return summary, failures, peak_error
    if profile.reject_dc and dc and not _same_dc(channels, expected, profile):
        failures.append(f"{name}:dc")
    if not finite:
        failures.append(f"{name}:nonfinite")
        _note_impulse_tail(name, reference, profile, failures)
        _attach_diagnostics(name, channels, profile, summary)
        return summary, failures, peak_error
    quantized_candidate = _quantize_channels(channels)
    quantized_reference = _quantize_channels(expected)
    head = profile.head_frames
    if not isinstance(head, int):
        raise SignalHarnessError("head_frames was not resolved")
    # Reward grading signs the whole render, past head_frames included
    # (spec §23 A4). A suite profile signs every rendered frame. Other
    # runs keep the exact check on the head.
    compared = profile.frames if reward_graded or _suite_profile(profile) else head
    summary["compared_frames"] = compared
    peak_error, token = compare_channels(
        [channel[:compared] for channel in quantized_candidate],
        [channel[:compared] for channel in quantized_reference],
        atol=profile.absolute_tolerance,
        rtol=profile.relative_tolerance,
    )
    if token == "reference":
        failures.append(f"{name}:reference")
    elif token == "reference_short":
        failures.append(f"{name}:reference_short")
    elif token == "nonfinite":
        failures.append(f"{name}:nonfinite")
    elif token == "channels":
        failures.append(f"{name}:channels")
    # Reward runs record the magnitude check on the whole render and
    # do not fail on it. A suite has already signed every frame, so
    # the coarse window is the samples past that compare. Other runs
    # keep the magnitude check on the whole render.
    if _suite_profile(profile) and not reward_graded:
        coarse_candidate = [channel[compared:] for channel in quantized_candidate]
        coarse_reference = [channel[compared:] for channel in quantized_reference]
    else:
        coarse_candidate = quantized_candidate
        coarse_reference = quantized_reference
    rms_gap, band_gap, rms_fail, band_fail = _coarse_gaps(
        coarse_candidate, coarse_reference, profile
    )
    summary["coarse"] = {
        "band_max_abs_error_nano": to_nano(band_gap),
        "block_rms_max_abs_error_nano": to_nano(rms_gap),
    }
    if not reward_graded and rms_fail:
        failures.append(f"{name}:envelope")
    if not reward_graded and band_fail:
        failures.append(f"{name}:bands")
    _note_impulse_tail(name, reference, profile, failures)
    _attach_diagnostics(name, channels, profile, summary)
    return summary, failures, peak_error


def harness_digest() -> str:
    """Return the digest of the toolchain pins a receipt would store.

    This is the object ``_harness_preimage`` names: Faust, faustlibraries,
    faustwasm, Node, the libfaust-wasm bytes, the render worker, the
    netns canary and the ``unshare`` binary. A reward record compares a
    stored ``harness_digest`` with this value. A mismatch is a stale pin.
    """
    return content_digest_for(_harness_preimage())


def _harness_preimage() -> dict[str, Any]:
    """Return the object hashed into ``harness_digest``.

    ``unshare_path`` and ``unshare_sha256`` are the identity
    ``unshare_identity`` reports. A swapped wrapper changes the digest
    before the network canary runs. The canary itself is the module
    shared with the compiler.
    """
    pin = runtime_pin()
    unshare_path, unshare_sha256 = unshare_identity()
    worker = worker_directory()
    return {
        "comparison": "head-exact+coarse",
        "faust_version": pin.faust_version,
        "faustlibraries_version": pin.faustlibraries_version,
        "faustwasm": FAUSTWASM_VERSION,
        "metric_version": METRIC_VERSION,
        "netns_canary_sha256": _file_sha256(worker / "netns-canary.mjs"),
        "node": pin.node,
        "renderer": "faustwasm",
        "render_worker_sha256": _file_sha256(worker / "render.mjs"),
        "runtime_sha256": {
            "libfaust-wasm.data": pin.data_sha256,
            "libfaust-wasm.js": pin.js_sha256,
            "libfaust-wasm.wasm": pin.wasm_sha256,
        },
        "unshare_path": unshare_path,
        "unshare_sha256": unshare_sha256,
    }


def _default_impulse_frames(profile: SignalProfile) -> SignalProfile:
    """Raise a default impulse window to the cap.

    Sine-only and noise-only profiles keep ``DEFAULT_FRAMES``. An
    explicit length other than that default is left alone.
    """
    if "impulse" not in profile.stimuli or profile.frames != DEFAULT_FRAMES:
        return profile
    cap = profile.max_frames
    if not isinstance(cap, int) or cap == profile.frames:
        return profile
    return replace(profile, frames=cap)


def _pad_reference(reference: SignalReference, frames: int) -> SignalReference:
    """Extend every channel with silence so the render can cover it."""
    if frames < reference.frames:
        raise SignalHarnessError("candidate render is shorter than the reference")
    if frames == reference.frames:
        return reference
    extra = frames - reference.frames
    samples = {
        name: [tuple(channel) + (0.0,) * extra for channel in reference.samples[name]]
        for name in reference.stimuli
    }
    return SignalReference(
        sample_rate=reference.sample_rate,
        block_size=reference.block_size,
        frames=frames,
        seed=reference.seed,
        stimuli=reference.stimuli,
        channels=reference.channels,
        samples=samples,
    )


def _toolchain_metrics(raw: object) -> dict[str, Any] | None:
    """Return Node, V8 and faustwasm versions recorded by the worker.

    Per-run filesystem allow paths are not copied. The stable Node
    flags are the sandbox identity flags the worker actually saw.
    """
    if not isinstance(raw, dict):
        return None
    node = raw.get("node")
    v8 = raw.get("v8")
    faustwasm = raw.get("faustwasm")
    flags = raw.get("node_flags")
    if not all(isinstance(item, str) and item for item in (node, v8, faustwasm)):
        return None
    if not isinstance(flags, list) or not all(isinstance(item, str) for item in flags):
        return None
    return {
        "faustwasm": faustwasm,
        "node": node,
        "node_flags": list(flags),
        "v8": v8,
    }


def _suite_profile(profile: SignalProfile) -> bool:
    """Return whether ``profile`` uses the nonlinear suite or one of its stimuli."""
    return profile.suite is not None or any(name in SUITE_STIMULI for name in profile.stimuli)


def _require_suite_floor(profile: SignalProfile) -> None:
    """Refuse a suite render shorter than the 144000-frame floor.

    The block size has to divide 144000, so the floor is not rounded
    down. Legacy impulse, sine and noise profiles are unchanged.
    """
    if not _suite_profile(profile):
        return
    if profile.block_size < 1 or MAX_FRAMES % profile.block_size != 0:
        raise ValueError("suite block_size must divide the 144000 frame floor")
    cap = profile.max_frames
    if not isinstance(cap, int) or profile.frames < MAX_FRAMES or cap < MAX_FRAMES:
        raise ValueError(
            "suite stimulus requires frames and max_frames of at least "
            "the 144000 block-aligned floor"
        )


def _pin_compile_flags(options: Sequence[str], *, pin: bool) -> tuple[str, ...]:
    """Return compiler flags, pinning ``-ftz`` when ``pin`` is set.

    ``-fm`` is refused before ``_validate_options`` when flags are
    pinned, so a signal render never reaches the compiler with fast
    math. A ``-ftz`` other than 0 is the same refusal. Unpinned runs
    keep the compiler allowlist, which already rejects ``-fm``.
    Diagnostic and reward-graded renders both pin, so one source
    hashes one compiler digest.
    """
    if pin and not isinstance(options, (str, bytes)) and isinstance(options, Sequence):
        for item in options:
            if isinstance(item, str) and (item == "-fm" or item.startswith("-fm")):
                raise SignalHarnessError("-fm is banned for a signal render")
    checked = _validate_options(options)
    if not pin:
        return checked
    ftz_at = None
    for index, item in enumerate(checked):
        if item == "-ftz":
            ftz_at = index
            break
    if ftz_at is None:
        return checked + PINNED_COMPILE_FLAGS
    value = checked[ftz_at + 1]
    if value != PINNED_FTZ:
        raise SignalHarnessError(
            f"-ftz {value} differs from the pinned value {PINNED_FTZ}"
        )
    return checked


def _limits_for(profile: SignalProfile) -> ResourceLimits:
    """Return sandbox bounds that can hold this render.

    The default 8 MiB cap fits a legacy render. The eight-stimulus
    suite writes a float32 input and up to two output channels per
    stimulus, which is past that cap, so the suite gets a larger
    ceiling and a longer timeout. A caller-supplied limit is kept.
    """
    outputs = profile.expected_channels if profile.expected_channels is not None else 2
    if outputs < 1:
        outputs = 1
    needed = len(profile.stimuli) * profile.frames * 4 * (1 + outputs) + 1024 * 1024
    default = 8 * 1024 * 1024
    if needed <= default:
        return ResourceLimits()
    mebibyte = 1024 * 1024
    output = ((needed + mebibyte - 1) // mebibyte) * mebibyte
    if output < 16 * mebibyte:
        output = 16 * mebibyte
    return ResourceLimits(timeout_s=120.0, output_bytes=output)


def _attach_diagnostics(
    name: str,
    channels: Sequence[Sequence[float]],
    profile: SignalProfile,
    summary: dict[str, Any],
) -> None:
    """Record suite diagnostics on ``summary`` without touching failures."""
    if profile.suite is None or not summary.get("finite"):
        return
    if not channels or not channels[0]:
        return
    from faustcoder.signal_suite import stimulus_diagnostics

    summary["diagnostics"] = stimulus_diagnostics(name, channels[0], profile.sample_rate)


def _prepare_render(
    profile: SignalProfile,
    reference: SignalReference | None,
    *,
    reward_graded: bool,
) -> tuple[SignalProfile, SignalReference | None]:
    """Apply reward gates and choose the impulse render length.

    A reward-graded run always rejects non-finite samples and requires
    a reference. With an impulse reference, ``max_frames`` below the
    144000 block-aligned cap raises ``ValueError`` before render. The
    cap is not raised. ``head_frames`` stays the pinned profile value
    on a reward impulse, so the frozen digest does not move. The
    signed compare covers the whole render. A shorter impulse
    reference is silence-padded out to that render. A suite stimulus
    below the 144000 floor raises ``ValueError`` before that impulse
    check. The suite signs every frame.
    """
    _require_suite_floor(profile)
    if (
        reward_graded
        and reference is not None
        and "impulse" in reference.stimuli
        and not _suite_profile(profile)
    ):
        aligned = MAX_FRAMES - (MAX_FRAMES % profile.block_size)
        if profile.max_frames < aligned:
            raise ValueError(
                "reward_graded impulse reference requires max_frames "
                "of at least the 144000 block-aligned cap"
            )
    if reward_graded:
        profile = replace(profile, reject_nonfinite=True, require_reference=True)
    profile = _default_impulse_frames(profile)
    if reference is None:
        if _suite_profile(profile):
            profile = replace(profile, head_frames=profile.frames)
        return profile, None
    if profile.frames < reference.frames:
        profile = replace(profile, frames=reference.frames)
    _require_same_identity(profile, reference)
    if profile.frames > reference.frames:
        if profile.stimuli != ("impulse",):
            _require_same_setup(profile, reference)
        reference = _pad_reference(reference, profile.frames)
    return profile, reference


def _require_same_identity(profile: SignalProfile, reference: SignalReference) -> None:
    """Refuse a comparison whose reference was rendered under another setup.

    Frame count is checked by the caller. A longer impulse render may
    silence-pad a shorter reference after this check.
    """
    if reference.sample_rate != profile.sample_rate:
        raise SignalHarnessError("reference sample rate does not match the profile")
    if reference.block_size != profile.block_size:
        raise SignalHarnessError("reference block size does not match the profile")
    if reference.seed != profile.seed:
        raise SignalHarnessError("reference seed does not match the profile")
    if tuple(reference.stimuli) != tuple(profile.stimuli):
        raise SignalHarnessError("reference stimulus does not match the profile")


def _require_same_setup(profile: SignalProfile, reference: SignalReference) -> None:
    """Refuse a comparison whose reference does not match, including length."""
    _require_same_identity(profile, reference)
    if reference.frames != profile.frames:
        raise SignalHarnessError("reference frame count does not match the profile")


def _quantize_channels(channels: Sequence[Sequence[float]]) -> list[list[float]]:
    """Map finite samples onto the 1e-9 grid stored in the reference."""
    return [[to_nano(float(sample)) / NANO for sample in channel] for channel in channels]


def _note_impulse_tail(
    name: str,
    reference: SignalReference,
    profile: SignalProfile,
    failures: list[str],
) -> None:
    """Fail an impulse window that misses late energy in the reference.

    The scan covers every sample, not only the last block. A silent
    gap before a delay or echo still counts. Sine and noise are
    sustained, so they are not gated. Energy that is still hot at
    ``max_frames`` has been followed to the cap and is left to the
    coarse check.
    """
    if name != "impulse":
        return
    threshold = profile.tail_threshold
    last_hot = -1
    for channel in reference.samples[name]:
        for index, sample in enumerate(channel):
            if abs(float(sample)) >= threshold:
                last_hot = max(last_hot, index)
    if last_hot < 0:
        return
    if last_hot >= profile.frames:
        failures.append(f"{name}:reference_tail")
        return
    block = profile.block_size
    end_hot = False
    for channel in reference.samples[name]:
        tail = channel[-block:] if len(channel) >= block else channel
        if any(abs(float(sample)) >= threshold for sample in tail):
            end_hot = True
            break
    cap = profile.max_frames
    if end_hot and isinstance(cap, int) and profile.frames < cap:
        failures.append(f"{name}:reference_tail")


def _coarse_gaps(
    candidate: Sequence[Sequence[float]],
    reference: Sequence[Sequence[float]],
    profile: SignalProfile,
) -> tuple[float, float, bool, bool]:
    """Compare per-block RMS and per-window band energies.

    Returns the maximum RMS gap, the maximum band gap, and whether
    each exceeded ``atol + rtol * abs(reference)``.
    """
    atol = profile.absolute_tolerance
    rtol = profile.relative_tolerance
    block = profile.block_size
    rms_peak = 0.0
    band_peak = 0.0
    rms_fail = False
    band_fail = False
    for cand, ref in zip(candidate, reference, strict=True):
        count = min(len(cand), len(ref))
        for start in range(0, count, block):
            stop = min(start + block, count)
            cand_rms = _rms(cand[start:stop])
            ref_rms = _rms(ref[start:stop])
            gap = abs(cand_rms - ref_rms)
            if gap > rms_peak:
                rms_peak = gap
            if gap > atol + rtol * abs(ref_rms):
                rms_fail = True
        offset = 0
        while offset < count:
            window = _window_length(min(count - offset, 1024))
            if window < 64:
                break
            cand_bands = _spectral(cand[offset : offset + window], profile.sample_rate)["bands_nano"]
            ref_bands = _spectral(ref[offset : offset + window], profile.sample_rate)["bands_nano"]
            for cand_nano, ref_nano in zip(cand_bands, ref_bands, strict=True):
                gap = abs(cand_nano - ref_nano) / NANO
                if gap > band_peak:
                    band_peak = gap
                if gap > atol + rtol * (abs(ref_nano) / NANO):
                    band_fail = True
            offset += window
    return rms_peak, band_peak, rms_fail, band_fail


def _rms(samples: Sequence[float]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(math.fsum(sample * sample for sample in samples) / len(samples))


def _spectral(channel: Sequence[float], sample_rate: int) -> dict[str, Any]:
    window = _window_length(len(channel))
    if window < 64:
        return {"band_count": 0, "bands_nano": [], "centroid_millihz": 0, "window": window}
    spectrum = _fft([complex(sample, 0.0) for sample in channel[:window]])
    bins = window // 2
    magnitudes = [abs(spectrum[bin_index]) / window for bin_index in range(bins)]
    band_count = 16
    width = max(1, bins // band_count)
    bands: list[int] = []
    for band in range(band_count):
        start = band * width
        stop = bins if band == band_count - 1 else start + width
        chunk = magnitudes[start:stop]
        mean = math.fsum(chunk) / len(chunk) if chunk else 0.0
        bands.append(to_nano(mean))
    weight = math.fsum(magnitudes)
    if weight == 0.0:
        centroid = 0
    else:
        hz = (
            math.fsum(index * magnitudes[index] for index in range(bins))
            / weight
            * sample_rate
            / window
        )
        centroid = int(round(hz * 1000.0))
    return {
        "band_count": band_count,
        "bands_nano": bands,
        "centroid_millihz": centroid,
        "window": window,
    }


def _render_termination(run: object, body: Mapping[str, Any] | None) -> dict[str, Any]:
    """Structured fields for the render stage. The exception text stays separate."""
    from faustcoder.compiler import WASM_TRAP_KINDS

    reported: dict[str, Any] = {}
    returncode = getattr(run, "returncode", 0)
    if isinstance(returncode, int) and returncode < 0:
        number = -returncode
        if 1 <= number <= 64:
            reported["termination_signal"] = number
    if isinstance(body, Mapping):
        if body.get("runtime_stack_overflow") is True:
            reported["runtime_stack_overflow"] = True
        trap = body.get("wasm_trap")
        if isinstance(trap, str) and trap in WASM_TRAP_KINDS:
            reported["wasm_trap"] = trap
    return reported


def _render(
    source: str,
    profile: SignalProfile,
    *,
    options: tuple[str, ...],
    limits: ResourceLimits,
) -> dict[str, Any]:
    script = worker_directory() / "render.mjs"
    if not script.is_file():
        raise SandboxError(f"render worker is missing: {script}")
    mono = stimuli_for(profile)
    request = json.dumps(
        {
            "source": source,
            "options": list(options),
            "sample_rate": profile.sample_rate,
            "block_size": profile.block_size,
            "frames": profile.frames,
            "stimuli": list(profile.stimuli),
            "press_buttons_first_block": profile.press_buttons_first_block,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="faustcoder-signal-") as temporary:
        workdir = Path(temporary)
        _stage_runtime(workdir)
        inputs = workdir / "inputs"
        inputs.mkdir(mode=0o700)
        for name, samples in mono.items():
            (inputs / f"{name}.f32").write_bytes(_f32_bytes(samples))
        command = node_command(
            script,
            [str(workdir)],
            read_paths=[worker_directory(), workdir],
            write_paths=[workdir],
            # Literal: realpath(/proc/net) is the parent's namespace.
            literal_reads=("/proc/net/dev",),
        )
        run = run_in_sandbox(command, stdin=request, workdir=workdir, limits=limits)
        _raise_if_canary_failed(run)
        if run.stop_reason:
            raise SignalHarnessError(
                f"renderer stopped: {run.stop_reason}",
                termination=_render_termination(run, None),
            )
        result_path = workdir / "result.json"
        if run.returncode != 0 or not result_path.is_file():
            detail = run.stderr.decode("utf-8", errors="replace").strip()
            raise SignalHarnessError(
                detail or "renderer failed",
                termination=_render_termination(run, None),
            )
        try:
            body = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SignalHarnessError("renderer result is not JSON") from exc
        if not isinstance(body, dict) or body.get("faustwasm_version") != FAUSTWASM_VERSION:
            raise SignalHarnessError("renderer result failed the version check")
        if body.get("compile_ok") is not True:
            diagnostic = body.get("diagnostics")
            text = diagnostic if isinstance(diagnostic, str) else "render compile failed"
            raise SignalHarnessError(
                text.strip() or "render compile failed",
                termination=_render_termination(run, body),
            )
        samples = _read_outputs(workdir, body, profile)
        body["samples"] = samples
        return body


def _read_outputs(
    workdir: Path, body: Mapping[str, Any], profile: SignalProfile
) -> dict[str, tuple[tuple[float, ...], ...]]:
    outputs = body.get("outputs")
    frames = body.get("frames")
    names = body.get("stimuli")
    if not isinstance(outputs, int) or outputs < 1:
        raise SignalHarnessError("renderer reported no outputs")
    if frames != profile.frames or not isinstance(names, list):
        raise SignalHarnessError("renderer result does not match the profile")
    if sorted(names) != sorted(profile.stimuli):
        raise SignalHarnessError("renderer stimuli do not match the profile")
    decoded: dict[str, tuple[tuple[float, ...], ...]] = {}
    expected = outputs * profile.frames * 4
    for name in names:
        if not isinstance(name, str) or _STIMULUS_FILE.fullmatch(name) is None:
            raise SignalHarnessError("renderer returned an unexpected stimulus name")
        path = workdir / f"out-{name}.f32"
        if path.is_symlink() or not path.is_file():
            raise SignalHarnessError(f"missing render output for {name}")
        raw = path.read_bytes()
        if len(raw) != expected:
            raise SignalHarnessError(f"render output for {name} has the wrong size")
        values = _f32_list(raw)
        channels = tuple(
            tuple(values[index * profile.frames : (index + 1) * profile.frames])
            for index in range(outputs)
        )
        decoded[name] = channels
    return decoded


def _store_payload(
    store: ArtifactStore,
    payload: Mapping[str, Any],
    *,
    created_at: str,
    producer: str,
) -> str:
    """Store ``payload``. The first envelope for that payload wins."""
    if not isinstance(payload, dict):
        raise SignalHarnessError("reference payload must be an object")
    digest = digest_hex(payload)
    if store.exists(digest):
        existing = store.get(digest)
        if existing.get("payload") != payload:
            raise SignalHarnessError("stored reference does not match this payload")
        return digest
    envelope = build_envelope(
        schema_version=SIGNAL_SCHEMA_VERSION,
        created_at=created_at,
        producer=producer,
        parents=[],
        payload=payload,
    )
    return store.put(envelope)


def _index_path(store: ArtifactStore, digest: str) -> Path:
    hex_id = _normalize_digest(digest).removeprefix("sha256:")
    return store.root / "dsp-receipt-index" / hex_id


def _normalize_digest(value: str) -> str:
    text = value.strip()
    hex_id = text[7:] if text.startswith("sha256:") else text
    if re.fullmatch(r"[0-9a-f]{64}", hex_id) is None:
        raise SignalHarnessError("reproducible digest must be sha256 and 64 hex characters")
    return f"sha256:{hex_id}"


def _sample_digest(channels: Sequence[Sequence[float]]) -> str:
    """Hash the little-endian binary32 bytes of ``channels``.

    The digest is those bytes, in channel order, with nothing rewritten.
    ``-0.0`` and ``0.0`` differ. A NaN is not replaced by one canonical
    payload: quiet payloads that survive the float32 store stay distinct,
    so two NaN results with different payloads do not match. The signed
    compare still treats every NaN as non-finite. This hash is the golden
    identity, not the pass gate.
    """
    chunks = [_f32_bytes(channel) for channel in channels]
    return "sha256:" + hashlib.sha256(b"".join(chunks)).hexdigest()


def _f32_bytes(samples: Sequence[float]) -> bytes:
    packed = array.array("f", [float(sample) for sample in samples])
    if sys.byteorder != "little":
        packed.byteswap()
    return packed.tobytes()


def _f32_list(raw: bytes) -> list[float]:
    unpacked = array.array("f")
    unpacked.frombytes(raw)
    if sys.byteorder != "little":
        unpacked.byteswap()
    return [float(sample) for sample in unpacked]


def _is_denormal(sample: float) -> bool:
    if not math.isfinite(sample) or sample == 0.0:
        return False
    return abs(sample) < _FLOAT32_MIN_NORMAL


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise SignalHarnessError(f"missing harness file: {path.name}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _xorshift64(state: int) -> int:
    value = state & _MASK64
    value ^= (value << 13) & _MASK64
    value ^= value >> 7
    value ^= (value << 17) & _MASK64
    return value


def _sin_series(angle: float) -> float:
    turns = angle / _TWO_PI
    frac = turns - math.trunc(turns)
    if frac < 0.0:
        frac += 1.0
    reduced = frac * _TWO_PI
    if reduced > _PI:
        reduced -= _TWO_PI
    term = reduced
    total = reduced
    square = reduced * reduced
    sign = -1.0
    for n in range(1, 9):
        term = term * square / ((2 * n) * (2 * n + 1))
        total += sign * term
        sign = -sign
    return total


def _window_length(frames: int) -> int:
    window = 1024 if frames >= 1024 else frames
    power = 1
    while power * 2 <= window:
        power *= 2
    return power


def _fft(values: list[complex]) -> list[complex]:
    count = len(values)
    if count == 1:
        return values
    even = _fft(values[0::2])
    odd = _fft(values[1::2])
    half = count // 2
    output = [0j] * count
    for index in range(half):
        angle = -_TWO_PI * index / count
        twiddle = complex(math.cos(angle), math.sin(angle))
        mixed = twiddle * odd[index]
        output[index] = even[index] + mixed
        output[index + half] = even[index] - mixed
    return output

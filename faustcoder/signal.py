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
energies, with the same tolerance. The render follows an impulse
reference until its tail drops below ``tail_threshold``, and it stops
at ``max_frames`` (144000, three seconds at 48 kHz) when the tail is
still hot. A hot impulse tail shorter than that cap fails the
comparison. Sine and noise do not decay, so they are not tail-gated.

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
receipt. The candidate stays in ``COMPILE_CHECKED``. A rendered
program that fails a required check does write a receipt with
``passed`` false and moves to ``REJECTED``.
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from faustcoder.candidate_machine import CandidateState, apply_signal
from faustcoder.canonical import build_envelope, content_digest_for, digest_hex
from faustcoder.compiler import (
    FAUSTWASM_VERSION,
    Compilation,
    compile_source,
    runtime_pin,
    store_compiler_receipt,
    worker_directory,
)
from faustcoder.compiler import _stage_runtime, _validate_options
import faustcoder.sandbox as sandbox
from faustcoder.sandbox import ResourceLimits, SandboxError, node_command, run_in_sandbox
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
MAX_FRAMES = 144_000
STIMULI = ("impulse", "sine", "noise")
METRIC_VERSION = 2
SIGNAL_SCHEMA_VERSION = "0.3.2"
_SCHEMA = "dsp-test-receipt.schema.json"
_FLOAT32_MIN_NORMAL = 1.1754943508222875e-38
_PI = 3.141592653589793
_TWO_PI = 6.283185307179586
_MASK64 = (1 << 64) - 1
_LIBRARY_IMPORT = re.compile(
    r"""(?ix)\b(?:import|library|component)\s*\(\s*["'](?!https?://)"""
)
_STIMULUS_FILE = re.compile(r"^(impulse|sine|noise)$")


class SignalHarnessError(Exception):
    """The harness failed before it could judge the signal."""


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
            if name not in STIMULI:
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
            if name not in STIMULI:
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
    """One rate's compile, render and DSPTestReceipt."""

    compilation: Compilation
    receipt: dict[str, Any]
    reproducible_digest: str
    failures: tuple[str, ...]
    reference_payload: dict[str, Any] | None


@dataclass(frozen=True)
class SignalSuite:
    """Both sample rates, or the rates the caller asked for."""

    runs: tuple[SignalRun, ...]

    @property
    def passed(self) -> bool:
        return all(run.receipt["passed"] for run in self.runs)


@dataclass(frozen=True)
class SignalCommit:
    """Stored receipts and the candidate state after the signal edge."""

    state: CandidateState
    artifact_ids: tuple[str, ...]
    suite: SignalSuite


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
        else:
            built[name] = noise_samples(profile.frames, profile.seed, profile.noise_amplitude)
    return built


def source_needs_libraries(source: str) -> bool:
    """Return whether ``source`` imports a Faust library or component."""
    return _LIBRARY_IMPORT.search(source) is not None


def profile_payload(profile: SignalProfile) -> dict[str, Any]:
    """Return the canonical object hashed into ``test_suite_digest``."""
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
    """Return ``sha256:`` of the receipt without CPU wall time.

    ``cpu_duration_ms`` inside ``metrics`` is the only dropped field.
    It is present only for a promotion candidate.
    """
    body = {key: value for key, value in receipt.items()}
    metrics = body.get("metrics")
    if isinstance(metrics, dict) and "cpu_duration_ms" in metrics:
        metrics = {key: value for key, value in metrics.items() if key != "cpu_duration_ms"}
        body["metrics"] = metrics
    return content_digest_for(body)


def run_signal(
    source: str,
    profile: SignalProfile,
    reference: SignalReference | None = None,
    *,
    options: Sequence[str] = (),
    limits: ResourceLimits | None = None,
    promotion_candidate: bool = False,
) -> SignalRun:
    """Compile and render ``source``. Return a schema-valid receipt.

    Raises ``SignalLibrariesUnavailable`` when ``source`` imports a
    library. Raises ``SignalHarnessError`` when the sandbox or the
    worker fails. A program that renders and fails a check returns a
    receipt with ``passed`` false.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    if reference is not None:
        _require_same_setup(profile, reference)
    if source_needs_libraries(source):
        raise SignalLibrariesUnavailable(
            "pinned faustlibraries are not staged; T03b owns that tree, "
            "and this harness does not render library imports"
        )
    checked = _validate_options(options)
    if "-double" in checked:
        raise SignalHarnessError(
            "signal render uses the float32 offline processor; -double is not supported"
        )
    bounds = limits or ResourceLimits()
    started = time.monotonic()
    compiled = compile_source(source, lang="wasm", options=checked, limits=bounds)
    if compiled.receipt["exit_code"] != 0 or compiled.receipt["diagnostic_class"] not in {
        "ok",
        "warning",
    }:
        raise SignalHarnessError(
            "signal tests require a successful wasm compile "
            f"({compiled.receipt['diagnostic_class']})"
        )
    rendered = _render(source, profile, options=checked, limits=bounds)
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
    **profile_kwargs: Any,
) -> SignalSuite:
    """Run ``source`` at each sample rate. Default rates are 44.1 and 48 kHz."""
    if not sample_rates:
        raise ValueError("sample_rates must not be empty")
    runs: list[SignalRun] = []
    for rate in sample_rates:
        profile = SignalProfile(
            sample_rate=rate,
            block_size=block_size,
            seed=seed,
            frames=frames,
            **profile_kwargs,
        )
        runs.append(
            run_signal(
                source,
                profile,
                reference_for(profile),
                options=options,
                limits=limits,
                promotion_candidate=promotion_candidate,
            )
        )
    return SignalSuite(runs=tuple(runs))


def commit_signal_check(
    store: ArtifactStore,
    suite: SignalSuite,
    *,
    state: CandidateState,
    created_at: str,
    producer: str = "faustcoder.signal",
) -> SignalCommit:
    """Store each DSPTestReceipt and take the signal edge.

    The compiler receipt is stored first and is a parent. A reference
    document, when the run has one, is the other parent. A harness
    exception never reaches this function, so a failed sandbox does
    not move the candidate.
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
        artifact_ids.append(
            store_signal_receipt(
                store,
                run.receipt,
                created_at=created_at,
                producer=producer,
                parents=parents,
            )
        )
    return SignalCommit(
        state=apply_signal(state, passed=suite.passed),
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
            name, channels, profile, reference
        )
        renders[name] = summary
        failures.extend(stimulus_failures)
        if peak_error is not None and math.isfinite(peak_error):
            summary["max_abs_error_nano"] = to_nano(peak_error)
    failures = sorted(set(failures))
    metrics: dict[str, Any] = {
        "comparison": "head-exact+coarse",
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
    if promotion_candidate and cpu_duration_ms is not None:
        metrics["cpu_duration_ms"] = cpu_duration_ms
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
    pin = runtime_pin()
    harness = {
        "comparison": "head-exact+coarse",
        "faust_version": pin.faust_version,
        "faustlibraries_version": pin.faustlibraries_version,
        "faustwasm": FAUSTWASM_VERSION,
        "metric_version": METRIC_VERSION,
        "node": pin.node,
        "renderer": "faustwasm",
        "render_worker_sha256": _file_sha256(worker_directory() / "render.mjs"),
        "runtime_sha256": {
            "libfaust-wasm.data": pin.data_sha256,
            "libfaust-wasm.js": pin.js_sha256,
            "libfaust-wasm.wasm": pin.wasm_sha256,
        },
    }
    unshare_sha = _unshare_sha256()
    if unshare_sha is not None:
        harness["unshare_sha256"] = unshare_sha
    receipt: dict[str, Any] = {
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "test_suite_digest": content_digest_for(profile_payload(profile)),
        "sample_rate": profile.sample_rate,
        "block_size": profile.block_size,
        "seed": profile.seed,
        "metrics": metrics,
        "thresholds": thresholds,
        "passed": not failures,
        "harness_digest": content_digest_for(harness),
        "renderer": "faustwasm",
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


def _measure_stimulus(
    name: str,
    channels: Sequence[Sequence[float]],
    profile: SignalProfile,
    reference: SignalReference | None,
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
        if profile.reject_dc and dc:
            failures.append(f"{name}:dc")
        if profile.reject_clipping and clipping:
            failures.append(f"{name}:clipping")
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
    if not finite:
        failures.append(f"{name}:nonfinite")
        _note_impulse_tail(name, reference, profile, failures)
        return summary, failures, peak_error
    quantized_candidate = _quantize_channels(channels)
    quantized_reference = _quantize_channels(expected)
    head = profile.head_frames
    if not isinstance(head, int):
        raise SignalHarnessError("head_frames was not resolved")
    peak_error, token = compare_channels(
        [channel[:head] for channel in quantized_candidate],
        [channel[:head] for channel in quantized_reference],
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
    rms_gap, band_gap, rms_fail, band_fail = _coarse_gaps(
        quantized_candidate, quantized_reference, profile
    )
    summary["coarse"] = {
        "band_max_abs_error_nano": to_nano(band_gap),
        "block_rms_max_abs_error_nano": to_nano(rms_gap),
    }
    if rms_fail:
        failures.append(f"{name}:envelope")
    if band_fail:
        failures.append(f"{name}:bands")
    _note_impulse_tail(name, reference, profile, failures)
    return summary, failures, peak_error


def _require_same_setup(profile: SignalProfile, reference: SignalReference) -> None:
    """Refuse a comparison whose reference was rendered under another setup."""
    if reference.sample_rate != profile.sample_rate:
        raise SignalHarnessError("reference sample rate does not match the profile")
    if reference.block_size != profile.block_size:
        raise SignalHarnessError("reference block size does not match the profile")
    if reference.frames != profile.frames:
        raise SignalHarnessError("reference frame count does not match the profile")
    if reference.seed != profile.seed:
        raise SignalHarnessError("reference seed does not match the profile")
    if tuple(reference.stimuli) != tuple(profile.stimuli):
        raise SignalHarnessError("reference stimulus does not match the profile")


def _unshare_sha256() -> str | None:
    """Hash the unshare binary when T03b exports ``unshare_executable``.

    PR #40 owns that lookup and the wrapper check. This harness does not
    resolve ``unshare`` itself. The digest omits the hash until the
    function exists.
    """
    resolver = getattr(sandbox, "unshare_executable", None)
    if resolver is None:
        return None
    path = Path(resolver())
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _quantize_channels(channels: Sequence[Sequence[float]]) -> list[list[float]]:
    """Map finite samples onto the 1e-9 grid stored in the reference."""
    return [[to_nano(float(sample)) / NANO for sample in channel] for channel in channels]


def _note_impulse_tail(
    name: str,
    reference: SignalReference,
    profile: SignalProfile,
    failures: list[str],
) -> None:
    """Fail an impulse window that ends while the reference is still hot.

    Sine and noise are sustained, so they are not gated. A hot tail at
    ``max_frames`` has been followed to the cap and is left to the
    coarse check.
    """
    if name != "impulse":
        return
    block = profile.block_size
    threshold = profile.tail_threshold
    hot = False
    for channel in reference.samples[name]:
        tail = [float(sample) for sample in channel[-block:]]
        if any(abs(sample) >= threshold for sample in tail):
            hot = True
            break
    if not hot:
        return
    cap = profile.max_frames
    if isinstance(cap, int) and profile.frames >= cap:
        return
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
        )
        run = run_in_sandbox(command, stdin=request, workdir=workdir, limits=limits)
        if run.stop_reason:
            raise SignalHarnessError(f"renderer stopped: {run.stop_reason}")
        result_path = workdir / "result.json"
        if run.returncode != 0 or not result_path.is_file():
            detail = run.stderr.decode("utf-8", errors="replace").strip()
            raise SignalHarnessError(detail or "renderer failed")
        try:
            body = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SignalHarnessError("renderer result is not JSON") from exc
        if not isinstance(body, dict) or body.get("faustwasm_version") != FAUSTWASM_VERSION:
            raise SignalHarnessError("renderer result failed the version check")
        if body.get("compile_ok") is not True:
            diagnostic = body.get("diagnostics")
            text = diagnostic if isinstance(diagnostic, str) else "render compile failed"
            raise SignalHarnessError(text.strip() or "render compile failed")
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

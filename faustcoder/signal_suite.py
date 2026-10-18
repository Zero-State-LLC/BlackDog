"""Nonlinear stimulus suite (T04 follow-up, N6).

Eight float32 stimuli, each 144000 frames at 48 kHz. The pass gate is
the existing signed per-sample check. THD+N, SMPTE IMD and sweep
harmonic ratios are diagnostics. v0.2 does not reward this suite
(D5, 2026-10-17): ``REWARD_PROFILES`` has no entry for it, and a task
that needs it is tagged unrewardable until a review adds the digest.

The four-stimulus fallback drops the sweep, the twin tone, the second
noise level and the DC step. It is documented and it is not rewarded
either.

Stimulus samples use the same float32 rounding and Taylor sine as the
legacy builders, plus a range-reduced series for ``exp``. They do not
call libm ``sin`` or ``exp``, so the bytes stay fixed on IEEE-754
platforms. A cross-arch mismatch of those bytes, or of a wire render,
is ``infra_fault``. Tolerances are not widened here.
"""

from __future__ import annotations

import math
import platform
import time
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

from faustcoder.signal import (
    MAX_FRAMES,
    NONLINEAR_SUITE_FALLBACK_STIMULI,
    NONLINEAR_SUITE_FALLBACK_V1,
    NONLINEAR_SUITE_STIMULI,
    NONLINEAR_SUITE_V1,
    PINNED_COMPILE_FLAGS,
    SignalHarnessError,
    SignalProfile,
    SignalReference,
    _PI,
    _TWO_PI,
    _sin_series,
    f32,
    _f32_bytes,
    noise_samples,
    profile_digest,
    sine_samples,
    stimuli_for,
    to_nano,
)

# Pinned constants. The series below uses these decimals, not libm.
_LN2 = 0.6931471805599453
_LN10 = 2.302585092994046
_LN1000 = 6.907755278982137
_SUITE_RATE = 48000
_ESS_F1_HZ = 20.0
_ESS_SECONDS = 2.0
# 10 ms. A 0.5 s fade ate the sweep down to about 112 Hz–3.6 kHz.
_ESS_FADE_SECONDS = 0.01
_LN_ORDER = {
    2: 0.6931471805599453,
    3: 1.0986122886681098,
    4: 1.3862943611198906,
    5: 1.6094379124341003,
}
_DC_ONSET_AT_48K = 4800
_DC_HOLD_AT_48K = 48000
_DC_LEVEL = 0.25
_NOISE_M12_SEED = 1
_NOISE_M30_SEED = 2
_NOISE_FADE_FRAMES = 64
_NOISE_LEVEL = "rms"
_SINE_HZ = 997
_SMPTE_LOW_HZ = 60
_SMPTE_HIGH_HZ = 7000

UNREWARDABLE_REASONS = frozenset({"nonlinear", "time_variant"})
# Closed TaskSpec.effect enum. Only the first two are rewardable (D5).
REWARDABLE_EFFECTS = frozenset({"linear", "time_invariant"})
TASK_EFFECTS = REWARDABLE_EFFECTS | UNREWARDABLE_REASONS
CROSS_ARCH_PENDING_ARM = "pending-dgx-spark"
CROSS_ARCH_PENDING_X86 = "pending-x86"


def _exp_reduced(value: float) -> float:
    """Return a Taylor ``exp`` for a reduced argument."""
    term = 1.0
    total = 1.0
    for n in range(1, 24):
        term *= value / n
        total += term
    return total


def _exp(value: float) -> float:
    """Return a deterministic ``exp`` from a pinned ``ln(2)`` reduction."""
    if value == 0.0:
        return 1.0
    power = int(math.floor(value / _LN2 + 0.5))
    reduced = value - power * _LN2
    return math.ldexp(_exp_reduced(reduced), power)


def _dbfs(db: float) -> float:
    """Return the float32 amplitude for a dBFS peak, ``10**(db/20)``."""
    return f32(_exp(db / 20.0 * _LN10))


def _cos_series(angle: float) -> float:
    """Return ``cos(angle)`` from the shared sine series."""
    return _sin_series(angle + _PI / 2.0)


def _raised_cosine(unit: float) -> float:
    """Return a raised-cosine fade in ``[0, 1]``."""
    if unit <= 0.0:
        return 0.0
    if unit >= 1.0:
        return 1.0
    return 0.5 * (1.0 - _cos_series(_PI * unit))


def _ess_lengths(sample_rate: int) -> tuple[int, int]:
    sweep = int(round(_ESS_SECONDS * sample_rate))
    fade = int(round(_ESS_FADE_SECONDS * sample_rate))
    return sweep, fade


def _dc_span(frames: int, sample_rate: int) -> tuple[int, int]:
    onset = int(round(_DC_ONSET_AT_48K * sample_rate / _SUITE_RATE))
    hold = int(round(_DC_HOLD_AT_48K * sample_rate / _SUITE_RATE))
    if onset < 0:
        onset = 0
    end = onset + hold
    if end > frames:
        end = frames
    if onset > frames:
        onset = frames
    return onset, end


def _farina_phase(index: int, sample_rate: int, duration: float) -> float:
    """Return the analytic Farina phase at sample ``index``.

    ``φ(t) = 2π f1 L (exp(t/L) - 1)`` with ``L = T / ln(f2/f1)``.
    The sine series range-reduces this angle. It is not an Euler step.
    """
    ell = duration / _LN1000
    time = index / sample_rate
    return _TWO_PI * _ESS_F1_HZ * ell * (_exp(time / ell) - 1.0)


def _ess_frequency(time: float, duration: float) -> float:
    """Return the instantaneous frequency of the analytic sweep."""
    return _ESS_F1_HZ * _exp((time / duration) * _LN1000)


def _ess_passband(sample_rate: int) -> tuple[int, int, int, int]:
    """Return sweep length, fade length, and passband edges in millihertz.

    The passband is the unfaded part of the sweep. With a 10 ms fade
    at each end of the 2.0 s, 20 Hz–20 kHz sweep, that band is about
    21 Hz to 19.3 kHz. The faded ends are outside it.
    """
    sweep, fade = _ess_lengths(sample_rate)
    if fade < 1 or fade * 2 >= sweep:
        raise ValueError("ess fade does not fit the sweep")
    duration = sweep / sample_rate
    low = _ess_frequency(fade / sample_rate, duration)
    high = _ess_frequency((sweep - fade) / sample_rate, duration)
    return sweep, fade, int(round(low * 1000.0)), int(round(high * 1000.0))


def _ess_schedule(sample_rate: int) -> tuple[list[float], list[float], float, int]:
    """Return analytic phase, fade window, float32 amplitude and sweep length.

    The sweep runs from 20 Hz to 20 kHz in 2.0 s. A raised-cosine fade
    covers the first 10 ms and the last 10 ms, so the passband stays
    near the sweep ends. Phase is the Farina closed form.
    """
    sweep, fade, _low, _high = _ess_passband(sample_rate)
    duration = sweep / sample_rate
    amplitude = _dbfs(-6.0)
    phases: list[float] = []
    windows: list[float] = []
    for index in range(sweep):
        if index < fade:
            window = _raised_cosine(index / fade)
        elif index >= sweep - fade:
            remain = (sweep - 1 - index) / fade
            window = _raised_cosine(remain)
        else:
            window = 1.0
        phases.append(_farina_phase(index, sample_rate, duration))
        windows.append(window)
    return phases, windows, amplitude, sweep


def _sweep_forward(sample_rate: int) -> tuple[list[float], int]:
    """Return the fade-windowed sweep and its length."""
    phases, windows, amplitude, sweep = _ess_schedule(sample_rate)
    samples = [
        f32(_sin_series(phase) * amplitude * windows[index])
        for index, phase in enumerate(phases)
    ]
    return samples, sweep


def ess_samples(frames: int, sample_rate: int) -> list[float]:
    """Return the exponential sweep, then silence through ``frames``."""
    forward, sweep = _sweep_forward(sample_rate)
    if frames < sweep:
        raise ValueError("ess sweep does not fit in the render")
    return forward + [0.0] * (frames - sweep)


def ess_inverse_samples(sample_rate: int) -> list[float]:
    """Return the Farina inverse filter for the generated sweep.

    The inverse is the time-reversed sweep times ``(f2/f1)^(-t/T)``.
    Convolution with the sweep is a diagnostic. It is not a pass gate.
    """
    forward, sweep = _sweep_forward(sample_rate)
    duration = sweep / sample_rate
    inverse: list[float] = []
    for index, sample in enumerate(reversed(forward)):
        time = index / sample_rate
        envelope = _exp((-time / duration) * _LN1000)
        inverse.append(f32(sample * envelope))
    return inverse


def smpte_samples(frames: int, sample_rate: int) -> list[float]:
    """Return 60 Hz + 7 kHz at 4:1, scaled so the float32 peak is −1 dBFS."""
    low = sine_samples(frames, sample_rate, _SMPTE_LOW_HZ, 1.0)
    high = sine_samples(frames, sample_rate, _SMPTE_HIGH_HZ, 1.0)
    mixed = [f32(4.0 * low[index] + high[index]) for index in range(frames)]
    peak = max(abs(sample) for sample in mixed)
    if peak == 0.0:
        raise SignalHarnessError("smpte mix was silent")
    scale = _dbfs(-1.0) / peak
    return [f32(sample * scale) for sample in mixed]


def dc_step_samples(frames: int, sample_rate: int) -> list[float]:
    """Return silence, a 0.25 hold starting at frame 4800, then silence.

    At 48 kHz the hold is 48000 frames (1.0 s). The onset and the hold
    scale with the sample rate. The tail is the gate-release region.
    """
    onset, end = _dc_span(frames, sample_rate)
    level = f32(_DC_LEVEL)
    samples = [0.0] * frames
    for index in range(onset, end):
        samples[index] = level
    return samples


def _rms_noise(frames: int, seed: int, rms_db: float) -> list[float]:
    """Return seeded noise at an RMS target, with a silent first sample.

    The xorshift generator is uniform, so a dBFS figure on its raw
    range would be a peak. These suite levels are RMS. A one-block
    raised-cosine fade starts at 0, which removes the frame-0 step
    from whatever the generator's first draw was.
    """
    unit = noise_samples(frames, seed, 1.0)
    fade = min(_NOISE_FADE_FRAMES, frames)
    faded: list[float] = []
    for index, sample in enumerate(unit):
        if index < fade:
            faded.append(sample * _raised_cosine(index / fade))
        else:
            faded.append(sample)
    measured = _rms(faded)
    if measured == 0.0:
        raise SignalHarnessError("noise rms was zero")
    scale = _dbfs(rms_db) / measured
    return [f32(sample * scale) for sample in faded]


def suite_stimulus(name: str, frames: int, sample_rate: int) -> list[float]:
    """Return one suite stimulus. Legacy names are built by ``stimuli_for``."""
    if frames < 1:
        raise ValueError("frames must be positive")
    if name == "ess":
        return ess_samples(frames, sample_rate)
    if name == "sine_997_m1":
        return sine_samples(frames, sample_rate, _SINE_HZ, _dbfs(-1.0))
    if name == "sine_997_m20":
        return sine_samples(frames, sample_rate, _SINE_HZ, _dbfs(-20.0))
    if name == "smpte":
        return smpte_samples(frames, sample_rate)
    if name == "noise_m12":
        return _rms_noise(frames, _NOISE_M12_SEED, -12.0)
    if name == "noise_m30":
        return _rms_noise(frames, _NOISE_M30_SEED, -30.0)
    if name == "dc_step":
        return dc_step_samples(frames, sample_rate)
    raise ValueError(f"unknown suite stimulus: {name}")


def _noise_plan(name: str, seed: int, rms_db: int, frames: int) -> dict[str, Any]:
    """Return the noise plan, naming RMS and the resulting peak."""
    samples = _rms_noise(frames, seed, float(rms_db))
    peak = max((abs(sample) for sample in samples), default=0.0)
    return {
        "fade_in_frames": min(_NOISE_FADE_FRAMES, frames),
        "kind": "noise",
        "level": _NOISE_LEVEL,
        "name": name,
        "peak_nano": to_nano(peak),
        "rms_dbfs": rms_db,
        "rms_nano": to_nano(_rms(samples)),
        "seed": seed,
    }


def _plan_one(name: str, profile: SignalProfile) -> dict[str, Any]:
    """Return the integer description of one stimulus."""
    if name == "impulse":
        return {
            "amplitude_nano": to_nano(profile.impulse_amplitude),
            "kind": "impulse",
            "name": "impulse",
        }
    if name == "sine":
        return {
            "amplitude_nano": to_nano(profile.sine_amplitude),
            "hz": profile.sine_hz,
            "kind": "sine",
            "name": "sine",
        }
    if name == "noise":
        return {
            "amplitude_nano": to_nano(profile.noise_amplitude),
            "kind": "noise",
            "name": "noise",
            "seed": profile.seed,
        }
    if name == "ess":
        sweep, fade, low, high = _ess_passband(profile.sample_rate)
        return {
            "f1_hz": 20,
            "f2_hz": 20000,
            "fade_frames": fade,
            "kind": "ess",
            "name": "ess",
            "passband_millihz": [low, high],
            "peak_dbfs": -6,
            "phase": "farina",
            "sweep_frames": sweep,
        }
    if name == "sine_997_m1":
        return {"hz": _SINE_HZ, "kind": "sine", "name": name, "peak_dbfs": -1}
    if name == "sine_997_m20":
        return {"hz": _SINE_HZ, "kind": "sine", "name": name, "peak_dbfs": -20}
    if name == "smpte":
        return {
            "high_hz": _SMPTE_HIGH_HZ,
            "kind": "smpte",
            "low_hz": _SMPTE_LOW_HZ,
            "name": "smpte",
            "peak_dbfs": -1,
            "ratio_den": 1,
            "ratio_num": 4,
        }
    if name == "noise_m12":
        return _noise_plan(name, _NOISE_M12_SEED, -12, profile.frames)
    if name == "noise_m30":
        return _noise_plan(name, _NOISE_M30_SEED, -30, profile.frames)
    if name == "dc_step":
        onset, end = _dc_span(profile.frames, profile.sample_rate)
        return {
            "hold_frames": end - onset,
            "kind": "dc_step",
            "level_nano": to_nano(_DC_LEVEL),
            "name": "dc_step",
            "onset_frame": onset,
        }
    raise ValueError(f"unknown stimulus: {name}")


def stimulus_plan(profile: SignalProfile) -> list[dict[str, Any]]:
    """Return the per-stimulus plan stored on the receipt metrics."""
    return [_plan_one(name, profile) for name in profile.stimuli]


def nonlinear_suite_profile(*, fallback: bool = False) -> SignalProfile:
    """Return the 8-render suite, or the 4-render fallback.

    Both are 48 kHz, block 64, 144000 frames, and they sign every
    sample. Neither profile is rewardable in v0.2.
    """
    if fallback:
        return SignalProfile(
            sample_rate=_SUITE_RATE,
            block_size=64,
            seed=1,
            frames=MAX_FRAMES,
            max_frames=MAX_FRAMES,
            head_frames=MAX_FRAMES,
            stimuli=NONLINEAR_SUITE_FALLBACK_STIMULI,
            suite=NONLINEAR_SUITE_FALLBACK_V1,
        )
    return SignalProfile(
        sample_rate=_SUITE_RATE,
        block_size=64,
        seed=1,
        frames=MAX_FRAMES,
        max_frames=MAX_FRAMES,
        head_frames=MAX_FRAMES,
        stimuli=NONLINEAR_SUITE_STIMULI,
        suite=NONLINEAR_SUITE_V1,
    )


def stimulus_record(profile: SignalProfile) -> dict[str, Any]:
    """Return the suite stimulus plan and the raw float32 byte hash.

    This is not ``profile_digest``. The allowlist digest stays the
    version-2 profile payload. A change in these bytes is visible on
    the receipt metrics.
    """
    import hashlib

    mono = stimuli_for(profile)
    parts = [
        name.encode("utf-8") + b"\0" + _f32_bytes(mono[name]) for name in profile.stimuli
    ]
    return {
        "stimulus_plan": stimulus_plan(profile),
        "stimulus_sha256": "sha256:" + hashlib.sha256(b"".join(parts)).hexdigest(),
    }


def suite_test_digest(profile: SignalProfile | None = None, *, fallback: bool = False) -> str:
    """Return ``profile_digest`` for the suite.

    Compile flags are not in this digest. ``profile_digest`` is the
    only profile digest.
    """
    chosen = profile if profile is not None else nonlinear_suite_profile(fallback=fallback)
    return profile_digest(chosen)


def assert_reward_allowed(
    profile: SignalProfile, *, compile_flags: Sequence[str] = ()
) -> None:
    """Raise when ``profile`` is not a frozen reward profile.

    The nonlinear suite fails this check. A render may still write a
    diagnostic receipt. Reward is a separate decision. ``compile_flags``
    is accepted and ignored: flags are not part of ``profile_digest``.
    """
    del compile_flags
    from faustcoder.reward.profiles import REWARD_PROFILES

    if profile_digest(profile) not in REWARD_PROFILES:
        raise SignalHarnessError("profile is not in the reward allowlist")


def tag_task_unrewardable(task: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    """Return a copy of ``task`` marked unrewardable.

    ``reason`` is ``nonlinear`` or ``time_variant``. It is written to
    the required TaskSpec ``effect`` field. ``rewardable`` is a bool on
    ``test_profile``. v0.2 does not reward those tasks (D5).
    """
    if reason not in UNREWARDABLE_REASONS:
        raise ValueError("unrewardable reason must be nonlinear or time_variant")
    profile = task.get("test_profile") if isinstance(task, Mapping) else None
    if not isinstance(profile, Mapping):
        raise ValueError("task test_profile must be an object")
    updated = dict(task)
    marked = dict(profile)
    marked["rewardable"] = False
    marked["unrewardable_reason"] = reason
    updated["effect"] = reason
    updated["test_profile"] = marked
    return updated


def _test_profile(task: Mapping[str, Any]) -> Mapping[str, Any]:
    profile = task.get("test_profile") if isinstance(task, Mapping) else None
    if not isinstance(profile, Mapping):
        raise ValueError("task test_profile must be an object")
    return profile


def _rewardable_bit(profile: Mapping[str, Any]) -> bool | None:
    """Return the rewardable bit, or None when the task leaves it unset.

    The string ``\"false\"`` is rejected. It is not a bool, and it must
    not be read as rewardable just because a non-empty string is true.
    """
    if "rewardable" not in profile:
        return None
    value = profile["rewardable"]
    if type(value) is not bool:
        raise ValueError("rewardable must be a bool")
    return value


def _closed_effect(value: object, *, field: str) -> str:
    """Return a TaskSpec effect, or raise when the value is not the enum.

    Missing, unknown and misspelled values are not coerced. ``Nonlinear``,
    ``non_linear``, ``time-variant`` and a tuple all fail here. They are
    not treated as linear.
    """
    if type(value) is not str or value not in TASK_EFFECTS:
        raise ValueError(
            f"{field} must be linear, time_invariant, nonlinear, or time_variant"
        )
    return value


def _task_effect(task: Mapping[str, Any]) -> str:
    """Return the required TaskSpec ``effect``."""
    if "effect" not in task:
        raise ValueError("effect is required")
    effect = _closed_effect(task["effect"], field="effect")
    profile = _test_profile(task)
    if "effect" in profile:
        inner = _closed_effect(profile["effect"], field="test_profile.effect")
        if inner in UNREWARDABLE_REASONS:
            return inner
    classes = profile.get("classes")
    if isinstance(classes, list):
        for item in classes:
            if item in UNREWARDABLE_REASONS:
                return str(item)
    return effect


def task_is_unrewardable(task: Mapping[str, Any]) -> bool:
    """Return whether a reward builder must drop ``task``.

    Only ``linear`` and ``time_invariant`` can be rewardable. ``nonlinear``
    and ``time_variant`` are unrewardable even when ``rewardable`` is true
    (D5). A missing or misspelled ``effect`` raises. An explicit
    ``rewardable`` false on a linear task needs a closed reason.
    """
    profile = _test_profile(task)
    bit = _rewardable_bit(profile)
    effect = _task_effect(task)
    if effect in UNREWARDABLE_REASONS:
        return True
    if bit is False:
        reason = profile.get("unrewardable_reason")
        if reason not in UNREWARDABLE_REASONS:
            raise ValueError("unrewardable task is missing a closed reason")
        return True
    return False


def require_task_rewardable(task: Mapping[str, Any]) -> None:
    """Refuse a reward-bearing row for ``task``.

    ``dataset_reward_row`` and ``rl_batch`` call this. A diagnostic
    render does not.
    """
    if task_is_unrewardable(task):
        raise SignalHarnessError("task is unrewardable")


def assert_task_reward_allowed(task: Mapping[str, Any]) -> None:
    """Raise when ``task`` is not rewardable."""
    require_task_rewardable(task)


def _tone_basis(sample_rate: int, freq_hz: float, count: int) -> list[tuple[float, float]]:
    """Return ``(sin, cos)`` at ``freq_hz``, rebased every 256 samples.

    The step comes from the shared sine series. Between rebases the
    phasor rotates by that step. The sequence is deterministic and
    does not call libm.
    """
    step = _TWO_PI * freq_hz / sample_rate
    cos_step = _cos_series(step)
    sin_step = _sin_series(step)
    cos_value = 1.0
    sin_value = 0.0
    basis: list[tuple[float, float]] = []
    for index in range(count):
        if index % 256 == 0:
            angle = step * index
            sin_value = _sin_series(angle)
            cos_value = _cos_series(angle)
        basis.append((sin_value, cos_value))
        next_cos = cos_value * cos_step - sin_value * sin_step
        next_sin = sin_value * cos_step + cos_value * sin_step
        cos_value = next_cos
        sin_value = next_sin
    return basis


def _tone_energies(
    samples: Sequence[float], sample_rate: int, freq_hz: float
) -> tuple[float, float]:
    """Return fundamental energy and residual energy at ``freq_hz``."""
    basis = _tone_basis(sample_rate, freq_hz, len(samples))
    sin_acc = 0.0
    cos_acc = 0.0
    sin2 = 0.0
    cos2 = 0.0
    cross = 0.0
    for sample, (sn, cs) in zip(samples, basis, strict=True):
        sin_acc += sample * sn
        cos_acc += sample * cs
        sin2 += sn * sn
        cos2 += cs * cs
        cross += sn * cs
    det = sin2 * cos2 - cross * cross
    if det == 0.0:
        residual = math.fsum(sample * sample for sample in samples)
        return 0.0, residual
    amp_sin = (sin_acc * cos2 - cos_acc * cross) / det
    amp_cos = (cos_acc * sin2 - sin_acc * cross) / det
    fund = 0.0
    resid = 0.0
    for sample, (sn, cs) in zip(samples, basis, strict=True):
        recon = amp_sin * sn + amp_cos * cs
        err = sample - recon
        fund += recon * recon
        resid += err * err
    return fund, resid


def _ratio_nano(numer: float, denom: float) -> int | None:
    if denom <= 0.0 or not math.isfinite(numer) or not math.isfinite(denom):
        return None
    ratio = math.sqrt(numer / denom)
    if not math.isfinite(ratio):
        return None
    return to_nano(ratio)


def _thd_n(samples: Sequence[float], sample_rate: int, freq_hz: int) -> dict[str, Any]:
    fund, resid = _tone_energies(samples, sample_rate, freq_hz)
    return {
        "fundamental_hz": freq_hz,
        "kind": "thd_n",
        "thd_n_nano": _ratio_nano(resid, fund),
    }


def _imd(samples: Sequence[float], sample_rate: int) -> dict[str, Any]:
    carrier, _resid = _tone_energies(samples, sample_rate, _SMPTE_HIGH_HZ)
    side = 0.0
    for multiple in (1, 2, 3):
        offset = multiple * _SMPTE_LOW_HZ
        for freq in (_SMPTE_HIGH_HZ - offset, _SMPTE_HIGH_HZ + offset):
            energy, _ignored = _tone_energies(samples, sample_rate, freq)
            side += energy
    return {
        "carrier_hz": _SMPTE_HIGH_HZ,
        "imd_nano": _ratio_nano(side, carrier),
        "kind": "imd_smpte",
        "modulator_hz": _SMPTE_LOW_HZ,
    }


def _conv_at(rendered: Sequence[float], inverse: Sequence[float], lag: int) -> float:
    """Return one sample of ``rendered`` convolved with ``inverse``."""
    inv_len = len(inverse)
    ren_len = len(rendered)
    start = max(0, lag - (inv_len - 1))
    stop = min(ren_len, lag + 1)
    acc = 0.0
    for index in range(start, stop):
        acc += rendered[index] * inverse[lag - index]
    return acc


def _ess_inverse(samples: Sequence[float], sample_rate: int) -> dict[str, Any]:
    """Log the Farina inverse-filter peaks. Not a pass threshold.

    The linear peak is the convolution at the end of the sweep. Higher
    harmonics land earlier by ``T ln(k) / ln(f2/f1)``. A few samples
    around each predicted lag are searched. The passband is the
    unfaded part of the sweep.
    """
    inverse = ess_inverse_samples(sample_rate)
    sweep, _fade, low, high = _ess_passband(sample_rate)
    linear_at = sweep - 1
    linear = 0.0
    for lag in range(linear_at - 4, linear_at + 1):
        value = abs(_conv_at(samples, inverse, lag))
        if value > linear:
            linear = value
    orders: list[dict[str, Any]] = []
    duration = sweep / sample_rate
    for order, ln_order in _LN_ORDER.items():
        shift = int(round(duration * ln_order / _LN1000 * sample_rate))
        center = linear_at - shift
        peak = 0.0
        for lag in range(center - 4, center + 5):
            value = abs(_conv_at(samples, inverse, lag))
            if value > peak:
                peak = value
        orders.append(
            {
                "order": order,
                "ratio_nano": _ratio_nano(peak * peak, linear * linear),
            }
        )
    return {
        "inverse_frames": len(inverse),
        "kind": "ess_inverse",
        "linear_peak_nano": to_nano(linear),
        "orders": orders,
        "passband_millihz": [low, high],
    }


def _rms(samples: Sequence[float]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(math.fsum(sample * sample for sample in samples) / len(samples))


def stimulus_diagnostics(
    name: str, samples: Sequence[float], sample_rate: int
) -> dict[str, Any]:
    """Return diagnostic numbers for one rendered stimulus.

    Callers log the dict. They do not read it when deciding ``passed``.
    """
    if name in {"sine_997_m1", "sine_997_m20"}:
        return _thd_n(samples, sample_rate, _SINE_HZ)
    if name == "sine":
        return _thd_n(samples, sample_rate, 440)
    if name == "smpte":
        return _imd(samples, sample_rate)
    if name == "ess":
        return _ess_inverse(samples, sample_rate)
    if name == "dc_step":
        onset, end = _dc_span(len(samples), sample_rate)
        hold = samples[onset:end]
        tail = samples[end:]
        hold_mean = math.fsum(hold) / len(hold) if hold else 0.0
        return {
            "hold_mean_nano": to_nano(hold_mean),
            "kind": "dc_step",
            "tail_rms_nano": to_nano(_rms(tail)),
        }
    if name in {"noise", "noise_m12", "noise_m30"}:
        rms = _rms(samples)
        peak = max((abs(sample) for sample in samples), default=0.0)
        crest = peak / rms if rms > 0.0 else 0.0
        return {"crest_nano": to_nano(crest), "kind": "noise"}
    peak = max((abs(sample) for sample in samples), default=0.0)
    return {"kind": "impulse", "peak_nano": to_nano(peak)}


def wire_reference(profile: SignalProfile) -> SignalReference:
    """Return a reference that copies each stimulus to one output channel."""
    mono = stimuli_for(profile)
    return SignalReference(
        sample_rate=profile.sample_rate,
        block_size=profile.block_size,
        frames=profile.frames,
        seed=profile.seed,
        stimuli=profile.stimuli,
        channels=1,
        samples={name: [samples] for name, samples in mono.items()},
    )


def signal_arch_body(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return the fields a cross-arch compare is allowed to read.

    ``harness_digest`` binds the local ``unshare`` binary. ``render_ms``,
    ``wall_ms`` and ``toolchain`` are timing and identity. A mismatch of
    the sample hashes is the fault. Versions are recorded beside the
    hashes and are not themselves the compare.
    """
    programs = document.get("programs")
    if isinstance(programs, dict):
        samples = {
            name: entry.get("sample_sha256")
            for name, entry in programs.items()
            if isinstance(entry, dict)
        }
    else:
        samples = document.get("stimuli", {})
    return {
        "compile_flags": list(document.get("compile_flags", [])),
        "programs": samples,
        "suite": document.get("suite"),
        "test_suite_digest": document.get("test_suite_digest"),
    }


def compare_arch_documents(left: Mapping[str, Any], right: Mapping[str, Any]) -> str:
    """Return ``match`` or ``infra_fault``.

    A mismatch is an infrastructure fault. This function does not
    change ``atol`` or ``rtol``.
    """
    if signal_arch_body(left) != signal_arch_body(right):
        return "infra_fault"
    return "match"


def cross_arch_status(machine: str, other: Mapping[str, Any] | None) -> str:
    """Return the cross-arch state when the other machine's document is absent."""
    if other is not None:
        return "ready"
    if machine in {"aarch64", "arm64"}:
        return CROSS_ARCH_PENDING_X86
    return CROSS_ARCH_PENDING_ARM


# Small DSP bank. No library imports. Goldens are the x86 sample hashes.
# The denormal pole is 0.999 so an impulse decays through the float32
# subnormal range inside the 144000-frame render.
DSP_BANK: Mapping[str, str] = MappingProxyType(
    {
        "biquad_cascade": """
conv3(k0,k1,k2,x) = k0*x + k1*x' + k2*x'';
conv2(k0,k1,x) = k0*x' + k1*x'';
tf2(b0,b1,b2,a1,a2) = sub ~ conv2(a1,a2) : conv3(b0,b1,b2)
with {
  sub(x,y) = x - y;
};
process = tf2(0.02, 0.04, 0.02, -1.4, 0.5)
        : tf2(0.03, 0.02, 0.03, -1.2, 0.4)
        : tf2(0.05, 0.0, 0.05, -1.1, 0.3);
""",
        "feedback_comb": "process = + ~ (@(480) : *(0.5));\n",
        "denormal_decay": "process = + ~ *(0.999);\n",
        "tanh_sin_shaper": """
tanh(x) = (exp(2.0 * x) - 1.0) / (exp(2.0 * x) + 1.0);
process = min(1.2, max(-1.2, _)) : tanh : sin;
""",
        "lfo_delay": """
inc = 6.283185307179586 * 0.5 / 48000.0;
phase = (+(inc)) ~ _;
lfo = 0.5 * (1.0 + sin(phase));
process = _ <: @(160) * lfo, @(288) * (1.0 - lfo) :> _;
""",
    }
)


def render_dsp_bank() -> dict[str, Any]:
    """Render the DSP bank through the suite and return sample digests.

    Compared fields are the suite digest, the pinned flags and each
    program's per-stimulus sample hashes. ``render_ms``, ``wall_ms``
    and ``toolchain`` are recorded and are not compared. ``wall_ms``
    for ``denormal_decay`` is the measurement against the 120 s cap.
    """
    from faustcoder.signal import run_signal

    profile = nonlinear_suite_profile()
    reference = wire_reference(profile)
    programs: dict[str, Any] = {}
    toolchain: dict[str, Any] | None = None
    for name, source in DSP_BANK.items():
        started = time.monotonic()
        run = run_signal(source, profile, reference, options=PINNED_COMPILE_FLAGS)
        wall_ms = int((time.monotonic() - started) * 1000)
        renders = run.receipt["metrics"]["renders"]
        programs[name] = {
            "render_ms": run.receipt["metrics"].get("render_ms", {}),
            "sample_sha256": {stim: renders[stim]["sample_sha256"] for stim in profile.stimuli},
            "wall_ms": wall_ms,
        }
        recorded = run.receipt["metrics"].get("toolchain")
        if isinstance(recorded, dict):
            toolchain = recorded
    return {
        "arch": platform.machine(),
        "compile_flags": list(PINNED_COMPILE_FLAGS),
        "programs": programs,
        "suite": profile.suite,
        "test_suite_digest": suite_test_digest(profile),
        "toolchain": toolchain or {},
    }


def render_arch_document() -> dict[str, Any]:
    """Render the DSP bank. This is the cross-arch document."""
    return render_dsp_bank()

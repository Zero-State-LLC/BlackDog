"""DSP signal harness: stimuli, receipts, fixtures, and the sandbox."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from faustcoder.candidate_machine import CandidateState
from faustcoder.signal import (
    DEFAULT_FRAMES,
    DEFAULT_TOLERANCE,
    SAMPLE_RATES,
    SignalHarnessError,
    SignalLibrariesUnavailable,
    SignalProfile,
    SignalReference,
    SignalSuite,
    commit_signal_check,
    compare_channels,
    f32,
    impulse_samples,
    lookup_signal_receipt,
    noise_samples,
    reproducible_signal_digest,
    run_signal,
    run_signal_suite,
    sine_samples,
    source_needs_libraries,
    stimuli_for,
    to_nano,
)
from faustcoder.store import ArtifactStore

ROOT = Path(__file__).resolve().parents[1]
DSP = ROOT / "tests" / "fixtures" / "dsp"
SIGNAL = DSP / "signal"
CREATED = "2026-10-17T00:00:00Z"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _profile(rate: int = 48000, **kwargs: object) -> SignalProfile:
    base: dict[str, object] = {"sample_rate": rate, "frames": 256, "block_size": 64, "seed": 1}
    base.update(kwargs)
    return SignalProfile(**base)  # type: ignore[arg-type]


def _scale(samples: list[float], gain: float) -> list[float]:
    gain32 = f32(gain)
    return [f32(f32(sample) * gain32) for sample in samples]


def _delay(samples: list[float]) -> list[float]:
    return [0.0, *samples[:-1]]


def _pole(samples: list[float], coef: float = 0.5) -> list[float]:
    prev = 0.0
    coef32 = f32(coef)
    rendered: list[float] = []
    for sample in samples:
        prev = f32(f32(sample) + coef32 * prev)
        rendered.append(prev)
    return rendered


def _button(frames: int, block_size: int) -> list[float]:
    return [1.0 if index < block_size else 0.0 for index in range(frames)]


def _reference(profile: SignalProfile, transform) -> SignalReference:
    stimuli = stimuli_for(profile)
    return SignalReference(
        channels=1,
        frames=profile.frames,
        samples={name: [transform(samples)] for name, samples in stimuli.items()},
    )


def _run(source: str, profile: SignalProfile, reference: SignalReference | None = None, **kwargs):
    return run_signal(source, profile, reference, **kwargs)


def test_defaults_follow_the_rate_decision() -> None:
    assert SAMPLE_RATES == (44100, 48000)
    assert DEFAULT_FRAMES == 2048
    assert DEFAULT_TOLERANCE == 2e-6
    assert to_nano(DEFAULT_TOLERANCE) == 2000


def test_stimuli_are_deterministic_float32() -> None:
    impulse = impulse_samples(8, 1.0)
    assert impulse[0] == 1.0
    assert impulse[1:] == [0.0] * 7
    sine = sine_samples(64, 48000, 440, 0.5)
    assert sine[0] == 0.0
    assert sine == sine_samples(64, 48000, 440, 0.5)
    assert max(abs(sample) for sample in sine) <= 0.5
    first = noise_samples(32, 1)
    assert first == noise_samples(32, 1)
    assert first != noise_samples(32, 2)
    assert all(-1.0 <= sample < 1.0 for sample in first)


def test_sample_rate_is_closed() -> None:
    with pytest.raises(ValueError, match="44100 or 48000"):
        SignalProfile(sample_rate=22050)


def test_prefix_comparison_uses_absolute_tolerance() -> None:
    candidate = [[0.0, 1.0]]
    longer = [[0.0, 1.0, 0.5]]
    assert compare_channels(candidate, longer, tolerance=2e-6) == (0.0, None)
    short = [[0.0]]
    assert compare_channels(candidate, short, tolerance=2e-6)[1] == "reference_short"
    off = [[0.0, 1.0 + 1e-4]]
    error, token = compare_channels(candidate, off, tolerance=2e-6)
    assert token == "reference"
    assert error > 2e-6


def test_reproducible_digest_drops_cpu_only() -> None:
    receipt = {
        "source_sha256": "ab" * 32,
        "test_suite_digest": "sha256:" + "cd" * 32,
        "sample_rate": 48000,
        "block_size": 64,
        "seed": 1,
        "metrics": {"cpu_duration_ms": 3, "failures": []},
        "thresholds": {"absolute_tolerance_nano": 2000},
        "passed": True,
        "harness_digest": "sha256:" + "ef" * 32,
        "renderer": "faustwasm",
    }
    slower = {
        **receipt,
        "metrics": {"cpu_duration_ms": 90, "failures": []},
    }
    assert reproducible_signal_digest(receipt) == reproducible_signal_digest(slower)
    changed = {**receipt, "passed": False}
    assert reproducible_signal_digest(receipt) != reproducible_signal_digest(changed)


def test_library_import_is_refused_until_t03b() -> None:
    source = _read(SIGNAL / "needs_stdfaust.dsp")
    assert source_needs_libraries(source)
    with pytest.raises(SignalLibrariesUnavailable, match="T03b"):
        _run(source, _profile(), None)
    assert "Not from the Faust distribution" in source


def test_fixtures_are_not_eval_or_holdout_data() -> None:
    assert list((ROOT / "eval").rglob("*.dsp")) == []
    assert list(ROOT.rglob("holdout/**/*.dsp")) == []
    for path in SIGNAL.glob("*.dsp"):
        text = path.read_text(encoding="utf-8")
        assert "Not from the Faust distribution" in text
        assert "impulse-tests" not in text


@pytest.mark.parametrize("rate", SAMPLE_RATES)
def test_wire_matches_the_stimulus(rate: int) -> None:
    profile = _profile(rate)
    source = "process = _;\n"
    reference = _reference(profile, lambda samples: samples)
    first = _run(source, profile, reference)
    second = _run(source, profile, reference)
    assert first.receipt["passed"] is True
    assert first.failures == ()
    assert first.reproducible_digest == second.reproducible_digest
    assert "cpu_duration_ms" not in first.receipt["metrics"]
    for name in profile.stimuli:
        assert first.receipt["metrics"]["renders"][name]["max_abs_error_nano"] == 0


def test_gain_and_delay_and_button_match_closed_forms() -> None:
    profile = _profile()
    gain = _run(
        _read(DSP / "gain.dsp"),
        profile,
        _reference(profile, lambda samples: _scale(samples, 0.5)),
    )
    delay = _run(
        _read(SIGNAL / "delay.dsp"),
        profile,
        _reference(profile, _delay),
    )
    button = _run(
        _read(SIGNAL / "button.dsp"),
        profile,
        SignalReference(
            channels=1,
            frames=profile.frames,
            samples={
                name: [_button(profile.frames, profile.block_size)] for name in profile.stimuli
            },
        ),
    )
    assert gain.receipt["passed"] is True
    assert delay.receipt["passed"] is True
    assert button.receipt["passed"] is True
    assert gain.receipt["renderer"] == "faustwasm"
    assert gain.receipt["sample_rate"] == 48000


def test_legal_feedback_passes_at_both_rates_and_counts_denormals(store: ArtifactStore) -> None:
    source = _read(SIGNAL / "feedback.dsp")

    def reference_for(profile: SignalProfile) -> SignalReference:
        return _reference(profile, _pole)

    suite = run_signal_suite(
        source,
        reference_for,
        frames=256,
        block_size=64,
        seed=1,
        noise_amplitude=0.25,
    )
    assert suite.passed is True
    assert [run.receipt["sample_rate"] for run in suite.runs] == [44100, 48000]
    for run in suite.runs:
        impulse = run.receipt["metrics"]["renders"]["impulse"]
        assert impulse["denormal_count"] > 0
        assert "denormal" not in "".join(run.failures)
        assert run.receipt["passed"] is True
    committed = commit_signal_check(
        store, suite, state=CandidateState.COMPILE_CHECKED, created_at=CREATED
    )
    assert committed.state is CandidateState.SIGNAL_CHECKED
    assert len(committed.artifact_ids) == 2
    stored = store.get(committed.artifact_ids[0])
    assert stored["producer"] == "faustcoder.signal"
    assert stored["payload"]["passed"] is True
    assert len(stored["parents"]) == 2
    again = commit_signal_check(
        store, suite, state=CandidateState.COMPILE_CHECKED, created_at="2026-10-17T00:00:01Z"
    )
    assert again.artifact_ids == committed.artifact_ids
    found = lookup_signal_receipt(store, suite.runs[0].reproducible_digest)
    assert found is not None
    assert found["artifact_id"] == committed.artifact_ids[0]


def test_silence_dc_nan_inf_and_clip_fail() -> None:
    profile = _profile(require_reference=False)
    cases = {
        "silence.dsp": "silence",
        "dc.dsp": "dc",
        "nan.dsp": "nan",
        "inf.dsp": "inf",
        "clip.dsp": "clipping",
    }
    for name, token in cases.items():
        run = _run(_read(SIGNAL / name), profile, None)
        assert run.receipt["passed"] is False
        assert any(token in failure for failure in run.failures)


def test_constant_denormal_fails_only_when_the_profile_rejects_it() -> None:
    source = _read(SIGNAL / "denormal.dsp")
    reported = _run(
        source,
        _profile(require_reference=False, reject_silence=False, reject_dc=False),
        None,
    )
    assert reported.receipt["passed"] is True
    assert reported.receipt["metrics"]["renders"]["impulse"]["denormal_count"] > 0
    rejected = _run(
        source,
        _profile(
            require_reference=False,
            reject_silence=False,
            reject_dc=False,
            max_denormal_count=0,
        ),
        None,
    )
    assert rejected.receipt["passed"] is False
    assert any(failure.endswith(":denormal") for failure in rejected.failures)


def test_channel_mismatch_fails_and_is_stored_as_rejected(store: ArtifactStore) -> None:
    suite = run_signal_suite(
        _read(SIGNAL / "stereo.dsp"),
        lambda _profile: None,
        sample_rates=(48000,),
        frames=256,
        block_size=64,
        seed=1,
        expected_channels=1,
        require_reference=False,
    )
    assert suite.passed is False
    assert "channels" in suite.runs[0].failures
    committed = commit_signal_check(
        store, suite, state=CandidateState.COMPILE_CHECKED, created_at=CREATED
    )
    assert committed.state is CandidateState.REJECTED
    assert store.get(committed.artifact_ids[0])["payload"]["passed"] is False


def test_promotion_candidate_records_cpu_outside_the_digest() -> None:
    profile = _profile()
    reference = _reference(profile, lambda samples: samples)
    source = "process = _;\n"
    first = _run(source, profile, reference, promotion_candidate=True)
    second = _run(source, profile, reference, promotion_candidate=True)
    assert "cpu_duration_ms" in first.receipt["metrics"]
    assert first.reproducible_digest == second.reproducible_digest


def test_remote_import_does_not_render() -> None:
    with pytest.raises(SignalHarnessError, match="successful wasm compile"):
        _run(_read(DSP / "remote.dsp"), _profile(), None)


def test_commit_refuses_the_wrong_state(store: ArtifactStore) -> None:
    empty = SignalSuite(runs=())
    with pytest.raises(SignalHarnessError, match="COMPILE_CHECKED"):
        commit_signal_check(store, empty, state=CandidateState.DRAFT, created_at=CREATED)
    with pytest.raises(SignalHarnessError, match="empty"):
        commit_signal_check(
            store, empty, state=CandidateState.COMPILE_CHECKED, created_at=CREATED
        )


def test_signal_digest_covers_the_source_bytes() -> None:
    source = "process = _;\n"
    profile = _profile()
    run = _run(source, profile, _reference(profile, lambda samples: samples))
    assert run.receipt["source_sha256"] == hashlib.sha256(source.encode("utf-8")).hexdigest()
    assert run.receipt["reference_digest"].startswith("sha256:")
    assert run.receipt["harness_digest"].startswith("sha256:")
    assert run.receipt["test_suite_digest"].startswith("sha256:")

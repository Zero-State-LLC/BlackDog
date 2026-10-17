"""DSP signal harness: stimuli, receipts, fixtures, and the sandbox."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from faustcoder.candidate_machine import CandidateState
from faustcoder.signal import (
    DEFAULT_FRAMES,
    DEFAULT_RELATIVE_TOLERANCE,
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
        sample_rate=profile.sample_rate,
        block_size=profile.block_size,
        frames=profile.frames,
        seed=profile.seed,
        stimuli=profile.stimuli,
        channels=1,
        samples={name: [transform(samples)] for name, samples in stimuli.items()},
    )


def _echo(samples: list[float], delay: int, gain: float) -> list[float]:
    gain32 = f32(gain)
    rendered: list[float] = []
    for index, sample in enumerate(samples):
        delayed = samples[index - delay] if index >= delay else 0.0
        rendered.append(f32(f32(sample) + f32(delayed * gain32)))
    return rendered


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


def test_prefix_comparison_uses_absolute_and_relative_tolerance() -> None:
    candidate = [[0.0, 1.0]]
    longer = [[0.0, 1.0, 0.5]]
    assert compare_channels(candidate, longer, tolerance=2e-6) == (0.0, None)
    short = [[0.0]]
    assert compare_channels(candidate, short, tolerance=2e-6)[1] == "reference_short"
    off = [[0.0, 1.0 + 1e-4]]
    error, token = compare_channels(candidate, off, tolerance=2e-6)
    assert token == "reference"
    assert error > 2e-6
    loud = [[1.0 + 1e-5]]
    reference = [[1.0]]
    gap, loud_token = compare_channels(loud, reference, atol=2e-6, rtol=1e-5)
    assert loud_token is None
    assert gap > 2e-6
    quiet_gap, quiet_token = compare_channels([[1e-7]], [[0.0]], atol=2e-6, rtol=1e-5)
    assert quiet_token is None
    assert quiet_gap < 2e-6


def test_nonfinite_comparison_scans_past_the_first_bad_sample() -> None:
    candidate = [[float("nan"), 0.0, 5.0]]
    reference = [[0.0, 0.0, 0.0]]
    peak, token = compare_channels(candidate, reference, atol=2e-6, rtol=0.0)
    assert token == "nonfinite"
    assert peak == 5.0


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
        rendered = first.receipt["metrics"]["renders"][name]
        assert rendered["max_abs_error_nano"] == 0
        assert rendered["coarse"]["block_rms_max_abs_error_nano"] == 0
        assert rendered["coarse"]["band_max_abs_error_nano"] == 0
    assert first.receipt["thresholds"]["relative_tolerance_nano"] == to_nano(
        DEFAULT_RELATIVE_TOLERANCE
    )
    assert first.reference_payload is not None
    assert first.reference_payload["sample_rate"] == profile.sample_rate
    assert first.reference_payload["block_size"] == profile.block_size
    assert first.reference_payload["frames"] == profile.frames
    assert first.reference_payload["seed"] == profile.seed
    assert first.reference_payload["stimulus_names"] == list(profile.stimuli)


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
            sample_rate=profile.sample_rate,
            block_size=profile.block_size,
            frames=profile.frames,
            seed=profile.seed,
            stimuli=profile.stimuli,
            channels=1,
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


def test_long_delay_against_dry_fails() -> None:
    profile = _profile(frames=4096, stimuli=("impulse",))
    reference = _reference(profile, lambda samples: _echo(samples, 4000, 1.0))
    run = _run("process = _;\n", profile, reference)
    impulse = run.receipt["metrics"]["renders"]["impulse"]
    assert run.receipt["passed"] is False
    assert impulse["max_abs_error_nano"] == 0
    assert "impulse:envelope" in run.failures
    assert "impulse:bands" in run.failures


def test_half_second_echo_against_dry_fails() -> None:
    profile = _profile(frames=24128, stimuli=("impulse",))
    reference = _reference(profile, lambda samples: _echo(samples, 24000, 0.5))
    run = _run("process = _;\n", profile, reference)
    impulse = run.receipt["metrics"]["renders"]["impulse"]
    assert profile.frames / profile.sample_rate == pytest.approx(0.502666, rel=1e-3)
    assert run.receipt["passed"] is False
    assert impulse["max_abs_error_nano"] == 0
    assert "impulse:envelope" in run.failures
    assert "impulse:bands" in run.failures


def test_dc_after_3000_fails() -> None:
    profile = _profile(frames=4096, stimuli=("impulse",))
    reference = _reference(profile, lambda samples: samples)
    run = _run(_read(SIGNAL / "late_dc.dsp"), profile, reference)
    impulse = run.receipt["metrics"]["renders"]["impulse"]
    assert run.receipt["passed"] is False
    assert impulse["max_abs_error_nano"] == 0
    assert "impulse:envelope" in run.failures
    assert "impulse:bands" in run.failures


def test_hot_impulse_tail_fails_before_the_cap() -> None:
    profile = _profile(stimuli=("impulse",))
    reference = _reference(profile, lambda samples: _pole(samples, 0.999))
    run = _run("process = + ~ *(0.999);\n", profile, reference)
    assert run.receipt["passed"] is False
    assert run.receipt["metrics"]["renders"]["impulse"]["max_abs_error_nano"] == 0
    assert "impulse:reference" not in run.failures
    assert "impulse:reference_tail" in run.failures


def test_nonfinite_comparison_fails_with_the_count_flag_off() -> None:
    profile = _profile(
        stimuli=("impulse",),
        reject_nonfinite=False,
        reject_silence=False,
        reject_dc=False,
    )
    reference = _reference(profile, lambda samples: samples)
    source = "process = _ * 0 + sqrt(0 - (1 - 1')) + 0.3;\n"
    run = _run(source, profile, reference)
    assert run.receipt["passed"] is False
    assert any(failure.endswith(":nonfinite") for failure in run.failures)
    assert not any(failure.endswith(":nan") or failure.endswith(":inf") for failure in run.failures)
    assert run.receipt["metrics"]["renders"]["impulse"]["nan_count"] > 0


def test_nonfinite_reference_is_refused_at_load() -> None:
    profile = _profile(frames=64, block_size=64, stimuli=("impulse",))
    base = {
        "sample_rate": profile.sample_rate,
        "block_size": profile.block_size,
        "frames": profile.frames,
        "seed": profile.seed,
        "stimuli": profile.stimuli,
        "channels": 1,
    }
    with pytest.raises(SignalHarnessError, match="non-finite"):
        SignalReference(**base, samples={"impulse": [[float("nan")] * profile.frames]})
    with pytest.raises(SignalHarnessError, match="non-finite"):
        finite = [0.0] * profile.frames
        finite[-1] = float("inf")
        SignalReference(**base, samples={"impulse": [finite]})


def test_reference_identity_must_match() -> None:
    profile = _profile()
    good = _reference(profile, lambda samples: samples)
    mismatches = [
        ("sample rate", SignalReference(
            sample_rate=44100,
            block_size=good.block_size,
            frames=good.frames,
            seed=good.seed,
            stimuli=good.stimuli,
            channels=1,
            samples=good.samples,
        )),
        ("block size", SignalReference(
            sample_rate=good.sample_rate,
            block_size=32,
            frames=good.frames,
            seed=good.seed,
            stimuli=good.stimuli,
            channels=1,
            samples=good.samples,
        )),
        ("seed", SignalReference(
            sample_rate=good.sample_rate,
            block_size=good.block_size,
            frames=good.frames,
            seed=good.seed + 1,
            stimuli=good.stimuli,
            channels=1,
            samples=good.samples,
        )),
        ("stimulus", _reference(_profile(stimuli=("sine",)), lambda samples: samples)),
    ]
    short = _profile(frames=128)
    mismatches.append(("frame count", _reference(short, lambda samples: samples)))
    for label, reference in mismatches:
        with pytest.raises(SignalHarnessError, match=label):
            _run("process = _;\n", profile, reference)


def test_staged_inputs_count_toward_the_output_cap(tmp_path: Path) -> None:
    from faustcoder.sandbox import _produced_bytes

    staged = tmp_path / "inputs"
    staged.mkdir()
    (staged / "impulse.f32").write_bytes(b"\x00" * 4096)
    (tmp_path / "input.dsp").write_bytes(b"process = _;\n")
    assert _produced_bytes(tmp_path) == 4096


def test_render_canary_fails_closed_outside_the_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from faustcoder.compiler import _raise_if_canary_failed, worker_directory
    from faustcoder.sandbox import ResourceLimits, SandboxError, SandboxRun, node_command
    from faustcoder.signal import _render

    worker = worker_directory()
    command = node_command(
        worker / "render.mjs",
        [str(tmp_path)],
        read_paths=[worker],
        write_paths=[tmp_path],
        literal_reads=("/proc/net/dev",),
    )
    assert "--allow-fs-read=/proc/net/dev" in command
    assert "--allow-net" not in " ".join(command)
    completed = subprocess.run(
        command,
        input=b"",
        capture_output=True,
        timeout=5,
        env={"FAUSTCODER_SANDBOX": "1", "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert completed.returncode == 2
    assert b"sandbox_canary_failed:" in completed.stderr
    assert b"non-loopback" in completed.stderr
    observed = SandboxRun(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        stop_reason="",
        stdout_truncated=False,
        stderr_truncated=False,
    )
    monkeypatch.setattr("faustcoder.signal.run_in_sandbox", lambda *args, **kwargs: observed)
    with pytest.raises(SandboxError, match="network namespace canary failed"):
        _render(
            "process = _;\n",
            _profile(frames=64, block_size=64, stimuli=("impulse",)),
            options=(),
            limits=ResourceLimits(),
        )
    ordinary = SandboxRun(
        returncode=2,
        stdout=b"",
        stderr=b"request is not JSON\n",
        stop_reason="",
        stdout_truncated=False,
        stderr_truncated=False,
    )
    _raise_if_canary_failed(ordinary)


def test_unshare_identity_is_in_the_harness_digest() -> None:
    from faustcoder.canonical import content_digest_for
    from faustcoder.sandbox import unshare_identity
    from faustcoder.signal import _harness_preimage

    path, digest = unshare_identity()
    preimage = _harness_preimage()
    assert preimage["unshare_path"] == path
    assert preimage["unshare_sha256"] == digest
    assert len(digest) == 64
    swapped = dict(preimage)
    swapped["unshare_sha256"] = "0" * 64
    assert content_digest_for(preimage) != content_digest_for(swapped)
    moved = dict(preimage)
    moved["unshare_path"] = f"{path}-other"
    assert content_digest_for(preimage) != content_digest_for(moved)

"""Nonlinear suite: digests, the frame floor, flag pins, and signed compares."""

from __future__ import annotations

import json
import math
import platform
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from faustcoder.canonical import content_digest_for
from faustcoder.errors import SchemaValidationError
from faustcoder.schemas import validate
from faustcoder.compiler import compile_source
from faustcoder.signal import (
    KNOWN_STIMULI,
    MAX_FRAMES,
    NONLINEAR_SUITE_FALLBACK_STIMULI,
    NONLINEAR_SUITE_STIMULI,
    NONLINEAR_SUITE_V1,
    PINNED_COMPILE_FLAGS,
    SignalHarnessError,
    SignalProfile,
    SignalReference,
    _pin_compile_flags,
    _sample_digest,
    f32,
    profile_payload,
    reproducible_signal_digest,
    run_signal,
    stimuli_for,
)
from faustcoder.reward.profiles import REWARD_PROFILES
from faustcoder.signal_suite import (
    DSP_BANK,
    assert_reward_allowed,
    assert_task_reward_allowed,
    compare_arch_documents,
    cross_arch_status,
    nonlinear_suite_profile,
    render_dsp_bank,
    require_task_rewardable,
    stimulus_record,
    suite_test_digest,
    tag_task_unrewardable,
    task_is_unrewardable,
)

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tests" / "fixtures" / "valid" / "task-spec.json"
WORKER = ROOT / "faust" / "worker" / "render.mjs"
GOLDENS = ROOT / "tests" / "fixtures" / "signal" / "nonlinear-x86-goldens.json"


def _reference(profile: SignalProfile, transform) -> SignalReference:
    mono = stimuli_for(profile)
    return SignalReference(
        sample_rate=profile.sample_rate,
        block_size=profile.block_size,
        frames=profile.frames,
        seed=profile.seed,
        stimuli=profile.stimuli,
        channels=1,
        samples={name: [transform(samples)] for name, samples in mono.items()},
    )


def _integrate(samples: list[float]) -> list[float]:
    """Scaled running sum. An impulse becomes a constant 0.5."""
    acc = 0.0
    gain = f32(0.5)
    rendered: list[float] = []
    for sample in samples:
        acc = f32(acc + f32(gain * sample))
        rendered.append(acc)
    return rendered


def _clip(samples: list[float], limit: float) -> list[float]:
    level = f32(limit)
    return [f32(min(level, max(-level, sample))) for sample in samples]


def test_suite_stimuli_are_deterministic_and_block_aligned() -> None:
    profile = nonlinear_suite_profile()
    fallback = nonlinear_suite_profile(fallback=True)
    assert profile.stimuli == NONLINEAR_SUITE_STIMULI
    assert fallback.stimuli == NONLINEAR_SUITE_FALLBACK_STIMULI
    assert len(profile.stimuli) == 8
    assert len(fallback.stimuli) == 4
    first = stimuli_for(profile)
    second = stimuli_for(profile)
    assert first.keys() == second.keys()
    for name, samples in first.items():
        assert samples == second[name]
        assert len(samples) == MAX_FRAMES
        assert len(samples) % profile.block_size == 0
        assert len(samples) >= 144000
    dc = first["dc_step"]
    assert dc[4799] == 0.0
    assert dc[4800] == f32(0.25)
    assert dc[4800 + 48000 - 1] == f32(0.25)
    assert dc[4800 + 48000] == 0.0
    assert first["ess"][0] == 0.0
    assert first["ess"][96000] == 0.0
    assert max(abs(sample) for sample in first["ess"][24000:72000]) > 0.1
    plan = stimulus_record(profile)["stimulus_plan"]
    ess = next(item for item in plan if item["name"] == "ess")
    assert ess["phase"] == "farina"
    assert ess["fade_frames"] == 480
    low, high = ess["passband_millihz"]
    assert low > 20_000
    assert high < 20_000_000
    assert high - low > 15_000_000
    assert first["noise_m12"][0] == 0.0
    assert first["noise_m30"][0] == 0.0
    assert max(abs(sample) for sample in first["noise_m12"]) < 1.0
    assert first["noise_m12"] != first["noise_m30"]
    for item in plan:
        if item["kind"] == "noise":
            assert item["level"] == "rms"
            assert "peak_dbfs" not in item
            assert item["peak_nano"] < 1_000_000_000
    assert max(abs(sample) for sample in first["sine_997_m1"]) > max(
        abs(sample) for sample in first["sine_997_m20"]
    )


def test_suite_digest_stays_v2_and_flags_do_not_move_it() -> None:
    profile = nonlinear_suite_profile()
    payload = profile_payload(profile)
    assert payload == profile_payload(profile)
    assert payload["version"] == 2
    assert "compile_flags" not in payload
    assert "stimulus_sha256" not in payload
    record = stimulus_record(profile)
    assert record["stimulus_sha256"].startswith("sha256:")
    assert len(record["stimulus_plan"]) == 8
    assert suite_test_digest(profile) == content_digest_for(payload)
    fallback = suite_test_digest(fallback=True)
    assert fallback != suite_test_digest(profile)
    assert suite_test_digest(profile) not in REWARD_PROFILES
    assert fallback not in REWARD_PROFILES
    assert NONLINEAR_SUITE_V1 not in REWARD_PROFILES.values()
    assert set(REWARD_PROFILES.values()) == {"impulse-44100-v1", "impulse-48000-v1"}
    with pytest.raises(SignalHarnessError, match="reward allowlist"):
        assert_reward_allowed(profile, compile_flags=PINNED_COMPILE_FLAGS)


def test_reproducible_digest_drops_diagnostics_and_render_time() -> None:
    receipt = {
        "block_size": 64,
        "harness_digest": "sha256:" + "ef" * 32,
        "metrics": {
            "cpu_duration_ms": 3,
            "render_ms": {"impulse": 10},
            "toolchain": {"node": "v22.0.0", "v8": "12.0"},
            "renders": {
                "impulse": {"diagnostics": {"thd_n_nano": 1}, "rms_nano": 5},
            },
        },
        "passed": True,
        "renderer": "faustwasm",
        "sample_rate": 48000,
        "seed": 1,
        "source_sha256": "ab" * 32,
        "test_suite_digest": "sha256:" + "cd" * 32,
        "thresholds": {"absolute_tolerance_nano": 2000},
    }
    slower = {
        **receipt,
        "metrics": {
            "cpu_duration_ms": 90,
            "render_ms": {"impulse": 800},
            "toolchain": {"node": "v20.0.0", "v8": "11.0"},
            "renders": {
                "impulse": {"diagnostics": {"thd_n_nano": 999}, "rms_nano": 5},
            },
        },
    }
    assert reproducible_signal_digest(receipt) == reproducible_signal_digest(slower)
    changed = {
        **receipt,
        "metrics": {
            "renders": {"impulse": {"diagnostics": {"thd_n_nano": 1}, "rms_nano": 6}},
        },
    }
    assert reproducible_signal_digest(receipt) != reproducible_signal_digest(changed)


def test_suite_floor_refuses_a_short_render_before_compile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("compile started")

    monkeypatch.setattr("faustcoder.signal.compile_source", explode)
    monkeypatch.setattr("faustcoder.signal._render", explode)
    profile = SignalProfile(
        sample_rate=48000,
        frames=4096,
        max_frames=4096,
        stimuli=("ess",),
    )
    with pytest.raises(ValueError, match="144000"):
        run_signal("process = _;\n", profile, None, reward_graded=True)
    with pytest.raises(ValueError, match="144000"):
        SignalProfile(
            sample_rate=48000,
            frames=4096,
            max_frames=4096,
            head_frames=4096,
            stimuli=NONLINEAR_SUITE_STIMULI,
            suite=NONLINEAR_SUITE_V1,
        )


def test_fast_math_and_a_different_ftz_are_refused_before_compile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("compile started")

    monkeypatch.setattr("faustcoder.signal.compile_source", explode)
    monkeypatch.setattr("faustcoder.signal._render", explode)
    profile = nonlinear_suite_profile()
    with pytest.raises(SignalHarnessError, match="-fm"):
        run_signal(
            "process = _;\n",
            profile,
            None,
            options=("-fm", "def"),
            reward_graded=True,
        )
    with pytest.raises(SignalHarnessError, match="-ftz"):
        run_signal(
            "process = _;\n",
            profile,
            None,
            options=("-ftz", "2"),
            reward_graded=True,
        )
    with pytest.raises(SignalHarnessError, match="-fm"):
        run_signal(
            "process = _;\n",
            SignalProfile(sample_rate=48000, frames=256, stimuli=("sine",)),
            None,
            options=("-fm", "def"),
            reward_graded=False,
        )
    assert _pin_compile_flags((), pin=True) == PINNED_COMPILE_FLAGS
    assert _pin_compile_flags(("-ftz", "0"), pin=True) == ("-ftz", "0")
    with pytest.raises(ValueError, match="not allowed"):
        _pin_compile_flags(("-fm",), pin=False)


def test_diagnostic_and_reward_pin_the_same_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, ...]] = []

    def capture(*_args: object, **kwargs: object) -> None:
        options = kwargs.get("options", ())
        seen.append(tuple(options) if isinstance(options, tuple) else tuple(options))  # type: ignore[arg-type]
        raise SignalHarnessError("stopped after flags")

    monkeypatch.setattr("faustcoder.signal.compile_source", capture)
    profile = SignalProfile(sample_rate=48000, frames=256, stimuli=("sine",))
    for graded in (False, True):
        with pytest.raises(SignalHarnessError, match="stopped after flags"):
            run_signal("process = _;\n", profile, None, reward_graded=graded)
    assert seen == [PINNED_COMPILE_FLAGS, PINNED_COMPILE_FLAGS]


def test_pinned_flags_share_one_compiler_digest() -> None:
    source = "process = _;\n"
    pinned = compile_source(source, lang="wasm", options=PINNED_COMPILE_FLAGS)
    again = compile_source(source, lang="wasm", options=PINNED_COMPILE_FLAGS)
    bare = compile_source(source, lang="wasm", options=())
    assert pinned.reproducible_digest == again.reproducible_digest
    assert pinned.reproducible_digest != bare.reproducible_digest


def test_nonlinear_task_can_be_tagged_unrewardable() -> None:
    task = json.loads(TASK.read_text(encoding="utf-8"))
    assert_task_reward_allowed(task)
    require_task_rewardable(task)
    assert task_is_unrewardable(task) is False
    for reason in ("nonlinear", "time_variant"):
        tagged = tag_task_unrewardable(task, reason=reason)
        validate(tagged, "task-spec.schema.json")
        assert tagged["test_profile"]["rewardable"] is False
        assert type(tagged["test_profile"]["rewardable"]) is bool
        assert tagged["test_profile"]["unrewardable_reason"] == reason
        assert tagged["effect"] == reason
        assert task_is_unrewardable(tagged) is True
        with pytest.raises(SignalHarnessError, match="unrewardable"):
            require_task_rewardable(tagged)
        untagged = json.loads(TASK.read_text(encoding="utf-8"))
        untagged["test_profile"] = {"effect": reason}
        assert task_is_unrewardable(untagged) is True
        with pytest.raises(SignalHarnessError, match="unrewardable"):
            require_task_rewardable(untagged)
        via_class = json.loads(TASK.read_text(encoding="utf-8"))
        via_class["test_profile"] = {"classes": [reason]}
        assert task_is_unrewardable(via_class) is True
        via_tuple = json.loads(TASK.read_text(encoding="utf-8"))
        via_tuple["test_profile"] = {"classes": (reason,)}
        assert task_is_unrewardable(via_tuple) is True
        with pytest.raises(SignalHarnessError, match="unrewardable"):
            require_task_rewardable(via_tuple)
        opted_in = json.loads(TASK.read_text(encoding="utf-8"))
        opted_in["test_profile"] = {"effect": reason, "rewardable": True}
        with pytest.raises(SignalHarnessError, match="unrewardable"):
            require_task_rewardable(opted_in)
        lied = json.loads(TASK.read_text(encoding="utf-8"))
        lied["test_profile"] = {"effect": reason, "rewardable": "false"}
        with pytest.raises(ValueError, match="bool"):
            require_task_rewardable(lied)
    with pytest.raises(ValueError, match="nonlinear or time_variant"):
        tag_task_unrewardable(task, reason="loud")
    assert task["test_profile"] == {"classes": ["syntax"]}
    assert task["effect"] == "linear"


def test_effect_enum_rejects_missing_and_misspelled_values() -> None:
    base = json.loads(TASK.read_text(encoding="utf-8"))
    missing = dict(base)
    del missing["effect"]
    with pytest.raises(ValueError, match="effect is required"):
        require_task_rewardable(missing)
    with pytest.raises(SchemaValidationError):
        validate(missing, "task-spec.schema.json")
    for effect in ("Nonlinear", "non_linear", "time-variant", ("nonlinear",), ("time_variant",)):
        task = dict(base)
        task["effect"] = effect
        with pytest.raises(ValueError, match="effect must be"):
            require_task_rewardable(task)
        with pytest.raises(SchemaValidationError):
            validate(task, "task-spec.schema.json")
    for effect in ("linear", "time_invariant"):
        task = dict(base)
        task["effect"] = effect
        require_task_rewardable(task)
        validate(task, "task-spec.schema.json")
        assert task_is_unrewardable(task) is False


def test_sample_hash_keeps_distinct_nan_payloads() -> None:
    quiet = struct.unpack("<f", struct.pack("<I", 0x7FC00000))[0]
    other = struct.unpack("<f", struct.pack("<I", 0x7FC00001))[0]
    assert math.isnan(quiet) and math.isnan(other)
    assert _sample_digest([[quiet]]) != _sample_digest([[other]])
    assert _sample_digest([[0.0]]) != _sample_digest([[-0.0]])


def test_tanh_sin_shaper_contains_tanh() -> None:
    source = DSP_BANK["tanh_sin_shaper"]
    assert "tanh(x)" in source
    assert "exp(2.0 * x)" in source
    assert ": tanh : sin" in source


def test_worker_accepts_every_known_stimulus() -> None:
    text = WORKER.read_text(encoding="utf-8")
    for name in KNOWN_STIMULI:
        assert f'"{name}"' in text


def test_cross_arch_mismatch_is_infra_fault_and_x86_stays_pending() -> None:
    left = {
        "arch": "x86_64",
        "compile_flags": ["-ftz", "0"],
        "stimuli": {"impulse": "sha256:" + "11" * 32},
        "suite": NONLINEAR_SUITE_V1,
        "test_suite_digest": "sha256:" + "ab" * 32,
    }
    assert compare_arch_documents(left, dict(left)) == "match"
    drifted = {**left, "stimuli": {"impulse": "sha256:" + "22" * 32}}
    assert compare_arch_documents(left, drifted) == "infra_fault"
    assert cross_arch_status("x86_64", None) == "pending-dgx-spark"
    assert cross_arch_status("aarch64", None) == "pending-x86"
    if platform.machine() in {"x86_64", "AMD64"}:
        assert cross_arch_status(platform.machine(), None) == "pending-dgx-spark"


def test_cross_arch_script_does_not_widen_a_mismatch(tmp_path: Path) -> None:
    document = {
        "arch": "x86_64",
        "compile_flags": ["-ftz", "0"],
        "stimuli": {"impulse": "sha256:" + "11" * 32},
        "suite": NONLINEAR_SUITE_V1,
        "test_suite_digest": "sha256:" + "ab" * 32,
    }
    left = tmp_path / "x86.json"
    right = tmp_path / "arm.json"
    left.write_text(json.dumps(document), encoding="utf-8")
    right.write_text(json.dumps(document), encoding="utf-8")
    script = ROOT / "scripts" / "signal_cross_arch.py"
    matched = subprocess.run(
        [sys.executable, str(script), "--compare", str(left), str(right)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert matched.returncode == 0, matched.stderr
    assert "match" in matched.stdout
    right.write_text(
        json.dumps({**document, "test_suite_digest": "sha256:" + "ff" * 32}),
        encoding="utf-8",
    )
    failed = subprocess.run(
        [sys.executable, str(script), "--compare", str(left), str(right)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert failed.returncode == 2
    assert "infra_fault" in failed.stdout
    assert "2e-6" not in failed.stdout
    isolated = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "from pathlib import Path\n"
            f"script = Path({str(script)!r})\n"
            "root = script.resolve().parents[1]\n"
            "sys.path = [\n"
            "    item for item in sys.path\n"
            "    if item not in ('', str(root))\n"
            "    and Path(item).resolve() != root\n"
            "]\n"
            "def _finder_module(finder):\n"
            "    module = getattr(finder, '__module__', '')\n"
            "    if isinstance(module, str) and module:\n"
            "        return module\n"
            "    return type(finder).__module__\n"
            "sys.meta_path = [\n"
            "    finder for finder in sys.meta_path\n"
            "    if 'faustcoder' not in _finder_module(finder)\n"
            "]\n"
            "sys.path = [item for item in sys.path if 'faustcoder' not in item]\n"
            "for name in list(sys.modules):\n"
            "    if name == 'faustcoder' or name.startswith('faustcoder.'):\n"
            "        del sys.modules[name]\n"
            "try:\n"
            "    import faustcoder\n"
            "except ImportError:\n"
            "    pass\n"
            "else:\n"
            "    raise SystemExit('faustcoder was importable without the shim')\n"
            "sys.argv = ['signal_cross_arch.py', '--status']\n"
            "import runpy\n"
            "runpy.run_path(str(script), run_name='__main__')\n",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd="/tmp",
    )
    assert isolated.returncode == 0, isolated.stderr
    if platform.machine() in {"x86_64", "AMD64"}:
        assert "pending-dgx-spark" in isolated.stdout


def test_constant_output_fails_the_suite_on_sines_and_noise() -> None:
    profile = nonlinear_suite_profile()
    reference = _reference(profile, _integrate)
    run = run_signal("process = _*0 + 0.5;\n", profile, reference)
    assert run.receipt["passed"] is False
    assert run.receipt["metrics"]["comparison"] == "suite-signed"
    assert run.receipt["test_suite_digest"] == suite_test_digest(profile)
    assert run.receipt["thresholds"]["reward_allowlisted"] is False
    assert "impulse:reference" not in run.failures
    for name in ("sine_997_m1", "sine_997_m20", "noise_m12", "noise_m30"):
        assert f"{name}:reference" in run.failures


def test_level_dependent_tanh_fails_the_loud_sine() -> None:
    profile = nonlinear_suite_profile()
    reference = _reference(
        profile, lambda samples: [f32(math.tanh(4.0 * sample)) for sample in samples]
    )
    run = run_signal("process = *(4);\n", profile, reference)
    assert "sine_997_m1:reference" in run.failures
    loud = run.receipt["metrics"]["renders"]["sine_997_m1"]
    quiet = run.receipt["metrics"]["renders"]["sine_997_m20"]
    assert loud["max_abs_error_nano"] > quiet["max_abs_error_nano"]
    # The candidate is still a sine. Its THD+N is a log, not the gate.
    assert loud["diagnostics"]["kind"] == "thd_n"
    assert "thd" not in " ".join(run.failures)


def test_hard_clip_levels_fail_the_loud_sine_and_the_twin_tone() -> None:
    profile = nonlinear_suite_profile()
    reference = _reference(profile, lambda samples: _clip(samples, 0.5))
    run = run_signal("process = max(-0.6, min(0.6, _));\n", profile, reference)
    assert "sine_997_m1:reference" in run.failures
    assert "smpte:reference" in run.failures
    assert "sine_997_m20:reference" not in run.failures
    assert run.receipt["metrics"]["renders"]["smpte"]["diagnostics"]["kind"] == "imd_smpte"
    ess = run.receipt["metrics"]["renders"]["ess"]["diagnostics"]
    assert ess["kind"] == "ess_inverse"
    assert ess["inverse_frames"] == 96000
    assert ess["passband_millihz"][1] - ess["passband_millihz"][0] > 15_000_000


def test_dsp_bank_matches_committed_x86_goldens() -> None:
    if platform.machine() not in {"x86_64", "AMD64"}:
        pytest.skip("x86 goldens; ARM compare is pending on the DGX Spark")
    rendered = render_dsp_bank()
    golden = json.loads(GOLDENS.read_text(encoding="utf-8"))
    assert compare_arch_documents(rendered, golden) == "match"
    toolchain = rendered["toolchain"]
    assert toolchain["faustwasm"] == "0.19.0"
    assert toolchain["node"].startswith("v")
    assert toolchain["v8"]
    assert "--permission" in toolchain["node_flags"]
    assert any(flag.startswith("--stack-size=") for flag in toolchain["node_flags"])
    denormal = rendered["programs"]["denormal_decay"]
    render_sum = sum(denormal["render_ms"].values())
    assert render_sum < 60_000
    assert denormal["wall_ms"] < 120_000
    Path("/tmp/faustcoder-denormal-timing.json").write_text(
        json.dumps(
            {"render_ms": denormal["render_ms"], "render_sum_ms": render_sum, "wall_ms": denormal["wall_ms"]}
        ),
        encoding="utf-8",
    )

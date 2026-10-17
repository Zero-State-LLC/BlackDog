"""Compiler harness: receipts, diagnostics, and the sandbox."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

import pytest

from faustcoder import (
    COMPILER_SCHEMA_VERSION,
    EXCLUDED_TIMING_FIELDS,
    FAUSTWASM_VERSION,
    NODE_SANDBOX_FLAGS,
    UNGRADED_EXIT_FLOOR,
    ArtifactStore,
    NativeFaustUnavailable,
    ResourceLimits,
    classify_diagnostic,
    compile_source,
    cross_check_native,
    digest_hex,
    lookup_compiler_receipt,
    node_command,
    reproducible_receipt_digest,
    run_in_sandbox,
    runtime_pin,
    store_compiler_receipt,
    validate,
)
from faustcoder.canonical import canonical_bytes
from faustcoder.compiler import (
    FAUSTLIBRARIES_PIN_VERSION,
    canonical_output_bytes,
    environment_preimage,
    worker_directory,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "dsp"
_ESCAPE = Path("/tmp/faustcoder-t03-escape")


def _source(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _probe(mode: str, limits: ResourceLimits, workdir: Path) -> object:
    script = worker_directory() / "probe.mjs"
    command = node_command(
        script,
        [mode, str(workdir)],
        read_paths=[worker_directory(), workdir],
        write_paths=[workdir],
    )
    return run_in_sandbox(command, stdin=b"", workdir=workdir, limits=limits)


def test_timing_exclusion_is_duration_only() -> None:
    assert EXCLUDED_TIMING_FIELDS == ("duration_ms",)


def test_classify_known_compiler_text() -> None:
    assert classify_diagnostic("", compile_ok=True) == "ok"
    assert (
        classify_diagnostic("WARNING : shadowed pattern-matching rule: foo\n", compile_ok=True)
        == "warning"
    )
    assert (
        classify_diagnostic("input:1 : ERROR : syntax error, unexpected ENDDEF\n", compile_ok=False)
        == "parse_error"
    )
    assert (
        classify_diagnostic("ERROR : undefined symbol : not_a_real_identifier\n", compile_ok=False)
        == "unbound_symbol"
    )
    assert (
        classify_diagnostic("ERROR : too much arguments : 2, instead of : 1\n", compile_ok=False)
        == "arity_error"
    )
    shape = (
        "ERROR : sequential composition A:B\n"
        "The number of outputs [1] of A must be equal to the number of inputs [2] of B\n"
    )
    assert classify_diagnostic(shape, compile_ok=False) == "type_error"


def test_output_bundle_is_ordered_and_length_prefixed() -> None:
    blob = canonical_output_bytes([("output.wasm", b"ab"), ("output.json", b"z")])
    assert blob == b"output.json\n" + (1).to_bytes(8, "big") + b"z" + b"output.wasm\n" + (
        2
    ).to_bytes(8, "big") + b"ab"


def test_reproducible_digest_drops_duration_only() -> None:
    receipt = {
        "source_sha256": "ab" * 32,
        "faust_version": "2.90.0",
        "command": ["libfaust-wasm", f"--faustwasm={FAUSTWASM_VERSION}", "-lang", "wasm"],
        "exit_code": 0,
        "stdout_digest": "sha256:" + "cd" * 32,
        "stderr_digest": "sha256:" + "ef" * 32,
        "duration_ms": 12,
        "environment_digest": "sha256:" + "11" * 32,
        "compiler": "libfaust-wasm",
        "lang": "wasm",
        "options": [],
        "diagnostic_class": "ok",
    }
    slower = dict(receipt, duration_ms=99)
    failed = dict(receipt, exit_code=1)
    assert reproducible_receipt_digest(receipt) == reproducible_receipt_digest(slower)
    assert reproducible_receipt_digest(receipt) != reproducible_receipt_digest(failed)
    assert "duration_ms" not in {
        key: value
        for key, value in receipt.items()
        if key not in EXCLUDED_TIMING_FIELDS
    }
    assert digest_hex(receipt) != digest_hex(slower)


def test_path_options_are_rejected() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        compile_source("process = _;", options=["-I", "/tmp"])


def test_source_over_the_size_limit_is_a_resource_receipt() -> None:
    compiled = compile_source("process = _;\n", limits=ResourceLimits(source_bytes=4))
    assert compiled.receipt["exit_code"] == 125
    assert compiled.receipt["diagnostic_class"] == "resource_limit"
    assert compiled.diagnostics == "resource limit: source size\n"
    assert compiled.receipt["duration_ms"] == 0
    assert compiled.receipt["faust_version"] == "2.90.0"
    assert compiled.receipt["exit_code"] >= UNGRADED_EXIT_FLOOR
    assert compiled.receipt["stdout_digest"].endswith(hashlib.sha256(b"").hexdigest())


def test_node_command_does_not_grant_network_or_processes(tmp_path: Path) -> None:
    command = node_command(
        worker_directory() / "probe.mjs",
        ["network", str(tmp_path)],
        read_paths=[worker_directory()],
        write_paths=[tmp_path],
    )
    text = " ".join(command)
    assert "--permission" in command
    assert "--disallow-code-generation-from-strings" in command
    for flag in NODE_SANDBOX_FLAGS:
        assert flag in command
    assert "--allow-net" not in text
    assert "--allow-child-process" not in text
    assert "--allow-worker" not in text
    assert "--allow-addons" not in text
    assert "--allow-wasi" not in text


def test_gain_receipt_is_reproducible_and_stored(store: ArtifactStore) -> None:
    source = _source("gain.dsp")
    first = compile_source(source, lang="wasm")
    second = compile_source(source, lang="wasm")
    receipt = first.receipt
    validate(receipt, "compiler-receipt.schema.json")
    assert receipt["compiler"] == "libfaust-wasm"
    assert receipt["lang"] == "wasm"
    assert receipt["faust_version"] == "2.90.0"
    assert receipt["exit_code"] == 0
    assert receipt["diagnostic_class"] == "ok"
    assert receipt["options"] == []
    assert f"--faustwasm={FAUSTWASM_VERSION}" in receipt["command"]
    assert "--libfaust=2.90.0" in receipt["command"]
    assert receipt["source_sha256"] == hashlib.sha256(source.encode("utf-8")).hexdigest()
    assert first.diagnostics == ""
    assert "Aborted" not in first.diagnostics
    assert receipt["stderr_digest"] == "sha256:" + hashlib.sha256(b"").hexdigest()
    assert first.reproducible_digest == second.reproducible_digest
    assert receipt["stdout_digest"] == second.receipt["stdout_digest"]
    artifact_id = store_compiler_receipt(
        store, receipt, created_at="2026-10-17T00:00:00Z"
    )
    stored = store.get(artifact_id)
    assert stored["payload"] == receipt
    assert stored["schema_version"] == COMPILER_SCHEMA_VERSION
    tweaked = dict(receipt, duration_ms=receipt["duration_ms"] + 1)
    assert reproducible_receipt_digest(tweaked) == first.reproducible_digest
    assert digest_hex(tweaked) != digest_hex(receipt)
    again = store_compiler_receipt(store, tweaked, created_at="2026-10-17T00:00:01Z")
    assert again == artifact_id
    found = lookup_compiler_receipt(store, first.reproducible_digest)
    assert found is not None
    assert found["artifact_id"] == artifact_id
    assert found["payload"]["duration_ms"] == receipt["duration_ms"]
    assert store.list() == [artifact_id]


@pytest.mark.parametrize(
    ("name", "diagnostic_class", "snippet"),
    [
        ("syntax.dsp", "parse_error", "syntax error"),
        ("shape.dsp", "type_error", "number of outputs"),
        ("arity.dsp", "arity_error", "too much arguments"),
        ("unbound.dsp", "unbound_symbol", "undefined symbol"),
    ],
)
def test_known_bad_fixtures(name: str, diagnostic_class: str, snippet: str) -> None:
    compiled = compile_source(_source(name), lang="wasm")
    assert compiled.receipt["exit_code"] == 1
    assert compiled.receipt["diagnostic_class"] == diagnostic_class
    assert snippet in compiled.diagnostics.lower()
    assert compiled.receipt["stdout_digest"] == "sha256:" + hashlib.sha256(b"").hexdigest()
    assert "Aborted" not in compiled.diagnostics


def test_cpp_backend_is_absent_on_this_faustwasm_pin() -> None:
    compiled = compile_source(_source("gain.dsp"), lang="cpp")
    assert compiled.receipt["lang"] == "cpp"
    assert compiled.receipt["exit_code"] == 1
    assert compiled.receipt["diagnostic_class"] == "other"
    assert "CPP backend is not built" in compiled.diagnostics
    assert compiled.receipt["faust_version"] == "2.90.0"


def test_compiler_timeout_is_classified() -> None:
    compiled = compile_source(
        _source("gain.dsp"),
        limits=ResourceLimits(timeout_s=0.02),
    )
    assert compiled.receipt["diagnostic_class"] == "timeout"
    assert compiled.receipt["exit_code"] == 124
    assert compiled.diagnostics == "timeout: wall clock limit exceeded\n"


def test_network_is_blocked(tmp_path: Path) -> None:
    run = _probe("network", ResourceLimits(timeout_s=3), tmp_path)
    assert run.stop_reason == ""
    assert run.returncode == 0
    assert run.stdout == b"blocked\n"


def test_eval_is_blocked(tmp_path: Path) -> None:
    run = _probe("eval", ResourceLimits(timeout_s=3), tmp_path)
    assert run.returncode == 0
    assert run.stdout == b"eval-blocked\n"


def test_filesystem_escape_is_blocked(tmp_path: Path) -> None:
    _ESCAPE.unlink(missing_ok=True)
    try:
        run = _probe("escape", ResourceLimits(timeout_s=3), tmp_path)
        assert run.returncode == 0
        assert run.stdout == b"fs-blocked\n"
        assert not _ESCAPE.exists()
    finally:
        _ESCAPE.unlink(missing_ok=True)


def test_parent_proxy_environment_is_not_visible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("NODE_OPTIONS", "--allow-net")
    run = _probe("env", ResourceLimits(timeout_s=3), tmp_path)
    assert run.stdout == b"env-clean\n"
    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:9"


def test_memory_limit_kills_the_process(tmp_path: Path) -> None:
    run = _probe(
        "memory",
        ResourceLimits(timeout_s=5, memory_bytes=80 * 1024 * 1024),
        tmp_path,
    )
    assert run.stop_reason == "memory"


def test_output_limit_kills_the_process(tmp_path: Path) -> None:
    run = _probe(
        "output",
        ResourceLimits(timeout_s=5, output_bytes=16 * 1024),
        tmp_path,
    )
    assert run.stop_reason == "output"


def test_native_cross_check_matches_diagnostic_class() -> None:
    try:
        gain = cross_check_native(_source("gain.dsp"))
        syntax = cross_check_native(_source("syntax.dsp"))
    except NativeFaustUnavailable as exc:
        pytest.skip(str(exc))
    assert gain.diagnostic_class_matches
    assert gain.wasm.receipt["diagnostic_class"] == "ok"
    assert gain.native.receipt["compiler"] == "faust-cli"
    assert gain.native.receipt["faust_version"] == "2.88.0"
    assert gain.native.receipt["lang"] == "cpp"
    assert syntax.diagnostic_class_matches
    assert syntax.wasm.receipt["diagnostic_class"] == "parse_error"


def test_runtime_pin_records_bundle_bytes_and_library_drift() -> None:
    pin = runtime_pin()
    runtime = (
        worker_directory()
        / "node_modules"
        / "@grame"
        / "faustwasm"
        / "libfaust-wasm"
    )
    assert pin.faust_version == "2.90.0"
    assert pin.faustlibraries_version == "2.74.2"
    assert pin.faustlibraries_version != FAUSTLIBRARIES_PIN_VERSION
    assert pin.data_sha256 == hashlib.sha256(
        (runtime / "libfaust-wasm.data").read_bytes()
    ).hexdigest()
    assert pin.wasm_sha256 == hashlib.sha256(
        (runtime / "libfaust-wasm.wasm").read_bytes()
    ).hexdigest()
    assert pin.js_sha256 == hashlib.sha256(
        (runtime / "libfaust-wasm.js").read_bytes()
    ).hexdigest()
    preimage = environment_preimage(
        compiler="libfaust-wasm",
        faust_version=pin.faust_version,
        lang="wasm",
        options=(),
        pin=pin,
    )
    assert preimage["libfaust_wasm_data_sha256"] == pin.data_sha256
    assert preimage["runtime_sha256"]["libfaust-wasm.wasm"] == pin.wasm_sha256
    assert preimage["runtime_sha256"]["libfaust-wasm.data"] == pin.data_sha256
    assert preimage["user_map"] == "current"


def test_harness_failures_keep_the_success_environment() -> None:
    source = _source("gain.dsp")
    ok = compile_source(source, lang="wasm")
    timed = compile_source(source, limits=ResourceLimits(timeout_s=0.05))
    memory = compile_source(
        source,
        limits=ResourceLimits(timeout_s=15, memory_bytes=64 * 1024 * 1024, poll_interval_s=0.02),
    )
    output = compile_source(source, limits=ResourceLimits(timeout_s=15, output_bytes=1024))
    assert ok.receipt["faust_version"] == "2.90.0"
    assert ok.receipt["environment_digest"] == "sha256:" + hashlib.sha256(
        canonical_bytes(
            environment_preimage(
                compiler="libfaust-wasm",
                faust_version="2.90.0",
                lang="wasm",
                options=(),
                pin=runtime_pin(),
            )
        )
    ).hexdigest()
    cases = (
        (timed, 124, "timeout"),
        (memory, 125, "resource_limit"),
        (output, 125, "resource_limit"),
    )
    for compiled, exit_code, diagnostic_class in cases:
        assert compiled.receipt["exit_code"] == exit_code
        assert compiled.receipt["diagnostic_class"] == diagnostic_class
        assert compiled.receipt["faust_version"] == "2.90.0"
        assert "--libfaust=2.90.0" in compiled.receipt["command"]
        assert compiled.receipt["environment_digest"] == ok.receipt["environment_digest"]
        assert compiled.receipt["exit_code"] >= UNGRADED_EXIT_FLOOR


@pytest.mark.parametrize(
    "source",
    [
        _source("remote.dsp"),
        'process = library("https://example.invalid/x.lib");\n',
        "process = component('http://example.invalid/x.lib');\n",
    ],
)
def test_remote_url_imports_are_internal(source: str) -> None:
    compiled = compile_source(source, lang="wasm")
    assert compiled.receipt["exit_code"] == 126
    assert compiled.receipt["diagnostic_class"] == "internal"
    assert compiled.diagnostics == "internal: remote import rejected\n"
    assert compiled.receipt["faust_version"] == "2.90.0"
    assert compiled.receipt["duration_ms"] == 0


def test_deep_recursion_is_internal() -> None:
    compiled = compile_source(_source("recurse.dsp"), lang="wasm")
    assert compiled.receipt["exit_code"] == 126
    assert compiled.receipt["diagnostic_class"] == "internal"
    assert "maximum call stack size exceeded" in compiled.diagnostics.lower()
    assert compiled.receipt["faust_version"] == "2.90.0"


def test_sandbox_uid_is_unprivileged_and_offline(tmp_path: Path) -> None:
    script = worker_directory() / "probe.mjs"
    command = node_command(
        script,
        ["identity", str(tmp_path)],
        read_paths=[worker_directory(), tmp_path, Path("/proc")],
        write_paths=[tmp_path],
    )
    run = run_in_sandbox(command, stdin=b"", workdir=tmp_path, limits=ResourceLimits(timeout_s=3))
    assert run.returncode == 0, run.stderr
    lines = run.stdout.decode().splitlines()
    assert lines[0].startswith("uid ")
    uid = int(lines[0].split()[1])
    assert uid != 0
    assert lines[1].startswith("capeff ")
    assert int(lines[1].split()[1], 16) == 0
    assert lines[2] == "blocked"


def test_timeout_is_armed_before_stdin(tmp_path: Path) -> None:
    script = worker_directory() / "probe.mjs"
    command = node_command(
        script,
        ["hold", str(tmp_path)],
        read_paths=[worker_directory(), tmp_path],
        write_paths=[tmp_path],
    )
    started = time.monotonic()
    run = run_in_sandbox(
        command,
        stdin=b"x" * (256 * 1024),
        workdir=tmp_path,
        limits=ResourceLimits(timeout_s=0.4),
    )
    elapsed = time.monotonic() - started
    assert run.stop_reason == "timeout"
    assert elapsed < 3

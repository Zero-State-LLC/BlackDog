"""Compiler harness: receipts, diagnostics, and the sandbox."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import selectors
import shutil
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from faustcoder import (
    COMPILER_SCHEMA_VERSION,
    EXCLUDED_TIMING_FIELDS,
    FAUSTWASM_VERSION,
    NODE_SANDBOX_FLAGS,
    NODE_STACK_SIZE_KB,
    UNGRADED_EXIT_FLOOR,
    ArtifactStore,
    CompilerExclusion,
    NativeFaustUnavailable,
    ResourceLimits,
    SandboxError,
    classify_diagnostic,
    compile_directory,
    compile_native,
    compile_source,
    cross_check_native,
    digest_hex,
    lookup_compiler_receipt,
    node_command,
    reproducible_receipt_digest,
    run_in_sandbox,
    runtime_pin,
    store_compiler_receipt,
    unshare_executable,
    validate,
)
from faustcoder.canonical import canonical_bytes
from faustcoder.sandbox import (
    _MASK_EXEC,
    SandboxRun,
    _reported_faust_directories,
    faust_fallback_mounts,
    faust_library_mounts,
    unshare_identity,
)
from faustcoder.compiler import (
    FAUSTLIBRARIES_PIN,
    FAUSTLIBRARIES_PIN_VERSION,
    _native_command,
    canonical_output_bytes,
    environment_preimage,
    native_faust_version,
    worker_directory,
    _build,
)
from faustcoder.exclusions import exclusion_for_source, exclusions, normalize_source
import faustcoder.libraries as libraries
from faustcoder.libraries import (
    FAUSTLIBRARIES_SHARE_SHA256,
    FAUSTLIBRARIES_TREE_SHA256,
    canonical_tree_sha256,
    library_root,
    share_directory,
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


def test_runtime_pin_records_the_staged_libraries_and_the_bundle() -> None:
    pin = runtime_pin()
    runtime = (
        worker_directory()
        / "node_modules"
        / "@grame"
        / "faustwasm"
        / "libfaust-wasm"
    )
    assert pin.faust_version == "2.90.0"
    assert pin.faustlibraries_version == FAUSTLIBRARIES_PIN_VERSION
    assert pin.faustlibraries_commit == FAUSTLIBRARIES_PIN
    assert pin.faustlibraries_tree_sha256 == FAUSTLIBRARIES_TREE_SHA256
    assert pin.bundled_faustlibraries_version == "2.74.2"
    assert pin.bundled_faustlibraries_version != pin.faustlibraries_version
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
    assert preimage["faustlibraries_commit"] == FAUSTLIBRARIES_PIN
    assert preimage["faustlibraries_tree_sha256"] == FAUSTLIBRARIES_TREE_SHA256
    assert preimage["faustlibraries_share_sha256"] == FAUSTLIBRARIES_SHARE_SHA256
    assert preimage["faustlibraries_version"] == "2.80.0"
    assert preimage["bundled_faustlibraries_version"] == "2.74.2"
    assert preimage["runtime_sha256"]["libfaust-wasm.wasm"] == pin.wasm_sha256
    assert preimage["runtime_sha256"]["libfaust-wasm.data"] == pin.data_sha256
    assert preimage["user_map"] == "current"
    assert f"--stack-size={NODE_STACK_SIZE_KB}" in preimage["node_flags"]


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


def test_url_in_a_comment_is_not_a_remote_import() -> None:
    source = '// import("https://example.invalid/x.lib")\nprocess = _;\n'
    compiled = compile_source(source, lang="wasm")
    assert compiled.receipt["exit_code"] == 0
    block = '/* component("https://example.invalid/y.lib") */\nprocess = _;\n'
    compiled_block = compile_source(block, lang="wasm")
    assert compiled_block.receipt["exit_code"] == 0


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


def test_deep_recursion_is_internal(store, tmp_path: Path) -> None:
    # --stack-size=8192 lets this unroll until the worker SIGSEGVs. The
    # catchable "Maximum call stack size exceeded" path is what a smaller
    # stack produced. Either way the raw receipt stays exit 126 internal.
    # Commit does not rerun it. The row stays ungraded until triage.
    import signal

    from faustcoder.candidate_machine import CandidateState
    from faustcoder.reward import RewardLedger, Ungraded, UngradedReason
    from faustcoder.signal import SignalRun, SignalSuite, commit_signal_check

    source = _source("recurse.dsp")
    compiled = compile_source(source, lang="wasm")
    assert compiled.receipt["exit_code"] == 126, repr(compiled.diagnostics)
    assert compiled.receipt["diagnostic_class"] == "internal"
    assert compiled.receipt["faust_version"] == "2.90.0"
    assert "wasm_trap" not in compiled.receipt
    # The same source either dies on SIGSEGV, with no recursion text, or
    # the runtime catches Maximum call stack size exceeded. Both are real.
    if compiled.diagnostics == "internal: worker failed\n":
        assert compiled.receipt["termination_signal"] == signal.SIGSEGV
        assert "runtime_stack_overflow" not in compiled.receipt
    else:
        assert compiled.diagnostics == "Maximum call stack size exceeded\n"
        assert compiled.receipt["runtime_stack_overflow"] is True
    ledger = RewardLedger(tmp_path / "recursion")
    from faustcoder.reward.grader import task_digest_full
    run = SignalRun(
        reward_task_digest=task_digest_full(json.loads(
            (Path(__file__).parent / "fixtures/valid/task-spec.json").read_text(encoding="utf-8"))),
        compilation=compiled,
        receipt=None,
        reproducible_digest=compiled.reproducible_digest,
        failures=("compiler",),
        reference_payload=None,
        reward_failure="compiler",
        source=source,
    )
    committed = commit_signal_check(
        store,
        SignalSuite(runs=(run,), ledger=ledger),
        state=CandidateState.COMPILE_CHECKED,
        created_at="2026-10-18T00:00:00Z",
        task=json.loads(
            (Path(__file__).parent / "fixtures/valid/task-spec.json").read_text(encoding="utf-8")
        ),
    )
    assert committed.state is CandidateState.COMPILE_CHECKED
    assert len(committed.outcomes) == 1
    outcome = committed.outcomes[0]
    assert isinstance(outcome, Ungraded)
    assert outcome.reason is UngradedReason.UNATTRIBUTED
    assert ledger.queue.count() == 1


def test_stack_overflow_in_eval_stays_internal() -> None:
    # libfaust-wasm catches Faust's stackOverflowDetector and writes
    # "ERROR : stack overflow in eval" into the worker result. The same
    # source sometimes SIGSEGVs first. Both are internal crashes.
    compiled = _build(
        b"f(n) = f(n - 1) + 1;\n",
        compiler="libfaust-wasm",
        faust_version="2.90.0",
        lang="wasm",
        options=(),
        compile_ok=False,
        diagnostics="ERROR : stack overflow in eval\n",
        outputs=[],
        duration_ms=1,
    )
    assert compiled.receipt["exit_code"] == 126
    assert compiled.receipt["diagnostic_class"] == "internal"
    syntax = _build(
        b"process = ;\n",
        compiler="libfaust-wasm",
        faust_version="2.90.0",
        lang="wasm",
        options=(),
        compile_ok=False,
        diagnostics="input:1 : ERROR : syntax error, unexpected ENDDEF\n",
        outputs=[],
        duration_ms=1,
    )
    assert syntax.receipt["exit_code"] == 1
    assert syntax.receipt["diagnostic_class"] == "parse_error"
    padded = _build(
        b"f(n) = f(n - 1) + 1;\n",
        compiler="libfaust-wasm",
        faust_version="2.90.0",
        lang="wasm",
        options=(),
        compile_ok=False,
        diagnostics="  ERROR : stack overflow in eval  \n",
        outputs=[],
        duration_ms=1,
    )
    assert padded.receipt["exit_code"] == 126
    near = _build(
        b"process = 1;\n",
        compiler="libfaust-wasm",
        faust_version="2.90.0",
        lang="wasm",
        options=(),
        compile_ok=False,
        diagnostics="ERROR : stack overflow in eval happened\n",
        outputs=[],
        duration_ms=1,
    )
    assert near.receipt["exit_code"] == 1


def _source_failure(diagnostics: str) -> object:
    return _build(
        b"process = 1;\n",
        compiler="libfaust-wasm",
        faust_version="2.90.0",
        lang="wasm",
        options=(),
        compile_ok=False,
        diagnostics=diagnostics,
        outputs=[],
        duration_ms=1,
    )


@pytest.mark.parametrize("separator", ["\u2028", "\u0085", "\v"])
def test_unicode_separators_do_not_fake_a_runtime_line(separator: str) -> None:
    compiled = _source_failure(f"x{separator}TypeError: y")
    assert compiled.receipt["exit_code"] == 1
    assert compiled.receipt["diagnostic_class"] != "internal"


def test_real_newline_still_starts_a_runtime_line() -> None:
    compiled = _source_failure("x\nTypeError: y\n")
    assert compiled.receipt["exit_code"] == 126
    assert compiled.receipt["diagnostic_class"] == "internal"


@pytest.mark.parametrize(
    "diagnostics",
    [
        "RangeError: Maximum call stack size exceeded\n",
        "ReferenceError: allocate is not defined\n",
        "TypeError: foo is not a function\n",
        "SyntaxError: Unexpected token\n",
        "InternalError: too much recursion\n",
        "Aborted(stack overflow)\n",
        "Aborted(ERROR : stack overflow in eval)\n",
        "Maximum call stack size exceeded\n",
    ],
)
def test_js_runtime_line_start_is_internal(diagnostics: str) -> None:
    compiled = _source_failure(diagnostics)
    assert compiled.receipt["exit_code"] == 126
    assert compiled.receipt["diagnostic_class"] == "internal"


@pytest.mark.parametrize(
    "source",
    [
        "process = TypeError;\n",
        "process = rangeerror;\n",
        "process = SyntaxError;\n",
        'process = component("stack overflow.dsp");\n',
        'process = library("TypeError.lib");\n',
        "typeerror(x) = x <: _, _;\nprocess = typeerror(1, 2);\n",
        'process = hslider("stack overflow", 0, 1, 0, 0.1);\n',
    ],
)
def test_echoed_crash_tokens_stay_source_errors(source: str) -> None:
    compiled = compile_source(source, lang="wasm")
    assert compiled.receipt["exit_code"] == 1
    assert compiled.receipt["diagnostic_class"] != "internal"


@pytest.mark.parametrize(
    "diagnostics",
    [
        "input:1 : ERROR : undefined symbol : TypeError\n",
        "input:1 : ERROR : undefined symbol : rangeerror\n",
        "input:1 : ERROR : undefined symbol : SyntaxError\n",
        "ERROR : unable to open file stack overflow.dsp\n",
        "ERROR : unable to open file TypeError.lib\n",
        "ERROR : too much arguments : 2, instead of : 1\nwhen applying : typeerror\nto : (1,2)\n",
        'ERROR : min = 1 should be less than max = 0 in '
        "'hslider(\"stack overflow\",0.0f,1.0f,0.0f,0.1f)'\n",
        "ERROR : unable to open file Aborted(stack overflow).dsp\n",
        "// TypeError: Maximum call stack size exceeded\n"
        "input:2 : ERROR : syntax error, unexpected ENDDEF\n",
        'declare name "ReferenceError: allocate is not defined";\n'
        "input:2 : ERROR : syntax error, unexpected ENDDEF\n",
        "typeerror: foo is not defined\n",
        "note TypeError: foo is not a function\n",
        "note Maximum call stack size exceeded\n",
        "maximum call stack size exceeded\n",
    ],
)
def test_crash_markers_inside_source_diagnostics_stay_exit_1(diagnostics: str) -> None:
    compiled = _source_failure(diagnostics)
    assert compiled.receipt["exit_code"] == 1
    assert compiled.receipt["diagnostic_class"] != "internal"


@pytest.mark.parametrize(
    "source",
    [
        "// TypeError: Maximum call stack size exceeded\n"
        "// RangeError: Maximum call stack size exceeded\n"
        "process = ;\n",
        'declare name "ReferenceError: allocate is not defined";\n'
        'declare author "SyntaxError: is not a function";\n'
        "process = ;\n",
    ],
)
def test_crash_markers_in_comments_and_declares_stay_exit_1(source: str) -> None:
    compiled = compile_source(source, lang="wasm")
    assert compiled.receipt["exit_code"] == 1
    assert compiled.receipt["diagnostic_class"] != "internal"


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


EXAMPLES = Path(__file__).resolve().parents[1] / "faust" / "examples" / "2.88.0"
_MULTI_FILE_COMPILE = (
    "SAM/16_channel_volume/16_channel_volume.dsp",
    "SAM/chorus/chorus.dsp",
    "SAM/effects/chorus.dsp",
    "SAM/effects/flanger.dsp",
    "SAM/effects/freeverb.dsp",
    "SAM/flanger/flanger.dsp",
    "SAM/freeverb/freeverb.dsp",
    "SAM/virtualAnalog/virtualAnalog.dsp",
    "filtering/multibandFilter.dsp",
    "misc/mixer.dsp",
)
_MULTI_FILE_EXCLUDED = (
    "SAM/echo/echo.dsp",
    "SAM/effects/echo.dsp",
    "SAM/effects/effects.dsp",
)


def _examples() -> Path:
    if not EXAMPLES.is_dir():
        pytest.fail("Faust 2.88.0 examples are missing; run scripts/fetch-faust-examples.sh")
    return EXAMPLES


def test_pinned_library_aliases_and_softmax_resolve() -> None:
    for name in ("fastmath.dsp", "pinktrombone.dsp", "softmax.dsp"):
        compiled = compile_source(_source(name))
        assert compiled.receipt["exit_code"] == 0, compiled.diagnostics
        assert compiled.receipt["diagnostic_class"] == "ok"
        assert f"--faustlibraries={FAUSTLIBRARIES_PIN}" in compiled.receipt["command"]


def test_function_removed_at_the_pin_is_unbound() -> None:
    compiled = compile_source(_source("removed.dsp"))
    assert compiled.receipt["exit_code"] == 1
    assert compiled.receipt["diagnostic_class"] == "unbound_symbol"
    assert "undefined symbol" in compiled.diagnostics


def test_one_library_byte_changes_the_tree_hash(tmp_path: Path) -> None:
    (tmp_path / "a.lib").write_bytes(b"a = 1;\n")
    first = canonical_tree_sha256(tmp_path)
    (tmp_path / "a.lib").write_bytes(b"a = 2;\n")
    second = canonical_tree_sha256(tmp_path)
    assert first != second
    pin = runtime_pin()
    preimage = environment_preimage(
        compiler="libfaust-wasm",
        faust_version=pin.faust_version,
        lang="wasm",
        options=(),
        pin=pin,
    )
    mutated = dict(preimage, faustlibraries_tree_sha256=second)
    assert hashlib.sha256(canonical_bytes(preimage)).digest() != hashlib.sha256(
        canonical_bytes(mutated)
    ).digest()
    mounted = dict(preimage, faustlibraries_share_sha256=second)
    assert hashlib.sha256(canonical_bytes(preimage)).digest() != hashlib.sha256(
        canonical_bytes(mounted)
    ).digest()
    assert preimage["faustlibraries_share_sha256"] == FAUSTLIBRARIES_SHARE_SHA256
    assert canonical_tree_sha256(share_directory()) == FAUSTLIBRARIES_SHARE_SHA256


def test_native_command_points_at_the_pinned_share_tree() -> None:
    share = share_directory()
    command = _native_command("/usr/bin/faust", share, ())
    assert command[:4] == ["/usr/bin/faust", "-I", str(share), "-lang"]
    assert (share / "stdfaust.lib").is_file()
    assert (share / "fastmath.lib").is_file()
    assert (share / "pinktrombone.lib").is_file()
    assert (share / "dx7.lib").is_file()
    assert (share / "old" / "music.lib").is_file()


def test_native_preimage_uses_the_same_library_tree() -> None:
    preimage = environment_preimage(
        compiler="faust-cli",
        faust_version="2.88.0",
        lang="cpp",
        options=(),
        pin=None,
    )
    assert preimage["faustlibraries_commit"] == FAUSTLIBRARIES_PIN
    assert preimage["faustlibraries_tree_sha256"] == FAUSTLIBRARIES_TREE_SHA256
    assert preimage["faustlibraries_share_sha256"] == FAUSTLIBRARIES_SHARE_SHA256
    assert preimage["faustlibraries_version"] == FAUSTLIBRARIES_PIN_VERSION
    assert preimage["bundled_faustlibraries_version"] == ""
    unshare_path, unshare_sha256 = unshare_identity()
    assert preimage["unshare_path"] == unshare_path
    assert preimage["unshare_sha256"] == unshare_sha256


def test_library_tree_mismatch_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "version.lib").write_bytes(b"version = 0, 0, 0;\n")
    monkeypatch.setenv("FAUSTCODER_LIBRARIES", str(tmp_path))
    with pytest.raises(SandboxError, match="sha256"):
        compile_source("process = _;\n")


def test_two_entries_under_one_root_do_not_share_a_source_identity(tmp_path: Path) -> None:
    (tmp_path / "a.dsp").write_text("process = _ * 0.5;\n", encoding="utf-8")
    (tmp_path / "b.dsp").write_text("process = _ * 0.25;\n", encoding="utf-8")
    first = compile_directory(tmp_path, "a.dsp")
    second = compile_directory(tmp_path, "b.dsp")
    assert first.receipt["exit_code"] == 0, first.diagnostics
    assert second.receipt["exit_code"] == 0, second.diagnostics
    assert first.receipt["source_sha256"] != second.receipt["source_sha256"]


def test_concurrent_processes_publish_one_share(tmp_path: Path) -> None:
    checkout = tmp_path / "2edec0537f53"
    _copy_library_checkout(checkout)
    script = (
        "import os, sys\n"
        "os.environ['FAUSTCODER_LIBRARIES'] = sys.argv[1]\n"
        "from faustcoder.libraries import (\n"
        "    FAUSTLIBRARIES_SHARE_SHA256, canonical_tree_sha256, share_directory,\n"
        ")\n"
        "path = share_directory()\n"
        "digest = canonical_tree_sha256(path)\n"
        "if digest != FAUSTLIBRARIES_SHARE_SHA256:\n"
        "    raise SystemExit(digest)\n"
        "print(path)\n"
    )
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(checkout)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(8)
    ]
    results = []
    for process in processes:
        stdout, stderr = process.communicate()
        results.append((process.returncode, stdout, stderr))
    failures = [item for item in results if item[0] != 0]
    assert not failures, failures
    paths = {stdout.decode().strip() for _, stdout, _ in results}
    assert len(paths) == 1
    assert (tmp_path / "share-2edec0537f53").is_dir()
    assert (tmp_path / "share-2edec0537f53.lock").is_file()
    assert not (tmp_path / "share-2edec0537f53.lock").is_symlink()


def test_hung_share_lock_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "2edec0537f53"
    _copy_library_checkout(checkout)
    lock_path = tmp_path / "share-2edec0537f53.lock"
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import fcntl, os, sys, time\n"
            "fd = os.open(sys.argv[1], os.O_CREAT | os.O_RDWR, 0o644)\n"
            "fcntl.flock(fd, fcntl.LOCK_EX)\n"
            "print('held', flush=True)\n"
            "time.sleep(8)\n",
            str(lock_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert _read_line(holder, 5) == b"held\n"
        monkeypatch.setenv("FAUSTCODER_LIBRARIES", str(checkout))
        monkeypatch.setattr("faustcoder.libraries.SHARE_LOCK_TIMEOUT_S", 0.4)
        started = time.monotonic()
        with pytest.raises(
            SandboxError, match="timed out waiting for the faustlibraries share lock"
        ):
            share_directory()
        assert time.monotonic() - started < 3
        assert not (tmp_path / "share-2edec0537f53").exists()
    finally:
        holder.kill()
        holder.wait(timeout=5)


def test_share_lock_symlink_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "2edec0537f53"
    _copy_library_checkout(checkout)
    target = tmp_path / "lock-target"
    fd = os.open(target, os.O_CREAT | os.O_RDWR, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)
    lock_path = tmp_path / "share-2edec0537f53.lock"
    lock_path.symlink_to(target)
    monkeypatch.setenv("FAUSTCODER_LIBRARIES", str(checkout))
    # A follow of this symlink would block on the held target, then time out.
    monkeypatch.setattr("faustcoder.libraries.SHARE_LOCK_TIMEOUT_S", 0.4)
    real_open = os.open
    real_is_symlink = Path.is_symlink
    opened: list[int] = []

    def spy_open(
        path: object, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if Path(str(path)) == lock_path:
            opened.append(flags)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    def hide_lock_symlink(self: Path) -> bool:
        if self == lock_path:
            return False
        return real_is_symlink(self)

    monkeypatch.setattr(os, "open", spy_open)
    monkeypatch.setattr(Path, "is_symlink", hide_lock_symlink)
    started = time.monotonic()
    try:
        with pytest.raises(SandboxError, match="share lock is a symlink"):
            share_directory()
        assert time.monotonic() - started < 2
        assert not (tmp_path / "share-2edec0537f53").exists()
        assert opened
        assert all(flags & os.O_NOFOLLOW for flags in opened)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def test_share_lock_directory_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "2edec0537f53"
    _copy_library_checkout(checkout)
    (tmp_path / "share-2edec0537f53.lock").mkdir()
    monkeypatch.setenv("FAUSTCODER_LIBRARIES", str(checkout))
    with pytest.raises(SandboxError, match="share lock is a directory"):
        share_directory()
    assert not (tmp_path / "share-2edec0537f53").exists()


def test_mkdir_failure_releases_the_process_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "2edec0537f53"
    _copy_library_checkout(checkout)
    monkeypatch.setenv("FAUSTCODER_LIBRARIES", str(checkout))
    monkeypatch.setattr("faustcoder.libraries.SHARE_LOCK_TIMEOUT_S", 0.4)
    real_mkdir = Path.mkdir

    def fail_parent(self: Path, *args: object, **kwargs: object) -> None:
        if Path(self) == tmp_path:
            raise OSError(errno.EACCES, "Permission denied", str(self))
        real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_parent)
    with pytest.raises(OSError, match="Permission denied") as first:
        share_directory()
    assert first.value.errno == errno.EACCES
    assert not libraries._LOCK.locked()
    started = time.monotonic()
    with pytest.raises(OSError, match="Permission denied") as second:
        share_directory()
    assert second.value.errno == errno.EACCES
    assert time.monotonic() - started < 0.3
    assert not libraries._LOCK.locked()


def test_in_process_share_lock_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "2edec0537f53"
    _copy_library_checkout(checkout)
    monkeypatch.setenv("FAUSTCODER_LIBRARIES", str(checkout))
    monkeypatch.setattr("faustcoder.libraries.SHARE_LOCK_TIMEOUT_S", 0.4)
    assert libraries._LOCK.acquire(timeout=1)
    try:
        started = time.monotonic()
        with pytest.raises(SandboxError, match="another thread in this process"):
            share_directory()
        assert time.monotonic() - started < 3
        assert not (tmp_path / "share-2edec0537f53").exists()
    finally:
        libraries._LOCK.release()


def test_thread_lock_and_flock_share_one_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "2edec0537f53"
    _copy_library_checkout(checkout)
    holder = _hold_share_lock(tmp_path / "share-2edec0537f53.lock")
    monkeypatch.setenv("FAUSTCODER_LIBRARIES", str(checkout))
    monkeypatch.setattr("faustcoder.libraries.SHARE_LOCK_TIMEOUT_S", 1.0)

    class DelayedLock:
        def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
            time.sleep(0.6)
            return True

        def release(self) -> None:
            return None

    monkeypatch.setattr("faustcoder.libraries._LOCK", DelayedLock())
    try:
        started = time.monotonic()
        with pytest.raises(SandboxError, match="another process holds"):
            share_directory()
        # A second full timeout after the 0.6s thread-lock delay would pass 1.6s.
        assert time.monotonic() - started < 1.35
        assert not (tmp_path / "share-2edec0537f53").exists()
    finally:
        holder.kill()
        holder.wait(timeout=5)


def test_native_sandbox_masks_a_host_faust_share(tmp_path: Path) -> None:
    secret = tmp_path / "share"
    secret.mkdir()
    (secret / "stdfaust.lib").write_text("PWNED\n", encoding="ascii")
    script = (
        "uid=$(id -u); cap=$(awk '/^CapEff:/ {print $2}' /proc/self/status); "
        'if [ -e "$1/stdfaust.lib" ]; then seen=visible; else seen=hidden; fi; '
        "printf '%s %s %s\\n' \"$uid\" \"$cap\" \"$seen\""
    )
    command = ["/bin/sh", "-c", script, "sh", str(secret)]
    limits = ResourceLimits(timeout_s=5)
    masked = run_in_sandbox(
        command,
        stdin=b"",
        workdir=tmp_path,
        limits=limits,
        mask_directories=(secret,),
    )
    assert masked.returncode == 0, masked.stderr
    assert masked.stdout == f"{os.getuid()} 0000000000000000 hidden\n".encode()
    assert (secret / "stdfaust.lib").read_text(encoding="ascii") == "PWNED\n"
    plain = run_in_sandbox(command, stdin=b"", workdir=tmp_path, limits=limits)
    assert plain.returncode == 0, plain.stderr
    assert plain.stdout.endswith(b"visible\n")


def test_native_sandbox_drops_all_capabilities_and_sets_no_new_privs(tmp_path: Path) -> None:
    masked = tmp_path / "masked"
    masked.mkdir()
    run = run_in_sandbox(
        ["/bin/cat", "/proc/self/status"],
        stdin=b"",
        workdir=tmp_path,
        limits=ResourceLimits(timeout_s=5),
        mask_directories=(masked,),
    )
    assert run.returncode == 0, run.stderr
    status = dict(line.split(":", 1) for line in run.stdout.decode().splitlines() if ":" in line)
    for field in ("CapInh", "CapPrm", "CapEff", "CapAmb"):
        assert int(status[field].strip(), 16) == 0, (field, status[field])
    assert status["NoNewPrivs"].strip() == "1"


def test_faust_fallback_mounts_skip_missing_and_resolve_symlinks(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    present = tmp_path / "faust"
    present.mkdir()
    link = tmp_path / "link"
    link.symlink_to(present)
    assert faust_fallback_mounts((missing, present, link)) == (present.resolve(),)
    root = tmp_path / "root"
    root.symlink_to("/")
    with pytest.raises(SandboxError, match="resolves to /"):
        faust_fallback_mounts((root,))
    file_path = tmp_path / "file"
    file_path.write_text("nope\n", encoding="ascii")
    with pytest.raises(SandboxError, match="not a directory"):
        faust_fallback_mounts((file_path,))
    defaults = (Path("/usr/local/share/faust"), Path("/usr/share/faust"))
    assert faust_fallback_mounts() == tuple(
        path.resolve() for path in defaults if path.exists()
    )


def test_native_compile_uses_a_hashed_private_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = share_directory()
    monkeypatch.setattr("faustcoder.compiler._require_native_faust", lambda: "/usr/bin/faust")
    monkeypatch.setattr("faustcoder.sandbox._reported_faust_directories", lambda _binary: ())
    # /usr/share is mode 0777 on GitHub-hosted Ubuntu. This test checks the
    # private copy, not that host mode.
    monkeypatch.setattr("faustcoder.sandbox._is_root_only_directory", lambda _path: True)

    def fake_run(command: list[str], **kwargs: object) -> SandboxRun:
        include = Path(command[command.index("-I") + 1])
        assert include != live
        assert include.parent == Path(str(kwargs["workdir"]))
        assert canonical_tree_sha256(include) == FAUSTLIBRARIES_SHARE_SHA256
        assert kwargs["mask_directories"] == faust_library_mounts(
            "/usr/bin/faust", private=include
        )
        return SandboxRun(0, b"int process(){return 0;}\n", b"", "", False, False)

    monkeypatch.setattr("faustcoder.compiler.run_in_sandbox", fake_run)
    compiled = compile_native("process = _;\n")
    assert compiled.receipt["exit_code"] == 0
    assert compiled.receipt["compiler"] == "faust-cli"


def test_library_mounts_cover_the_prefix_beside_the_binary(tmp_path: Path) -> None:
    prefix = tmp_path / "fprefix"
    binary = prefix / "bin" / "faust"
    _fake_faust(binary)
    share = prefix / "share" / "faust"
    lib = prefix / "lib" / "faust"
    share.mkdir(parents=True)
    lib.mkdir(parents=True)
    (prefix / "bin" / "share" / "faust").mkdir(parents=True)
    private = tmp_path / "private"
    private.mkdir()
    mounts = faust_library_mounts(binary, private=private)
    assert share.resolve() in mounts
    assert lib.resolve() in mounts
    assert private.resolve() not in mounts

    hidden = tmp_path / "hidden-share"
    hidden.mkdir()
    via = tmp_path / "via"
    via_bin = via / "bin" / "faust"
    _fake_faust(via_bin)
    via_share = via / "share" / "faust"
    via_share.parent.mkdir(parents=True)
    via_share.symlink_to(hidden, target_is_directory=True)
    (via / "lib" / "faust").mkdir(parents=True)
    (via / "bin" / "share" / "faust").mkdir(parents=True)
    via_mounts = faust_library_mounts(via_bin, private=private)
    assert hidden.resolve() in via_mounts


def test_library_mounts_mask_reported_dirs_except_the_private_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "bin" / "faust"
    _fake_faust(binary)
    _prefix_library_dirs(binary)
    private = tmp_path / "private"
    private.mkdir()
    extra = tmp_path / "reported"
    extra.mkdir()
    loader = Path("/usr/lib")

    def reported(_binary: Path) -> tuple[Path, ...]:
        return (private, extra, loader)

    monkeypatch.setattr("faustcoder.sandbox._reported_faust_directories", reported)
    mounts = faust_library_mounts(binary, private=private)
    assert extra.resolve() in mounts
    assert private.resolve() not in mounts
    assert loader.resolve() not in mounts


def test_library_mounts_refuse_a_user_writable_absent_prefix(tmp_path: Path) -> None:
    binary = tmp_path / "bin" / "faust"
    _fake_faust(binary)
    private = tmp_path / "private"
    private.mkdir()
    with pytest.raises(SandboxError, match="not root-only"):
        faust_library_mounts(binary, private=private)


def test_library_mounts_keep_absent_root_only_directories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("faustcoder.sandbox._reported_faust_directories", lambda _binary: ())
    monkeypatch.setattr("faustcoder.sandbox._is_root_only_directory", lambda _path: True)
    private = Path("/usr/lib/faustcoder-private-copy")
    mounts = faust_library_mounts("/usr/bin/faust", private=private)
    for path in (
        Path("/usr/share/faust"),
        Path("/usr/local/share/faust"),
        Path("/usr/lib/faust"),
        Path("/usr/bin/share/faust"),
    ):
        assert path in mounts or path.resolve() in mounts
    assert private not in mounts


def _mount_with_absent_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: Path, *, kind: str
) -> tuple[Path, ...]:
    binary = tmp_path / "opt" / "bin" / "faust"
    _fake_faust(binary)
    _prefix_library_dirs(binary)
    if kind == "fallback":
        monkeypatch.setattr("faustcoder.sandbox.FAUST_FALLBACK_DIRECTORIES", (missing,))
        monkeypatch.setattr("faustcoder.sandbox._reported_faust_directories", lambda _binary: ())
    else:
        monkeypatch.setattr("faustcoder.sandbox.FAUST_FALLBACK_DIRECTORIES", ())
        monkeypatch.setattr(
            "faustcoder.sandbox._reported_faust_directories",
            lambda _binary: (missing,),
        )
    private = tmp_path / "private"
    private.mkdir()
    return faust_library_mounts(binary, private=private)


@pytest.mark.parametrize("kind", ["fallback", "reported"])
def test_absent_mask_refuses_a_group_writable_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    parent = tmp_path / "share"
    parent.mkdir()
    parent.chmod(0o775)
    missing = parent / "faust"
    with pytest.raises(SandboxError, match="not root-only"):
        _mount_with_absent_candidate(tmp_path, monkeypatch, missing, kind=kind)


@pytest.mark.parametrize("kind", ["fallback", "reported"])
def test_absent_mask_refuses_a_non_root_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    parent = tmp_path / "share"
    parent.mkdir()
    parent.chmod(0o755)
    missing = parent / "faust"
    with pytest.raises(SandboxError, match="not root-only"):
        _mount_with_absent_candidate(tmp_path, monkeypatch, missing, kind=kind)


def test_absent_mask_refuses_a_user_writable_grandparent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from faustcoder.sandbox import _component_is_root_only

    grand = tmp_path / "gp"
    grand.mkdir()
    grand.chmod(0o777)
    parent = grand / "par"
    subprocess.run(["sudo", "-n", "mkdir", "-p", "--", str(parent)], check=True)
    subprocess.run(["sudo", "-n", "chown", "root:root", "--", str(parent)], check=True)
    subprocess.run(["sudo", "-n", "chmod", "755", "--", str(parent)], check=True)
    info = parent.lstat()
    assert info.st_uid == 0
    assert stat.S_ISDIR(info.st_mode)
    assert not stat.S_ISLNK(info.st_mode)
    assert info.st_mode & 0o777 == 0o755
    assert grand.stat().st_uid != 0
    assert grand.stat().st_mode & 0o777 == 0o777
    # The immediate parent would pass the single-directory check.
    assert _component_is_root_only(parent, allow_sticky=False)
    missing = parent / "faust"
    assert not missing.exists()
    with pytest.raises(SandboxError, match="not root-only"):
        _mount_with_absent_candidate(tmp_path, monkeypatch, missing, kind="reported")


def test_root_only_walk_allows_a_root_sticky_ancestor_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from faustcoder.sandbox import _is_root_only_directory

    def stat_of(mode: int, uid: int) -> os.stat_result:
        return os.stat_result((stat.S_IFDIR | mode, 0, 0, 1, uid, 0, 0, 0, 0, 0))

    modes = {
        "/": (0o755, 0),
        "/var": (0o1777, 0),
        "/var/par": (0o755, 0),
    }

    def fake(path: Path) -> os.stat_result:
        mode, uid = modes[str(path)]
        return stat_of(mode, uid)

    monkeypatch.setattr("faustcoder.sandbox._lstat_or_none", fake)
    assert _is_root_only_directory(Path("/var/par"))
    assert not _is_root_only_directory(Path("/var"))
    modes["/var"] = (0o777, 1000)
    assert not _is_root_only_directory(Path("/var/par"))
    modes["/var"] = (0o775, 0)
    assert not _is_root_only_directory(Path("/var/par"))
    modes["/var"] = (0o1777, 1000)
    assert not _is_root_only_directory(Path("/var/par"))


@pytest.mark.parametrize("kind", ["fallback", "reported"])
def test_absent_mask_accepts_a_symlink_to_a_root_only_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    target = Path("/usr")
    info = target.stat()
    assert info.st_uid == 0
    assert stat.S_ISDIR(info.st_mode)
    assert info.st_mode & 0o022 == 0
    link = tmp_path / "share"
    link.symlink_to(target)
    missing = link / "faustcoder-absent-mask"
    assert not missing.exists()
    mounts = _mount_with_absent_candidate(tmp_path, monkeypatch, missing, kind=kind)
    assert missing in mounts


def test_native_sandbox_passes_an_absent_mask_candidate(tmp_path: Path) -> None:
    secret = tmp_path / "share"
    secret.mkdir()
    (secret / "stdfaust.lib").write_text("PWNED\n", encoding="ascii")
    absent = tmp_path / "missing-share"
    script = (
        'if [ -e "$1/stdfaust.lib" ]; then seen=visible; else seen=hidden; fi; '
        'if [ -e "$2" ]; then late=appeared; else late=absent; fi; '
        "printf '%s %s\\n' \"$seen\" \"$late\""
    )
    command = ["/bin/sh", "-c", script, "sh", str(secret), str(absent)]
    masked = run_in_sandbox(
        command,
        stdin=b"",
        workdir=tmp_path,
        limits=ResourceLimits(timeout_s=5),
        mask_directories=(secret, absent),
    )
    assert masked.returncode == 0, masked.stderr
    assert masked.stdout == b"hidden absent\n"
    assert (secret / "stdfaust.lib").read_text(encoding="ascii") == "PWNED\n"
    assert not absent.exists()


def test_mask_script_fails_when_an_absent_candidate_appears(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _MASK_EXEC.rsplit("\nmain()\n", 1)[0]
    namespace: dict[str, object] = {}
    exec(source, namespace)  # noqa: S102
    refuse = namespace["refuse_if_unmasked"]
    assert callable(refuse)
    missing = tmp_path / "late"
    refuse([str(missing)])
    missing.mkdir()
    with pytest.raises(SystemExit):
        refuse([str(missing)])
    captured = capsys.readouterr()
    assert "faustcoder_mask_failed:" in captured.err
    assert "exists unmasked" in captured.err


def test_reported_faust_directories_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing-faust"
    with pytest.raises(SandboxError, match="is not a file"):
        _reported_faust_directories(missing)

    binary = tmp_path / "faust"
    binary.write_text("#!/bin/sh\nexit 7\n", encoding="ascii")
    binary.chmod(0o755)
    with pytest.raises(SandboxError, match="exited 7"):
        _reported_faust_directories(binary)

    binary.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    binary.chmod(0o755)
    with pytest.raises(SandboxError, match="FAUST dsp library paths:"):
        _reported_faust_directories(binary)

    def timed_out(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="faust", timeout=10)

    monkeypatch.setattr("faustcoder.sandbox.subprocess.run", timed_out)
    with pytest.raises(SandboxError, match="timed out"):
        _reported_faust_directories(binary)


def test_reported_faust_directories_refuse_a_non_utf8_pathslist(tmp_path: Path) -> None:
    """A lone 0xec in --pathslist is a refusal, not a UnicodeDecodeError.

    LANG=C does not make Faust's bytes ASCII. The CI flake was
    ``text=True`` decoding that byte as UTF-8. The path does not exist.
    """
    binary = tmp_path / "faust"
    # ``\354`` is byte 0xec. POSIX ``printf`` has no ``\x`` escape.
    binary.write_bytes(
        b"#!/bin/sh\n"
        b'case "$1" in\n'
        b"  --pathslist)\n"
        b"    printf '%s\\n' 'FAUST dsp library paths:'\n"
        b"    printf '/tmp/faust-pathslist-\\354\\n'\n"
        b"    ;;\n"
        b"esac\n"
        b"exit 0\n"
    )
    binary.chmod(0o755)
    try:
        _reported_faust_directories(binary)
    except SandboxError as exc:
        assert "non-decodable" in str(exc)
        assert "nonexistent" in str(exc)
        assert not isinstance(exc.__cause__, UnicodeDecodeError)
    except UnicodeDecodeError as exc:
        raise AssertionError("pathslist decode crashed") from exc
    else:
        raise AssertionError("a non-decodable pathslist was accepted")


def test_reported_faust_directories_refuse_a_nul_in_pathslist(tmp_path: Path) -> None:
    """A NUL in --pathslist is a SandboxError, not an uncaught ValueError."""
    binary = tmp_path / "faust"
    binary.write_bytes(
        b"#!/bin/sh\n"
        b'case "$1" in\n'
        b"  --pathslist)\n"
        b"    printf '%s\\n' 'FAUST dsp library paths:'\n"
        b"    printf '%s' '/tmp/faust-nul-'\n"
        b"    printf '\\000'\n"
        b"    printf '%s\\n' 'extra'\n"
        b"    ;;\n"
        b"esac\n"
        b"exit 0\n"
    )
    binary.chmod(0o755)
    try:
        _reported_faust_directories(binary)
    except SandboxError as exc:
        assert "cannot be checked" in str(exc)
        assert isinstance(exc.__cause__, ValueError)
    except ValueError as exc:
        raise AssertionError("a NUL in pathslist escaped the sandbox") from exc
    else:
        raise AssertionError("a NUL in pathslist was accepted")


def test_reported_faust_directories_keep_absolute_paths(tmp_path: Path) -> None:
    binary = tmp_path / "faust"
    binary.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        "  --libdir) printf '%s\\n' /tmp/reported-lib ;;\n"
        "  --pathslist)\n"
        "    printf '%s\\n' 'FAUST dsp library paths:' /tmp/reported-one\n"
        "    ;;\n"
        "esac\n"
        "exit 0\n",
        encoding="ascii",
    )
    binary.chmod(0o755)
    found = _reported_faust_directories(binary)
    assert Path("/tmp/reported-lib") in found
    assert Path("/tmp/reported-one") in found


def test_install_script_pins_the_faust_tarball(tmp_path: Path) -> None:
    script = Path("scripts/install-faust-2.88.0.sh").read_text(encoding="utf-8")
    pinned = "e4e175cf236924b5b7d4784cbb8c50cc01e211159e169655dd9e6d8f92b871d9"
    assert pinned in script
    assert script.index("sha256sum -c") < script.index("tar -xzf")
    assert "/usr/share/faust" in script
    assert "/usr/local/share/faust" in script
    assert script.index("O_NOFOLLOW") < script.index("already on PATH")
    assert "0o755" in script
    assert "chown -h root:root" in script
    assert "refusing pre-seeded symlink" in script
    assert "world-writable parent" in script
    tarball = tmp_path / "faust-2.88.0.tar.gz"
    tarball.write_bytes(b"not-the-release\n")
    check = subprocess.run(
        ["sha256sum", "-c"],
        input=f"{pinned}  {tarball}\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode != 0


def _ensure_root_dir(path: Path) -> subprocess.CompletedProcess[str]:
    script = Path("scripts/install-faust-2.88.0.sh").resolve()
    return subprocess.run(
        ["bash", "-c", 'source "$1"; ensure_root_dir "$2"', "bash", str(script), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


def _scratch(mode: str) -> Path:
    """A root-owned directory directly under ``/tmp``, removed by the caller."""
    path = Path("/tmp") / f"faustcoder-install-{os.getpid()}-{uuid.uuid4().hex}"
    subprocess.run(["sudo", "-n", "mkdir", "--", str(path)], check=True)
    subprocess.run(["sudo", "-n", "chown", "root:root", "--", str(path)], check=True)
    subprocess.run(["sudo", "-n", "chmod", mode, "--", str(path)], check=True)
    return path


def _sudo_rm(path: Path) -> None:
    subprocess.run(["sudo", "-n", "rm", "-rf", "--", str(path)], check=False)


def _chmod_nofollow(path: Path) -> subprocess.CompletedProcess[str]:
    script = Path("scripts/install-faust-2.88.0.sh").resolve()
    return subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; chmod_directory_nofollow "$2"',
            "bash",
            str(script),
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_install_refuses_a_symlink_a_file_and_a_world_writable_bin(tmp_path: Path) -> None:
    parent = _scratch("1777")
    try:
        attacker = tmp_path / "attacker"
        attacker.mkdir()
        (attacker / "stdfaust.lib").write_text("PWNED\n", encoding="ascii")
        link = parent / "architecture"
        link.symlink_to(attacker, target_is_directory=True)
        before = attacker.stat()
        refused = _ensure_root_dir(link)
        assert refused.returncode != 0
        assert "pre-seeded symlink" in refused.stderr
        assert link.is_symlink()
        after = attacker.stat()
        assert after.st_uid == before.st_uid
        assert after.st_mode == before.st_mode
        assert (attacker / "stdfaust.lib").read_text(encoding="ascii") == "PWNED\n"

        planted = parent / "not-a-dir"
        planted.write_text("nope\n", encoding="ascii")
        refused_file = _ensure_root_dir(planted)
        assert refused_file.returncode != 0
        assert "non-directory" in refused_file.stderr
        assert planted.is_file()
    finally:
        _sudo_rm(parent)

    open_bin = tmp_path / "open-bin"
    open_bin.mkdir()
    open_bin.chmod(0o777)
    refused_open = _ensure_root_dir(open_bin / "architecture")
    assert refused_open.returncode != 0
    assert "world-writable" in refused_open.stderr
    assert not (open_bin / "architecture").exists()

    sticky_user = tmp_path / "sticky-user"
    sticky_user.mkdir()
    sticky_user.chmod(0o1777)
    refused_sticky = _ensure_root_dir(sticky_user / "architecture")
    assert refused_sticky.returncode != 0
    assert "world-writable" in refused_sticky.stderr
    assert not (sticky_user / "architecture").exists()


def test_install_refuses_group_writable_non_root_and_a_user_grandparent(
    tmp_path: Path,
) -> None:
    groupy = _scratch("775")
    try:
        refused_group = _ensure_root_dir(groupy / "architecture")
        assert refused_group.returncode != 0
        assert "group-writable" in refused_group.stderr
        assert not (groupy / "architecture").exists()
    finally:
        _sudo_rm(groupy)

    user_owned = tmp_path / "user-bin"
    user_owned.mkdir()
    user_owned.chmod(0o755)
    refused_user = _ensure_root_dir(user_owned / "architecture")
    assert refused_user.returncode != 0
    assert "non-root" in refused_user.stderr
    assert not (user_owned / "architecture").exists()

    grand = tmp_path / "grand"
    grand.mkdir()
    grand.chmod(0o777)
    parent = grand / "parent"
    try:
        subprocess.run(["sudo", "-n", "mkdir", "--", str(parent)], check=True)
        subprocess.run(["sudo", "-n", "chown", "root:root", "--", str(parent)], check=True)
        subprocess.run(["sudo", "-n", "chmod", "755", "--", str(parent)], check=True)
        refused_chain = _ensure_root_dir(parent / "architecture")
        assert refused_chain.returncode != 0
        assert "world-writable" in refused_chain.stderr
        assert str(grand) in refused_chain.stderr
        assert not (parent / "architecture").exists()
    finally:
        _sudo_rm(parent)


def test_install_refuses_a_preexisting_directory_with_planted_contents(tmp_path: Path) -> None:
    parent = _scratch("1777")
    try:
        planted = parent / "architecture"
        planted.mkdir()
        (planted / "stdfaust.lib").write_text("PWNED\n", encoding="ascii")
        before = planted.stat()
        file_before = (planted / "stdfaust.lib").stat()
        refused = _ensure_root_dir(planted)
        assert refused.returncode != 0
        assert "pre-existing" in refused.stderr
        after = planted.stat()
        assert after.st_uid == before.st_uid
        assert after.st_uid != 0
        assert after.st_mode == before.st_mode
        assert (planted / "stdfaust.lib").read_text(encoding="ascii") == "PWNED\n"
        assert (planted / "stdfaust.lib").stat().st_uid == file_before.st_uid

        group_owned = parent / "groupy"
        subprocess.run(["sudo", "-n", "mkdir", "--", str(group_owned)], check=True)
        subprocess.run(["sudo", "-n", "chown", "root:root", "--", str(group_owned)], check=True)
        subprocess.run(["sudo", "-n", "chmod", "775", "--", str(group_owned)], check=True)
        refused_mode = _ensure_root_dir(group_owned)
        assert refused_mode.returncode != 0
        assert "pre-existing" in refused_mode.stderr
        assert group_owned.stat().st_mode & 0o777 == 0o775
        assert group_owned.stat().st_uid == 0
    finally:
        _sudo_rm(parent)


def test_install_creates_a_real_root_owned_directory() -> None:
    parent = _scratch("755")
    try:
        created = _ensure_root_dir(parent / "architecture")
        assert created.returncode == 0, created.stderr
        info = (parent / "architecture").lstat()
        assert stat.S_ISDIR(info.st_mode)
        assert not stat.S_ISLNK(info.st_mode)
        assert info.st_uid == 0
        assert info.st_mode & 0o777 == 0o755
        again = _ensure_root_dir(parent / "architecture")
        assert again.returncode == 0, again.stderr
        assert (parent / "architecture").lstat().st_uid == 0
    finally:
        _sudo_rm(parent)

    sticky = _scratch("1777")
    try:
        allowed = _ensure_root_dir(sticky / "architecture")
        assert allowed.returncode == 0, allowed.stderr
        child = (sticky / "architecture").lstat()
        assert stat.S_ISDIR(child.st_mode)
        assert not stat.S_ISLNK(child.st_mode)
        assert child.st_uid == 0
        assert child.st_mode & 0o777 == 0o755
    finally:
        _sudo_rm(sticky)


def test_chmod_directory_nofollow_does_not_follow_a_symlink(tmp_path: Path) -> None:
    target = tmp_path / "victim"
    target.mkdir()
    target.chmod(0o700)
    link = tmp_path / "architecture"
    link.symlink_to(target, target_is_directory=True)
    refused = _chmod_nofollow(link)
    assert refused.returncode != 0
    assert target.stat().st_mode & 0o777 == 0o700

    directory = tmp_path / "real"
    directory.mkdir()
    directory.chmod(0o700)
    changed = _chmod_nofollow(directory)
    assert changed.returncode == 0, changed.stderr
    assert directory.stat().st_mode & 0o777 == 0o755


def test_native_compile_rejects_a_library_planted_beside_the_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = shutil.which("faust")
    if binary is None or native_faust_version() != "2.88.0":
        pytest.skip("skipped-without-faust: native Faust 2.88.0 is not installed")
    prefix = tmp_path / "fprefix"
    planted = prefix / "bin" / "faust"
    planted.parent.mkdir(parents=True)
    shutil.copy2(binary, planted)
    planted.chmod(0o755)
    share = prefix / "share" / "faust"
    share.mkdir(parents=True)
    (prefix / "lib" / "faust").mkdir(parents=True)
    (prefix / "bin" / "share" / "faust").mkdir(parents=True)
    (share / "zzprobe.lib").write_text("zzprobe = 1;\n", encoding="utf-8")
    _create_writable_reported_directories(planted)
    source = 'import("zzprobe.lib"); process = zzprobe;\n'
    dsp = tmp_path / "probe.dsp"
    dsp.write_text(source, encoding="utf-8")
    empty = tmp_path / "empty-inc"
    empty.mkdir()
    direct = subprocess.run(
        [str(planted), "-I", str(empty), "-lang", "cpp", str(dsp)],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert direct.returncode == 0, direct.stderr
    monkeypatch.setenv("PATH", f"{planted.parent}{os.pathsep}{os.environ['PATH']}")
    compiled = compile_native(source)
    assert compiled.receipt["exit_code"] != 0
    assert compiled.receipt["diagnostic_class"] != "ok"
    assert "zzprobe" in compiled.diagnostics


def _fake_faust(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        "  --pathslist)\n"
        "    printf '%s\\n' 'FAUST dsp library paths:' 'FAUST architectures paths:'\n"
        "    ;;\n"
        "esac\n"
        "exit 0\n",
        encoding="ascii",
    )
    path.chmod(0o755)


def _create_writable_reported_directories(binary: Path) -> None:
    """Create absent directories this binary reports under a writable parent.

    The sandbox refuses an absent reported path unless ``realpath`` of its
    parent is root-only. A prefix under tmp has to contain those
    directories so the compile can mask them. Root-only parents are left
    absent.
    """
    for path in _reported_faust_directories(binary):
        if path.exists():
            continue
        parent = Path(os.path.realpath(path)).parent
        info = parent.stat()
        if info.st_uid == 0 and stat.S_ISDIR(info.st_mode) and info.st_mode & 0o022 == 0:
            continue
        path.mkdir(parents=True, exist_ok=True)


def _prefix_library_dirs(binary: Path) -> None:
    prefix = binary.parent.parent
    for path in (
        prefix / "share" / "faust",
        prefix / "lib" / "faust",
        binary.parent / "share" / "faust",
    ):
        path.mkdir(parents=True, exist_ok=True)


def test_native_compile_refuses_a_share_tampered_after_the_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "2edec0537f53"
    _copy_library_checkout(checkout)
    monkeypatch.setenv("FAUSTCODER_LIBRARIES", str(checkout))
    share_directory()

    def tamper_after_hash() -> Path:
        path = libraries.share_directory()
        maths = path / "maths.lib"
        maths.write_bytes(maths.read_bytes() + b"PWNED = 42;\n")
        return path

    monkeypatch.setattr("faustcoder.compiler.share_directory", tamper_after_hash)
    monkeypatch.setattr("faustcoder.compiler._require_native_faust", lambda: "/usr/bin/faust")

    def fail_run(*_args: object, **_kwargs: object) -> SandboxRun:
        raise AssertionError("native compile started after a tampered snapshot")

    monkeypatch.setattr("faustcoder.compiler.run_in_sandbox", fail_run)
    with pytest.raises(SandboxError, match="share"):
        compile_native("process = _;\n")


def _hold_share_lock(path: Path) -> subprocess.Popen[bytes]:
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import fcntl, os, sys, time\n"
            "fd = os.open(sys.argv[1], os.O_CREAT | os.O_RDWR, 0o644)\n"
            "fcntl.flock(fd, fcntl.LOCK_EX)\n"
            "print('held', flush=True)\n"
            "time.sleep(30)\n",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert _read_line(process, 5) == b"held\n"
    except Exception:
        process.kill()
        process.wait(timeout=5)
        raise
    return process


def _read_line(process: subprocess.Popen[bytes], timeout: float) -> bytes:
    assert process.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    if not selector.select(timeout):
        process.kill()
        err = process.stderr.read() if process.stderr is not None else b""
        raise AssertionError(err.decode() or "share-lock holder produced no output")
    return process.stdout.readline()


def test_sibling_import_from_the_same_directory_compiles() -> None:
    compiled = compile_directory(FIXTURES / "multi", "main.dsp")
    assert compiled.receipt["exit_code"] == 0, compiled.diagnostics
    assert compiled.receipt["diagnostic_class"] == "ok"


@pytest.mark.parametrize("entry", _MULTI_FILE_COMPILE)
def test_faust_multi_file_example_compiles(entry: str) -> None:
    compiled = compile_directory(
        _examples(), entry, limits=ResourceLimits(timeout_s=60)
    )
    assert compiled.receipt["exit_code"] == 0, compiled.diagnostics
    assert compiled.receipt["diagnostic_class"] == "ok"


@pytest.mark.parametrize("entry", _MULTI_FILE_EXCLUDED)
def test_multi_file_ffunction_is_an_exclusion_not_other(entry: str) -> None:
    source = (_examples() / entry).read_bytes().decode("utf-8")
    with pytest.raises(CompilerExclusion) as caught:
        compile_source(source)
    assert "ffunction" in caught.value.exclusion.reason
    assert caught.value.exclusion.group == "multi_file_ffunction"


def test_stk_ffunction_files_are_recorded_exclusions() -> None:
    recorded = [item for item in exclusions() if item.group == "stk_ffunction"]
    assert [item.path for item in recorded] == [
        "physicalModeling/faust-stk/bass.dsp",
        "physicalModeling/faust-stk/harpsi.dsp",
        "physicalModeling/faust-stk/modalBar.dsp",
        "physicalModeling/faust-stk/piano.dsp",
        "physicalModeling/faust-stk/voiceForm.dsp",
    ]
    root = _examples()
    for item in recorded:
        source = (root / item.path).read_bytes().decode("utf-8")
        assert hashlib.sha256(source.encode("utf-8")).hexdigest() == item.sha256
        assert "ffunction" in item.reason
        with pytest.raises(CompilerExclusion) as caught:
            compile_source(source)
        assert caught.value.exclusion.path == item.path


def test_thin_plate_compiles_within_the_stack_bound() -> None:
    assert NODE_STACK_SIZE_KB == 8192
    assert f"--stack-size={NODE_STACK_SIZE_KB}" in NODE_SANDBOX_FLAGS
    source = (
        _examples() / "physicalModeling" / "fds" / "2dKirchhoffThinPlate.dsp"
    ).read_bytes().decode("utf-8")
    compiled = compile_source(source, limits=ResourceLimits(timeout_s=60))
    assert compiled.receipt["exit_code"] == 0, compiled.diagnostics
    assert compiled.receipt["diagnostic_class"] == "ok"


def test_unshare_path_defaults_to_the_system_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FAUSTCODER_UNSHARE", raising=False)
    system = unshare_executable()
    assert Path(system).name == "unshare"
    monkeypatch.setenv("FAUSTCODER_UNSHARE", system)
    assert unshare_executable() == str(Path(system).resolve())
    monkeypatch.setenv("FAUSTCODER_UNSHARE", str(tmp_path / "missing-unshare"))
    with pytest.raises(SandboxError, match="FAUSTCODER_UNSHARE"):
        unshare_executable()
    monkeypatch.setenv("FAUSTCODER_UNSHARE", "unshare")
    with pytest.raises(SandboxError, match="absolute"):
        unshare_executable()


def test_configured_unshare_executes_in_sandbox(tmp_path: Path) -> None:
    # Preserve the dedicated AppArmor-approved binary on self-hosted runners.
    run = run_in_sandbox(
        ["/bin/true"],
        stdin=b"",
        workdir=tmp_path,
        limits=ResourceLimits(timeout_s=5),
    )
    assert run.returncode == 0
    assert run.stop_reason == ""


def _copy_library_checkout(destination: Path) -> None:
    source = library_root()
    for path in source.rglob("*.lib"):
        if path.is_symlink() or not path.is_file():
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def test_tampered_share_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    checkout = tmp_path / "2edec0537f53"
    _copy_library_checkout(checkout)
    monkeypatch.setenv("FAUSTCODER_LIBRARIES", str(checkout))
    share = share_directory()
    maths = share / "maths.lib"
    maths.write_bytes(maths.read_bytes() + b"PWNED = 42;\n")
    assert (share / ".tree-sha256").is_file()
    with pytest.raises(SandboxError, match="share"):
        compile_source("process = ma.PWNED;\n")
    assert share.is_dir()


def test_deleting_a_tampered_share_restages_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "2edec0537f53"
    _copy_library_checkout(checkout)
    monkeypatch.setenv("FAUSTCODER_LIBRARIES", str(checkout))
    share = share_directory()
    maths = share / "maths.lib"
    maths.write_bytes(maths.read_bytes() + b"PWNED = 42;\n")
    with pytest.raises(SandboxError, match="share"):
        share_directory()
    shutil.rmtree(share)
    restored = share_directory()
    assert canonical_tree_sha256(restored) == FAUSTLIBRARIES_SHARE_SHA256
    assert b"PWNED" not in (restored / "maths.lib").read_bytes()


def test_compiler_exclusion_of_model_output_is_a_failure_not_a_pass() -> None:
    # When rewards land, this exception is a failure. It must not become a
    # pass or an ungraded receipt.
    source = (_examples() / "SAM/effects/effects.dsp").read_bytes().decode("utf-8")
    with pytest.raises(CompilerExclusion) as caught:
        compile_source(source)
    assert caught.value.reward_disposition == "failure"
    assert not hasattr(caught.value, "receipt")


def test_six_of_eight_exclusion_hashes_change_after_t06_normalization() -> None:
    unchanged = []
    changed = []
    root = _examples()
    for item in exclusions():
        source = (root / item.path).read_bytes().decode("utf-8")
        raw = hashlib.sha256(source.encode("utf-8")).hexdigest()
        normalized = hashlib.sha256(normalize_source(source).encode("utf-8")).hexdigest()
        assert raw == item.sha256
        assert normalized == item.normalized_sha256
        assert _exclusion_matches(source, item.path)
        assert _exclusion_matches(normalize_source(source), item.path)
        if item.sha256 == item.normalized_sha256:
            unchanged.append(item.path)
        else:
            changed.append(item.path)
    assert len(changed) == 6
    assert unchanged == [
        "physicalModeling/faust-stk/modalBar.dsp",
        "SAM/effects/effects.dsp",
    ]


def _exclusion_matches(source: str, path: str) -> bool:
    found = exclusion_for_source(source)
    return found is not None and found.path == path


def test_environment_digest_names_the_unshare_binary_actually_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FAUSTCODER_UNSHARE", raising=False)
    path, digest = unshare_identity()
    assert path == str(Path(unshare_executable()).resolve())
    assert digest == hashlib.sha256(Path(path).read_bytes()).hexdigest()
    pin = runtime_pin()
    preimage = environment_preimage(
        compiler="libfaust-wasm",
        faust_version=pin.faust_version,
        lang="wasm",
        options=(),
        pin=pin,
    )
    assert preimage["unshare_path"] == path
    assert preimage["unshare_sha256"] == digest


def test_swapped_unshare_wrapper_changes_the_digest_before_the_canary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path("/opt/faustcoder-canary-identity")
    first = root / "bin" / "fc-unshare-a"
    second = root / "bin" / "fc-unshare-b"
    subprocess.run(["sudo", "rm", "-rf", str(root)], check=True)
    try:
        subprocess.run(
            ["sudo", "install", "-d", "-o", "root", "-g", "root", "-m", "0755", str(first.parent)],
            check=True,
        )
        for path, body in ((first, b"#!/bin/sh\necho a\n"), (second, b"#!/bin/sh\necho b\n")):
            subprocess.run(
                ["sudo", "tee", str(path)],
                input=body,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(["sudo", "chown", "root:root", str(path)], check=True)
            subprocess.run(["sudo", "chmod", "0755", str(path)], check=True)
        pin = runtime_pin()

        def preimage_for(binary: Path) -> dict[str, object]:
            monkeypatch.setenv("FAUSTCODER_UNSHARE", str(binary))
            return environment_preimage(
                compiler="libfaust-wasm",
                faust_version=pin.faust_version,
                lang="wasm",
                options=(),
                pin=pin,
            )

        left = preimage_for(first)
        right = preimage_for(second)
        assert left["unshare_path"] == str(first.resolve())
        assert right["unshare_path"] == str(second.resolve())
        assert left["unshare_sha256"] != right["unshare_sha256"]
        assert hashlib.sha256(canonical_bytes(left)).digest() != hashlib.sha256(
            canonical_bytes(right)
        ).digest()
    finally:
        subprocess.run(["sudo", "rm", "-rf", str(root)], check=False)


def test_user_owned_unshare_wrapper_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapper = tmp_path / "fc-unshare"
    wrapper.write_text("#!/bin/sh\nwhile [ \"$1\" != \"--\" ]; do shift; done\nshift\nexec \"$@\"\n")
    wrapper.chmod(0o755)
    monkeypatch.setenv("FAUSTCODER_UNSHARE", str(wrapper))
    with pytest.raises(SandboxError, match="FAUSTCODER_UNSHARE"):
        unshare_executable()
    link = tmp_path / "unshare-link"
    link.symlink_to("/usr/bin/unshare")
    monkeypatch.setenv("FAUSTCODER_UNSHARE", str(link))
    with pytest.raises(SandboxError, match="regular file"):
        unshare_executable()


def test_root_owned_unshare_wrapper_fails_the_network_canary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path("/opt/faustcoder-canary")
    binary = root / "bin" / "fc-unshare"
    script = "#!/bin/sh\nwhile [ \"$1\" != \"--\" ]; do shift; done\nshift\nexec \"$@\"\n"
    subprocess.run(["sudo", "rm", "-rf", str(root)], check=True)
    try:
        subprocess.run(["sudo", "install", "-d", "-o", "root", "-g", "root", "-m", "0755", str(binary.parent)], check=True)
        subprocess.run(["sudo", "tee", str(binary)], input=script.encode(), check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["sudo", "chown", "root:root", str(binary)], check=True)
        subprocess.run(["sudo", "chmod", "0755", str(binary)], check=True)
        monkeypatch.setenv("FAUSTCODER_UNSHARE", str(binary))
        assert unshare_executable() == str(binary)
        with pytest.raises(SandboxError, match="canary"):
            compile_source("process = _;\n", limits=ResourceLimits(timeout_s=20))
    finally:
        subprocess.run(["sudo", "rm", "-rf", str(root)], check=False)

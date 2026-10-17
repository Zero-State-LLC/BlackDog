"""Compiler harness: receipts, diagnostics, and the sandbox."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import os
import selectors
import shutil
import subprocess
import sys
import time
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
from faustcoder.sandbox import SandboxRun, faust_fallback_mounts, unshare_identity
from faustcoder.compiler import (
    FAUSTLIBRARIES_PIN,
    FAUSTLIBRARIES_PIN_VERSION,
    _native_command,
    canonical_output_bytes,
    environment_preimage,
    worker_directory,
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
    # --stack-size=8192 lets this unroll until the worker SIGSEGVs. The
    # catchable "Maximum call stack size exceeded" path is what a smaller
    # stack produced. Either way the receipt stays exit 126 internal.
    compiled = compile_source(_source("recurse.dsp"), lang="wasm")
    assert compiled.receipt["exit_code"] == 126
    assert compiled.receipt["diagnostic_class"] == "internal"
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


def test_faust_fallback_mounts_skip_missing_and_refuse_symlinks(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    present = tmp_path / "faust"
    present.mkdir()
    link = tmp_path / "link"
    link.symlink_to(present)
    assert faust_fallback_mounts((missing, present)) == (present.resolve(),)
    with pytest.raises(SandboxError, match="symlink"):
        faust_fallback_mounts((link,))
    defaults = (Path("/usr/local/share/faust"), Path("/usr/share/faust"))
    if any(path.is_symlink() for path in defaults):
        with pytest.raises(SandboxError, match="symlink"):
            faust_fallback_mounts()
    else:
        assert faust_fallback_mounts() == tuple(
            path.resolve() for path in defaults if path.is_dir()
        )


def test_native_compile_uses_a_hashed_private_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = share_directory()
    monkeypatch.setattr("faustcoder.compiler._require_native_faust", lambda: "/usr/bin/faust")

    def fake_run(command: list[str], **kwargs: object) -> SandboxRun:
        include = Path(command[command.index("-I") + 1])
        assert include != live
        assert include.parent == Path(str(kwargs["workdir"]))
        assert canonical_tree_sha256(include) == FAUSTLIBRARIES_SHARE_SHA256
        assert kwargs["mask_directories"] == faust_fallback_mounts()
        return SandboxRun(0, b"int process(){return 0;}\n", b"", "", False, False)

    monkeypatch.setattr("faustcoder.compiler.run_in_sandbox", fake_run)
    compiled = compile_native("process = _;\n")
    assert compiled.receipt["exit_code"] == 0
    assert compiled.receipt["compiler"] == "faust-cli"


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
    run = run_in_sandbox(
        ["/bin/true"],
        stdin=b"",
        workdir=tmp_path,
        limits=ResourceLimits(timeout_s=5),
    )
    assert run.returncode == 0
    assert run.stop_reason == ""
    monkeypatch.setenv("FAUSTCODER_UNSHARE", str(tmp_path / "missing-unshare"))
    with pytest.raises(SandboxError, match="FAUSTCODER_UNSHARE"):
        unshare_executable()
    monkeypatch.setenv("FAUSTCODER_UNSHARE", "unshare")
    with pytest.raises(SandboxError, match="absolute"):
        unshare_executable()


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

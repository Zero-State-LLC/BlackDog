"""Sandboxed Faust compiler receipts (T03, R-005, R-013).

The primary compiler is libfaust from ``@grame/faustwasm`` 0.19.0, driven
through ``faust/worker/compile.mjs``. One subprocess is one compile. The
subprocess is isolated by :mod:`faustcoder.sandbox`.

What this pin can compile
-------------------------
faustwasm 0.19.0 embeds libfaust 2.90.0. ``compiler.version()`` reports
``2.90.0``. That build includes the WebAssembly, Cmajor and AssemblyScript
backends. It does not include the C++ backend: ``-lang cpp`` fails with a
stable diagnostic, ``CPP backend is not built``. ``lang="wasm"`` is the
successful path. ``lang="cpp"`` is still invoked and recorded; it does not
pretend to succeed.

The native Faust 2.88.0 CLI is a cross-check, not the primary compiler.
``compile_native`` and ``cross_check_native`` raise
``NativeFaustUnavailable`` when ``faust`` is absent or is not 2.88.0.
CI does not install native Faust, so those tests skip there. The same
job clears Ubuntu's unprivileged-userns AppArmor restriction so
``unshare --net --map-root-user`` can create the network namespace
(see :mod:`faustcoder.sandbox`). Versions
differ (wasm libfaust 2.90.0 versus native 2.88.0), so the cross-check
compares ``diagnostic_class``, not output bytes.

Receipt digest
--------------
The stored payload is a CompilerReceipt
(``schemas/compiler-receipt.schema.json``). T02 defines ``artifact_id`` as
the SHA-256 of that whole payload, so ``duration_ms`` is part of the
artifact id. The reproducible receipt digest is different on purpose.

``EXCLUDED_TIMING_FIELDS`` is exactly ``("duration_ms",)``.
``reproducible_receipt_digest`` hashes the canonical JSON of the receipt
with that key removed. No other receipt field is removed. In particular
``exit_code``, ``stdout_digest``, ``stderr_digest``, ``faust_version``,
``command``, ``options``, ``diagnostic_class`` and ``environment_digest``
stay in the hash. The envelope fields ``created_at``, ``producer`` and
``parents`` are not part of the payload, so they are not part of either
digest. The first stored envelope for a payload wins (T02).

``duration_ms`` is the wall-clock time of the sandboxed process, truncated
to milliseconds. A source rejected for size never starts the process and
records ``0``.

``environment_digest`` hashes a canonical object with ``compiler``,
``faust_version``, ``faustwasm`` (``0.19.0`` or ``""`` for the native CLI),
``lang``, ``network`` (``unshare-net-userns``), ``node_flags`` (the
identity flags, not per-run temp paths) and ``options``. Host name, Node
patch version and the job directory are not included.

``command`` records the logical compiler invocation, including
``--faustwasm=0.19.0``. The schema has no separate faustwasm field, so the
version lives there and inside ``environment_digest``.

``stdout_digest`` hashes the canonical output bundle: for each output file
in lexicographic filename order, the UTF-8 filename, a newline, an 8-byte
big-endian length, and the file bytes. Wasm compiles write ``output.wasm``
and ``output.json`` (the compiler's JSON text, not re-serialized). A
failed compile hashes the empty bundle. Timeout, resource and internal
failures also hash the empty bundle; partial output is discarded.

``stderr_digest`` hashes the diagnostic text (UTF-8). Line endings are
``\\n``. A successful compile with no diagnostic hashes the empty string.
The text itself is not a schema field. ``Compilation.diagnostics`` keeps
it in memory.

Diagnostic class
----------------
``diagnostic_class`` uses the ADR-0004 / schema enum. Mapping from the
compiler text, first match:

- success and the text contains ``WARNING`` -> ``warning``
- success -> ``ok``
- ``syntax error`` -> ``parse_error``
- ``undefined symbol`` -> ``other`` (unbound identifier; the enum has no
  separate value)
- ``too much arguments`` or ``too few arguments`` -> ``arity_error``
- ``number of outputs``, ``number of inputs``, ``type error`` or
  ``incompatible type`` -> ``type_error`` (channel shape included)
- anything else the compiler returns -> ``other``

Harness failures override that text:

- wall clock or CPU backstop -> ``timeout``, exit 124
- memory, output size or source size -> ``other``, exit 125, diagnostic
  ``resource limit: ...``
- worker crash or an unreadable result -> ``other``, exit 126, diagnostic
  ``internal: ...``

Compiler rejection of the source is exit 1. Exit 0 is ``ok`` or ``warning``.

Options are an allowlist (``-double``, ``-single``, ``-vec``, ``-scal``,
``-inpl``, and ``-ct``, ``-es``, ``-mcd``, ``-ftz`` with a non-negative
integer). Path-taking flags such as ``-I`` and ``-o`` are rejected. The
worker also rejects any option that is not a short flag or an integer.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from faustcoder.canonical import build_envelope, canonical_bytes, content_digest_for
from faustcoder.sandbox import (
    NODE_SANDBOX_FLAGS,
    ResourceLimits,
    SandboxError,
    SandboxRun,
    node_command,
    run_in_sandbox,
)
from faustcoder.schemas import validate
from faustcoder.store import ArtifactStore

FAUSTWASM_VERSION = "0.19.0"
NATIVE_FAUST_VERSION = "2.88.0"
EXCLUDED_TIMING_FIELDS = ("duration_ms",)
_COMPILER_SCHEMA = "compiler-receipt.schema.json"
_FLAGS = {"-double", "-single", "-vec", "-scal", "-inpl"}
_FLAGS_WITH_INT = {"-ct", "-es", "-mcd", "-ftz"}
_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")
_OUTPUT_NAME = re.compile(r"^output\.[a-z0-9]+$")
_RUNTIME_FILES = (
    "libfaust-wasm.js",
    "libfaust-wasm.wasm",
    "libfaust-wasm.data",
)


class CompilerHarnessError(Exception):
    """The harness failed before it could classify a compile."""


class NativeFaustUnavailable(CompilerHarnessError):
    """The native Faust 2.88.0 CLI is not available for a cross-check."""


@dataclass(frozen=True)
class Compilation:
    """One compile.

    ``receipt`` validates against the CompilerReceipt schema. ``diagnostics``
    is the exact text hashed into ``stderr_digest``. ``reproducible_digest``
    excludes ``duration_ms`` and nothing else.
    """

    receipt: dict[str, Any]
    diagnostics: str
    reproducible_digest: str


@dataclass(frozen=True)
class CrossCheck:
    """Wasm compile beside a native 2.88.0 C++ compile of the same source."""

    wasm: Compilation
    native: Compilation

    @property
    def diagnostic_class_matches(self) -> bool:
        return self.wasm.receipt["diagnostic_class"] == self.native.receipt["diagnostic_class"]


def worker_directory() -> Path:
    """Return the ``faust/worker`` directory that holds the Node worker."""
    override = os.environ.get("FAUSTCODER_WORKER_DIR")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parent.parent / "faust" / "worker"


def classify_diagnostic(diagnostics: str, *, compile_ok: bool) -> str:
    """Map compiler text to an ADR-0004 ``diagnostic_class``."""
    if compile_ok:
        if "WARNING" in diagnostics:
            return "warning"
        return "ok"
    folded = diagnostics.lower()
    if "syntax error" in folded:
        return "parse_error"
    if "undefined symbol" in folded:
        return "other"
    if "too much arguments" in folded or "too few arguments" in folded:
        return "arity_error"
    if (
        "number of outputs" in folded
        or "number of inputs" in folded
        or "type error" in folded
        or "incompatible type" in folded
    ):
        return "type_error"
    return "other"


def reproducible_receipt_digest(receipt: Mapping[str, Any]) -> str:
    """Return ``sha256:`` of the receipt with timing fields removed.

    The removed keys are ``EXCLUDED_TIMING_FIELDS`` (``duration_ms`` only).
    The hashed object is not schema-valid, because ``duration_ms`` is
    required on a stored CompilerReceipt. ``artifact_id`` still hashes the
    stored payload, including ``duration_ms``.
    """
    body = {key: value for key, value in receipt.items() if key not in EXCLUDED_TIMING_FIELDS}
    return content_digest_for(body)


def canonical_output_bytes(files: Sequence[tuple[str, bytes]]) -> bytes:
    """Return the stdout bundle hashed into ``stdout_digest``."""
    chunks: list[bytes] = []
    for name, data in sorted(files, key=lambda item: item[0]):
        if _OUTPUT_NAME.fullmatch(name) is None:
            raise CompilerHarnessError(f"invalid output name: {name}")
        chunks.append(name.encode("utf-8") + b"\n" + len(data).to_bytes(8, "big") + data)
    return b"".join(chunks)


def compile_source(
    source: str,
    *,
    lang: str = "wasm",
    options: Sequence[str] = (),
    limits: ResourceLimits | None = None,
) -> Compilation:
    """Compile ``source`` with libfaust-wasm and return a receipt.

    ``lang`` is ``wasm`` or ``cpp``. A Faust rejection is a receipt with
    exit code 1, not an exception. A missing sandbox tool raises
    ``SandboxError``.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    if lang not in {"wasm", "cpp"}:
        raise ValueError("lang must be 'wasm' or 'cpp'")
    checked = _validate_options(options)
    bounds = limits or ResourceLimits()
    source_bytes = source.encode("utf-8")
    if len(source_bytes) > bounds.source_bytes:
        return _harness_receipt(
            source_bytes,
            lang=lang,
            options=checked,
            stop_reason="source",
            duration_ms=0,
            faust_version="unknown",
        )
    _installed_faustwasm_version()
    script = worker_directory() / "compile.mjs"
    if not script.is_file():
        raise SandboxError(f"compiler worker is missing: {script}")
    request = json.dumps(
        {"source": source, "lang": lang, "options": list(checked)},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="faustcoder-") as temporary:
        workdir = Path(temporary)
        _stage_runtime(workdir)
        command = node_command(
            script,
            [str(workdir)],
            read_paths=[worker_directory(), workdir],
            write_paths=[workdir],
        )
        run = run_in_sandbox(command, stdin=request, workdir=workdir, limits=bounds)
        duration_ms = int((time.monotonic() - started) * 1000)
        if run.stop_reason:
            return _harness_receipt(
                source_bytes,
                lang=lang,
                options=checked,
                stop_reason=run.stop_reason,
                duration_ms=duration_ms,
                faust_version="unknown",
            )
        return _receipt_from_worker(
            source_bytes,
            lang=lang,
            options=checked,
            limits=bounds,
            workdir=workdir,
            run=run,
            duration_ms=duration_ms,
        )


def compile_native(
    source: str,
    *,
    options: Sequence[str] = (),
    limits: ResourceLimits | None = None,
) -> Compilation:
    """Compile ``source`` with the native Faust 2.88.0 CLI, ``-lang cpp``.

    Raises ``NativeFaustUnavailable`` when the cross-check cannot run.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    checked = _validate_options(options)
    bounds = limits or ResourceLimits()
    binary = _require_native_faust()
    source_bytes = source.encode("utf-8")
    if len(source_bytes) > bounds.source_bytes:
        return _harness_receipt(
            source_bytes,
            lang="cpp",
            options=checked,
            stop_reason="source",
            duration_ms=0,
            faust_version=NATIVE_FAUST_VERSION,
            compiler="faust-cli",
        )
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="faustcoder-") as temporary:
        workdir = Path(temporary)
        (workdir / "input.dsp").write_bytes(source_bytes)
        command = [binary, "-lang", "cpp", *checked, "input.dsp"]
        run = run_in_sandbox(command, stdin=b"", workdir=workdir, limits=bounds, cwd=workdir)
        duration_ms = int((time.monotonic() - started) * 1000)
        if run.stop_reason:
            return _harness_receipt(
                source_bytes,
                lang="cpp",
                options=checked,
                stop_reason=run.stop_reason,
                duration_ms=duration_ms,
                faust_version=NATIVE_FAUST_VERSION,
                compiler="faust-cli",
            )
        diagnostics = _normalize_diagnostics(run.stderr.decode("utf-8", errors="replace"), workdir)
        compile_ok = run.returncode == 0
        if not compile_ok and diagnostics == "":
            diagnostics = "compiler returned failure\n"
        outputs = [("output.cpp", run.stdout)] if compile_ok else []
        return _build(
            source_bytes,
            compiler="faust-cli",
            faust_version=NATIVE_FAUST_VERSION,
            lang="cpp",
            options=checked,
            compile_ok=compile_ok,
            diagnostics=diagnostics,
            outputs=outputs,
            duration_ms=duration_ms,
        )


def cross_check_native(
    source: str,
    *,
    options: Sequence[str] = (),
    limits: ResourceLimits | None = None,
) -> CrossCheck:
    """Compile with libfaust-wasm and with native Faust 2.88.0.

    The native compiler is checked before the wasm compile so a missing
    binary does not spend a worker run.
    """
    _require_native_faust()
    return CrossCheck(
        wasm=compile_source(source, lang="wasm", options=options, limits=limits),
        native=compile_native(source, options=options, limits=limits),
    )


def native_faust_version() -> str | None:
    """Return the installed ``faust`` version, or None when it is absent."""
    binary = shutil.which("faust")
    if binary is None:
        return None
    try:
        completed = subprocess.run(
            [binary, "-v"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = _VERSION_RE.search(completed.stdout + completed.stderr)
    if match is None:
        return None
    return match.group(1)


def store_compiler_receipt(
    store: ArtifactStore,
    receipt: Mapping[str, Any],
    *,
    created_at: str,
    producer: str = "faustcoder.compiler",
    parents: Sequence[str] = (),
) -> str:
    """Validate ``receipt`` and store it. Return the artifact id."""
    if not isinstance(receipt, dict):
        raise CompilerHarnessError("receipt must be a JSON object")
    validate(receipt, _COMPILER_SCHEMA)
    envelope = build_envelope(
        schema_version="0.3.0",
        created_at=created_at,
        producer=producer,
        parents=list(parents),
        payload=receipt,
    )
    return store.put(envelope)


def _require_native_faust() -> str:
    binary = shutil.which("faust")
    if binary is None:
        raise NativeFaustUnavailable(
            "faust binary is absent; the native 2.88.0 cross-check is optional "
            "and CI does not install Faust"
        )
    version = native_faust_version()
    if version != NATIVE_FAUST_VERSION:
        raise NativeFaustUnavailable(
            f"faust binary reports {version}, expected {NATIVE_FAUST_VERSION}"
        )
    return binary


def _installed_faustwasm_version() -> str:
    manifest = worker_directory() / "node_modules" / "@grame" / "faustwasm" / "package.json"
    if not manifest.is_file():
        raise SandboxError(
            "faustwasm is not installed; run npm ci --ignore-scripts in faust/worker"
        )
    version = json.loads(manifest.read_text(encoding="utf-8")).get("version")
    if version != FAUSTWASM_VERSION:
        raise SandboxError(
            f"installed @grame/faustwasm is {version}, expected {FAUSTWASM_VERSION}"
        )
    return version


def _stage_runtime(workdir: Path) -> None:
    source = worker_directory() / "node_modules" / "@grame" / "faustwasm" / "libfaust-wasm"
    target = workdir / "runtime"
    target.mkdir(mode=0o700)
    for name in _RUNTIME_FILES:
        origin = source / name
        if not origin.is_file():
            raise SandboxError(f"missing faustwasm runtime file: {name}")
        shutil.copyfile(origin, target / name)


def _validate_options(options: Sequence[str]) -> tuple[str, ...]:
    if isinstance(options, (str, bytes)) or not isinstance(options, Sequence):
        raise ValueError("options must be a sequence of strings")
    parsed: list[str] = []
    seen: set[str] = set()
    items = list(options)
    index = 0
    while index < len(items):
        flag = items[index]
        if not isinstance(flag, str):
            raise ValueError("options must be strings")
        if flag in _FLAGS:
            if flag in seen:
                raise ValueError(f"duplicate option: {flag}")
            seen.add(flag)
            parsed.append(flag)
            index += 1
            continue
        if flag in _FLAGS_WITH_INT:
            if flag in seen:
                raise ValueError(f"duplicate option: {flag}")
            if index + 1 >= len(items):
                raise ValueError(f"{flag} requires an integer")
            value = items[index + 1]
            if not isinstance(value, str) or re.fullmatch(r"[0-9]+", value) is None:
                raise ValueError(f"{flag} requires an integer")
            seen.add(flag)
            parsed.extend([flag, value])
            index += 2
            continue
        raise ValueError(f"option is not allowed: {flag}")
    if "-double" in seen and "-single" in seen:
        raise ValueError("choose either -double or -single")
    if "-vec" in seen and "-scal" in seen:
        raise ValueError("choose either -vec or -scal")
    return tuple(parsed)


def _receipt_from_worker(
    source_bytes: bytes,
    *,
    lang: str,
    options: tuple[str, ...],
    limits: ResourceLimits,
    workdir: Path,
    run: SandboxRun,
    duration_ms: int,
) -> Compilation:
    result_path = workdir / "result.json"
    if run.returncode != 0 or not result_path.is_file():
        return _harness_receipt(
            source_bytes,
            lang=lang,
            options=options,
            stop_reason="internal",
            duration_ms=duration_ms,
            faust_version="unknown",
        )
    try:
        body = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _harness_receipt(
            source_bytes,
            lang=lang,
            options=options,
            stop_reason="internal",
            duration_ms=duration_ms,
            faust_version="unknown",
        )
    if not isinstance(body, dict) or body.get("faustwasm_version") != FAUSTWASM_VERSION:
        return _harness_receipt(
            source_bytes,
            lang=lang,
            options=options,
            stop_reason="internal",
            duration_ms=duration_ms,
            faust_version="unknown",
        )
    faust_version = body.get("libfaust_version")
    if not isinstance(faust_version, str) or re.fullmatch(r"[\w.+-]{1,64}", faust_version) is None:
        faust_version = "unknown"
    diagnostics = body.get("diagnostics")
    if not isinstance(diagnostics, str):
        diagnostics = ""
    diagnostics = _normalize_diagnostics(diagnostics, workdir)
    compile_ok = body.get("compile_ok") is True
    outputs: list[tuple[str, bytes]] = []
    if compile_ok:
        names = body.get("output_files")
        if not isinstance(names, list) or not names:
            return _harness_receipt(
                source_bytes,
                lang=lang,
                options=options,
                stop_reason="internal",
                duration_ms=duration_ms,
                faust_version=faust_version,
            )
        total = 0
        for name in names:
            if not isinstance(name, str) or _OUTPUT_NAME.fullmatch(name) is None:
                return _harness_receipt(
                    source_bytes,
                    lang=lang,
                    options=options,
                    stop_reason="internal",
                    duration_ms=duration_ms,
                    faust_version=faust_version,
                )
            path = workdir / name
            if path.is_symlink() or not path.is_file():
                return _harness_receipt(
                    source_bytes,
                    lang=lang,
                    options=options,
                    stop_reason="internal",
                    duration_ms=duration_ms,
                    faust_version=faust_version,
                )
            size = path.stat().st_size
            total += size
            if size > limits.output_bytes or total > limits.output_bytes:
                return _harness_receipt(
                    source_bytes,
                    lang=lang,
                    options=options,
                    stop_reason="output",
                    duration_ms=duration_ms,
                    faust_version=faust_version,
                )
            outputs.append((name, path.read_bytes()))
    if not compile_ok and diagnostics == "":
        diagnostics = "compiler returned failure\n"
    return _build(
        source_bytes,
        compiler="libfaust-wasm",
        faust_version=faust_version,
        lang=lang,
        options=options,
        compile_ok=compile_ok,
        diagnostics=diagnostics,
        outputs=outputs,
        duration_ms=duration_ms,
    )


def _harness_receipt(
    source_bytes: bytes,
    *,
    lang: str,
    options: tuple[str, ...],
    stop_reason: str,
    duration_ms: int,
    faust_version: str,
    compiler: str = "libfaust-wasm",
) -> Compilation:
    messages = {
        "timeout": "timeout: wall clock limit exceeded\n",
        "memory": "resource limit: memory\n",
        "output": "resource limit: output size\n",
        "source": "resource limit: source size\n",
        "internal": "internal: worker failed\n",
        "cpu": "timeout: wall clock limit exceeded\n",
    }
    diagnostics = messages.get(stop_reason, "internal: worker failed\n")
    reason = "timeout" if stop_reason in {"timeout", "cpu"} else stop_reason
    return _build(
        source_bytes,
        compiler=compiler,
        faust_version=faust_version,
        lang=lang,
        options=options,
        compile_ok=False,
        diagnostics=diagnostics,
        outputs=[],
        duration_ms=duration_ms,
        harness=reason,
    )


def _build(
    source_bytes: bytes,
    *,
    compiler: str,
    faust_version: str,
    lang: str,
    options: tuple[str, ...],
    compile_ok: bool,
    diagnostics: str,
    outputs: Sequence[tuple[str, bytes]],
    duration_ms: int,
    harness: str | None = None,
) -> Compilation:
    if harness == "timeout":
        diagnostic_class = "timeout"
        exit_code = 124
    elif harness in {"memory", "output", "source"}:
        diagnostic_class = "other"
        exit_code = 125
    elif harness == "internal":
        diagnostic_class = "other"
        exit_code = 126
    elif compile_ok:
        diagnostic_class = classify_diagnostic(diagnostics, compile_ok=True)
        exit_code = 0
    else:
        diagnostic_class = classify_diagnostic(diagnostics, compile_ok=False)
        exit_code = 1
    if harness is not None:
        outputs = []
    stdout = canonical_output_bytes(outputs)
    preimage = {
        "compiler": compiler,
        "faust_version": faust_version,
        "faustwasm": FAUSTWASM_VERSION if compiler == "libfaust-wasm" else "",
        "lang": lang,
        "network": "unshare-net-userns",
        "node_flags": list(NODE_SANDBOX_FLAGS) if compiler == "libfaust-wasm" else [],
        "options": list(options),
    }
    command = _logical_command(compiler, faust_version, lang, options)
    receipt = {
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "faust_version": faust_version,
        "command": command,
        "exit_code": exit_code,
        "stdout_digest": _digest(stdout),
        "stderr_digest": _digest(diagnostics.encode("utf-8")),
        "duration_ms": duration_ms,
        "environment_digest": _digest(canonical_bytes(preimage)),
        "compiler": compiler,
        "lang": lang,
        "options": list(options),
        "diagnostic_class": diagnostic_class,
    }
    validate(receipt, _COMPILER_SCHEMA)
    return Compilation(
        receipt=receipt,
        diagnostics=diagnostics,
        reproducible_digest=reproducible_receipt_digest(receipt),
    )


def _logical_command(
    compiler: str, faust_version: str, lang: str, options: tuple[str, ...]
) -> list[str]:
    if compiler == "libfaust-wasm":
        command = ["libfaust-wasm", f"--faustwasm={FAUSTWASM_VERSION}"]
        if faust_version != "unknown":
            command.append(f"--libfaust={faust_version}")
    else:
        command = ["faust"]
        if faust_version != "unknown":
            command.append(f"--faust={faust_version}")
    command.extend(["-lang", lang, *options])
    return command


def _normalize_diagnostics(text: str, workdir: Path) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    for token in {str(workdir), os.path.realpath(workdir)}:
        if token:
            cleaned = cleaned.replace(token, "workdir")
    if cleaned == "":
        return ""
    return cleaned if cleaned.endswith("\n") else f"{cleaned}\n"


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()

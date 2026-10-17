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
CI does not install native Faust, so those tests skip there. The pytest
job clears Ubuntu's unprivileged-userns AppArmor restriction only on
GitHub-hosted runners (see :mod:`faustcoder.sandbox` and
``docs/runbooks/compiler-harness.md``). Versions
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
``faust_version``, ``faustlibraries_version`` (``vl.version`` of the staged
pin, ``2.80.0``), ``faustlibraries_commit`` (``2edec0537f53``),
``faustlibraries_tree_sha256`` (the canonical checkout),
``faustlibraries_share_sha256`` (the tree mounted at ``/usr/share/faust``,
checkout paths plus the flat ``old/*.lib`` and ``dx7/*.lib`` copies),
``bundled_faustlibraries_version`` (the triplet still embedded in
``libfaust-wasm.data``, ``2.74.2`` for wasm and ``""`` for the native CLI),
``faustwasm`` (``0.19.0`` or ``""``), ``lang``,
``libfaust_wasm_data_sha256``, ``network`` (``unshare-net-userns``),
``node`` (major.minor only), ``node_flags`` (the identity flags, including
``--stack-size=8192``, not per-run temp paths), ``options``,
``runtime_sha256`` (sha256 of the staged ``libfaust-wasm.js``, ``.wasm``
and ``.data``), ``unshare_path`` (the resolved path of the ``unshare``
binary this process executes, including the system binary when
``FAUSTCODER_UNSHARE`` is unset), ``unshare_sha256`` (sha256 of that
file) and ``user_map`` (``current``). Host name, Node patch version, the
job directory and the host library path are not included. The unshare
path is included because a different binary is a different sandbox. A
swapped wrapper changes ``environment_digest`` before the network canary
runs.

The libfaust version is resolved once per runtime hash and reused on
every receipt from that runtime, including timeout, memory, output and
internal receipts. ``faustlibraries_share_sha256`` is the hash of the
share directory, recomputed on every compile, and of the bytes the worker
writes into the Emscripten filesystem. Those two hashes have to match the
pin. A mismatch raises before a receipt is written. One changed byte of
that mounted tree changes the digest. A checkout that does not match the
pin is refused the same way.

Before every wasm compile the worker replaces ``/usr/share/faust`` in the
Emscripten filesystem with that pinned share, then hashes exactly those
mounted bytes and returns the digest. The harness refuses the result
unless it is the pinned share hash. In the same process, before compiling,
the worker reads ``/proc/net/dev`` and requires the only interface to be
``lo``, then requires a connect to fail. The native 2.88.0 cross-check
passes the same directory as ``-I``. The logical ``command`` records
``--faustlibraries=2edec0537f53`` and not the host path. The tree is
fetched on the host. The sandbox does not download it. Do not run a T06
or T07 compile check, and do not feed a receipt into a reward, against a
harness that skipped this staging.

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
- ``undefined symbol`` -> ``unbound_symbol``
- ``too much arguments`` or ``too few arguments`` -> ``arity_error``
- ``number of outputs``, ``number of inputs``, ``type error`` or
  ``incompatible type`` -> ``type_error`` (channel shape included)
- anything else the compiler returns -> ``other``

Harness failures override that text:

- wall clock or CPU backstop -> ``timeout``, exit 124
- memory, output size or source size -> ``resource_limit``, exit 125,
  diagnostic ``resource limit: ...``
- a JS runtime exception (``allocate is not defined``, ``Maximum call
  stack size exceeded``, ``ReferenceError``, ``RangeError``, ``TypeError``,
  and the same family), a remote ``import`` / ``library`` / ``component``
  URL rejected before spawn, a worker crash (including ``SIGSEGV`` from a
  recursive source once ``--stack-size=8192`` lets it pass the old V8
  limit), or an unreadable result -> ``internal``, exit 126

Compiler rejection of the source is exit 1. Exit 0 is ``ok`` or ``warning``.

Reward consumers key on the pair ``(exit_code, diagnostic_class)``.
Exit codes 124 and above are ungraded: they are not rungs on the R-005
ladder. A harness failure must not score as ``other`` or as a compiler
rejection. ``unbound_symbol`` is a compiler class (exit 1). See
``docs/runbooks/compiler-harness.md`` and ADR-0005. A receipt whose exit
is 124 or above is not evidence that another operator reproduced a
successful compile of that source; compare ``environment_digest`` for the
pin, and ``reproducible_digest`` only across receipts with the same exit
and diagnostic class.

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
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from faustcoder.canonical import build_envelope, canonical_bytes, content_digest_for
from faustcoder.exclusions import CompilerExclusion, exclusion_for_source
from faustcoder.libraries import (
    FAUSTLIBRARIES_COMMIT,
    FAUSTLIBRARIES_SHARE_SHA256,
    FAUSTLIBRARIES_VERSION,
    require_library_tree,
    share_directory,
)
from faustcoder.sandbox import (
    NODE_SANDBOX_FLAGS,
    ResourceLimits,
    SandboxError,
    SandboxRun,
    node_command,
    node_executable,
    run_in_sandbox,
    unshare_identity,
)
from faustcoder.schemas import validate
from faustcoder.store import ArtifactStore

FAUSTWASM_VERSION = "0.19.0"
NATIVE_FAUST_VERSION = "2.88.0"
COMPILER_SCHEMA_VERSION = "0.3.2"
# ADR-0004 / T05 pin. Staged into /usr/share/faust before every compile.
# The wasm bundle's version.lib is still 2.74.2 and is not the compile set.
FAUSTLIBRARIES_PIN = FAUSTLIBRARIES_COMMIT
FAUSTLIBRARIES_PIN_VERSION = FAUSTLIBRARIES_VERSION
_MAX_REQUEST_BYTES = 2 * 1024 * 1024
_SOURCE_PATH = re.compile(r"^[A-Za-z0-9_.+-]+$")
EXCLUDED_TIMING_FIELDS = ("duration_ms",)
UNGRADED_EXIT_FLOOR = 124
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
_LIB_VERSION = re.compile(
    rb"version\s*=\s*(\d+),\s*//\s*MAJOR version when we make incompatible API changes,\s*"
    rb"(\d+),\s*//\s*MINOR version when we add functionality in a backwards compatible manner,\s*"
    rb"(\d+);\s*//\s*PATCH version"
)
_REMOTE_IMPORT = re.compile(
    r"""(?ix)\b(?:import|library|component)\s*\(\s*["']https?://"""
)


def _code_without_comments(source: str) -> str:
    """Return ``source`` with Faust ``//`` and ``/* */`` comments removed.

    Quoted strings are kept, so a URL inside a string argument is
    still visible and a URL that only appears in a comment is not.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    out: list[str] = []
    index = 0
    length = len(source)
    while index < length:
        character = source[index]
        if character in {'"', "'"}:
            quote = character
            end = index + 1
            while end < length and source[end] != quote:
                if source[end] == "\\":
                    end += 2
                    continue
                end += 1
            out.append(source[index : min(end + 1, length)])
            index = end + 1
            continue
        if source.startswith("//", index):
            newline = source.find("\n", index)
            index = length if newline < 0 else newline
            continue
        if source.startswith("/*", index):
            close = source.find("*/", index + 2)
            index = length if close < 0 else close + 2
            continue
        out.append(character)
        index += 1
    return "".join(out)
_JS_RUNTIME = (
    "allocate is not defined",
    "maximum call stack size exceeded",
    "referenceerror",
    "rangeerror",
    "typeerror",
    "syntaxerror",
    "is not defined",
    "is not a function",
)
_PIN_LOCK = threading.Lock()
_PIN_CACHE: dict[tuple[str, ...], "RuntimePin"] = {}


class CompilerHarnessError(Exception):
    """The harness failed before it could classify a compile."""


class NativeFaustUnavailable(CompilerHarnessError):
    """The native Faust 2.88.0 CLI is not available for a cross-check."""


@dataclass(frozen=True)
class RuntimePin:
    """Identity of one staged libfaust runtime.

    ``faustlibraries_version`` is ``vl.version`` of the pinned tree that is
    staged over the bundle. ``bundled_faustlibraries_version`` is the
    triplet still sitting in ``libfaust-wasm.data``. ``node`` is
    major.minor. The sha256 fields are hex digests with no ``sha256:``
    prefix.
    """

    faust_version: str
    faustlibraries_version: str
    bundled_faustlibraries_version: str
    faustlibraries_commit: str
    faustlibraries_tree_sha256: str
    node: str
    js_sha256: str
    wasm_sha256: str
    data_sha256: str


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
        return "unbound_symbol"
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
    filename: str = "input.dsp",
    siblings: Mapping[str, str] | None = None,
) -> Compilation:
    """Compile ``source`` with libfaust-wasm and return a receipt.

    ``lang`` is ``wasm`` or ``cpp``. A Faust rejection is a receipt with
    exit code 1, not an exception. A missing sandbox tool raises
    ``SandboxError``. ``siblings`` maps relative ``.dsp`` paths to source
    text from the same program. They are written into the Emscripten
    filesystem so ``import`` and ``component`` of those paths resolve.
    A known faust-stk or fastpow2 source raises ``CompilerExclusion``
    instead of a receipt. ``grade_compiler_exclusion`` grades that as
    ``parse_error`` (spec §23 A1). It is not a pass and not an
    ungraded refuge.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    if lang not in {"wasm", "cpp"}:
        raise ValueError("lang must be 'wasm' or 'cpp'")
    checked = _validate_options(options)
    files = _source_files(filename, source, siblings)
    _reject_excluded(source)
    bounds = limits or ResourceLimits()
    entry = _normalize_dsp_path(filename) if siblings else None
    source_bytes = _source_identity(files, entry=entry)
    pin = runtime_pin()
    if sum(len(text.encode("utf-8")) for _, text in files) > bounds.source_bytes:
        return _harness_receipt(
            source_bytes,
            lang=lang,
            options=checked,
            stop_reason="source",
            duration_ms=0,
            faust_version=pin.faust_version,
            pin=pin,
        )
    # A6: the pre-filter sees string arguments of import/library/component,
    # not comments. A URL in a comment is not a remote import.
    if any(_REMOTE_IMPORT.search(_code_without_comments(text)) for _, text in files):
        return _harness_receipt(
            source_bytes,
            lang=lang,
            options=checked,
            stop_reason="remote",
            duration_ms=0,
            faust_version=pin.faust_version,
            pin=pin,
        )
    script = worker_directory() / "compile.mjs"
    if not script.is_file():
        raise SandboxError(f"compiler worker is missing: {script}")
    libraries = share_directory()
    payload: dict[str, Any] = {
        "source": source,
        "lang": lang,
        "options": list(checked),
        "sources": [],
    }
    if siblings:
        payload["filename"] = _normalize_dsp_path(filename)
        payload["sources"] = [{"path": path, "source": text} for path, text in files]
    request = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(request) > _MAX_REQUEST_BYTES:
        return _harness_receipt(
            source_bytes,
            lang=lang,
            options=checked,
            stop_reason="source",
            duration_ms=0,
            faust_version=pin.faust_version,
            pin=pin,
        )
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="faustcoder-") as temporary:
        workdir = Path(temporary)
        _stage_runtime(workdir)
        command = node_command(
            script,
            [str(workdir), str(libraries)],
            read_paths=[worker_directory(), workdir, libraries],
            write_paths=[workdir],
            # /proc/net is a symlink to self/net. realpath would grant the
            # parent's pid. The canary has to read the child's namespace.
            literal_reads=("/proc/net/dev",),
        )
        run = run_in_sandbox(command, stdin=request, workdir=workdir, limits=bounds)
        duration_ms = int((time.monotonic() - started) * 1000)
        _raise_if_canary_failed(run)
        if run.stop_reason:
            return _harness_receipt(
                source_bytes,
                lang=lang,
                options=checked,
                stop_reason=run.stop_reason,
                duration_ms=duration_ms,
                faust_version=pin.faust_version,
                pin=pin,
            )
        return _receipt_from_worker(
            source_bytes,
            lang=lang,
            options=checked,
            limits=bounds,
            workdir=workdir,
            run=run,
            duration_ms=duration_ms,
            pin=pin,
        )


def compile_directory(
    directory: Path,
    entry: str,
    *,
    lang: str = "wasm",
    options: Sequence[str] = (),
    limits: ResourceLimits | None = None,
) -> Compilation:
    """Compile ``entry`` plus every ``.dsp`` file under ``directory``.

    Paths stay relative to ``directory``. ``component("../x.dsp")`` resolves
    when ``directory`` is the common parent of the entry and ``x.dsp``.
    Symlinks are skipped.
    """
    root = directory.resolve()
    if not root.is_dir():
        raise CompilerHarnessError(f"source directory is missing: {directory}")
    entry_rel = _normalize_dsp_path(entry)
    siblings: dict[str, str] = {}
    source = ""
    found = False
    for path in root.rglob("*.dsp"):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        text = path.read_bytes().decode("utf-8")
        if rel == entry_rel:
            found = True
            source = text
            continue
        siblings[rel] = text
    if not found:
        raise CompilerHarnessError(f"entry is not in the source directory: {entry}")
    return compile_source(
        source,
        lang=lang,
        options=options,
        limits=limits,
        filename=entry_rel,
        siblings=siblings,
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
    libraries = share_directory()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="faustcoder-") as temporary:
        workdir = Path(temporary)
        (workdir / "input.dsp").write_bytes(source_bytes)
        command = _native_command(binary, libraries, checked)
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
    """Validate ``receipt`` and store it. Return the artifact id.

    Receipts are deduplicated by ``reproducible_digest``. A second store of
    a receipt that differs only by ``duration_ms`` returns the first
    artifact id and does not write another envelope. ``created_at`` on the
    first envelope wins. Look the stored envelope up with
    ``lookup_compiler_receipt``.
    """
    if not isinstance(receipt, dict):
        raise CompilerHarnessError("receipt must be a JSON object")
    validate(receipt, _COMPILER_SCHEMA)
    digest = reproducible_receipt_digest(receipt)
    existing = lookup_compiler_receipt(store, digest)
    if existing is not None:
        return str(existing["artifact_id"])
    envelope = build_envelope(
        schema_version=COMPILER_SCHEMA_VERSION,
        created_at=created_at,
        producer=producer,
        parents=list(parents),
        payload=receipt,
    )
    artifact_id = store.put(envelope)
    path = _receipt_index_path(store, digest)
    path.parent.mkdir(mode=0o755, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        winner = lookup_compiler_receipt(store, digest)
        if winner is None:
            raise CompilerHarnessError("receipt index disappeared during store")
        return str(winner["artifact_id"])
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(artifact_id + "\n")
    return artifact_id


def lookup_compiler_receipt(
    store: ArtifactStore, reproducible_digest: str
) -> dict[str, Any] | None:
    """Return the envelope stored for ``reproducible_digest``, or None.

    The index lives beside the artifact store, outside ``sha256/``. The
    payload's reproducible digest is checked against the requested digest.
    """
    path = _receipt_index_path(store, reproducible_digest)
    if path.is_symlink():
        raise CompilerHarnessError("receipt index path is a symlink")
    if not path.is_file():
        return None
    artifact_id = path.read_text(encoding="ascii").strip()
    if re.fullmatch(r"[0-9a-f]{64}", artifact_id) is None:
        raise CompilerHarnessError("receipt index does not hold an artifact id")
    envelope = store.get(artifact_id)
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise CompilerHarnessError("stored receipt payload is not an object")
    if reproducible_receipt_digest(payload) != _normalize_digest(reproducible_digest):
        raise CompilerHarnessError("receipt index does not match the stored payload")
    return envelope


def runtime_pin() -> RuntimePin:
    """Return the installed libfaust pin, probing the runtime once per hash."""
    _installed_faustwasm_version()
    libraries = require_library_tree()
    runtime = _runtime_directory()
    hashes = tuple(_file_sha256(runtime / name) for name in _RUNTIME_FILES)
    cache_key = (*hashes, libraries.sha256)
    with _PIN_LOCK:
        cached = _PIN_CACHE.get(cache_key)
    if cached is not None:
        return cached
    bundled = _faustlibraries_version(runtime / "libfaust-wasm.data")
    node = _node_major_minor()
    faust_version = _probe_libfaust_version()
    pin = RuntimePin(
        faust_version=faust_version,
        faustlibraries_version=libraries.version,
        bundled_faustlibraries_version=bundled,
        faustlibraries_commit=libraries.commit,
        faustlibraries_tree_sha256=libraries.sha256,
        node=node,
        js_sha256=hashes[0],
        wasm_sha256=hashes[1],
        data_sha256=hashes[2],
    )
    with _PIN_LOCK:
        _PIN_CACHE[cache_key] = pin
    return pin


def environment_preimage(
    *,
    compiler: str,
    faust_version: str,
    lang: str,
    options: Sequence[str],
    pin: RuntimePin | None,
    mounted_share_sha256: str | None = None,
) -> dict[str, Any]:
    """Return the object hashed into ``environment_digest``.

    ``faustlibraries_share_sha256`` is the hash of the tree mounted at
    ``/usr/share/faust``. The share directory is re-hashed on this call.
    ``mounted_share_sha256``, when the worker returned one, has to be that
    same value. A mismatch raises and the caller writes no receipt.
    """
    libraries = require_library_tree()
    share_directory(libraries)
    if mounted_share_sha256 is not None and mounted_share_sha256 != FAUSTLIBRARIES_SHARE_SHA256:
        raise SandboxError(
            "worker hash of /usr/share/faust does not match the pinned share: "
            f"{mounted_share_sha256}"
        )
    wasm = compiler == "libfaust-wasm" and pin is not None
    unshare_path, unshare_sha256 = unshare_identity()
    return {
        "bundled_faustlibraries_version": pin.bundled_faustlibraries_version if wasm else "",
        "compiler": compiler,
        "faust_version": faust_version,
        "faustlibraries_commit": libraries.commit,
        "faustlibraries_share_sha256": FAUSTLIBRARIES_SHARE_SHA256,
        "faustlibraries_tree_sha256": libraries.sha256,
        "faustlibraries_version": libraries.version,
        "faustwasm": FAUSTWASM_VERSION if compiler == "libfaust-wasm" else "",
        "lang": lang,
        "libfaust_wasm_data_sha256": pin.data_sha256 if wasm else "",
        "network": "unshare-net-userns",
        "unshare_path": unshare_path,
        "unshare_sha256": unshare_sha256,
        "node": pin.node if wasm else "",
        "node_flags": list(NODE_SANDBOX_FLAGS) if compiler == "libfaust-wasm" else [],
        "options": list(options),
        "runtime_sha256": {
            "libfaust-wasm.data": pin.data_sha256,
            "libfaust-wasm.js": pin.js_sha256,
            "libfaust-wasm.wasm": pin.wasm_sha256,
        }
        if wasm
        else {},
        "user_map": "current",
    }


def _native_command(binary: str, libraries: Path, options: Sequence[str]) -> list[str]:
    """Argv for the native cross-check. ``-I`` is the pinned share tree."""
    return [binary, "-I", str(libraries), "-lang", "cpp", *options, "input.dsp"]


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


def _source_files(
    filename: str, source: str, siblings: Mapping[str, str] | None
) -> list[tuple[str, str]]:
    if not siblings:
        return [("input.dsp", source)]
    entry = _normalize_dsp_path(filename)
    files = {entry: source}
    for name, text in siblings.items():
        if not isinstance(text, str):
            raise ValueError("sibling source must be a string")
        rel = _normalize_dsp_path(name)
        if rel in files:
            raise ValueError(f"duplicate source path: {rel}")
        files[rel] = text
    return sorted(files.items())


def _source_identity(files: Sequence[tuple[str, str]], *, entry: str | None = None) -> bytes:
    """Bytes hashed into ``source_sha256``.

    A single file is the source text alone. A multi-file program also
    hashes every path and the selected entry, so two entries over the
    same directory do not share an identity.
    """
    if entry is None:
        if len(files) != 1:
            raise CompilerHarnessError("multi-file source identity requires an entry path")
        return files[0][1].encode("utf-8")
    chunks = [b"entry\n" + entry.encode("utf-8") + b"\n"]
    for path, text in files:
        data = text.encode("utf-8")
        chunks.append(path.encode("utf-8") + b"\n" + len(data).to_bytes(8, "big") + data)
    return b"".join(chunks)


def _raise_if_canary_failed(run: SandboxRun) -> None:
    """A failed network canary is not an ordinary internal receipt."""
    marker = b"sandbox_canary_failed:"
    if marker not in run.stderr:
        return
    detail = run.stderr.decode("utf-8", errors="replace").strip()
    raise SandboxError(f"network namespace canary failed: {detail}")


def _reject_excluded(source: str) -> None:
    # CompilerExclusion is not a receipt. When rewards land, an exclusion
    # of model output is a failure, not a pass and not an ungraded refuge.
    found = exclusion_for_source(source)
    if found is not None:
        raise CompilerExclusion(found)


def _normalize_dsp_path(name: str) -> str:
    if not isinstance(name, str) or "\\" in name or name.startswith("/"):
        raise ValueError("source path must be relative")
    parts = name.split("/")
    if not parts or any(
        part in {"", ".", ".."} or _SOURCE_PATH.fullmatch(part) is None for part in parts
    ):
        raise ValueError("source path must stay inside the source directory")
    if not name.endswith(".dsp"):
        raise ValueError("source path must be a .dsp file")
    return "/".join(parts)


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
    pin: RuntimePin,
) -> Compilation:
    result_path = workdir / "result.json"
    if run.returncode != 0 or not result_path.is_file():
        return _harness_receipt(
            source_bytes,
            lang=lang,
            options=options,
            stop_reason="internal",
            duration_ms=duration_ms,
            faust_version=pin.faust_version,
            pin=pin,
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
            faust_version=pin.faust_version,
            pin=pin,
        )
    if not isinstance(body, dict) or body.get("faustwasm_version") != FAUSTWASM_VERSION:
        return _harness_receipt(
            source_bytes,
            lang=lang,
            options=options,
            stop_reason="internal",
            duration_ms=duration_ms,
            faust_version=pin.faust_version,
            pin=pin,
        )
    reported = body.get("libfaust_version")
    if reported != pin.faust_version:
        return _harness_receipt(
            source_bytes,
            lang=lang,
            options=options,
            stop_reason="internal",
            duration_ms=duration_ms,
            faust_version=pin.faust_version,
            pin=pin,
        )
    mounted = body.get("library_tree_sha256")
    # The worker hashes the bytes it wrote into /usr/share/faust. That has
    # to equal the Python hash of the share directory just mounted.
    if not isinstance(mounted, str) or mounted != FAUSTLIBRARIES_SHARE_SHA256:
        raise SandboxError(
            "worker hash of /usr/share/faust does not match the pinned share: "
            f"{mounted}"
        )
    faust_version = pin.faust_version
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
                pin=pin,
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
                    pin=pin,
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
                    pin=pin,
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
                    pin=pin,
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
        pin=pin,
        mounted_share_sha256=mounted,
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
    pin: RuntimePin | None = None,
) -> Compilation:
    messages = {
        "timeout": "timeout: wall clock limit exceeded\n",
        "memory": "resource limit: memory\n",
        "output": "resource limit: output size\n",
        "source": "resource limit: source size\n",
        "internal": "internal: worker failed\n",
        "remote": "internal: remote import rejected\n",
        "cpu": "timeout: wall clock limit exceeded\n",
    }
    diagnostics = messages.get(stop_reason, "internal: worker failed\n")
    if stop_reason in {"timeout", "cpu"}:
        reason = "timeout"
    elif stop_reason == "remote":
        reason = "internal"
    else:
        reason = stop_reason
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
        pin=pin,
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
    pin: RuntimePin | None = None,
    harness: str | None = None,
    mounted_share_sha256: str | None = None,
) -> Compilation:
    runtime_failure = harness is None and not compile_ok and _is_js_runtime(diagnostics)
    if harness == "timeout":
        diagnostic_class = "timeout"
        exit_code = 124
    elif harness in {"memory", "output", "source"}:
        diagnostic_class = "resource_limit"
        exit_code = 125
    elif harness == "internal" or runtime_failure:
        diagnostic_class = "internal"
        exit_code = 126
    elif compile_ok:
        diagnostic_class = classify_diagnostic(diagnostics, compile_ok=True)
        exit_code = 0
    else:
        diagnostic_class = classify_diagnostic(diagnostics, compile_ok=False)
        exit_code = 1
    if harness is not None or runtime_failure:
        outputs = []
    stdout = canonical_output_bytes(outputs)
    preimage = environment_preimage(
        compiler=compiler,
        faust_version=faust_version,
        lang=lang,
        options=options,
        pin=pin,
        mounted_share_sha256=mounted_share_sha256,
    )
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
    command.append(f"--faustlibraries={FAUSTLIBRARIES_PIN}")
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


def _is_js_runtime(diagnostics: str) -> bool:
    if "ERROR :" in diagnostics or "WARNING" in diagnostics:
        return False
    folded = diagnostics.lower()
    return any(marker in folded for marker in _JS_RUNTIME)


def _normalize_digest(value: str) -> str:
    text = value.strip()
    hex_id = text[7:] if text.startswith("sha256:") else text
    if re.fullmatch(r"[0-9a-f]{64}", hex_id) is None:
        raise CompilerHarnessError("reproducible digest must be sha256 and 64 hex characters")
    return f"sha256:{hex_id}"


def _receipt_index_path(store: ArtifactStore, digest: str) -> Path:
    hex_id = _normalize_digest(digest).removeprefix("sha256:")
    return store.root / "receipt-index" / hex_id


def _runtime_directory() -> Path:
    return worker_directory() / "node_modules" / "@grame" / "faustwasm" / "libfaust-wasm"


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise SandboxError(f"missing faustwasm runtime file: {path.name}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _faustlibraries_version(data_path: Path) -> str:
    match = _LIB_VERSION.search(data_path.read_bytes())
    if match is None:
        raise SandboxError("bundled version.lib does not declare vl.version")
    return ".".join(part.decode("ascii") for part in match.groups())


def _node_major_minor() -> str:
    completed = subprocess.run(
        [node_executable(), "--version"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    match = re.fullmatch(r"v(\d+)\.(\d+)\.\d+", completed.stdout.strip())
    if match is None:
        raise SandboxError(f"node --version returned {completed.stdout!r}")
    return f"{match.group(1)}.{match.group(2)}"


def _probe_libfaust_version() -> str:
    script = worker_directory() / "version.mjs"
    if not script.is_file():
        raise SandboxError(f"version worker is missing: {script}")
    with tempfile.TemporaryDirectory(prefix="faustcoder-pin-") as temporary:
        workdir = Path(temporary)
        _stage_runtime(workdir)
        command = node_command(
            script,
            [str(workdir)],
            read_paths=[worker_directory(), workdir],
            write_paths=[workdir],
        )
        run = run_in_sandbox(
            command,
            stdin=b"",
            workdir=workdir,
            limits=ResourceLimits(timeout_s=30),
        )
    if run.stop_reason or run.returncode != 0:
        detail = run.stderr.decode("utf-8", errors="replace").strip()
        raise SandboxError(
            "libfaust version probe failed: "
            + (detail or run.stop_reason or str(run.returncode))
        )
    version = run.stdout.decode("utf-8").strip()
    if re.fullmatch(r"[\w.+-]{1,64}", version) is None:
        raise SandboxError(f"libfaust version probe returned {version!r}")
    return version

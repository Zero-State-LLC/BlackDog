"""Process isolation for the Faust compiler worker.

The worker is a Node.js process. This module does not trust it with the
parent environment, the network, or an unbounded runtime.

Enforcement, in order:

1. Network and user. ``unshare --net --map-current-user`` (util-linux
   2.38 or newer) runs the process in a new network namespace with no
   interfaces, and maps the calling uid to itself. A connect fails with
   ``ENETUNREACH``. Inside that namespace the uid is not 0 and ``CapEff``
   is 0. ``--map-root-user`` is not used: it maps the caller to uid 0 with
   a full capability set. Node 22's ``--permission`` model does not deny
   network and rejects ``--allow-net``; the namespace is the control that
   holds on the Node 22 line used in CI. GitHub-hosted Ubuntu sets
   ``kernel.apparmor_restrict_unprivileged_userns=1``, and ``unshare`` then
   fails with ``EPERM`` writing ``/proc/self/uid_map``. The pytest job
   clears that sysctl only when ``runner.environment`` is
   ``github-hosted``, then checks ``unshare --net --map-current-user --
   true``. On a DGX Spark or any self-hosted runner, do not set that
   sysctl. Install a root-owned copy of the unshare binary at
   ``/opt/faustcoder/bin/fc-unshare`` and point ``FAUSTCODER_UNSHARE`` at
   it. See ``docs/runbooks/compiler-harness.md``. When ``FAUSTCODER_UNSHARE``
   is set, the path has to be absolute, a regular file, owned by root, and
   not writable by group or others. The parent directory has to meet the
   same ownership rule. A symlink or a user-owned wrapper is refused.
   Unset, the sandbox uses the system ``unshare``, which is the CI
   default. The compile worker then checks, in that same process, that
   the network namespace has no non-loopback interface and that a connect
   fails. The scrubbed environment also drops ``HTTP_PROXY``,
   ``HTTPS_PROXY``, ``ALL_PROXY``, ``NODE_OPTIONS`` and the rest of the
   parent environment.
2. Code generation. Node is started with
   ``--disallow-code-generation-from-strings``, which rejects ``eval`` and
   ``new Function``. faustwasm 0.19.0 still compiles under that flag.
   ``--stack-size=8192`` sets the V8 stack to 8192 KB. Node's default
   (about 984 KB) overflows while compiling
   ``physicalModeling/fds/2dKirchhoffThinPlate.dsp``. 6144 KB still
   overflows. 6272 KB is the smallest size observed to compile that file
   on Node 22. 8192 KB is the harness bound, a round step above that
   failure. The flag is part of the compiler identity. A Faust definition
   with no base case then runs until the worker dies with ``SIGSEGV``
   instead of raising a catchable JavaScript stack error. That is still
   an internal failure. The resident cap below is what stops a compile
   that merely allocates.
3. Filesystem, process, and addons. ``--permission`` is on and the command
   does not pass ``--allow-child-process``, ``--allow-worker``,
   ``--allow-addons``, ``--allow-wasi`` or ``--allow-net``. Read and write
   are limited to the absolute paths passed in. Write is the job directory.
4. Time. The wall-clock timer is armed before stdin is written, and the
   write runs on its own thread, so a child that never reads a full pipe
   is still killed at ``timeout_s``. ``prlimit --cpu`` is a CPU-time
   backstop (``ceil(timeout_s) + 1`` seconds) and is reported as a timeout.
5. Memory. ``RLIMIT_AS`` is not used: the embedded libfaust module reserves
   a large virtual address space (about 11 GB) while the compile's resident
   set stays near 80 MB. A parent thread samples ``VmRSS`` of the process
   tree every ``poll_interval_s`` and kills the group when the sum exceeds
   ``memory_bytes``. This is a userspace cap. A spike between samples can
   pass it; a kernel OOM kill is reported as an internal failure.
6. Output size. ``prlimit --fsize`` caps each file the child creates.
   Node reports that cap as ``EFBIG`` instead of dying on ``SIGXFSZ``.
   The supervisor treats produced bytes at or above ``output_bytes`` as the
   limit, and a child that exits with ``EFBIG`` is the same failure.
   Staged runtime inputs are not counted. Captured stdout and stderr use
   the same cap.
7. Job directory. The caller creates a fresh directory and deletes it.
   ``HOME`` and ``TMPDIR`` inside the child are that directory.

``prlimit`` and ``unshare`` come from util-linux. Both are on Ubuntu images
used by GitHub-hosted runners. If either is missing, the sandbox raises
and does not run the compiler on the host network.
"""

from __future__ import annotations

import math
import os
import shutil
import signal
import stat
import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# Flags that are part of the compiler identity. Per-run filesystem allow
# paths are absolute temp directories and are not part of this tuple.
# --stack-size is kilobytes of V8 stack. 8192 KB is the documented bound
# for physicalModeling/fds/2dKirchhoffThinPlate.dsp. See the module docstring.
NODE_STACK_SIZE_KB = 8192
NODE_SANDBOX_FLAGS = (
    "--disallow-code-generation-from-strings",
    "--permission",
    f"--stack-size={NODE_STACK_SIZE_KB}",
)

_IGNORED_OUTPUTS = {
    "runtime/libfaust-wasm.js",
    "runtime/libfaust-wasm.wasm",
    "runtime/libfaust-wasm.data",
    "input.dsp",
}
_STDERR_CAP = 65_536


class SandboxError(Exception):
    """The sandbox could not be constructed. The compiler was not started."""


@dataclass(frozen=True)
class ResourceLimits:
    """Bounds for one sandboxed run.

    ``memory_bytes`` is resident set size, not virtual address space.
    ``output_bytes`` caps each child-created file and the total size of
    those files. ``source_bytes`` is enforced by the compiler before the
    worker starts; the sandbox itself does not read the Faust source.
    """

    timeout_s: float = 15.0
    # 768 MB covers SAM/virtualAnalog/virtualAnalog.dsp, which exceeds
    # 608 MB and compiles at 640 MB. The 50 ms poll needs room above that
    # peak. The plate compile stays near 510 MB.
    memory_bytes: int = 768 * 1024 * 1024
    output_bytes: int = 8 * 1024 * 1024
    source_bytes: int = 1024 * 1024
    poll_interval_s: float = 0.05

    def __post_init__(self) -> None:
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        if self.memory_bytes <= 0 or self.output_bytes <= 0 or self.source_bytes <= 0:
            raise ValueError("resource limits must be positive")
        if self.poll_interval_s <= 0:
            raise ValueError("poll_interval_s must be positive")


@dataclass(frozen=True)
class SandboxRun:
    """Result of one sandboxed command.

    ``stop_reason`` is empty when the process exited on its own. ``timeout``
    covers the wall clock and the CPU backstop. ``output`` covers the file
    and pipe caps. ``memory`` covers the resident-set supervisor.
    ``internal`` is an unexpected ``SIGKILL``.
    """

    returncode: int
    stdout: bytes
    stderr: bytes
    stop_reason: str
    stdout_truncated: bool
    stderr_truncated: bool


def node_executable() -> str:
    """Return the absolute path of ``node`` on ``PATH``."""
    return _require_tool("node")


def unshare_executable() -> str:
    """Return the ``unshare`` binary this process will execute.

    ``FAUSTCODER_UNSHARE`` selects a dedicated binary such as
    ``/opt/faustcoder/bin/fc-unshare``. When it is set, the path must be
    absolute, a regular file (not a symlink), owned by root, and not
    writable by group or others. The parent directory must be a root-owned
    directory that group and others cannot write. Unset, the system
    ``unshare`` is used. CI leaves the variable unset. A shell wrapper is
    the wrong binary: the ``unshare`` syscall has to come from the file
    AppArmor names.
    """
    override = os.environ.get("FAUSTCODER_UNSHARE", "").strip()
    if not override:
        return _require_tool("unshare")
    if not os.path.isabs(override):
        raise SandboxError(f"FAUSTCODER_UNSHARE must be an absolute path: {override}")
    path = Path(override)
    _require_root_owned(path, "FAUSTCODER_UNSHARE", directory=False)
    _require_root_owned(path.parent, "FAUSTCODER_UNSHARE directory", directory=True)
    if not os.access(path, os.X_OK):
        raise SandboxError(f"FAUSTCODER_UNSHARE is not executable: {override}")
    return override


def node_command(
    script: Path,
    args: Sequence[str],
    *,
    read_paths: Sequence[Path],
    write_paths: Sequence[Path],
    literal_reads: Sequence[str] = (),
) -> list[str]:
    """Build the Node command line for one sandboxed script.

    The command enables the permission model and does not grant network,
    child processes, worker threads, native addons or WASI.
    ``literal_reads`` are appended as written. ``/proc/net/dev`` has to
    stay literal: ``realpath`` follows ``/proc/net`` into the parent's pid.
    """
    command = [node_executable(), *NODE_SANDBOX_FLAGS]
    for path in read_paths:
        command.append(f"--allow-fs-read={_permission_path(path)}")
    for item in literal_reads:
        if not item.startswith("/") or "\x00" in item:
            raise SandboxError(f"literal read path must be absolute: {item}")
        command.append(f"--allow-fs-read={item}")
    for path in write_paths:
        command.append(f"--allow-fs-write={_permission_path(path)}")
    command.append(str(script.resolve()))
    command.extend(args)
    return command


def run_in_sandbox(
    command: Sequence[str],
    *,
    stdin: bytes,
    workdir: Path,
    limits: ResourceLimits,
    cwd: Path | None = None,
) -> SandboxRun:
    """Run ``command`` inside the network namespace and resource limits.

    ``command`` is executed as-is after ``prlimit`` and ``unshare``. The
    child environment is not a copy of the parent environment.
    """
    if not command:
        raise SandboxError("sandbox command is empty")
    prlimit = _require_tool("prlimit")
    unshare = unshare_executable()
    cpu_seconds = max(1, math.ceil(limits.timeout_s) + 1)
    wrapped = [
        prlimit,
        "--core=0",
        f"--fsize={limits.output_bytes}",
        f"--cpu={cpu_seconds}",
        "--",
        unshare,
        "--net",
        "--map-current-user",
        "--",
        *command,
    ]
    process = subprocess.Popen(
        wrapped,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd or workdir),
        env=_child_environment(workdir),
        start_new_session=True,
    )
    reason: dict[str, str] = {"value": ""}
    lock = threading.Lock()
    stop = threading.Event()

    def mark(value: str) -> None:
        with lock:
            if not reason["value"]:
                reason["value"] = value

    def watch() -> None:
        while True:
            if _resident_bytes(process.pid) > limits.memory_bytes:
                mark("memory")
                _kill_group(process.pid)
                return
            if _produced_bytes(workdir) >= limits.output_bytes:
                mark("output")
                _kill_group(process.pid)
                return
            if stop.wait(limits.poll_interval_s):
                return

    stdout: dict[str, object] = {"data": b"", "truncated": False}
    stderr: dict[str, object] = {"data": b"", "truncated": False}

    def drain(pipe: object, cap: int, box: dict[str, object]) -> None:
        data, truncated = _read_capped(pipe, cap)
        box["data"] = data
        box["truncated"] = truncated

    assert process.stdout is not None and process.stderr is not None
    out_thread = threading.Thread(
        target=drain,
        args=(process.stdout, limits.output_bytes, stdout),
        daemon=True,
    )
    err_thread = threading.Thread(
        target=drain,
        args=(process.stderr, _STDERR_CAP, stderr),
        daemon=True,
    )
    watcher = threading.Thread(target=watch, daemon=True)
    def expire() -> None:
        mark("timeout")
        _kill_group(process.pid)

    # Armed before stdin is written. A full pipe must not block the parent
    # past timeout_s.
    timer = threading.Timer(limits.timeout_s, expire)
    timer.daemon = True

    def write_stdin() -> None:
        if process.stdin is None:
            return
        try:
            process.stdin.write(stdin)
        except (BrokenPipeError, OSError, ValueError):
            pass
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass

    writer = threading.Thread(target=write_stdin, daemon=True)
    out_thread.start()
    err_thread.start()
    watcher.start()
    timer.start()
    writer.start()
    try:
        try:
            process.wait(timeout=limits.timeout_s + 5)
        except subprocess.TimeoutExpired:
            expire()
            process.wait(timeout=5)
    finally:
        timer.cancel()
        stop.set()
        writer.join(timeout=1)
        watcher.join(timeout=1)
        out_thread.join(timeout=1)
        err_thread.join(timeout=1)
    returncode = process.returncode if process.returncode is not None else -1
    stop_reason = reason["value"]
    if returncode == -signal.SIGXCPU and not stop_reason:
        stop_reason = "timeout"
    if returncode == -signal.SIGXFSZ and not stop_reason:
        stop_reason = "output"
    if returncode == -signal.SIGKILL and not stop_reason:
        stop_reason = "internal"
    stderr_bytes = stderr["data"] if isinstance(stderr["data"], bytes) else b""
    if not stop_reason and (
        _produced_bytes(workdir) >= limits.output_bytes or b"EFBIG" in stderr_bytes
    ):
        stop_reason = "output"
    if stdout["truncated"] or stderr["truncated"]:
        stop_reason = stop_reason or "output"
    return SandboxRun(
        returncode=returncode,
        stdout=stdout["data"] if isinstance(stdout["data"], bytes) else b"",
        stderr=stderr["data"] if isinstance(stderr["data"], bytes) else b"",
        stop_reason=stop_reason,
        stdout_truncated=bool(stdout["truncated"]),
        stderr_truncated=bool(stderr["truncated"]),
    )


def _child_environment(workdir: Path) -> dict[str, str]:
    root = str(workdir)
    return {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "HOME": root,
        "TMPDIR": root,
        "FAUSTCODER_SANDBOX": "1",
        "NODE_DISABLE_COMPILE_CACHE": "1",
        "NODE_NO_WARNINGS": "1",
    }


def _permission_path(path: Path) -> str:
    text = os.path.realpath(path)
    if os.path.isdir(text) and not text.endswith(os.sep):
        return text + os.sep
    return text


def _require_root_owned(path: Path, label: str, *, directory: bool) -> None:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise SandboxError(f"{label} is not available: {path}") from exc
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    expected = "directory" if directory else "regular file"
    if not kind(info.st_mode):
        raise SandboxError(f"{label} is not a {expected}: {path}")
    if info.st_uid != 0:
        raise SandboxError(f"{label} must be owned by root: {path}")
    if info.st_mode & 0o022:
        raise SandboxError(f"{label} must not be writable by group or others: {path}")


def _require_tool(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise SandboxError(f"{name} is required for the compiler sandbox and was not found")
    return found


def _read_capped(pipe: object, cap: int) -> tuple[bytes, bool]:
    chunks: list[bytes] = []
    size = 0
    truncated = False
    while True:
        block = pipe.read(65_536)  # type: ignore[attr-defined]
        if not block:
            break
        if size < cap:
            take = block[: cap - size]
            chunks.append(take)
            size += len(take)
            if len(take) < len(block):
                truncated = True
        else:
            truncated = True
    return b"".join(chunks), truncated


def _resident_bytes(pid: int) -> int:
    total = 0
    pending = [pid]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if current in seen or current <= 0:
            continue
        seen.add(current)
        total += _vm_rss(current)
        pending.extend(_children(current))
    return total


def _vm_rss(pid: int) -> int:
    try:
        text = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    except OSError:
        return 0
    for line in text.splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    return 0


def _children(pid: int) -> list[int]:
    try:
        text = Path(f"/proc/{pid}/task/{pid}/children").read_text(encoding="utf-8")
    except OSError:
        return []
    children: list[int] = []
    for token in text.split():
        try:
            children.append(int(token))
        except ValueError:
            continue
    return children


def _produced_bytes(workdir: Path) -> int:
    total = 0
    for path in workdir.rglob("*"):
        if path.is_symlink():
            return 2**62
        if not path.is_file():
            continue
        relative = path.relative_to(workdir).as_posix()
        if relative in _IGNORED_OUTPUTS:
            continue
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            return

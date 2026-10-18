"""Process isolation for the Faust compiler worker.

The worker is a Node.js process. This module does not trust it with the
parent environment, the network, or an unbounded runtime.

Enforcement, in order:

1. Network and user. ``unshare --net --map-current-user`` (util-linux
   2.38 or newer) runs the process in a new network namespace with no
   interfaces, and maps the calling uid to itself. A connect fails with
   ``ENETUNREACH``. Inside that namespace the uid is not 0 and ``CapEff``
   is 0. ``--map-root-user`` is not used for the compiler process: it maps
   the caller to uid 0 with a full capability set. The native cross-check
   is the one caller that enters a mount namespace. It covers each
   Faust library directory (the ``/usr`` shares, ``<binary>/../share/faust``,
   ``<binary>/../lib/faust``, and the directories ``faust`` itself reports)
   with an empty tmpfs, including candidates that are not there yet. If
   one of those appears during the mount and stays unmasked, the compile
   fails. An absent prefix ``share/faust`` or ``lib/faust`` whose
   resolved parent is not root-only is refused. An absent fallback or
   reported directory is refused unless every component of
   ``realpath`` of its parent, up to ``/``, is a real root-owned
   directory with no group or other write. A root-owned sticky
   directory is allowed above that parent, not as the parent itself:
   another user can still create a missing path in a sticky directory.
   A symlink such as ``/usr/share`` is judged at that resolved
   directory. Faust's own directory
   query fails closed. Faust then runs as the calling uid with ``CapEff``
   0. The hashed private copy passed as ``-I`` is not masked. Wasm compiles
   do not take that path. Node 22's
   ``--permission`` model does not deny
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

Staged inputs count toward the output cap. The signal harness writes
its stimulus files under ``inputs/`` before the worker starts, and a
later write there is counted too. The runtime trio and ``input.dsp``
are the only ignored files.
"""

from __future__ import annotations

import hashlib
import math
import os
import shutil
import signal
import stat
import subprocess
import sys
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


def unshare_identity() -> tuple[str, str]:
    """Return the resolved path and sha256 of the unshare binary in use.

    ``FAUSTCODER_UNSHARE`` unset means the system ``unshare``. The path is
    resolved, so a symlink is named by its target. The sha256 is of that
    file's bytes. ``environment_digest`` records both, so a swapped wrapper
    changes the digest before the network canary runs.
    """
    path = Path(unshare_executable()).resolve()
    return str(path), hashlib.sha256(path.read_bytes()).hexdigest()


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


# Faust searches -I, then the install prefix, then <binary>/../share/faust
# and <binary>/share/faust, then these two. A host install is visible
# through a network namespace, so a native compile masks each one that exists.
FAUST_FALLBACK_DIRECTORIES = (
    Path("/usr/local/share/faust"),
    Path("/usr/share/faust"),
)

# --libdir often names one of these. Masking it stops the dynamic linker.
# A Faust tree under them (lib/faust, share/faust) is still masked.
_LOADER_DIRECTORIES = frozenset(
    {
        Path("/lib"),
        Path("/lib64"),
        Path("/usr/lib"),
        Path("/usr/lib64"),
        Path("/usr/local/lib"),
        Path("/usr/local/lib64"),
        Path("/lib/x86_64-linux-gnu"),
        Path("/usr/lib/x86_64-linux-gnu"),
        Path("/etc"),
        Path("/bin"),
        Path("/usr/bin"),
        Path("/usr/local/bin"),
    }
)

# Information flags. Each one prints and then Faust exits. -pathslist is the
# import and architecture search list; the others are the prefix directories.
_FAUST_DIRECTORY_FLAGS = (
    "--libdir",
    "--dspdir",
    "--includedir",
    "--archdir",
    "--pathslist",
)

# Runs inside unshare --mount --map-root-user. Mounts empty tmpfs directories,
# then re-enters as the calling uid with CapEff 0 and execs the command.
_MASK_EXEC = r"""
import ctypes
import os
import sys

def fail(message):
    sys.stderr.write("faustcoder_mask_failed: " + message + "\n")
    raise SystemExit(1)

def mount_tmpfs(directory):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.mount.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_ulong,
        ctypes.c_char_p,
    ]
    libc.mount.restype = ctypes.c_int
    # MS_RDONLY | MS_NOSUID | MS_NODEV | MS_NOEXEC
    flags = 15
    ret = libc.mount(
        b"tmpfs", os.fsencode(directory), b"tmpfs", flags, b"mode=0555,size=64k"
    )
    if ret != 0:
        fail("mount %s: errno %s" % (directory, ctypes.get_errno()))

def drop_capabilities():
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [
        ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong
    ]
    libc.prctl.restype = ctypes.c_int
    libc.prctl(47, 4, 0, 0, 0)

    class Header(ctypes.Structure):
        _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]

    class Data(ctypes.Structure):
        _fields_ = [
            ("effective", ctypes.c_uint32),
            ("permitted", ctypes.c_uint32),
            ("inheritable", ctypes.c_uint32),
        ]

    header = Header(0x20080522, 0)
    data = (Data * 2)()
    libc.syscall.restype = ctypes.c_long
    if libc.syscall(126, ctypes.byref(header), data) != 0:
        fail("capset errno %s" % ctypes.get_errno())
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        fail("no_new_privs errno %s" % ctypes.get_errno())

def refuse_if_unmasked(absent):
    for directory in absent:
        if os.path.lexists(directory):
            fail("exists unmasked: %s" % directory)

def main():
    if len(sys.argv) < 4:
        fail("mask arguments are missing")
    uid = int(sys.argv[1])
    gid = int(sys.argv[2])
    count = int(sys.argv[3])
    directories = sys.argv[4:4 + count]
    command = sys.argv[4 + count:]
    if not command:
        fail("mask command is empty")
    present = []
    absent = []
    for directory in directories:
        if os.path.lexists(directory):
            present.append(directory)
        else:
            absent.append(directory)
    for directory in present:
        mount_tmpfs(directory)
    refuse_if_unmasked(absent)
    ready_r, ready_w = os.pipe()
    done_r, done_w = os.pipe()
    writer = os.fork()
    if writer == 0:
        os.close(ready_w)
        os.close(done_r)
        os.read(ready_r, 1)
        os.close(ready_r)
        target = os.getppid()
        try:
            with open("/proc/%s/setgroups" % target, "w", encoding="ascii") as handle:
                handle.write("deny\n")
            with open("/proc/%s/uid_map" % target, "w", encoding="ascii") as handle:
                handle.write("%s 0 1\n" % uid)
            with open("/proc/%s/gid_map" % target, "w", encoding="ascii") as handle:
                handle.write("%s 0 1\n" % gid)
        except OSError as exc:
            fail("uid map: %s" % exc)
        os.write(done_w, b"1")
        os.close(done_w)
        os._exit(0)
    os.close(ready_r)
    os.close(done_w)
    os.unshare(os.CLONE_NEWUSER)
    os.write(ready_w, b"1")
    os.close(ready_w)
    if os.read(done_r, 1) != b"1":
        fail("uid map was not written")
    os.close(done_r)
    os.waitpid(writer, 0)
    drop_capabilities()
    try:
        os.execv(command[0], command)
    except OSError as exc:
        fail("exec %s: errno %s" % (command[0], exc.errno))

main()
"""


def faust_fallback_mounts(paths: Sequence[Path] | None = None) -> tuple[Path, ...]:
    """Return host Faust library directories a native compile must hide.

    Missing paths are omitted. A symlink is resolved and the target
    directory is masked: Faust follows it. A symlink to ``/`` or to a file
    is refused. Faust searches these after ``-I``, so an unmasked directory
    is another library tree the private copy does not cover.
    """
    selected = FAUST_FALLBACK_DIRECTORIES if paths is None else tuple(paths)
    mounts: list[Path] = []
    for path in selected:
        resolved = _resolve_mask_directory(path)
        if resolved is None or resolved in mounts:
            continue
        mounts.append(resolved)
    return tuple(mounts)


def faust_library_mounts(
    binary: str | Path, *, private: Path | None = None
) -> tuple[Path, ...]:
    """Every Faust search directory to mask, except the hashed private copy.

    The binary path is resolved (symlinks followed). ``<prefix>/share/faust``
    and ``<prefix>/lib/faust`` are masked when they exist, and so is
    ``<binary dir>/share/faust``. ``faust --libdir``, ``--dspdir``,
    ``--includedir``, ``--archdir`` and ``--pathslist`` add every absolute
    directory they print. A candidate that is not there yet is still
    returned. The mount step covers it if it has appeared, and fails if it
    exists afterward and was not covered. An absent prefix, fallback, or
    reported directory is refused unless every component of ``realpath``
    of its parent, up to ``/``, is a real root-owned directory with no
    group or other write. A root-owned sticky directory is allowed only
    above that parent. The caller cannot create that directory, or
    rename the parent out of a writable ancestor, in the window before
    exec. A symlink such as ``/usr/share`` is judged at the resolved
    directory. A reported loader
    directory such
    as ``/usr/lib`` is left in place so the compiler can start;
    ``lib/faust`` under it is still masked. ``private`` is the hashed
    ``-I`` directory and is never masked. The directory query fails closed.
    """
    binary_path = Path(binary)
    prefix = _prefix_faust_directories(binary_path)
    required = [*FAUST_FALLBACK_DIRECTORIES, *prefix]
    reported = _reported_faust_directories(binary_path)
    protected = _protected_faust_paths(binary_path, private)
    return _select_mask_directories(
        [*required, *reported],
        required=set(required),
        prefix=set(prefix),
        reported=set(reported),
        protected=protected,
        binary=binary_path,
    )


def _prefix_faust_directories(binary: Path) -> list[Path]:
    """``share/faust`` and ``lib/faust`` next to this binary, symlinks resolved."""
    found: list[Path] = []
    for location in _binary_locations(binary):
        prefix = location.parent.parent
        exe_dir = location.parent
        for candidate in (
            prefix / "share" / "faust",
            prefix / "lib" / "faust",
            exe_dir / "share" / "faust",
        ):
            if candidate not in found:
                found.append(candidate)
    return found


def _binary_locations(binary: Path) -> list[Path]:
    """The path Faust will be executed as, plus one symlink and the real path.

    Faust's ``exepath::get`` follows one symlink of ``argv[0]``.
    ``Path.resolve`` follows the whole chain. Masking both prefixes covers
    either choice.
    """
    absolute = Path(os.path.abspath(binary))
    locations = [absolute]
    if absolute.is_symlink():
        target = os.readlink(absolute)
        if not os.path.isabs(target):
            target = os.path.join(absolute.parent, target)
        locations.append(Path(os.path.normpath(target)))
    try:
        locations.append(absolute.resolve())
    except OSError:
        pass
    unique: list[Path] = []
    for location in locations:
        if location not in unique:
            unique.append(location)
    return unique


def _reported_faust_directories(binary: Path) -> tuple[Path, ...]:
    """Directories ``faust`` prints. A failed query raises ``SandboxError``.

    Every flag must exit 0. ``--pathslist`` must print a line
    ``FAUST dsp library paths:``. Stdout is read as bytes and decoded
    with ``os.fsdecode`` (``surrogateescape``). A non-decodable path is
    refused, including one that is not on disk. A well-formed absolute
    path that is missing is still returned. The query runs in a network
    namespace with ``FAUST_LIB_PATH`` unset, matching the scrubbed
    compile environment. Non-absolute lines are ignored.
    """
    if not binary.is_file():
        raise SandboxError(f"faust directory query failed: {binary} is not a file")
    unshare = unshare_executable()
    env = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "HOME": "/tmp",
        "TMPDIR": "/tmp",
    }
    found: list[Path] = []
    header = "FAUST dsp library paths:"
    for flag in _FAUST_DIRECTORY_FLAGS:
        try:
            completed = subprocess.run(
                [unshare, "--net", "--map-current-user", "--", str(binary), flag],
                capture_output=True,
                timeout=10,
                check=False,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise SandboxError(f"faust directory query failed: {flag} timed out") from exc
        except OSError as exc:
            raise SandboxError(f"faust directory query failed: {flag}: {exc}") from exc
        if completed.returncode != 0:
            raise SandboxError(
                f"faust directory query failed: {flag} exited {completed.returncode}"
            )
        text = _decode_directory_query(completed.stdout, flag)
        lines = text.splitlines()
        if flag == "--pathslist" and not any(line.strip() == header for line in lines):
            raise SandboxError(
                "faust directory query failed: --pathslist did not print "
                f"'{header}'"
            )
        for line in lines:
            path = _reported_directory(line, flag)
            if path is not None:
                found.append(path)
    return tuple(found)


def _decode_directory_query(data: bytes, flag: str) -> str:
    """Decode Faust's directory listing without assuming UTF-8.

    ``LANG=C`` does not make the bytes ASCII. ``os.fsdecode`` uses the
    filesystem encoding and ``surrogateescape``, so a lone byte such as
    ``0xec`` stays visible instead of raising ``UnicodeDecodeError``.
    """
    if not isinstance(data, bytes):
        raise SandboxError(f"faust directory query failed: {flag} output was not bytes")
    try:
        return os.fsdecode(data)
    except UnicodeError as exc:
        raise SandboxError(
            f"faust directory query failed: {flag} printed a non-decodable path"
        ) from exc


def _reported_directory(line: str, flag: str) -> Path | None:
    """One absolute directory from a Faust query, or ``None`` to skip.

    A non-absolute line is ignored. A surrogate in the line is refused.
    That refusal covers a nonexistent path and one that is on disk: the
    query does not continue with a path it cannot name. A path that
    cannot be stated is refused. A well-formed absolute path that is
    not on disk is returned: the mount covers an absent directory, and
    refuses one whose parent the caller can write.
    """
    if _has_surrogate(line):
        stripped = line.strip()
        present = False
        if stripped.startswith("/"):
            try:
                present = Path(stripped).exists()
            except OSError:
                present = False
        if not present:
            raise SandboxError(
                f"faust directory query failed: {flag} printed a non-decodable "
                "nonexistent path"
            )
        raise SandboxError(
            f"faust directory query failed: {flag} printed a non-decodable path"
        )
    stripped = line.strip()
    if not stripped.startswith("/"):
        return None
    path = Path(stripped)
    try:
        path.lstat()
    except FileNotFoundError:
        return path
    except OSError as exc:
        raise SandboxError(
            f"faust directory query failed: {flag} printed a path that cannot be checked"
        ) from exc
    return path


def _has_surrogate(text: str) -> bool:
    """True when ``text`` holds a byte ``surrogateescape`` could not decode."""
    return any(0xD800 <= ord(character) <= 0xDFFF for character in text)


def _protected_faust_paths(binary: Path, private: Path | None) -> list[Path]:
    protected = [Path(sys.executable), *_binary_locations(binary)]
    if private is not None:
        protected.append(private)
    return protected


def _select_mask_directories(
    candidates: Sequence[Path],
    *,
    required: set[Path],
    prefix: set[Path],
    reported: set[Path],
    protected: Sequence[Path],
    binary: Path,
) -> tuple[Path, ...]:
    protected_resolved: list[Path] = []
    for item in protected:
        try:
            protected_resolved.append(item.resolve())
        except OSError:
            protected_resolved.append(Path(os.path.abspath(item)))
    unmaskable = set(_LOADER_DIRECTORIES)
    unmaskable.update(_shared_library_directories(binary))
    mounts: list[Path] = []
    for path in candidates:
        info = _lstat_or_none(path)
        if info is not None and stat.S_ISLNK(info.st_mode) and not path.exists():
            if path in required or _is_faust_library_dir(path):
                raise SandboxError(f"Faust library path is a dangling symlink: {path}")
            continue
        if info is None:
            _pass_absent_mask(
                path,
                mounts,
                required,
                prefix,
                reported,
                protected_resolved,
                unmaskable,
            )
            continue
        try:
            resolved = _resolve_mask_directory(path)
        except SandboxError:
            if path in required or _is_faust_library_dir(path):
                raise
            continue
        if resolved is None or resolved in mounts:
            continue
        if _leaves_the_compiler_running(resolved, protected_resolved, unmaskable):
            if any(resolved == item for item in protected_resolved):
                continue
            if path in required or _is_faust_library_dir(path):
                raise SandboxError(
                    "Faust library path would hide the compiler or the private "
                    f"copy: {path}"
                )
            continue
        mounts.append(resolved)
    return tuple(mounts)


def _lstat_or_none(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except OSError:
        return None


def _pass_absent_mask(
    path: Path,
    mounts: list[Path],
    required: set[Path],
    prefix: set[Path],
    reported: set[Path],
    protected: Sequence[Path],
    unmaskable: set[Path],
) -> None:
    """Pass an absent candidate through, or refuse a parent the caller can write.

    An absent prefix, fallback, or reported directory is refused unless
    every component of ``realpath`` of its parent, up to ``/``, is a
    real root-owned directory that group and others cannot write. A
    root-owned sticky directory is allowed only above that parent.
    The mount does not cover a path that is missing, so a caller who
    can create it, or who can rename a parent out of a writable
    ancestor, can plant a library before exec. ``/usr/share`` may be a
    symlink; the check follows it and then walks the resolved chain.
    """
    absolute = Path(os.path.abspath(path))
    if absolute in mounts:
        return
    if _leaves_the_compiler_running(absolute, protected, unmaskable):
        if path in required or _is_faust_library_dir(path):
            raise SandboxError(
                "Faust library path would hide the compiler or the private "
                f"copy: {path}"
            )
        return
    if _absent_mask_must_be_root_only(path, absolute, prefix, reported):
        parent = _resolved_parent(absolute)
        unsafe = _first_unsafe_ancestor(parent)
        if unsafe is not None:
            _refuse_unsafe_parent(
                absolute,
                unsafe,
                "Faust mask parent is not root-only, so an absent directory "
                "cannot be masked safely",
            )
    mounts.append(absolute)


def _absent_mask_must_be_root_only(
    path: Path, absolute: Path, prefix: set[Path], reported: set[Path]
) -> bool:
    if path in prefix or absolute in {Path(os.path.abspath(item)) for item in prefix}:
        return True
    if absolute in _fallback_absolutes():
        return True
    return absolute in {Path(os.path.abspath(item)) for item in reported}


def _fallback_absolutes() -> set[Path]:
    return {Path(os.path.abspath(path)) for path in FAUST_FALLBACK_DIRECTORIES}


def _resolved_parent(path: Path) -> Path:
    """Directory a caller would create ``path`` in, after symlinks.

    ``os.path.realpath`` resolves existing ancestors and leaves the missing
    leaf in place. The parent of that result is the directory to check.
    """
    try:
        resolved = Path(os.path.realpath(path))
    except OSError as exc:
        raise SandboxError(f"Faust library path could not be resolved: {path}") from exc
    return _nearest_existing_ancestor(resolved)


def _refuse_unsafe_parent(path: Path, ancestor: Path, reason: str) -> None:
    info = _lstat_or_none(ancestor)
    mode = 0 if info is None else info.st_mode & 0o777
    uid = -1 if info is None else info.st_uid
    raise SandboxError(f"{reason}: {path} (parent {ancestor}, uid {uid}, mode {mode:o})")


def _nearest_existing_ancestor(path: Path) -> Path:
    current = Path(os.path.abspath(path))
    while True:
        parent = current.parent
        if parent == current:
            return current
        if _lstat_or_none(parent) is None:
            current = parent
            continue
        return parent


def _is_root_only_directory(path: Path) -> bool:
    """True when ``path`` and every ancestor up to ``/`` is root-only.

    ``path`` itself must be a real directory, owned by root, with no
    group or other write. Each ancestor must be the same, or a
    root-owned sticky directory. The sticky exception does not apply
    to ``path``: another user can create an entry in a sticky
    directory even when they cannot remove one.
    """
    return _first_unsafe_ancestor(path) is None


def _first_unsafe_ancestor(path: Path) -> Path | None:
    """Return the first unsafe component from ``path`` up to ``/``."""
    current = Path(os.path.abspath(path))
    allow_sticky = False
    while True:
        if not _component_is_root_only(current, allow_sticky=allow_sticky):
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent
        allow_sticky = True


def _component_is_root_only(path: Path, *, allow_sticky: bool) -> bool:
    """True when ``path`` is a real root-owned directory safe to trust.

    A symlink is not a directory here. ``lstat`` does not follow one.
    Group or other write is refused unless ``allow_sticky`` and the
    directory is root-owned and sticky.
    """
    info = _lstat_or_none(path)
    if info is None or stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        return False
    if info.st_uid != 0:
        return False
    if info.st_mode & 0o022 == 0:
        return True
    return bool(allow_sticky and info.st_mode & stat.S_ISVTX)


def _leaves_the_compiler_running(
    resolved: Path, protected: Sequence[Path], unmaskable: set[Path]
) -> bool:
    """True when masking ``resolved`` would hide the compiler or its libraries."""
    if resolved in unmaskable:
        return True
    for item in protected:
        if _is_ancestor(resolved, item):
            return True
    for loader in unmaskable:
        if _is_ancestor(resolved, loader):
            return True
    return False


def _is_ancestor(directory: Path, protected: Path) -> bool:
    try:
        protected.relative_to(directory)
    except ValueError:
        return False
    return True


def _is_faust_library_dir(path: Path) -> bool:
    parts = path.parts
    return len(parts) >= 2 and parts[-2:] in {("share", "faust"), ("lib", "faust")}


def _shared_library_directories(binary: Path) -> set[Path]:
    """Directories named by ``ldd``. Masking one of them stops ``exec``."""
    if not binary.is_file():
        return set()
    try:
        completed = subprocess.run(
            ["ldd", str(binary)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    found: set[Path] = set()
    for line in completed.stdout.splitlines():
        if "=>" not in line:
            continue
        target = line.split("=>", 1)[1].strip().split(" ", 1)[0]
        if target.startswith("/"):
            found.add(Path(target).resolve().parent)
    return found


def _resolve_mask_directory(path: Path) -> Path | None:
    """Real directory to cover, or None when the path is absent.

    Raises ``SandboxError`` when the path exists and is not a directory,
    or when it resolves to ``/``.
    """
    try:
        info = path.lstat()
    except OSError:
        return None
    if stat.S_ISLNK(info.st_mode) and not path.exists():
        return None
    if not stat.S_ISLNK(info.st_mode) and not stat.S_ISDIR(info.st_mode):
        raise SandboxError(f"Faust fallback path is not a directory: {path}")
    try:
        resolved = path.resolve()
    except OSError as exc:
        raise SandboxError(f"Faust fallback path cannot be resolved: {path}") from exc
    if resolved == Path("/"):
        raise SandboxError(f"Faust fallback path resolves to /: {path}")
    if not resolved.is_dir():
        raise SandboxError(f"Faust fallback path is not a directory: {path}")
    return resolved


def run_in_sandbox(
    command: Sequence[str],
    *,
    stdin: bytes,
    workdir: Path,
    limits: ResourceLimits,
    cwd: Path | None = None,
    mask_directories: Sequence[Path] = (),
) -> SandboxRun:
    """Run ``command`` inside the network namespace and resource limits.

    ``command`` is executed as-is after ``prlimit`` and ``unshare``. The
    child environment is not a copy of the parent environment.
    ``mask_directories`` are covered with an empty tmpfs so the command
    cannot read the host files there. The command still runs as the
    calling uid with ``CapEff`` 0.
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
        *_unshare_command(unshare, command, mask_directories),
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


def _unshare_command(
    unshare: str, command: Sequence[str], mask_directories: Sequence[Path]
) -> list[str]:
    """Argv after ``prlimit --``. Masks use a mount namespace; other runs do not."""
    if not mask_directories:
        return [unshare, "--net", "--map-current-user", "--", *command]
    masks = [str(path) for path in mask_directories]
    return [
        unshare,
        "--net",
        "--mount",
        "--map-root-user",
        "--propagation",
        "private",
        "--",
        sys.executable,
        "-I",
        "-c",
        _MASK_EXEC,
        str(os.getuid()),
        str(os.getgid()),
        str(len(masks)),
        *masks,
        *command,
    ]


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

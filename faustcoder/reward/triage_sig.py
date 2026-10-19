"""Human triage signatures (spec §26 0.3.10, amended 0.3.11).

A triage statement is signed with an Ed25519 key in the OpenSSH
namespace ``faustcoder-triage-v1``. Verification is ``ssh-keygen -Y
verify`` against the allowed-signers file. OpenSSH 9.6 reads the
message on stdin; a trailing filename is not that message. The key
must be valid at both ``appended_at`` and ``triaged_at``. OpenSSH
treats the ``valid-before`` instant as still valid, and this module
does not: a key revoked at that instant does not clear a halt.

Every timestamp this module hands to OpenSSH is UTC.
``valid-after``, ``valid-before``, and ``-Overify-time`` are
``YYYYMMDD`` or ``YYYYMMDDHHMMSS`` with no offset, interpreted as UTC.
RFC 3339 stamps are converted to UTC before that formatting.
"""

from __future__ import annotations

import os
import pwd
import re
import stat
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from faustcoder.canonical import canonical_bytes
from faustcoder.reward.records import GRADER_USER, RewardRecordError

NAMESPACE = "faustcoder-triage-v1"
ALLOWED_SIGNERS_PATH = Path("/etc/faustcoder/triage-allowed-signers")
# Absolute path. ``PATH`` is not consulted: a caller-controlled
# ssh-keygen earlier on ``PATH`` must not be the verifier.
SSH_KEYGEN_PATH = "/usr/bin/ssh-keygen"
_KEYGEN_TIMEOUT_SECONDS = 30
_MIN_OPENSSH = (8, 7)
_PROBE_PRINCIPAL = "fc-version-probe"
_PROBE_STAMP = "20200101000000"
_BOX_UID = 1000
_ALLOWED_MODE = 0o644
_MAX_SIGNERS_BYTES = 1_048_576
_MAX_DROP_BYTES = 1_048_576
_PRINCIPAL_FORBIDDEN = frozenset("*?!,")
_KEY_TYPES = frozenset({"ssh-ed25519", "sk-ssh-ed25519@openssh.com"})
_DECISIONS = frozenset({"accept_stored", "accept_rerun", "exclude"})
_STATEMENT_KEYS = frozenset(
    {
        "consumed_id",
        "decision",
        "halt_report_mac",
        "halt_seq",
        "key_fingerprint",
        "record_id",
        "row_ids_digest",
        "run_id",
        "triaged_at",
        "type",
        "v",
    }
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_FINGERPRINT = re.compile(r"^SHA256:[A-Za-z0-9+/]+={0,2}$")
_OPENSSH_VERSION = re.compile(r"OpenSSH_(\d+)\.(\d+)")
_STAMP14 = re.compile(r"^\d{14}$")
_STAMP8 = re.compile(r"^\d{8}$")


@dataclass(frozen=True)
class SignerEntry:
    """One allowed-signers line that passed the parser."""

    principals: tuple[str, ...]
    options: tuple[tuple[str, str], ...]
    key_type: str
    key_blob: str
    raw: str

    def option(self, name: str) -> str | None:
        for key, value in self.options:
            if key == name:
                return value
        return None


@dataclass(frozen=True)
class DropFile:
    """A human-signed drop, read from one O_NOFOLLOW fd."""

    owner_uid: int
    owner_name: str
    principal: str
    triaged_by: str
    statement: dict[str, object]
    signature: str


def default_allowed_signers() -> Path:
    """The allowed-signers file. The default is the spec path."""
    return ALLOWED_SIGNERS_PATH


def require_openssh() -> tuple[int, int]:
    """Fail closed unless ``SSH_KEYGEN_PATH`` is OpenSSH 8.7 or newer.

    The binary is that constant (default ``/usr/bin/ssh-keygen``), not
    whatever ``ssh`` or ``ssh-keygen`` ``PATH`` finds. It must be a
    root-owned regular file and not group- or world-writable. A symlink
    is refused. The version is read from that binary: a printed
    ``OpenSSH_M.N`` banner, or, when the binary prints none, acceptance
    of ``-Overify-time``, which OpenSSH added in 8.7. A timeout is a
    refusal. Called when a signature is checked and when P3 starts.
    """
    _checked_keygen()
    return _openssh_version()


def canonical_statement(statement: Mapping[str, object]) -> bytes:
    """Canonical bytes of a triage statement. The signature covers these."""
    return canonical_bytes(_require_statement(statement))


def sign_statement(statement: Mapping[str, object], key_path: Path | str) -> str:
    """Armored SSHSIG over ``statement``, made by ``ssh-keygen -Y sign``.

    Refuses a key that is group- or world-readable, mode ``0644``, or
    owned by ``fc-grader``. The private key is not returned.
    """
    require_openssh()
    payload = canonical_statement(statement)
    path = Path(key_path)
    _refuse_exposed_key(path)
    with tempfile.TemporaryDirectory(prefix="fc-triage-sign-") as directory:
        root = Path(directory)
        os.chmod(root, 0o700)
        message = root / "statement"
        signature = root / "statement.sig"
        message.write_bytes(payload)
        os.chmod(message, 0o600)
        completed = _run_keygen(
            [
                "-Y",
                "sign",
                "-f",
                str(path),
                "-n",
                NAMESPACE,
                "-s",
                str(signature),
                str(message),
            ],
            reason="audit triage signature is not usable",
        )
        if completed.returncode != 0 or not signature.is_file():
            raise RewardRecordError("audit triage signature is not usable")
        text = signature.read_text(encoding="utf-8")
    if "-----BEGIN SSH SIGNATURE-----" not in text:
        raise RewardRecordError("audit triage signature is not usable")
    return text


def verify_statement(
    statement: Mapping[str, object],
    signature: str,
    *,
    principal: str,
    allowed_signers: Path | str,
    appended_at: str,
    triaged_at: str,
) -> None:
    """Verify ``signature`` at ``appended_at`` and again at ``triaged_at``.

    Both checks use ``-Overify-time``. A key whose ``valid-before`` is
    at or before either instant is refused, including the exact second
    OpenSSH would still accept.
    """
    require_openssh()
    if type(signature) is not str or "-----BEGIN SSH SIGNATURE-----" not in signature:
        raise RewardRecordError("audit triage signature is not usable")
    if type(principal) is not str or principal == "" or any(char.isspace() for char in principal):
        raise RewardRecordError("audit triage signature is not usable")
    payload = canonical_statement(statement)
    fingerprint = statement["key_fingerprint"]
    if type(fingerprint) is not str:
        raise RewardRecordError("audit triage signature is not usable")
    appended = _require_instant(appended_at)
    triaged = _require_instant(triaged_at)
    source = open_allowed_signers(allowed_signers)
    matched = [
        entry
        for entry in source
        if principal in entry.principals and entry.fingerprint() == fingerprint
    ]
    if not matched:
        raise RewardRecordError("audit triage signature is not usable")
    for entry in matched:
        if NAMESPACE not in _namespaces(entry):
            raise RewardRecordError("audit triage signature is not usable")
        _refuse_revoked(entry, appended)
        _refuse_revoked(entry, triaged)
    with tempfile.TemporaryDirectory(prefix="fc-triage-verify-") as directory:
        root = Path(directory)
        os.chmod(root, 0o700)
        subset = root / "allowed"
        subset.write_text("".join(f"{entry.raw}\n" for entry in matched), encoding="utf-8")
        os.chmod(subset, 0o644)
        _ssh_verify(payload, signature, principal, subset, appended)
        _ssh_verify(payload, signature, principal, subset, triaged)


def require_allowed_signers(path: Path | str | None = None) -> Path:
    """Refuse a missing, misowned, or writable allowed-signers file.

    The file is root-owned mode ``0644``. Its parent is root-owned and
    not group- or world-writable. A symlink is refused. ``fc-grader``
    must not be able to write the file or that directory.
    """
    location = ALLOWED_SIGNERS_PATH if path is None else Path(path)
    _read_allowed(location)
    return location


def open_allowed_signers(path: Path | str | None = None) -> tuple[SignerEntry, ...]:
    """Parse the allowed-signers file after the ownership checks."""
    text = _read_allowed(ALLOWED_SIGNERS_PATH if path is None else Path(path))
    return _parse_allowed(text)


def reviewer_uids(path: Path | str | None = None) -> frozenset[int]:
    """OS uids of enrolled principals that are local accounts."""
    found: set[int] = set()
    for entry in open_allowed_signers(path):
        for principal in entry.principals:
            try:
                user = pwd.getpwnam(principal)
            except KeyError:
                continue
            found.add(user.pw_uid)
    return frozenset(found)


def require_p3_grader_account(allowed_signers: Path | str | None = None) -> None:
    """P3 starts only as ``fc-grader``, not uid 1000, and not a reviewer.

    The allowed-signers file is required so the reviewer uids are known.
    A missing file, a missing account, or an old OpenSSH fails closed.
    """
    require_openssh()
    uid = os.geteuid()
    if type(uid) is not int or isinstance(uid, bool) or uid == _BOX_UID:
        raise RewardRecordError(
            "P3 refuses to start: the grader process is uid 1000, not the dedicated fc-grader account"
        )
    try:
        grader = pwd.getpwnam(GRADER_USER)
    except KeyError as exc:
        raise RewardRecordError(
            "P3 refuses to start: the dedicated fc-grader account does not exist"
        ) from exc
    if grader.pw_uid == 0 or grader.pw_uid == _BOX_UID or uid != grader.pw_uid:
        raise RewardRecordError(
            "P3 refuses to start: the grader process is not the dedicated fc-grader account"
        )
    location = ALLOWED_SIGNERS_PATH if allowed_signers is None else Path(allowed_signers)
    if uid in reviewer_uids(location):
        raise RewardRecordError(
            "P3 refuses to start: fc-grader is an enrolled reviewer principal"
        )


def read_drop(path: Path | str) -> DropFile:
    """Read a regular drop file and its owner from one no-follow fd.

    The open is ``O_RDONLY | O_NONBLOCK | O_NOFOLLOW``, so a FIFO cannot
    block the grader. A hard link (``st_nlink`` other than 1) is refused.
    """
    fd = _open_nofollow(path, "audit triage drop file is not usable")
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise RewardRecordError("audit triage drop file is not usable")
        if info.st_size > _MAX_DROP_BYTES:
            raise RewardRecordError("audit triage drop file is not usable")
        data = _read_fd(fd, _MAX_DROP_BYTES)
    finally:
        os.close(fd)
    try:
        owner = pwd.getpwuid(info.st_uid)
    except KeyError as exc:
        raise RewardRecordError("audit triage writer is not usable") from exc
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise RewardRecordError("audit triage drop file is not usable") from exc
    from faustcoder.canonical import loads_strict
    from faustcoder.errors import CanonicalError

    try:
        body = loads_strict(text)
    except CanonicalError as exc:
        raise RewardRecordError("audit triage drop file is not usable") from exc
    if not isinstance(body, dict):
        raise RewardRecordError("audit triage drop file is not usable")
    principal = body.get("principal")
    actor = body.get("triaged_by")
    statement = body.get("statement")
    signature = body.get("signature")
    if (
        type(principal) is not str
        or type(actor) is not str
        or type(signature) is not str
        or not isinstance(statement, dict)
    ):
        raise RewardRecordError("audit triage drop file is not usable")
    return DropFile(
        owner_uid=info.st_uid,
        owner_name=owner.pw_name,
        principal=principal,
        triaged_by=actor,
        statement=statement,
        signature=signature,
    )


def public_fingerprint(key_path: Path | str) -> str:
    """OpenSSH ``SHA256:`` fingerprint of ``key_path``."""
    require_openssh()
    completed = _run_keygen(
        ["-lf", str(key_path)],
        reason="audit triage key is not usable",
    )
    if completed.returncode != 0:
        raise RewardRecordError("audit triage key is not usable")
    return _fingerprint_token(completed.stdout.decode("utf-8", "replace"))


def write_drop(
    path: Path | str,
    *,
    principal: str,
    triaged_by: str,
    statement: Mapping[str, object],
    signature: str,
) -> None:
    """Write a new drop file. An existing path is left untouched."""
    body = {
        "principal": principal,
        "signature": signature,
        "statement": _require_statement(statement),
        "triaged_by": triaged_by,
    }
    data = canonical_bytes(body) + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    try:
        fd = os.open(path, flags, 0o644)
    except OSError as exc:
        raise RewardRecordError("audit triage drop file is not usable") from exc
    try:
        _write_fd(fd, data)
    finally:
        os.close(fd)


def _require_statement(statement: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(statement, Mapping) or set(statement) != _STATEMENT_KEYS:
        raise RewardRecordError("audit triage statement is not usable")
    copied = dict(statement)
    if copied.get("type") != "audit_triage_statement" or copied.get("v") != 1:
        raise RewardRecordError("audit triage statement is not usable")
    if copied.get("decision") not in _DECISIONS:
        raise RewardRecordError("audit triage statement is not usable")
    halt_seq = copied.get("halt_seq")
    if type(halt_seq) is not int or isinstance(halt_seq, bool) or halt_seq < 1:
        raise RewardRecordError("audit triage statement is not usable")
    for name in ("run_id", "record_id", "triaged_at", "key_fingerprint"):
        if type(copied.get(name)) is not str or copied[name] == "":
            raise RewardRecordError("audit triage statement is not usable")
    for name in ("halt_report_mac", "row_ids_digest", "consumed_id"):
        value = copied.get(name)
        if type(value) is not str or _HEX64.fullmatch(value) is None:
            raise RewardRecordError("audit triage statement is not usable")
    fingerprint = copied["key_fingerprint"]
    if type(fingerprint) is not str or _FINGERPRINT.fullmatch(fingerprint) is None:
        raise RewardRecordError("audit triage statement is not usable")
    return copied


def _require_instant(value: object) -> datetime:
    if type(value) is not str:
        raise RewardRecordError("audit triage time is not usable")
    from faustcoder.reward.audit import _parse_rfc3339

    parsed = _parse_rfc3339(value)
    if parsed is None:
        raise RewardRecordError("audit triage time is not usable")
    return parsed


def _refuse_revoked(entry: SignerEntry, instant: datetime) -> None:
    """Refuse a key that is not valid at ``instant``.

    OpenSSH treats the ``valid-before`` second as still valid. A key
    revoked at that second does not clear a halt.
    """
    raw = entry.option("valid-before")
    if raw is not None:
        expires = _openssh_time(raw)
        if expires is None or instant >= expires:
            raise RewardRecordError("audit triage signature is not usable")
    after = entry.option("valid-after")
    if after is not None:
        starts = _openssh_time(after)
        if starts is None or instant < starts:
            raise RewardRecordError("audit triage signature is not usable")


def _openssh_time(value: str) -> datetime | None:
    """Parse an OpenSSH validity stamp as UTC.

    The text has no zone. ``YYYYMMDD`` and ``YYYYMMDDHHMMSS`` are UTC,
    the same clock ``-Overify-time`` uses.
    """
    if _STAMP14.fullmatch(value) is not None:
        parsed = datetime.strptime(value, "%Y%m%d%H%M%S")
    elif _STAMP8.fullmatch(value) is not None:
        parsed = datetime.strptime(value, "%Y%m%d")
    else:
        return None
    return parsed.replace(tzinfo=timezone.utc)


def _namespaces(entry: SignerEntry) -> frozenset[str]:
    raw = entry.option("namespaces")
    if raw is None or raw == "":
        raise RewardRecordError("audit triage signature is not usable")
    return frozenset(part for part in raw.split(",") if part != "")


def _ssh_verify(
    payload: bytes,
    signature: str,
    principal: str,
    allowed: Path,
    when: datetime,
) -> None:
    # ``-Overify-time`` is UTC. ``when`` is an absolute instant.
    stamp = when.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
    with tempfile.TemporaryDirectory(prefix="fc-triage-sig-") as directory:
        root = Path(directory)
        os.chmod(root, 0o700)
        sig_path = root / "statement.sig"
        sig_path.write_text(signature, encoding="utf-8")
        os.chmod(sig_path, 0o600)
        completed = _run_keygen(
            [
                "-Y",
                "verify",
                "-f",
                str(allowed),
                "-I",
                principal,
                "-n",
                NAMESPACE,
                "-s",
                str(sig_path),
                f"-Overify-time={stamp}",
            ],
            input_bytes=payload,
            reason="audit triage signature is not usable",
        )
    if completed.returncode != 0:
        raise RewardRecordError("audit triage signature is not usable")


def _read_allowed(path: Path) -> str:
    parent = path.parent
    try:
        directory = os.lstat(parent)
    except OSError as exc:
        raise RewardRecordError("audit triage allowed signers are not usable") from exc
    if stat.S_ISLNK(directory.st_mode) or not stat.S_ISDIR(directory.st_mode):
        raise RewardRecordError("audit triage allowed signers are not usable")
    if directory.st_uid != 0 or stat.S_IMODE(directory.st_mode) & 0o022:
        raise RewardRecordError("audit triage allowed signers are not usable")
    grader = _grader_account()
    if grader is not None and _writable_by(directory, grader.pw_uid, grader.pw_gid):
        raise RewardRecordError("audit triage allowed signers are not usable")
    fd = _open_nofollow(path, "audit triage allowed signers are not usable")
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise RewardRecordError("audit triage allowed signers are not usable")
        if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != _ALLOWED_MODE:
            raise RewardRecordError("audit triage allowed signers are not usable")
        if grader is not None and _writable_by(info, grader.pw_uid, grader.pw_gid):
            raise RewardRecordError("audit triage allowed signers are not usable")
        if info.st_size > _MAX_SIGNERS_BYTES:
            raise RewardRecordError("audit triage allowed signers are not usable")
        data = _read_fd(fd, _MAX_SIGNERS_BYTES)
    finally:
        os.close(fd)
    try:
        return data.decode("utf-8")
    except UnicodeError as exc:
        raise RewardRecordError("audit triage allowed signers are not usable") from exc


def _parse_allowed(text: str) -> tuple[SignerEntry, ...]:
    found: list[SignerEntry] = []
    seen: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        entry = _parse_signer_line(stripped)
        identity = entry.fingerprint()
        if identity in seen:
            raise RewardRecordError("audit triage allowed signers are not usable")
        seen.add(identity)
        found.append(entry)
    if not found:
        raise RewardRecordError("audit triage allowed signers are not usable")
    return tuple(found)


def _parse_signer_line(line: str) -> SignerEntry:
    """One principal, no pattern characters, and a UTC ``valid-after``.

    OpenSSH allows several comma-separated principals, and ``*``, ``?``,
    and ``!`` as patterns. One key listed twice, or once as ``alice,bob``,
    would otherwise count as two votes. This parser refuses those lines.
    """
    parts = line.split()
    if len(parts) < 3:
        raise RewardRecordError("audit triage allowed signers are not usable")
    principal = parts[0]
    if principal == "" or any(char in _PRINCIPAL_FORBIDDEN for char in principal):
        raise RewardRecordError("audit triage allowed signers are not usable")
    index = 1
    options: tuple[tuple[str, str], ...] = ()
    if "=" in parts[1]:
        options = _parse_options(parts[1])
        index = 2
    if len(parts) <= index + 1:
        raise RewardRecordError("audit triage allowed signers are not usable")
    key_type = parts[index]
    key_blob = parts[index + 1]
    if key_type not in _KEY_TYPES or key_blob == "":
        raise RewardRecordError("audit triage allowed signers are not usable")
    entry = SignerEntry(
        principals=(principal,),
        options=options,
        key_type=key_type,
        key_blob=key_blob,
        raw=line,
    )
    if NAMESPACE not in _namespaces(entry):
        raise RewardRecordError("audit triage allowed signers are not usable")
    if _openssh_time(entry.option("valid-after") or "") is None:
        raise RewardRecordError("audit triage allowed signers are not usable")
    return entry


def _parse_options(text: str) -> tuple[tuple[str, str], ...]:
    found: list[tuple[str, str]] = []
    for part in text.split(","):
        if part == "" or "=" not in part:
            raise RewardRecordError("audit triage allowed signers are not usable")
        name, value = part.split("=", 1)
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if name == "" or value == "":
            raise RewardRecordError("audit triage allowed signers are not usable")
        found.append((name, value))
    return tuple(found)


def _fingerprint_of(key_type: str, key_blob: str) -> str:
    line = f"{key_type} {key_blob}\n".encode("ascii")
    completed = _run_keygen(
        ["-lf", "-"],
        input_bytes=line,
        reason="audit triage signature is not usable",
    )
    if completed.returncode != 0:
        raise RewardRecordError("audit triage signature is not usable")
    return _fingerprint_token(completed.stdout.decode("utf-8", "replace"))


def _fingerprint_token(text: str) -> str:
    for token in text.split():
        if token.startswith("SHA256:"):
            return token
    raise RewardRecordError("audit triage key is not usable")


def SignerEntry_fingerprint(self: SignerEntry) -> str:
    return _fingerprint_of(self.key_type, self.key_blob)


# Bound after the class body so the helper can live with the other parsers.
SignerEntry.fingerprint = SignerEntry_fingerprint  # type: ignore[method-assign]


def _refuse_exposed_key(path: Path) -> None:
    fd = _open_nofollow(path, "audit triage key is not usable")
    try:
        info = os.fstat(fd)
    finally:
        os.close(fd)
    if not stat.S_ISREG(info.st_mode):
        raise RewardRecordError("audit triage key is not usable")
    mode = stat.S_IMODE(info.st_mode)
    if mode & 0o077 or mode == 0o644:
        raise RewardRecordError("audit triage key is not usable")
    grader = _grader_account()
    if grader is not None and info.st_uid == grader.pw_uid:
        raise RewardRecordError("audit triage key is not usable")
    if grader is not None and mode & 0o040 and info.st_gid == grader.pw_gid:
        raise RewardRecordError("audit triage key is not usable")


def _grader_account() -> pwd.struct_passwd | None:
    try:
        user = pwd.getpwnam(GRADER_USER)
    except KeyError:
        return None
    if user.pw_uid == 0:
        return None
    return user


def _writable_by(info: os.stat_result, uid: int, gid: int) -> bool:
    mode = stat.S_IMODE(info.st_mode)
    if info.st_uid == uid and mode & 0o200:
        return True
    if info.st_gid == gid and mode & 0o020:
        return True
    return bool(mode & 0o002)


def _open_nofollow(path: Path | str, reason: str) -> int:
    """Open ``path`` for reading without following a symlink or blocking.

    ``O_NONBLOCK`` is what stops a FIFO from hanging the grader. A
    regular file is unaffected.
    """
    try:
        return os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        raise RewardRecordError(reason) from exc


def _read_fd(fd: int, limit: int) -> bytes:
    found = bytearray()
    while len(found) <= limit:
        block = os.read(fd, 65536)
        if block == b"":
            return bytes(found)
        found.extend(block)
    raise RewardRecordError("audit triage drop file is not usable")


def _write_fd(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        wrote = os.write(fd, view)
        if wrote <= 0:
            raise RewardRecordError("audit triage drop file is not usable")
        view = view[wrote:]


def _completed_text(completed: subprocess.CompletedProcess[bytes] | subprocess.CompletedProcess[str]) -> str:
    chunks: list[str] = []
    for part in (completed.stderr, completed.stdout):
        if part is None:
            continue
        if isinstance(part, bytes):
            chunks.append(part.decode("utf-8", "replace"))
        else:
            chunks.append(part)
    return "".join(chunks)


def _checked_keygen() -> str:
    """Absolute ``SSH_KEYGEN_PATH`` after the root-owned binary checks."""
    raw = SSH_KEYGEN_PATH
    if type(raw) is not str or not raw.startswith("/") or raw.endswith("/"):
        raise RewardRecordError("audit triage requires ssh-keygen")
    path = Path(raw)
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise RewardRecordError("audit triage requires ssh-keygen") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise RewardRecordError("audit triage requires ssh-keygen")
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
        raise RewardRecordError("audit triage requires ssh-keygen")
    if not os.access(path, os.X_OK):
        raise RewardRecordError("audit triage requires ssh-keygen")
    return str(path)


def _run_keygen(
    args: list[str],
    *,
    reason: str,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run the checked ``ssh-keygen``. A timeout or an exec error is refused."""
    binary = _checked_keygen()
    command = [binary, *args]
    try:
        return subprocess.run(
            command,
            input=input_bytes,
            stdin=None if input_bytes is not None else subprocess.DEVNULL,
            check=False,
            capture_output=True,
            timeout=_KEYGEN_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise RewardRecordError(reason) from exc


def _openssh_version() -> tuple[int, int]:
    """Version of the checked ``ssh-keygen`` binary.

    ``ssh -V`` is not used. OpenSSH's ``ssh-keygen`` has no version flag
    (``-V`` is a certificate validity interval). The probe runs that
    binary with ``-Overify-time``. A banner of ``OpenSSH_M.N`` in the
    output is the version. When the binary prints no banner, accepting
    the option is OpenSSH 8.7 or newer and the returned pair is that
    floor. Rejecting the option, or timing out, is a refusal.
    """
    with tempfile.TemporaryDirectory(prefix="fc-triage-version-") as directory:
        root = Path(directory)
        os.chmod(root, 0o700)
        allowed = root / "allowed"
        signature = root / "statement.sig"
        allowed.write_text(
            f'{_PROBE_PRINCIPAL} namespaces="{NAMESPACE}",valid-after="{_PROBE_STAMP}" '
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n",
            encoding="utf-8",
        )
        os.chmod(allowed, 0o644)
        signature.write_text(
            "-----BEGIN SSH SIGNATURE-----\nAAAA\n-----END SSH SIGNATURE-----\n",
            encoding="utf-8",
        )
        os.chmod(signature, 0o600)
        completed = _run_keygen(
            [
                "-Y",
                "verify",
                "-f",
                str(allowed),
                "-I",
                _PROBE_PRINCIPAL,
                "-n",
                NAMESPACE,
                "-s",
                str(signature),
                f"-Overify-time={_PROBE_STAMP}",
            ],
            reason="audit triage requires ssh-keygen",
        )
    text = _completed_text(completed)
    match = _OPENSSH_VERSION.search(text)
    if match is not None:
        version = (int(match.group(1)), int(match.group(2)))
        if version < _MIN_OPENSSH:
            raise RewardRecordError("audit triage requires OpenSSH 8.7 or newer")
        return version
    lowered = text.lower()
    if "invalid option" in lowered or "unknown option" in lowered or "unsupported" in lowered:
        raise RewardRecordError("audit triage requires OpenSSH 8.7 or newer")
    if completed.returncode != 0 and "signature" in lowered:
        return _MIN_OPENSSH
    raise RewardRecordError("audit triage requires OpenSSH 8.7 or newer")

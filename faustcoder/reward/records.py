"""MAC'd reward-row records (ADR-0006 D3, option H).

The library can persist a ``GroupHeader`` and then one ``RewardRowRecord``
per member, including ungraded members. T10 wires that writer into a
rollout. The tag is HMAC-SHA256 under a key scoped to one run. The run
key is HKDF-SHA256 of a per-Spark root key and that run id. The root key
is read from a file that is mode ``0400`` and owned by the dedicated
``fc-grader`` uid. This module does not generate, print or log key bytes.

``load_records`` and ``rl_batch_from_records`` re-check every row:
MAC, pins, source, task, reference and profile, then ``grade_receipt``
with no ``rerun``, ``known_good`` or ``triage``. Rewards are not read
off the row. A group with a missing, ungraded or quarantined member is
dropped and claimed in the consumed log so it is not re-entered. A
re-check does not observe A7 rates.

The pass-weighted re-execution audit and Ed25519 are not this module.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import hmac
import json
import os
import pwd
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from faustcoder.canonical import canonical_bytes, content_digest_for, loads_strict
from faustcoder.compiler import NATIVE_FAUST_VERSION
from faustcoder.reward.grader import grade_receipt, task_binding_digest, task_digest_full
from faustcoder.reward.profiles import REWARD_PROFILES
from faustcoder.reward.types import (
    QUARANTINE_REASONS,
    QuarantineQueue,
    QuarantineRecord,
    RewardableSignalReceipt,
    SourceAttributedFailure,
    Ungraded,
    UngradedRateTracker,
    UngradedReason,
)
from faustcoder.sandbox import NODE_SANDBOX_FLAGS
from faustcoder.schemas import schema_directory
from faustcoder.signal import SIGNAL_SCHEMA_VERSION

DOMAIN_ROW = b"faustcoder.reward-row.v1"
DOMAIN_GROUP = b"faustcoder.reward-group.v1"
HKDF_INFO_PREFIX = b"faustcoder.reward.v1"
ROOT_KEY_PATH = Path("/etc/faustcoder/reward-root.key")
GRADER_USER = "fc-grader"
_ROOT_KEY_BYTES = 32
_MAX_GROUP = 64
_COMPILER_SCHEMA = "0.3.2"
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_OUTCOME = re.compile(r"^(pass|fail|source_attributed|ungraded:[a-z0-9_]+)$")
_KINDS = frozenset({"signal", "compiler", "crash"})
_GRADER_SOURCES = (
    "faustcoder/canonical.py",
    "faustcoder/compiler.py",
    "faustcoder/sandbox.py",
    "faustcoder/schemas.py",
    "faustcoder/signal.py",
    "faustcoder/signal_suite.py",
    "faustcoder/reward/__init__.py",
    "faustcoder/reward/grader.py",
    "faustcoder/reward/ledger.py",
    "faustcoder/reward/profiles.py",
    "faustcoder/reward/records.py",
    "faustcoder/reward/types.py",
)
_LOG_MODE = 0o640
_grader_digest_cache: str | None = None
_HEADER_STATEMENT = (
    "group_id",
    "group_size",
    "key_id",
    "run_id",
    "task_digest_full",
    "type",
)
_ROW_IDENTITY = (
    "compiler_schema_version",
    "envelope",
    "grader_commit",
    "grader_digest",
    "group_id",
    "group_size",
    "harness_digest",
    "kind",
    "member_index",
    "native_envelope",
    "native_faust_version",
    "node_flags",
    "outcome",
    "policy_checkpoint",
    "profile_digest",
    "profiles_allowlist_digest",
    "reference_digest",
    "rollout_id",
    "run_id",
    "signal_schema_version",
    "source_sha256",
    "stimulus_digest",
    "task",
    "task_binding_digest",
    "task_digest_full",
)


class RewardKeyError(Exception):
    """The reward root key cannot be used. The message names no key bytes."""


class RewardRecordError(Exception):
    """A persisted reward record or its log failed closed."""


def grader_digest() -> str:
    """SHA-256 over the reward, signal, compiler, sandbox and schema sources.

    The digest is the bytes on disk, not a git sha, so a dirty tree is
    a different pin. It is computed once in this process. ``canonical.py``
    and ``signal_suite.py`` are part of the pin.
    """
    global _grader_digest_cache
    if _grader_digest_cache is not None:
        return _grader_digest_cache
    root = Path(__file__).resolve().parents[2]
    files: list[tuple[str, Path]] = [(name, root / name) for name in _GRADER_SOURCES]
    schema_root = schema_directory()
    for path in sorted(schema_root.glob("*.schema.json")):
        files.append((path.name, path))
    hasher = hashlib.sha256()
    for label, path in files:
        data = path.read_bytes()
        hasher.update(label.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(len(data).to_bytes(8, "big"))
        hasher.update(data)
    _grader_digest_cache = "sha256:" + hasher.hexdigest()
    return _grader_digest_cache


def profiles_allowlist_digest() -> str:
    """Digest of ``REWARD_PROFILES``. A changed allowlist is a new pin."""
    return content_digest_for(dict(REWARD_PROFILES))


def current_harness_digest() -> str:
    """The harness pin this process would write. Missing pins fail closed."""
    try:
        from faustcoder.signal import harness_digest

        digest = harness_digest()
    except Exception as exc:
        raise RewardRecordError("harness pin is not available") from exc
    if type(digest) is not str or _DIGEST.fullmatch(digest) is None:
        raise RewardRecordError("harness pin is not available")
    return digest


def _grader_uid() -> int:
    try:
        user = pwd.getpwnam(GRADER_USER)
    except KeyError as exc:
        raise RewardKeyError("reward root key owner fc-grader is not a user") from exc
    if user.pw_uid == 0:
        raise RewardKeyError("reward root key owner fc-grader is not a user")
    return user.pw_uid


def _key_directory(parent: Path) -> os.stat_result:
    """Refuse a symlink or a group- or world-writable directory.

    The owner is checked after the file, so a wrong file uid still
    reports the file. Root may own the directory (``/etc/faustcoder``).
    """
    try:
        info = os.lstat(parent)
    except OSError as exc:
        raise RewardKeyError("reward root key directory cannot be used") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise RewardKeyError("reward root key directory cannot be used")
    if stat.S_IMODE(info.st_mode) & 0o022:
        raise RewardKeyError("reward root key directory cannot be used")
    return info


def load_root_key(path: Path | str | None = None, *, grader_uid: int | None = None) -> bytes:
    """Read the 32-byte root key. Mode must be ``0400`` and the owner the grader uid.

    ``path`` defaults to ``ROOT_KEY_PATH``. ``grader_uid`` defaults to the
    ``fc-grader`` account. Tests pass the uid that owns their temporary
    file. Uid 0 is refused. The returned bytes are the key. This function
    does not log them.
    """
    location = ROOT_KEY_PATH if path is None else Path(path)
    expected = _grader_uid() if grader_uid is None else grader_uid
    if type(expected) is not int or isinstance(expected, bool) or expected <= 0:
        raise RewardKeyError("reward root key must be owned by the grader uid")
    directory = _key_directory(location.parent)
    try:
        fd = os.open(
            location,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
        )
    except OSError as exc:
        raise RewardKeyError("reward root key cannot be opened") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise RewardKeyError("reward root key must be a regular file")
        if stat.S_IMODE(info.st_mode) != 0o400:
            raise RewardKeyError("reward root key must be mode 0400")
        if info.st_nlink != 1:
            raise RewardKeyError("reward root key must not be linked elsewhere")
        if info.st_uid == 0 or info.st_uid != expected:
            raise RewardKeyError("reward root key must be owned by the grader uid")
        if directory.st_uid != expected and directory.st_uid != 0:
            raise RewardKeyError("reward root key directory cannot be used")
        if info.st_size != _ROOT_KEY_BYTES:
            raise RewardKeyError("reward root key must be 32 bytes")
        key = os.read(fd, _ROOT_KEY_BYTES)
    finally:
        os.close(fd)
    if len(key) != _ROOT_KEY_BYTES:
        raise RewardKeyError("reward root key must be 32 bytes")
    return key


def _hkdf_sha256(ikm: bytes, info: bytes, length: int = 32) -> bytes:
    """HKDF-SHA256 (RFC 5869) with the default salt of HashLen zeros."""
    salt = b"\x00" * 32
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    okm = b""
    block = b""
    counter = 1
    while len(okm) < length:
        block = hmac.new(prk, block + info + bytes((counter,)), hashlib.sha256).digest()
        okm += block
        counter += 1
    return okm[:length]


def derive_run_key(root_key: bytes, run_id: str) -> bytes:
    """HKDF of the root key. ``info`` is ``faustcoder.reward.v1`` plus ``run_id``."""
    if type(root_key) is not bytes or len(root_key) != _ROOT_KEY_BYTES:
        raise RewardKeyError("reward root key must be 32 bytes")
    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        raise RewardKeyError("reward run id is not usable")
    return _hkdf_sha256(root_key, HKDF_INFO_PREFIX + run_id.encode("ascii"))


def key_id_for(run_key: bytes) -> str:
    """Public id of a run key: HMAC(run_key, ``key-id``) truncated to 16 bytes."""
    if type(run_key) is not bytes or len(run_key) != _ROOT_KEY_BYTES:
        raise RewardKeyError("reward run key is not usable")
    return hmac.new(run_key, b"key-id", hashlib.sha256).digest()[:16].hex()


class RewardKeyring:
    """One run's keys. A row that claims another run does not resolve.

    The root key is not kept after the run key is derived. ``repr`` does
    not include key bytes. Pickle is refused.
    """

    def __init__(self, root_key: bytes, *, run_id: str) -> None:
        if type(root_key) is not bytes or len(root_key) != _ROOT_KEY_BYTES:
            raise RewardKeyError("reward root key must be 32 bytes")
        if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
            raise RewardKeyError("reward run id is not usable")
        run_key = derive_run_key(root_key, run_id)
        self._run_id = run_id
        self._run_key = run_key
        self._key_id = key_id_for(run_key)
        self._retired: dict[str, bytes] = {}

    def __repr__(self) -> str:
        return "RewardKeyring(redacted)"

    def __getstate__(self) -> None:
        raise RewardKeyError("reward keyring cannot be serialized")

    def __setstate__(self, state: object) -> None:
        raise RewardKeyError("reward keyring cannot be serialized")

    @property
    def run_id(self) -> str:
        return self._run_id

    def run_key(self, run_id: str) -> bytes:
        if type(run_id) is not str or run_id != self._run_id:
            raise RewardKeyError("reward key id is not in the keyring")
        return bytes(self._run_key)

    def key_id(self, run_id: str) -> str:
        if type(run_id) is not str or run_id != self._run_id:
            raise RewardKeyError("reward key id is not in the keyring")
        return self._key_id

    def remember(self, run_key: bytes) -> str:
        """Keep a retired key for this run only. The id is public."""
        ident = key_id_for(run_key)
        self._retired[ident] = bytes(run_key)
        return ident

    def resolve(self, *, key_id: str, run_id: str) -> bytes:
        if type(key_id) is not str or type(run_id) is not str or run_id != self._run_id:
            raise RewardKeyError("reward key id is not in the keyring")
        if _equal(self._key_id, key_id):
            return bytes(self._run_key)
        retired = self._retired.get(key_id)
        if retired is not None and _equal(key_id_for(retired), key_id):
            return bytes(retired)
        raise RewardKeyError("reward key id is not in the keyring")


def _equal(expected: str, presented: object) -> bool:
    if type(presented) is not str or len(presented) != len(expected) or expected == "":
        return False
    return hmac.compare_digest(expected, presented)


def _tag(domain: bytes, statement: Mapping[str, Any], run_key: bytes) -> str:
    try:
        payload = canonical_bytes(dict(statement))
    except UnicodeEncodeError as exc:
        raise RewardRecordError("reward record is not usable") from exc
    message = domain + b"\n" + payload
    return hmac.new(run_key, message, hashlib.sha256).hexdigest()


def _freeze(value: object) -> Any:
    return loads_strict(canonical_bytes(value).decode("utf-8"))


@dataclass(frozen=True, repr=False)
class GroupHeader:
    """Signed before any member. ``G`` is ``group_size``."""

    group_id: str
    task_digest_full: str
    group_size: int
    run_id: str
    key_id: str
    mac: str
    log_index: int = -1

    def __repr__(self) -> str:
        return f"GroupHeader(group_id={self.group_id!r}, group_size={self.group_size!r})"

    def statement(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "group_size": self.group_size,
            "key_id": self.key_id,
            "run_id": self.run_id,
            "task_digest_full": self.task_digest_full,
            "type": "group_header",
        }

    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self.statement())


@dataclass(frozen=True, repr=False)
class RewardRowRecord:
    """One persisted member. ``source`` is stored beside the signed hash."""

    record_id: str
    run_id: str
    rollout_id: str
    policy_checkpoint: str
    group_id: str
    group_size: int
    member_index: int
    source_sha256: str
    task_digest_full: str
    task_binding_digest: str
    profile_digest: str
    reference_digest: str
    stimulus_digest: str
    harness_digest: str
    compiler_schema_version: str
    signal_schema_version: str
    native_faust_version: str
    node_flags: tuple[str, ...]
    grader_digest: str
    grader_commit: str
    profiles_allowlist_digest: str
    kind: str
    envelope: dict[str, Any]
    native_envelope: dict[str, Any] | None
    outcome: str
    graded_at: str
    key_id: str
    mac: str
    task: dict[str, Any]
    source: bytes
    log_index: int = -1

    def __repr__(self) -> str:
        return f"RewardRowRecord(record_id={self.record_id!r}, group_id={self.group_id!r})"

    def identity_body(self) -> dict[str, Any]:
        return {name: _json_field(self, name) for name in _ROW_IDENTITY}

    def statement(self) -> dict[str, Any]:
        body = self.identity_body()
        body["graded_at"] = self.graded_at
        body["key_id"] = self.key_id
        body["record_id"] = self.record_id
        body["type"] = "reward_row"
        return body

    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self.statement())


def _json_field(record: RewardRowRecord, name: str) -> Any:
    value = getattr(record, name)
    if name == "node_flags":
        return list(value)
    return value


def mac(record: GroupHeader | RewardRowRecord, run_key: bytes) -> str:
    """HMAC-SHA256 of the record statement under ``run_key``."""
    domain = DOMAIN_GROUP if isinstance(record, GroupHeader) else DOMAIN_ROW
    return _tag(domain, record.statement(), run_key)


def verify(record: GroupHeader | RewardRowRecord, keyring: RewardKeyring) -> None:
    """Raise when the MAC or the row id does not match. Uses ``compare_digest``."""
    if not isinstance(keyring, RewardKeyring):
        raise RewardKeyError("reward verify requires a keyring")
    run_key = keyring.resolve(key_id=record.key_id, run_id=record.run_id)
    if not _equal(mac(record, run_key), record.mac):
        raise RewardRecordError("reward record mac does not verify")
    if isinstance(record, RewardRowRecord):
        ident = hashlib.sha256(canonical_bytes(record.identity_body())).hexdigest()
        if not _equal(ident, record.record_id):
            raise RewardRecordError("reward record id does not match its body")


def _count(value: object, label: str, *, zero: bool = False) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise RewardRecordError(f"reward record {label} is not an integer")
    if value < 0 or (value == 0 and not zero):
        raise RewardRecordError(f"reward record {label} is not an integer")
    if value > _MAX_GROUP:
        raise RewardRecordError("reward group is larger than 64")
    return value


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or _RUN_ID.fullmatch(value) is None:
        raise RewardRecordError(f"reward record {label} is not usable")
    return value


def sign_group_header(
    *,
    group_id: str,
    task_digest_full: str,
    group_size: int,
    run_id: str,
    run_key: bytes,
) -> GroupHeader:
    """MAC a header. Callers write it before the members."""
    key_id = key_id_for(run_key)
    if type(task_digest_full) is not str or _DIGEST.fullmatch(task_digest_full) is None:
        raise RewardRecordError("reward record task digest is not usable")
    header = GroupHeader(
        group_id=_identifier(group_id, "group id"),
        task_digest_full=task_digest_full,
        group_size=_count(group_size, "group size"),
        run_id=_identifier(run_id, "run id"),
        key_id=key_id,
        mac="",
    )
    return GroupHeader(
        group_id=header.group_id,
        task_digest_full=header.task_digest_full,
        group_size=header.group_size,
        run_id=header.run_id,
        key_id=key_id,
        mac=mac(header, run_key),
    )


def _refuse_passed_contradiction(payload: Mapping[str, Any]) -> None:
    """Refuse a row whose ``passed`` bit does not match ``metrics.failures``."""
    if "passed" not in payload:
        return
    passed = payload.get("passed")
    metrics = payload.get("metrics")
    failures = metrics.get("failures") if isinstance(metrics, dict) else None
    if (
        type(passed) is not bool
        or not isinstance(failures, list)
        or any(type(item) is not str for item in failures)
        or passed is not (failures == [])
    ):
        raise RewardRecordError("passed does not match failures")


def _signal_shaped(kind: str, envelope: Mapping[str, Any], payload: Mapping[str, Any]) -> bool:
    schema = envelope.get("schema_version")
    return (
        kind == "signal"
        or schema == SIGNAL_SCHEMA_VERSION
        or "passed" in payload
        or payload.get("purpose") == "reward"
    )


def _payload_has_signal_pins(payload: Mapping[str, Any]) -> bool:
    if any(name in payload for name in ("profile", "test_suite_digest", "reference_digest", "harness_digest")):
        return True
    metrics = payload.get("metrics")
    return isinstance(metrics, dict) and "stimulus" in metrics


def _signal_pin_values(payload: Mapping[str, Any]) -> tuple[str, str, str]:
    """Profile, reference and stimulus digests. Harness is checked by the caller."""
    suite = payload.get("test_suite_digest")
    profile = payload.get("profile")
    if type(suite) is not str or not isinstance(profile, dict):
        raise RewardRecordError("reward record profile is not usable")
    if suite != content_digest_for(profile):
        raise RewardRecordError("reward record profile is not usable")
    reference = payload.get("reference_digest", "")
    if type(reference) is not str:
        raise RewardRecordError("reward record reference is not usable")
    stimulus = ""
    metrics = payload.get("metrics")
    if isinstance(metrics, dict) and "stimulus" in metrics:
        stimulus = content_digest_for(metrics["stimulus"])
    harness = payload.get("harness_digest")
    if type(harness) is not str or _DIGEST.fullmatch(harness) is None:
        raise RewardRecordError("reward record harness is not usable")
    return suite, reference, stimulus


def sign_reward_row(
    *,
    run_key: bytes,
    run_id: str,
    rollout_id: str,
    policy_checkpoint: str,
    group_id: str,
    group_size: int,
    member_index: int,
    source: bytes,
    task: Mapping[str, Any],
    envelope: Mapping[str, Any],
    outcome: str,
    kind: str,
    graded_at: str,
    native_envelope: Mapping[str, Any] | None = None,
    grader_commit: str = "",
) -> RewardRowRecord:
    """Sign one member. This does not grade. The loader grades again.

    ``outcome`` is what the writer claims. A ``passed`` bit that does not
    match ``metrics.failures`` is refused here. A signal envelope cannot
    be signed as another kind. Compiler and crash envelopes that carry a
    harness, profile, reference or stimulus are checked the same way.
    """
    if isinstance(outcome, str) and outcome.startswith("shadow"):
        raise RewardRecordError("a shadow log is not a reward row")
    if type(outcome) is not str or _OUTCOME.fullmatch(outcome) is None:
        raise RewardRecordError("reward record outcome is not usable")
    if kind not in _KINDS:
        raise RewardRecordError("reward record kind is not usable")
    if type(source) is not bytes:
        raise RewardRecordError("reward record source is not bytes")
    if type(graded_at) is not str or _STAMP.fullmatch(graded_at) is None:
        raise RewardRecordError("reward record graded_at is not usable")
    if type(policy_checkpoint) is not str or _DIGEST.fullmatch(policy_checkpoint) is None:
        raise RewardRecordError("reward record checkpoint is not usable")
    if type(grader_commit) is not str or len(grader_commit) > 128 or "\n" in grader_commit:
        raise RewardRecordError("reward record grader commit is not usable")
    size = _count(group_size, "group size")
    index = _count(member_index, "member index", zero=True)
    if index >= size:
        raise RewardRecordError("reward record member index is outside the group")
    frozen_task = _freeze(dict(task))
    frozen_envelope = _freeze(dict(envelope))
    if not isinstance(frozen_task, dict) or not isinstance(frozen_envelope, dict):
        raise RewardRecordError("reward record task or envelope is not an object")
    payload = frozen_envelope.get("payload")
    if not isinstance(payload, dict):
        raise RewardRecordError("reward record envelope has no payload")
    _refuse_passed_contradiction(payload)
    if _signal_shaped(kind, frozen_envelope, payload) and kind != "signal":
        raise RewardRecordError("reward record kind does not match the envelope")
    source_sha = hashlib.sha256(source).hexdigest()
    if kind == "signal" and payload.get("source_sha256") != source_sha:
        raise RewardRecordError("reward record source does not match the envelope")
    profile_digest = ""
    reference_digest = ""
    stimulus_digest = ""
    if kind == "signal" or _payload_has_signal_pins(payload):
        profile_digest, reference_digest, stimulus_digest = _signal_pin_values(payload)
        if payload.get("harness_digest") != current_harness_digest():
            raise RewardRecordError("reward record harness is not usable")
    native_frozen: dict[str, Any] | None
    if native_envelope is None:
        native_frozen = None
        native_version = ""
    else:
        frozen_native = _freeze(dict(native_envelope))
        if not isinstance(frozen_native, dict):
            raise RewardRecordError("reward record native envelope is not an object")
        native_frozen = frozen_native
        native_version = NATIVE_FAUST_VERSION
    identity = {
        "compiler_schema_version": _COMPILER_SCHEMA,
        "envelope": frozen_envelope,
        "grader_commit": grader_commit,
        "grader_digest": grader_digest(),
        "group_id": _identifier(group_id, "group id"),
        "group_size": size,
        "harness_digest": current_harness_digest(),
        "kind": kind,
        "member_index": index,
        "native_envelope": native_frozen,
        "native_faust_version": native_version,
        "node_flags": list(NODE_SANDBOX_FLAGS),
        "outcome": outcome,
        "policy_checkpoint": policy_checkpoint,
        "profile_digest": profile_digest,
        "profiles_allowlist_digest": profiles_allowlist_digest(),
        "reference_digest": reference_digest,
        "rollout_id": _identifier(rollout_id, "rollout id"),
        "run_id": _identifier(run_id, "run id"),
        "signal_schema_version": SIGNAL_SCHEMA_VERSION,
        "source_sha256": source_sha,
        "stimulus_digest": stimulus_digest,
        "task": frozen_task,
        "task_binding_digest": task_binding_digest(frozen_task),
        "task_digest_full": task_digest_full(frozen_task),
    }
    record_id = hashlib.sha256(canonical_bytes(identity)).hexdigest()
    key_id = key_id_for(run_key)
    record = RewardRowRecord(
        record_id=record_id,
        run_id=identity["run_id"],
        rollout_id=identity["rollout_id"],
        policy_checkpoint=policy_checkpoint,
        group_id=identity["group_id"],
        group_size=size,
        member_index=index,
        source_sha256=source_sha,
        task_digest_full=identity["task_digest_full"],
        task_binding_digest=identity["task_binding_digest"],
        profile_digest=profile_digest,
        reference_digest=reference_digest,
        stimulus_digest=stimulus_digest,
        harness_digest=identity["harness_digest"],
        compiler_schema_version=_COMPILER_SCHEMA,
        signal_schema_version=SIGNAL_SCHEMA_VERSION,
        native_faust_version=native_version,
        node_flags=tuple(NODE_SANDBOX_FLAGS),
        grader_digest=identity["grader_digest"],
        grader_commit=grader_commit,
        profiles_allowlist_digest=identity["profiles_allowlist_digest"],
        kind=kind,
        envelope=frozen_envelope,
        native_envelope=native_frozen,
        outcome=outcome,
        graded_at=graded_at,
        key_id=key_id,
        mac="",
        task=frozen_task,
        source=bytes(source),
    )
    return RewardRowRecord(
        record_id=record.record_id,
        run_id=record.run_id,
        rollout_id=record.rollout_id,
        policy_checkpoint=record.policy_checkpoint,
        group_id=record.group_id,
        group_size=record.group_size,
        member_index=record.member_index,
        source_sha256=record.source_sha256,
        task_digest_full=record.task_digest_full,
        task_binding_digest=record.task_binding_digest,
        profile_digest=record.profile_digest,
        reference_digest=record.reference_digest,
        stimulus_digest=record.stimulus_digest,
        harness_digest=record.harness_digest,
        compiler_schema_version=record.compiler_schema_version,
        signal_schema_version=record.signal_schema_version,
        native_faust_version=record.native_faust_version,
        node_flags=record.node_flags,
        grader_digest=record.grader_digest,
        grader_commit=record.grader_commit,
        profiles_allowlist_digest=record.profiles_allowlist_digest,
        kind=record.kind,
        envelope=record.envelope,
        native_envelope=record.native_envelope,
        outcome=record.outcome,
        graded_at=record.graded_at,
        key_id=record.key_id,
        mac=mac(record, run_key),
        task=record.task,
        source=record.source,
    )


def outcome_for(grade: object) -> str:
    """The outcome a re-check must see. A ``ShadowLog`` is refused."""
    from faustcoder.reward.grader import ShadowLog

    if isinstance(grade, ShadowLog):
        raise RewardRecordError("a shadow log is not a reward row")
    if isinstance(grade, RewardableSignalReceipt):
        return "pass" if grade.passed else "fail"
    if isinstance(grade, SourceAttributedFailure):
        return "source_attributed"
    if isinstance(grade, Ungraded):
        return f"ungraded:{grade.reason.value}"
    raise RewardRecordError("reward regrade did not return a grade")


@dataclass(frozen=True)
class RowCheck:
    """One re-check. ``reason`` is empty when the row may train."""

    reason: str
    grade: object = None


def regrade_record(
    record: RewardRowRecord,
    keyring: RewardKeyring,
    *,
    queue: QuarantineQueue | None = None,
    rates: UngradedRateTracker | None = None,
) -> RowCheck:
    """Re-check one row. Pins and binding failures do not call ``grade_receipt``.

    ``rates`` is ignored. The rollout already counted the sample, and a
    reload must not observe it again.
    """
    del rates
    verify(record, keyring)
    if _pins_stale(record):
        return RowCheck("stale_pin")
    if _binding_failed(record):
        return RowCheck("binding")
    grade = grade_receipt(
        record.envelope,
        task=record.task,
        queue=queue,
        row_record_id=record.record_id,
        group_id=record.group_id,
    )
    try:
        fresh = outcome_for(grade)
    except RewardRecordError:
        return RowCheck("shadow")
    if fresh != record.outcome:
        return RowCheck("outcome", grade)
    return RowCheck("", grade)


def _pins_stale(record: RewardRowRecord) -> bool:
    if record.grader_digest != grader_digest():
        return True
    if record.profiles_allowlist_digest != profiles_allowlist_digest():
        return True
    if record.harness_digest != current_harness_digest():
        return True
    if record.signal_schema_version != SIGNAL_SCHEMA_VERSION:
        return True
    if record.compiler_schema_version != _COMPILER_SCHEMA:
        return True
    if list(record.node_flags) != list(NODE_SANDBOX_FLAGS):
        return True
    if record.native_envelope is None:
        return record.native_faust_version != ""
    return record.native_faust_version != NATIVE_FAUST_VERSION


def _signal_pins_mismatch(record: RewardRowRecord, payload: Mapping[str, Any]) -> bool:
    """Harness, profile, reference and stimulus. Used for every kind."""
    profile = payload.get("profile")
    suite = payload.get("test_suite_digest")
    if not isinstance(profile, dict) or type(suite) is not str:
        return True
    try:
        if suite != content_digest_for(profile) or record.profile_digest != suite:
            return True
    except Exception:
        return True
    reference = payload.get("reference_digest", "")
    if type(reference) is not str or record.reference_digest != reference:
        return True
    stimulus = ""
    metrics = payload.get("metrics")
    if isinstance(metrics, dict) and "stimulus" in metrics:
        try:
            stimulus = content_digest_for(metrics["stimulus"])
        except Exception:
            return True
    if record.stimulus_digest != stimulus:
        return True
    if payload.get("harness_digest") != record.harness_digest:
        return True
    return False


def _binding_failed(record: RewardRowRecord) -> bool:
    digest = hashlib.sha256(record.source).hexdigest()
    if digest != record.source_sha256:
        return True
    payload = record.envelope.get("payload")
    if not isinstance(payload, dict):
        return True
    payload_source = payload.get("source_sha256")
    shaped = _signal_shaped(record.kind, record.envelope, payload)
    if shaped and record.kind != "signal":
        return True
    if record.kind == "signal" or shaped:
        if payload_source != digest:
            return True
        if _signal_pins_mismatch(record, payload):
            return True
    else:
        if isinstance(payload_source, str) and payload_source != digest:
            return True
        if (
            _payload_has_signal_pins(payload)
            or record.profile_digest
            or record.reference_digest
            or record.stimulus_digest
        ) and _signal_pins_mismatch(record, payload):
            return True
    try:
        if task_digest_full(record.task) != record.task_digest_full:
            return True
        if task_binding_digest(record.task) != record.task_binding_digest:
            return True
    except Exception:
        return True
    return False


def _read_text(fd: int) -> str:
    """Read a log until EOF. A single capped ``os.read`` drops the tail."""
    chunks: list[bytes] = []
    while True:
        block = os.read(fd, 1024 * 1024)
        if not block:
            break
        chunks.append(block)
    try:
        return b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RewardRecordError("reward record log is not utf-8") from exc


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise RewardRecordError("reward record log write failed")
        view = view[written:]


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class RewardRecordStore:
    """Append-only JSONL. A torn last line is ignored. A bad middle line raises."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append_header(self, header: GroupHeader) -> None:
        body = header.statement()
        body["mac"] = header.mac
        self._append(body)

    def append_row(self, record: RewardRowRecord) -> None:
        body = record.statement()
        body["mac"] = record.mac
        body["source_b64"] = base64.b64encode(record.source).decode("ascii")
        self._append(body)

    def _append(self, body: Mapping[str, Any]) -> None:
        line = canonical_bytes(dict(body)) + b"\n"
        fd = os.open(
            self.path,
            os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_CLOEXEC,
            _LOG_MODE,
        )
        try:
            os.fchmod(fd, _LOG_MODE)
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                _write_all(fd, line)
                os.fsync(fd)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
        _fsync_dir(self.path.parent)


@dataclass(frozen=True)
class LoadedLog:
    """Headers and rows in log order, after a MAC check and a re-check."""

    headers: tuple[GroupHeader, ...]
    rows: tuple[RewardRowRecord, ...]
    checks: tuple[RowCheck, ...]


def load_records(
    path: Path | str,
    keyring: RewardKeyring,
    *,
    queue: QuarantineQueue | None = None,
    rates: UngradedRateTracker | None = None,
) -> LoadedLog:
    """Load one log. Every complete row is verified and re-checked.

    A final line with no newline is a torn write and is ignored. Any
    earlier line that is not JSON fails the load. A bad MAC fails the
    load. ``queue`` and ``rates`` are optional; the batch builder is
    what records drops.
    """
    headers, rows = _parse_log(Path(path))
    for header in headers:
        verify(header, keyring)
    checks: list[RowCheck] = []
    for row in rows:
        checks.append(regrade_record(row, keyring, queue=queue, rates=rates))
    return LoadedLog(headers=headers, rows=rows, checks=tuple(checks))


def _complete_bytes(data: bytes) -> bytes:
    if not data:
        return b""
    if data.endswith(b"\n"):
        return data
    kept, _separator, _tail = data.rpartition(b"\n")
    if not kept:
        return b""
    return kept + b"\n"


def _parse_log(path: Path) -> tuple[tuple[GroupHeader, ...], tuple[RewardRowRecord, ...]]:
    if not path.is_file():
        return (), ()
    fd = os.open(path, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
        try:
            chunks: list[bytes] = []
            while True:
                block = os.read(fd, 1024 * 1024)
                if not block:
                    break
                chunks.append(block)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    data = _complete_bytes(b"".join(chunks))
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RewardRecordError("reward record log is not utf-8") from exc
    headers: list[GroupHeader] = []
    rows: list[RewardRowRecord] = []
    seen_headers: set[str] = set()
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            body = loads_strict(line)
        except Exception as exc:
            raise RewardRecordError(f"reward record log line {number} is corrupt") from exc
        if not isinstance(body, dict):
            raise RewardRecordError(f"reward record log line {number} is corrupt")
        kind = body.get("type")
        try:
            if kind == "group_header":
                header = _header_from_body(body, number - 1)
                if header.group_id in seen_headers:
                    raise RewardRecordError("reward record log repeats a group header")
                seen_headers.add(header.group_id)
                headers.append(header)
            elif kind == "reward_row":
                rows.append(_row_from_body(body, number - 1))
            else:
                raise RewardRecordError(f"reward record log line {number} is corrupt")
        except RewardRecordError:
            raise
        except Exception as exc:
            raise RewardRecordError(f"reward record log line {number} is corrupt") from exc
    return tuple(headers), tuple(rows)


def _header_from_body(body: Mapping[str, Any], log_index: int) -> GroupHeader:
    allowed = set(_HEADER_STATEMENT) | {"mac"}
    if set(body) != allowed:
        raise RewardRecordError("reward record has a field that is not signed")
    mac_value = body["mac"]
    if type(mac_value) is not str or _HEX64.fullmatch(mac_value) is None:
        raise RewardRecordError("reward record mac does not verify")
    return GroupHeader(
        group_id=_identifier(body["group_id"], "group id"),
        task_digest_full=body["task_digest_full"]
        if type(body["task_digest_full"]) is str
        else "",
        group_size=_count(body["group_size"], "group size"),
        run_id=_identifier(body["run_id"], "run id"),
        key_id=body["key_id"] if type(body["key_id"]) is str else "",
        mac=mac_value,
        log_index=log_index,
    )


def _row_from_body(body: Mapping[str, Any], log_index: int) -> RewardRowRecord:
    allowed = set(_ROW_IDENTITY) | {"record_id", "graded_at", "key_id", "type", "mac", "source_b64"}
    if set(body) != allowed:
        raise RewardRecordError("reward record has a field that is not signed")
    mac_value = body["mac"]
    if type(mac_value) is not str or _HEX64.fullmatch(mac_value) is None:
        raise RewardRecordError("reward record mac does not verify")
    record_id = body["record_id"]
    if type(record_id) is not str or _HEX64.fullmatch(record_id) is None:
        raise RewardRecordError("reward record id does not match its body")
    try:
        source = base64.b64decode(body["source_b64"], validate=True)
    except Exception as exc:
        raise RewardRecordError("reward record source is not bytes") from exc
    node_flags = body["node_flags"]
    if not isinstance(node_flags, list) or any(type(item) is not str for item in node_flags):
        raise RewardRecordError("reward record node flags are not usable")
    envelope = body["envelope"]
    task = body["task"]
    native = body["native_envelope"]
    if not isinstance(envelope, dict) or not isinstance(task, dict):
        raise RewardRecordError("reward record task or envelope is not an object")
    if native is not None and not isinstance(native, dict):
        raise RewardRecordError("reward record native envelope is not an object")
    return RewardRowRecord(
        record_id=record_id,
        run_id=_exact_str(body["run_id"], "run id"),
        rollout_id=_exact_str(body["rollout_id"], "rollout id"),
        policy_checkpoint=_exact_str(body["policy_checkpoint"], "checkpoint"),
        group_id=_exact_str(body["group_id"], "group id"),
        group_size=_count(body["group_size"], "group size"),
        member_index=_count(body["member_index"], "member index", zero=True),
        source_sha256=_exact_str(body["source_sha256"], "source hash"),
        task_digest_full=_exact_str(body["task_digest_full"], "task digest"),
        task_binding_digest=_exact_str(body["task_binding_digest"], "task binding"),
        profile_digest=_exact_str(body["profile_digest"], "profile digest"),
        reference_digest=_exact_str(body["reference_digest"], "reference digest"),
        stimulus_digest=_exact_str(body["stimulus_digest"], "stimulus digest"),
        harness_digest=_exact_str(body["harness_digest"], "harness digest"),
        compiler_schema_version=_exact_str(body["compiler_schema_version"], "compiler schema"),
        signal_schema_version=_exact_str(body["signal_schema_version"], "signal schema"),
        native_faust_version=_exact_str(body["native_faust_version"], "native faust version"),
        node_flags=tuple(node_flags),
        grader_digest=_exact_str(body["grader_digest"], "grader digest"),
        grader_commit=_exact_str(body["grader_commit"], "grader commit"),
        profiles_allowlist_digest=_exact_str(
            body["profiles_allowlist_digest"], "profiles allowlist"
        ),
        kind=_exact_str(body["kind"], "kind"),
        envelope=envelope,
        native_envelope=native,
        outcome=_exact_str(body["outcome"], "outcome"),
        graded_at=_exact_str(body["graded_at"], "graded_at"),
        key_id=_exact_str(body["key_id"], "key id"),
        mac=mac_value,
        task=task,
        source=source,
        log_index=log_index,
    )


def _exact_str(value: object, label: str) -> str:
    if type(value) is not str:
        raise RewardRecordError(f"reward record {label} is not usable")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise RewardRecordError(f"reward record {label} is not usable") from exc
    return value


class ConsumedLog:
    """Append-only ``group_id`` decisions. A group already present is refused."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._seen: dict[str, str] = {}
        if self.path.is_file():
            self._replay()

    def disposition(self, group_id: str) -> str | None:
        return self._seen.get(group_id)

    def claim(
        self,
        group_id: str,
        disposition: str,
        *,
        task_digest_full: str,
        policy_checkpoint: str,
    ) -> None:
        if type(disposition) is not str or disposition == "":
            raise RewardRecordError("reward consumed disposition is empty")
        line = {
            "disposition": disposition,
            "group_id": group_id,
            "policy_checkpoint": policy_checkpoint,
            "task_digest_full": task_digest_full,
        }
        encoded = canonical_bytes(line) + b"\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(
            self.path,
            os.O_CREAT | os.O_RDWR | os.O_APPEND | os.O_CLOEXEC,
            _LOG_MODE,
        )
        try:
            os.fchmod(fd, _LOG_MODE)
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                self._seen.clear()
                os.lseek(fd, 0, os.SEEK_SET)
                self._ingest(_read_text(fd))
                if group_id in self._seen:
                    raise RewardRecordError("reward group was already consumed")
                _write_all(fd, encoded)
                os.fsync(fd)
                self._seen[group_id] = disposition
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _replay(self) -> None:
        fd = os.open(self.path, os.O_RDONLY | os.O_CLOEXEC)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
            try:
                text = _read_text(fd)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
        self._ingest(text)

    def _ingest(self, text: str) -> None:
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                body = loads_strict(line)
            except Exception as exc:
                raise RewardRecordError(f"reward consumed log line {number} is corrupt") from exc
            if not isinstance(body, dict):
                raise RewardRecordError(f"reward consumed log line {number} is corrupt")
            group_id = body.get("group_id")
            disposition = body.get("disposition")
            if type(group_id) is not str or type(disposition) is not str or group_id == "":
                raise RewardRecordError(f"reward consumed log line {number} is corrupt")
            if group_id in self._seen:
                raise RewardRecordError("reward consumed log repeats a group")
            self._seen[group_id] = disposition


@dataclass(frozen=True)
class RecordBatch:
    """Rows that may train, and the groups that were dropped."""

    rows: tuple[dict[str, object], ...]
    drops: tuple[tuple[str, str], ...]


def rl_batch_from_records(
    headers: tuple[GroupHeader, ...] | list[GroupHeader],
    records: tuple[RewardRowRecord, ...] | list[RewardRowRecord],
    *,
    keyring: RewardKeyring,
    expected_run_id: str,
    policy_checkpoints: str | tuple[str, ...] | list[str],
    queue: QuarantineQueue,
    rates: UngradedRateTracker,
    consumed: ConsumedLog,
) -> RecordBatch:
    """Build a binary batch. A bad member drops its whole group.

    ``expected_run_id`` is the run this builder accepts. ``policy_checkpoints``
    is the allowlist for ``policy_checkpoint``. A mismatch raises before
    any group is claimed. A1 source failures are graded ``0.0`` members.
    Ungraded, quarantined, stale, incomplete and duplicate groups
    contribute no row. A group id already in ``consumed`` is refused.
    """
    allowed = _checkpoint_allowlist(policy_checkpoints)
    if (
        type(expected_run_id) is not str
        or keyring.run_id != expected_run_id
        or any(header.run_id != expected_run_id for header in headers)
        or any(record.run_id != expected_run_id for record in records)
    ):
        raise RewardRecordError("reward record run id does not match")
    if any(record.policy_checkpoint not in allowed for record in records):
        raise RewardRecordError("reward record checkpoint is not allowed")
    header_by_id: dict[str, GroupHeader] = {}
    for header in headers:
        verify(header, keyring)
        if header.group_id in header_by_id:
            raise RewardRecordError("reward record log repeats a group header")
        header_by_id[header.group_id] = header
    members: dict[str, list[RewardRowRecord]] = {group_id: [] for group_id in header_by_id}
    order = list(header_by_id)
    for record in records:
        verify(record, keyring)
        if record.group_id not in members:
            members[record.group_id] = []
            order.append(record.group_id)
        members[record.group_id].append(record)
    for group_id in order:
        if consumed.disposition(group_id) is not None:
            raise RewardRecordError("reward group was already consumed")
    record_ids: dict[str, int] = {}
    for record in records:
        record_ids[record.record_id] = record_ids.get(record.record_id, 0) + 1
    quarantined_groups, quarantined_rows = _quarantine_index(queue)
    rows: list[dict[str, object]] = []
    drops: list[tuple[str, str]] = []
    for group_id in order:
        header = header_by_id.get(group_id)
        group_rows = members.get(group_id, [])
        reason = _group_structure(
            header,
            group_rows,
            record_ids,
            quarantined_groups,
            quarantined_rows,
        )
        checkpoint = group_rows[0].policy_checkpoint if group_rows else ""
        task_digest = header.task_digest_full if header is not None else ""
        if reason is None and header is not None:
            reason, built = _grade_group(header, group_rows, keyring, queue, rates)
        else:
            built = []
        if reason is None:
            consumed.claim(
                group_id,
                "used",
                task_digest_full=task_digest,
                policy_checkpoint=checkpoint,
            )
            rows.extend(built)
        else:
            _hold_drop(queue, group_rows, reason)
            if reason == "stale_pin":
                for _record in group_rows:
                    rates.observe("reward-records", ungraded=True)
            consumed.claim(
                group_id,
                f"dropped:{reason}",
                task_digest_full=task_digest,
                policy_checkpoint=checkpoint,
            )
            drops.append((group_id, reason))
    return RecordBatch(rows=tuple(rows), drops=tuple(drops))


def _checkpoint_allowlist(value: str | tuple[str, ...] | list[str]) -> frozenset[str]:
    if type(value) is str:
        items: tuple[object, ...] = (value,)
    elif isinstance(value, (list, tuple)):
        items = tuple(value)
    else:
        raise RewardRecordError("reward record checkpoint is not allowed")
    allowed: set[str] = set()
    for item in items:
        if type(item) is not str or _DIGEST.fullmatch(item) is None:
            raise RewardRecordError("reward record checkpoint is not allowed")
        allowed.add(item)
    if not allowed:
        raise RewardRecordError("reward record checkpoint is not allowed")
    return frozenset(allowed)


def _quarantine_index(queue: QuarantineQueue) -> tuple[set[str], set[str]]:
    groups: set[str] = set()
    rows: set[str] = set()
    for held in queue.holds():
        if held.group_id:
            groups.add(held.group_id)
        if held.row_record_id:
            rows.add(held.row_record_id)
    return groups, rows


def _group_structure(
    header: GroupHeader | None,
    rows: list[RewardRowRecord],
    record_ids: Mapping[str, int],
    quarantined_groups: set[str],
    quarantined_rows: set[str],
) -> str | None:
    group_id = header.group_id if header is not None else (rows[0].group_id if rows else "")
    if group_id in quarantined_groups or any(row.record_id in quarantined_rows for row in rows):
        return "quarantined"
    if header is None:
        return "incomplete"
    if any(row.log_index < header.log_index or row.log_index < 0 or header.log_index < 0 for row in rows):
        return "header_after_members"
    if any(record_ids.get(row.record_id, 0) > 1 for row in rows):
        return "duplicate"
    indexes = [row.member_index for row in rows]
    if len(indexes) != len(set(indexes)):
        return "duplicate"
    if len(rows) != header.group_size or set(indexes) != set(range(header.group_size)):
        return "incomplete"
    for row in rows:
        if row.group_size != header.group_size or row.run_id != header.run_id:
            return "incomplete"
        if row.task_digest_full != header.task_digest_full:
            return "binding"
    return None


def _grade_group(
    header: GroupHeader,
    rows: list[RewardRowRecord],
    keyring: RewardKeyring,
    queue: QuarantineQueue,
    rates: UngradedRateTracker,
) -> tuple[str | None, list[dict[str, object]]]:
    ordered = sorted(rows, key=lambda row: row.member_index)
    built: list[dict[str, object]] = []
    for record in ordered:
        check = regrade_record(record, keyring, queue=queue, rates=rates)
        if check.reason == "stale_pin":
            return "stale_pin", []
        if check.reason in {"binding", "outcome", "shadow", "mac"}:
            return check.reason or "binding", []
        grade = check.grade
        if isinstance(grade, Ungraded):
            if grade.reason in QUARANTINE_REASONS or grade.quarantined:
                return "quarantined", []
            return "ungraded", []
        if not isinstance(grade, (RewardableSignalReceipt, SourceAttributedFailure)):
            return "ungraded", []
        try:
            from faustcoder.signal_suite import require_task_rewardable

            require_task_rewardable(record.task)
        except (TypeError, ValueError) as exc:
            if type(exc).__name__ not in {"TypeError", "ValueError", "SignalHarnessError"}:
                raise
            return "ungraded", []
        except Exception as exc:
            if type(exc).__name__ != "SignalHarnessError":
                raise
            return "ungraded", []
        if isinstance(grade, RewardableSignalReceipt):
            reward = 1.0 if grade.passed else 0.0
        else:
            reward = 0.0
        built.append(
            {
                "group_id": record.group_id,
                "member_index": record.member_index,
                "provenance": grade,
                "record_id": record.record_id,
                "reward": reward,
                "task": record.task,
            }
        )
    if header.group_id != ordered[0].group_id:
        return "incomplete", []
    return None, built


def _hold_drop(queue: QuarantineQueue, rows: list[RewardRowRecord], reason: str) -> None:
    """Remember a drop that ``grade_receipt`` did not already hold."""
    if reason not in {"stale_pin", "binding", "outcome"}:
        return
    for record in rows:
        payload = record.envelope.get("payload")
        digest = ""
        if isinstance(payload, dict):
            stored = payload.get("reproducible_digest")
            if isinstance(stored, str):
                digest = stored
        queue.hold(
            QuarantineRecord(
                policy="reward-records",
                reason=UngradedReason.HARNESS_DEFECT,
                reproducible_digest=digest,
                detail=reason,
                row_record_id=record.record_id,
                group_id=record.group_id,
            )
        )

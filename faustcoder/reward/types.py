"""Types the reward grader returns.

``RewardableSignalReceipt`` is minted only by ``grade_receipt``. Other
grades are ``Ungraded`` (no reward sample) or ``SourceAttributedFailure``
(ADR-0006 A1, the ``parse_error`` rung).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Callable
from weakref import WeakKeyDictionary


class UngradedReason(StrEnum):
    """Why a sample is not a reward.

    ``infra_fault``, ``harness_defect`` and ``unattributed`` are the
    ADR-0006 A2 quarantine reasons. ``unattributed`` covers an exit
    124 timeout, an exit 125 resource kill, an exit 126 ``internal``
    receipt, and a worker or harness crash, until auto-attribution or
    triage says otherwise. Exit 126 is ``internal``, not a timeout.
    """

    NOT_REWARD_GRADED = "not_reward_graded"
    PROFILE_NOT_ALLOWLISTED = "profile_not_allowlisted"
    DIGEST_MISMATCH = "digest_mismatch"
    SCHEMA_VERSION_UNSUPPORTED = "schema_version_unsupported"
    SCHEMA_INVALID = "schema_invalid"
    COMPARISON_NOT_FULL = "comparison_not_full"
    INFRA_FAULT = "infra_fault"
    HARNESS_DEFECT = "harness_defect"
    UNATTRIBUTED = "unattributed"


QUARANTINE_REASONS = frozenset(
    {
        UngradedReason.INFRA_FAULT,
        UngradedReason.HARNESS_DEFECT,
        UngradedReason.UNATTRIBUTED,
    }
)


@dataclass(frozen=True)
class Ungraded:
    """No reward sample. Quarantine reasons stay in the pending queue."""

    reason: UngradedReason
    detail: str = ""
    reproducible_digest: str = ""

    @property
    def quarantined(self) -> bool:
        return self.reason in QUARANTINE_REASONS


class RewardableSignalReceipt:
    """A signal receipt ``grade_receipt`` has accepted for reward.

    ``passed`` is the graded bit. Reward is 1 when it is true and 0
    when it is false. The constructor and ``_mint`` both refuse.
    ``grade_receipt`` registers the instance in a private mint table.
    ``apply_signal`` accepts the instance only while that table still
    matches its fields, so ``object.__new__`` plus ``object.__setattr__``
    cannot forge or flip one.
    """

    __slots__ = (
        "passed",
        "profile_name",
        "test_suite_digest",
        "reproducible_digest",
        "schema_version",
        "__weakref__",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "RewardableSignalReceipt can only be constructed by grade_receipt"
        )

    @classmethod
    def _mint(cls, *args: object, **kwargs: object) -> RewardableSignalReceipt:
        """Refuse a caller that spoofs the grader module name."""
        raise TypeError(
            "RewardableSignalReceipt can only be constructed by grade_receipt"
        )

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("RewardableSignalReceipt is immutable")

    def __repr__(self) -> str:
        return (
            "RewardableSignalReceipt("
            f"passed={self.passed!r}, profile_name={self.profile_name!r})"
        )

    def __eq__(self, other: object) -> bool:
        if type(other) is not RewardableSignalReceipt:
            return NotImplemented
        return self._snapshot() == other._snapshot()

    def __hash__(self) -> int:
        return hash(self._snapshot())

    def _snapshot(self) -> tuple[object, ...]:
        return (
            self.passed,
            self.profile_name,
            self.test_suite_digest,
            self.reproducible_digest,
            self.schema_version,
        )


def _mint_registry() -> tuple[
    Callable[[RewardableSignalReceipt], None],
    Callable[[object], bool],
]:
    """Close over the mint table so replacing the module global does not."""
    registry: WeakKeyDictionary[RewardableSignalReceipt, tuple[object, ...]] = (
        WeakKeyDictionary()
    )

    def register(receipt: RewardableSignalReceipt) -> None:
        registry[receipt] = receipt._snapshot()

    def is_minted(receipt: object) -> bool:
        if type(receipt) is not RewardableSignalReceipt:
            return False
        snapshot = registry.get(receipt)
        if snapshot is None:
            return False
        return snapshot == receipt._snapshot()

    return register, is_minted


_register_mint, is_minted = _mint_registry()


@dataclass(frozen=True)
class SourceAttributedFailure:
    """A failure ADR-0006 A1 grades at the ``parse_error`` rung.

    This is a reward of 0, not an ungraded sample. Auto-attribution
    and source tags (remote import, stack overflow) produce it.
    """

    rung: str = "parse_error"
    detail: str = ""

    def __post_init__(self) -> None:
        if self.rung != "parse_error":
            raise ValueError("A1 grades source-attributable failures at parse_error")


@dataclass(frozen=True)
class RerunOutcome:
    """One quiet-worker rerun of the same reproducible digest."""

    failed: bool
    exit_code: int
    diagnostic_class: str
    reproducible_digest: str
    environment_digest: str | None = None


@dataclass(frozen=True)
class FixtureOutcome:
    """A known-good fixture run beside that rerun."""

    passed: bool
    environment_digest: str | None = None


@dataclass(frozen=True)
class QuarantineRecord:
    """One retained ungraded row. Reward is absent; the row is not."""

    policy: str
    reason: UngradedReason
    reproducible_digest: str
    detail: str = ""
    reward: None = None
    record_id: str = ""
    held_at: str = ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class QuarantineQueue:
    """Pending A2 rows. Dropped from reward, retained and countable.

    ``path`` is an append-only JSONL file. ``hold`` and ``resolve``
    append a line and fsync it. Reopening the path replays the log.
    Resolved rows stay in the file and leave ``pending``.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._rows: list[QuarantineRecord] = []
        self._resolved: dict[str, str] = {}
        if self.path is not None and self.path.is_file():
            self._replay()

    def hold(self, record: QuarantineRecord) -> QuarantineRecord:
        if record.reason not in QUARANTINE_REASONS:
            raise ValueError("only A2 reasons enter the quarantine queue")
        if record.reward is not None:
            raise ValueError("a quarantined row has no reward")
        if not record.record_id or not record.held_at:
            record = replace(
                record,
                record_id=record.record_id or uuid.uuid4().hex,
                held_at=record.held_at or _utc_now(),
            )
        self._rows.append(record)
        self._append(
            {
                "op": "hold",
                "record_id": record.record_id,
                "policy": record.policy,
                "reason": record.reason.value,
                "reproducible_digest": record.reproducible_digest,
                "detail": record.detail,
                "held_at": record.held_at,
            }
        )
        return record

    def resolve(self, record_id: str, *, resolved_at: str | None = None) -> None:
        """Append a resolve line. The row leaves ``pending`` and stays on disk."""
        if not isinstance(record_id, str) or not record_id:
            raise KeyError(record_id)
        if record_id not in {row.record_id for row in self._rows}:
            raise KeyError(record_id)
        if record_id in self._resolved:
            return
        stamp = resolved_at or _utc_now()
        self._resolved[record_id] = stamp
        self._append({"op": "resolve", "record_id": record_id, "resolved_at": stamp})

    def pending(self, policy: str | None = None) -> tuple[QuarantineRecord, ...]:
        rows = [row for row in self._rows if row.record_id not in self._resolved]
        if policy is None:
            return tuple(rows)
        return tuple(row for row in rows if row.policy == policy)

    def count(self, policy: str | None = None) -> int:
        return len(self.pending(policy))

    def age_alarm(
        self,
        *,
        now: datetime | None = None,
        limit_seconds: int = 24 * 60 * 60,
    ) -> tuple[QuarantineRecord, ...]:
        """Return pending rows older than ``limit_seconds``.

        The default is 24 hours, a provisional age alarm. A resolved
        row does not alarm.
        """
        if limit_seconds < 0:
            raise ValueError("limit_seconds must be non-negative")
        moment = now or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        stale: list[QuarantineRecord] = []
        for row in self.pending():
            held = datetime.fromisoformat(row.held_at.replace("Z", "+00:00"))
            if held.tzinfo is None:
                held = held.replace(tzinfo=timezone.utc)
            if (moment - held).total_seconds() > limit_seconds:
                stale.append(row)
        return tuple(stale)

    def _append(self, row: dict[str, object]) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n"
        fd = os.open(self.path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    def _replay(self) -> None:
        if self.path is None:
            return
        text = self.path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                body = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"quarantine log line {line_number} is not JSON") from exc
            if not isinstance(body, dict):
                raise ValueError(f"quarantine log line {line_number} is not an object")
            op = body.get("op")
            if op == "hold":
                reason = UngradedReason(str(body["reason"]))
                self._rows.append(
                    QuarantineRecord(
                        policy=str(body["policy"]),
                        reason=reason,
                        reproducible_digest=str(body["reproducible_digest"]),
                        detail=str(body.get("detail", "")),
                        record_id=str(body["record_id"]),
                        held_at=str(body["held_at"]),
                    )
                )
            elif op == "resolve":
                self._resolved[str(body["record_id"])] = str(body["resolved_at"])
            else:
                raise ValueError(f"quarantine log line {line_number} has op {op!r}")


# ADR-0006 A7 provisional starting values. Danny may tune them after
# the first runs. They are not a silent change to the ladder.
UNGRADED_WINDOW = 500
UNGRADED_RATE_LIMIT = 0.01
UNGRADED_BASELINE_MULTIPLE = 2.0
# Early alarm when no baseline is configured: five ungraded samples,
# or a rate above 1% once one hundred samples are in, before the
# 500-sample window fills. The baseline floor stops a baseline of 0
# from firing on the first row.
UNGRADED_ABSOLUTE_FLOOR = 5
UNGRADED_EARLY_MIN_SAMPLES = 100
UNGRADED_BASELINE_MIN_SAMPLES = 5
UNGRADED_BASELINE_RATE_FLOOR = UNGRADED_RATE_LIMIT
# Provisional quarantine age. A pending row older than this alarms.
QUARANTINE_MAX_AGE_SECONDS = 24 * 60 * 60


class UngradedRateTracker:
    """Per-policy ungraded rate and the A7 alarm hook.

    Graded rewards and A1 ``parse_error`` outcomes count in the
    denominator. Ungraded A2 rows count, and so do ``schema_invalid``,
    ``digest_mismatch`` and ``comparison_not_full``. With no baseline
    the alarm also fires at five ungraded samples, or when the rate
    is above 1% once one hundred samples are in. A baseline uses
    ``max(2× baseline, 1%)`` and waits for five samples, so a baseline
    of 0 does not fire on the first row. After the rate recovers the
    alarm re-arms and can fire again.
    """

    def __init__(
        self,
        *,
        baseline: float | None = None,
        on_alarm: Any = None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        if baseline is not None and (baseline < 0 or baseline > 1):
            raise ValueError("baseline must lie in [0, 1]")
        self.baseline = baseline
        self.on_alarm = on_alarm
        self.on_change = on_change
        self._samples: dict[str, list[bool]] = {}
        self._alarmed: set[str] = set()

    def observe(self, policy: str, *, ungraded: bool) -> None:
        if not isinstance(policy, str) or not policy:
            raise ValueError("policy must be a non-empty string")
        self._samples.setdefault(policy, []).append(bool(ungraded))
        firing = self.alarm(policy)
        if firing and policy not in self._alarmed:
            self._alarmed.add(policy)
            hook = self.on_alarm
            if hook is not None:
                hook(policy, self.rate(policy))
        elif not firing and policy in self._alarmed:
            self._alarmed.discard(policy)
        if self.on_change is not None:
            self.on_change()

    def rate(self, policy: str) -> float:
        window = self._samples.get(policy, [])[-UNGRADED_WINDOW:]
        if not window:
            return 0.0
        return sum(window) / len(window)

    def alarm(self, policy: str) -> bool:
        rows = self._samples.get(policy, [])
        window = rows[-UNGRADED_WINDOW:]
        if not window:
            return False
        count = len(window)
        ungraded = sum(window)
        rate = ungraded / count
        if count >= UNGRADED_WINDOW and rate > UNGRADED_RATE_LIMIT:
            return True
        if self.baseline is None:
            if ungraded >= UNGRADED_ABSOLUTE_FLOOR:
                return True
            if count >= UNGRADED_EARLY_MIN_SAMPLES and rate > UNGRADED_RATE_LIMIT:
                return True
            return False
        floor = max(UNGRADED_BASELINE_MULTIPLE * self.baseline, UNGRADED_BASELINE_RATE_FLOOR)
        if count >= UNGRADED_BASELINE_MIN_SAMPLES and rate > floor:
            return True
        return False

    def export_state(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline,
            "samples": {policy: list(rows) for policy, rows in self._samples.items()},
            "alarmed": sorted(self._alarmed),
        }

    def load_state(self, payload: Mapping[str, Any]) -> None:
        samples = payload.get("samples")
        if not isinstance(samples, dict):
            raise ValueError("rates state is missing samples")
        restored: dict[str, list[bool]] = {}
        for policy, rows in samples.items():
            if not isinstance(policy, str) or not isinstance(rows, list):
                raise ValueError("rates state samples are malformed")
            restored[policy] = [bool(item) for item in rows]
        alarmed = payload.get("alarmed", [])
        if not isinstance(alarmed, list):
            raise ValueError("rates state alarmed is malformed")
        self._samples = restored
        self._alarmed = {str(item) for item in alarmed}

    @property
    def alarmed_policies(self) -> frozenset[str]:
        return frozenset(self._alarmed)

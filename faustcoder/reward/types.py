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
class UngradedReason(StrEnum):
    """Why a sample is not a reward.

    ``infra_fault``, ``harness_defect`` and ``unattributed`` are the
    ADR-0006 A2 quarantine reasons. ``unattributed`` covers an exit
    124 timeout, an exit 125 resource kill, an exit 126 ``internal``
    receipt, and a worker or harness crash, until triage attributes
    it. Exit 126 is ``internal``, not a timeout. A rerun plus a
    known-good fixture is not attribution.
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
    ``grade_receipt`` seals the instance in a mint table that is
    private to that function. ``apply_signal`` accepts the instance
    only while the seal matches this object's identity and fields, so
    a lookalike with the same fields is not a reward.

    ``task_digest`` is the canonical digest of the task id and effect
    this receipt was minted for. It is ``None`` when grading did not
    bind a task. Training builders refuse an unbound receipt and a
    receipt whose digest does not match the row's task.

    ``unrewardable`` is true when that task is not a reward target.
    ``apply_signal`` refuses the receipt. A linear mint leaves it false.
    """

    __slots__ = (
        "passed",
        "profile_name",
        "test_suite_digest",
        "reproducible_digest",
        "schema_version",
        "task_digest",
        "unrewardable",
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
        # A lookalike from ``object.__new__`` may leave a slot unset.
        # Hashing that object must not raise; the mint seal still rejects it.
        return tuple(
            getattr(self, name, None)
            for name in (
                "passed",
                "profile_name",
                "test_suite_digest",
                "reproducible_digest",
                "schema_version",
                "task_digest",
                "unrewardable",
            )
        )


@dataclass(frozen=True)
class SourceAttributedFailure:
    """A failure ADR-0006 A1 grades at the ``parse_error`` rung.

    This is a reward of 0, not an ungraded sample. Triage that
    attributes a quarantined row to the source produces it, and so
    do the source-class rules that do not wait: a remote import, a
    source over 1 MiB, and a line-start Faust ``ERROR``.
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


class TriageAttribution(StrEnum):
    """Who a quarantined timeout or crash is blamed on.

    ``source`` re-grades the row at the A1 ``parse_error`` rung.
    ``harness`` and ``infrastructure`` drop the row. It is never scored.
    """

    SOURCE = "source"
    HARNESS = "harness"
    INFRASTRUCTURE = "infrastructure"


@dataclass(frozen=True)
class TriageDecision:
    """A recorded triage decision: who, why, and evidence.

    ``triaged_by`` is who. ``attribution`` is why. ``evidence`` is the
    note. A bare string is not a decision. A2-T is not implemented, so
    ``grade_receipt`` does not turn ``source`` into a score. ``harness``
    or ``infrastructure`` can only drop a remote-import or source-size
    score.
    """

    attribution: TriageAttribution
    triaged_by: str
    evidence: str


@dataclass(frozen=True)
class TriageResolution:
    """The attribution recorded when a quarantine row is resolved."""

    record_id: str
    attribution: TriageAttribution
    triaged_by: str
    triaged_at: str
    grade: SourceAttributedFailure | Ungraded
    evidence: str = ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class QuarantineQueue:
    """Pending A2 rows. Dropped from reward, retained and countable.

    ``path`` is an append-only JSONL file. ``hold`` and ``resolve``
    append a line and fsync it. Reopening the path replays the log.
    ``resolve`` requires an attribution, who triaged the row, and when.
    A row nobody has resolved stays in ``pending`` and is not a score.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._rows: list[QuarantineRecord] = []
        self._resolutions: dict[str, TriageResolution] = {}
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

    def resolve(
        self,
        record_id: str,
        *,
        attribution: TriageAttribution,
        triaged_by: str,
        triaged_at: str | None = None,
        evidence: str = "",
    ) -> SourceAttributedFailure | Ungraded:
        """Re-grade one pending row and append the triage outcome.

        ``attribution`` is required. ``source`` returns the A1
        ``parse_error`` rung and requires non-empty ``evidence``.
        ``harness`` and ``infrastructure`` return an ungraded row that
        is dropped and never scored. ``triaged_by`` and ``triaged_at``
        are stored with that outcome. ``triaged_at`` is a timezone-aware
        ISO-8601 timestamp, is not in the future, and is not earlier
        than the row's ``held_at``. Calling this without an attribution
        raises ``TypeError`` and leaves the row pending.
        """
        if not isinstance(record_id, str) or not record_id:
            raise KeyError(record_id)
        row = next((item for item in self._rows if item.record_id == record_id), None)
        if row is None:
            raise KeyError(record_id)
        existing = self._resolutions.get(record_id)
        if existing is not None:
            return existing.grade
        kind = _attribution(attribution)
        if not isinstance(triaged_by, str) or not triaged_by.strip():
            raise ValueError("triage requires the name of who resolved the row")
        stamp = _require_triaged_at(triaged_at or _utc_now(), held_at=row.held_at)
        note = _require_evidence(kind, evidence)
        grade = _triage_grade(row, kind)
        outcome = _outcome_for(kind)
        resolution = TriageResolution(
            record_id=record_id,
            attribution=kind,
            triaged_by=triaged_by.strip(),
            triaged_at=stamp,
            grade=grade,
            evidence=note,
        )
        self._resolutions[record_id] = resolution
        self._append(
            {
                "op": "resolve",
                "record_id": record_id,
                "attribution": kind.value,
                "triaged_by": resolution.triaged_by,
                "triaged_at": stamp,
                "outcome": outcome,
                "evidence": note,
            }
        )
        return grade

    def resolution(self, record_id: str) -> TriageResolution | None:
        """Return the triage record for ``record_id``, if it was resolved."""
        return self._resolutions.get(record_id)

    def pending(self, policy: str | None = None) -> tuple[QuarantineRecord, ...]:
        rows = [row for row in self._rows if row.record_id not in self._resolutions]
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
                record_id = str(body["record_id"])
                if record_id in self._resolutions:
                    raise ValueError(
                        f"quarantine log line {line_number} resolves {record_id} a second time"
                    )
                row = next((item for item in self._rows if item.record_id == record_id), None)
                if row is None:
                    raise ValueError(
                        f"quarantine log line {line_number} resolves an unknown row"
                    )
                kind = _attribution(body.get("attribution"))
                triaged_by = body.get("triaged_by")
                if not isinstance(triaged_by, str) or not triaged_by.strip():
                    raise ValueError(
                        f"quarantine log line {line_number} has no triage attribution"
                    )
                try:
                    triaged_at = _require_triaged_at(
                        body.get("triaged_at"), held_at=row.held_at
                    )
                    evidence = _require_evidence(kind, body.get("evidence", ""))
                except ValueError as exc:
                    raise ValueError(
                        f"quarantine log line {line_number} {exc}"
                    ) from exc
                expected = _outcome_for(kind)
                if body.get("outcome") != expected:
                    raise ValueError(
                        f"quarantine log line {line_number} outcome does not match {kind.value}"
                    )
                self._resolutions[record_id] = TriageResolution(
                    record_id=record_id,
                    attribution=kind,
                    triaged_by=triaged_by.strip(),
                    triaged_at=triaged_at,
                    grade=_triage_grade(row, kind),
                    evidence=evidence,
                )
            else:
                raise ValueError(f"quarantine log line {line_number} has op {op!r}")


def _attribution(value: object) -> TriageAttribution:
    """Return a triage attribution, or refuse a missing or unknown one."""
    if isinstance(value, TriageAttribution):
        return value
    try:
        return TriageAttribution(value)
    except ValueError as exc:
        raise ValueError(
            "attribution must be source, harness, or infrastructure"
        ) from exc


def _outcome_for(attribution: TriageAttribution) -> str:
    """Return the on-disk outcome that ``attribution`` must record."""
    if attribution is TriageAttribution.SOURCE:
        return "parse_error"
    return "drop"


def _require_evidence(attribution: TriageAttribution, evidence: object) -> str:
    """Source triage needs a free-text note or a receipt reference."""
    if not isinstance(evidence, str):
        raise ValueError("evidence must be a string")
    note = evidence.strip()
    if attribution is TriageAttribution.SOURCE and not note:
        raise ValueError("source triage requires evidence")
    return note


def _require_triaged_at(value: object, *, held_at: str | None = None) -> str:
    """Return a timezone-aware ISO-8601 timestamp that is not in the future.

    When ``held_at`` is set, the stamp must not be earlier than the
    quarantine hold.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("triaged_at must be a timezone-aware ISO-8601 timestamp")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("triaged_at must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise ValueError("triaged_at must be a timezone-aware ISO-8601 timestamp")
    if parsed > datetime.now(timezone.utc):
        raise ValueError("triaged_at must not be in the future")
    if held_at is not None:
        if not isinstance(held_at, str) or not held_at.strip():
            raise ValueError("triaged_at must not be earlier than the quarantine hold")
        try:
            held = datetime.fromisoformat(held_at.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                "triaged_at must not be earlier than the quarantine hold"
            ) from exc
        if held.tzinfo is None or held.tzinfo.utcoffset(held) is None:
            raise ValueError("triaged_at must not be earlier than the quarantine hold")
        if parsed < held:
            raise ValueError("triaged_at must not be earlier than the quarantine hold")
    return text


def _triage_grade(
    row: QuarantineRecord, attribution: TriageAttribution
) -> SourceAttributedFailure | Ungraded:
    """Re-grade ``row``. Source is parse_error. The other two are dropped."""
    if attribution is TriageAttribution.SOURCE:
        return SourceAttributedFailure(
            detail="triage attributed the quarantined failure to the source"
        )
    if attribution is TriageAttribution.HARNESS:
        return Ungraded(
            UngradedReason.HARNESS_DEFECT,
            "triage dropped the row; a harness defect is not scored",
            row.reproducible_digest,
        )
    return Ungraded(
        UngradedReason.INFRA_FAULT,
        "triage dropped the row; an infrastructure fault is not scored",
        row.reproducible_digest,
    )


# ADR-0006 A7 provisional starting values. Danny may tune them after
# the first runs. They are not a silent change to the ladder.
# Alarm only when the rate is above 1% over a full 500-sample window,
# or above 2× the known-good baseline, whichever comes first.
UNGRADED_WINDOW = 500
UNGRADED_RATE_LIMIT = 0.01
UNGRADED_BASELINE_MULTIPLE = 2.0
# Provisional quarantine age. A pending row older than this alarms.
QUARANTINE_MAX_AGE_SECONDS = 24 * 60 * 60


def _restore_baseline(value: object) -> float | int | None:
    """Return a baseline stored by ``export_state``, or raise."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("baseline must lie in [0, 1]")
    if value < 0 or value > 1:
        raise ValueError("baseline must lie in [0, 1]")
    return value


class UngradedRateTracker:
    """Per-policy ungraded rate and the A7 alarm hook.

    Graded rewards and A1 ``parse_error`` outcomes count in the
    denominator. Ungraded A2 rows count, and so do ``schema_invalid``,
    ``digest_mismatch`` and ``comparison_not_full``. The alarm fires
    when the rate is above 1% over a full 500-sample window, or above
    2× ``baseline`` when a baseline is set, whichever comes first.
    Five ungraded samples in 500 do not alarm. Six do. After the rate
    recovers the alarm re-arms and can fire again.
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
        rate = sum(window) / count
        if count >= UNGRADED_WINDOW and rate > UNGRADED_RATE_LIMIT:
            return True
        if self.baseline is not None and rate > UNGRADED_BASELINE_MULTIPLE * self.baseline:
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
        baseline = self.baseline
        if "baseline" in payload:
            baseline = _restore_baseline(payload.get("baseline"))
        self._samples = restored
        self._alarmed = {str(item) for item in alarmed}
        self.baseline = baseline

    @property
    def alarmed_policies(self) -> frozenset[str]:
        return frozenset(self._alarmed)

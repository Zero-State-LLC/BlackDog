"""Types the reward grader returns.

``RewardableSignalReceipt`` is minted only by ``grade_receipt``. Other
grades are ``Ungraded`` (no reward sample) or ``SourceAttributedFailure``
(ADR-0006 A1, the ``parse_error`` rung).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


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
    when it is false. Callers cannot build this with the constructor.
    """

    __slots__ = (
        "passed",
        "profile_name",
        "test_suite_digest",
        "reproducible_digest",
        "schema_version",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "RewardableSignalReceipt can only be constructed by grade_receipt"
        )

    @classmethod
    def _mint(
        cls,
        *,
        passed: bool,
        profile_name: str,
        test_suite_digest: str,
        reproducible_digest: str,
        schema_version: str,
    ) -> RewardableSignalReceipt:
        caller = sys._getframe(1)
        if caller.f_globals.get("__name__") != "faustcoder.reward.grader":
            raise TypeError(
                "RewardableSignalReceipt can only be constructed by grade_receipt"
            )
        self = object.__new__(cls)
        object.__setattr__(self, "passed", passed)
        object.__setattr__(self, "profile_name", profile_name)
        object.__setattr__(self, "test_suite_digest", test_suite_digest)
        object.__setattr__(self, "reproducible_digest", reproducible_digest)
        object.__setattr__(self, "schema_version", schema_version)
        return self

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
        return all(
            getattr(self, name) == getattr(other, name) for name in self.__slots__
        )

    def __hash__(self) -> int:
        return hash(tuple(getattr(self, name) for name in self.__slots__))


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


class QuarantineQueue:
    """Pending A2 rows. Dropped from reward, retained and countable."""

    def __init__(self) -> None:
        self._rows: list[QuarantineRecord] = []

    def hold(self, record: QuarantineRecord) -> None:
        if record.reason not in QUARANTINE_REASONS:
            raise ValueError("only A2 reasons enter the quarantine queue")
        if record.reward is not None:
            raise ValueError("a quarantined row has no reward")
        self._rows.append(record)

    def pending(self, policy: str | None = None) -> tuple[QuarantineRecord, ...]:
        if policy is None:
            return tuple(self._rows)
        return tuple(row for row in self._rows if row.policy == policy)

    def count(self, policy: str | None = None) -> int:
        return len(self.pending(policy))


# ADR-0006 A7 provisional starting values. Danny may tune them after
# the first runs. They are not a silent change to the ladder.
UNGRADED_WINDOW = 500
UNGRADED_RATE_LIMIT = 0.01
UNGRADED_BASELINE_MULTIPLE = 2.0


class UngradedRateTracker:
    """Per-policy ungraded rate and the A7 alarm hook.

    A sample counts as ungraded only for an A2 quarantine reason.
    Graded rewards and A1 ``parse_error`` outcomes count in the
    denominator. The alarm fires when the rate over the last 500
    samples is above 1%, or above twice the known-good baseline,
    whichever comes first. The hook runs once per policy.
    """

    def __init__(
        self,
        *,
        baseline: float | None = None,
        on_alarm: Any = None,
    ) -> None:
        if baseline is not None and (baseline < 0 or baseline > 1):
            raise ValueError("baseline must lie in [0, 1]")
        self.baseline = baseline
        self.on_alarm = on_alarm
        self._samples: dict[str, list[bool]] = {}
        self._alarmed: set[str] = set()

    def observe(self, policy: str, *, ungraded: bool) -> None:
        if not isinstance(policy, str) or not policy:
            raise ValueError("policy must be a non-empty string")
        self._samples.setdefault(policy, []).append(bool(ungraded))
        if policy not in self._alarmed and self.alarm(policy):
            self._alarmed.add(policy)
            hook = self.on_alarm
            if hook is not None:
                hook(policy, self.rate(policy))

    def rate(self, policy: str) -> float:
        window = self._samples.get(policy, [])[-UNGRADED_WINDOW:]
        if not window:
            return 0.0
        return sum(window) / len(window)

    def alarm(self, policy: str) -> bool:
        rows = self._samples.get(policy, [])
        window = rows[-UNGRADED_WINDOW:]
        if len(window) >= UNGRADED_WINDOW and (sum(window) / len(window)) > UNGRADED_RATE_LIMIT:
            return True
        if self.baseline is not None and rows:
            if self.rate(policy) > UNGRADED_BASELINE_MULTIPLE * self.baseline:
                return True
        return False

    @property
    def alarmed_policies(self) -> frozenset[str]:
        return frozenset(self._alarmed)

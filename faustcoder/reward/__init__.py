"""Reward grading (spec §23, ADR-0006).

ADR-0006 is in force here. ``grade_receipt`` is the only way to mint
a ``RewardableSignalReceipt``. Ungraded samples are dropped from
reward and A2 rows stay in the quarantine queue.
"""

from faustcoder.reward.grader import (
    grade_compiler_exclusion,
    grade_receipt,
    dataset_reward_row,
    require_rewardable_provenance,
    reward_value,
    rl_batch,
    RewardProvenanceError,
)
from faustcoder.reward.profiles import REWARD_PROFILES, reward_profiles
from faustcoder.reward.types import (
    UNGRADED_BASELINE_MULTIPLE,
    UNGRADED_RATE_LIMIT,
    UNGRADED_WINDOW,
    FixtureOutcome,
    QuarantineQueue,
    QuarantineRecord,
    RerunOutcome,
    RewardableSignalReceipt,
    SourceAttributedFailure,
    Ungraded,
    UngradedRateTracker,
    UngradedReason,
)

__all__ = [
    "REWARD_PROFILES",
    "UNGRADED_BASELINE_MULTIPLE",
    "UNGRADED_RATE_LIMIT",
    "UNGRADED_WINDOW",
    "FixtureOutcome",
    "QuarantineQueue",
    "QuarantineRecord",
    "RerunOutcome",
    "RewardProvenanceError",
    "RewardableSignalReceipt",
    "SourceAttributedFailure",
    "Ungraded",
    "UngradedRateTracker",
    "UngradedReason",
    "dataset_reward_row",
    "grade_compiler_exclusion",
    "grade_receipt",
    "require_rewardable_provenance",
    "reward_profiles",
    "reward_value",
    "rl_batch",
]

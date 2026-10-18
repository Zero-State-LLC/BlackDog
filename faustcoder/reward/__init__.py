"""Reward grading (spec §23, ADR-0006).

ADR-0006 is in force here. ``grade_receipt`` is the only way to mint
a ``RewardableSignalReceipt``. Ungraded samples are dropped from
reward and A2 rows stay in the quarantine queue.
"""

from faustcoder.reward.grader import (
    grade_compiler_exclusion,
    grade_receipt,
    dataset_reward_row,
    is_minted,
    require_rewardable_provenance,
    reward_value,
    rl_batch,
    RewardOutcomeHeld,
    RewardProvenanceError,
    RewardUseRefused,
)
from faustcoder.reward.ledger import RewardLedger, ledger_for_store
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
    TriageAttribution,
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
    "RewardLedger",
    "RewardOutcomeHeld",
    "RewardProvenanceError",
    "RewardUseRefused",
    "RewardableSignalReceipt",
    "SourceAttributedFailure",
    "TriageAttribution",
    "Ungraded",
    "UngradedRateTracker",
    "UngradedReason",
    "dataset_reward_row",
    "grade_compiler_exclusion",
    "grade_receipt",
    "is_minted",
    "ledger_for_store",
    "require_rewardable_provenance",
    "reward_profiles",
    "reward_value",
    "rl_batch",
]

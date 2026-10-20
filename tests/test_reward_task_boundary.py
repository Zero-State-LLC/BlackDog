"""Additional regression checks for task-bound reward consumption.

These tests protect the existing grader contract without modifying its API.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from faustcoder.reward import (
    RewardProvenanceError,
    RewardableSignalReceipt,
    grade_receipt,
    reward_value,
)
from tests.support import allowlisted_reward_envelope


def _task() -> dict:
    path = Path(__file__).parent / "fixtures/valid/task-spec.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_unbound_low_level_receipt_cannot_be_consumed() -> None:
    graded = grade_receipt(allowlisted_reward_envelope(passed=True))
    assert isinstance(graded, RewardableSignalReceipt)
    with pytest.raises(RewardProvenanceError):
        reward_value(graded, _task())


def test_task_mutation_after_mint_refuses_reward() -> None:
    task = _task()
    graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    changed = copy.deepcopy(task)
    changed["prompt"] = str(changed.get("prompt", "")) + " modified"
    with pytest.raises(RewardProvenanceError):
        reward_value(graded, changed)


def test_task_effect_change_after_mint_refuses_reward() -> None:
    task = _task()
    graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    changed = copy.deepcopy(task)
    changed["effect"] = "nonlinear"
    with pytest.raises(RewardProvenanceError):
        reward_value(graded, changed)


def test_correct_task_can_consume_bound_receipt() -> None:
    task = _task()
    graded = grade_receipt(allowlisted_reward_envelope(passed=True), task=task)
    assert reward_value(graded, task) == 1.0


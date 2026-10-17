"""Candidate-program state machine (spec §7.2).

The transition table is the contract. ``next_state`` only resolves a
legal edge. T04 persists the ``signal_passed`` and ``signal_failed``
effects (a DSPTestReceipt). The other effects stay in the table so
illegal edges are rejected; later tasks write their artifacts.

``REPAIRING`` and ``repair_produced`` are INFERRED in spec §7.2.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CandidateState(StrEnum):
    """States of one candidate program (spec §7.2)."""

    DRAFT = "DRAFT"
    COMPILE_CHECKED = "COMPILE_CHECKED"
    SIGNAL_CHECKED = "SIGNAL_CHECKED"
    TARGET_CHECKED = "TARGET_CHECKED"
    REVIEWED = "REVIEWED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    REPAIRING = "REPAIRING"


class CandidateEvent(StrEnum):
    """Events of the candidate machine (spec §7.2)."""

    COMPILE_PASSED = "compile_passed"
    COMPILE_FAILED = "compile_failed"
    REPAIR_PRODUCED = "repair_produced"
    ABSTAIN = "abstain"
    SIGNAL_PASSED = "signal_passed"
    SIGNAL_FAILED = "signal_failed"
    LANES_PASSED = "lanes_passed"
    LANE_FAILED = "lane_failed"
    REVIEW_RECORDED = "review_recorded"
    ACCEPT = "accept"
    REJECT = "reject"


class IllegalTransition(Exception):
    """``event`` is not an edge out of ``state``."""

    def __init__(self, state: CandidateState, event: CandidateEvent) -> None:
        self.state = state
        self.event = event
        super().__init__(f"no {event.value} edge out of {state.value}")


class GuardRejected(Exception):
    """The edge exists and its guard refused the transition."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = list(reasons)
        detail = "; ".join(self.reasons) if self.reasons else "guard rejected"
        super().__init__(detail)


@dataclass(frozen=True)
class Transition:
    """One row of the spec §7.2 table."""

    source: CandidateState
    event: CandidateEvent
    target: CandidateState
    guard: str
    effect: str
    inferred: bool = False

    @property
    def event_label(self) -> str:
        if self.inferred:
            return f"{self.event.value} (INFERRED)"
        return self.event.value


INITIAL_STATE = CandidateState.DRAFT
FINAL_STATES = frozenset({CandidateState.ACCEPTED, CandidateState.REJECTED})
INFERRED_STATES = frozenset({CandidateState.REPAIRING})

TRANSITIONS: tuple[Transition, ...] = (
    Transition(
        CandidateState.DRAFT,
        CandidateEvent.COMPILE_PASSED,
        CandidateState.COMPILE_CHECKED,
        "Sandboxed pinned compiler exit code 0 (R-005, R-013)",
        "Write CompilerReceipt",
    ),
    Transition(
        CandidateState.DRAFT,
        CandidateEvent.COMPILE_FAILED,
        CandidateState.REPAIRING,
        "`repair_attempts < max_repair_attempts`",
        "Write CompilerReceipt with diagnostics; increment `repair_attempts`",
    ),
    Transition(
        CandidateState.DRAFT,
        CandidateEvent.COMPILE_FAILED,
        CandidateState.REJECTED,
        "`repair_attempts >= max_repair_attempts`",
        "Write CompilerReceipt; record abstention disposition (R-012)",
    ),
    Transition(
        CandidateState.DRAFT,
        CandidateEvent.ABSTAIN,
        CandidateState.REJECTED,
        "Model or policy declines (R-012)",
        "Record abstention disposition",
    ),
    Transition(
        CandidateState.REPAIRING,
        CandidateEvent.REPAIR_PRODUCED,
        CandidateState.DRAFT,
        "Repair output is a new CandidateProgram whose parent is the failed one (INFERRED)",
        "New node; diff recorded for J-02 (INFERRED)",
        inferred=True,
    ),
    Transition(
        CandidateState.REPAIRING,
        CandidateEvent.ABSTAIN,
        CandidateState.REJECTED,
        "Repair declined or produced no change (INFERRED)",
        "Record abstention disposition",
    ),
    Transition(
        CandidateState.COMPILE_CHECKED,
        CandidateEvent.SIGNAL_PASSED,
        CandidateState.SIGNAL_CHECKED,
        (
            "All signal tests in the TaskSpec `test_profile` pass: "
            "reference comparison, finite output, channel count, silence, "
            "DC and clipping (R-006, amended 0.3.0)"
        ),
        "Write DSPTestReceipt",
    ),
    Transition(
        CandidateState.COMPILE_CHECKED,
        CandidateEvent.SIGNAL_FAILED,
        CandidateState.REJECTED,
        "Any required signal test fails",
        "Write DSPTestReceipt with failing metrics",
    ),
    Transition(
        CandidateState.SIGNAL_CHECKED,
        CandidateEvent.LANES_PASSED,
        CandidateState.TARGET_CHECKED,
        (
            "Every lane the TaskSpec `target` names passes "
            "(R-019, R-021 to R-024); none named for host-only tasks (ADD 0.3.0)"
        ),
        "Write one TargetReceipt per lane",
    ),
    Transition(
        CandidateState.SIGNAL_CHECKED,
        CandidateEvent.LANE_FAILED,
        CandidateState.REJECTED,
        "Any named lane fails (ADD 0.3.0)",
        "Write the failing TargetReceipt",
    ),
    Transition(
        CandidateState.TARGET_CHECKED,
        CandidateEvent.REVIEW_RECORDED,
        CandidateState.REVIEWED,
        "Reviewer is independent of the generating model (R-011)",
        "Record review against gate results",
    ),
    Transition(
        CandidateState.REVIEWED,
        CandidateEvent.ACCEPT,
        CandidateState.ACCEPTED,
        (
            "All gates pass; for J-03, semantic and signal comparison "
            "against the baseline shows no regression and equivalence is evidenced"
        ),
        "Write DecisionRecord (disposition = accepted)",
    ),
    Transition(
        CandidateState.REVIEWED,
        CandidateEvent.REJECT,
        CandidateState.REJECTED,
        "Any gate fails, or J-03 equivalence is unproven",
        "Write DecisionRecord (disposition = rejected, rationale)",
    ),
)

# Spec §7.2 illegal transitions that are not rows.
ILLEGAL_EDGES: tuple[tuple[CandidateState, CandidateEvent, str], ...] = (
    (
        CandidateState.DRAFT,
        CandidateEvent.SIGNAL_PASSED,
        "DRAFT -> SIGNAL_CHECKED: signal tests need a successful compile",
    ),
    (
        CandidateState.DRAFT,
        CandidateEvent.REVIEW_RECORDED,
        "DRAFT -> REVIEWED: signal tests and review need a successful compile",
    ),
    (
        CandidateState.DRAFT,
        CandidateEvent.ACCEPT,
        "DRAFT -> ACCEPTED: signal tests and review need a successful compile",
    ),
    (
        CandidateState.COMPILE_CHECKED,
        CandidateEvent.ACCEPT,
        "COMPILE_CHECKED -> ACCEPTED: compilation alone is never acceptance",
    ),
    (
        CandidateState.SIGNAL_CHECKED,
        CandidateEvent.REVIEW_RECORDED,
        "SIGNAL_CHECKED -> REVIEWED: target lanes come first, even when the set is empty",
    ),
    (
        CandidateState.SIGNAL_CHECKED,
        CandidateEvent.ACCEPT,
        "SIGNAL_CHECKED -> ACCEPTED without REVIEWED",
    ),
    (
        CandidateState.TARGET_CHECKED,
        CandidateEvent.ACCEPT,
        "TARGET_CHECKED -> ACCEPTED without REVIEWED",
    ),
    (
        CandidateState.ACCEPTED,
        CandidateEvent.REJECT,
        "No transition out of ACCEPTED",
    ),
    (
        CandidateState.REJECTED,
        CandidateEvent.COMPILE_PASSED,
        "No transition out of REJECTED; a new attempt is a new node",
    ),
)


def transition_row(
    state: CandidateState,
    event: CandidateEvent,
    *,
    repair_attempts: int = 0,
    max_repair_attempts: int = 1,
) -> Transition | None:
    """Return the row for ``state`` and ``event``, if one exists.

    ``compile_failed`` has two rows. The attempt bound selects one.
    ``repair_attempts`` and ``max_repair_attempts`` are ignored for
    every other event.
    """
    matches = [row for row in TRANSITIONS if row.source is state and row.event is event]
    if not matches:
        return None
    if state is CandidateState.DRAFT and event is CandidateEvent.COMPILE_FAILED:
        if repair_attempts < 0 or max_repair_attempts < 0:
            raise ValueError("repair attempt counts must be non-negative")
        repairing = repair_attempts < max_repair_attempts
        target = CandidateState.REPAIRING if repairing else CandidateState.REJECTED
        chosen = [row for row in matches if row.target is target]
        if len(chosen) != 1:
            raise IllegalTransition(state, event)
        return chosen[0]
    if len(matches) != 1:
        raise IllegalTransition(state, event)
    return matches[0]


def next_state(
    state: CandidateState,
    event: CandidateEvent,
    *,
    guard_passed: bool,
    repair_attempts: int = 0,
    max_repair_attempts: int = 1,
) -> CandidateState:
    """Return the target state for one legal edge.

    Does not write artifacts. ``guard_passed`` is the caller's
    evaluation of that row's guard. A false guard leaves the subject
    where it is by raising ``GuardRejected``.
    """
    row = transition_row(
        state,
        event,
        repair_attempts=repair_attempts,
        max_repair_attempts=max_repair_attempts,
    )
    if row is None:
        raise IllegalTransition(state, event)
    if not guard_passed:
        raise GuardRejected([row.guard])
    return row.target


def apply_signal(state: CandidateState, receipt: object) -> CandidateState:
    """Move ``COMPILE_CHECKED`` on a graded reward receipt.

    Spec §23 A5. ``receipt`` is a ``RewardableSignalReceipt`` from
    ``grade_receipt``. A bool or a diagnostic receipt is a
    ``TypeError``. This does not write the receipt;
    ``faustcoder.signal.commit_signal_check`` does. ``passed`` on the
    receipt selects ``signal_passed`` or ``signal_failed``.
    """
    from faustcoder.reward.types import RewardableSignalReceipt

    if type(receipt) is not RewardableSignalReceipt:
        raise TypeError("apply_signal requires a RewardableSignalReceipt from grade_receipt")
    event = CandidateEvent.SIGNAL_PASSED if receipt.passed else CandidateEvent.SIGNAL_FAILED
    return next_state(state, event, guard_passed=True)


def apply_diagnostic_signal(state: CandidateState, *, passed: bool) -> CandidateState:
    """Move a diagnostic signal check. This is not a reward.

    Non-reward receipts may filter SFT data. They never satisfy
    ``apply_signal``.
    """
    if not isinstance(passed, bool):
        raise TypeError("passed must be a bool")
    event = CandidateEvent.SIGNAL_PASSED if passed else CandidateEvent.SIGNAL_FAILED
    return next_state(state, event, guard_passed=True)


def render_mermaid() -> str:
    """Return a ``stateDiagram-v2`` body, including fences."""
    lines = [
        "```mermaid",
        "stateDiagram-v2",
        "    [*] --> DRAFT",
    ]
    for row in TRANSITIONS:
        lines.append(
            f"    {row.source.value} --> {row.target.value}: {row.event_label}"
        )
    lines.extend(
        [
            "    ACCEPTED --> [*]",
            "    REJECTED --> [*]",
            "```",
        ]
    )
    return "\n".join(lines)


def render_candidate_machine_markdown() -> str:
    """Return the committed candidate-machine note.

    Tests require ``docs/state-machines/candidate.md`` to equal this
    string, so the table, the illegal edges and the diagram cannot
    drift from ``TRANSITIONS``.
    """
    lines = [
        "# Candidate machine",
        "",
        "Contract: [spec §7.2](../../specs/001-faustcoder/spec.md).",
        "Implementation: [`faustcoder/candidate_machine.py`](../../faustcoder/candidate_machine.py).",
        "T04 persists the `signal_passed` and `signal_failed` effects",
        "(a DSPTestReceipt). The other effects stay in the table so illegal",
        "edges are rejected; later tasks write their artifacts.",
        "`apply_signal` takes a `RewardableSignalReceipt` from",
        "`grade_receipt` (spec §23 A5). The receipt must carry",
        "`thresholds.reward_graded` and a profile digest in",
        "`REWARD_PROFILES`. Diagnostic checks use",
        "`apply_diagnostic_signal` and are not rewards.",
        "",
        f"Initial state: `{INITIAL_STATE.value}`.",
        "",
        "Final states: "
        + ", ".join(f"`{state.value}`" for state in CandidateState if state in FINAL_STATES)
        + ".",
        "",
        "INFERRED states (spec §7.2): "
        + ", ".join(
            f"`{state.value}`" for state in CandidateState if state in INFERRED_STATES
        )
        + ".",
        "",
        "## States",
        "",
        "| State | INFERRED |",
        "|---|---|",
    ]
    for state in CandidateState:
        flag = "yes" if state in INFERRED_STATES else "no"
        lines.append(f"| `{state.value}` | {flag} |")
    lines.extend(["", "## Events", "", "| Event |", "|---|"])
    for event in CandidateEvent:
        lines.append(f"| `{event.value}` |")
    lines.extend(
        [
            "",
            "## Transition table",
            "",
            "| From | Event | Guard | To | Effect |",
            "|---|---|---|---|---|",
        ]
    )
    for row in TRANSITIONS:
        lines.append(
            f"| `{row.source.value}` | `{row.event.value}` | {row.guard} "
            f"| `{row.target.value}` | {row.effect} |"
        )
    lines.extend(["", "## Illegal transitions", ""])
    for _source, _event, text in ILLEGAL_EDGES:
        lines.append(f"- {text}")
    lines.extend(
        [
            "- `compile_failed` -> `REPAIRING` when "
            "`repair_attempts >= max_repair_attempts`. The row selected is "
            "`REJECTED` (R-012). There is no unbounded repair loop.",
            "- `review_recorded` or `accept` driven by the generating model's "
            "self-assessment (R-011). The `review_recorded` guard states this; "
            "the caller passes a failed guard.",
            "- Rejecting a program only because its raw signal graph contains "
            "legal, delayed feedback (§4.2, ADR-0001). The signal harness has "
            "no such check.",
            "- Any transition out of `ACCEPTED` or `REJECTED`. A new attempt "
            "is a new node.",
            "",
            "## Diagram",
            "",
            render_mermaid(),
            "",
        ]
    )
    return "\n".join(lines)

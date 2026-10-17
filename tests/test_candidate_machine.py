"""Candidate-machine table, diagram, and the signal edges."""

from __future__ import annotations

from pathlib import Path

import pytest

from faustcoder.candidate_machine import (
    FINAL_STATES,
    ILLEGAL_EDGES,
    INFERRED_STATES,
    INITIAL_STATE,
    TRANSITIONS,
    CandidateEvent,
    CandidateState,
    GuardRejected,
    IllegalTransition,
    apply_signal,
    next_state,
    render_candidate_machine_markdown,
    render_mermaid,
    transition_row,
)

DOC = Path(__file__).resolve().parents[1] / "docs" / "state-machines" / "candidate.md"


def test_initial_and_final_states_match_the_spec() -> None:
    assert INITIAL_STATE is CandidateState.DRAFT
    assert FINAL_STATES == {CandidateState.ACCEPTED, CandidateState.REJECTED}
    assert INFERRED_STATES == {CandidateState.REPAIRING}
    assert {state.value for state in CandidateState} == {
        "DRAFT",
        "COMPILE_CHECKED",
        "SIGNAL_CHECKED",
        "TARGET_CHECKED",
        "REVIEWED",
        "ACCEPTED",
        "REJECTED",
        "REPAIRING",
    }
    assert {event.value for event in CandidateEvent} == {
        "compile_passed",
        "compile_failed",
        "repair_produced",
        "abstain",
        "signal_passed",
        "signal_failed",
        "lanes_passed",
        "lane_failed",
        "review_recorded",
        "accept",
        "reject",
    }


def test_each_event_has_one_row_per_source_except_compile_failed() -> None:
    seen: set[tuple[CandidateState, CandidateEvent, CandidateState]] = set()
    for row in TRANSITIONS:
        key = (row.source, row.event, row.target)
        assert key not in seen
        seen.add(key)
        if row.event is CandidateEvent.COMPILE_FAILED:
            attempts = 0 if row.target is CandidateState.REPAIRING else 1
            assert (
                transition_row(
                    row.source,
                    row.event,
                    repair_attempts=attempts,
                    max_repair_attempts=1,
                )
                is row
            )
        else:
            assert transition_row(row.source, row.event) is row


def test_compile_failed_follows_the_attempt_bound() -> None:
    assert next_state(
        CandidateState.DRAFT,
        CandidateEvent.COMPILE_FAILED,
        guard_passed=True,
        repair_attempts=0,
        max_repair_attempts=3,
    ) is CandidateState.REPAIRING
    assert next_state(
        CandidateState.DRAFT,
        CandidateEvent.COMPILE_FAILED,
        guard_passed=True,
        repair_attempts=3,
        max_repair_attempts=3,
    ) is CandidateState.REJECTED


def test_signal_edges_leave_compile_checked() -> None:
    from faustcoder.candidate_machine import apply_diagnostic_signal
    from faustcoder.reward import grade_receipt
    from tests.support import allowlisted_reward_envelope

    passed = grade_receipt(allowlisted_reward_envelope(passed=True))
    failed = grade_receipt(allowlisted_reward_envelope(passed=False))
    assert apply_signal(CandidateState.COMPILE_CHECKED, passed) is CandidateState.SIGNAL_CHECKED
    assert apply_signal(CandidateState.COMPILE_CHECKED, failed) is CandidateState.REJECTED
    with pytest.raises(IllegalTransition):
        apply_signal(CandidateState.DRAFT, passed)
    with pytest.raises(TypeError, match="RewardableSignalReceipt"):
        apply_signal(CandidateState.COMPILE_CHECKED, True)  # type: ignore[arg-type]
    assert apply_diagnostic_signal(CandidateState.COMPILE_CHECKED, passed=True) is (
        CandidateState.SIGNAL_CHECKED
    )
    assert apply_diagnostic_signal(CandidateState.COMPILE_CHECKED, passed=False) is (
        CandidateState.REJECTED
    )


def test_signal_guard_can_reject_without_moving() -> None:
    with pytest.raises(GuardRejected):
        next_state(
            CandidateState.COMPILE_CHECKED,
            CandidateEvent.SIGNAL_PASSED,
            guard_passed=False,
        )


@pytest.mark.parametrize(("state", "event", "text"), ILLEGAL_EDGES)
def test_illegal_edges_are_absent(
    state: CandidateState, event: CandidateEvent, text: str
) -> None:
    assert text
    assert transition_row(state, event) is None
    with pytest.raises(IllegalTransition):
        next_state(state, event, guard_passed=True)


@pytest.mark.parametrize("state", [CandidateState.ACCEPTED, CandidateState.REJECTED])
def test_terminal_states_have_no_outgoing_edge(state: CandidateState) -> None:
    for event in CandidateEvent:
        assert transition_row(state, event) is None


def test_mermaid_and_doc_match_the_table() -> None:
    diagram = render_mermaid()
    assert diagram.startswith("```mermaid\nstateDiagram-v2\n")
    assert "[*] --> DRAFT" in diagram
    for row in TRANSITIONS:
        assert f"{row.source.value} --> {row.target.value}: {row.event_label}" in diagram
    for state in FINAL_STATES:
        assert f"{state.value} --> [*]" in diagram
    assert DOC.read_text(encoding="utf-8") == render_candidate_machine_markdown()

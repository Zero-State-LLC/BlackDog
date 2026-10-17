"""Training-machine table, diagram, and the env_verified edge."""

from __future__ import annotations

from pathlib import Path

import pytest

from faustcoder.training_machine import (
    FINAL_STATES,
    ILLEGAL_EDGES,
    INFERRED_STATES,
    INITIAL_STATE,
    TRANSITIONS,
    GuardRejected,
    IllegalTransition,
    TrainingEvent,
    TrainingState,
    next_state,
    render_mermaid,
    render_training_machine_markdown,
    transition_row,
)

DOC = Path(__file__).resolve().parents[1] / "docs" / "state-machines" / "training.md"


def test_initial_and_final_states_match_the_spec() -> None:
    assert INITIAL_STATE is TrainingState.PLANNED
    assert FINAL_STATES == {
        TrainingState.ADMITTED,
        TrainingState.REJECTED,
        TrainingState.FAILED,
        TrainingState.INVALIDATED,
    }
    assert INFERRED_STATES == {TrainingState.FAILED, TrainingState.INVALIDATED}
    assert {state.value for state in TrainingState} == {
        "PLANNED",
        "ENV_VERIFIED",
        "RUNNING",
        "COMPLETED",
        "EVALUATED",
        "ADMITTED",
        "REJECTED",
        "FAILED",
        "INVALIDATED",
    }
    assert {event.value for event in TrainingEvent} == {
        "env_verified",
        "run_started",
        "run_finished",
        "run_failed",
        "evaluation_recorded",
        "admit",
        "reject",
        "upstream_invalidated",
    }


def test_each_event_has_one_row_per_source() -> None:
    seen: set[tuple[TrainingState, TrainingEvent]] = set()
    for row in TRANSITIONS:
        key = (row.source, row.event)
        assert key not in seen
        seen.add(key)
        assert transition_row(row.source, row.event) is row


def test_env_verified_is_the_only_edge_out_of_planned() -> None:
    assert next_state(
        TrainingState.PLANNED,
        TrainingEvent.ENV_VERIFIED,
        guard_passed=True,
    ) is TrainingState.ENV_VERIFIED
    with pytest.raises(GuardRejected):
        next_state(
            TrainingState.PLANNED,
            TrainingEvent.ENV_VERIFIED,
            guard_passed=False,
        )


@pytest.mark.parametrize(("state", "event", "text"), ILLEGAL_EDGES)
def test_illegal_edges_are_absent(
    state: TrainingState, event: TrainingEvent, text: str
) -> None:
    assert text
    assert transition_row(state, event) is None
    with pytest.raises(IllegalTransition):
        next_state(state, event, guard_passed=True)


@pytest.mark.parametrize(
    "state",
    [TrainingState.REJECTED, TrainingState.FAILED, TrainingState.INVALIDATED],
)
def test_terminal_states_have_no_outgoing_edge(state: TrainingState) -> None:
    for event in TrainingEvent:
        assert transition_row(state, event) is None


def test_run_started_guard_can_pass_without_writing_a_training_run() -> None:
    assert next_state(
        TrainingState.ENV_VERIFIED,
        TrainingEvent.RUN_STARTED,
        guard_passed=True,
    ) is TrainingState.RUNNING


def test_mermaid_and_doc_match_the_table() -> None:
    diagram = render_mermaid()
    assert diagram.startswith("```mermaid\nstateDiagram-v2\n")
    assert "[*] --> PLANNED" in diagram
    for row in TRANSITIONS:
        assert (
            f"{row.source.value} --> {row.target.value}: {row.event_label}"
            in diagram
        )
    for state in FINAL_STATES:
        assert f"{state.value} --> [*]" in diagram
    assert DOC.is_file()
    assert DOC.read_text(encoding="utf-8") == render_training_machine_markdown()

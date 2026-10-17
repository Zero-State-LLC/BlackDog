"""Training-run state machine (spec §7.3).

The transition table is the contract. ``next_state`` only resolves a
legal edge. The only effect this module persists is ``env_verified``
(R-001): record an environment digest. Later tasks own the other
effects (TrainingRun, checkpoints, evaluation, decision records).

``FAILED`` and ``INVALIDATED``, the ``run_failed`` event, and the
``upstream_invalidated`` effect are INFERRED in spec §7.3. They are
included so illegal edges can be rejected. They are not given new
meaning here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TrainingState(StrEnum):
    """States of one training-run subject (spec §7.3)."""

    PLANNED = "PLANNED"
    ENV_VERIFIED = "ENV_VERIFIED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    EVALUATED = "EVALUATED"
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    INVALIDATED = "INVALIDATED"


class TrainingEvent(StrEnum):
    """Events of the training-run machine (spec §7.3)."""

    ENV_VERIFIED = "env_verified"
    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"
    RUN_FAILED = "run_failed"
    EVALUATION_RECORDED = "evaluation_recorded"
    ADMIT = "admit"
    REJECT = "reject"
    UPSTREAM_INVALIDATED = "upstream_invalidated"


class IllegalTransition(Exception):
    """``event`` is not an edge out of ``state``."""

    def __init__(self, state: TrainingState, event: TrainingEvent) -> None:
        self.state = state
        self.event = event
        super().__init__(f"no {event.value} edge out of {state.value}")


class GuardRejected(Exception):
    """The edge exists and its guard refused the transition."""

    def __init__(
        self,
        reasons: list[str],
        *,
        diagnostics_digest: str | None = None,
        diagnostics_id: str | None = None,
    ) -> None:
        self.reasons = list(reasons)
        self.diagnostics_digest = diagnostics_digest
        self.diagnostics_id = diagnostics_id
        detail = "; ".join(self.reasons) if self.reasons else "guard rejected"
        super().__init__(detail)


@dataclass(frozen=True)
class Transition:
    """One row of the spec §7.3 table."""

    source: TrainingState
    event: TrainingEvent
    target: TrainingState
    guard: str
    effect: str
    inferred: bool = False

    @property
    def event_label(self) -> str:
        if self.inferred and self.event is TrainingEvent.RUN_FAILED:
            return f"{self.event.value} (INFERRED)"
        return self.event.value


INITIAL_STATE = TrainingState.PLANNED
FINAL_STATES = frozenset(
    {
        TrainingState.ADMITTED,
        TrainingState.REJECTED,
        TrainingState.FAILED,
        TrainingState.INVALIDATED,
    }
)
INFERRED_STATES = frozenset({TrainingState.FAILED, TrainingState.INVALIDATED})

_FROZEN_GUARD = (
    "Dataset snapshot is `FROZEN`; split, config and code revision "
    "digests pinned (R-009)"
)
_UPSTREAM_GUARD = (
    "An ancestor (dataset, split, base model, code) was invalidated"
)
_UPSTREAM_EFFECT = (
    "Mark dependent attestations invalid until rerun (INFERRED)"
)

TRANSITIONS: tuple[Transition, ...] = (
    Transition(
        TrainingState.PLANNED,
        TrainingEvent.ENV_VERIFIED,
        TrainingState.ENV_VERIFIED,
        "Pinned dependencies and hardware diagnostics recorded on DGX Spark (R-001)",
        "Record environment digest",
    ),
    Transition(
        TrainingState.ENV_VERIFIED,
        TrainingEvent.RUN_STARTED,
        TrainingState.RUNNING,
        _FROZEN_GUARD,
        "Write TrainingRun with parents",
    ),
    Transition(
        TrainingState.RUNNING,
        TrainingEvent.RUN_FINISHED,
        TrainingState.COMPLETED,
        "Training exited cleanly",
        "Record `checkpoint_digests`",
    ),
    Transition(
        TrainingState.RUNNING,
        TrainingEvent.RUN_FAILED,
        TrainingState.FAILED,
        "Crash, OOM or timeout (INFERRED)",
        "Append failure receipt; a retry is a new TrainingRun (§4.1)",
        inferred=True,
    ),
    Transition(
        TrainingState.COMPLETED,
        TrainingEvent.EVALUATION_RECORDED,
        TrainingState.EVALUATED,
        (
            "Independent EvaluationRun on the development suite and "
            "sealed holdout (§9, R-011)"
        ),
        "Write EvaluationRun with paired comparison and confidence intervals",
    ),
    Transition(
        TrainingState.EVALUATED,
        TrainingEvent.ADMIT,
        TrainingState.ADMITTED,
        "Gates met against the frozen baseline (D-005)",
        "Write DecisionRecord (admitted)",
    ),
    Transition(
        TrainingState.EVALUATED,
        TrainingEvent.REJECT,
        TrainingState.REJECTED,
        "Gates not met",
        "Write DecisionRecord (rejected)",
    ),
    Transition(
        TrainingState.COMPLETED,
        TrainingEvent.UPSTREAM_INVALIDATED,
        TrainingState.INVALIDATED,
        _UPSTREAM_GUARD,
        _UPSTREAM_EFFECT,
        inferred=True,
    ),
    Transition(
        TrainingState.EVALUATED,
        TrainingEvent.UPSTREAM_INVALIDATED,
        TrainingState.INVALIDATED,
        _UPSTREAM_GUARD,
        _UPSTREAM_EFFECT,
        inferred=True,
    ),
    Transition(
        TrainingState.ADMITTED,
        TrainingEvent.UPSTREAM_INVALIDATED,
        TrainingState.INVALIDATED,
        _UPSTREAM_GUARD,
        _UPSTREAM_EFFECT,
        inferred=True,
    ),
)

# Spec §7.3 illegal transitions that are not rows. Guard text that
# further restricts a row lives on that row; these are absent edges.
ILLEGAL_EDGES: tuple[tuple[TrainingState, TrainingEvent, str], ...] = (
    (
        TrainingState.PLANNED,
        TrainingEvent.RUN_STARTED,
        "PLANNED -> RUNNING: the environment is verified first (R-001)",
    ),
    (
        TrainingState.COMPLETED,
        TrainingEvent.ADMIT,
        "COMPLETED -> ADMITTED: admission needs an independent evaluation",
    ),
    (
        TrainingState.REJECTED,
        TrainingEvent.ADMIT,
        "No edge out of REJECTED (spec §7.3)",
    ),
    (
        TrainingState.FAILED,
        TrainingEvent.RUN_STARTED,
        "No edge out of FAILED (spec §7.3, INFERRED state)",
    ),
    (
        TrainingState.INVALIDATED,
        TrainingEvent.ENV_VERIFIED,
        "No edge out of INVALIDATED (spec §7.3, INFERRED state)",
    ),
    (
        TrainingState.ADMITTED,
        TrainingEvent.REJECT,
        "Any transition out of REJECTED is forbidden; ADMITTED has no reject edge",
    ),
)


def transition_row(state: TrainingState, event: TrainingEvent) -> Transition | None:
    """Return the unique row for ``state`` and ``event``, if one exists."""
    matches = [
        row for row in TRANSITIONS if row.source is state and row.event is event
    ]
    if len(matches) > 1:
        raise IllegalTransition(state, event)
    if not matches:
        return None
    return matches[0]


def next_state(
    state: TrainingState,
    event: TrainingEvent,
    *,
    guard_passed: bool,
) -> TrainingState:
    """Return the target state for one legal edge.

    Does not write artifacts. ``guard_passed`` is the caller's
    evaluation of that row's guard. A false guard leaves the subject
    where it is by raising ``GuardRejected``.
    """
    row = transition_row(state, event)
    if row is None:
        raise IllegalTransition(state, event)
    if not guard_passed:
        raise GuardRejected([row.guard])
    return row.target


def render_mermaid() -> str:
    """Return the spec §7.3 ``stateDiagram-v2`` body, including fences."""
    lines = [
        "```mermaid",
        "stateDiagram-v2",
        "    [*] --> PLANNED",
    ]
    for row in TRANSITIONS:
        lines.append(
            f"    {row.source.value} --> {row.target.value}: {row.event_label}"
        )
    lines.extend(
        [
            "    ADMITTED --> [*]",
            "    REJECTED --> [*]",
            "    FAILED --> [*]",
            "    INVALIDATED --> [*]",
            "```",
        ]
    )
    return "\n".join(lines)


def render_training_machine_markdown() -> str:
    """Return the committed training-machine note.

    Tests require ``docs/state-machines/training.md`` to equal this
    string, so the table, the illegal edges and the diagram cannot
    drift from ``TRANSITIONS``.
    """
    lines = [
        "# Training machine",
        "",
        "Contract: [spec §7.3](../../specs/001-faustcoder/spec.md).",
        "Implementation: [`faustcoder/training_machine.py`](../../faustcoder/training_machine.py).",
        "T09 persists the `env_verified` effect only. The other effects",
        "stay in the table so illegal edges are rejected; T10 and later",
        "tasks write their artifacts.",
        "",
        f"Initial state: `{INITIAL_STATE.value}`.",
        "",
        "Final states: "
        + ", ".join(
            f"`{state.value}`" for state in TrainingState if state in FINAL_STATES
        )
        + ".",
        "",
        "INFERRED states (spec §7.3): "
        + ", ".join(
            f"`{state.value}`" for state in TrainingState if state in INFERRED_STATES
        )
        + ".",
        "",
        "## States",
        "",
        "| State | INFERRED |",
        "|---|---|",
    ]
    for state in TrainingState:
        flag = "yes" if state in INFERRED_STATES else "no"
        lines.append(f"| `{state.value}` | {flag} |")
    lines.extend(["", "## Events", "", "| Event |", "|---|"])
    for event in TrainingEvent:
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
            "- `run_started` on a dataset that is not `FROZEN`, or with any "
            "holdout item in the training data (§9). The `run_started` guard "
            "states this; T10 evaluates it.",
            "- Overwriting a failed run's receipts on retry (§4.1). A retry "
            "is a new subject.",
            "",
            "## Diagram",
            "",
            render_mermaid(),
            "",
        ]
    )
    return "\n".join(lines)

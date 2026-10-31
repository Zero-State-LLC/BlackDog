"""Static checks on the spec 002 receipt graph (R-N004, R-N005).

The graph is the set of stored envelopes keyed by content digest, with
an edge from each child to each of its ``parents``. ``ArtifactStore``
already refuses cycles and missing parents at write time; this module
re-checks a whole graph after the fact, adds the spec 002 rules, and
names every failure instead of stopping at the first one.

Invalidation reuses the training machine: a TrainingRun that descends
from an invalidated node takes the ``upstream_invalidated`` edge. A
rerun is a new TrainingRun whose lineage avoids the invalid node, so it
is not affected.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from faustcoder.canonical import build_envelope
from faustcoder.errors import SchemaValidationError
from faustcoder.nvidia.receipts import (
    ReceiptKind,
    ReceiptRuleError,
    parents_of,
    parse_rfc3339,
    receipt_kind,
    rule_violations,
)
from faustcoder.schemas import validate
from faustcoder.spark_probe import DIAGNOSTICS_KIND, environment_guard
from faustcoder.store import ArtifactStore
from faustcoder.training_machine import (
    IllegalTransition,
    TrainingEvent,
    TrainingState,
    next_state,
)

Nodes = Mapping[str, Mapping[str, object]]
TRAINING_RUN = "TrainingRun"
ENVIRONMENT = DIAGNOSTICS_KIND
OTHER = "Other"


class FindingCode(StrEnum):
    """Why a node fails the static check."""

    MISSING_PARENT = "missing_parent"
    PARENT_NOT_EARLIER = "parent_not_earlier"
    CYCLE = "cycle"
    TRAINING_RUN_UNPINNED = "training_run_unpinned"
    PARENT_RULE = "parent_rule"


@dataclass(frozen=True)
class Finding:
    """One rule failure on one node."""

    code: FindingCode
    node: str
    detail: str


@dataclass(frozen=True)
class GraphReport:
    """Result of ``check_receipt_graph``. ``ok`` means no findings."""

    node_count: int
    findings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        """Return True when the graph passed every rule."""
        return not self.findings


@dataclass(frozen=True)
class Invalidation:
    """TrainingRun state changes caused by one invalidated ancestor."""

    cause: str
    changed: Mapping[str, TrainingState]
    untouched: tuple[str, ...]


def load_nodes(store: ArtifactStore) -> dict[str, Mapping[str, object]]:
    """Return every stored envelope keyed by its content digest."""
    return {f"sha256:{artifact_id}": store.get(artifact_id) for artifact_id in store.list()}


def node_kind(envelope: Mapping[str, object]) -> str:
    """Return the graph kind of one envelope.

    Spec 002 receipts and environment diagnostics carry a payload
    ``kind``. A TrainingRun has none, so it is recognized by its schema.
    """
    payload = _payload(envelope)
    kind = receipt_kind(payload)
    if kind is not None:
        return kind.value
    if payload.get("kind") == DIAGNOSTICS_KIND:
        return ENVIRONMENT
    try:
        validate(dict(payload), "training-run.schema.json")
    except SchemaValidationError:
        return OTHER
    return TRAINING_RUN


def check_receipt_graph(nodes: Nodes) -> GraphReport:
    """Run every static rule over ``nodes`` and collect the failures."""
    findings: list[Finding] = []
    for digest in sorted(nodes):
        findings.extend(_edge_findings(nodes, digest))
        findings.extend(_rule_findings(nodes, digest))
    findings.extend(_cycle_findings(nodes))
    for digest in sorted(nodes):
        if node_kind(nodes[digest]) != TRAINING_RUN:
            continue
        kinds = {node_kind(nodes[node]) for node in ancestors(nodes, digest)}
        if ReceiptKind.CONTAINER_PIN.value not in kinds:
            findings.append(
                Finding(
                    FindingCode.TRAINING_RUN_UNPINNED, digest, "no ContainerPinReceipt ancestor"
                )
            )
    return GraphReport(node_count=len(nodes), findings=tuple(findings))


def ancestors(nodes: Nodes, digest: str, *, skip_kinds: Iterable[str] = ()) -> set[str]:
    """Return the stored ancestors of ``digest``.

    Nodes whose kind is in ``skip_kinds`` are neither returned nor
    walked through. Missing parents are ignored; the static check
    reports them.
    """
    skipped = set(skip_kinds)
    seen: set[str] = set()
    stack = list(parents_of(nodes[digest]))
    while stack:
        current = stack.pop()
        if current in seen or current not in nodes:
            continue
        if node_kind(nodes[current]) in skipped:
            continue
        seen.add(current)
        stack.extend(parents_of(nodes[current]))
    return seen


def dependent_training_runs(nodes: Nodes, invalid: str) -> tuple[str, ...]:
    """Return every TrainingRun that has ``invalid`` as an ancestor."""
    return tuple(
        digest
        for digest in sorted(nodes)
        if node_kind(nodes[digest]) == TRAINING_RUN and invalid in ancestors(nodes, digest)
    )


def invalidate_dependents(
    nodes: Nodes, invalid: str, states: Mapping[str, TrainingState]
) -> Invalidation:
    """Apply ``upstream_invalidated`` to each dependent TrainingRun.

    ``states`` holds each run's current state. A run in a state with no
    ``upstream_invalidated`` edge (or with no known state) is listed in
    ``untouched`` rather than forced.
    """
    changed: dict[str, TrainingState] = {}
    untouched: list[str] = []
    for run in dependent_training_runs(nodes, invalid):
        state = states.get(run)
        if state is None:
            untouched.append(run)
            continue
        try:
            changed[run] = next_state(state, TrainingEvent.UPSTREAM_INVALIDATED, guard_passed=True)
        except IllegalTransition:
            untouched.append(run)
    return Invalidation(cause=invalid, changed=changed, untouched=tuple(untouched))


def record_invalidation(
    store: ArtifactStore,
    invalidation: Invalidation,
    states: Mapping[str, TrainingState],
    *,
    actor: str,
    timestamp: str,
) -> tuple[str, ...]:
    """Store one TransitionReceipt per changed run and return their ids.

    Each receipt's parents are the invalidated node and the run, so the
    invalidation itself is append-only lineage.
    """
    stored: list[str] = []
    for run, target in sorted(invalidation.changed.items()):
        payload: dict[str, object] = {
            "actor": actor,
            "timestamp": timestamp,
            "input_hashes": [invalidation.cause, run],
            "machine": "training",
            "from": states[run].value,
            "event": TrainingEvent.UPSTREAM_INVALIDATED.value,
            "to": target.value,
            "disposition": "Invalidate dependents until rerun",
        }
        validate(payload, "transition-receipt.schema.json")
        envelope = build_envelope(
            schema_version="0.1.0",
            created_at=timestamp,
            producer="faustcoder.nvidia.graph",
            parents=[invalidation.cause, run],
            payload=payload,
        )
        stored.append(store.put(envelope))
    return tuple(stored)


def check_evaluation_run(
    nodes: Nodes,
    evaluation: str,
    *,
    dataset_snapshot: str,
    nim_deployment: str | None = None,
) -> list[str]:
    """Return R-N003/R-N005 failures for the canonical EvaluationRun.

    The run must trace to a Spark environment fingerprint that passes
    the R-001 guard and to ``dataset_snapshot`` along paths that do not
    pass through an ExternalCapacityReceipt, so credit usage stays
    metadata. When ``nim_deployment`` served the run it must be a
    direct parent.
    """
    if evaluation not in nodes:
        return [f"evaluation run {evaluation} is not stored"]
    local = ancestors(nodes, evaluation, skip_kinds={ReceiptKind.EXTERNAL_CAPACITY.value})
    reasons: list[str] = []
    spark = [
        node
        for node in local
        if node_kind(nodes[node]) == ENVIRONMENT and not environment_guard(_payload(nodes[node]))
    ]
    if not spark:
        reasons.append("no local Spark fingerprint outside external-capacity parents")
    if dataset_snapshot not in local:
        reasons.append("dataset snapshot is not an ancestor outside external-capacity parents")
    if nim_deployment is not None:
        if nim_deployment not in parents_of(nodes[evaluation]):
            reasons.append("NIMDeploymentReceipt is not a direct parent")
        elif node_kind(nodes[nim_deployment]) != ReceiptKind.NIM_DEPLOYMENT.value:
            reasons.append("nim_deployment does not name a NIMDeploymentReceipt")
    return reasons


def _payload(envelope: Mapping[str, object]) -> Mapping[str, object]:
    payload = envelope.get("payload")
    if isinstance(payload, Mapping):
        return payload
    return {}


def _edge_findings(nodes: Nodes, digest: str) -> list[Finding]:
    found: list[Finding] = []
    try:
        child_time = parse_rfc3339(nodes[digest].get("created_at"))
    except ReceiptRuleError as exc:
        return [Finding(FindingCode.PARENT_NOT_EARLIER, digest, str(exc))]
    for parent in parents_of(nodes[digest]):
        if parent not in nodes:
            found.append(Finding(FindingCode.MISSING_PARENT, digest, parent))
            continue
        try:
            parent_time = parse_rfc3339(nodes[parent].get("created_at"))
        except ReceiptRuleError as exc:
            found.append(Finding(FindingCode.PARENT_NOT_EARLIER, digest, f"{parent}: {exc}"))
            continue
        if parent_time > child_time:
            found.append(Finding(FindingCode.PARENT_NOT_EARLIER, digest, parent))
    return found


def _rule_findings(nodes: Nodes, digest: str) -> list[Finding]:
    """Spec 002 receipt rules. Missing parents and ordering are edge findings."""
    if receipt_kind(_payload(nodes[digest])) is None:
        return []
    return [
        Finding(FindingCode.PARENT_RULE, digest, reason)
        for reason in rule_violations(nodes[digest], nodes.get)
    ]


def _cycle_findings(nodes: Nodes) -> list[Finding]:
    """Report each node that closes a cycle, using an iterative DFS."""
    done: set[str] = set()
    found: list[Finding] = []
    for root in sorted(nodes):
        if root in done:
            continue
        path: list[str] = [root]
        on_path: set[str] = {root}
        stack: list[list[str]] = [list(parents_of(nodes[root]))]
        while stack:
            pending = stack[-1]
            if not pending:
                stack.pop()
                finished = path.pop()
                on_path.discard(finished)
                done.add(finished)
                continue
            parent = pending.pop()
            if parent in on_path:
                found.append(Finding(FindingCode.CYCLE, path[-1], parent))
            elif parent in nodes and parent not in done:
                path.append(parent)
                on_path.add(parent)
                stack.append(list(parents_of(nodes[parent])))
    return found

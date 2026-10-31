"""N02 and N07: static checks, invalidation and the Spark trace."""

from __future__ import annotations

import json
from pathlib import Path

from faustcoder import ArtifactStore, validate
from faustcoder.nvidia.graph import (
    ENVIRONMENT,
    OTHER,
    TRAINING_RUN,
    FindingCode,
    ancestors,
    check_evaluation_run,
    check_receipt_graph,
    dependent_training_runs,
    invalidate_dependents,
    load_nodes,
    node_kind,
    record_invalidation,
)
from faustcoder.nvidia.receipts import build_receipt, put_receipt
from faustcoder.training_machine import TrainingState
from tests.nvidia_support import (
    OTHER_PIN,
    T0,
    T1,
    T2,
    T3,
    T4,
    T5,
    put_plain,
    spark_diagnostics,
    stored_pin,
    training_run,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "valid"


def _fixture(stem: str) -> dict[str, object]:
    value = json.loads((FIXTURES / f"{stem}.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _digest(n: int) -> str:
    return "sha256:" + f"{n:x}" * 64


def _node(
    parents: list[str], created_at: str = T1, payload: dict[str, object] | None = None
) -> dict[str, object]:
    return {"created_at": created_at, "parents": parents, "payload": payload or {"x": 1}}


def _attempt(pin: str, dataset: str, credit: str | None = None) -> dict[str, object]:
    payload = _fixture("nemo-training-attempt")
    payload.update(
        container_pin_digest=pin,
        dataset_snapshot_digest=dataset,
        external_capacity_digest=credit,
        status="completed",
        peak_memory_bytes=1024,
        export={"format": "hf_adapter", "checkpoint_digests": [_digest(9)]},
    )
    return payload


def _pipeline(store: ArtifactStore, *, gpu: str = "NVIDIA GB10") -> dict[str, str]:
    """Store Spark diagnostics, dataset, pin, attempt and TrainingRun."""
    spark = put_plain(store, spark_diagnostics(gpu_name=gpu), [], T0)
    dataset = put_plain(store, {"snapshot": "frozen"}, [], T0)
    pin = stored_pin(store, host=spark)
    attempt = "sha256:" + put_receipt(
        store, build_receipt(_attempt(pin, dataset), created_at=T2, producer="p")
    )
    run = put_plain(store, training_run(dataset), [attempt, pin, dataset], T3)
    return {"spark": spark, "dataset": dataset, "pin": pin, "attempt": attempt, "run": run}


def test_completed_graph_has_no_findings(store: ArtifactStore) -> None:
    ids = _pipeline(store)
    nodes = load_nodes(store)
    report = check_receipt_graph(nodes)
    assert report.ok, report.findings
    assert report.node_count == 5
    assert node_kind(nodes[ids["run"]]) == TRAINING_RUN
    assert node_kind(nodes[ids["spark"]]) == ENVIRONMENT
    assert node_kind(nodes[ids["dataset"]]) == OTHER


def test_cycles_are_reported() -> None:
    a, b, c = _digest(1), _digest(2), _digest(3)
    nodes = {a: _node([b]), b: _node([c]), c: _node([a])}
    codes = [finding.code for finding in check_receipt_graph(nodes).findings]
    assert codes.count(FindingCode.CYCLE) == 1
    self_loop = {a: _node([a])}
    assert [f.code for f in check_receipt_graph(self_loop).findings] == [FindingCode.CYCLE]


def test_diamond_is_not_a_cycle() -> None:
    a, b, c, d = _digest(1), _digest(2), _digest(3), _digest(4)
    nodes = {a: _node([], T0), b: _node([a]), c: _node([a]), d: _node([b, c], T2)}
    assert check_receipt_graph(nodes).ok


def test_missing_and_later_parents_are_reported() -> None:
    a, b = _digest(1), _digest(2)
    nodes = {a: _node([], T3), b: _node([a, _digest(5)], T1)}
    codes = sorted(f.code for f in check_receipt_graph(nodes).findings)
    assert codes == [FindingCode.MISSING_PARENT, FindingCode.PARENT_NOT_EARLIER]


def test_bad_timestamps_are_findings() -> None:
    a, b = _digest(1), _digest(2)
    nodes = {a: _node([], "never"), b: _node([a], T1)}
    findings = check_receipt_graph(nodes).findings
    assert {f.node for f in findings} == {a, b}
    assert {f.code for f in findings} == {FindingCode.PARENT_NOT_EARLIER}


def test_unpinned_training_run_is_reported(store: ArtifactStore) -> None:
    dataset = put_plain(store, {"snapshot": "s"}, [], T0)
    run = put_plain(store, training_run(dataset), [dataset], T3)
    findings = check_receipt_graph(load_nodes(store)).findings
    assert [(f.code, f.node) for f in findings] == [(FindingCode.TRAINING_RUN_UNPINNED, run)]


def test_receipt_rule_breaks_are_reported() -> None:
    pin_payload = _fixture("container-pin-receipt")
    dataset = _digest(2)
    pin = _digest(1)
    unlisted = _attempt(pin, dataset)
    nodes = {
        pin: _node([], T0, pin_payload),
        dataset: _node([], T0),
        _digest(3): _node([dataset], T2, unlisted),
        _digest(4): _node([], T2, {"kind": "NeMoTrainingAttempt"}),
    }
    findings = [
        f for f in check_receipt_graph(nodes).findings if f.code is FindingCode.PARENT_RULE
    ]
    assert {f.node for f in findings} == {_digest(3), _digest(4)}


def test_invalidating_a_pin_invalidates_dependent_runs(store: ArtifactStore) -> None:
    ids = _pipeline(store)
    rerun_pin = stored_pin(store, host=ids["spark"], pin=OTHER_PIN)
    rerun = put_plain(
        store, training_run(ids["dataset"], "run-2"), [rerun_pin, ids["dataset"]], T4
    )
    nodes = load_nodes(store)
    assert dependent_training_runs(nodes, ids["pin"]) == (ids["run"],)
    states = {ids["run"]: TrainingState.EVALUATED, rerun: TrainingState.EVALUATED}
    result = invalidate_dependents(nodes, ids["pin"], states)
    assert result.changed == {ids["run"]: TrainingState.INVALIDATED}
    assert result.untouched == ()
    stored = record_invalidation(store, result, states, actor="auditor", timestamp=T5)
    receipt = store.get(stored[0])
    validate(receipt["payload"], "transition-receipt.schema.json")
    assert receipt["parents"] == [ids["pin"], ids["run"]]
    assert receipt["payload"]["event"] == "upstream_invalidated"
    assert check_receipt_graph(load_nodes(store)).ok


def test_runs_without_an_invalidation_edge_are_left_untouched(store: ArtifactStore) -> None:
    ids = _pipeline(store)
    nodes = load_nodes(store)
    for states in ({ids["run"]: TrainingState.RUNNING}, {}):
        result = invalidate_dependents(nodes, ids["dataset"], states)
        assert result.changed == {}
        assert result.untouched == (ids["run"],)


def test_evaluation_traces_to_spark_and_dataset(store: ArtifactStore) -> None:
    ids = _pipeline(store)
    evaluation = put_plain(store, {"evaluation": "e"}, [ids["run"]], T4)
    nodes = load_nodes(store)
    assert check_evaluation_run(nodes, evaluation, dataset_snapshot=ids["dataset"]) == []
    assert check_evaluation_run(nodes, _digest(7), dataset_snapshot=ids["dataset"]) == [
        f"evaluation run {_digest(7)} is not stored"
    ]
    assert check_evaluation_run(nodes, evaluation, dataset_snapshot=_digest(7)) == [
        "dataset snapshot is not an ancestor outside external-capacity parents"
    ]


def test_credit_backed_run_still_needs_a_local_spark(store: ArtifactStore) -> None:
    cloud = put_plain(store, spark_diagnostics(gpu_name="NVIDIA H100", arch="x86_64"), [], T0)
    local = put_plain(store, spark_diagnostics(), [], T0)
    dataset = put_plain(store, {"snapshot": "frozen"}, [], T0)
    credit_payload = _fixture("external-capacity-receipt")
    credit = "sha256:" + put_receipt(
        store, build_receipt(credit_payload, created_at=T1, producer="p")
    )
    pin = stored_pin(store, host=cloud)
    attempt = "sha256:" + put_receipt(
        store, build_receipt(_attempt(pin, dataset, credit), created_at=T2, producer="p")
    )
    run = put_plain(store, training_run(dataset), [attempt, pin, dataset], T3)
    cloud_only = put_plain(store, {"evaluation": "cloud"}, [run], T4)
    canonical = put_plain(store, {"evaluation": "local"}, [run, local], T4)
    nodes = load_nodes(store)
    assert check_receipt_graph(nodes).ok
    assert credit in ancestors(nodes, run)
    assert check_evaluation_run(nodes, cloud_only, dataset_snapshot=dataset) == [
        "no local Spark fingerprint outside external-capacity parents"
    ]
    assert check_evaluation_run(nodes, canonical, dataset_snapshot=dataset) == []


def test_credit_parent_does_not_carry_the_trace() -> None:
    spark, credit, evaluation, dataset = _digest(1), _digest(2), _digest(3), _digest(4)
    nodes = {
        spark: _node([], T0, spark_diagnostics()),
        dataset: _node([], T0),
        credit: _node([spark, dataset], T1, _fixture("external-capacity-receipt")),
        evaluation: _node([credit], T2),
    }
    assert len(check_evaluation_run(nodes, evaluation, dataset_snapshot=dataset)) == 2


def test_nim_deployment_must_be_a_direct_parent(store: ArtifactStore) -> None:
    ids = _pipeline(store)
    nim = _fixture("nim-deployment-receipt")
    nim.update(container_pin_digest=ids["pin"], model_artifact_digest=ids["run"])
    deployment = "sha256:" + put_receipt(store, build_receipt(nim, created_at=T4, producer="p"))
    direct = put_plain(store, {"evaluation": "nim"}, [ids["run"], deployment], T5)
    indirect = put_plain(store, {"evaluation": "no-nim"}, [ids["run"]], T5)
    nodes = load_nodes(store)
    kwargs = {"dataset_snapshot": ids["dataset"]}
    assert check_evaluation_run(nodes, direct, nim_deployment=deployment, **kwargs) == []
    assert check_evaluation_run(nodes, indirect, nim_deployment=deployment, **kwargs) == [
        "NIMDeploymentReceipt is not a direct parent"
    ]
    assert check_evaluation_run(nodes, direct, nim_deployment=ids["run"], **kwargs) == [
        "nim_deployment does not name a NIMDeploymentReceipt"
    ]


def test_odd_node_shapes() -> None:
    assert node_kind({"payload": "x"}) == OTHER
    a = _digest(1)
    assert check_receipt_graph({a: {"created_at": T1, "parents": "x", "payload": {}}}).ok

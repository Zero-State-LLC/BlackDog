"""Reward grader (N4, N5, spec §23, ADR-0006 A1–A7).

Spec 001 §23 and R-005 are in force in this module. ADR-0006 is in
force in reward code: ungraded A2 rows are not scored, and a
source-attributed failure is the ``parse_error`` rung.

``grade_receipt`` is the only constructor of ``RewardableSignalReceipt``.
It re-validates the envelope, recomputes ``reproducible_signal_digest``
and ``test_suite_digest`` from the stored payload, and accepts the
profile only when that digest is in ``REWARD_PROFILES``. Anything else
is ``Ungraded``. An ungraded sample is dropped from reward (the value
is ``None``, not 0). A2 reasons are also appended to a quarantine
queue so they stay retained and countable.

ADR-0006 A4: a reward receipt must record a signed comparison of the
whole render up to the pinned ``max_frames``, including samples past
``head_frames``. The reward-graded harness writes that comparison.
Receipts that only sign ``head_frames`` and check the tail by
magnitude are ``comparison_not_full`` and are not rewarded.

ADR-0006 A2, with the 2026-10-17 4:28 PM PT ruling: an unattributed
exit 124, 125 or 126, or a worker or harness crash, is
``Ungraded(unattributed)`` until triage attributes it. It is never
scored before then. Exit 126 is ``internal``. The rerun-plus-fixture
path is not sanctioned and must not be supplied. ``grade_receipt``
raises ``AutoAttributionRefused`` when ``rerun`` or ``known_good``
is passed, and it does not call either hook. A bare ``triage`` string
is not that attribution. A ``TriageDecision`` records who, why, and
evidence. A2-T is not implemented, so the decision fails closed and
the unattributed row stays ungraded. ``QuarantineQueue.resolve`` is
the recorded human decision and is unchanged.

A remote import and a source over 1 MiB are source-class rules and
do not wait. A harness or infrastructure ``TriageDecision`` drops
that source score. The row is then ungraded. A line that is exactly
``ERROR : stack overflow`` on exit 1, or ``ERROR : stack overflow in
eval`` on exit 126, is a source failure only when a sealed native
Faust 2.88.0 ``faust-cli`` receipt (``lang`` ``cpp``, exit exactly 1)
failed with that same line. Without that match the row stays
ungraded, including the plain exit-1 line. It is not a compiler
rejection. A compiler receipt with ``termination_signal`` set is
ungraded and quarantined. Marker matching is case-sensitive and does
not read harness text or a later render crash. A JS
``runtime_stack_overflow`` flag and a ``wasm_trap`` kind stay
ungraded. ``shadow_observe`` may rerun and log. Its ``ShadowLog`` is
not a grade and never reaches ``reward_value`` or a receipt.

A receipt that leaves this process is a MAC'd reward-row record
(ADR-0006 D3, option H). This module still recomputes digests. A
MAC is not accepted in place of that re-check. ``passed`` is true
only when ``metrics.failures`` is empty. The seal binds the whole
task. Ed25519 and the sampled re-execution audit are later changes.

Reward-graded ``run_signal`` and ``commit_signal_check`` are the
production path. They pass a persistent quarantine queue and the A7
tracker into ``grade_receipt``. A reward-graded compiler failure or
worker crash with no ledger is refused, not scored and not dropped.
``compile_source`` by itself is not a reward consumer.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import weakref
from typing import Any

from faustcoder.canonical import content_digest_for
from faustcoder.compiler import NATIVE_FAUST_VERSION, reproducible_receipt_digest
from faustcoder.errors import SchemaValidationError
from faustcoder.reward.profiles import reward_profiles
from faustcoder.reward.types import (
    QUARANTINE_REASONS,
    FixtureOutcome,
    QuarantineQueue,
    QuarantineRecord,
    RerunOutcome,
    RewardableSignalReceipt,
    SourceAttributedFailure,
    TriageAttribution,
    TriageDecision,
    Ungraded,
    UngradedRateTracker,
    UngradedReason,
)
from faustcoder.schemas import validate
from faustcoder.signal import (
    SIGNAL_SCHEMA_VERSION,
    reproducible_signal_digest,
)

# Signal envelopes this grader accepts. A bump forces a new allowlist
# entry because ``metric_version`` is inside the profile digest.
ACCEPTED_SIGNAL_SCHEMA_VERSIONS = frozenset({SIGNAL_SCHEMA_VERSION})
ACCEPTED_COMPILER_SCHEMA_VERSIONS = frozenset({"0.3.2"})
FULL_COMPARISON = "reward-graded-signed-full"
_REMOTE_DIAGNOSTIC = "internal: remote import rejected\n"
_SOURCE_SIZE_DIAGNOSTIC = "resource limit: source size\n"
# Faust's own compile diagnostic, at the start of a line, case-sensitive.
# Harness prose and render exceptions are not in this list.
_COMPILE_STACK_LINES = (
    "ERROR : stack overflow in eval",
    "ERROR : stack overflow",
)
_HARNESS_PREFIXES = ("internal:", "resource limit:", "timeout:", "renderer stopped:")
_EXIT_CLASS = {124: "timeout", 125: "resource_limit", 126: "internal"}
_CRASH_KINDS = frozenset({"worker_crash", "harness_crash"})
_CRASH_EXITS = frozenset({None, 126, 137, 139, -9})
_SIGNAL_KILL_EXITS = frozenset({137, 139, -9})
_ENVELOPE_FIELDS = frozenset(
    {
        "schema_version",
        "artifact_id",
        "content_digest",
        "created_at",
        "producer",
        "parents",
        "payload",
    }
)
# Counted in the A7 rate, including the three closed failures that are
# not A2 quarantine reasons.
_RATE_REASONS = QUARANTINE_REASONS | {
    UngradedReason.SCHEMA_INVALID,
    UngradedReason.DIGEST_MISMATCH,
    UngradedReason.COMPARISON_NOT_FULL,
}
_THRESHOLD_KEYS = (
    "absolute_tolerance_nano",
    "clip_peak_nano",
    "head_frames",
    "relative_tolerance_nano",
    "silence_rms_nano",
    "tail_threshold_nano",
)

Grade = RewardableSignalReceipt | Ungraded | SourceAttributedFailure
Rerun = Callable[[Mapping[str, Any]], RerunOutcome]
KnownGood = Callable[[], FixtureOutcome]


class RewardProvenanceError(Exception):
    """A reward-bearing row has no ``RewardableSignalReceipt``."""


class RewardUseRefused(Exception):
    """A reward-graded failure had no ledger, so it was not scored or dropped."""


class RewardOutcomeHeld(Exception):
    """A compiler or crash outcome was graded onto the ledger and is not a score."""

    def __init__(self, grade: Grade) -> None:
        self.grade = grade
        super().__init__("reward outcome is held and is not a score")


class AutoAttributionRefused(Exception):
    """``rerun`` or ``known_good`` was supplied to grading.

    That path is not sanctioned. The row is not scored and the hooks
    are not called. Shadow mode is ``shadow_observe``, not this path.
    """


class NativeStackMatch:
    """A sealed native Faust 2.88.0 stack failure.

    Only ``mint_native_stack_match`` constructs this. A raw dict is not
    a match. ``grade_receipt`` attributes a compile stack line only when
    this seal is intact and the stack-line text is the same.
    """

    __slots__ = ("source_sha256", "stack_line", "__weakref__")

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("NativeStackMatch can only be constructed by mint_native_stack_match")

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("NativeStackMatch is immutable")

    def _snapshot(self) -> tuple[object, ...]:
        return (
            getattr(self, "source_sha256", None),
            getattr(self, "stack_line", None),
        )


@dataclass(frozen=True)
class ShadowLog:
    """A2-T shadow record. Not a grade and not a receipt.

    ``reward_value`` refuses this. It cannot be minted into a
    ``RewardableSignalReceipt`` and it cannot enter a reward row.
    """

    signature: str
    detail: str


def reward_value(result: Grade, task: object = None) -> float | None:
    """Return 1, 0, or ``None`` when the sample is dropped.

    ``Ungraded`` is ``None``. It is not scored 0. A graded signal
    failure and an A1 source failure are 0. A
    ``RewardableSignalReceipt`` is training-facing: ``task`` is
    required and must be the task the receipt was minted for.
    """
    if isinstance(result, Ungraded):
        return None
    if isinstance(result, SourceAttributedFailure):
        return 0.0
    if isinstance(result, RewardableSignalReceipt):
        if not is_minted(result):
            raise RewardProvenanceError("reward receipt was not minted by grade_receipt")
        _require_receipt_task(result, task)
        from faustcoder.signal_suite import require_task_rewardable

        require_task_rewardable(task)
        if result.passed:
            return 1.0
        return 0.0
    if isinstance(result, ShadowLog):
        raise TypeError("a shadow log is not a grade and has no reward")
    raise TypeError("reward_value requires a grade result")


def grade_compiler_exclusion(exclusion: object) -> SourceAttributedFailure:
    """Grade a ``CompilerExclusion`` at the A1 ``parse_error`` rung.

    Spec §23 A1. Matching an excluded source is a graded failure, not
    a pass and not an ungraded refuge.
    """
    from faustcoder.exclusions import CompilerExclusion

    if not isinstance(exclusion, CompilerExclusion):
        raise TypeError("grade_compiler_exclusion requires a CompilerExclusion")
    if exclusion.reward_disposition != "failure":
        raise TypeError("CompilerExclusion reward_disposition must be failure")
    return SourceAttributedFailure(detail="CompilerExclusion matched by model output")


def require_rewardable_provenance(receipt: object) -> RewardableSignalReceipt:
    """Fail unless ``receipt`` was minted by ``grade_receipt``.

    Dataset and RL batch builders call this for every reward-bearing
    row. A diagnostic receipt, an ``Ungraded`` value, or a bare dict
    is not provenance.
    """
    if type(receipt) is not RewardableSignalReceipt or not is_minted(receipt):
        raise RewardProvenanceError(
            "reward-bearing row lacks RewardableSignalReceipt provenance"
        )
    return receipt


def dataset_reward_row(
    receipt: object, *, task: object = None, **fields: object
) -> dict[str, object]:
    """Build one dataset row. The reward comes only from ``receipt``.

    ``task`` is a TaskSpec. ``require_task_rewardable`` refuses a
    missing effect, a misspelling, and ``nonlinear`` or
    ``time_variant`` even when the receipt passed.
    """
    graded = require_rewardable_provenance(receipt)
    from faustcoder.signal_suite import require_task_rewardable

    require_task_rewardable(task if isinstance(task, Mapping) else {})
    _require_receipt_task(graded, task)
    if "reward" in fields or "provenance" in fields or "task" in fields:
        raise RewardProvenanceError("reward and provenance are derived from the receipt")
    row = dict(fields)
    row["task"] = task
    row["reward"] = 1.0 if graded.passed else 0.0
    row["provenance"] = graded
    return row


def rl_batch(rows: list[Mapping[str, object]] | tuple[Mapping[str, object], ...]) -> tuple[dict[str, object], ...]:
    """Copy ``rows`` after every reward row proves its provenance.

    Jev Q1: the reward is binary, 1.0 on a full pass and 0.0 on every
    graded failure. A group with any quarantined member is dropped
    whole and is never re-entered. A quarantined row is not a
    ``RewardableSignalReceipt``, so the provenance check refuses it
    instead of masking it into the batch.
    """
    built: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for row in rows:
        if not isinstance(row, Mapping) or "reward" not in row:
            raise RewardProvenanceError("RL batch row is missing a reward")
        graded = require_rewardable_provenance(row.get("provenance"))
        from faustcoder.signal_suite import require_task_rewardable

        task = row.get("task")
        require_task_rewardable(task if isinstance(task, Mapping) else {})
        _require_receipt_task(graded, task)
        reward = _finite_reward(row.get("reward"))
        # Jev Q1 (2026-10-17): binary reward. A full pass is 1.0 and
        # every graded failure is 0.0. A group with any quarantined
        # member is dropped whole and never re-entered. The provenance
        # check above already refuses that member, so it is not masked
        # into the rows returned here.
        if graded.passed:
            if reward != 1.0:
                raise RewardProvenanceError("reward must be 1.0 when the receipt passed")
        elif reward != 0.0:
            raise RewardProvenanceError("reward must be zero when the receipt failed")
        marker = (
            graded.reproducible_digest,
            graded.task_digest,
            graded.task_digest_full,
            graded.passed,
        )
        if marker in seen:
            raise RewardProvenanceError("RL batch row is a duplicate")
        seen.add(marker)
        built.append(dict(row))
    return tuple(built)


def _finite_reward(reward: object) -> float:
    """Return a finite float reward. Bools, strings and ints are refused."""
    if isinstance(reward, bool) or not isinstance(reward, float) or not math.isfinite(reward):
        raise RewardProvenanceError("reward must be a finite float")
    return reward


def task_binding_digest(task: Mapping[str, Any]) -> str:
    """Return the canonical digest of a task id and its effect.

    This is the compatibility binding. The seal also carries
    ``task_digest_full``, the whole task. A string subclass is refused.
    """
    task_id = task.get("task_id")
    effect = task.get("effect")
    if type(task_id) is not str or task_id == "":
        raise RewardProvenanceError("task binding requires a task_id")
    if type(effect) is not str or effect == "":
        raise RewardProvenanceError("task binding requires an effect")
    return content_digest_for({"effect": effect, "task_id": task_id})


def _json_task(value: object) -> object:
    """Copy ``value`` into JSON types. A tuple is a list."""
    if isinstance(value, tuple):
        return [_json_task(item) for item in value]
    if isinstance(value, list):
        return [_json_task(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_task(item) for key, item in value.items()}
    return value


def task_digest_full(task: Mapping[str, Any]) -> str:
    """Return the canonical digest of the whole task.

    A different prompt, id or effect is a different digest. A tuple in
    the task is hashed as a JSON list. The caller passes the task at
    grade time. The persisted row's MAC is what stops that envelope
    from being sealed for a second task later.
    """
    if not isinstance(task, Mapping):
        raise RewardProvenanceError("task binding requires a task")
    frozen = _json_task(task)
    if not isinstance(frozen, dict):
        raise RewardProvenanceError("task binding requires a task")
    return content_digest_for(frozen)


def _task_digests_for_mint(task: object) -> tuple[str | None, str | None]:
    """Digest ``task`` when grading binds one. ``None`` stays unbound."""
    if task is None:
        return None, None
    if not isinstance(task, Mapping):
        raise RewardProvenanceError("task binding requires a task")
    return task_binding_digest(task), task_digest_full(task)


def _require_receipt_task(receipt: RewardableSignalReceipt, task: object) -> None:
    """Fail closed unless ``task`` is the task ``receipt`` was minted for."""
    if not isinstance(task, Mapping):
        raise RewardProvenanceError("reward row task does not match the receipt")
    digest = task_binding_digest(task)
    if type(receipt.task_digest) is not str or digest != receipt.task_digest:
        raise RewardProvenanceError("reward row task does not match the receipt")
    full = task_digest_full(task)
    if type(receipt.task_digest_full) is not str or full != receipt.task_digest_full:
        raise RewardProvenanceError("reward row task does not match the receipt")


def grade_receipt(
    envelope: Mapping[str, Any],
    *,
    diagnostics: str | None = None,
    rerun: Rerun | None = None,
    known_good: KnownGood | None = None,
    triage: object = None,
    policy: str = "default",
    queue: QuarantineQueue | None = None,
    rates: UngradedRateTracker | None = None,
    task: object = None,
    native: Mapping[str, Any] | None = None,
    native_diagnostics: str | None = None,
    row_record_id: str = "",
    group_id: str = "",
) -> Grade:
    """Grade one stored envelope.

    A DSP receipt becomes ``RewardableSignalReceipt`` or ``Ungraded``.
    When ``task`` is set, a minted receipt carries the digest of that
    task's id and effect. An unattributed exit 124, 125 or 126, or a
    worker or harness crash, stays ``unattributed`` and, when
    ``queue`` is set, pending. ``triage`` does not score that row.
    ``rerun`` and ``known_good`` are not a grading path.
    ``native`` is a sealed Faust 2.88.0 CLI match. It can attribute a
    compile stack line and nothing else.
    """
    if rerun is not None or known_good is not None:
        raise AutoAttributionRefused(
            "rerun and known_good are not sanctioned and must not be supplied to grading"
        )
    result = _grade(
        envelope,
        diagnostics=diagnostics,
        triage=triage,
        task=task,
        native=native,
        native_diagnostics=native_diagnostics,
    )
    _account(
        result,
        policy=policy,
        queue=queue,
        rates=rates,
        row_record_id=row_record_id,
        group_id=group_id,
    )
    return result


class _IdentitySeal:
    """Mint table keyed by ``id``, not by the object's hash.

    ``object.__setattr__`` can change ``task_digest`` after mint. A
    hash-keyed table would miss that object. This table still finds it,
    and the stored snapshot then fails the comparison.
    """

    def __init__(self) -> None:
        self._refs: dict[int, weakref.ReferenceType[object]] = {}
        self._rows: dict[int, tuple[object, ...]] = {}

    def remember(self, obj: object, row: tuple[object, ...]) -> None:
        ident = id(obj)

        def _drop(_ref: object, ident: int = ident) -> None:
            self._refs.pop(ident, None)
            self._rows.pop(ident, None)

        self._refs[ident] = weakref.ref(obj, _drop)
        self._rows[ident] = row

    def row(self, obj: object) -> tuple[object, ...] | None:
        ident = id(obj)
        ref = self._refs.get(ident)
        if ref is None or ref() is not obj:
            return None
        return self._rows.get(ident)


def _bind_grade_receipt(grade: Callable[..., Grade]) -> tuple[
    Callable[..., Grade],
    Callable[[object], bool],
]:
    """Seal receipts inside ``grade`` so the registry is not a module global.

    The seal closes over a nonce and the object's identity. A lookalike
    built with the same fields is a different object and is rejected.
    A later ``object.__setattr__`` on ``task_digest`` breaks the seal.
    """
    registry = _IdentitySeal()
    token = object()

    def is_minted(receipt: object) -> bool:
        if type(receipt) is not RewardableSignalReceipt:
            return False
        row = registry.row(receipt)
        if row is None:
            return False
        identity, stamp, snapshot = row
        return identity == id(receipt) and stamp is token and snapshot == receipt._snapshot()

    def grade_receipt(
        envelope: Mapping[str, Any],
        *,
        diagnostics: str | None = None,
        rerun: Rerun | None = None,
        known_good: KnownGood | None = None,
        triage: object = None,
        policy: str = "default",
        queue: QuarantineQueue | None = None,
        rates: UngradedRateTracker | None = None,
        task: object = None,
        native: Mapping[str, Any] | None = None,
        native_diagnostics: str | None = None,
        row_record_id: str = "",
        group_id: str = "",
    ) -> Grade:
        result = grade(
            envelope,
            diagnostics=diagnostics,
            rerun=rerun,
            known_good=known_good,
            triage=triage,
            policy=policy,
            queue=queue,
            rates=rates,
            task=task,
            native=native,
            native_diagnostics=native_diagnostics,
            row_record_id=row_record_id,
            group_id=group_id,
        )
        if isinstance(result, RewardableSignalReceipt):
            registry.remember(result, (id(result), token, result._snapshot()))
        return result

    return grade_receipt, is_minted


def _bind_native_mint() -> tuple[
    Callable[[Mapping[str, Any], str], NativeStackMatch],
    Callable[[object], bool],
]:
    """Seal native stack matches. A raw receipt dict is not a seal."""
    registry = _IdentitySeal()
    token = object()

    def is_native_minted(match: object) -> bool:
        if type(match) is not NativeStackMatch:
            return False
        row = registry.row(match)
        if row is None:
            return False
        identity, stamp, snapshot = row
        return identity == id(match) and stamp is token and snapshot == match._snapshot()

    def mint_native_stack_match(
        receipt: Mapping[str, Any], diagnostics: str
    ) -> NativeStackMatch:
        """Seal one native Faust 2.88.0 compile failure.

        ``exit_code`` must be exactly ``int`` and equal to 1. ``1.0``,
        bools and ``int`` subclasses are refused, as are harness exits
        124, 125, 126, 137, 139 and -9, and any ``termination_signal``.
        ``lang`` must be ``cpp``. ``command`` must contain ``-lang``
        exactly once, and that argument must be ``cpp``. A command that
        omits ``-lang`` is refused. The diagnostics must contain exactly
        one of the two stack lines.
        """
        if not isinstance(receipt, Mapping) or type(diagnostics) is not str:
            raise RewardProvenanceError("native match requires a receipt and its diagnostics")
        exit_code = receipt.get("exit_code")
        # ``1.0``, ``True`` and an ``int`` subclass compare equal to 1.
        # Only a real ``int`` may mint.
        if type(exit_code) is not int or exit_code != 1:
            raise RewardProvenanceError("native match requires a normal compile failure, exit 1")
        body = dict(receipt)
        try:
            validate(body, "compiler-receipt.schema.json")
        except SchemaValidationError as exc:
            raise RewardProvenanceError("native receipt is not a compiler receipt") from exc
        if body.get("compiler") != "faust-cli" or body.get("faust_version") != NATIVE_FAUST_VERSION:
            raise RewardProvenanceError("native match requires Faust 2.88.0 faust-cli")
        if body.get("lang") != "cpp" or not _native_command(body.get("command")):
            raise RewardProvenanceError("native match requires the faust CLI cpp command")
        if body.get("exit_code") != 1 or "termination_signal" in body:
            raise RewardProvenanceError("native match requires a normal compile failure, exit 1")
        source = body.get("source_sha256")
        if type(source) is not str or source == "":
            raise RewardProvenanceError("native match requires a source hash")
        if _sha256_text(diagnostics) != body.get("stderr_digest"):
            raise RewardProvenanceError("native diagnostics do not match stderr_digest")
        line = _exact_stack_line(diagnostics)
        if line is None:
            raise RewardProvenanceError("native diagnostics have no single stack line")
        sealed = object.__new__(NativeStackMatch)
        object.__setattr__(sealed, "source_sha256", source)
        object.__setattr__(sealed, "stack_line", line)
        registry.remember(sealed, (id(sealed), token, sealed._snapshot()))
        return sealed

    return mint_native_stack_match, is_native_minted


mint_native_stack_match, is_native_minted = _bind_native_mint()


def _native_command(command: object) -> bool:
    """True when ``command`` is the native ``faust`` CLI, not libfaust-wasm.

    ``-lang`` must appear exactly once and its argument must be ``cpp``.
    Omitting ``-lang`` is refused. A second ``-lang``, including another
    ``cpp``, is refused.
    """
    if not isinstance(command, list) or not command or type(command[0]) is not str:
        return False
    if command[0] != "faust":
        return False
    if any(type(item) is not str for item in command):
        return False
    if any(item == "libfaust-wasm" or item.startswith("--faustwasm=") for item in command):
        return False
    seen_lang = False
    index = 0
    while index < len(command):
        item = command[index]
        if item != "-lang":
            index += 1
            continue
        if seen_lang or index + 1 >= len(command) or command[index + 1] != "cpp":
            return False
        seen_lang = True
        index += 2
    return seen_lang


def shadow_observe(
    envelope: Mapping[str, Any],
    *,
    diagnostics: str | None = None,
    rerun: Rerun | None = None,
    known_good: KnownGood | None = None,
    native: Mapping[str, Any] | None = None,
    native_diagnostics: str | None = None,
) -> ShadowLog:
    """Log an A2-T observation. This does not grade.

    The rerun and fixture hooks may run here. Their results are text
    on the log. This function does not mint a receipt, does not call
    ``grade_receipt``, and does not return a value ``reward_value``
    accepts.
    """
    if not isinstance(envelope, Mapping):
        raise RewardProvenanceError("shadow observe requires an envelope")
    payload = envelope.get("payload")
    notes: list[str] = []
    if rerun is not None:
        outcome = rerun(dict(payload) if isinstance(payload, dict) else {})
        notes.append(f"rerun failed={getattr(outcome, 'failed', None)}")
    if known_good is not None:
        fixture = known_good()
        notes.append(f"fixture passed={getattr(fixture, 'passed', None)}")
    wasm_line = _exact_stack_line(diagnostics) if isinstance(diagnostics, str) else None
    matched = wasm_line is not None and _native_stack_match(
        payload if isinstance(payload, Mapping) else {},
        native,
        wasm_line,
    )
    if native is not None or native_diagnostics is not None:
        notes.append("native Faust 2.88.0 stack match" if matched else "native match absent")
    detail = "; ".join(notes) if notes else "logged, not graded"
    return ShadowLog(signature=_shadow_signature(payload, diagnostics), detail=detail)


def _shadow_signature(payload: object, diagnostics: str | None) -> str:
    """Name the observed signature. This name is not a reward."""
    if isinstance(payload, Mapping):
        if payload.get("runtime_stack_overflow") is True:
            return "runtime_stack_overflow"
        trap = payload.get("wasm_trap")
        if isinstance(trap, str) and trap != "":
            return "wasm_trap"
        exit_code = payload.get("exit_code")
        if exit_code in (124, 125, 126):
            if isinstance(diagnostics, str) and _compile_stack_line(diagnostics):
                return "stack_line"
            return f"exit_{exit_code}"
    if isinstance(diagnostics, str) and _compile_stack_line(diagnostics):
        return "stack_line"
    return "unspecified"


def _grade(
    envelope: Mapping[str, Any],
    *,
    diagnostics: str | None,
    triage: object,
    task: object,
    native: Mapping[str, Any] | None,
    native_diagnostics: str | None,
) -> Grade:
    if not isinstance(envelope, Mapping):
        return Ungraded(UngradedReason.SCHEMA_INVALID, "envelope is not an object")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        return Ungraded(UngradedReason.SCHEMA_INVALID, "payload is not an object")
    if _unknown_envelope_fields(envelope):
        return Ungraded(UngradedReason.SCHEMA_INVALID, "envelope has a field outside the artifact schema")
    try:
        validate(dict(envelope), "artifact-envelope.schema.json")
    except SchemaValidationError as exc:
        return Ungraded(UngradedReason.SCHEMA_INVALID, exc.detail)
    if _is_crash(payload):
        return _grade_crash(
            envelope,
            payload,
            diagnostics=diagnostics,
            triage=triage,
        )
    if "exit_code" in payload and "passed" not in payload:
        return _grade_compiler(
            envelope,
            payload,
            diagnostics=diagnostics,
            triage=triage,
            native=native,
            native_diagnostics=native_diagnostics,
        )
    return _grade_signal(envelope, payload, task=task)


def _grade_signal(
    envelope: Mapping[str, Any], payload: dict[str, Any], *, task: object
) -> Grade:
    version = envelope.get("schema_version")
    if version not in ACCEPTED_SIGNAL_SCHEMA_VERSIONS:
        return Ungraded(
            UngradedReason.SCHEMA_VERSION_UNSUPPORTED,
            f"schema_version {version!r} is not in the signal allowlist",
        )
    try:
        validate(payload, "dsp-test-receipt.schema.json")
    except SchemaValidationError as exc:
        return Ungraded(UngradedReason.SCHEMA_INVALID, exc.detail)
    if _envelope_digest_mismatch(envelope, payload):
        return Ungraded(UngradedReason.DIGEST_MISMATCH, "envelope digest does not match the payload")
    purpose = payload.get("purpose")
    thresholds = payload.get("thresholds")
    reward_bit = thresholds.get("reward_graded") if isinstance(thresholds, dict) else None
    if purpose != "reward" or reward_bit is not True:
        return Ungraded(
            UngradedReason.NOT_REWARD_GRADED,
            "diagnostic receipts are not a reward",
        )
    profile = payload.get("profile")
    metrics = payload.get("metrics")
    if not isinstance(profile, dict) or not isinstance(metrics, dict) or not isinstance(thresholds, dict):
        return Ungraded(UngradedReason.SCHEMA_INVALID, "reward receipt is missing profile, metrics or thresholds")
    if not _comparison_is_full(payload, profile, metrics):
        return Ungraded(
            UngradedReason.COMPARISON_NOT_FULL,
            "reward comparison must sign the whole render up to max_frames",
        )
    try:
        validate(payload, "dsp-reward-receipt.schema.json")
    except SchemaValidationError as exc:
        return Ungraded(UngradedReason.SCHEMA_INVALID, exc.detail)
    suite = payload.get("test_suite_digest")
    recomputed_suite = content_digest_for(profile)
    if suite != recomputed_suite:
        return Ungraded(
            UngradedReason.DIGEST_MISMATCH,
            "test_suite_digest does not match the stored profile",
        )
    if not _thresholds_match(profile, thresholds):
        return Ungraded(
            UngradedReason.DIGEST_MISMATCH,
            "thresholds do not match the digested profile",
        )
    if not _identity_matches(payload, profile, metrics):
        return Ungraded(
            UngradedReason.DIGEST_MISMATCH,
            "receipt identity does not match the digested profile",
        )
    # Recomputed so a later reader does not trust a stored copy.
    reproducible = reproducible_signal_digest(payload)
    allowlist = reward_profiles()
    name = allowlist.get(recomputed_suite)
    if name is None:
        return Ungraded(
            UngradedReason.PROFILE_NOT_ALLOWLISTED,
            "profile digest is not in REWARD_PROFILES",
        )
    passed = payload.get("passed")
    if type(passed) is not bool:
        return Ungraded(UngradedReason.SCHEMA_INVALID, "passed is not a boolean")
    failures = metrics.get("failures")
    if not isinstance(failures, list) or any(type(item) is not str for item in failures):
        return Ungraded(
            UngradedReason.DIGEST_MISMATCH,
            "passed does not match failures",
        )
    # ``passed`` is the graded bit. It is true only when nothing failed.
    if passed is not (failures == []):
        return Ungraded(
            UngradedReason.DIGEST_MISMATCH,
            "passed does not match failures",
        )
    binding, full = _task_digests_for_mint(task)
    return _mint_receipt(
        passed=passed,
        profile_name=name,
        test_suite_digest=recomputed_suite,
        reproducible_digest=reproducible,
        schema_version=str(version),
        task_digest=binding,
        task_digest_full=full,
        unrewardable=_task_marks_unrewardable(task),
    )


def _mint_receipt(
    *,
    passed: bool,
    profile_name: str,
    test_suite_digest: str,
    reproducible_digest: str,
    schema_version: str,
    task_digest: str | None,
    task_digest_full: str | None,
    unrewardable: bool,
) -> RewardableSignalReceipt:
    """Register one receipt. The class ``_mint`` method always refuses."""
    receipt = object.__new__(RewardableSignalReceipt)
    object.__setattr__(receipt, "passed", passed)
    object.__setattr__(receipt, "profile_name", profile_name)
    object.__setattr__(receipt, "test_suite_digest", test_suite_digest)
    object.__setattr__(receipt, "reproducible_digest", reproducible_digest)
    object.__setattr__(receipt, "schema_version", schema_version)
    object.__setattr__(receipt, "task_digest", task_digest)
    object.__setattr__(receipt, "task_digest_full", task_digest_full)
    object.__setattr__(receipt, "unrewardable", unrewardable)
    return receipt


grade_receipt, is_minted = _bind_grade_receipt(grade_receipt)


def _comparison_is_full(
    payload: Mapping[str, Any], profile: Mapping[str, Any], metrics: Mapping[str, Any]
) -> bool:
    if metrics.get("comparison") != FULL_COMPARISON:
        return False
    frames = profile.get("frames")
    if not isinstance(frames, int) or isinstance(frames, bool):
        return False
    if profile.get("max_frames") != frames:
        return False
    if metrics.get("frame_count") != frames or metrics.get("signed_frames") != frames:
        return False
    if metrics.get("head_frames") != profile.get("head_frames"):
        return False
    head = profile.get("head_frames")
    if not isinstance(head, int) or isinstance(head, bool) or head < 1 or head > frames:
        return False
    renders = metrics.get("renders")
    if not isinstance(renders, dict) or not renders:
        return False
    for render in renders.values():
        if not isinstance(render, dict) or render.get("compared_frames") != frames:
            return False
    return True


def _thresholds_match(profile: Mapping[str, Any], thresholds: Mapping[str, Any]) -> bool:
    if thresholds.get("reward_graded") is not True:
        return False
    for key in _THRESHOLD_KEYS:
        if thresholds.get(key) != profile.get(key):
            return False
    return True


def _identity_matches(
    payload: Mapping[str, Any], profile: Mapping[str, Any], metrics: Mapping[str, Any]
) -> bool:
    if payload.get("sample_rate") != profile.get("sample_rate"):
        return False
    if payload.get("block_size") != profile.get("block_size"):
        return False
    if payload.get("seed") != profile.get("seed"):
        return False
    return True


def _task_marks_unrewardable(task: object) -> bool:
    """True when ``task`` is not a reward target.

    A task ``grade_receipt`` cannot read stays rewardable here.
    ``apply_signal`` refuses a receipt this marks.
    """
    if not isinstance(task, Mapping):
        return False
    from faustcoder.signal_suite import task_is_unrewardable

    try:
        return task_is_unrewardable(task) is True
    except (TypeError, ValueError):
        return False


def _grade_compiler(
    envelope: Mapping[str, Any],
    payload: dict[str, Any],
    *,
    diagnostics: str | None,
    triage: object,
    native: Mapping[str, Any] | None,
    native_diagnostics: str | None,
) -> Grade:
    version = envelope.get("schema_version")
    if version not in ACCEPTED_COMPILER_SCHEMA_VERSIONS:
        return Ungraded(
            UngradedReason.SCHEMA_VERSION_UNSUPPORTED,
            f"schema_version {version!r} is not in the compiler allowlist",
        )
    try:
        validate(payload, "compiler-receipt.schema.json")
    except SchemaValidationError as exc:
        return Ungraded(UngradedReason.SCHEMA_INVALID, exc.detail)
    if _envelope_digest_mismatch(envelope, payload):
        return Ungraded(UngradedReason.DIGEST_MISMATCH, "envelope digest does not match the payload")
    # The sealed native match carries the stack line. Raw native text is not one.
    del native_diagnostics
    tagged = _source_tag(payload, diagnostics, native=native)
    if tagged == "mismatch":
        return Ungraded(
            UngradedReason.DIGEST_MISMATCH,
            "diagnostics do not match stderr_digest",
        )
    digest = reproducible_receipt_digest(payload)
    # A signal death is not exit 1 and not a source score.
    if "termination_signal" in payload:
        return _unattributed(digest)
    decision = _recorded_triage(triage)
    if tagged in {"remote import", "source size"}:
        if decision is not None and decision.attribution in {
            TriageAttribution.HARNESS,
            TriageAttribution.INFRASTRUCTURE,
        }:
            return _drop_source_score(decision, digest)
        return SourceAttributedFailure(detail=tagged)
    if tagged == "unmatched stack":
        return _unattributed(digest)
    if tagged is not None:
        return SourceAttributedFailure(detail=tagged)
    # A string, or a recorded source decision, does not score. A2-T is
    # not implemented, so the override fails closed.
    exit_code = payload.get("exit_code")
    diagnostic_class = payload.get("diagnostic_class")
    # A compiler receipt killed at 137, 139, or -9 is a crash. It is
    # queued, not schema_invalid, and not scored.
    if exit_code in _SIGNAL_KILL_EXITS:
        return _unattributed(digest)
    if exit_code not in _EXIT_CLASS:
        if diagnostic_class == "parse_error" or exit_code == 1:
            return SourceAttributedFailure(detail="compiler rejection")
        return Ungraded(
            UngradedReason.SCHEMA_INVALID,
            "compiler receipt is not an unattributed 124, 125 or 126",
        )
    if diagnostic_class != _EXIT_CLASS[exit_code]:
        return Ungraded(
            UngradedReason.SCHEMA_INVALID,
            "exit_code does not match diagnostic_class",
        )
    # Exit 124, 125 and an untagged 126 stay ungraded until triage.
    return _unattributed(digest)


def _grade_crash(
    envelope: Mapping[str, Any],
    payload: dict[str, Any],
    *,
    diagnostics: str | None,
    triage: object,
) -> Grade:
    version = envelope.get("schema_version")
    if version not in ACCEPTED_COMPILER_SCHEMA_VERSIONS | ACCEPTED_SIGNAL_SCHEMA_VERSIONS:
        return Ungraded(
            UngradedReason.SCHEMA_VERSION_UNSUPPORTED,
            f"schema_version {version!r} is not in the allowlist",
        )
    if _envelope_digest_mismatch(envelope, payload):
        return Ungraded(UngradedReason.DIGEST_MISMATCH, "envelope digest does not match the payload")
    digest = payload.get("reproducible_digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        return Ungraded(UngradedReason.SCHEMA_INVALID, "crash record has no reproducible digest")
    # A crash is exit 126 internal, or a kill at 137, 139, or -9, until
    # something attributes it. Those kills are not schema_invalid.
    if payload.get("exit_code") not in _CRASH_EXITS:
        return Ungraded(
            UngradedReason.SCHEMA_INVALID,
            "a crash record uses exit 126, 137, 139, or -9",
        )
    if payload.get("diagnostic_class") not in (None, "internal"):
        return Ungraded(
            UngradedReason.SCHEMA_INVALID,
            "a crash is diagnostic_class internal, not a timeout",
        )
    # A2-T is not implemented. A triage string or decision cannot score a crash.
    del triage
    # Render exception text is not a marker source. A stack overflow or
    # wasm trap on this stage stays unattributed: those structured
    # fields are harness-limit signatures, not a compile warning and
    # not harness prose.
    del diagnostics
    return _unattributed(digest)


def _unattributed(digest: str) -> Ungraded:
    """Hold a row until triage. This is not a score."""
    return Ungraded(
        UngradedReason.UNATTRIBUTED,
        "quarantined until triage",
        digest,
    )


def _source_tag(
    payload: Mapping[str, Any],
    diagnostics: str | None,
    *,
    native: object = None,
) -> str | None:
    """Return a source tag, ``mismatch``, ``unmatched stack``, or ``None``.

    Remote import and ``resource limit: source size`` are exact harness
    diagnostics and are already the source. The two Faust stack lines
    are source only with a sealed native Faust 2.88.0 failure of the
    same source and the same line. An exit-1 receipt that carries one
    of those lines without that seal is ``unmatched stack``, not a
    compiler rejection. Harness prose is not scanned. Render exceptions
    are not scanned here. ``runtime_stack_overflow`` and ``wasm_trap``
    are not source tags.
    """
    stderr = payload.get("stderr_digest")
    if stderr == _sha256_text(_REMOTE_DIAGNOSTIC):
        return "remote import"
    if stderr == _sha256_text(_SOURCE_SIZE_DIAGNOSTIC):
        return "source size"
    if diagnostics is None:
        return None
    if _sha256_text(diagnostics) != stderr:
        return "mismatch"
    if diagnostics.startswith(_HARNESS_PREFIXES):
        return None
    exit_code = payload.get("exit_code")
    diagnostic_class = payload.get("diagnostic_class")
    wasm_line = _exact_stack_line(diagnostics)
    # Exit 126 internal is the stored form of the wasm ``in eval`` line.
    # A timeout or a kill stays unattributed even when a native exit 1
    # names the same line.
    if type(exit_code) is int and exit_code == 126 and diagnostic_class == "internal":
        if wasm_line is not None and _native_stack_match(payload, native, wasm_line):
            return "stack overflow"
        return None
    # The plain line is stored as exit 1. It is gradeable only with the
    # sealed native match of an exact int exit. ``1.0`` and an int
    # subclass must not fall through to a compiler rejection.
    if (
        type(exit_code) is not bool
        and exit_code == 1
        and _contains_exact_stack_line(diagnostics)
    ):
        if (
            type(exit_code) is int
            and wasm_line is not None
            and _native_stack_match(payload, native, wasm_line)
        ):
            return "stack overflow"
        return "unmatched stack"
    return None


def _recorded_triage(triage: object) -> TriageDecision | None:
    """Return a complete decision, or None when ``triage`` is not one.

    A string is not a decision. Who, why, and evidence are all required.
    """
    if type(triage) is not TriageDecision:
        return None
    if type(triage.attribution) is not TriageAttribution:
        return None
    if type(triage.triaged_by) is not str or triage.triaged_by.strip() == "":
        return None
    if type(triage.evidence) is not str or triage.evidence.strip() == "":
        return None
    return triage


def _drop_source_score(decision: TriageDecision, digest: str) -> Ungraded:
    """Drop a remote-import or source-size score. This is not a reward."""
    who = decision.triaged_by.strip()
    evidence = decision.evidence.strip()
    if decision.attribution is TriageAttribution.HARNESS:
        return Ungraded(
            UngradedReason.HARNESS_DEFECT,
            f"harness triage by {who}: {evidence}",
            digest,
        )
    return Ungraded(
        UngradedReason.INFRA_FAULT,
        f"infrastructure triage by {who}: {evidence}",
        digest,
    )


def _contains_exact_stack_line(text: str) -> bool:
    """True when one line is exactly a Faust stack-overflow line."""
    return any(line in _COMPILE_STACK_LINES for line in text.split("\n"))


def _native_stack_match(
    payload: Mapping[str, Any],
    native: object,
    wasm_line: str,
) -> bool:
    """True when a sealed native exit 1 names the same stack line and source.

    A raw dict is not a match. The stack-line text must be equal:
    ``ERROR : stack overflow in eval`` does not match
    ``ERROR : stack overflow``.
    """
    if type(native) is not NativeStackMatch or not is_native_minted(native):
        return False
    source = payload.get("source_sha256")
    if type(source) is not str or source == "" or source != native.source_sha256:
        return False
    return native.stack_line == wasm_line


def _exact_stack_line(text: str) -> str | None:
    """The one stack line in ``text``, or None.

    The line must equal ``ERROR : stack overflow`` or
    ``ERROR : stack overflow in eval``. A longer prefix is not that
    line. Two different stack lines are not one line.
    """
    found: str | None = None
    for line in text.split("\n"):
        if line not in _COMPILE_STACK_LINES:
            continue
        if found is not None and found != line:
            return None
        found = line
    return found


def _compile_stack_line(text: str) -> bool:
    """True when a compile diagnostic line starts with Faust's stack error.

    Lines break on ``\\n`` only. NEL (U+0085) and U+2028 stay inside the
    line, so they cannot open a line-start match.
    """
    for line in text.split("\n"):
        if any(line.startswith(prefix) for prefix in _COMPILE_STACK_LINES):
            return True
    return False


def _is_crash(payload: Mapping[str, Any]) -> bool:
    """A crash record is a crash kind, or a bare kill at 137, 139, or -9."""
    if payload.get("kind") in _CRASH_KINDS:
        return True
    return (
        payload.get("exit_code") in _SIGNAL_KILL_EXITS
        and "passed" not in payload
        and "faust_version" not in payload
    )


def _unknown_envelope_fields(envelope: Mapping[str, Any]) -> bool:
    return any(key not in _ENVELOPE_FIELDS for key in envelope)


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _envelope_digest_mismatch(envelope: Mapping[str, Any], payload: Mapping[str, Any]) -> bool:
    digest = content_digest_for(payload)
    if envelope.get("content_digest") != digest:
        return True
    artifact_id = envelope.get("artifact_id")
    return artifact_id != digest.removeprefix("sha256:")


def _account(
    result: Grade,
    *,
    policy: str,
    queue: QuarantineQueue | None,
    rates: UngradedRateTracker | None,
    row_record_id: str = "",
    group_id: str = "",
) -> None:
    quarantined = isinstance(result, Ungraded) and result.reason in QUARANTINE_REASONS
    counted = isinstance(result, Ungraded) and result.reason in _RATE_REASONS
    graded = isinstance(result, (RewardableSignalReceipt, SourceAttributedFailure))
    if rates is not None and (counted or graded):
        rates.observe(policy, ungraded=counted)
    if queue is None or not quarantined or not isinstance(result, Ungraded):
        return
    queue.hold(
        QuarantineRecord(
            policy=policy,
            reason=result.reason,
            reproducible_digest=result.reproducible_digest,
            detail=result.detail,
            row_record_id=row_record_id,
            group_id=group_id,
        )
    )

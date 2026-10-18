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
``Ungraded(unattributed)`` until it is attributed. Exit 126 is
``internal``. Auto-attribution reruns the same reproducible digest
on a quiet worker and runs a known-good fixture alongside. If the
fixture passes and the candidate fails again, the failure is graded
at the A1 ``parse_error`` rung. A remote-import or stack-overflow
tag is already source attribution and does not wait. The rerun and
the fixture are caller hooks: this module does not spawn a worker.

Receipt signing is deferred (D3). This module recomputes digests. It
does not require a signature.

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
from typing import Any
from weakref import WeakKeyDictionary

from faustcoder.canonical import content_digest_for
from faustcoder.compiler import reproducible_receipt_digest
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
_STACK_MARKERS = ("maximum call stack size exceeded", "stack overflow")
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


def reward_profile_allowlist() -> dict[str, str]:
    """Return the frozen ``{digest: name}`` allowlist."""
    return reward_profiles()


class RewardProvenanceError(Exception):
    """A reward-bearing row has no ``RewardableSignalReceipt``."""


class RewardUseRefused(Exception):
    """A reward-graded failure had no ledger, so it was not scored or dropped."""


class RewardOutcomeHeld(Exception):
    """A compiler or crash outcome was graded onto the ledger and is not a score."""

    def __init__(self, grade: Grade) -> None:
        self.grade = grade
        super().__init__("reward outcome is held and is not a score")


def reward_value(result: Grade) -> float | None:
    """Return 1, 0, or ``None`` when the sample is dropped.

    ``Ungraded`` is ``None``. It is not scored 0. A graded signal
    failure and an A1 source failure are 0.
    """
    if isinstance(result, Ungraded):
        return None
    if isinstance(result, SourceAttributedFailure):
        return 0.0
    if isinstance(result, RewardableSignalReceipt):
        return 1.0 if result.passed else 0.0
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
    if type(receipt) is not RewardableSignalReceipt:
        raise RewardProvenanceError(
            "reward-bearing row lacks RewardableSignalReceipt provenance"
        )
    return receipt


def dataset_reward_row(receipt: object, **fields: object) -> dict[str, object]:
    """Build one dataset row. The reward comes only from ``receipt``."""
    graded = require_rewardable_provenance(receipt)
    if "reward" in fields or "provenance" in fields:
        raise RewardProvenanceError("reward and provenance are derived from the receipt")
    row = dict(fields)
    row["reward"] = 1.0 if graded.passed else 0.0
    row["provenance"] = graded
    return row


def rl_batch(rows: list[Mapping[str, object]] | tuple[Mapping[str, object], ...]) -> tuple[dict[str, object], ...]:
    """Copy ``rows`` after every reward row proves its provenance."""
    built: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping) or "reward" not in row:
            raise RewardProvenanceError("RL batch row is missing a reward")
        graded = require_rewardable_provenance(row.get("provenance"))
        reward = _finite_reward(row.get("reward"))
        # Pending Danny's binary-versus-lowest-rung ruling. Until that
        # lands, a passed receipt is exactly 1.0 and a failed receipt is exactly 0.0.
        if graded.passed:
            if reward != 1.0:
                raise RewardProvenanceError("reward must be 1.0 when the receipt passed")
        elif reward != 0.0:
            raise RewardProvenanceError("reward must be zero when the receipt failed")
        built.append(dict(row))
    return tuple(built)


def _finite_reward(reward: object) -> float:
    """Return a finite float reward. Bools, strings and ints are refused."""
    if isinstance(reward, bool) or not isinstance(reward, float) or not math.isfinite(reward):
        raise RewardProvenanceError("reward must be a finite float")
    return reward


def grade_receipt(
    envelope: Mapping[str, Any],
    *,
    diagnostics: str | None = None,
    rerun: Rerun | None = None,
    known_good: KnownGood | None = None,
    triage: str | None = None,
    policy: str = "default",
    queue: QuarantineQueue | None = None,
    rates: UngradedRateTracker | None = None,
) -> Grade:
    """Grade one stored envelope.

    A DSP receipt becomes ``RewardableSignalReceipt`` or ``Ungraded``.
    A compiler receipt at exit 124, 125 or 126, or a worker or harness
    crash, is auto-attributed when ``rerun`` and ``known_good`` are
    supplied. ``rerun`` must use the same reproducible digest on a
    quiet worker. ``known_good`` is the fixture that runs alongside.
    Without those hooks the row stays ``unattributed`` and, when
    ``queue`` is set, pending.
    """
    result = _grade(
        envelope,
        diagnostics=diagnostics,
        rerun=rerun,
        known_good=known_good,
        triage=triage,
    )
    _account(result, policy=policy, queue=queue, rates=rates)
    return result


def _bind_grade_receipt(grade: Callable[..., Grade]) -> tuple[
    Callable[..., Grade],
    Callable[[object], bool],
]:
    """Seal receipts inside ``grade`` so the registry is not a module global.

    The seal closes over a nonce and the object's identity. A lookalike
    built with the same five fields is a different object and is rejected.
    """
    registry: WeakKeyDictionary[RewardableSignalReceipt, tuple[object, ...]] = (
        WeakKeyDictionary()
    )
    token = object()

    def is_minted(receipt: object) -> bool:
        if type(receipt) is not RewardableSignalReceipt:
            return False
        row = registry.get(receipt)
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
        triage: str | None = None,
        policy: str = "default",
        queue: QuarantineQueue | None = None,
        rates: UngradedRateTracker | None = None,
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
        )
        if isinstance(result, RewardableSignalReceipt):
            registry[result] = (id(result), token, result._snapshot())
        return result

    return grade_receipt, is_minted


def _grade(
    envelope: Mapping[str, Any],
    *,
    diagnostics: str | None,
    rerun: Rerun | None,
    known_good: KnownGood | None,
    triage: str | None,
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
            rerun=rerun,
            known_good=known_good,
            triage=triage,
        )
    if "exit_code" in payload and "passed" not in payload:
        return _grade_compiler(
            envelope,
            payload,
            diagnostics=diagnostics,
            rerun=rerun,
            known_good=known_good,
            triage=triage,
        )
    return _grade_signal(envelope, payload)


def _grade_signal(envelope: Mapping[str, Any], payload: dict[str, Any]) -> Grade:
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
    if not isinstance(passed, bool):
        return Ungraded(UngradedReason.SCHEMA_INVALID, "passed is not a boolean")
    return _mint_receipt(
        passed=passed,
        profile_name=name,
        test_suite_digest=recomputed_suite,
        reproducible_digest=reproducible,
        schema_version=str(version),
    )


def _mint_receipt(
    *,
    passed: bool,
    profile_name: str,
    test_suite_digest: str,
    reproducible_digest: str,
    schema_version: str,
) -> RewardableSignalReceipt:
    """Register one receipt. The class ``_mint`` method always refuses."""
    receipt = object.__new__(RewardableSignalReceipt)
    object.__setattr__(receipt, "passed", passed)
    object.__setattr__(receipt, "profile_name", profile_name)
    object.__setattr__(receipt, "test_suite_digest", test_suite_digest)
    object.__setattr__(receipt, "reproducible_digest", reproducible_digest)
    object.__setattr__(receipt, "schema_version", schema_version)
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


def _grade_compiler(
    envelope: Mapping[str, Any],
    payload: dict[str, Any],
    *,
    diagnostics: str | None,
    rerun: Rerun | None,
    known_good: KnownGood | None,
    triage: str | None,
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
    tagged = _source_tag(payload, diagnostics)
    if tagged == "mismatch":
        return Ungraded(
            UngradedReason.DIGEST_MISMATCH,
            "diagnostics do not match stderr_digest",
        )
    if tagged is not None:
        return SourceAttributedFailure(detail=tagged)
    if triage == "source":
        return SourceAttributedFailure(detail="triage attributed the failure to the source")
    digest = reproducible_receipt_digest(payload)
    if triage == "harness":
        return Ungraded(
            UngradedReason.HARNESS_DEFECT,
            "triage established a deterministic harness defect",
            digest,
        )
    if triage == "infra":
        return Ungraded(
            UngradedReason.INFRA_FAULT,
            "triage established a reproducible infrastructure failure",
            digest,
        )
    if triage not in (None,):
        return Ungraded(UngradedReason.SCHEMA_INVALID, "triage is not source, harness or infra")
    exit_code = payload.get("exit_code")
    diagnostic_class = payload.get("diagnostic_class")
    # A compiler receipt killed at 137, 139, or -9 is a crash. It is
    # queued, not schema_invalid.
    if exit_code in _SIGNAL_KILL_EXITS:
        return _auto_attribute(digest, rerun=rerun, known_good=known_good)
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
    return _auto_attribute(digest, rerun=rerun, known_good=known_good)


def _grade_crash(
    envelope: Mapping[str, Any],
    payload: dict[str, Any],
    *,
    rerun: Rerun | None,
    known_good: KnownGood | None,
    triage: str | None,
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
    if triage == "source":
        return SourceAttributedFailure(detail="triage attributed the crash to the source")
    if triage == "harness":
        return Ungraded(
            UngradedReason.HARNESS_DEFECT,
            "triage established a deterministic harness defect",
            digest,
        )
    if triage == "infra":
        return Ungraded(
            UngradedReason.INFRA_FAULT,
            "triage established a reproducible infrastructure failure",
            digest,
        )
    if triage not in (None,):
        return Ungraded(UngradedReason.SCHEMA_INVALID, "triage is not source, harness or infra")
    return _auto_attribute(digest, rerun=rerun, known_good=known_good)


def _auto_attribute(
    digest: str,
    *,
    rerun: Rerun | None,
    known_good: KnownGood | None,
) -> Grade:
    """Rerun on a quiet worker. Source only if the fixture stays healthy."""
    if rerun is None or known_good is None:
        return Ungraded(
            UngradedReason.UNATTRIBUTED,
            "quarantined until triage",
            digest,
        )
    outcome = rerun({"reproducible_digest": digest})
    fixture = known_good()
    if not isinstance(outcome, RerunOutcome) or not isinstance(fixture, FixtureOutcome):
        return Ungraded(UngradedReason.SCHEMA_INVALID, "rerun or fixture returned an unexpected type")
    if outcome.reproducible_digest != digest:
        return Ungraded(
            UngradedReason.UNATTRIBUTED,
            "rerun digest does not match the original receipt",
            digest,
        )
    rerun_env = _present_digest(outcome.environment_digest)
    fixture_env = _present_digest(fixture.environment_digest)
    if rerun_env is None or fixture_env is None or rerun_env != fixture_env:
        return Ungraded(
            UngradedReason.UNATTRIBUTED,
            "rerun and known-good fixture do not share an environment digest",
            digest,
        )
    if fixture.passed and outcome.failed:
        return SourceAttributedFailure(
            detail="auto-attributed: known-good fixture passed and the candidate failed again"
        )
    if not fixture.passed:
        return Ungraded(
            UngradedReason.INFRA_FAULT,
            "known-good fixture failed under the same harness",
            digest,
        )
    return Ungraded(
        UngradedReason.UNATTRIBUTED,
        "candidate did not fail again; quarantined until triage",
        digest,
    )


def _source_tag(payload: Mapping[str, Any], diagnostics: str | None) -> str | None:
    """Return a source tag, ``mismatch``, or ``None``.

    Remote import is tagged by the harness diagnostic
    ``internal: remote import rejected``. Stack overflow is tagged
    when the diagnostics that hash to ``stderr_digest`` contain that
    marker. Both are already attributed to the source.
    """
    stderr = payload.get("stderr_digest")
    if stderr == _sha256_text(_REMOTE_DIAGNOSTIC):
        return "remote import"
    if diagnostics is None:
        return None
    if _sha256_text(diagnostics) != stderr:
        return "mismatch"
    folded = diagnostics.casefold()
    if "remote import rejected" in folded:
        return "remote import"
    if any(marker in folded for marker in _STACK_MARKERS):
        return "stack overflow"
    return None


def _present_digest(value: object) -> str | None:
    """Return a non-empty digest, or None when it is missing or blank."""
    if isinstance(value, str) and value.strip():
        return value
    return None


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
        )
    )

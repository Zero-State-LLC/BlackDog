"""Sampled rerun-from-source audit (D3-H2), before P3.

Every passing row, a deterministic 5% sample of failing rows, and every
canary are rerun from source. A disagreement leaves that row ungraded,
drops its whole group, and halts P3. The seed and the sample ids are
part of the machine-readable report. A row that fails the H1 HMAC check
is refused before any rerun. A stored pass or fail is not rewritten.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass

from faustcoder.canonical import canonical_bytes
from faustcoder.reward.records import (
    ConsumedLog,
    RewardKeyring,
    RewardRecordError,
    RewardRowRecord,
    verify,
)

_SAMPLE_PERCENT = 5


@dataclass(frozen=True)
class AuditDisagreement:
    """One rerun that did not match the stored outcome."""

    record_id: str
    group_id: str
    stored_outcome: str
    rerun_outcome: str


@dataclass(frozen=True)
class RerunAudit:
    """The audit result. ``halted`` means P3 does not proceed."""

    seed: str
    sample_ids: tuple[str, ...]
    audited_ids: tuple[str, ...]
    disagreements: tuple[AuditDisagreement, ...]
    dropped_groups: tuple[str, ...]
    ungraded_ids: tuple[str, ...]
    kept_ids: tuple[str, ...]
    halted: bool

    def report(self) -> dict[str, object]:
        """Machine-readable report. ``p3`` is ``halt`` or ``clear``."""
        return {
            "audited_ids": list(self.audited_ids),
            "disagreements": [
                {
                    "group_id": item.group_id,
                    "record_id": item.record_id,
                    "rerun_outcome": item.rerun_outcome,
                    "row": "ungraded",
                    "stored_outcome": item.stored_outcome,
                }
                for item in self.disagreements
            ],
            "dropped_groups": list(self.dropped_groups),
            "halted": self.halted,
            "kept_ids": list(self.kept_ids),
            "p3": "halt" if self.halted else "clear",
            "sample_ids": list(self.sample_ids),
            "seed": self.seed,
            "ungraded_ids": list(self.ungraded_ids),
        }

    def canonical_report(self) -> bytes:
        return canonical_bytes(self.report())


def p3_may_proceed(audit: RerunAudit) -> bool:
    """False when the audit halted P3."""
    return audit.report()["p3"] == "clear" and not audit.halted and audit.disagreements == ()


def select_fail_sample(record_ids: Sequence[str], seed: str) -> tuple[str, ...]:
    """First floor(5%) of the unique ``record_ids``, ordered by SHA-256(seed, id).

    The order does not depend on the input order. The same seed and the
    same ids always return the same sample.
    """
    _require_seed(seed)
    ordered = tuple(sorted(set(_require_ids(record_ids))))
    ranked = sorted(ordered, key=lambda record_id: _sample_key(seed, record_id))
    count = (len(ranked) * _SAMPLE_PERCENT) // 100
    return tuple(ranked[:count])


def audit_sampled_reruns(
    records: Sequence[RewardRowRecord],
    keyring: RewardKeyring,
    *,
    seed: str,
    rerun: Callable[[RewardRowRecord], str],
    consumed: ConsumedLog,
    canary_ids: Collection[str] = (),
) -> RerunAudit:
    """Rerun the pass set, the fail sample, and every canary from source.

    ``rerun`` receives the stored row, including its source bytes, and
    returns the outcome it observed. HMAC verification runs first. A
    failure there raises and does not call ``rerun``. A stored outcome
    is not rewritten when the rerun disagrees.
    """
    _require_seed(seed)
    rows = tuple(records)
    _refuse_bad_hmac(rows, keyring)
    canaries = frozenset(_require_ids(tuple(canary_ids)))
    known = {row.record_id for row in rows}
    missing = sorted(canaries - known)
    if missing:
        raise RewardRecordError("audit canary is not in the rows")
    fails = tuple(row.record_id for row in rows if row.outcome == "fail")
    sample = select_fail_sample(fails, seed)
    selected = set(sample)
    selected.update(row.record_id for row in rows if row.outcome == "pass")
    selected.update(canaries)
    audited = tuple(row.record_id for row in rows if row.record_id in selected)
    disagreements: list[AuditDisagreement] = []
    for row in rows:
        if row.record_id not in selected:
            continue
        observed = rerun(row)
        if type(observed) is not str or observed != row.outcome:
            disagreements.append(
                AuditDisagreement(
                    record_id=row.record_id,
                    group_id=row.group_id,
                    stored_outcome=row.outcome,
                    rerun_outcome=observed if type(observed) is str else "",
                )
            )
    dropped = tuple(sorted({item.group_id for item in disagreements}))
    for group_id in dropped:
        _claim_dropped(consumed, rows, group_id)
    dropped_set = set(dropped)
    ungraded = tuple(item.record_id for item in disagreements)
    kept = tuple(row.record_id for row in rows if row.group_id not in dropped_set)
    halted = len(disagreements) > 0
    return RerunAudit(
        seed=seed,
        sample_ids=sample,
        audited_ids=audited,
        disagreements=tuple(disagreements),
        dropped_groups=dropped,
        ungraded_ids=ungraded,
        kept_ids=kept,
        halted=halted,
    )


def _require_seed(seed: str) -> None:
    if type(seed) is not str or seed == "":
        raise RewardRecordError("audit seed is not usable")
    try:
        seed.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise RewardRecordError("audit seed is not usable") from exc


def _require_ids(record_ids: Sequence[str]) -> tuple[str, ...]:
    found: list[str] = []
    for record_id in record_ids:
        if type(record_id) is not str or record_id == "":
            raise RewardRecordError("audit record id is not usable")
        found.append(record_id)
    return tuple(found)


def _sample_key(seed: str, record_id: str) -> bytes:
    return hashlib.sha256(seed.encode("utf-8") + b"\0" + record_id.encode("utf-8")).digest()


def _refuse_bad_hmac(rows: tuple[RewardRowRecord, ...], keyring: RewardKeyring) -> None:
    for row in rows:
        try:
            verify(row, keyring)
        except RewardRecordError as exc:
            raise RewardRecordError("audit refused a row that failed the HMAC check") from exc


def _claim_dropped(
    consumed: ConsumedLog,
    rows: tuple[RewardRowRecord, ...],
    group_id: str,
) -> None:
    row = next(item for item in rows if item.group_id == group_id)
    try:
        consumed.claim(
            group_id,
            "dropped:audit",
            task_digest_full=row.task_digest_full,
            policy_checkpoint=row.policy_checkpoint,
        )
    except RewardRecordError as exc:
        if "already consumed" not in str(exc):
            raise

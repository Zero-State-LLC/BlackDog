"""Sampled rerun-from-source audit (D3-H2, spec §26 0.3.9), before P3.

Every passing row, a ceil(5%) sample of graded 0.0 rows, and every signed
canary are rerun from source. The seed is HMAC-SHA256 of the run key and
``d3-h2-seed`` plus the run id. Any other seed is refused. A disagreement
leaves that row ungraded, drops its group, and persists a halt. P3 reads
that report and does not start while the latest one is not clear.
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from faustcoder.canonical import CanonicalError, canonical_bytes, loads_strict
from faustcoder.reward.records import (
    ConsumedLog,
    RewardGroupConsumed,
    RewardKeyError,
    RewardKeyring,
    RewardRecordError,
    RewardRowRecord,
    _fsync_dir,
    _open_consumed,
    _read_text,
    _write_all,
    verify,
)

_SAMPLE_PERCENT = 5
_SEED_LABEL = b"d3-h2-seed"
_REPORT_DOMAIN = b"faustcoder.reward-audit-report.v1"
_FAIL_OUTCOMES = frozenset({"fail", "source_attributed"})
_LOG_MODE = 0o640


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

    run_id: str
    seed: str
    sample_ids: tuple[str, ...]
    audited_ids: tuple[str, ...]
    disagreements: tuple[AuditDisagreement, ...]
    dropped_groups: tuple[str, ...]
    late_groups: tuple[str, ...]
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
            "late_groups": [
                {"disposition": "late", "group_id": group_id} for group_id in self.late_groups
            ],
            "p3": "halt" if self.halted else "clear",
            "run_id": self.run_id,
            "sample_ids": list(self.sample_ids),
            "seed": self.seed,
            "ungraded_ids": list(self.ungraded_ids),
        }

    def canonical_report(self) -> bytes:
        return canonical_bytes(self.report())


class AuditReportLog:
    """Append-only MAC'd audit reports for one run.

    The file sits next to the consumed log. A halt stays until human
    triage is recorded against each disagreement. A later clear report
    does not replace it.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def append(self, keyring: RewardKeyring, report: Mapping[str, object]) -> None:
        """Persist ``report``. A clear report cannot cover an open halt."""
        run_key = _run_key(keyring)
        body = _report_body(keyring.run_id, report)
        self._append_line(run_key, body)

    def record_triage(
        self,
        keyring: RewardKeyring,
        *,
        record_id: str,
        triaged_by: str,
        triaged_at: str,
    ) -> None:
        """Record human triage for one disagreement. This is the only clear."""
        if type(record_id) is not str or record_id == "":
            raise RewardRecordError("audit triage record id is not usable")
        if type(triaged_by) is not str or triaged_by == "" or "\n" in triaged_by:
            raise RewardRecordError("audit triage actor is not usable")
        if type(triaged_at) is not str or triaged_at == "" or "\n" in triaged_at:
            raise RewardRecordError("audit triage time is not usable")
        lines = self._verified(keyring)
        open_ids = _halt_ids(lines)
        if record_id not in open_ids:
            raise RewardRecordError("audit triage does not match a disagreement")
        if record_id in _triaged_ids(lines):
            return
        self._append_line(
            _run_key(keyring),
            {
                "record_id": record_id,
                "run_id": keyring.run_id,
                "triaged_at": triaged_at,
                "triaged_by": triaged_by,
                "type": "audit_triage",
            },
        )

    def _verified(self, keyring: RewardKeyring) -> tuple[dict[str, object], ...]:
        if not self.path.is_file():
            return ()
        fd = os.open(self.path, os.O_RDONLY | os.O_CLOEXEC)
        try:
            text = _read_text(fd)
        finally:
            os.close(fd)
        if text == "":
            raise RewardRecordError("audit report log is not usable")
        run_key = _run_key(keyring)
        found: list[dict[str, object]] = []
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                body = loads_strict(line)
            except CanonicalError as exc:
                raise RewardRecordError(f"audit report log line {number} is corrupt") from exc
            if not isinstance(body, dict):
                raise RewardRecordError(f"audit report log line {number} is corrupt")
            _verify_line(body, run_key, keyring.run_id)
            found.append(body)
        if not found:
            raise RewardRecordError("audit report log is not usable")
        return tuple(found)

    def _append_line(self, run_key: bytes, body: dict[str, object]) -> None:
        signed = dict(body)
        signed["mac"] = _line_mac(run_key, body)
        encoded = canonical_bytes(signed) + b"\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, created = _open_consumed(self.path)
        try:
            os.fchmod(fd, _LOG_MODE)
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                existing = _read_text(fd)
                if existing.strip():
                    _reject_tamper(existing, run_key)
                    if body.get("type") == "audit_report":
                        report = body.get("report")
                        if (
                            isinstance(report, dict)
                            and report.get("p3") == "clear"
                            and _untriaged(_bodies(existing, run_key))
                        ):
                            raise RewardRecordError("audit halt is not cleared by another report")
                _write_all(fd, encoded)
                os.fsync(fd)
                if created:
                    _fsync_dir(self.path.parent)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def derive_audit_seed(keyring: RewardKeyring, run_id: str) -> str:
    """HMAC-SHA256(run key, ``d3-h2-seed`` || run id). Not a caller choice."""
    if not isinstance(keyring, RewardKeyring):
        raise RewardKeyError("audit seed requires a keyring")
    if type(run_id) is not str or run_id != keyring.run_id:
        raise RewardRecordError("audit seed run id does not match")
    try:
        message = _SEED_LABEL + run_id.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RewardRecordError("audit seed run id does not match") from exc
    return hmac.new(keyring.run_key(run_id), message, hashlib.sha256).hexdigest()


def p3_may_proceed(run_id: str, *, keyring: RewardKeyring, reports: AuditReportLog) -> bool:
    """True only when this run's latest persisted report is clear.

    An open halt stays closed until triage is recorded for each
    disagreement. A missing report is not clear. A bad MAC raises.
    """
    if not isinstance(reports, AuditReportLog):
        raise RewardRecordError("P3 requires the persisted audit report")
    if not isinstance(keyring, RewardKeyring) or type(run_id) is not str or keyring.run_id != run_id:
        raise RewardRecordError("audit report run id does not match")
    if not reports.path.is_file():
        return False
    lines = reports._verified(keyring)
    if _untriaged(lines):
        return False
    latest = _latest_report(lines)
    if latest is None:
        return False
    if latest.get("p3") == "clear":
        return True
    return _halt_ids(lines) <= _triaged_ids(lines)


def select_fail_sample(record_ids: Sequence[str], seed: str) -> tuple[str, ...]:
    """First ceil(5%) of the unique ``record_ids``, ordered by SHA-256(seed, id).

    When ``record_ids`` is not empty the sample has at least one id.
    The order does not depend on the input order.
    """
    _require_seed(seed)
    ordered = tuple(sorted(set(_require_ids(record_ids))))
    ranked = sorted(ordered, key=lambda record_id: _sample_key(seed, record_id))
    count = _sample_count(len(ranked))
    return tuple(ranked[:count])


def audit_sampled_reruns(
    records: Sequence[RewardRowRecord],
    keyring: RewardKeyring,
    *,
    rerun: Callable[[RewardRowRecord], str],
    consumed: ConsumedLog,
    reports: AuditReportLog,
    seed: str | None = None,
    canary_ids: Collection[str] | None = None,
) -> RerunAudit:
    """Rerun the pass set, the fail sample, and every signed canary.

    ``seed``, when passed, must be the derived run seed. ``canary_ids``,
    when passed, must equal the signed canary set. HMAC verification runs
    before any rerun. The report is persisted before return.
    """
    if not isinstance(keyring, RewardKeyring):
        raise RewardKeyError("audit requires a keyring")
    if not isinstance(reports, AuditReportLog):
        raise RewardRecordError("audit requires a report log")
    if not isinstance(consumed, ConsumedLog):
        raise RewardRecordError("audit requires a consumed log")
    derived = derive_audit_seed(keyring, keyring.run_id)
    _require_matching_seed(seed, derived)
    rows = tuple(records)
    _refuse_bad_hmac(rows, keyring)
    signed_canaries = frozenset(row.record_id for row in rows if row.canary is True)
    _require_canary_set(canary_ids, signed_canaries)
    fails = tuple(row.record_id for row in rows if row.outcome in _FAIL_OUTCOMES)
    sample = select_fail_sample(fails, derived)
    selected = set(sample)
    selected.update(row.record_id for row in rows if row.outcome == "pass")
    selected.update(signed_canaries)
    audited = tuple(row.record_id for row in rows if row.record_id in selected)
    disagreements: list[AuditDisagreement] = []
    claimed: dict[str, str] = {}
    try:
        for row in rows:
            if row.record_id not in selected:
                continue
            observed = _observe(rerun, row)
            if type(observed) is str and observed == row.outcome:
                continue
            disagreements.append(
                AuditDisagreement(
                    record_id=row.record_id,
                    group_id=row.group_id,
                    stored_outcome=row.outcome,
                    rerun_outcome=observed if type(observed) is str else "",
                )
            )
            if row.group_id not in claimed:
                claimed[row.group_id] = _claim_dropped(consumed, rows, row.group_id)
    except RewardGroupConsumed:
        _persist(reports, keyring, _audit_from(keyring.run_id, derived, sample, audited, disagreements, claimed, rows))
        raise
    audit = _audit_from(keyring.run_id, derived, sample, audited, disagreements, claimed, rows)
    _persist(reports, keyring, audit)
    return audit


def _audit_from(
    run_id: str,
    seed: str,
    sample: tuple[str, ...],
    audited: tuple[str, ...],
    disagreements: list[AuditDisagreement],
    claimed: dict[str, str],
    rows: tuple[RewardRowRecord, ...],
) -> RerunAudit:
    dropped = tuple(sorted(group_id for group_id, status in claimed.items() if status == "dropped"))
    late = tuple(sorted(group_id for group_id, status in claimed.items() if status == "late"))
    blocked = set(dropped) | set(late)
    halted = len(disagreements) > 0
    return RerunAudit(
        run_id=run_id,
        seed=seed,
        sample_ids=sample,
        audited_ids=audited,
        disagreements=tuple(disagreements),
        dropped_groups=dropped,
        late_groups=late,
        ungraded_ids=tuple(item.record_id for item in disagreements),
        kept_ids=tuple(row.record_id for row in rows if row.group_id not in blocked),
        halted=halted,
    )


def _persist(reports: AuditReportLog, keyring: RewardKeyring, audit: RerunAudit) -> None:
    reports.append(keyring, audit.report())


def _observe(rerun: Callable[[RewardRowRecord], str], row: RewardRowRecord) -> object:
    try:
        return rerun(row)
    except Exception:
        return None


def _sample_count(count: int) -> int:
    if count <= 0:
        return 0
    return (count * _SAMPLE_PERCENT + 99) // 100


def _require_seed(seed: str) -> None:
    if type(seed) is not str or seed == "":
        raise RewardRecordError("audit seed is not usable")
    try:
        seed.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise RewardRecordError("audit seed is not usable") from exc


def _require_matching_seed(seed: str | None, derived: str) -> None:
    if seed is None:
        return
    if type(seed) is not str or len(seed) != len(derived) or not hmac.compare_digest(seed, derived):
        raise RewardRecordError("audit seed does not match the run")


def _require_ids(record_ids: Sequence[str]) -> tuple[str, ...]:
    found: list[str] = []
    for record_id in record_ids:
        if type(record_id) is not str or record_id == "":
            raise RewardRecordError("audit record id is not usable")
        found.append(record_id)
    return tuple(found)


def _require_canary_set(canary_ids: Collection[str] | None, signed: frozenset[str]) -> None:
    if canary_ids is None:
        return
    presented = frozenset(_require_ids(tuple(canary_ids)))
    if presented != signed:
        raise RewardRecordError("audit canary list does not match the signed rows")


def _sample_key(seed: str, record_id: str) -> bytes:
    return hashlib.sha256(seed.encode("utf-8") + b"\0" + record_id.encode("utf-8")).digest()


def _refuse_bad_hmac(rows: tuple[RewardRowRecord, ...], keyring: RewardKeyring) -> None:
    for row in rows:
        if row.run_id != keyring.run_id:
            raise RewardRecordError("audit refused a row that failed the HMAC check")
        try:
            verify(row, keyring)
        except RewardRecordError as exc:
            raise RewardRecordError("audit refused a row that failed the HMAC check") from exc


def _claim_dropped(
    consumed: ConsumedLog,
    rows: tuple[RewardRowRecord, ...],
    group_id: str,
) -> str:
    row = next(item for item in rows if item.group_id == group_id)
    try:
        consumed.claim(
            group_id,
            "dropped:audit",
            task_digest_full=row.task_digest_full,
            policy_checkpoint=row.policy_checkpoint,
        )
    except RewardGroupConsumed as exc:
        if exc.disposition == "dropped:audit":
            return "dropped"
        if exc.disposition == "used":
            return "late"
        raise
    return "dropped"


def _run_key(keyring: RewardKeyring) -> bytes:
    if not isinstance(keyring, RewardKeyring):
        raise RewardKeyError("audit report requires a keyring")
    return keyring.run_key(keyring.run_id)


def _report_body(run_id: str, report: Mapping[str, object]) -> dict[str, object]:
    if report.get("run_id") != run_id or report.get("p3") not in {"halt", "clear"}:
        raise RewardRecordError("audit report is not usable")
    copied = json.loads(canonical_bytes(dict(report)))
    if not isinstance(copied, dict):
        raise RewardRecordError("audit report is not usable")
    return {"report": copied, "run_id": run_id, "type": "audit_report"}


def _mac_matches(body: Mapping[str, object], run_key: bytes) -> bool:
    mac = body.get("mac")
    if type(mac) is not str or len(mac) != 64:
        return False
    unsigned = {key: value for key, value in body.items() if key != "mac"}
    return hmac.compare_digest(mac, _line_mac(run_key, unsigned))


def _line_mac(run_key: bytes, body: Mapping[str, object]) -> str:
    message = _REPORT_DOMAIN + b"\n" + canonical_bytes(dict(body))
    return hmac.new(run_key, message, hashlib.sha256).hexdigest()


def _verify_line(body: dict[str, object], run_key: bytes, run_id: str) -> None:
    mac = body.get("mac")
    if type(mac) is not str or len(mac) != 64:
        raise RewardRecordError("audit report mac does not verify")
    unsigned = {key: value for key, value in body.items() if key != "mac"}
    expected = _line_mac(run_key, unsigned)
    if not hmac.compare_digest(mac, expected):
        raise RewardRecordError("audit report mac does not verify")
    if body.get("run_id") != run_id:
        raise RewardRecordError("audit report run id does not match")
    kind = body.get("type")
    if kind == "audit_report":
        report = body.get("report")
        if not isinstance(report, dict) or report.get("run_id") != run_id:
            raise RewardRecordError("audit report is not usable")
        if report.get("p3") not in {"halt", "clear"}:
            raise RewardRecordError("audit report is not usable")
        return
    if kind == "audit_triage":
        if type(body.get("record_id")) is not str or type(body.get("triaged_by")) is not str:
            raise RewardRecordError("audit triage is not usable")
        return
    raise RewardRecordError("audit report is not usable")


def _bodies(text: str, run_key: bytes) -> tuple[dict[str, object], ...]:
    found: list[dict[str, object]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            body = loads_strict(line)
        except CanonicalError as exc:
            raise RewardRecordError("audit report log is corrupt") from exc
        if not isinstance(body, dict) or not _mac_matches(body, run_key):
            raise RewardRecordError("audit report mac does not verify")
        found.append(body)
    return tuple(found)


def _reject_tamper(text: str, run_key: bytes) -> None:
    """A torn or retagged prefix is not appended over."""
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            body = loads_strict(line)
        except CanonicalError as exc:
            raise RewardRecordError("audit report log is corrupt") from exc
        if not isinstance(body, dict):
            raise RewardRecordError("audit report log is corrupt")
        if not _mac_matches(body, run_key):
            raise RewardRecordError("audit report mac does not verify")


def _latest_report(lines: Sequence[Mapping[str, object]]) -> Mapping[str, object] | None:
    found: Mapping[str, object] | None = None
    for line in lines:
        if line.get("type") == "audit_report":
            report = line.get("report")
            if isinstance(report, dict):
                found = report
    return found


def _halt_ids(lines: Sequence[Mapping[str, object]]) -> set[str]:
    found: set[str] = set()
    for line in lines:
        if line.get("type") != "audit_report":
            continue
        report = line.get("report")
        if not isinstance(report, dict) or report.get("p3") != "halt":
            continue
        items = report.get("disagreements")
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and type(item.get("record_id")) is str:
                found.add(item["record_id"])
    return found


def _triaged_ids(lines: Sequence[Mapping[str, object]]) -> set[str]:
    found: set[str] = set()
    for line in lines:
        if line.get("type") != "audit_triage":
            continue
        record_id = line.get("record_id")
        if type(record_id) is str:
            found.add(record_id)
    return found


def _untriaged(lines: Sequence[Mapping[str, object]]) -> bool:
    return not _halt_ids(lines) <= _triaged_ids(lines)

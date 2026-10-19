"""Sampled rerun-from-source audit (D3-H2, spec §26 0.3.9), before P3.

Every passing row, a ceil(5%) sample of graded 0.0 rows, and every signed
canary are rerun from source. The seed is HMAC-SHA256 of the run key and
``d3-h2-seed`` plus the run id. Any other seed is refused. A disagreement
leaves that row ungraded, drops its group, and persists a halt. Every
halt also appends a MAC'd halt-marker claim to the consumed log, inside
the anchor's claim-byte coverage. A new report chain is refused while
that marker remains and the anchor is gone. P3 reads the report and
does not start while the latest one is not clear.
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import pwd
import unicodedata
import warnings
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rfc3339_validator import RFC3339_REGEX, validate_rfc3339

from faustcoder.canonical import CanonicalError, canonical_bytes, loads_strict
from faustcoder.reward.records import (
    GRADER_USER,
    ConsumedLog,
    RewardGroupConsumed,
    RewardKeyError,
    RewardKeyring,
    RewardRecordError,
    RewardRowRecord,
    _fsync_dir,
    _grader_uid,
    _open_consumed,
    _read_text,
    _write_all,
    verify,
)
from faustcoder.reward.triage_sig import (
    read_drop,
    verify_statement,
    _require_statement,
)

_SAMPLE_PERCENT = 5
_SEED_LABEL = b"d3-h2-seed"
_REPORT_DOMAIN = b"faustcoder.reward-audit-report.v1"
_CONSUMED_ID_DOMAIN = b"faustcoder.consumed-id.v1"
_ANCHOR_DOMAIN = b"faustcoder.audit-anchor.v1"
_HALT_DOMAIN = b"faustcoder.audit-halt.v1"
_HALT_PREFIX = b"audit-halt v1 "
_FAIL_OUTCOMES = frozenset({"fail", "source_attributed"})
_LOG_MODE = 0o640
_GENESIS_MAC = "0" * 64
_ANCHOR_LEN = 248
_ACTOR_MAX = 128
_ROOT_USER = "root"
_TRIAGE_SKEW = timedelta(minutes=5)
# Hyphen-like and letter confusables that NFKC + casefold do not fold
# to ASCII. U+2011 (non-breaking hyphen) becomes U+2010, not "-".
_CONFUSABLE_SKELETON = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u02d7": "-",
        "\u2043": "-",
        "\u207b": "-",
        "\u208b": "-",
        "\u2212": "-",
        "\ufe58": "-",
        "\u0261": "g",
        "\u03bf": "o",
        "\u03c4": "t",
        "\u0430": "a",
        "\u0435": "e",
        "\u043e": "o",
        "\u0441": "c",
        "\u0442": "t",
        "\u0501": "d",
    }
)


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
    row_ids: tuple[str, ...]
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
            "row_ids": list(self.row_ids),
            "row_ids_digest": _row_ids_digest(self.row_ids),
            "run_id": self.run_id,
            "sample_ids": list(self.sample_ids),
            "seed": self.seed,
            "ungraded_ids": list(self.ungraded_ids),
        }

    def canonical_report(self) -> bytes:
        return canonical_bytes(self.report())


class RefusedTriageWarning(UserWarning):
    """A MAC'd triage line was skipped and did not clear a halt."""


@dataclass(frozen=True)
class RefusedTriage:
    """One MAC'd triage line that does not clear a halt.

    The line stays in the report log. ``reason`` is the refusal.
    """

    seq: int
    record_id: str
    reason: str


class AuditReportLog:
    """Append-only MAC'd audit reports for one run.

    The file sits next to the consumed log. A halt stays until a
    signed human triage is recorded against each disagreement. A
    run-key MAC alone does not clear it. A triage from the grader
    account or from root does not clear it. A MAC'd triage line that
    fails a check stays in the log and is reported; it does not make
    the log unreadable and it does not clear the halt. A later clear
    report does not replace a halt.
    """

    def __init__(
        self,
        path: Path | str,
        consumed: ConsumedLog,
        *,
        allowed_signers: Path | str | None = None,
    ) -> None:
        if not isinstance(consumed, ConsumedLog):
            raise RewardRecordError("audit report requires its consumed log")
        self.path = Path(path)
        self.consumed = consumed
        self.allowed_signers = None if allowed_signers is None else Path(allowed_signers)

    def append(self, keyring: RewardKeyring, report: Mapping[str, object]) -> None:
        """Persist ``report``. A clear report cannot cover an open halt.

        A halt is stamped ``halted_at`` from this clock, under the MAC.
        Triage cannot be earlier than that stamp.
        """
        run_key = _run_key(keyring)
        stored = dict(report)
        stored["consumed_id"] = _consumed_id(run_key, self.consumed.path)
        stored["consumed_path"] = os.path.realpath(self.consumed.path)
        if stored.get("p3") == "halt":
            stamp = _utc_stamp()
            stored["halted_at"] = stamp
            stored["persisted_at"] = stamp
        body = _report_body(keyring.run_id, stored)
        self._append_line(run_key, body)

    def record_triage(
        self,
        keyring: RewardKeyring,
        *,
        record_id: str,
        triaged_by: str,
        triaged_at: str,
        drop_path: Path | str | None = None,
    ) -> None:
        """Record one signed human triage. This is the only clear.

        ``triaged_by`` is stripped and must be a short printable name.
        ``triaged_at`` is RFC 3339, not earlier than the halt it clears,
        and not later than now plus five minutes. ``drop_path`` is the
        human's signed drop. Its owner, read with ``fstat`` on an
        ``O_NONBLOCK | O_NOFOLLOW`` fd, is the recorded writer. The grader
        account and root are refused after NFKC, casefold, and a small
        confusable skeleton. The same principal, and the same key
        fingerprint, cannot sign one disagreement twice. A late halt
        needs two distinct principals and two distinct key fingerprints.
        """
        if type(record_id) is not str or record_id == "":
            raise RewardRecordError("audit triage record id is not usable")
        actor = _require_actor(triaged_by)
        when = _require_triaged_at(triaged_at)
        lines = self._verified(keyring)
        open_ids = _halt_ids(lines)
        if record_id not in open_ids:
            raise RewardRecordError("audit triage does not match a disagreement")
        _require_not_before_halt(when, record_id, lines)
        if drop_path is None:
            raise RewardRecordError("audit triage signature is not usable")
        drop = read_drop(drop_path)
        if _require_actor(drop.triaged_by) != actor:
            raise RewardRecordError("audit triage actor is not usable")
        writer_uid, writer_user = _require_os_user(drop.owner_name, drop.owner_uid)
        decision = _require_statement_binding(
            drop.statement,
            record_id,
            when,
            lines,
            keyring.run_id,
        )
        if type(drop.principal) is not str or drop.principal == "":
            raise RewardRecordError("audit triage signature is not usable")
        principals, fingerprints = _accepted_votes(lines, self.allowed_signers).get(
            record_id, (set(), set())
        )
        fingerprint = drop.statement.get("key_fingerprint")
        if drop.principal in principals or fingerprint in fingerprints:
            raise RewardRecordError("audit triage signature is not usable")
        appended_at = _utc_stamp()
        appended = _parse_rfc3339(appended_at)
        if appended is None or appended < _halt_instant(lines, record_id):
            raise RewardRecordError("audit triage time is not usable")
        verify_statement(
            drop.statement,
            drop.signature,
            principal=drop.principal,
            allowed_signers=_signers_path(self.allowed_signers),
            appended_at=appended_at,
            triaged_at=when,
        )
        self._append_line(
            _run_key(keyring),
            {
                "appended_at": appended_at,
                "decision": decision,
                "principal": drop.principal,
                "record_id": record_id,
                "run_id": keyring.run_id,
                "signature": drop.signature,
                "statement": dict(drop.statement),
                "triaged_at": when,
                "triaged_by": actor,
                "type": "audit_triage",
                "v": 2,
                "writer_uid": writer_uid,
                "writer_user": writer_user,
            },
        )

    def refused_triages(self, keyring: RewardKeyring) -> tuple[RefusedTriage, ...]:
        """MAC'd triage lines that do not clear a halt.

        The log stays readable. A listed line never clears its halt.
        """
        lines = self._verified(keyring)
        return _refused_triages(lines, self.allowed_signers)

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
        _check_chain(found)
        lines = tuple(found)
        for item in _refused_triages(lines, self.allowed_signers):
            warnings.warn(
                f"refused audit triage seq {item.seq} does not clear a halt",
                RefusedTriageWarning,
                stacklevel=2,
            )
        return lines

    def _append_line(self, run_key: bytes, body: dict[str, object]) -> None:
        """Append one chained line and move the consumed-log anchor with it."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, created = _open_consumed(self.path)
        try:
            os.fchmod(fd, _LOG_MODE)
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                existing = _read_text(fd)
                seq, prev = _next_link(existing, run_key, self.consumed)
                chained = dict(body)
                chained["prev"] = prev
                chained["seq"] = seq
                if chained.get("type") == "audit_report" and existing.strip():
                    report = chained.get("report")
                    if (
                        isinstance(report, dict)
                        and report.get("p3") == "clear"
                        and _untriaged(_bodies(existing, run_key), self.allowed_signers)
                    ):
                        raise RewardRecordError("audit halt is not cleared by another report")
                signed = dict(chained)
                signed["mac"] = _line_mac(run_key, chained)
                _write_all(fd, canonical_bytes(signed) + b"\n")
                os.fsync(fd)
                if created:
                    _fsync_dir(self.path.parent)
                # The report line is durable before the anchor moves. A crash
                # in between leaves the tail ahead of the anchor. The next
                # read and the next append both fail closed. There is no repair.
                # A halt marker is written in that same anchor update, so the
                # new anchor MAC covers it.
                mac = signed["mac"]
                if type(mac) is not str:
                    raise RewardRecordError("audit report mac does not verify")
                _advance_anchor(
                    self.consumed,
                    run_key,
                    seq,
                    mac,
                    record_ids=_marker_ids(signed),
                )
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


def p3_may_proceed(
    run_id: str,
    *,
    keyring: RewardKeyring,
    reports: AuditReportLog,
    consumed: ConsumedLog,
) -> bool:
    """True only when this run's latest persisted report is clear.

    The report must be the chain anchored in ``consumed``. An open halt
    stays closed until triage is recorded for each disagreement. A
    missing report is not clear. A bad MAC, a foreign consumed log, or
    a truncated chain raises. A MAC'd triage line that fails the actor,
    time, writer, or signature check does not raise and does not clear
    the halt. A line counts only at ``v == 2`` after the signature
    verifies. A late halt needs two distinct principals.
    """
    if not isinstance(reports, AuditReportLog):
        raise RewardRecordError("P3 requires the persisted audit report")
    if not isinstance(consumed, ConsumedLog):
        raise RewardRecordError("P3 requires the consumed log")
    if not isinstance(keyring, RewardKeyring) or type(run_id) is not str or keyring.run_id != run_id:
        raise RewardRecordError("audit report run id does not match")
    if os.path.realpath(reports.consumed.path) != os.path.realpath(consumed.path):
        raise RewardRecordError("audit report consumed log does not match")
    if not reports.path.is_file():
        return False
    lines = reports._verified(keyring)
    run_key = _run_key(keyring)
    _require_consumed_binding(lines, run_key, consumed.path)
    _require_anchor(consumed, run_key, lines)
    if _untriaged(lines, reports.allowed_signers):
        return False
    latest = _latest_report(lines)
    if latest is None:
        return False
    if latest.get("p3") == "clear":
        return True
    return _halt_ids(lines) <= _triaged_ids(lines, reports.allowed_signers)


def require_audit_coverage(
    run_id: str,
    records: Sequence[RewardRowRecord],
    *,
    keyring: RewardKeyring,
    reports: AuditReportLog,
    consumed: ConsumedLog,
) -> None:
    """Refuse a batch row the persisted audits did not cover.

    Every record id must sit in the union of ``row_ids``. A pass or a
    signed canary must also sit in the union of ``audited_ids``.
    """
    if not reports.path.is_file():
        raise RewardRecordError("P3 audit did not cover this row")
    lines = reports._verified(keyring)
    run_key = _run_key(keyring)
    _require_consumed_binding(lines, run_key, consumed.path)
    _require_anchor(consumed, run_key, lines)
    covered: set[str] = set()
    rerun: set[str] = set()
    for line in lines:
        if line.get("type") != "audit_report":
            continue
        report = line.get("report")
        if not isinstance(report, dict) or report.get("run_id") != run_id:
            raise RewardRecordError("audit report is not usable")
        covered.update(_id_list(report.get("row_ids"), report.get("row_ids_digest")))
        rerun.update(_plain_ids(report.get("audited_ids")))
    for record in records:
        if record.record_id not in covered:
            raise RewardRecordError("P3 audit did not cover this row")
        if (record.outcome == "pass" or record.canary is True) and record.record_id not in rerun:
            raise RewardRecordError("P3 audit did not cover this row")


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
                claimed[row.group_id] = _preview_claim(consumed, row.group_id)
    except RewardGroupConsumed:
        _persist(
            reports,
            keyring,
            _audit_from(keyring.run_id, derived, sample, audited, disagreements, claimed, rows),
        )
        raise
    audit = _audit_from(keyring.run_id, derived, sample, audited, disagreements, claimed, rows)
    _persist(reports, keyring, audit)
    # Claims follow the report so a fresh halt can still open its chain.
    # The halt marker is already in the claim bytes. A claim refreshes
    # the anchor MAC over those bytes.
    for group_id in claimed:
        _claim_dropped(consumed, rows, group_id, _run_key(keyring))
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
        row_ids=tuple(sorted({row.record_id for row in rows})),
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


def _preview_claim(consumed: ConsumedLog, group_id: str) -> str:
    """The disposition a later claim will record, without writing it."""
    existing = consumed.disposition(group_id)
    if existing is None or existing == "dropped:audit":
        return "dropped"
    if existing == "used":
        return "late"
    raise RewardGroupConsumed(group_id, existing)


def _claim_dropped(
    consumed: ConsumedLog,
    rows: tuple[RewardRowRecord, ...],
    group_id: str,
    run_key: bytes,
) -> str:
    row = next(item for item in rows if item.group_id == group_id)
    try:
        consumed.claim(
            group_id,
            "dropped:audit",
            task_digest_full=row.task_digest_full,
            policy_checkpoint=row.policy_checkpoint,
            run_key=run_key,
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


def _name_skeleton(name: str) -> str:
    """Fold ``name`` for the reserved-name comparison.

    NFKC and casefold turn ``FC-GRADER``, ``Root``, and fullwidth
    letters into the ASCII names. The confusable map then folds
    hyphen-like characters and letters that NFKC leaves unchanged.
    """
    folded = unicodedata.normalize("NFKC", name).casefold()
    folded = unicodedata.normalize("NFKC", folded)
    return folded.translate(_CONFUSABLE_SKELETON)


_RESERVED_SKELETONS = frozenset(
    (_name_skeleton(GRADER_USER), _name_skeleton(_ROOT_USER))
)


def _is_reserved_name(name: str) -> bool:
    """True when ``name`` is the grader account or root after folding."""
    return _name_skeleton(name) in _RESERVED_SKELETONS


def _printable_name(name: str) -> bool:
    """True when every character is printable and none is format or control."""
    if name == "" or not name.isprintable():
        return False
    for char in name:
        category = unicodedata.category(char)
        if category[0] == "C" or category in {"Zl", "Zp"}:
            return False
    return True


def _require_actor(value: object) -> str:
    """Strip ``value`` and refuse a blank, huge, or non-printable name.

    The grader account and root are refused after NFKC, casefold, and
    the confusable skeleton. The stored name is the stripped text.
    """
    if type(value) is not str:
        raise RewardRecordError("audit triage actor is not usable")
    name = value.strip()
    if name == "" or len(name) > _ACTOR_MAX or not _printable_name(name):
        raise RewardRecordError("audit triage actor is not usable")
    if _is_reserved_name(name):
        raise RewardRecordError("audit triage actor is not usable")
    return name


def _dedicated_grader_uid() -> int | None:
    """Uid of the dedicated grader account, or None when it is not provisioned.

    ``_grader_uid`` refuses a missing account and a root-owned grader.
    A host without that account has no grader uid to match. Uid 0 is
    still refused by the writer check.
    """
    try:
        return _grader_uid()
    except RewardKeyError:
        return None


def _require_os_user(name: object, uid: object) -> tuple[int, str]:
    """Refuse root, the grader account, and an unusable recorded writer."""
    if type(uid) is not int or isinstance(uid, bool) or uid <= 0:
        raise RewardRecordError("audit triage writer is not usable")
    if type(name) is not str or name != name.strip():
        raise RewardRecordError("audit triage writer is not usable")
    if name == "" or len(name) > _ACTOR_MAX or not _printable_name(name):
        raise RewardRecordError("audit triage writer is not usable")
    if _is_reserved_name(name):
        raise RewardRecordError("audit triage writer is not usable")
    grader_uid = _dedicated_grader_uid()
    if grader_uid is not None and uid == grader_uid:
        raise RewardRecordError("audit triage writer is not usable")
    return uid, name


def _utc_stamp() -> str:
    """RFC 3339 UTC time, whole seconds, uppercase ``Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_rfc3339(value: object) -> datetime | None:
    """The UTC instant, or None when ``value`` is not a whole RFC 3339 stamp.

    ``validate_rfc3339`` uses ``$``, which matches before one trailing
    newline. A newline is not part of the timestamp. Lowercase ``t``
    and ``z`` are refused. An offset that cannot be converted to UTC
    is refused rather than raised.
    """
    if type(value) is not str or value == "" or "\n" in value or "\r" in value:
        return None
    if RFC3339_REGEX.fullmatch(value) is None or validate_rfc3339(value) is not True:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    # astimezone raises OverflowError for offsets that leave the
    # datetime range (year 1 with +14:00, year 9999 with -12:00).
    # That is a refused stamp, not an error the gate may raise.
    try:
        if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None


def _require_triaged_at(value: object) -> str:
    """Refuse a stamp that is not RFC 3339 or is later than now plus skew."""
    parsed = _parse_rfc3339(value)
    if parsed is None or type(value) is not str:
        raise RewardRecordError("audit triage time is not usable")
    if parsed > datetime.now(timezone.utc) + _TRIAGE_SKEW:
        raise RewardRecordError("audit triage time is not usable")
    return value


def _disagreement_ids(report: Mapping[str, object]) -> set[str]:
    items = report.get("disagreements")
    if not isinstance(items, list):
        return set()
    found: set[str] = set()
    for item in items:
        if isinstance(item, dict) and type(item.get("record_id")) is str:
            found.add(item["record_id"])
    return found


def _persist_instant(report: Mapping[str, object]) -> datetime:
    """The halt's persist time.

    ``persisted_at`` is that time when the line carries it. A line
    written before that field existed uses ``halted_at``. A halt that
    names the disagreement and has no usable stamp fails closed.
    """
    if "persisted_at" in report:
        parsed = _parse_rfc3339(report.get("persisted_at"))
    else:
        parsed = _parse_rfc3339(report.get("halted_at"))
    if parsed is None:
        raise RewardRecordError("audit triage time is not usable")
    return parsed


def _halt_instant(lines: Sequence[Mapping[str, object]], record_id: str) -> datetime:
    """Latest persist time among halts that include ``record_id``."""
    latest: datetime | None = None
    for line in lines:
        if line.get("type") != "audit_report":
            continue
        report = line.get("report")
        if not isinstance(report, dict) or report.get("p3") != "halt":
            continue
        if record_id not in _disagreement_ids(report):
            continue
        parsed = _persist_instant(report)
        if latest is None or parsed > latest:
            latest = parsed
    if latest is None:
        raise RewardRecordError("audit triage time is not usable")
    return latest


def _require_not_before_halt(
    stamp: str,
    record_id: str,
    lines: Sequence[Mapping[str, object]],
) -> None:
    parsed = _parse_rfc3339(stamp)
    if parsed is None or parsed < _halt_instant(lines, record_id):
        raise RewardRecordError("audit triage time is not usable")


def _signers_path(path: Path | None) -> Path:
    from faustcoder.reward.triage_sig import default_allowed_signers

    return default_allowed_signers() if path is None else path


def _require_statement_binding(
    statement: object,
    record_id: str,
    when: str,
    lines: Sequence[Mapping[str, object]],
    run_id: str,
) -> str:
    """Return the decision when ``statement`` names this halt line."""
    if not isinstance(statement, Mapping):
        raise RewardRecordError("audit triage signature is not usable")
    checked = _require_statement(statement)
    if checked["run_id"] != run_id or checked["record_id"] != record_id:
        raise RewardRecordError("audit triage signature is not usable")
    if checked["triaged_at"] != when:
        raise RewardRecordError("audit triage signature is not usable")
    halt_seq = checked["halt_seq"]
    halt: Mapping[str, object] | None = None
    for line in lines:
        if line.get("type") != "audit_report" or line.get("seq") != halt_seq:
            continue
        report = line.get("report")
        if isinstance(report, dict) and report.get("p3") == "halt":
            halt = line
            break
    if halt is None or halt_seq != _latest_halt_seq(lines, record_id):
        raise RewardRecordError("audit triage signature is not usable")
    report = halt.get("report")
    if not isinstance(report, dict):
        raise RewardRecordError("audit triage signature is not usable")
    if halt.get("run_id") != run_id or halt.get("mac") != checked["halt_report_mac"]:
        raise RewardRecordError("audit triage signature is not usable")
    if report.get("row_ids_digest") != checked["row_ids_digest"]:
        raise RewardRecordError("audit triage signature is not usable")
    if report.get("consumed_id") != checked["consumed_id"]:
        raise RewardRecordError("audit triage signature is not usable")
    if record_id not in _disagreement_ids(report):
        raise RewardRecordError("audit triage signature is not usable")
    decision = checked["decision"]
    if type(decision) is not str:
        raise RewardRecordError("audit triage signature is not usable")
    return decision


def _latest_halt_seq(lines: Sequence[Mapping[str, object]], record_id: str) -> int:
    """Sequence of the newest halt line that names ``record_id``."""
    latest: int | None = None
    for line in lines:
        if line.get("type") != "audit_report":
            continue
        report = line.get("report")
        if not isinstance(report, dict) or report.get("p3") != "halt":
            continue
        if record_id not in _disagreement_ids(report):
            continue
        seq = line.get("seq")
        if type(seq) is not int or isinstance(seq, bool):
            raise RewardRecordError("audit triage signature is not usable")
        if latest is None or seq > latest:
            latest = seq
    if latest is None:
        raise RewardRecordError("audit triage signature is not usable")
    return latest


def _late_disagreement(lines: Sequence[Mapping[str, object]], record_id: str) -> bool:
    """True when any halt names ``record_id`` in a late group.

    A disagreement with no group id fails closed and needs two votes.
    """
    saw = False
    late = False
    for line in lines:
        if line.get("type") != "audit_report":
            continue
        report = line.get("report")
        if not isinstance(report, dict) or report.get("p3") != "halt":
            continue
        late_ids: set[str] = set()
        groups = report.get("late_groups")
        if isinstance(groups, list):
            for item in groups:
                if isinstance(item, dict) and type(item.get("group_id")) is str:
                    late_ids.add(item["group_id"])
        items = report.get("disagreements")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("record_id") != record_id:
                continue
            saw = True
            group = item.get("group_id")
            if type(group) is not str or group in late_ids:
                late = True
    if not saw:
        return True
    return late


def _quorum(lines: Sequence[Mapping[str, object]], record_id: str) -> int:
    return 2 if _late_disagreement(lines, record_id) else 1


def _accepted_triage(
    body: Mapping[str, object],
    lines: Sequence[Mapping[str, object]],
    allowed_signers: Path | None,
) -> tuple[str, str, str]:
    """Return ``(record_id, principal, key_fingerprint)`` for one vote.

    The same rules apply on write and on read. A refused line does not
    clear the halt. Only ``v == 2`` can count, and only after the
    signature verifies at the recorded ``appended_at`` and at
    ``triaged_at``.
    """
    record_id = body.get("record_id")
    if type(record_id) is not str or record_id == "":
        raise RewardRecordError("audit triage is not usable")
    _require_actor(body.get("triaged_by"))
    when = _require_triaged_at(body.get("triaged_at"))
    _require_os_user(body.get("writer_user"), body.get("writer_uid"))
    _require_not_before_halt(when, record_id, lines)
    version = body.get("v")
    if type(version) is not int or isinstance(version, bool) or version != 2:
        raise RewardRecordError("audit triage signature is not usable")
    statement = body.get("statement")
    signature = body.get("signature")
    principal = body.get("principal")
    appended_at = body.get("appended_at")
    if (
        type(signature) is not str
        or type(principal) is not str
        or principal == ""
        or type(appended_at) is not str
        or not isinstance(statement, Mapping)
    ):
        raise RewardRecordError("audit triage signature is not usable")
    _require_statement_binding(statement, record_id, when, lines, _line_run_id(body, lines))
    verify_statement(
        statement,
        signature,
        principal=principal,
        allowed_signers=_signers_path(allowed_signers),
        appended_at=appended_at,
        triaged_at=when,
    )
    fingerprint = statement.get("key_fingerprint")
    if type(fingerprint) is not str or fingerprint == "":
        raise RewardRecordError("audit triage signature is not usable")
    return record_id, principal, fingerprint


def _line_run_id(body: Mapping[str, object], lines: Sequence[Mapping[str, object]]) -> str:
    run_id = body.get("run_id")
    if type(run_id) is str and run_id != "":
        return run_id
    for line in lines:
        if line.get("type") == "audit_report" and type(line.get("run_id")) is str:
            return line["run_id"]
    raise RewardRecordError("audit triage signature is not usable")


def _shown_record_id(value: object) -> str:
    if type(value) is not str or len(value) > _ACTOR_MAX:
        return ""
    return value


def _refused_triages(
    lines: Sequence[Mapping[str, object]],
    allowed_signers: Path | None = None,
) -> tuple[RefusedTriage, ...]:
    """Triage lines in ``lines`` that fail acceptance."""
    found: list[RefusedTriage] = []
    for line in lines:
        if line.get("type") != "audit_triage":
            continue
        try:
            _accepted_triage(line, lines, allowed_signers)
        except RewardRecordError as exc:
            seq = line.get("seq")
            if type(seq) is not int or isinstance(seq, bool):
                seq = 0
            found.append(
                RefusedTriage(
                    seq=seq,
                    record_id=_shown_record_id(line.get("record_id")),
                    reason=str(exc),
                )
            )
    return tuple(found)


def _verify_line(body: dict[str, object], run_key: bytes, run_id: str) -> None:
    mac = body.get("mac")
    if type(mac) is not str or len(mac) != 64:
        raise RewardRecordError("audit report mac does not verify")
    unsigned = {key: value for key, value in body.items() if key != "mac"}
    expected = _line_mac(run_key, unsigned)
    if not hmac.compare_digest(mac, expected):
        raise RewardRecordError("audit report mac does not verify")
    seq = body.get("seq")
    prev = body.get("prev")
    if type(seq) is not int or isinstance(seq, bool) or seq < 1:
        raise RewardRecordError("audit report sequence is not usable")
    if type(prev) is not str or len(prev) != 64:
        raise RewardRecordError("audit report chain does not verify")
    if body.get("run_id") != run_id:
        raise RewardRecordError("audit report run id does not match")
    kind = body.get("type")
    if kind == "audit_report":
        report = body.get("report")
        if not isinstance(report, dict) or report.get("run_id") != run_id:
            raise RewardRecordError("audit report is not usable")
        if report.get("p3") not in {"halt", "clear"}:
            raise RewardRecordError("audit report is not usable")
        _id_list(report.get("row_ids"), report.get("row_ids_digest"))
        audited = set(_plain_ids(report.get("audited_ids")))
        if not audited <= set(_plain_ids(report.get("row_ids"))):
            raise RewardRecordError("audit report row ids are not usable")
        if type(report.get("consumed_id")) is not str or type(report.get("consumed_path")) is not str:
            raise RewardRecordError("audit report consumed log does not match")
        return
    if kind == "audit_triage":
        # The MAC and the chain already held. Acceptance is what clears
        # a halt. A line that fails it is reported and skipped.
        return
    raise RewardRecordError("audit report is not usable")


def _row_ids_digest(record_ids: Sequence[str]) -> str:
    return hashlib.sha256(canonical_bytes(list(record_ids))).hexdigest()


def _plain_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(type(item) is not str or item == "" for item in value):
        raise RewardRecordError("audit report row ids are not usable")
    return tuple(value)


def _id_list(value: object, digest: object) -> tuple[str, ...]:
    ids = _plain_ids(value)
    if list(ids) != sorted(set(ids)):
        raise RewardRecordError("audit report row ids are not usable")
    expected = _row_ids_digest(ids)
    if type(digest) is not str or len(digest) != len(expected) or not hmac.compare_digest(digest, expected):
        raise RewardRecordError("audit report row ids are not usable")
    return ids


def _check_chain(lines: Sequence[Mapping[str, object]]) -> None:
    previous = _GENESIS_MAC
    for index, body in enumerate(lines, start=1):
        seq = body.get("seq")
        prev = body.get("prev")
        if seq != index or prev != previous:
            raise RewardRecordError("audit report chain does not verify")
        mac = body.get("mac")
        if type(mac) is not str:
            raise RewardRecordError("audit report mac does not verify")
        previous = mac


def _next_link(existing: str, run_key: bytes, consumed: ConsumedLog) -> tuple[int, str]:
    """The next sequence and prev MAC, or a rollback error."""
    anchor = _read_anchor(consumed, run_key)
    if not existing.strip():
        if (
            anchor is not None
            or _dropped_audit_remains(consumed)
            or _unresolved_halt_marker(consumed, run_key)
        ):
            raise RewardRecordError("audit report log was rolled back")
        return 1, _GENESIS_MAC
    _reject_tamper(existing, run_key)
    lines = _bodies(existing, run_key)
    _check_chain(lines)
    tail = lines[-1]
    seq = tail.get("seq")
    mac = tail.get("mac")
    if type(seq) is not int or isinstance(seq, bool) or type(mac) is not str:
        raise RewardRecordError("audit report chain does not verify")
    if anchor is None or anchor[0] != seq or not hmac.compare_digest(anchor[1], mac):
        raise RewardRecordError("audit report log was rolled back")
    return seq + 1, mac


def _consumed_id(run_key: bytes, path: Path) -> str:
    resolved = os.path.realpath(path).encode("utf-8")
    return hmac.new(run_key, _CONSUMED_ID_DOMAIN + b"\n" + resolved, hashlib.sha256).hexdigest()


def _anchor_bind(
    run_key: bytes,
    *,
    seq: int,
    line_mac: str,
    consumed_id: str,
    path: Path,
    claim_digest: str,
) -> str:
    """MAC the anchor over the report tail and the consumed-log claim bytes."""
    message = (
        _ANCHOR_DOMAIN
        + b"\n"
        + str(seq).encode("ascii")
        + b"\n"
        + line_mac.encode("ascii")
        + b"\n"
        + consumed_id.encode("ascii")
        + b"\n"
        + os.path.realpath(path).encode("utf-8")
        + b"\n"
        + claim_digest.encode("ascii")
    )
    return hmac.new(run_key, message, hashlib.sha256).hexdigest()


def _claim_digest(data: bytes) -> str:
    """SHA-256 of the consumed log with the anchor line removed."""
    offset = _anchor_offset(data)
    if offset is None:
        material = data
    else:
        material = data[:offset] + data[offset + _ANCHOR_LEN :]
    return hashlib.sha256(material).hexdigest()


def _dropped_audit_remains(consumed: ConsumedLog) -> bool:
    """True when a halt claim is still in the log and the anchor is gone."""
    if not consumed.path.is_file():
        return False
    data = _read_consumed_bytes(consumed.path)
    if _anchor_offset(data) is not None:
        return False
    for line in data.splitlines():
        if not line.strip():
            continue
        try:
            body = loads_strict(line.decode("utf-8"))
        except CanonicalError:
            continue
        if isinstance(body, dict) and body.get("disposition") == "dropped:audit":
            return True
    return False


def _marker_ids(signed: Mapping[str, object]) -> tuple[str, ...] | None:
    """Disagreement ids for a halt line, or None when the line is not a halt."""
    if signed.get("type") != "audit_report":
        return None
    report = signed.get("report")
    if not isinstance(report, dict) or report.get("p3") != "halt":
        return None
    items = report.get("disagreements")
    if not isinstance(items, list) or not items:
        raise RewardRecordError("audit halt marker is not usable")
    found: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            raise RewardRecordError("audit halt marker is not usable")
        record_id = item.get("record_id")
        if type(record_id) is not str or record_id == "" or "\n" in record_id:
            raise RewardRecordError("audit halt marker is not usable")
        found.append(record_id)
    return tuple(sorted(set(found)))


def _halt_body(seq: int, report_mac: str, consumed_id: str, record_ids: tuple[str, ...]) -> dict[str, object]:
    return {
        "consumed_id": consumed_id,
        "record_ids": list(record_ids),
        "report_mac": report_mac,
        "seq": seq,
        "state": "unresolved",
        "type": "audit_halt",
    }


def _halt_mac(run_key: bytes, body: Mapping[str, object]) -> str:
    message = _HALT_DOMAIN + b"\n" + canonical_bytes(dict(body))
    return hmac.new(run_key, message, hashlib.sha256).hexdigest()


def _halt_line(
    run_key: bytes,
    seq: int,
    line_mac: str,
    consumed_id: str,
    record_ids: tuple[str, ...],
) -> bytes:
    body = _halt_body(seq, line_mac, consumed_id, record_ids)
    body["mac"] = _halt_mac(run_key, body)
    return _HALT_PREFIX + canonical_bytes(body) + b"\n"


def _unresolved_halt_marker(consumed: ConsumedLog, run_key: bytes) -> bool:
    """True when a halt marker is still in the log and the anchor is gone.

    The marker is MAC'd under the run key. A bad marker fails closed.
    With the anchor removed, that halt is unresolved.
    """
    if not consumed.path.is_file():
        return False
    data = _read_consumed_bytes(consumed.path)
    if _anchor_offset(data) is not None:
        return False
    found = False
    for raw in data.splitlines():
        if not raw.startswith(_HALT_PREFIX):
            continue
        _verify_halt_line(raw, run_key, consumed.path)
        found = True
    return found


def _verify_halt_line(raw: bytes, run_key: bytes, path: Path) -> None:
    if not raw.startswith(_HALT_PREFIX) or len(raw) == len(_HALT_PREFIX):
        raise RewardRecordError("audit halt marker is not usable")
    try:
        body = loads_strict(raw[len(_HALT_PREFIX) :].decode("utf-8"))
    except (UnicodeDecodeError, CanonicalError) as exc:
        raise RewardRecordError("audit halt marker is not usable") from exc
    if not isinstance(body, dict):
        raise RewardRecordError("audit halt marker is not usable")
    mac = body.get("mac")
    if type(mac) is not str or len(mac) != 64:
        raise RewardRecordError("audit halt marker is not usable")
    unsigned = {key: value for key, value in body.items() if key != "mac"}
    expected = _halt_mac(run_key, unsigned)
    if not hmac.compare_digest(mac, expected):
        raise RewardRecordError("audit halt marker is not usable")
    consumed_id = body.get("consumed_id")
    expected_id = _consumed_id(run_key, path)
    if (
        body.get("type") != "audit_halt"
        or body.get("state") != "unresolved"
        or type(consumed_id) is not str
        or len(consumed_id) != len(expected_id)
        or not hmac.compare_digest(consumed_id, expected_id)
    ):
        raise RewardRecordError("audit halt marker is not usable")


def _anchor_text(seq: int, line_mac: str, consumed_id: str, bind: str) -> bytes:
    text = f"audit-anchor v1 seq={seq:020d} mac={line_mac} id={consumed_id} bind={bind}\n"
    if len(text) != _ANCHOR_LEN:
        raise RewardRecordError("audit anchor is not usable")
    return text.encode("ascii")


def _parse_anchor(line: bytes) -> tuple[int, str, str, str]:
    if len(line) != _ANCHOR_LEN or not line.startswith(b"audit-anchor v1 seq=") or line[-1:] != b"\n":
        raise RewardRecordError("audit anchor is not usable")
    text = line[:-1].decode("ascii")
    if text[40:45] != " mac=" or text[109:113] != " id=" or text[177:183] != " bind=":
        raise RewardRecordError("audit anchor is not usable")
    seq_text = text[20:40]
    line_mac = text[45:109]
    consumed_id = text[113:177]
    bind = text[183:247]
    if not seq_text.isdigit() or len(line_mac) != 64 or len(consumed_id) != 64 or len(bind) != 64:
        raise RewardRecordError("audit anchor is not usable")
    seq = int(seq_text)
    if seq < 1:
        raise RewardRecordError("audit anchor is not usable")
    return seq, line_mac, consumed_id, bind


def _anchor_offset(data: bytes) -> int | None:
    prefix = b"audit-anchor v1 "
    offsets: list[int] = []
    start = 0
    while True:
        index = data.find(prefix, start)
        if index < 0:
            break
        if index == 0 or data[index - 1:index] == b"\n":
            offsets.append(index)
        start = index + len(prefix)
    if not offsets:
        return None
    if len(offsets) != 1:
        raise RewardRecordError("audit anchor is not usable")
    offset = offsets[0]
    if data[offset + _ANCHOR_LEN - 1:offset + _ANCHOR_LEN] != b"\n":
        raise RewardRecordError("audit anchor is not usable")
    return offset


def _read_consumed_bytes(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
        try:
            chunks: list[bytes] = []
            while True:
                block = os.read(fd, 1024 * 1024)
                if not block:
                    break
                chunks.append(block)
            return b"".join(chunks)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _verified_anchor(data: bytes, run_key: bytes, path: Path) -> tuple[int, str, str] | None:
    offset = _anchor_offset(data)
    if offset is None:
        return None
    seq, line_mac, consumed_id, bind = _parse_anchor(data[offset : offset + _ANCHOR_LEN])
    expected_id = _consumed_id(run_key, path)
    expected_bind = _anchor_bind(
        run_key,
        seq=seq,
        line_mac=line_mac,
        consumed_id=consumed_id,
        path=path,
        claim_digest=_claim_digest(data),
    )
    if not hmac.compare_digest(consumed_id, expected_id) or not hmac.compare_digest(bind, expected_bind):
        raise RewardRecordError("audit anchor is not usable")
    return seq, line_mac, consumed_id


def _read_anchor(consumed: ConsumedLog, run_key: bytes) -> tuple[int, str, str] | None:
    if not consumed.path.is_file():
        return None
    return _verified_anchor(_read_consumed_bytes(consumed.path), run_key, consumed.path)


def _pwrite_all(fd: int, data: bytes, offset: int) -> None:
    view = memoryview(data)
    at = offset
    while view:
        written = os.pwrite(fd, view, at)
        if written <= 0:
            raise RewardRecordError("reward record log write failed")
        at += written
        view = view[written:]


def _run_report_exists(consumed_path: Path, run_key: bytes) -> bool:
    """True when a sibling file holds a MAC'd report for this consumed log.

    Only the no-anchor claim path asks. A report for another log, or a
    line that does not verify under ``run_key``, does not count.
    """
    parent = consumed_path.parent
    if not parent.is_dir():
        return False
    try:
        names = os.listdir(parent)
    except OSError as exc:
        # Not knowing whether a report exists is not the same as there
        # being no report. A missing anchor must not be extended.
        raise RewardRecordError("audit anchor is not usable") from exc
    expected_id = _consumed_id(run_key, consumed_path)
    expected_real = os.path.realpath(consumed_path)
    for name in names:
        candidate = parent / name
        try:
            if os.path.realpath(candidate) == expected_real or not candidate.is_file():
                continue
            text = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if _text_binds_report(text, run_key, expected_id, expected_real):
            return True
    return False


def _text_binds_report(text: str, run_key: bytes, expected_id: str, expected_real: str) -> bool:
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            body = loads_strict(line)
        except CanonicalError:
            continue
        if not isinstance(body, dict) or body.get("type") != "audit_report":
            continue
        if not _mac_matches(body, run_key):
            continue
        report = body.get("report")
        if not isinstance(report, dict):
            continue
        consumed_id = report.get("consumed_id")
        consumed_path = report.get("consumed_path")
        if (
            type(consumed_id) is str
            and type(consumed_path) is str
            and len(consumed_id) == len(expected_id)
            and hmac.compare_digest(consumed_id, expected_id)
            and consumed_path == expected_real
        ):
            return True
    return False


def _refresh_anchor_bind(
    path: Path,
    run_key: bytes,
    *,
    locked: bool = False,
    prior: bytes | None = None,
    appended: bytes = b"",
) -> None:
    """Re-MAC an existing anchor over the claim bytes now in ``path``.

    The anchor MAC is checked before the bind is rewritten. ``prior`` is
    the byte string that MAC covers. ``appended`` is the one claim line
    just written. The file must be exactly those two strings; any other
    byte, including a line injected after the append, is refused. With
    no anchor yet, this is a no-op. An anchor that was in ``prior`` and
    is gone now is refused.

    ``locked`` means the caller already holds the consumed-log lock. A
    second flock on this file would deadlock, so this open does not lock.
    """
    if not path.is_file():
        return
    flags = os.O_RDWR | os.O_CLOEXEC
    fd = os.open(path, flags)
    try:
        if not locked:
            fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            chunks: list[bytes] = []
            while True:
                block = os.read(fd, 1024 * 1024)
                if not block:
                    break
                chunks.append(block)
            data = b"".join(chunks)
            offset = _anchor_offset(data)
            if offset is None:
                if prior is not None and _anchor_offset(prior) is not None:
                    raise RewardRecordError("audit anchor is not usable")
                return
            if prior is None:
                signed = data
            elif data != prior + appended:
                raise RewardRecordError("audit anchor is not usable")
            else:
                signed = prior
            verified = _verified_anchor(signed, run_key, path)
            if verified is None:
                raise RewardRecordError("audit anchor is not usable")
            seq, line_mac, consumed_id = verified
            bind = _anchor_bind(
                run_key,
                seq=seq,
                line_mac=line_mac,
                consumed_id=consumed_id,
                path=path,
                claim_digest=_claim_digest(data),
            )
            _pwrite_all(fd, _anchor_text(seq, line_mac, consumed_id, bind), offset)
            os.fsync(fd)
        finally:
            if not locked:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _advance_anchor(
    consumed: ConsumedLog,
    run_key: bytes,
    seq: int,
    line_mac: str,
    *,
    record_ids: tuple[str, ...] | None = None,
) -> None:
    """Move the anchor. A halt appends its marker under the same lock.

    The marker is claim bytes, so the anchor MAC written here covers it.
    """
    consumed_id = _consumed_id(run_key, consumed.path)
    consumed.path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CLOEXEC
    try:
        fd = os.open(consumed.path, flags | os.O_CREAT | os.O_EXCL, _LOG_MODE)
        created = True
    except FileExistsError:
        fd = os.open(consumed.path, flags)
        created = False
    try:
        os.fchmod(fd, _LOG_MODE)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            chunks: list[bytes] = []
            while True:
                block = os.read(fd, 1024 * 1024)
                if not block:
                    break
                chunks.append(block)
            data = b"".join(chunks)
            # The report-chain check ran before this lock. Re-verify the
            # anchor against the bytes held here, before any marker or bind
            # write. A later report must already have an anchor: a missing
            # one is not a first write, and signing the truncated log would
            # drop a halt marker deleted in the gap.
            verified = _verified_anchor(data, run_key, consumed.path)
            if seq > 1 and verified is None:
                raise RewardRecordError("audit anchor is not usable")
            offset = _anchor_offset(data)
            if record_ids is not None:
                os.lseek(fd, 0, os.SEEK_END)
                marker = _halt_line(run_key, seq, line_mac, consumed_id, record_ids)
                _write_all(fd, marker)
                data += marker
            bind = _anchor_bind(
                run_key,
                seq=seq,
                line_mac=line_mac,
                consumed_id=consumed_id,
                path=consumed.path,
                claim_digest=_claim_digest(data),
            )
            encoded = _anchor_text(seq, line_mac, consumed_id, bind)
            if offset is None:
                os.lseek(fd, 0, os.SEEK_END)
                _write_all(fd, encoded)
            else:
                _pwrite_all(fd, encoded, offset)
            os.fsync(fd)
            if created:
                _fsync_dir(consumed.path.parent)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _require_anchor(consumed: ConsumedLog, run_key: bytes, lines: Sequence[Mapping[str, object]]) -> None:
    anchor = _read_anchor(consumed, run_key)
    if not lines:
        raise RewardRecordError("audit report log is not usable")
    tail = lines[-1]
    seq = tail.get("seq")
    mac = tail.get("mac")
    if (
        anchor is None
        or type(seq) is not int
        or isinstance(seq, bool)
        or type(mac) is not str
        or anchor[0] != seq
        or not hmac.compare_digest(anchor[1], mac)
    ):
        raise RewardRecordError("audit report log was rolled back")


def _require_consumed_binding(lines: Sequence[Mapping[str, object]], run_key: bytes, path: Path) -> None:
    expected_id = _consumed_id(run_key, path)
    expected_path = os.path.realpath(path)
    saw_report = False
    for line in lines:
        if line.get("type") != "audit_report":
            continue
        saw_report = True
        report = line.get("report")
        if not isinstance(report, dict):
            raise RewardRecordError("audit report consumed log does not match")
        consumed_id = report.get("consumed_id")
        consumed_path = report.get("consumed_path")
        if (
            type(consumed_id) is not str
            or type(consumed_path) is not str
            or len(consumed_id) != len(expected_id)
            or not hmac.compare_digest(consumed_id, expected_id)
            or consumed_path != expected_path
        ):
            raise RewardRecordError("audit report consumed log does not match")
    if not saw_report:
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
        found.update(_disagreement_ids(report))
    return found


def _accepted_votes(
    lines: Sequence[Mapping[str, object]],
    allowed_signers: Path | None = None,
) -> dict[str, tuple[set[str], set[str]]]:
    """Principals and key fingerprints whose triage line still verifies."""
    found: dict[str, tuple[set[str], set[str]]] = {}
    for line in lines:
        if line.get("type") != "audit_triage":
            continue
        try:
            record_id, principal, fingerprint = _accepted_triage(line, lines, allowed_signers)
        except RewardRecordError:
            continue
        principals, fingerprints = found.setdefault(record_id, (set(), set()))
        principals.add(principal)
        fingerprints.add(fingerprint)
    return found


def _triaged_ids(
    lines: Sequence[Mapping[str, object]],
    allowed_signers: Path | None = None,
) -> set[str]:
    """Ids whose accepted votes meet the quorum.

    A line that fails the actor, time, writer, or signature check does
    not count. One reviewer clears an ordinary halt. A late halt needs
    two distinct principals and two distinct key fingerprints. The same
    principal twice counts once. The same key twice counts once, even
    when the two lines name different principals.
    """
    found: set[str] = set()
    accepted = _accepted_votes(lines, allowed_signers)
    for record_id, (principals, fingerprints) in accepted.items():
        need = _quorum(lines, record_id)
        if len(principals) >= need and len(fingerprints) >= need:
            found.add(record_id)
    return found


def _untriaged(
    lines: Sequence[Mapping[str, object]],
    allowed_signers: Path | None = None,
) -> bool:
    return not _halt_ids(lines) <= _triaged_ids(lines, allowed_signers)

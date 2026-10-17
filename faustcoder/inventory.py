"""T06 inventory contract.

There is no SourceRecord schema on main, and T05's inventory is still
in review. This document is the unit list T06 admits. It is not a copy
of ``corpus/rights-inventory.v1.json`` and it does not contain program
text. Each unit is one file, one function slice, or one multi-file source: a
primary ``.dsp`` plus sibling imports from the same directory. Those
files stay one unit through normalize, dedup and the manifest. An
explicit exclusion carries a reason code. ``ffunction`` is the code for
faust-stk files that embed a foreign function; they are not compiled
here.

``schema_version`` is ``t06-inventory.v1``. ``policy`` must name the
2026-10-17 rights defaults. ``generated_at`` is the inventory's clock.
The snapshot digest depends on it only because ``SourceRecord.retrieved_at``
stores it. The run clock is a separate argument and is not read here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from faustcoder.errors import InventoryError

INVENTORY_VERSION = "t06-inventory.v1"
POLICY_ID = "t05-rights-defaults-2026-10-17"
MAX_UNITS = 10_000

_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_IDENT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,80}$")
_REASON = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
FFUNCTION_REASON = "ffunction"
_FUNCTION = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DECISIONS = frozenset({"rights_cleared", "training_only", "vendored", "reject"})
_LABELS = frozenset({"OBSERVED", "INFERRED", "SPECULATIVE"})
_FLAGS = ("train", "eval", "redistribute")
_TOP_KEYS = frozenset({"schema_version", "generated_at", "policy", "units"})
_UNIT_KEYS = frozenset(
    {
        "unit_id",
        "source_id",
        "decision",
        "repo",
        "pin",
        "path",
        "blob_sha",
        "license",
        "eligible_for",
        "evidence_label",
        "attribution",
        "notice",
        "impulse",
        "holdout",
        "training_only",
        "slice",
        "files",
        "upstream_unit_id",
        "reviewer",
        "reason",
    }
)
_NOTICE_KEYS = frozenset({"path", "blob_sha", "copyright", "license"})
_SLICE_KEYS = frozenset({"name", "start_line", "end_line"})
_FILE_KEYS = frozenset({"path", "blob_sha", "role"})
_ROLES = frozenset({"primary", "import"})


@dataclass(frozen=True)
class Notice:
    """License and copyright linkage for one unit. Not the notice bytes."""

    path: str
    blob_sha: str
    copyright: str
    license: str


@dataclass(frozen=True)
class Slice:
    """Function slice. Line numbers refer to LF-normalized file text."""

    name: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class FileMember:
    """One file inside a unit. Imports share the primary file's directory."""

    path: str
    blob_sha: str
    role: str


@dataclass(frozen=True)
class Unit:
    """One inventory row. Program text is not a field.

    ``path`` and ``blob_sha`` are the primary file. ``files`` is the
    whole group, primary first, then imports sorted by path.
    """

    unit_id: str
    source_id: str
    decision: str
    repo: str
    pin: str
    path: str
    blob_sha: str
    files: tuple[FileMember, ...]
    license: str
    eligible_for: tuple[str, ...]
    evidence_label: str
    attribution: str
    notice: Notice | None
    impulse: bool
    holdout: bool
    training_only: bool
    slice: Slice | None
    upstream_unit_id: str | None
    reviewer: str
    reason: str
    generated_at: str


def parse_inventory(document: Mapping[str, Any]) -> tuple[Unit, ...]:
    """Validate and return the units. Raise ``InventoryError`` on a bad document."""
    if not isinstance(document, Mapping):
        raise InventoryError("inventory must be a JSON object")
    extra = set(document) - _TOP_KEYS
    if extra:
        raise InventoryError("inventory has unknown fields")
    if document.get("schema_version") != INVENTORY_VERSION:
        raise InventoryError("unsupported inventory schema_version")
    if document.get("policy") != POLICY_ID:
        raise InventoryError("inventory policy is not the approved defaults")
    generated_at = document.get("generated_at")
    if not isinstance(generated_at, str) or _TIME.fullmatch(generated_at) is None:
        raise InventoryError("generated_at must be a UTC RFC3339 timestamp")
    rows = document.get("units")
    if not isinstance(rows, list) or not rows:
        raise InventoryError("inventory has no units")
    if len(rows) > MAX_UNITS:
        raise InventoryError("inventory exceeds the unit cap")
    units = tuple(_unit(row, generated_at) for row in rows)
    _unique(units)
    return units


def source_uri(unit: Unit) -> str:
    """Return a stable https identifier. Fetching uses the pin and blob sha."""
    base = f"https://github.com/{unit.repo}/blob/{unit.pin}/{unit.path}"
    fragment = f"unit={unit.unit_id}"
    imports = [item.path for item in unit.files if item.role == "import"]
    if imports:
        fragment += "&imports=" + ",".join(imports)
    if unit.slice is not None:
        fragment += (
            f"&fn={unit.slice.name}&lines={unit.slice.start_line}-{unit.slice.end_line}"
        )
    return f"{base}#{fragment}"


def _unit(row: object, generated_at: str) -> Unit:
    if not isinstance(row, Mapping):
        raise InventoryError("unit must be an object")
    extra = set(row) - _UNIT_KEYS
    if extra:
        raise InventoryError("unit has unknown fields")
    unit_id = _ident(row.get("unit_id"), "unit_id")
    decision = row.get("decision")
    if decision not in _DECISIONS:
        raise InventoryError(f"{unit_id}: decision is not a T06 outcome")
    label = row.get("evidence_label")
    if label not in _LABELS:
        raise InventoryError(f"{unit_id}: evidence_label is not a label")
    if label == "SPECULATIVE":
        raise InventoryError(f"{unit_id}: speculative claims are not evidence")
    reason = row.get("reason", "")
    if decision == "reject":
        reason = _reason(row.get("reason"), unit_id)
    elif reason not in ("", None):
        raise InventoryError(f"{unit_id}: reason is only for reject")
    if not isinstance(reason, str):
        raise InventoryError(f"{unit_id}: reason must be a string")
    reviewer = row.get("reviewer", "")
    if reviewer in (None, ""):
        reviewer = ""
    if not isinstance(reviewer, str):
        raise InventoryError(f"{unit_id}: reviewer must be a string")
    if label == "INFERRED" and len(reviewer.strip()) < 3:
        raise InventoryError(f"{unit_id}: an inferred clearance needs a named reviewer")
    upstream = row.get("upstream_unit_id")
    if decision == "vendored":
        upstream = _ident(upstream, f"{unit_id}: upstream_unit_id")
    elif upstream not in (None, ""):
        raise InventoryError(f"{unit_id}: upstream_unit_id is only for vendored units")
    else:
        upstream = None
    files = _files(row, unit_id)
    line_slice = _slice(row.get("slice"), unit_id)
    if line_slice is not None and len(files) != 1:
        raise InventoryError(f"{unit_id}: a function slice is a single file")
    return Unit(
        unit_id=unit_id,
        source_id=_ident(row.get("source_id"), f"{unit_id}: source_id"),
        decision=str(decision),
        repo=_repo(row.get("repo"), unit_id),
        pin=_hex40(row.get("pin"), f"{unit_id}: pin"),
        path=files[0].path,
        blob_sha=files[0].blob_sha,
        files=files,
        license=_short(row.get("license"), f"{unit_id}: license", minimum=1, limit=80),
        eligible_for=_flags(row.get("eligible_for"), unit_id),
        evidence_label=str(label),
        attribution=_short(
            row.get("attribution"), f"{unit_id}: attribution", minimum=0, limit=400
        ),
        notice=_notice(row.get("notice"), unit_id, decision),
        impulse=_bool(row.get("impulse"), f"{unit_id}: impulse"),
        holdout=_bool(row.get("holdout"), f"{unit_id}: holdout"),
        training_only=_bool(row.get("training_only"), f"{unit_id}: training_only"),
        slice=line_slice,
        upstream_unit_id=upstream,
        reviewer=reviewer.strip(),
        reason=reason.strip(),
        generated_at=generated_at,
    )


def _unique(units: tuple[Unit, ...]) -> None:
    seen: set[str] = set()
    whole: set[tuple[str, str, str]] = set()
    slices: set[tuple[str, str, str, str]] = set()
    for unit in units:
        if unit.unit_id in seen:
            raise InventoryError(f"repeated unit_id {unit.unit_id}")
        seen.add(unit.unit_id)
        if unit.slice is not None:
            key = (unit.repo, unit.pin, unit.path, unit.slice.name)
            path_key = (unit.repo, unit.pin, unit.path)
            if key in slices or path_key in whole:
                raise InventoryError(f"{unit.unit_id}: repeated repo, pin, path and slice")
            slices.add(key)
            continue
        for member in unit.files:
            path_key = (unit.repo, unit.pin, member.path)
            if path_key in whole or any(item[:3] == path_key for item in slices):
                raise InventoryError(f"{unit.unit_id}: file {member.path} is already in a unit")
            whole.add(path_key)
    by_id = {unit.unit_id: unit for unit in units}
    for unit in units:
        if unit.upstream_unit_id is None:
            continue
        if unit.upstream_unit_id == unit.unit_id:
            raise InventoryError(f"{unit.unit_id}: vendored unit names itself")
        upstream = by_id.get(unit.upstream_unit_id)
        if upstream is None:
            raise InventoryError(f"{unit.unit_id}: upstream unit is not in the inventory")
        if upstream.decision not in {"rights_cleared", "training_only"}:
            raise InventoryError(f"{unit.unit_id}: upstream unit is not acquired")
        if upstream.holdout:
            raise InventoryError(f"{unit.unit_id}: upstream unit is a sealed holdout")


def _notice(value: object, unit_id: str, decision: str) -> Notice | None:
    acquired = decision in {"rights_cleared", "training_only"}
    if value is None:
        if acquired:
            raise InventoryError(f"{unit_id}: an acquired unit needs notice linkage")
        return None
    if not isinstance(value, Mapping):
        raise InventoryError(f"{unit_id}: notice must be an object")
    if set(value) != _NOTICE_KEYS:
        raise InventoryError(f"{unit_id}: notice fields are incomplete")
    if not acquired:
        raise InventoryError(f"{unit_id}: notice linkage is only for acquired units")
    return Notice(
        path=_path(value.get("path"), f"{unit_id}: notice path"),
        blob_sha=_hex40(value.get("blob_sha"), f"{unit_id}: notice blob_sha"),
        copyright=_short(
            value.get("copyright"), f"{unit_id}: notice copyright", minimum=3, limit=300
        ),
        license=_short(
            value.get("license"), f"{unit_id}: notice license", minimum=1, limit=80
        ),
    )


def _files(row: Mapping[str, Any], unit_id: str) -> tuple[FileMember, ...]:
    raw_files = row.get("files")
    has_path = "path" in row or "blob_sha" in row
    if raw_files is None:
        if not has_path:
            raise InventoryError(f"{unit_id}: a unit needs a path and blob_sha")
        return (
            FileMember(
                path=_path(row.get("path"), unit_id),
                blob_sha=_hex40(row.get("blob_sha"), f"{unit_id}: blob_sha"),
                role="primary",
            ),
        )
    if has_path:
        raise InventoryError(f"{unit_id}: use files or path, not both")
    if not isinstance(raw_files, list) or not raw_files:
        raise InventoryError(f"{unit_id}: files must be a non-empty list")
    members = tuple(_file_member(item, unit_id) for item in raw_files)
    primaries = [item for item in members if item.role == "primary"]
    if len(primaries) != 1:
        raise InventoryError(f"{unit_id}: a unit needs exactly one primary file")
    paths = [item.path for item in members]
    if len(set(paths)) != len(paths):
        raise InventoryError(f"{unit_id}: files repeat a path")
    primary = primaries[0]
    directory = _directory(primary.path)
    if len(members) > 1 and not primary.path.endswith(".dsp"):
        raise InventoryError(f"{unit_id}: a multi-file primary is a .dsp file")
    for item in members:
        if _directory(item.path) != directory:
            raise InventoryError(
                f"{unit_id}: imports must be siblings of the primary file"
            )
    ordered = (primary,) + tuple(
        sorted((item for item in members if item.role == "import"), key=lambda item: item.path)
    )
    return ordered


def _file_member(value: object, unit_id: str) -> FileMember:
    if not isinstance(value, Mapping) or set(value) != _FILE_KEYS:
        raise InventoryError(f"{unit_id}: a file needs path, blob_sha and role")
    role = value.get("role")
    if role not in _ROLES:
        raise InventoryError(f"{unit_id}: file role must be primary or import")
    return FileMember(
        path=_path(value.get("path"), f"{unit_id}: file path"),
        blob_sha=_hex40(value.get("blob_sha"), f"{unit_id}: file blob_sha"),
        role=str(role),
    )


def _directory(path: str) -> str:
    if "/" not in path:
        return ""
    return path.rsplit("/", 1)[0]


def _reason(value: object, unit_id: str) -> str:
    if not isinstance(value, str) or _REASON.fullmatch(value.strip()) is None:
        raise InventoryError(
            f"{unit_id}: an exclusion needs a reason code such as {FFUNCTION_REASON}"
        )
    return value.strip()


def _slice(value: object, unit_id: str) -> Slice | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != _SLICE_KEYS:
        raise InventoryError(f"{unit_id}: slice must name a line range")
    name = value.get("name")
    if not isinstance(name, str) or _FUNCTION.fullmatch(name) is None:
        raise InventoryError(f"{unit_id}: slice name is not a function name")
    start = _line(value.get("start_line"), f"{unit_id}: start_line")
    end = _line(value.get("end_line"), f"{unit_id}: end_line")
    if end < start:
        raise InventoryError(f"{unit_id}: slice end is before the start")
    return Slice(name=name, start_line=start, end_line=end)


def _flags(value: object, unit_id: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(isinstance(item, bool) or not isinstance(item, str) for item in value):
        raise InventoryError(f"{unit_id}: eligible_for must be a list of flags")
    if len(set(value)) != len(value):
        raise InventoryError(f"{unit_id}: eligible_for repeats a flag")
    unknown = [item for item in value if item not in _FLAGS]
    if unknown:
        raise InventoryError(f"{unit_id}: eligible_for has an unknown flag")
    return tuple(flag for flag in _FLAGS if flag in value)


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise InventoryError(f"{field} must be a boolean")
    return value


def _line(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise InventoryError(f"{field} must be a positive integer")
    return value


def _ident(value: object, field: str) -> str:
    if not isinstance(value, str) or _IDENT.fullmatch(value) is None:
        raise InventoryError(f"{field} is not a unit id")
    return value


def _hex40(value: object, field: str) -> str:
    if not isinstance(value, str) or _HEX40.fullmatch(value) is None:
        raise InventoryError(f"{field} must be 40 lowercase hex characters")
    return value


def _repo(value: object, unit_id: str) -> str:
    if not isinstance(value, str) or value.count("/") != 1:
        raise InventoryError(f"{unit_id}: repo must be owner/name")
    owner, name = value.split("/")
    if not owner or not name or owner in {".", ".."} or name in {".", ".."}:
        raise InventoryError(f"{unit_id}: repo must be owner/name")
    if any(char in ":?#%@\\" or ord(char) < 32 for char in value):
        raise InventoryError(f"{unit_id}: repo must be owner/name")
    return value


def _path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        raise InventoryError(f"{field} must be a relative path")
    if "\\" in value or any(ord(char) < 32 or char in ":?#%" for char in value):
        raise InventoryError(f"{field} must be a relative path")
    parts = value.split("/")
    if any(part in ("", ".", "..") or part.startswith("-") for part in parts):
        raise InventoryError(f"{field} must be a relative path")
    return value


def _short(value: object, field: str, *, minimum: int, limit: int = 200) -> str:
    if not isinstance(value, str):
        raise InventoryError(f"{field} must be a string")
    text = value.strip()
    if len(text) < minimum or len(text) > limit or any(ord(char) < 32 for char in text):
        raise InventoryError(f"{field} is missing or too long")
    return text

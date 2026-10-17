"""Shared builders for T06 tests. Not collected by pytest."""

from __future__ import annotations

from pathlib import Path

from faustcoder.acquire import git_blob_sha1

PIN = "a" * 40
PIN_B = "b" * 40
REPO = "acme/widgets"
NOTICE_TEXT = b"Copyright (c) 2026 Acme Example. MIT License.\n"
COPYRIGHT = "Copyright (c) 2026 Acme Example"
GENERATED_AT = "2026-10-17T13:04:00Z"
CREATED_AT = "2026-10-17T20:00:00Z"
ACTOR = "snapshot-bot"


def blob(data: bytes) -> str:
    return git_blob_sha1(data)


def notice_ref(data: bytes = NOTICE_TEXT) -> dict[str, str]:
    return {
        "path": "NOTICE",
        "blob_sha": blob(data),
        "copyright": COPYRIGHT,
        "license": "MIT",
    }


def unit(
    unit_id: str,
    data: bytes,
    *,
    path: str | None = None,
    decision: str = "rights_cleared",
    license_name: str = "MIT",
    eligible_for: list[str] | None = None,
    training_only: bool = False,
    impulse: bool = False,
    holdout: bool = False,
    pin: str = PIN,
    repo: str = REPO,
    evidence_label: str = "OBSERVED",
    reviewer: str = "",
    reason: str = "",
    upstream_unit_id: str | None = None,
    notice: dict[str, str] | None = None,
    files: list[dict[str, str]] | None = None,
    line_slice: dict[str, object] | None = None,
    source_id: str | None = None,
) -> dict[str, object]:
    """One inventory row. ``files`` replaces path and blob_sha."""
    row: dict[str, object] = {
        "unit_id": unit_id,
        "source_id": source_id or f"src-{unit_id}",
        "decision": decision,
        "repo": repo,
        "pin": pin,
        "license": license_name,
        "eligible_for": ["train", "eval", "redistribute"]
        if eligible_for is None
        else eligible_for,
        "evidence_label": evidence_label,
        "attribution": "Acme Example",
        "impulse": impulse,
        "holdout": holdout,
        "training_only": training_only,
        "reviewer": reviewer,
    }
    if files is None:
        row["path"] = path or f"{unit_id}.dsp"
        row["blob_sha"] = blob(data)
    else:
        row["files"] = files
    if decision in {"rights_cleared", "training_only"}:
        row["notice"] = notice if notice is not None else notice_ref()
    if line_slice is not None:
        row["slice"] = line_slice
    if upstream_unit_id is not None:
        row["upstream_unit_id"] = upstream_unit_id
    if reason:
        row["reason"] = reason
    return row


def inventory(
    units: list[dict[str, object]], generated_at: str = GENERATED_AT
) -> dict[str, object]:
    return {
        "schema_version": "t06-inventory.v1",
        "generated_at": generated_at,
        "policy": "t05-rights-defaults-2026-10-17",
        "units": units,
    }


def stage(root: Path, repo: str, pin: str, path: str, data: bytes) -> str:
    """Write one fixture blob and return its git blob sha."""
    target = root.joinpath(*repo.split("/"), pin, *path.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return blob(data)


def stage_notice(root: Path, pin: str = PIN, repo: str = REPO) -> None:
    stage(root, repo, pin, "NOTICE", NOTICE_TEXT)


def long_text(prefix: str, count: int = 60, replacement: str | None = None) -> str:
    """A token stream long enough for the near-duplicate threshold."""
    words = [f"{prefix}{index}" for index in range(count)]
    if replacement is not None:
        words[-1] = replacement
    return " ".join(words) + "\n"

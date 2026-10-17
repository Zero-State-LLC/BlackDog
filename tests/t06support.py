"""Shared builders for T06 tests. Not collected by pytest."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from faustcoder.acquire import git_blob_sha1
from faustcoder.inventory import content_digest, parse_corpus

PIN = "a" * 40
PIN_B = "b" * 40
REPO = "acme/widgets"
COPYRIGHT = "Copyright (c) 2026 Acme Example"
GENERATED_AT = "2026-10-17T13:04:00Z"
CREATED_AT = "2026-10-17T20:00:00Z"
ACTOR = "snapshot-bot"
REVIEWER = "Boof (delegated by Danny 2026-10-17)"


def blob(data: bytes) -> str:
    return git_blob_sha1(data)


def entry(
    entry_id: str,
    data: bytes,
    *,
    path: str | None = None,
    decision: str = "rights_cleared",
    license_name: str = "MIT",
    eligible_for: list[str] | None = None,
    pin: str = PIN,
    repo: str = REPO,
    evidence_label: str = "OBSERVED",
    reviewer: str = REVIEWER,
    reason: str = "",
    function: str = "",
    attribution: str = "Acme Example",
) -> dict[str, object]:
    """One T05 inventory entry for a single file or function."""
    path = path or f"{entry_id}.dsp"
    spec: dict[str, object] = {"path": path, "blob_sha": blob(data)}
    row: dict[str, object] = {
        "id": entry_id,
        "decision": decision,
        "license": license_name,
        "eligible_for": ["train", "eval", "redistribute"]
        if eligible_for is None
        else eligible_for,
        "pin": {"repo": repo, "commit": pin, "ref": "fixture"},
        "evidence_label": evidence_label,
        "attribution": attribution,
        "reviewer": reviewer,
        "reason": reason or "cleared row",
        "evidence_uri": f"https://example.com/rights/{entry_id}",
        "url": f"https://example.com/rights/{entry_id}",
        "file_count": 1,
    }
    if function:
        spec["function"] = function
        row["functions"] = [spec]
    else:
        row["files"] = [spec]
    return row


def notice_row(
    data: bytes,
    *,
    path: str,
    license_name: str = "MIT",
    function: str = "",
    pin: str = PIN,
    repo: str = REPO,
    copyright_text: str = COPYRIGHT,
) -> dict[str, object]:
    """One notice-manifest row. ``function`` is null for a whole file."""
    return {
        "repo": repo,
        "commit": pin,
        "path": path,
        "blob_sha": blob(data),
        "function": function or None,
        "copyright": copyright_text,
        "license": license_name,
        "evidence_label": "OBSERVED",
    }


def cleared(
    entry_id: str,
    data: bytes,
    **kwargs: object,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return a cleared entry and the notice row that matches it."""
    options = dict(kwargs)
    path = str(options.pop("path", None) or f"{entry_id}.dsp")
    license_name = str(options.get("license_name") or "MIT")
    function = str(options.get("function") or "")
    pin = str(options.get("pin") or PIN)
    repo = str(options.get("repo") or REPO)
    built = entry(entry_id, data, path=path, **options)  # type: ignore[arg-type]
    notice = notice_row(
        data,
        path=path,
        license_name=license_name,
        function=function,
        pin=pin,
        repo=repo,
    )
    return built, notice


def inventory_doc(
    entries: list[dict[str, object]], generated_at: str = GENERATED_AT
) -> dict[str, object]:
    return {
        "schema_version": "rights-inventory.v1",
        "generated_at": generated_at,
        "method": "fixture",
        "policy": "t05-rights-defaults-2026-10-17",
        "entries": entries,
    }


def notice_doc(
    rows: list[dict[str, object]], generated_at: str = GENERATED_AT
) -> dict[str, object]:
    return {
        "schema_version": "notice-manifest.v1",
        "generated_at": generated_at,
        "entries": rows,
    }


@contextmanager
def pins_for(
    inventory: Mapping[str, Any], notice: Mapping[str, Any]
) -> Iterator[None]:
    """Point the production digest pins at one fixture corpus for a test."""
    import faustcoder.inventory as inventory_mod

    saved = (
        inventory_mod.PINNED_INVENTORY_DIGEST,
        inventory_mod.PINNED_NOTICE_DIGEST,
    )
    inventory_mod.PINNED_INVENTORY_DIGEST = content_digest(inventory)
    inventory_mod.PINNED_NOTICE_DIGEST = content_digest(notice)
    try:
        yield
    finally:
        (
            inventory_mod.PINNED_INVENTORY_DIGEST,
            inventory_mod.PINNED_NOTICE_DIGEST,
        ) = saved


def parse_pinned(inventory: Mapping[str, Any], notice: Mapping[str, Any]):
    """Parse a fixture corpus against its own content digests."""
    with pins_for(inventory, notice):
        return parse_corpus(inventory, notice)


def stage(root: Path, repo: str, pin: str, path: str, data: bytes) -> str:
    """Write one fixture blob and return its git blob sha."""
    target = root.joinpath(*repo.split("/"), pin, *path.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return blob(data)


def long_text(prefix: str, count: int = 60, replacement: str | None = None) -> str:
    """A token stream long enough for the near-duplicate threshold."""
    words = [f"{prefix}{index}" for index in range(count)]
    if replacement is not None:
        words[-1] = replacement
    return " ".join(words) + "\n"

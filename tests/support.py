"""Shared builders for artifact-store tests. Not a test module."""

from __future__ import annotations

from typing import Any

from faustcoder import build_envelope

HEX_A = "0123456789abcdef" * 4
HEX_B = "fedcba9876543210" * 4
DIGEST_A = "sha256:" + HEX_A
DIGEST_B = "sha256:" + HEX_B


def make_envelope(
    payload: dict[str, Any],
    parents: list[str] | tuple[str, ...] = (),
    **overrides: Any,
) -> dict[str, Any]:
    """Return an envelope whose id matches ``payload``."""
    fields: dict[str, Any] = {
        "schema_version": "0.3.0",
        "created_at": "2026-10-17T00:00:00Z",
        "producer": "t02-test",
        "parents": list(parents),
        "payload": payload,
    }
    fields.update(overrides)
    return build_envelope(
        schema_version=fields["schema_version"],
        created_at=fields["created_at"],
        producer=fields["producer"],
        parents=fields["parents"],
        payload=fields["payload"],
    )

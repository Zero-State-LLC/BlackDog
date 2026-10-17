"""2026-10-17 rights defaults. Unknown spellings abort; they are not guessed."""

from __future__ import annotations

import pytest

from faustcoder.errors import InventoryError, PolicyError
from faustcoder.inventory import parse_inventory
from faustcoder.policy import check_unit

from tests.t06support import inventory, unit


def _check(**kwargs: object) -> None:
    data = kwargs.pop("data", b"process = 1;\n")
    row = unit("osc", data, **kwargs)  # type: ignore[arg-type]
    check_unit(parse_inventory(inventory([row]))[0])


def test_bare_bsd_refuses_redistribution() -> None:
    with pytest.raises(PolicyError, match="looser"):
        _check(
            license_name="BSD",
            eligible_for=["train", "eval", "redistribute"],
        )
    _check(license_name="BSD", eligible_for=["train", "eval"], training_only=False)


def test_stk_clears_with_notice_and_refuses_a_missing_notice() -> None:
    _check(license_name="STK-4.3")
    row = unit("osc", b"process = 1;\n", license_name="STK-4.3")
    del row["notice"]
    with pytest.raises(InventoryError, match="notice"):
        parse_inventory(inventory([row]))


def test_gpl_eval_agpl_and_unrecognized_are_refused() -> None:
    with pytest.raises(PolicyError, match="looser"):
        _check(
            decision="training_only",
            license_name="GPL-3.0-only",
            eligible_for=["train", "eval"],
            training_only=False,
        )
    _check(
        decision="training_only",
        license_name="GPL-3.0-only",
        eligible_for=["train"],
        training_only=True,
    )
    with pytest.raises(PolicyError, match="cannot be acquired"):
        _check(license_name="AGPL-3.0-only", eligible_for=["train"], training_only=True)
    with pytest.raises(PolicyError, match="cannot be acquired"):
        _check(license_name="WTFPL")


def test_impulse_and_training_only_flags() -> None:
    with pytest.raises(PolicyError, match="impulse"):
        _check(
            decision="rights_cleared",
            impulse=True,
            eligible_for=["train", "eval"],
            training_only=False,
        )
    with pytest.raises(PolicyError, match="impulse"):
        _check(
            decision="training_only",
            impulse=True,
            holdout=True,
            eligible_for=["train"],
            training_only=True,
        )
    _check(
        decision="training_only",
        impulse=True,
        eligible_for=["train"],
        training_only=True,
    )
    with pytest.raises(PolicyError, match="training_only"):
        _check(eligible_for=["train"], training_only=False)


def test_inferred_needs_a_reviewer_and_speculative_is_refused() -> None:
    with pytest.raises(InventoryError, match="reviewer"):
        parse_inventory(
            inventory(
                [unit("osc", b"process = 1;\n", evidence_label="INFERRED", reviewer="")]
            )
        )
    _check(evidence_label="INFERRED", reviewer="Danny")
    with pytest.raises(InventoryError, match="speculative"):
        parse_inventory(
            inventory([unit("osc", b"process = 1;\n", evidence_label="SPECULATIVE")])
        )


def test_reject_requires_a_reason_code() -> None:
    with pytest.raises(InventoryError, match="reason"):
        parse_inventory(
            inventory(
                [
                    unit(
                        "stk",
                        b"",
                        decision="reject",
                        eligible_for=[],
                        license_name="unknown",
                    )
                ]
            )
        )
    parsed = parse_inventory(
        inventory(
            [
                unit(
                    "stk",
                    b"",
                    decision="reject",
                    eligible_for=[],
                    license_name="unknown",
                    reason="ffunction",
                )
            ]
        )
    )
    assert parsed[0].reason == "ffunction"
    check_unit(parsed[0])

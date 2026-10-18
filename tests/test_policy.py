"""2026-10-17 license table, and T05 inventory admission. Not a second guard."""

from __future__ import annotations

import pytest

from faustcoder.errors import InventoryError
from faustcoder.policy import license_class, maximum_flags

from tests.t06support import entry, inventory_doc, notice_doc, notice_row, parse_pinned


def test_license_table_records_the_2026_10_17_defaults() -> None:
    assert maximum_flags("MIT") == frozenset({"train", "eval", "redistribute"})
    assert maximum_flags("STK-4.3") == frozenset({"train", "eval", "redistribute"})
    assert maximum_flags("BSD") == frozenset({"train", "eval"})
    assert "redistribute" not in (maximum_flags("BSD") or set())
    assert maximum_flags("GPL-3.0-only") == frozenset({"train"})
    assert maximum_flags("AGPL-3.0-only") is None
    assert maximum_flags("WTFPL") is None
    assert license_class("BSD") == "bare_bsd"
    assert license_class("GPL-2.0-or-later") == "train_only"
    assert license_class("AGPL-3.0-only") == "excluded"
    assert license_class("WTFPL") == "unrecognized"


def test_inferred_clearance_needs_a_reviewer_and_speculative_is_refused() -> None:
    data = b"process = 1;\n"
    row = entry("osc", data, path="osc.dsp", evidence_label="INFERRED", reviewer="")
    notice = notice_row(data, path="osc.dsp")
    with pytest.raises(InventoryError, match="reviewer"):
        parse_pinned(inventory_doc([row]), notice_doc([notice]))
    named = entry(
        "osc",
        data,
        path="osc.dsp",
        evidence_label="INFERRED",
        reviewer="Danny",
    )
    corpus = parse_pinned(inventory_doc([named]), notice_doc([notice]))
    assert corpus.units[0].reviewer == "Danny"
    speculative = entry("osc", data, path="osc.dsp", evidence_label="SPECULATIVE")
    with pytest.raises(InventoryError, match="label"):
        parse_pinned(inventory_doc([speculative]), notice_doc([notice]))


def test_rejected_and_needs_human_rows_are_not_admitted() -> None:
    data = b"process = 1;\n"
    rejected = entry(
        "stk",
        data,
        path="foreign.dsp",
        decision="rights_rejected",
        eligible_for=[],
        license_name="unknown",
        reason="ffunction",
        reviewer="",
    )
    human = entry(
        "gap",
        data,
        path="gap.dsp",
        decision="needs_human",
        eligible_for=[],
        license_name="unknown",
        reason="copyright only",
        reviewer="",
    )
    corpus = parse_pinned(inventory_doc([rejected, human]), notice_doc([]))
    assert corpus.units == ()
    reasons = {item.entry_id: item.reason for item in corpus.excluded}
    assert reasons == {"stk": "ffunction", "gap": "copyright only"}

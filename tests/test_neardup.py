"""Near-duplicate shingles, and the exact-hash family they do not replace."""

from __future__ import annotations

from faustcoder.neardup import (
    cluster_families,
    is_near_duplicate,
    memorization_hits,
    strip_comments,
    tokens,
)

from tests.t06support import long_text


def test_comments_are_stripped_and_strings_stay() -> None:
    source = 'declare name "/* stay */"; // gone\nprocess = 1; /* gone */\n'
    assert "gone" not in strip_comments(source)
    assert "stay" in strip_comments(source)
    assert "ffunction" not in tokens("// ffunction\nprocess = 1;\n")


def test_short_boilerplate_is_not_a_near_duplicate() -> None:
    short = 'import("stdfaust.lib");\nprocess = os.osc(440);\n'
    assert is_near_duplicate(short, short) is False


def test_long_similar_texts_cluster_and_dissimilar_texts_do_not() -> None:
    left = long_text("alpha")
    close = long_text("alpha", replacement="renamed")
    other = long_text("omega")
    assert is_near_duplicate(left, close) is True
    assert is_near_duplicate(left, other) is False
    families = cluster_families([("left", left), ("close", close), ("other", other)])
    assert families["left"] == families["close"]
    assert families["left"] != families["other"]
    swapped = cluster_families([("other", other), ("close", close), ("left", left)])
    assert swapped["left"] == families["left"]


def test_exact_short_texts_share_a_family_without_being_near_duplicates() -> None:
    text = "process = 1;\n"
    assert is_near_duplicate(text, text) is False
    families = cluster_families([("a", text), ("b", text)])
    assert families["a"] == families["b"]


def test_memorization_hits_reports_the_corpus_id() -> None:
    left = long_text("alpha")
    close = long_text("alpha", replacement="renamed")
    other = long_text("omega")
    hits = memorization_hits(close, [("sealed", left), ("other", other)])
    assert [hit[0] for hit in hits] == ["sealed"]
    assert hits[0][1] > 0
    assert memorization_hits("process = 1;\n", [("sealed", left)]) == ()

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


def test_short_texts_use_the_character_fallback() -> None:
    """Under 40 tokens, a one-token edit matches and a different call shape does not.

    Both programs are shorter than 32 non-space characters, so the
    fallback requires an equal identifier-and-number skeleton and a
    character 5-gram Jaccard of at least 1/3. ``fi.lowpass`` keeps the
    skeleton and still falls under that fraction.
    """
    original = "process = os.osc(440);"
    edited = "process = os.osc(441);"
    renamed = "process = os.sine(440);"
    other = "process = fi.lowpass(2);"
    noise = "process = no.noise;"
    assert is_near_duplicate(original, edited) is True
    assert is_near_duplicate(original, renamed) is True
    assert is_near_duplicate(original, other) is False
    assert is_near_duplicate(original, noise) is False
    families = cluster_families(
        [("sealed", original), ("edited", edited), ("other", other)]
    )
    assert families["sealed"] == families["edited"]
    assert families["sealed"] != families["other"]
    hits = memorization_hits(edited, [("sealed", original), ("other", other)])
    assert [hit[0] for hit in hits] == ["sealed"]


def test_memorization_hits_reports_the_corpus_id() -> None:
    left = long_text("alpha")
    close = long_text("alpha", replacement="renamed")
    other = long_text("omega")
    hits = memorization_hits(close, [("sealed", left), ("other", other)])
    assert [hit[0] for hit in hits] == ["sealed"]
    assert hits[0][1] > 0
    assert memorization_hits("process = 1;\n", [("sealed", left)]) == ()

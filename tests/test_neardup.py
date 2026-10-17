"""Near-duplicate shingles, and the exact-hash family they do not replace."""

from __future__ import annotations

from faustcoder.neardup import (
    char_shingles,
    cluster_families,
    is_excerpt,
    is_near_duplicate,
    jaccard_counts,
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


def test_half_excerpt_is_not_a_jaccard_near_duplicate() -> None:
    """A 50% verbatim excerpt fails Jaccard 4/5 and is still an excerpt."""
    whole = long_text("lib", count=80)
    excerpt = " ".join(whole.split()[:40]) + "\n"
    assert is_near_duplicate(excerpt, whole) is False
    assert is_excerpt(excerpt, whole) is True
    assert is_excerpt(whole, excerpt) is False
    families = cluster_families(
        [("cleared", excerpt), ("rejected", whole), ("other", long_text("omega"))],
        ["rejected"],
    )
    assert families["cleared"] == families["rejected"]
    assert families["other"] != families["rejected"]
    untouched = cluster_families([("cleared", excerpt), ("rejected", whole)])
    assert untouched["cleared"] != untouched["rejected"]


def test_containment_threshold_is_one_half() -> None:
    shared = [f"shared{index}" for index in range(22)]
    part = " ".join(shared + [f"part{index}" for index in range(18)]) + "\n"
    whole = " ".join(shared + [f"whole{index}" for index in range(40)]) + "\n"
    short_share = [f"shared{index}" for index in range(21)]
    below = " ".join(short_share + [f"part{index}" for index in range(19)]) + "\n"
    assert is_excerpt(part, whole) is True
    assert is_excerpt(below, whole) is False


def test_verbatim_run_catches_a_statement_inside_a_larger_file() -> None:
    statement = long_text("stmt", count=40).split()
    cleared = " ".join(
        [f"head{index}" for index in range(80)]
        + statement
        + [f"tail{index}" for index in range(80)]
    )
    rejected = " ".join(
        [f"lib{index}" for index in range(100)]
        + statement
        + [f"end{index}" for index in range(100)]
    )
    assert is_near_duplicate(cleared, rejected) is False
    assert is_excerpt(cleared, rejected) is True


def test_exact_short_program_is_a_memorization_hit() -> None:
    text = "process = 1;\n"
    other = "process = no.noise;\n"
    hits = memorization_hits(text, [("sealed", text), ("other", other)])
    assert [hit[0] for hit in hits] == ["sealed"]
    assert hits[0][1] == hits[0][2] > 0


def test_short_hit_reports_character_shingles() -> None:
    original = "process = os.osc(440);"
    edited = "process = os.osc(441);"
    hits = memorization_hits(edited, [("sealed", original)])
    intersection, union = jaccard_counts(
        char_shingles(edited), char_shingles(original)
    )
    assert hits == (("sealed", intersection, union),)


def test_memorization_hits_reports_the_corpus_id() -> None:
    left = long_text("alpha")
    close = long_text("alpha", replacement="renamed")
    other = long_text("omega")
    hits = memorization_hits(close, [("sealed", left), ("other", other)])
    assert [hit[0] for hit in hits] == ["sealed"]
    assert hits[0][1] > 0
    assert memorization_hits("process = 1;\n", [("sealed", left)]) == ()

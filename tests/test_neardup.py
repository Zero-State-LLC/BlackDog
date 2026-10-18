"""Near-duplicate shingles, and the exact-hash family they do not replace."""

from __future__ import annotations

from faustcoder.neardup import (
    MIN_TOKENS,
    TOKEN_FLOOR,
    TOKEN_FLOOR_STATUS,
    VERBATIM_RUN,
    char_shingles,
    cluster_families,
    containment_at_least,
    has_verbatim_run,
    is_excerpt,
    is_near_duplicate,
    jaccard_counts,
    memorization_hits,
    shingles,
    strip_comments,
    tokens,
)

from tests.t06support import long_text


def test_token_floor_is_one_constant() -> None:
    """Jaccard, containment, and the verbatim run share ``TOKEN_FLOOR``."""
    assert TOKEN_FLOOR == 40
    assert TOKEN_FLOOR_STATUS == "provisional"
    assert MIN_TOKENS == TOKEN_FLOOR
    assert VERBATIM_RUN == TOKEN_FLOOR


def _words(count: int, prefix: str) -> list[str]:
    return [f"{prefix}{index}" for index in range(count)]


def _rejected_347(*, edit: bool) -> str:
    """347 tokens, one literal changed every 34 when ``edit`` is set."""
    words = _words(347, "w")
    if edit:
        index = 17
        while index < 347:
            words[index] = f"edited{index}"
            index += 34
    return " ".join(words) + "\n"


def _interleave_statements(rejected: str) -> str:
    words = rejected.split()
    parts: list[str] = []
    own = 0
    for start in range(0, len(words), 34):
        parts.append(" ".join(words[start : start + 34]))
        if start + 34 < len(words):
            parts.append(" ".join(_words(40, f"own{own}_")))
            own += 40
    return " ".join(parts) + "\n"


def _forward_excerpt(cleared: str, rejected: str) -> bool:
    """The pre-r5 check: a run, or half of the cleared shingles in the rejected text."""
    cleared_tokens = tokens(cleared)
    rejected_tokens = tokens(rejected)
    if len(cleared_tokens) < TOKEN_FLOOR:
        return False
    if has_verbatim_run(cleared_tokens, rejected_tokens):
        return True
    return containment_at_least(shingles(cleared_tokens), shingles(rejected_tokens))


def test_reverse_containment_catches_padded_and_interleaved_copies() -> None:
    """A 347-token rejected file stays inside a cleared file that edits or interleaves it.

    The unpadded edit is the control: forward containment already holds.
    Padding at 1.0x and 1.6x, and interleaving verbatim statements with
    the cleared file's own code, keep the forward ratio under 1/2 and
    break every 40-token run. Reverse containment still quarantines.
    """
    rejected = _rejected_347(edit=False)
    edited = _rejected_347(edit=True)
    pad_1 = edited.strip() + " " + " ".join(_words(347, "pad"))
    pad_16 = edited.strip() + " " + " ".join(_words((347 * 8) // 5, "wide"))
    interleaved = _interleave_statements(rejected)
    assert len(tokens(rejected)) == 347
    assert _forward_excerpt(edited, rejected) is True
    assert is_excerpt(edited, rejected) is True
    cases = {
        "pad-1.0": pad_1,
        "pad-1.6": pad_16,
        "interleaved": interleaved,
    }
    for name, cleared in cases.items():
        assert has_verbatim_run(tokens(cleared), tokens(rejected)) is False, name
        assert _forward_excerpt(cleared, rejected) is False, name
        assert containment_at_least(shingles(tokens(rejected)), shingles(tokens(cleared))), name
        assert is_excerpt(cleared, rejected) is True, name
        families = cluster_families(
            [("cleared", cleared), ("rejected", rejected), ("other", long_text("omega"))],
            ["rejected"],
        )
        assert families["cleared"] == families["rejected"], name
        assert families["other"] != families["rejected"], name
    control = cluster_families(
        [("cleared", edited), ("rejected", rejected), ("other", long_text("omega"))],
        ["rejected"],
    )
    assert control["cleared"] == control["rejected"]
    assert control["other"] != control["rejected"]


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
    # The run counts when the cleared file is the longer one. The
    # allowlist, not this predicate, keeps an upstream original.
    assert is_excerpt(whole, excerpt) is True
    families = cluster_families(
        [("cleared", excerpt), ("rejected", whole), ("other", long_text("omega"))],
        ["rejected"],
    )
    assert families["cleared"] == families["rejected"]
    assert families["other"] != families["rejected"]
    vendored = cluster_families(
        [("cleared", whole), ("rejected", excerpt), ("other", long_text("omega"))],
        ["rejected"],
    )
    assert vendored["cleared"] == vendored["rejected"]
    assert vendored["other"] != vendored["rejected"]
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


def test_vendored_rejected_file_plus_padding_is_an_excerpt() -> None:
    """Rejected R plus twice as much padding shares a 40-token run."""
    rejected = long_text("rejected", count=80)
    cleared = rejected.strip() + " " + long_text("pad", count=160)
    part = shingles(tokens(cleared))
    whole = shingles(tokens(rejected))
    assert len(tokens(rejected)) == 80
    assert len(tokens(cleared)) == 240
    assert containment_at_least(part, whole) is False
    assert is_near_duplicate(cleared, rejected) is False
    assert is_excerpt(cleared, rejected) is True
    families = cluster_families(
        [("cleared", cleared), ("rejected", rejected), ("other", long_text("omega"))],
        ["rejected"],
    )
    assert families["cleared"] == families["rejected"]
    assert families["other"] != families["rejected"]


def test_rejected_text_under_forty_tokens_is_not_an_excerpt() -> None:
    """At the operating floor, a 36-token rejected function is not an excerpt."""
    rejected = long_text("fn", count=36)
    cleared = rejected.strip() + " " + long_text("own", count=80)
    assert is_excerpt(cleared, rejected) is False
    assert is_near_duplicate(cleared, rejected) is False
    families = cluster_families(
        [("cleared", cleared), ("rejected", rejected)],
        ["rejected"],
    )
    assert families["cleared"] != families["rejected"]


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

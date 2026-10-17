"""Token n-gram near-duplicate comparison (task T06).

T07 leakage checks and the proposed output memorization gate import
this module. Both call ``memorization_hits`` or ``is_near_duplicate``.
The snapshot clusterer calls ``cluster_families``.

Algorithm (INFERRED; spec §4.2 forbids a Faust parser, so this is not
an AST shingle):

- Strip ``//`` and ``/* */`` comments outside double-quoted strings.
- Tokenize identifiers, numbers and single-character operators.
- Build a set of 5-token shingles.
- A pair is a near-duplicate when each side has at least
  ``TOKEN_FLOOR`` tokens and the Jaccard index is at least 4/5.
- The comparison is integer: ``intersection * 5 >= union * 4``.
  A reported float is not the decision.
- Jaccard is symmetric, so a verbatim excerpt of a rejected file
  stays under 4/5. An excerpt check is separate:
  ``|shingles(part) ∩ shingles(whole)| / |shingles(part)| >= 1/2``,
  or a contiguous run of ``TOKEN_FLOOR`` tokens appears in both.
  The run counts when the cleared file is the longer one. The part
  must still have at least ``TOKEN_FLOOR`` tokens.
  ``cluster_families`` applies that only from a non-comparison text
  into a comparison text.

``TOKEN_FLOOR`` is the single length constant for that minimum and
for the verbatim run. It is 40. That value is the operating floor,
not an accepted clearance policy. The measurement is
``docs/analysis/t06-short-kernel-floor.md``. Below the floor, shared
Faust boilerplate (``declare``, ``import``, ``process``) dominates
the shingles and unrelated programs look alike. Exact normalized-hash
equality is a separate pass and still clusters short texts.

Family ids are ``sha256:`` of the canonical JSON array of the sorted
unique normalized digests in the component. The id does not depend on
unit ids or comparison order.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Collection, Iterable, Sequence

from faustcoder.canonical import canonical_bytes, sha256_prefixed

NGRAM_N = 5
THRESHOLD_NUMERATOR = 4
THRESHOLD_DENOMINATOR = 5
# Single length constant. Jaccard, excerpt containment, and the
# verbatim run all use it. Not an accepted clearance policy.
TOKEN_FLOOR = 40
MIN_TOKENS = TOKEN_FLOOR
VERBATIM_RUN = TOKEN_FLOOR
# Asymmetric excerpt check. Jaccard 4/5 misses a half-file copy
# (INFERRED).
CONTAINMENT_NUMERATOR = 1
CONTAINMENT_DENOMINATOR = 2
# Short texts never reach the token shingles. A character 5-gram
# fallback covers them. Jaccard is still an integer compare.
# Texts of at least 32 non-space characters match at 4/5.
# Shorter texts match only when identifier-and-number skeletons are
# equal and the character Jaccard is at least 1/3, so a one-token
# rename of a tiny program is a near-duplicate and a different call
# shape is not. (INFERRED.)
CHAR_N = 5
CHAR_MIN_LENGTH = 32
CHAR_NUMERATOR = 4
CHAR_DENOMINATOR = 5
SHORT_SKELETON_NUMERATOR = 1
SHORT_SKELETON_DENOMINATOR = 3
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_STRING = re.compile(r'"[^"]*"')

_TOKEN = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+(?:\.[0-9]+)?|==|!=|<=|>=|&&|\|\||[^\s]"
)


def strip_comments(source: str) -> str:
    """Remove Faust comments, leaving string literals in place."""
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    out: list[str] = []
    index = 0
    length = len(source)
    while index < length:
        char = source[index]
        if char == '"':
            end = index + 1
            while end < length:
                if source[end] == "\\":
                    end += 2
                    continue
                if source[end] == '"':
                    end += 1
                    break
                end += 1
            out.append(source[index:end])
            index = end
            continue
        if char == "/" and index + 1 < length and source[index + 1] == "/":
            index += 2
            while index < length and source[index] != "\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and source[index + 1] == "*":
            index += 2
            while index + 1 < length and source[index : index + 2] != "*/":
                index += 1
            index = min(length, index + 2)
            continue
        out.append(char)
        index += 1
    return "".join(out)


def tokens(source: str) -> tuple[str, ...]:
    """Return the comment-stripped token sequence."""
    return tuple(_TOKEN.findall(strip_comments(source)))


def shingles(token_list: Sequence[str], n: int = NGRAM_N) -> frozenset[str]:
    """Return the set of ``n``-token shingles. Short inputs yield an empty set."""
    if n < 1:
        raise ValueError("n must be positive")
    if len(token_list) < n:
        return frozenset()
    return frozenset(
        "\0".join(token_list[index : index + n])
        for index in range(len(token_list) - n + 1)
    )


def jaccard_counts(
    left: frozenset[str], right: frozenset[str]
) -> tuple[int, int]:
    """Return ``(intersection, union)``. Empty inputs are ``(0, 0)``."""
    if not left and not right:
        return (0, 0)
    intersection = len(left & right)
    union = len(left | right)
    return (intersection, union)


def jaccard_at_least(
    left: frozenset[str],
    right: frozenset[str],
    numerator: int = THRESHOLD_NUMERATOR,
    denominator: int = THRESHOLD_DENOMINATOR,
) -> bool:
    """Return whether ``|A∩B| / |A∪B| >= numerator / denominator``."""
    if denominator < 1 or numerator < 0 or numerator > denominator:
        raise ValueError("threshold fraction is out of range")
    intersection, union = jaccard_counts(left, right)
    if union == 0:
        return False
    return intersection * denominator >= union * numerator


def _compact(source: str) -> str:
    return "".join(strip_comments(source).split())


def _skeleton(source: str) -> str:
    """Collapse strings, identifiers and numbers so a rename can match."""
    compact = _compact(source)
    compact = _STRING.sub('"s"', compact)
    compact = _IDENT.sub("id", compact)
    return _NUMBER.sub("n", compact)


def char_shingles(source: str, n: int = CHAR_N) -> frozenset[str]:
    """Return character n-grams of the comment-stripped, spaceless text."""
    compact = _compact(source)
    if len(compact) < n:
        return frozenset()
    return frozenset(compact[index : index + n] for index in range(len(compact) - n + 1))


def short_near_duplicate(left: str, right: str) -> bool:
    """Near-duplicate fallback for texts under ``TOKEN_FLOOR``.

    Identical texts return ``False``. The exact-hash pass owns those.
    """
    if left == right:
        return False
    left_compact = _compact(left)
    right_compact = _compact(right)
    if len(left_compact) >= CHAR_MIN_LENGTH and len(right_compact) >= CHAR_MIN_LENGTH:
        return jaccard_at_least(
            char_shingles(left),
            char_shingles(right),
            CHAR_NUMERATOR,
            CHAR_DENOMINATOR,
        )
    if _skeleton(left) != _skeleton(right):
        return False
    return jaccard_at_least(
        char_shingles(left),
        char_shingles(right),
        SHORT_SKELETON_NUMERATOR,
        SHORT_SKELETON_DENOMINATOR,
    )


def containment_at_least(
    part: frozenset[str],
    whole: frozenset[str],
    numerator: int = CONTAINMENT_NUMERATOR,
    denominator: int = CONTAINMENT_DENOMINATOR,
) -> bool:
    """Return whether ``|part ∩ whole| / |part| >= numerator / denominator``.

    An empty part is not contained. The denominator is the part, not
    the union, so a short verbatim excerpt of a long file matches.
    """
    if denominator < 1 or numerator < 0 or numerator > denominator:
        raise ValueError("threshold fraction is out of range")
    if not part:
        return False
    return len(part & whole) * denominator >= len(part) * numerator


def has_verbatim_run(
    part: Sequence[str],
    whole: Sequence[str],
    length: int | None = None,
) -> bool:
    """Return whether ``length`` contiguous tokens of ``part`` occur in ``whole``."""
    if length is None:
        length = TOKEN_FLOOR
    if length < 1 or len(part) < length or len(whole) < length:
        return False
    window = shingles(whole, length)
    return any(
        "\0".join(part[index : index + length]) in window
        for index in range(len(part) - length + 1)
    )


def is_excerpt(part: str, whole: str) -> bool:
    """Return whether ``part`` is a verbatim excerpt of ``whole``.

    Both the containment ratio and the long token run require
    ``TOKEN_FLOOR`` on the part. Identical texts are not excerpts;
    the exact-hash pass owns those.
    """
    if part == whole:
        return False
    part_tokens = tokens(part)
    if len(part_tokens) < TOKEN_FLOOR:
        return False
    whole_tokens = tokens(whole)
    # A run counts in either direction. A cleared file that vendors a
    # shorter rejected file, plus its own padding, still shares that run.
    # Upstream originals are kept by the allowlist, not by skipping here.
    if has_verbatim_run(part_tokens, whole_tokens):
        return True
    return containment_at_least(shingles(part_tokens), shingles(whole_tokens))


def is_near_duplicate(left: str, right: str) -> bool:
    """Return whether two normalized texts are near-duplicates.

    Identical short texts return ``False``. Exact equality is the hash
    pass in ``cluster_families``, not this predicate. A pair under
    ``TOKEN_FLOOR`` uses :func:`short_near_duplicate`.
    """
    left_tokens = tokens(left)
    right_tokens = tokens(right)
    if len(left_tokens) >= TOKEN_FLOOR and len(right_tokens) >= TOKEN_FLOOR:
        return jaccard_at_least(shingles(left_tokens), shingles(right_tokens))
    return short_near_duplicate(left, right)


def memorization_hits(
    candidate: str, corpus: Sequence[tuple[str, str]]
) -> tuple[tuple[str, int, int], ...]:
    """Return near-duplicate corpus hits for one candidate program.

    Each hit is ``(corpus_id, intersection, union)`` in corpus order.
    T07 calls this against a sealed split. The output gate calls it
    against the training-only set. This function does not quarantine
    and does not write artifacts.
    """
    hits: list[tuple[str, int, int]] = []
    for corpus_id, text in corpus:
        counted = _hit_counts(candidate, text)
        if counted is None:
            continue
        intersection, union = counted
        hits.append((corpus_id, intersection, union))
    return tuple(hits)


def _hit_counts(candidate: str, text: str) -> tuple[int, int] | None:
    """Return the scores of the comparison that actually matched.

    An exact copy is a hit, including under ``TOKEN_FLOOR``. A long
    pair reports token-shingle counts. A short pair reports character
    5-gram counts. An excerpt reports ``(intersection, |part shingles|)``.
    """
    if candidate == text:
        return _identical_counts(candidate)
    candidate_tokens = tokens(candidate)
    text_tokens = tokens(text)
    if len(candidate_tokens) >= TOKEN_FLOOR and len(text_tokens) >= TOKEN_FLOOR:
        left = shingles(candidate_tokens)
        right = shingles(text_tokens)
        if jaccard_at_least(left, right):
            return jaccard_counts(left, right)
        if is_excerpt(candidate, text):
            intersection = len(left & right)
            return (intersection, len(left))
        return None
    if short_near_duplicate(candidate, text):
        return jaccard_counts(char_shingles(candidate), char_shingles(text))
    return None


def _identical_counts(text: str) -> tuple[int, int]:
    text_tokens = tokens(text)
    if len(text_tokens) >= TOKEN_FLOOR:
        size = len(shingles(text_tokens))
        return (size, size)
    size = len(char_shingles(text))
    if size == 0:
        size = len(_compact(text)) or 1
    return (size, size)


def family_id(digests: Iterable[str]) -> str:
    """Return the duplicate-family id for a set of normalized digests."""
    ordered = sorted(set(digests))
    if not ordered:
        raise ValueError("a family needs at least one digest")
    return "sha256:" + hashlib.sha256(canonical_bytes(ordered)).hexdigest()


def cluster_families(
    items: Sequence[tuple[str, str]],
    comparison_ids: Collection[str] = (),
) -> dict[str, str]:
    """Map each item id to a duplicate-family id.

    ``items`` is ``(id, normalized_text)``. Exact normalized hashes are
    unioned first. Near-duplicate pairs are unioned after that. When
    ``comparison_ids`` is set, a non-comparison text that is an excerpt
    of a comparison text joins that component. The other direction does
    not. The family id is :func:`family_id` of the component's digests.
    """
    if not items:
        return {}
    seen: set[str] = set()
    parent: dict[str, str] = {}
    digest_of: dict[str, str] = {}
    token_count: dict[str, int] = {}
    shingle_of: dict[str, frozenset[str]] = {}
    for item_id, text in items:
        if item_id in seen:
            raise ValueError(f"duplicate clustering id: {item_id}")
        seen.add(item_id)
        parent[item_id] = item_id
        digest_of[item_id] = sha256_prefixed(text.encode("utf-8"))
        item_tokens = tokens(text)
        token_count[item_id] = len(item_tokens)
        shingle_of[item_id] = (
            shingles(item_tokens) if len(item_tokens) >= TOKEN_FLOOR else frozenset()
        )

    def find(item_id: str) -> str:
        root = item_id
        while parent[root] != root:
            root = parent[root]
        while parent[item_id] != root:
            parent[item_id], item_id = root, parent[item_id]
        return root

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if left_root < right_root:
            parent[right_root] = left_root
        else:
            parent[left_root] = right_root

    by_digest: dict[str, list[str]] = {}
    for item_id, digest in digest_of.items():
        by_digest.setdefault(digest, []).append(item_id)
    for group in by_digest.values():
        anchor = min(group)
        for item_id in group:
            union(anchor, item_id)

    text_of = {item_id: text for item_id, text in items}
    ordered_ids = sorted(parent)
    for index, left in enumerate(ordered_ids):
        for right in ordered_ids[index + 1 :]:
            if find(left) == find(right):
                continue
            both_long = (
                token_count[left] >= TOKEN_FLOOR and token_count[right] >= TOKEN_FLOOR
            )
            if both_long:
                if jaccard_at_least(shingle_of[left], shingle_of[right]):
                    union(left, right)
                continue
            if short_near_duplicate(text_of[left], text_of[right]):
                union(left, right)

    comparison = set(comparison_ids)
    unknown = comparison - seen
    if unknown:
        raise ValueError(f"comparison id is not in the cluster: {min(unknown)}")
    if comparison:
        token_of = {item_id: tokens(text) for item_id, text in text_of.items()}
        cleared_ids = [item_id for item_id in ordered_ids if item_id not in comparison]
        compared_ids = [item_id for item_id in ordered_ids if item_id in comparison]
        whole_shingles = {
            item_id: shingles(token_of[item_id]) for item_id in compared_ids
        }
        whole_runs = {
            item_id: shingles(token_of[item_id], TOKEN_FLOOR)
            if len(token_of[item_id]) >= TOKEN_FLOOR
            else frozenset()
            for item_id in compared_ids
        }
        for part_id in cleared_ids:
            part_tokens = token_of[part_id]
            if len(part_tokens) < TOKEN_FLOOR:
                continue
            part_shingles = shingles(part_tokens)
            part_runs = (
                shingles(part_tokens, TOKEN_FLOOR)
                if len(part_tokens) >= TOKEN_FLOOR
                else frozenset()
            )
            for whole_id in compared_ids:
                if find(part_id) == find(whole_id):
                    continue
                run = bool(part_runs and part_runs & whole_runs[whole_id])
                if run or containment_at_least(part_shingles, whole_shingles[whole_id]):
                    union(part_id, whole_id)

    components: dict[str, list[str]] = {}
    for item_id in ordered_ids:
        components.setdefault(find(item_id), []).append(item_id)
    families: dict[str, str] = {}
    for members in components.values():
        identifier = family_id(digest_of[item_id] for item_id in members)
        for item_id in members:
            families[item_id] = identifier
    return families

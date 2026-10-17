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
  ``MIN_TOKENS`` tokens and the Jaccard index is at least 4/5.
- The comparison is integer: ``intersection * 5 >= union * 4``.
  A reported float is not the decision.

``MIN_TOKENS`` is 40. Below that, shared Faust boilerplate
(``declare``, ``import``, ``process``) dominates the shingles and
unrelated programs look alike. Exact normalized-hash equality is a
separate pass and still clusters short texts.

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
MIN_TOKENS = 40

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


def is_near_duplicate(left: str, right: str) -> bool:
    """Return whether two normalized texts are near-duplicates.

    Identical short texts return ``False``. Exact equality is the hash
    pass in ``cluster_families``, not this predicate.
    """
    left_tokens = tokens(left)
    right_tokens = tokens(right)
    if len(left_tokens) < MIN_TOKENS or len(right_tokens) < MIN_TOKENS:
        return False
    return jaccard_at_least(shingles(left_tokens), shingles(right_tokens))


def memorization_hits(
    candidate: str, corpus: Sequence[tuple[str, str]]
) -> tuple[tuple[str, int, int], ...]:
    """Return near-duplicate corpus hits for one candidate program.

    Each hit is ``(corpus_id, intersection, union)`` in corpus order.
    T07 calls this against a sealed split. The output gate calls it
    against the training-only set. This function does not quarantine
    and does not write artifacts.
    """
    candidate_tokens = tokens(candidate)
    if len(candidate_tokens) < MIN_TOKENS:
        return ()
    candidate_shingles = shingles(candidate_tokens)
    hits: list[tuple[str, int, int]] = []
    for corpus_id, text in corpus:
        text_tokens = tokens(text)
        if len(text_tokens) < MIN_TOKENS:
            continue
        intersection, union = jaccard_counts(
            candidate_shingles, shingles(text_tokens)
        )
        if union and intersection * THRESHOLD_DENOMINATOR >= union * THRESHOLD_NUMERATOR:
            hits.append((corpus_id, intersection, union))
    return tuple(hits)


def family_id(digests: Iterable[str]) -> str:
    """Return the duplicate-family id for a set of normalized digests."""
    ordered = sorted(set(digests))
    if not ordered:
        raise ValueError("a family needs at least one digest")
    return "sha256:" + hashlib.sha256(canonical_bytes(ordered)).hexdigest()


def cluster_families(
    items: Sequence[tuple[str, str]],
) -> dict[str, str]:
    """Map each item id to a duplicate-family id.

    ``items`` is ``(id, normalized_text)``. Exact normalized hashes are
    unioned first. Near-duplicate pairs are unioned after that. The
    family id is :func:`family_id` of the component's digests.
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
            shingles(item_tokens) if len(item_tokens) >= MIN_TOKENS else frozenset()
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

    ordered_ids = sorted(parent)
    for index, left in enumerate(ordered_ids):
        if token_count[left] < MIN_TOKENS:
            continue
        for right in ordered_ids[index + 1 :]:
            if token_count[right] < MIN_TOKENS:
                continue
            if find(left) == find(right):
                continue
            if jaccard_at_least(shingle_of[left], shingle_of[right]):
                union(left, right)

    components: dict[str, list[str]] = {}
    for item_id in ordered_ids:
        components.setdefault(find(item_id), []).append(item_id)
    families: dict[str, str] = {}
    for members in components.values():
        identifier = family_id(digest_of[item_id] for item_id in members)
        for item_id in members:
            families[item_id] = identifier
    return families

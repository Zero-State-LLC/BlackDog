"""Token n-gram near-duplicate comparison (task T06).

H2/H3 shipping clustering and memorization compare raw OR canonical streams.
Source normalization/digests remain byte-preserving; comparison-only H3 applies
NFKC and drops non-whitespace Cf/Cc while preserving lexical whitespace.

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
  stays under 4/5. An excerpt check is separate. Forward containment
  is ``|shingles(cleared) ∩ shingles(rejected)| / |shingles(cleared)|
  >= 1/2``, and a contiguous run of ``TOKEN_FLOOR`` tokens counts in
  either direction. Reverse containment is
  ``|shingles(rejected) ∩ shingles(cleared)| / |shingles(rejected)|
  >= 1/2`` when the rejected text has at least ``TOKEN_FLOOR`` tokens.
  ``cluster_families`` applies both from a non-comparison text into a
  comparison text. The upstream allowlist, not this predicate, keeps
  a recorded original.

``TOKEN_FLOOR`` is the single length constant for that minimum and
for the verbatim run. It is 40. ``TOKEN_FLOOR_STATUS`` is
``provisional``. Danny has not accepted 40 as clearance policy.
Acceptance bounds for the value are ratified
(faustcoder/floor_protocol.py); the value itself is not. The
measurement is ``docs/analysis/t06-short-kernel-floor.md``. Below the
floor, shared Faust boilerplate (``declare``, ``import``, ``process``)
dominates the shingles and unrelated programs look alike. Exact
normalized-hash equality is a separate pass and still clusters short
texts.

Family ids are ``sha256:`` of the canonical JSON array of the sorted
unique normalized digests in the component. The id does not depend on
unit ids or comparison order.

Collective support on the shipping path unions every non-comparison unit
that shares at least one shingle with the comparison unit. The group
still needs at least three such units, and their union must cover at
least half of the comparison shingles. Group ids on that path are the
unmarked key ``[comparison, contributors, canonical, floor]``.

``marginal_coverage`` is a separate opt-in. It keeps only units that add
at least ``COLLECTIVE_MIN_MARGINAL`` not-yet-covered comparison shingles.
Selection does not stop at the 1/2 threshold while fewer than three
contributors are selected. It stops once three contributors meet that
threshold, or when no remaining unit supplies the minimum. The opt-in
idiom filter is a different switch and does not turn marginal coverage on.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Collection, Iterable, Sequence

from faustcoder.canonical import canonical_bytes, sha256_prefixed
from faustcoder.idiom_filter import IdiomFilter, idiom_shingles, scoped

NGRAM_N = 5
THRESHOLD_NUMERATOR = 4
THRESHOLD_DENOMINATOR = 5
# Single length constant. Jaccard, excerpt containment, and the
# verbatim run all use it. The status is provisional: Danny has not
# accepted 40 as clearance policy.
TOKEN_FLOOR = 40
TOKEN_FLOOR_STATUS = "provisional"
MIN_TOKENS = TOKEN_FLOOR
VERBATIM_RUN = TOKEN_FLOOR
# Asymmetric excerpt check. Jaccard 4/5 misses a half-file copy
# (INFERRED).
CONTAINMENT_NUMERATOR = 1
CONTAINMENT_DENOMINATOR = 2
# Opt-in marginal coverage only. A unit joins that rule when it supplies
# at least this many comparison shingles that no already selected unit
# covers. 1 means any positive new coverage. The shipping default does
# not use this constant: any shared shingle can join.
COLLECTIVE_MIN_MARGINAL = 1
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


# Comparison-only normalization; source bytes and provenance digests never change.
COMPARISON_VERSION = "t06-raw-or-canonical-h3.v1"
_CANONICAL_TOKEN = re.compile(
    r'"(?:\\.|[^"\\])*"|[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+'
    r'|[A-Za-z_][A-Za-z0-9_]*|(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?'
    r'|==|!=|<=|>=|&&|\|\||[^\s]'
)


def comparison_source(source: str) -> str:
    """H3: NFKC, comments removed before Cf/Cc removal.

    Lexical whitespace controls retain a space boundary so removing a newline
    cannot merge identifiers or extend a line comment into executable source.
    All other Cf/Cc characters are dropped. This never rewrites stored source.
    """
    source = strip_comments(unicodedata.normalize("NFKC", source))
    return "".join(" " if c in "\r\n\t\v\f" else c
                   for c in source if c in "\r\n\t\v\f"
                   or unicodedata.category(c) not in {"Cf", "Cc"})


def canonical_tokens(source: str) -> tuple[str, ...]:
    """H2 extra stream: ID/NUM/STR; qualified library members stay literal."""
    result = []
    for token in _CANONICAL_TOKEN.findall(comparison_source(source)):
        if token.startswith('"'):
            result.append("STR")
        elif _IDENT.fullmatch(token):
            result.append("ID")
        elif re.fullmatch(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", token):
            result.append("NUM")
        else:
            result.append(token)
    return tuple(result)


def _canonical_source(source: str) -> str:
    return " ".join(canonical_tokens(source))


def _require_floor(floor: int) -> None:
    if type(floor) is not int or floor not in (20, 30, 40):
        raise ValueError("floor must be one of 40, 30, 20")


def tokens(source: str) -> tuple[str, ...]:
    """Return the comment-stripped token sequence."""
    return tuple(_TOKEN.findall(comparison_source(source)))


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
    union = len(left) + len(right) - intersection
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
    return "".join(comparison_source(source).split())


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


def collective_scope_mark(scope, idiom: frozenset[str] | None) -> dict:
    """Identity of an enabled idiom filter inside a collective group id.

    Scope off does not append this mark. The unmarked key is main's group
    id. An enabled filter appends the mark so its id cannot match scope off
    when the selected units match.
    """
    if scope is None:
        return {"enabled": False, "label": "scope=off"}
    return {
        **scope.describe(),
        "enabled": True,
        "label": f"idiom_filter:D={scope.idiom_min_docs}:k={scope.idiom_min_repos}",
        "idiom_set_sha256": sha256_prefixed(canonical_bytes(sorted(idiom or ()))),
    }


def select_collective_contributors(
    overlaps: dict[str, frozenset[str]], whole: frozenset[str]
) -> list[str]:
    """Return units that each add ``COLLECTIVE_MIN_MARGINAL`` new shingles.

    Greedy by descending new coverage, then unit id. Do not stop when the
    1/2 containment threshold is reached with fewer than three contributors.
    Stop once three contributors meet that threshold, or when no remaining
    unit supplies the minimum (coverage is complete).
    """
    if type(COLLECTIVE_MIN_MARGINAL) is not int or COLLECTIVE_MIN_MARGINAL < 1:
        raise ValueError("COLLECTIVE_MIN_MARGINAL must be an int >= 1")
    remaining = {
        key for key, overlap in overlaps.items() if len(overlap) >= COLLECTIVE_MIN_MARGINAL
    }
    contributors: list[str] = []
    supplied: set[str] = set()
    while remaining:
        if len(contributors) >= 3 and containment_at_least(whole, frozenset(supplied)):
            break
        best = min(remaining, key=lambda key: (-len(overlaps[key] - supplied), key))
        added = overlaps[best] - supplied
        if len(added) < COLLECTIVE_MIN_MARGINAL:
            break
        contributors.append(best)
        supplied.update(added)
        remaining.remove(best)
    contributors.sort()
    return contributors


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


def _raw_is_excerpt(part: str, whole: str, *, floor: int = TOKEN_FLOOR) -> bool:
    """Return whether ``part`` copies ``whole`` or contains ``whole``.

    Forward containment and the token run require ``floor`` on
    ``part``. Reverse containment requires ``floor`` on
    ``whole`` and ``|sh(whole) ∩ sh(part)| / |sh(whole)| >= 1/2``.
    Identical texts are not excerpts; the exact-hash pass owns those.
    The upstream allowlist is applied by the snapshot, not here.
    """
    if part == whole:
        return False
    part_tokens = tokens(part)
    whole_tokens = tokens(whole)
    # Rejected text mostly contained in the cleared file. One edited
    # literal per statement, padding, or interleaving can keep the
    # forward ratio under 1/2 and still break a 40-token run.
    if len(whole_tokens) >= floor and containment_at_least(
        shingles(whole_tokens), shingles(part_tokens)
    ):
        return True
    if len(part_tokens) < floor:
        return False
    # A run counts in either direction. A cleared file that vendors a
    # shorter rejected file, plus its own padding, still shares that run.
    if has_verbatim_run(part_tokens, whole_tokens, floor):
        return True
    return containment_at_least(shingles(part_tokens), shingles(whole_tokens))


def _raw_is_near_duplicate(left: str, right: str, *, floor: int = TOKEN_FLOOR) -> bool:
    """Return whether two normalized texts are near-duplicates.

    Identical short texts return ``False``. Exact equality is the hash
    pass in ``cluster_families``, not this predicate. A pair under
    ``floor`` uses :func:`short_near_duplicate`.
    """
    left_tokens = tokens(left)
    right_tokens = tokens(right)
    if len(left_tokens) >= floor and len(right_tokens) >= floor:
        return jaccard_at_least(shingles(left_tokens), shingles(right_tokens))
    return short_near_duplicate(left, right)


def memorization_hits(
    candidate: str, corpus: Sequence[tuple[str, str]], *, floor: int = TOKEN_FLOOR
) -> tuple[tuple[str, int, int], ...]:
    """Return near-duplicate corpus hits for one candidate program.

    Each hit is ``(corpus_id, intersection, union)`` in corpus order.
    T07 calls this against a sealed split. The output gate calls it
    against the training-only set. This function does not quarantine
    and does not write artifacts.
    """
    hits: list[tuple[str, int, int]] = []
    for corpus_id, text in corpus:
        counted = _hit_counts(candidate, text, floor=floor)
        if counted is None:
            continue
        intersection, union = counted
        hits.append((corpus_id, intersection, union))
    return tuple(hits)


def _raw_hit_counts(candidate: str, text: str, *, floor: int = TOKEN_FLOOR) -> tuple[int, int] | None:
    """Return the scores of the comparison that actually matched.

    An exact copy is a hit, including under ``floor``. A long
    pair reports token-shingle counts. A short pair reports character
    5-gram counts. An excerpt reports ``(intersection, |part shingles|)``.
    """
    if candidate == text:
        return _identical_counts(candidate, floor=floor)
    candidate_tokens = tokens(candidate)
    text_tokens = tokens(text)
    if len(candidate_tokens) >= floor and len(text_tokens) >= floor:
        left = shingles(candidate_tokens)
        right = shingles(text_tokens)
        if jaccard_at_least(left, right):
            return jaccard_counts(left, right)
        if _raw_is_excerpt(candidate, text, floor=floor):
            intersection = len(left & right)
            return (intersection, len(left))
        return None
    if short_near_duplicate(candidate, text):
        return jaccard_counts(char_shingles(candidate), char_shingles(text))
    return None


def _identical_counts(text: str, *, floor: int = TOKEN_FLOOR) -> tuple[int, int]:
    text_tokens = tokens(text)
    if len(text_tokens) >= floor:
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


def _raw_cluster_families(
    items: Sequence[tuple[str, str]],
    comparison_ids: Collection[str] = (),
    *, floor: int = TOKEN_FLOOR, canonical: bool = False, evidence: list | None = None,
    scope: IdiomFilter | None = None, item_repos: dict[str, str] | None = None,
    marginal_coverage: bool = False,
) -> dict[str, str]:
    """Map each item id to a duplicate-family id.

    ``items`` is ``(id, normalized_text)``. Exact normalized hashes are
    unioned first. Near-duplicate pairs are unioned after that. When
    ``comparison_ids`` is set, a non-comparison text joins a comparison
    text when either side's shingles are at least half contained in the
    other, or the two share a ``floor`` token run. Reverse
    containment requires the comparison text to have at least
    ``floor`` tokens. The family id is :func:`family_id` of the
    component's digests.
    """
    tokenize = (lambda text: tuple(text.split())) if canonical else tokens
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
        item_tokens = tokenize(text)
        token_count[item_id] = len(item_tokens)
        shingle_of[item_id] = (
            shingles(item_tokens) if len(item_tokens) >= floor else frozenset()
        )

    def find(item_id: str) -> str:
        root = item_id
        while parent[root] != root:
            root = parent[root]
        while parent[item_id] != root:
            parent[item_id], item_id = root, parent[item_id]
        return root

    def union(left: str, right: str, reason: str, **details) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if evidence is not None:
            evidence.append(dict(left=left, right=right, reason=reason,
                                 stream="canonical" if canonical else "raw",
                                 floor=floor, **details))
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
            if not canonical or token_count[item_id] < 15 or token_count[item_id] >= floor:
                union(anchor, item_id, "exact")

    text_of = {item_id: text for item_id, text in items}
    ordered_ids = sorted(parent)
    # Cache comparison-only text features once per item, rather than repeatedly
    # stripping/tokenizing large library files for every short/long pair.
    compact_of = {key: _compact(text) for key, text in items} if not canonical else {}
    char_of = {key: frozenset(value[i:i+CHAR_N] for i in range(max(0,len(value)-CHAR_N+1)))
               for key,value in compact_of.items()}
    skeleton_of = {key: _NUMBER.sub("n", _IDENT.sub("id", _STRING.sub('"s"', value)))
                   for key,value in compact_of.items()}
    def short_match(left, right):
        if text_of[left] == text_of[right]:
            return False
        if len(compact_of[left]) >= CHAR_MIN_LENGTH and len(compact_of[right]) >= CHAR_MIN_LENGTH:
            return jaccard_at_least(char_of[left], char_of[right], CHAR_NUMERATOR, CHAR_DENOMINATOR)
        return (skeleton_of[left] == skeleton_of[right]
                and jaccard_at_least(char_of[left], char_of[right],
                                     SHORT_SKELETON_NUMERATOR, SHORT_SKELETON_DENOMINATOR))
    for index, left in enumerate(ordered_ids):
        for right in ordered_ids[index + 1 :]:
            if find(left) == find(right):
                continue
            both_long = (
                token_count[left] >= floor and token_count[right] >= floor
            )
            if both_long:
                if jaccard_at_least(shingle_of[left], shingle_of[right]):
                    union(left, right, "token_jaccard", intersection=len(shingle_of[left] & shingle_of[right]), union=len(shingle_of[left] | shingle_of[right]))
                continue
            if not canonical and short_match(left, right):
                union(left, right, "short_character_match")

    comparison = set(comparison_ids)
    unknown = comparison - seen
    if unknown:
        raise ValueError(f"comparison id is not in the cluster: {min(unknown)}")
    idiom = None
    if comparison:
        token_of = {item_id: tokenize(text) for item_id, text in text_of.items()}
        if scope is not None:
            # Opt-in comparison scope (UNREVIEWED proposal). Document
            # frequency is counted on this stream over non-comparison items.
            idiom = idiom_shingles(
                {key: shingles(value) for key, value in token_of.items()},
                comparison, scope.idiom_min_docs, item_repos=item_repos,
                min_repos=scope.idiom_min_repos)
            if evidence is not None:
                evidence.append(dict(reason="idiom_filter", **collective_scope_mark(scope, idiom),
                                     idiom_shingles=len(idiom),
                                     stream="canonical" if canonical else "raw", floor=floor))
        cleared_ids = [item_id for item_id in ordered_ids if item_id not in comparison]
        compared_ids = [item_id for item_id in ordered_ids if item_id in comparison]
        whole_shingles = {
            item_id: scoped(shingles(token_of[item_id]), idiom) for item_id in compared_ids
        }
        whole_runs = {
            item_id: shingles(token_of[item_id], floor)
            if len(token_of[item_id]) >= floor
            else frozenset()
            for item_id in compared_ids
        }
        for part_id in cleared_ids:
            part_tokens = token_of[part_id]
            part_shingles = scoped(shingles(part_tokens), idiom)
            part_long = len(part_tokens) >= floor
            part_runs = shingles(part_tokens, floor) if part_long else frozenset()
            for whole_id in compared_ids:
                if find(part_id) == find(whole_id):
                    continue
                # |sh(R) ∩ sh(C)| / |sh(R)| >= 1/2. The rejected side is
                # the denominator, so padding and interleaving in C do
                # not dilute it.
                if len(token_of[whole_id]) >= floor and containment_at_least(
                    whole_shingles[whole_id], part_shingles
                ):
                    union(part_id, whole_id, "reverse_containment", intersection=len(whole_shingles[whole_id] & part_shingles), denominator=len(whole_shingles[whole_id]))
                    continue
                if not part_long:
                    continue
                run = bool(part_runs and part_runs & whole_runs[whole_id])
                if run or containment_at_least(part_shingles, whole_shingles[whole_id]):
                    union(part_id, whole_id, "verbatim_run" if run else "forward_containment", intersection=len(part_shingles & whole_shingles[whole_id]), denominator=len(part_shingles))

    if comparison:
        # Reuse source features for collective coverage; no pairwise re-tokenization.
        all_shingles = {key: shingles(value) for key, value in token_of.items()}
        for whole_id in sorted(comparison):
            whole = scoped(shingle_of[whole_id], idiom)
            if not whole:
                continue
            overlaps = {key: all_shingles[key] & whole
                        for key in ordered_ids if key not in comparison}
            # Shipping path matches main: any shared shingle may join.
            # Marginal coverage is opt-in and is the only path that drops
            # a unit whose overlap is already covered.
            if marginal_coverage:
                contributors = select_collective_contributors(overlaps, whole)
            else:
                contributors = [key for key, overlap in overlaps.items() if overlap]
            covered = frozenset().union(*(overlaps[key] for key in contributors)) if contributors else frozenset()
            if len(contributors) >= 3 and containment_at_least(whole, covered):
                group_key = [whole_id, contributors, canonical, floor]
                if scope is not None:
                    group_key.append(collective_scope_mark(scope, idiom))
                if marginal_coverage:
                    group_key.append({
                        "marginal_coverage": True,
                        "collective_min_marginal": COLLECTIVE_MIN_MARGINAL,
                    })
                group_id = sha256_prefixed(canonical_bytes(group_key))
                if evidence is not None:
                    record = dict(reason="collective_support", group_id=group_id,
                                  comparison=whole_id, contributors=contributors,
                                  covered=len(covered), denominator=len(whole),
                                  stream="canonical" if canonical else "raw", floor=floor)
                    if scope is not None:
                        record["idiom_filter"] = collective_scope_mark(scope, idiom)
                    if marginal_coverage:
                        record["marginal_coverage"] = True
                        record["collective_min_marginal"] = COLLECTIVE_MIN_MARGINAL
                    evidence.append(record)
                for key in contributors:
                    union(key, whole_id, "collective_union", group_id=group_id)

    components: dict[str, list[str]] = {}
    for item_id in ordered_ids:
        components.setdefault(find(item_id), []).append(item_id)
    families: dict[str, str] = {}
    for members in components.values():
        identifier = family_id(digest_of[item_id] for item_id in members)
        for item_id in members:
            families[item_id] = identifier
    return families


# Raw predicates remain available for measuring each stream separately.
def is_excerpt(part: str, whole: str, *, floor: int = TOKEN_FLOOR) -> bool:
    _require_floor(floor)
    return _raw_is_excerpt(part, whole, floor=floor)


def is_near_duplicate(left: str, right: str, *, floor: int = TOKEN_FLOOR) -> bool:
    _require_floor(floor)
    return _raw_is_near_duplicate(left, right, floor=floor)


def _hit_counts(candidate: str, text: str, *, floor: int = TOKEN_FLOOR):
    _require_floor(floor)
    raw = _raw_hit_counts(candidate, text, floor=floor)
    if raw is not None:
        return raw
    a, b = canonical_tokens(candidate), canonical_tokens(text)
    if not a or not b:
        return None
    left, right = shingles(a), shingles(b)
    if a == b and (len(a) < 15 or len(a) >= floor):
        return (len(left) or 1, len(left) or 1)
    if len(a) >= floor and len(b) >= floor and jaccard_at_least(left, right):
        return jaccard_counts(left, right)
    if len(b) >= floor and containment_at_least(right, left):
        return (len(left & right), len(right))
    if len(a) >= floor and (has_verbatim_run(a,b,floor) or containment_at_least(left,right)):
        return (len(left & right), len(left))
    return None


def cluster_families(items, comparison_ids=(), *, floor: int = TOKEN_FLOOR, evidence: list | None = None,
                     scope: IdiomFilter | None = None, item_repos: dict[str, str] | None = None,
                     marginal_coverage: bool = False):
    """OR raw and canonical components; ids remain bound to original text.

    Canonical short exact matches are fail-closed pending reviewed idiom pairs.
    With the default ``scope=None`` no automatic boilerplate exemption or rights
    override is introduced. An ``IdiomFilter`` is an opt-in, UNREVIEWED proposal
    (see ``faustcoder.idiom_filter``); it never changes exact, Jaccard,
    verbatim-run or short-match joins. It is not the
    ``incomplete_comparison_scope`` blocker. Collective joins use main's
    any-overlap rule unless ``marginal_coverage`` is set. That flag is not
    implied by the idiom filter.
    Optional evidence records the deterministic joining forest and collective
    support sets, not every matching pair and not adjudicated copy labels.
    """
    _require_floor(floor)
    if scope is not None and not isinstance(scope, IdiomFilter):
        raise TypeError("scope must be an IdiomFilter or None")
    if type(marginal_coverage) is not bool:
        raise TypeError("marginal_coverage must be a bool")
    raw = _raw_cluster_families(
        items, comparison_ids, floor=floor, evidence=evidence, scope=scope,
        item_repos=item_repos, marginal_coverage=marginal_coverage)
    canonical = _raw_cluster_families(
        [(key, _canonical_source(text)) for key, text in items], comparison_ids, floor=floor, canonical=True,
        evidence=evidence, scope=scope, item_repos=item_repos, marginal_coverage=marginal_coverage)
    parent = {key: key for key, _ in items}
    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key
    for mapping in (raw, canonical):
        groups = {}
        for key, family in sorted(mapping.items()):
            if family in groups:
                a, b = find(key), find(groups[family])
                parent[max(a, b)] = min(a, b)
            else:
                groups[family] = key
    groups = {}
    for key, text in items:
        groups.setdefault(find(key), []).append(sha256_prefixed(text.encode("utf-8")))
    return {key: family_id(groups[find(key)]) for key, _ in items}

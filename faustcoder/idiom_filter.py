"""Opt-in idiom filter for T06 family clustering (UNREVIEWED proposal).

The feature name is idiom filter. It is not the
``incomplete_comparison_scope`` blocker, which means missing comparison
inputs. This module is ``idiom_filter.py``.

The shipping default is no filter object (``scope=None``, label ``scope=off``).
With no filter, exact, Jaccard, verbatim-run and short-match joins are
unchanged. Collective membership on that path is main's any-overlap rule.
Marginal coverage is a separate opt-in (``marginal_coverage``) and is not
implied by this filter.

An ``IdiomFilter`` names a document-frequency idiom set. A 5-token shingle
is an *idiom shingle* on a stream when it occurs in at least ``idiom_min_docs``
distinct non-comparison items of the clustered pool, counted on that stream.
Comparison (reject-class) items are never counted. A shingle must also occur
in at least idiom_min_repos distinct known repositories (default 2). Unknown
repository identities do not count. This limits single-repository leakage;
cross-repository copied code can still be suppressed and needs human review.

Idiom shingles are removed only from the ratio predicates that compare a
cleared item with a comparison item:

- forward containment (cleared shingles inside the comparison),
- reverse containment (comparison shingles inside the cleared item),
- collective support (contributor overlap and union coverage).

These predicates are untouched: exact normalized hash, token Jaccard between
pool items, the ``floor``-token verbatim run, and the short character match.
A contiguous run of ``floor`` tokens therefore still joins a family whatever
the idiom set says. ``TOKEN_FLOOR``, the containment and Jaccard fractions,
canonicalization (H2/H3) and source text are not changed.

This is a proposal. Selecting a scope for shipping needs ADVERSARY review,
a complete recompute and fixed-label FLOOR qualification, and a human gate
decision. Nothing here approves a label, a family removal or an idiom pair.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from faustcoder.canonical import content_digest_for

SCOPE_VERSION = "t06-idiom-filter-df.v2"


@dataclass(frozen=True)
class IdiomFilter:
    """Document-frequency idiom scope. ``idiom_min_docs`` must be at least 2."""

    idiom_min_docs: int
    version: str = SCOPE_VERSION
    idiom_min_repos: int = 2

    def __post_init__(self) -> None:
        if type(self.idiom_min_docs) is not int or self.idiom_min_docs < 2:
            raise ValueError("idiom_min_docs must be an int >= 2")
        if type(self.idiom_min_repos) is not int or self.idiom_min_repos < 2:
            raise ValueError("idiom_min_repos must be an int >= 2")
        if self.version != SCOPE_VERSION:
            raise ValueError(f"unknown idiom filter version: {self.version}")

    def describe(self) -> dict:
        return {"version": self.version, "idiom_min_docs": self.idiom_min_docs,
                "idiom_min_repos": self.idiom_min_repos}


def idiom_shingles(
    shingle_sets: dict[str, frozenset[str]],
    comparison_ids: Collection[str],
    min_docs: int,
    *, item_repos: dict[str, str] | None = None, min_repos: int = 2,
) -> frozenset[str]:
    """Require document frequency AND repository diversity; unknown repos fail closed."""
    if type(min_docs) is not int or min_docs < 2:
        raise ValueError("min_docs must be an int >= 2")
    if type(min_repos) is not int or min_repos < 2:
        raise ValueError("min_repos must be an int >= 2")
    comparison = set(comparison_ids)
    repositories: dict[str, set[str]] = {}
    counts: Counter[str] = Counter()
    for item_id in sorted(shingle_sets):
        if item_id in comparison:
            continue
        counts.update(shingle_sets[item_id])
        repository = (item_repos or {}).get(item_id)
        if repository:
            for shingle in shingle_sets[item_id]:
                repositories.setdefault(shingle, set()).add(repository)
    return frozenset(s for s, n in counts.items() if n >= min_docs and len(repositories.get(s, ())) >= min_repos)


def scoped(shingle_set: Iterable[str], idiom: frozenset[str] | None) -> frozenset[str]:
    """Remove idiom shingles; ``None`` means no scope and returns the input."""
    shingle_set = frozenset(shingle_set)
    if idiom is None:
        return shingle_set
    return shingle_set - idiom


def scope_descriptor(scope, streams=None):
    """Bind the enabled state and exact learned sets, including explicit scope-off.

    The recorded name is idiom filter. That is distinct from the
    ``incomplete_comparison_scope`` blocker, which means missing comparison
    inputs.
    """
    streams = streams or {}
    learned = {stream: sorted(streams.get(stream, ())) for stream in ("raw", "canonical")}
    base = {
        "enabled": scope is not None,
        "version": SCOPE_VERSION,
        "idiom_min_docs": scope.idiom_min_docs if scope else None,
        "idiom_min_repos": scope.idiom_min_repos if scope else None,
        "idiom_set_sha256": content_digest_for(learned),
    }
    if scope is None:
        return {**base, "label": "scope=off"}
    return {**base, "label": f"idiom_filter:D={scope.idiom_min_docs}:k={scope.idiom_min_repos}"}

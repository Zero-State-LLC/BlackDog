# T06 comparison scope (UNREVIEWED proposal)

Status: agent-prepared by Grok Bot (Jev), delegated by Danny Meyer.
Not reviewed. Needs ADVERSARY review, fixed-label FLOOR qualification and a
human gate decision before any shipping use. Nothing here changes
`TOKEN_FLOOR`, H2/H3 canonicalization, family rules, thresholds or source text.
The shipping default is `scope=None`, which is byte-identical to main.

## Problem (OBSERVED)

The Slice 2 batch-1 pool of 1430 units reproduces on main with 1313
quarantine candidates, 2086 joining edges and 19 collective support sets. The
canonical collective sets have 1186 to 1311 contributors each. The 1430 units
fall into 11 families and the tainted family holds all 1313 flagged units.
Most joins are canonical `collective_union` (537), canonical
`forward_containment` (508) and raw `collective_union` (389). INFERRED: shared
Faust idiom shingles, common to many cleared files, drive containment and
collective coverage against large rejected libraries.

## Proposal

`faustcoder.comparison_scope.ComparisonScope(idiom_min_docs=D)`, version
`t06-comparison-scope-df.v1`. On each stream a 5-token shingle is an idiom
shingle when it occurs in at least D distinct non-comparison pool items.
Comparison items are never counted. Idiom shingles are removed only from
forward containment, reverse containment and collective support. Exact
hashes, token Jaccard, the floor-token verbatim run and the short character
match are unchanged. Evidence records a `comparison_scope` entry per stream,
and `binding.json` records the scope and the module hash.

`python -m diagnostics.batch1_review ... --comparison-scope-min-docs D`
enables it. Without the flag, output is unchanged.

## Recompute (OBSERVED, box, inputs mirrored read-only from Delphi)

| D | Flagged (of 1430) | Unflagged by scope | 174 cohort flagged | Edges | Collective sets | Short groups | Families |
| --- | --- | --- | --- | --- | --- | --- | --- |
| none (main) | 1313 | 0 | 172 | 2086 | 19 | 23 | 11 |
| 5 | 661 | 652 | 93 | 1168 | 11 | 23 (identical) | 431 |
| 10 | 820 | 493 | 109 | 1323 | 15 | 23 (identical) | 299 |
| 20 | 975 | 338 | 135 | 1505 | 18 | 23 (identical) | 197 |
| 50 | 1083 | 230 | 141 | 1662 | 18 | 23 (identical) | 140 |

No unit becomes newly flagged at any D. The largest family still holds every
flagged unit at every D, so the scope reduces over-linking but does not split
the tainted component (OBSERVED). The surviving canonical collective sets at
D = 20 still have 74 to 760 contributors.

## Planted-window sensitivity (OBSERVED, not FLOOR qualification)

`diagnostics/scope_plant_check.py` appends each of the 200 unlabeled candidate
windows to hosts that do not already join that comparison blob and checks the
pairwise predicates with and without the scope. Windows are not gold and no
label is implied. Lost = detected without scope, missed with scope.

| Plants | Raw tokens | Baseline detected | Lost D=5 | Lost D=10 | Lost D=20 | Lost D=50 |
| --- | --- | --- | --- | --- | --- | --- |
| m=1, 50 | 17 | 5 | 5 | 5 | 4 | 4 |
| m=1, 50 | 25 | 18 | 8 | 11 | 7 | 10 |
| m=1, 50 | 35 | 36 | 8 | 9 | 7 | 9 |
| m=1, 50 | 50 | 50 | 0 | 0 | 0 | 0 |
| m=2, 92 to 99 | 17 | 8 | 8 | 8 | 7 | 7 |
| m=2, 92 to 99 | 25 | 27 | 12 | 17 | 14 | 16 |
| m=2, 92 to 99 | 35 | 50 | 14 | 15 | 15 | 18 |
| m=2, 92 to 99 | 50 | 99 | 0 | 0 | 0 | 0 |

Every 50-token plant is still caught by the raw verbatim run. Below the
floor the scope loses detections, mostly canonical `forward_containment`
(INFERRED: some of those baseline hits are themselves idiom-driven), and it
gains a few raw `forward_containment` hits. Copy-masking risk: text copied into
at least D cleared files becomes idiom for containment. D = 20 had the lowest
total plant loss (54) in this sweep; that is a measurement, not a selection.

## Human steps

1. ADVERSARY review of the predicate change and of copy-masking.
2. Fixed-label FLOOR qualification with and without the scope.
3. Gate decision on whether any D ships. The default stays `None` until then.

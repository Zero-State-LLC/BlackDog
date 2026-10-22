# T06 idiom filter (draft, default off)

This is an opt-in diagnostic proposal, not a shipping or source-label decision.
`TOKEN_FLOOR=40` remains provisional; T07 remains unfrozen. Danny approved
COPY/shared lineage for the exact pinned
`filter.lib` / `filters.lib` pair for leakage and family handling. See the
[hash-bound approval, receipt and remaining gates](../runbooks/qualification-sprint.md#superseding-filter-pair-copy-approval--2026-10-22).
This does not grant production admission or authorize merging PR #110.

## Configuration and naming

`IdiomFilter(idiom_min_docs=D, idiom_min_repos=k)` uses version
`t06-idiom-filter-df.v2`. The default k is 2: a shingle must occur in at least D
non-comparison items AND at least k distinct known repositories. Missing repo
identities contribute no repository support. Comparison items never count.
This prevents one repository alone from teaching the filter to suppress its
copied code; copied code spread across multiple repositories remains a risk.
The learned set still comes from the evaluated pool and is not independent gold.

Use `--idiom-filter-min-docs D --idiom-min-repos k` to enable it.
`ComparisonScope` and `--comparison-scope-min-docs` remain compatibility aliases.
Omitting the enable flag still passes `scope=None`; k alone does not enable it.
The feature is called **idiom filter**, distinct from the existing
`incomplete_comparison_scope` blocker for missing comparison inputs
(`diagnostics/batch1_review.py`). Receipts record it as `idiom_filter`.
Scope off is the label `scope=off`, not an omitted field.

Only enabled containment uses the learned filter. Exact hashes, token Jaccard,
floor-token verbatim runs and short matching are unchanged. Collective
membership uses `COLLECTIVE_MIN_MARGINAL` (OBSERVED value 1,
`faustcoder/neardup.py`) on every path, including scope off. A unit joins only
when it adds at least that many comparison shingles that no already selected
unit covers. Selection is greedy by new coverage, then unit id, and stops when
the union meets the existing 1/2 containment threshold. Groups still require at
least three selected contributors. This is a deterministic coverage witness,
not a minimum-set proof. Incidental overlap does not join.

## Binding and validation

`binding.json` always records `idiom_filter` with on/off, D, k, version, label
(`scope=off` when disabled) and a hash of the sorted raw and canonical learned
sets (OBSERVED, `diagnostics/batch1_review.py`). It always lists
`faustcoder/comparison_scope.py` among bound code files, because the default
path calls `scoped()`. Every output file has a SHA-256 and the same
`idiom_filter` descriptor in `binding.json` `outputs`. The binding file itself
is excluded to avoid a circular hash. Retain it as the trusted run receipt; it
is not a signature or human approval. `validate_outputs(output)` rejects a
missing idiom-filter record, a missing `comparison_scope.py` code hash,
missing/extra/changed files, hash mismatches, and scope-on outputs paired with
an off binding.

`candidate-ledger.json`, `summary.json`, match evidence, and every packet JSON
embed `idiom_filter`, including `scope=off`. Packet Markdown prints that label.
Collective group ids include the same kind of mark, so dropping the scope from
the group key changes the id. Tests fail when the scope record is deleted, the
scope is dropped from the group key, `comparison_scope.py` is tampered with
without the binding hash changing, or an output hash does not match.

Scope-off bytes are not identical to main. OBSERVED intentional fields, beyond
code hashes of files this branch edits:

- `binding.json`: `idiom_filter`, `outputs` (sha256 plus `idiom_filter` per file),
  and `code["faustcoder/comparison_scope.py"]`.
- `idiom_filter` on `candidate-ledger.json`, `summary.json`,
  `match-evidence.json`, `comparison-ledger.json`, `short-collision-groups.json`,
  `batch2-proposed-subset.json`, `review-decisions.UNAPPROVED.json`, and each
  `packets/*.json`.
- An idiom-filter label line on each `packets/*.md`.
- Collective contributor lists, group ids, quarantine flags, evidence paths,
  summary counts, and packet membership, because `COLLECTIVE_MIN_MARGINAL`
  applies with the filter off. Counts for group `202bb19f` are in the section
  below. `source-index.json` is not given an inline `idiom_filter` field.

## Replay and evidence corrections

The earlier historical review-v2 comparison was **1657/1659 byte-identical**,
not 1659/1659: absolute `source_path` values differed in `candidate-ledger.json`
and `source-index.json`. Of those 1659 payloads, **1430 are input source copies
and 229 are computed outputs**. This is a provenance/path difference, not a
claim that all 1659 files were newly computed. Bindings are reported separately.

An earlier commit on this branch reported that scope-off family ids and
evidence edges matched main `3ab3d1c`. That claim described the tree before
`COLLECTIVE_MIN_MARGINAL` applied with the idiom filter off. It does not
describe the current scope-off clustering. No claim of a fresh full 1659-file
serialization replay is made here.

## Collective membership on the 1430-unit pool

OBSERVED on the pinned public corpus (1430 cleared units, 19 comparison blobs,
0 blob-hash mismatches). Function bodies are the lexical spans from
`diagnostics/span_corpus.py` `definitions`. The scope-off any-overlap group
key for canonical `filters.lib`, without the new scope mark, is
`sha256:202bb19f7d3304d9a19c9f11dbcbc9ec15e10c8e5fa581a9ca176ed721a3a473`
(`faustcoder/neardup.py` group key before the mark was added). That is the
review group `202bb19f`.

`COLLECTIVE_MIN_MARGINAL` is 1 (`faustcoder/neardup.py:85`). D=20 below is
`IdiomFilter(20)` with `idiom_min_repos` 2, the current default. The review's
760-member D=20 figure was a v1 run without that repository gate and was not
recomputed here (the constructor refuses `idiom_min_repos` below 2).

| Setting | Rule | filters.lib canonical members | Flagged units | Newly flagged |
| --- | --- | --- | --- | --- |
| scope off | any shared shingle | 1311 (`202bb19f`) | 1313 |  |
| scope off | marginal coverage | 3 | 686 | 0 |
| D=20, k=2 | any shared shingle | 772 | 976 |  |
| D=20, k=2 | marginal coverage | 10 | 466 | 0 |

OBSERVED: scope off unflags 627 units and adds none. D=20 unflags 510 and adds
none. Scope-off coverage is 2029/2660 shingles from all 1311 overlapping units,
and 1406/2660 from the 3 selected units. At D=20 the denominator is 1987
idiom-filtered shingles; coverage goes from 1356/1987 (772 members) to
1011/1987 (10 members).

OBSERVED: the 3 scope-off contributors are
`tests/impulse-tests/dsp/filter.lib` (`u8ea99a0a7cb570b53333`),
`examples/physicalModeling/faust-stk/piano1.dsp`, and
`examples/SAM/virtualAnalog/virtualAnalogWithEffectsForBrowser.dsp`.
The same three remain inside the 10-member D=20 set. The group id changes
because the contributor list and the `scope=off` mark are part of the key
(`faustcoder/neardup.py:630`).

The D=20 marginal flag count 466 and 16 collective sets match the D=20 row of
the earlier k=2 table below. Other D rows in that table were not recomputed
in this pass. The "largest selected group" column was not recomputed here.

Previously recorded enabled sweep (k=2) on the local public 1430-unit pool.
D=20 flagged count 466 and 16 collective sets were reproduced in the section
above. The other cells were not recomputed in this pass:

| D | Flagged | Newly flagged | Edges | Collective sets | Largest selected group |
| --- | --- | --- | --- | --- | --- |
| 5 | 498 | 0 | 986 | 10 | 127 |
| 10 | 429 | 0 | 923 | 13 | 55 |
| 20 | 466 | 0 | 951 | 16 | 88 |
| 50 | 468 | 0 | 955 | 16 | 28 |
| 200 | 617 | 0 | 1094 | 11 | 14 |
| 400 | 658 | 0 | 1133 | 10 | 12 |

Zero new flags is an observation on this pool and these settings, not a guarantee.
The historical v1 counts are superseded by this k=2 / coverage-witness sweep.

## Corrected plant sensitivity (not gold recall)

Counts are **distinct window IDs with a lost/gained host row**, not row sums over
m=1 and m=2. Net = gained minus lost. A window lost at one host and gained at
another may appear in both sets. Separate by-D union counts and per-D/per-m
counts are retained. Floor artifacts are baseline detections caused solely by a
short host crossing 40 when its pre-plant text already meets forward containment;
they are excluded from scope-loss/gain counts and reported separately.

Original 200 byte windows, k=2; all D include m=1 and m=2:

| D | m=1 lost | gained | net | m=2 lost | gained | net |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 14 | 4 | -10 | 23 | 4 | -19 |
| 10 | 14 | 4 | -10 | 23 | 5 | -18 |
| 20 | 10 | 1 | -9 | 22 | 2 | -20 |
| 50 | 11 | 1 | -10 | 21 | 2 | -19 |
| 200 | 9 | 0 | -9 | 18 | 1 | -17 |
| 400 | 6 | 0 | -6 | 13 | 0 | -13 |

There are 15 floor-artifact windows at m=1 and 19 at m=2 in that original set.
These corrected figures also change the filter (k=2), so they are not a mere
relabeling of the historical v1 distinct-loss counts 30/36/34/37 of 200.

Expanded 900-window set adds 700 synthetic token-prefix windows: 50 each at
36 through 49 tokens, derived from the original 50-token windows. They are
explicitly marked synthetic, hash-bound, and are not new original byte slices
or human-approved gold. Per-width counts are retained in the receipt.

| D | m=1 lost | gained | net | m=2 lost | gained | net |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 46 | 6 | -40 | 79 | 8 | -71 |
| 10 | 44 | 5 | -39 | 73 | 10 | -63 |
| 20 | 41 | 1 | -40 | 71 | 6 | -65 |
| 50 | 33 | 1 | -32 | 63 | 6 | -57 |
| 200 | 27 | 0 | -27 | 53 | 4 | -49 |
| 400 | 19 | 0 | -19 | 35 | 0 | -35 |

The expanded sweep has 19 floor-artifact windows at m=1 and 40 at m=2, excluded
above. It places 900 m=1 rows and 1720 m=2 rows; 80 windows lack a second eligible
host under the existing host selector. No window is wholly unplaced. There are
51 rows with decreasing detection across increasing D, including 30 with
direction reversals; both lists are retained in the receipt.

All tested D retain non-artifact losses in this diagnostic. These unlabeled,
partially underfilled hosts cannot establish which D is adoptable or its true
copy recall. No D is selected; fixed-gold qualification and human review remain
necessary. The earlier blanket “no D is adoptable” conclusion is unsupported.

## Receipt location and limits

Local evidence is outside Git in `outputs/blackdog-t04-x86/pr110-review-20261022/`
(relative to the Codex workspace, not this repository). It contains the plant
CSV, window definitions, original/expanded summaries, full-pool recompute,
mutation checks and test logs. Nineteen public comparison blobs were Git-hash
verified; 1430 selected inputs came from the existing local replay. No Delphi
writes, private task access, label changes, production admission or floor freeze
are part of this work. The external original recompute README was not available
locally; the receipt README and this page state the corrected claims.

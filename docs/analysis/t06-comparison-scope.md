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
`incomplete_comparison_scope` blocker for missing comparison inputs.

Only enabled containment and collective support use the learned filter. Exact
hashes, token Jaccard, floor-token verbatim runs and short matching are unchanged.
Enabled collective groups greedily select the largest marginal shingle coverage
(ties by unit ID) until the coverage threshold is reached. Incidental one-shingle
contributors are not all joined. Groups still require at least three selected
contributors; this is a deterministic coverage witness, not a minimum-set proof.
The default-off collective algorithm is intentionally unchanged for replay.

## Binding and validation

`binding.json` always records on/off, D, k, version and a hash of the sorted raw
and canonical learned sets, plus the `comparison_scope.py` code hash even off.
Every output, including source copies and Markdown packets, has a SHA-256 and
scope descriptor in the binding. The binding itself is excluded to avoid a
circular hash. Retain it as the trusted run receipt; it is not a signature or
human approval. `validate_outputs(output)` rejects missing/extra/changed files
and inconsistent scope metadata, including scope-on outputs paired with an
off binding.

Enabled JSON ledgers, summaries and packets also embed scope metadata; packet
Markdown displays it. Off outputs retain their historical bytes and are scoped
through the per-output entries in the binding. Collective group IDs bind the
filter settings and the learned stream-set hash. Mutation checks confirm tests
fail when scope binding, group scope binding or the module code hash is removed.

## Replay and evidence corrections

The earlier historical review-v2 comparison was **1657/1659 byte-identical**,
not 1659/1659: absolute `source_path` values differed in `candidate-ledger.json`
and `source-index.json`. Of those 1659 payloads, **1430 are input source copies
and 229 are computed outputs**. This is a provenance/path difference, not a
claim that all 1659 files were newly computed. Bindings are reported separately.

The current full-pool scope-off replay equals original main `3ab3d1c` in both
family IDs and complete evidence edges. A separate serialization fixture
reproduces every non-binding output byte-for-byte against that main version.
No claim of a fresh full 1659-file serialization replay is made here.

The corrected enabled sweep (k=2) on the local public 1430-unit pool is:

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

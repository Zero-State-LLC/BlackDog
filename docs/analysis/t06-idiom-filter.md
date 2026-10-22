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
Omitting that flag still passes `scope=None`; k alone does not enable it.
There is no `ComparisonScope` alias and no `--comparison-scope-min-docs` alias.
The feature is called **idiom filter**, distinct from the existing
`incomplete_comparison_scope` blocker for missing comparison inputs
(`diagnostics/batch1_review.py`). Receipts record it as `idiom_filter`.
Scope off is the label `scope=off`, not an omitted field.

Only enabled containment uses the learned filter. Exact hashes, token Jaccard,
floor-token verbatim runs and short matching are unchanged. The shipping
collective rule is unchanged from main: any non-comparison unit that shares a
shingle may join, the group still needs at least three contributors, and their
union must cover at least half of the comparison shingles
(`faustcoder/neardup.py`). Scope off does not append a filter mark to the
group key, so those group ids stay main's unmarked ids.

Marginal coverage is a separate opt-in, `--marginal-coverage`, recorded as
`marginal_coverage` in `binding.json`. It is not turned on by the idiom filter.
`COLLECTIVE_MIN_MARGINAL` (OBSERVED value 1, `faustcoder/neardup.py:89`) applies
only on that path. Selection is greedy by new coverage, then unit id. It does
not stop at the 1/2 threshold while fewer than three contributors are selected.
It stops once three contributors meet that threshold, or when no remaining unit
supplies the minimum. A unit whose overlap is already covered does not join.
This is a deterministic coverage witness, not a minimum-set proof, and it is
not the shipping H1 rule.

## Binding and validation

`binding.json` always records `idiom_filter` with on/off, D, k, version, label
(`scope=off` when disabled) and a hash of the sorted raw and canonical learned
sets (OBSERVED, `diagnostics/batch1_review.py` `scope_descriptor`). It always
records `marginal_coverage` (false unless `--marginal-coverage` is passed).
It always lists `faustcoder/idiom_filter.py` among bound code files, because
the default path calls `scoped()`. Every output file has a SHA-256, the same
`idiom_filter` descriptor, and the same `marginal_coverage` flag in
`binding.json` `outputs`. The binding file itself is excluded to avoid a
circular hash. Retain it as the trusted run receipt; it is not a signature or
human approval. `validate_outputs(output)` rejects a missing idiom-filter
record, a missing marginal-coverage flag, a missing `idiom_filter.py` code
hash, an inventory mismatch, a per-receipt scope or marginal-coverage mismatch,
an inline ledger or summary mismatch, a packet JSON or Markdown scope mismatch,
and an output hash mismatch.

`candidate-ledger.json`, `summary.json`, match evidence, and every packet JSON
embed `idiom_filter`, including `scope=off`. Packet Markdown prints that label.
An enabled idiom filter is part of the collective group key, so two different
D values do not share a group id when the selected units match. Scope off does
not add that mark. Tests fail when the scope record is deleted, the filter is
dropped from an enabled group key, `idiom_filter.py` is tampered with without
the binding hash changing, a learned idiom set changes without
`idiom_set_sha256` changing, or an output hash does not match. `run` calls
`validate_outputs` on the output directory.

With both opts off, collective membership, group ids, quarantine flags and the
19 collective sets match main. OBSERVED intentional differences, beyond code
hashes of files this branch edits:

- `binding.json`: `idiom_filter`, `marginal_coverage`, `outputs` (sha256,
  `idiom_filter`, and `marginal_coverage` per file), and
  `code["faustcoder/idiom_filter.py"]`.
- `idiom_filter` on `candidate-ledger.json`, `summary.json`,
  `match-evidence.json`, `comparison-ledger.json`, `short-collision-groups.json`,
  `batch2-proposed-subset.json`, `review-decisions.UNAPPROVED.json`, and each
  `packets/*.json`.
- An idiom-filter label line on each `packets/*.md`.

`source-index.json` is not given an inline `idiom_filter` field. Detector
membership is not one of those differences when both opts are off.

## Replay and evidence corrections

The earlier historical review-v2 comparison was **1657/1659 byte-identical**,
not 1659/1659: absolute `source_path` values differed in `candidate-ledger.json`
and `source-index.json`. Of those 1659 payloads, **1430 are input source copies
and 229 are computed outputs**. This is a provenance/path difference, not a
claim that all 1659 files were newly computed. Bindings are reported separately.

An earlier commit on this branch applied marginal coverage on the default
path and changed scope-off clustering. That commit is superseded. With both
opts off, collective membership and group ids again follow main. No claim of
a fresh full 1659-file serialization replay is made here.

## Collective membership on the 1430-unit pool

OBSERVED on the pinned public corpus (1430 cleared units, 19 comparison blobs,
0 blob-hash mismatches, 0 skipped paths). Function bodies are the lexical spans
from `diagnostics/span_corpus.py` `definitions`. Shipping scope off (idiom
filter off and `marginal_coverage` off) was compared to main `ee456c73`'s
`faustcoder/neardup.py` on the same texts.

| Setting | Rule | filters.lib canonical members | Flagged units | Collective sets |
| --- | --- | --- | --- | --- |
| main `ee456c73` | any shared shingle | 1311 (`202bb19f`) | 1313 | 19 |
| scope off, marginal off | same rule | 1311 (`202bb19f`) | 1313 | 19 |
| scope off, `--marginal-coverage` | opt-in witness | 3 | 686 | 19 |

OBSERVED: scope off matches main on flagged unit ids and on every collective
group id and contributor list. The canonical `filters.lib` group id is
`sha256:202bb19f7d3304d9a19c9f11dbcbc9ec15e10c8e5fa581a9ca176ed721a3a473`.
Coverage of that group is the full any-overlap union.

OBSERVED: the opt-in rule flags 686 units, adds 0, and drops 627 relative to
scope off. It still emits 19 collective sets. The canonical `filters.lib`
witness has 3 contributors and covers 1406/2660. Its group id is
`sha256:5c2c87ebfe33b773c69e69a253175e6facec2a82677f9a26a24d0e7d75dfe888`
because the contributor list is the witness, not the any-overlap set. This
opt-in is not the shipping H1 rule. Changing the shipping rule still needs
Danny's sign-off.

Synthetic probes (OBSERVED, both streams, `tests/test_comparison_scope.py`):

| Probe | Opt-in result |
| --- | --- |
| 3-way split, pieces under 40 tokens | 3/3 contributors; the noise file is not a contributor and is not in the family |
| Interleaved 3-way (two hosts already cover half) | 3/3 |
| Two independent 3-way copies | 6/6, two distinct families |
| 4-way plus a noise file | 3/4 split files (`c0` `c1` `c2`). Selection stops once three contributors cover half, so `c3` is outside the witness. The noise file is not a contributor and is not in the family |

The shipping default joins the noise file on the 3-way probe, which is main's
any-overlap rule.

Previously recorded enabled sweep (k=2) on the local public 1430-unit pool,
from the superseded early-stop default. D is `IdiomFilter(D)` with
`idiom_min_repos` 2. Not recomputed under the restored shipping rule or the
current opt-in, and not a description of scope off:

| D | Flagged | Newly flagged | Edges | Collective sets | Largest selected group |
| --- | --- | --- | --- | --- | --- |
| 5 | 498 | 0 | 986 | 10 | 127 |
| 10 | 429 | 0 | 923 | 13 | 55 |
| 20 | 466 | 0 | 951 | 16 | 88 |
| 50 | 468 | 0 | 955 | 16 | 28 |
| 200 | 617 | 0 | 1094 | 11 | 14 |
| 400 | 658 | 0 | 1133 | 10 | 12 |

Zero new flags is an observation on that historical sweep, not a guarantee and
not the shipping scope-off result. The historical v1 counts were already
superseded by that sweep. Both are retained only as prior measurements.

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

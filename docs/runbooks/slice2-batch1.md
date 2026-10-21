# Slice 2 Batch 1 evidence completion

Batch 1 on `spark-af42` starts from merged main `585b188` on
`feat/slice2-batch1-qualification`. This completes machine evidence assembly,
not independent source approval, dataset qualification or a production freeze.
`TOKEN_FLOOR=40` remains provisional and T07 remains unfrozen.

## Results

- All 191 previously missing source blobs were retrieved at immutable inventory
  pins and matched their Git blob hashes. Retrieval does not grant rights.
- The complete scope is 1,430 candidate units and 510 verified blobs, including
  19 comparison-only blobs. All original 1,240 candidates remain covered;
  190 additional candidate rows are now available. No missing blobs or
  normalization failures remain in this scope.
- All three measurement floors flag 1,313 quarantine candidates and leave 117
  unflagged candidates, all from `grame-cncm/faustlibraries`. No floor or
  tolerance changed, and unflagged does not mean independently qualified.
- 110 packets cover every candidate exactly once. The ledger preserves original
  source hashes/ranges, rights, proposed closures, prior contract results and
  behavioral validation plans. All 362 external-member units and 23 short
  canonical collision groups remain explicitly reviewable.
- Optional clustering evidence records 2,086 joining edges and 19 collective
  support sets. Of the joining edges, 926 are collective-union links. Each
  quarantined candidate has an explanatory path to comparison evidence.
  This is a joining forest, not exhaustive pairwise matches or COPY labels.
- The proposed Batch 2 first wave has 172 units: all 44 prior bounded-contract
  passes plus 128 other eval-eligible candidates from Faust, Faust Playground
  and pd-faustgen. 170 remain quarantine candidates; 69 explanatory paths use
  collective-union evidence. The two unflagged candidates do not supply a
  second project. This is a review priority, not an admitted training subset.

## Evidence and tools

Receipts and downloaded source remain outside Git and `/tmp` under
`/home/delphi/blackdog-batch1-20261021/`. Start with `REVIEW-INDEX.md` and
`REPORT.md`. The index links all 110 packets and the machine-readable ledger,
match evidence, decision form, short-collision groups and proposed first wave.

`acquisition/` contains one retrieval receipt per missing blob, verified source
bytes and an extended discovery map. `review/` retains the initial partial
attempt that exposed tuple serialization; `review-v2/` is the successful build.
`complete-audit/` contains the three-floor replay. `validation.json` verifies
source hashes, complete packet membership and exact agreement between traced
and untraced floor-40 family assignments. Test logs and preservation manifests
remain alongside these receipts.

The new commands are `python -m diagnostics.batch1_acquire --help` and
`python -m diagnostics.batch1_review --help`, after sourcing `activate-local.sh`.
Both require explicit input paths and new output directories. The acquisition
command downloads pinned source only, bounds response size and concurrency,
and retains failures without admitting mismatched content. The review command
is offline. Neither invokes the compiler, installs dependencies or grants
rights. The clustering cache reuses shingle features without changing decisions.

## Validation and preservation

The broad no-sudo suite passed 597 tests with 2 skips and 57 warnings; the two
sudo-bearing modules (`test_compiler.py` and `test_reward_triage_sig.py`) were
excluded, so this is not a full-suite claim. Focused tracing/qualification tests
passed 68 tests, and the added end-to-end packet serialization regression passed
in the six-case Batch 1 test module. Ruff F checks, Markdown lint, Spec Kit and
`git diff --check` passed. All 104,013 pre-existing baseline entries were unchanged.
No commits, pushes, sudo, workload stops, environment installs or model downloads
were performed. Only the pinned source downloads described above were added.

## Human checkpoint and Batch 2

Review the 172-unit first wave in shared-source/behavior packets, preserving
individual exceptions. Inspect exact source, notices and direct/collective
match evidence before recording COPY or NOT_COPY. Approve dependency closure,
including external members and unadmitted helpers, separately from rights.
Approve executable semantic contracts and negative controls separately from
compile success. Unknown or conflicting cases remain quarantined.

If adjudication cannot yield cleared hosts from two repositories, identify
additional candidate projects rather than dropping comparison sources or
weakening thresholds. Formal FLOOR plants, natural-copy/FP labels, independent
development qualification, newly authored holdout custody, signing authority
and an explicit floor decision/provisional route remain subsequent gates.
No production freeze or training promotion is authorized by this batch.

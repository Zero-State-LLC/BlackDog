# Slice 1 corpus qualification

Branch `feat/slice1-corpus-qualification`, based on merged main `cd57be1`.
Merge is pending. T07 remains unfrozen and `TOKEN_FLOOR=40`
remains provisional. Diagnostic success does not approve a production manifest,
clear a dependency's rights, or establish all-domain function correctness.

## Inventory correction

Remove `s1`, `sample1`, `sample2`, `sample3`, and bare `play` from the pinned
`soundfiles.lib` inventory and matching notices. The first four are commented
examples. Bare `play` conflates a commented example with a nested environment
member; it cannot be silently replaced by a top-level function. The executable
`sound` owner remains. A future nested-member admission requires qualified
identity, owner closure, and notice review.

The LGPL entry count changes from 742 to 737; all other content remains unchanged.
The corrected corpus has 960 function identities. Admission uses new digests
computed by production `content_digest`, preserving its fail-closed checks:

- Inventory: `sha256:24456833b059f2b6b54923206a74652b49ca7e5c251668d60f02294765d7e8a1`
- Notices: `sha256:79f90f61b496afd13c04f0522fd1fd35f57c7a728d966cdf057419ce5080b4f8`

The earlier receipt-only proposed digest values differ from these production
content digests. They were not used to bypass validation. Old receipts remain
unchanged; `inventory-correction-audit.json` records both old and actual new pins
and checks that only the five removals and count adjustment occurred.

## Reproducible behavioral contracts

`diagnostics/span_qualification.py` constructs 117 explicit contracts for 44
named targets across compressors, maths, scale tuples, interpolation, analyzers,
routing, matrices, spatial audio, HOA, stereo conversion, and physical-model
helpers. References come from mathematical definitions, known permutations,
Kronecker deltas, and finite impulse responses. Private library source stays out
of Git; verified original-byte spans supply the compilation input.

Only contracts with identical ordered dependency closures may share a batch.
No neighboring contract can contribute an undeclared definition.
Contracts specify finite parameter domains. Constant answers are pulse encoded;
scalar zero answers use a fixed offset so silence detection remains active.
This is an encoding of the same answer, not a relaxed silence threshold.
Every output retains an explicit reference and channel range. Batches are capped
at 12 channels to fit the existing 8 MiB sandbox output bound. Each uses the
existing 768 MiB memory bound, 60-second diagnostic timeout, 144000 frames,
64-sample blocks, seed 1, and both 44100 and 48000 Hz. Default finite, silence,
DC, clipping, and reference checks remain enabled. Tolerances and goldens are
unchanged.

Each batch has a corrupted-reference negative control; this demonstrates
batch-wide rejection, not an isolated negative-control proof for every component.
Ascending and descending comparators also require named compiler failures when
their helper is omitted. Helper inclusion alone never promotes a helper as a
qualified target. Contracts do not prove long-tail state behavior, arbitrary
parameter domains, or runtime performance.

The ledger partitions every candidate across the 93 reviewed groups, verifies
span identity against the existing dependency ledger, and requires a complete,
duplicate-free result matrix. Every unit receives a bounded-pass or blocked
disposition. Blocked units retain concrete unresolved member expressions, helper
names, overload candidates, special forms, source identity and group oracle
plans. The original lexical graph remains an overapproximation; the driver does
not relabel it as certified closure.

## Receipts and rerun

Spark receipt root: `/home/delphi/blackdog-slice1-20261021/`, outside Git and `/tmp`.

- `candidate.UNAPPROVED.json`, `classification.json`: corrected corpus proposal.
- `inventory-correction-audit.json`: exact correction and production pin audit.
- `inputs/`, `code/`: preserved input ledgers and executed driver/regression source.
- `qualification-v1/`: initial diagnostic receipts, including zero-answer silence
  failures. Only that diagnostic queue was stopped with explicit user permission.
- `qualification-v2/`: retained output-cap abort from an oversized batch.
- `qualification-v3/`: bounded replacement run; plan, contracts, per-case source,
  compiler/signal/profile receipts, queue bindings, checksums, and qualification.
- `tests-final-nosudo.log`: final broad regression results.
- `REPORT.md`, `SHA256SUMS`: final result and receipt integrity summary.

From `~/BlackDog`, activate the existing environment and use a new receipt
output directory after any runtime/code/input change:

```bash
source ./activate-local.sh
export PYTHONDONTWRITEBYTECODE=1
python -m diagnostics.span_qualification \
  --candidate ~/blackdog-slice1-20261021/candidate.UNAPPROVED.json \
  --sources ~/blackdog-slice1-20261021/inputs/sources.json \
  --groups ~/blackdog-slice1-20261021/inputs/group-review-and-plans.PROPOSED.json \
  --closures ~/blackdog-slice1-20261021/inputs/dependency-closures.PROPOSED.json \
  --output ~/blackdog-slice1-rerun
```

The outer qualification lock and binding cover the candidate, groups, closures,
contracts, plan and runtime before any report writes. Existing unbound output
directories (including the original Slice 1 run) cannot be adopted; use a new
output directory. Complete admitted-corpus coverage and exact dependency-span
identity are checked before rendering. The queue refuses changed bindings,
tampered completed receipts and unsafe resumption. Do not remove an old binding or overwrite evidence to force reuse.

## Acceptance and remaining gates

In the original pre-review run on spark-af42, all **122/122 compiler/signal runs passed**: 60 positive
renders, 60 corrupted-reference controls and two missing-helper compiler controls.
The ledger covers all 960 candidate identities in 93 groups: **44 bounded-contract
passes, 916 blocked**. There are 117 domain contracts, packed into 30 positive
batches with paired controls. The 41 earlier span boundaries are unchanged.

Final no-sudo regressions: **567 passed, 2 skipped, 57 warnings** (123.56 seconds).
The two sudo-bearing test modules (`test_compiler.py` and
`test_reward_triage_sig.py`) were excluded; this is not a full-suite claim.
The 15 new qualification regressions also passed separately.

Preservation checked 101,121 existing files/symlinks: 101,120 are byte-for-byte
unchanged. Only generated `.pytest_cache/v/cache/nodeids` changed. Two incidental
bytecode caches were restored to their exact original checksums. Environments,
models, checkpoints, setup artifacts and prior receipts remain unchanged.
During the original diagnostic run, no sudo, model download, environment
installation, commit or push occurred.
Only the explicitly authorized initial diagnostic queue was stopped.

Slice 1's correction, diagnostic execution and exhaustive disposition are
recorded. **The production corpus-readiness exit is still blocked**; 916 units
lack completed contracts/closures, and even bounded passes require independent
manifest approval and downstream admission gates.

The next admission decision must select explicit tasks and domains from the
bounded evidence, review their source/closure manifests independently, and run
T06 H2/H3/FLOOR and project/family leakage qualification. The remaining corpus
needs external-member rights/closure review and executable stateful/special-form
oracles. A blocked ledger entry is accountable unfinished work, not an exclusion
chosen to inflate coverage. No production training subset or T07 split is approved
by this slice, and no production-readiness claim follows from its diagnostics.

## Publication review

Review added an outer receipt lock/binding, rejection of unbound existing outputs,
complete-corpus preflight, and exact dependency-span matching (including rejection
of empty span records). These fixes prevent report overwrites before a changed
queue is refused and move input failures ahead of expensive renders.

The review broad suite passed 572 tests, with 2 skipped and 57 warnings
(124.54 seconds), excluding the same two sudo-bearing modules. After the final
empty-span rejection was added, the focused suite passed 21 tests. Every one of the 62 generated DSP sources,
the plan and all 117 contracts match the original successful run exactly; the full
122 renders were not repeated for these orchestration-only fixes. All 1,308
original receipt checksums verified. Review evidence is preserved separately at
`/home/delphi/blackdog-slice1-review-20261021/`.

Publication uses `[skip ci]` because existing full CI invokes sudo, which was not
authorized for this review. Required CI must be enabled and pass before a later
merge; this PR does not request or perform a merge.

## PR 97 closure-isolation correction

Automated review found that the original batching union could let a contract use
an undeclared helper from a neighboring target. The original 122 successful
runs remain historical batch-conformance evidence; they must not establish an
isolated compilation-closure claim.

Batching now requires identical ordered `unit_ids`. Different closures and
changed overload ordering force a new batch. Regression coverage proves a
missing-helper target cannot acquire its neighbor's definitions. A real sandbox
compiler probe also rejects an omitted helper and accepts an explicit helper.
The targeted suite passed 101 tests.

The corrected plan retains 117 domain contracts and has 52 positive batches,
52 corrupted-reference batches and two missing-helper controls: 210 runs across
both rates. Fresh results and resumability/integrity verification are recorded
in PR #97 and `/home/delphi/blackdog-pr97-closure-fix-20261021/`, separately from
all original receipts. Existing CI sudo operations were subsequently authorized;
all required checks must pass on the corrected branch before merging.

# Corpus-wide span review and resumable validation

`diagnostics.span_corpus` accounts for every admitted function in one pass. It
produces unapproved lexical proposals and a review queue grouped by source file
and syntax risk. It does not grant rights, certify dependency closure, or freeze
T07. TOKEN_FLOOR=40 remains provisional.

## Scope and gates

The lexer respects original UTF-8 bytes, CRLF, comments, quoted strings, balanced
parentheses/brackets/braces, and top-level statement terminators. Documentation
blocks are skipped outside statements. It requires a unique top-level definition
matching the inventory name (and the line suffix for overloads). A malformed
source blocks all proposals from that blob. Existing proposed ranges are checked
against the result; trailing trivia may be preserved only when token sequences
agree. Other disagreements remain blocked. No production extraction rules change.

This is deliberately not a complete Faust parser. Lexical success does not prove
that a statement is valid Faust. Identifier hints include parameters, built-ins,
and local identifiers; they are not dependency closures. Syntax risks guide
review and can miss semantic recursion or state. Every proposal still requires
independent boundary, dependency, provenance and digest review.

The pinned Faust parser feasibility inspection is recorded in
[the pilot runbook](span-review-pilot.md#upstream-parser-feasibility). That
inspection found line metadata but no byte-offset export in the inspected
interfaces, so this implementation does not patch or install the compiler.

## Generate candidates

From the activated checkout, use existing source mappings and the preserved
41-span pilot candidate. Choose a new receipt directory outside Git and `/tmp`.

```bash
source ./activate-local.sh
export PYTHONDONTWRITEBYTECODE=1
pilot="$HOME/blackdog-span-pilot-20261021"
receipts="$HOME/blackdog-span-corpus-20261021"
python -m diagnostics.span_corpus propose \
  --inventory corpus/rights-inventory.v1.json \
  --notice corpus/notice-manifest.v1.json \
  --candidate "$pilot/function-spans.candidate.json" \
  --sources "$pilot/sources.json" \
  --output "$receipts/proposals-final"
```

The output directory must not exist. `classification.json` accounts for every
unit, including explicit blockers, review groups and existing-proposal matches.
`candidate.UNAPPROVED.json` contains only unambiguous proposals with exact hashes;
it is not an independently approved manifest. Source maps are verified against
Git blob hashes before classification. Private data belongs in receipt directories,
never in the repository.

## Validate and resume

Use an explicit reviewed diagnostic plan in the existing span-review format.
The queue never generates arbitrary wrappers or claims unused definitions were
exercised. Keep the existing independent references and negative controls.

```bash
python -m diagnostics.span_corpus queue \
  --inventory corpus/rights-inventory.v1.json \
  --notice corpus/notice-manifest.v1.json \
  --candidate "$pilot/function-spans.candidate.json" \
  --sources "$pilot/sources.json" \
  --plan "$pilot/plan.json" \
  --output "$receipts/queue"
```

Repeat the exact command to resume. One worker runs at a time under an exclusive
lock. Whole cases are checkpointed; an interrupted case gets a new attempt
directory and retains its earlier evidence. Completed failures remain failures,
not automatic retries. Harness exceptions abort immediately. Changed source,
plan, spans, Python code, worker files, runtime pins, executable identities or
execution settings require a new queue directory. Completed receipt files are
hashed and checked before reuse. These hashes detect accidental corruption; they
are not independent attestations against an actor rewriting all receipts.

The runner retains the existing sandbox, default signal checks, tolerances,
resource limits, and 44.1/48 kHz profiles. No sudo, workload stops, environment
installation or model downloads are needed. Do not interpret pilot replay as
behavioral coverage of newly proposed definitions.

## Review progression

1. Review source-file/syntax groups and resolve every explicit blocker.
2. Establish dependency groups and representative parameter/domain coverage.
3. Add independently justified references or clearly labeled property tests for
   each intended admission, with dependency-omission and wrong-reference controls.
4. Run new plans in new bound queues; archive logs, sources, results and checksums.
5. Report boundary-reviewed, dependency-qualified, compiled and behavior-qualified
   counts separately. Complete T06 H2/H3/FLOOR and T07 split/leakage qualification
   before requesting an independently approved digest or freeze.

## First corpus-wide run on spark-af42

The 2026-10-21 run accounts for all 965 inventory functions: 960 unapproved
proposals (including all 41 preserved pilot spans, plus 919 new proposals) and
five explicit blockers. The proposals form 93 source-file/syntax review groups.
All 41 existing ranges reproduce exactly, including the trailing comment in
`cross2`. No prior candidate was replaced.

The five blockers are `play`, `s1`, `sample1`, `sample2`, and `sample3` in
`soundfiles.lib`. Inspection found the latter four in a block-comment example;
`play` appears in that example and as a nested environment member. The inventory
identities need review before exclusion or reassignment. This run does not amend
inventory or silently promote commented/nested definitions.

The original pilot passed all 79 checks through the queue. This validates the
existing 41-case plan, not the 919 new proposals. Targeted regression validation
passed 116 tests; a subsequent 74-test subset passed after four additional queue
and nested-definition tests were added (120 distinct tests across the two runs).
Receipts are at `/home/delphi/blackdog-span-corpus-20261021/`.

The [93-group static review](#93-group-review-and-inventory-corrections) now
provides dependency candidates and representative plan designs. Next, qualify
the proposed closures and turn those designs into executable cases. Do not
mass-compile guessed wrappers or count lexical proposals as behavior-qualified
units. TOKEN_FLOOR=40 remains provisional and
T07 remains unfrozen.

## Pre-PR review

Review added refusal of existing queue evidence without its original binding and
of symlinked queue files. Malformed trailing text in an existing span now records
a boundary disagreement instead of aborting corpus classification. Temporary
receipt-path checks also resolve the platform's `/tmp` alias before comparison.

All 123 targeted tests passed after these changes on spark-af42. The regenerated
candidate is byte-identical to the original 960-proposal result. Separate review
receipts are at `/home/delphi/blackdog-span-corpus-review-20261021/`; original
receipts remain unchanged. Full CI was skipped for the initial PR because that
step prohibited sudo.
After existing CI operations were authorized, PR #95 merged as `0542321`: all
eight checks passed, including 722 tests (63 warnings). Review added atomic
checkpoint publication and an interrupted-publication regression. Merged-main
verification on Spark passed 124 targeted tests, 79/79 pilot checks and reuse of
all 41 cases. Receipts: `/home/delphi/blackdog-pr95-main-verification/`.
These pilot checks cover the existing plan, not the 919 new proposals.

## 93-group review and inventory corrections

The source-backed static review on spark-af42 used main `0542321` and the
validated Faust library tree at `2edec0537f53` (library version 2.80.0). It accounts
for all 965 inventory functions: 960 proposed spans in 93 groups and five
source-backed correction dispositions. All 960 span hashes and dependency target
identities verified. **No dependency closure was certified and no behavioral
test was executed during this review.** Lexical proposals remain unapproved.

The ledger proposes 1,318 dependency links and transitive candidate sets. Of the
960 units, 362 have external or scoped references and 38 reference names matching
local definitions absent from the admitted span set. All 17 referenced library
files are locally available, but availability does not grant rights. Parameters,
local shadowing, overload order/dispatch, environment members, primitives and
foreign ABI declarations still need explicit resolution.

### Five proposed inventory corrections

Evidence is from `soundfiles.lib`, blob
`63349341fd766d6064725c8881ddaf002b7a1ce2`, at the pinned library revision.

| Identity | Source evidence | Proposed disposition |
|---|---|---|
| `s1` | Line 282, inside block comment at lines 277–306 | Remove commented example from top-level inventory |
| `sample1` | Line 283, same comment | Remove commented example from top-level inventory |
| `sample2` | Line 284, same comment | Remove commented example from top-level inventory |
| `sample3` | Line 285, same comment | Remove commented example from top-level inventory |
| `play` | Commented example at line 299; executable member at line 240 inside `sound(sf, part)` | Remove ambiguous bare identity; any separate nested member needs a qualified identity, owner closure and notice review |

The receipt-only inventory/notice candidates remove five function records and
five notice rows; the affected inventory entry count changes from 742 to 737.
They retain source-rights metadata as provenance, not approval of the correction.
**Neither candidate is applied.** The production parser correctly refuses it
with `inventory digest does not match the T05 pin`. Adoption requires a separately
reviewed inventory/notice correction, coordinated T05 repinning, and rebuilding
and reviewing span manifests bound to those digests. Do not bypass the pin check.
The current pinned inventory still contains 965 function identities.

### Next validation steps

| Review wave | Groups | Required work |
|---|---:|---|
| Bounded deterministic | 31 | Resolve finite domains and concrete parameters; qualify scalar/tuple, routing, reduction and small-matrix references |
| Scoped or stateful | 34 | Resolve local shadowing and complete closures; specify initial state, reset, timelines and valid parameter domains |
| Specialized harness or oracle | 28 | Establish foreign/runtime contracts, namespace/UI/asset drivers, controlled stochastic excitation and converged physical/nonlinear references |

These waves prioritize review; they do not certify every member as runnable.
Start with the six concrete designs for `ratio2strength`, `strength2ratio`,
`identity`, `comparatorAsc`, `log2` and `ionian`. Resolve each closure and verify
that its wrapper exercises the intended unit. Turn the independent expected
values into executable references, retaining omission and wrong-reference
negative controls. Constant outputs need bounded pulse wrappers or explicit
contract tests; do not disable DC/clipping or finite checks to make them pass.

Plans retain 44.1/48 kHz, block size 64, existing tolerances and resource caps.
The current sparse-impulse queue cannot express every proposed timeline, asset
or property check; implement and regress those drivers before claiming coverage.
Keep compile success, behavioral qualification and independent approval separate.
After per-unit qualification, complete T06 H2/H3/FLOOR and T07 split/leakage gates.
`TOKEN_FLOOR=40` remains provisional; **T07 remains unfrozen**. This review does
not create a dataset admission, golden, holdout or training authorization.

### Group-review receipts and preservation

Receipt root: `/home/delphi/blackdog-span-group-review-20261021/`, outside Git and
`/tmp`. No off-host backup is claimed for this review.

- `REPORT.md`, `summary.json`, `GROUPS.md`: findings and all 93 groups.
- `group-review-and-plans.PROPOSED.json`: group membership, risks and behavior designs.
- `dependency-closures.PROPOSED.json`: per-unit candidate links and unresolved scopes.
- `external-library-evidence.json`: validated tree identity, namespace mappings and hashes.
- `inventory-dispositions.PROPOSED.json`: exact source offsets and correction rationale.
- `rights-inventory.UNAPPROVED.json`, `notice-manifest.UNAPPROVED.json`:
  unapplied correction candidates; `inventory-correction-check.json` records
  candidate digests and the expected T05-pin refusal.
- `first-wave-behavior-cases.PROPOSED.json`: six unexecuted case designs.
- `review-validation.json`, `review_groups.py`, `sources/`: static validation and
  private reproducibility evidence; source copies stay outside the repository.
- Preservation records and `SHA256SUMS`: 100,876 existing files/symlinks unchanged;
  all 1,648 prior receipt checksums passed and 46 new receipt-file hashes verified.

Environments and prior receipts were preserved. No sudo, workload stops,
downloads, installs or training occurred during the review.

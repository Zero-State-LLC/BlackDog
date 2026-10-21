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

Next, review the 93 groups and establish explicit dependency closures and
representative plans. Do not mass-compile guessed wrappers or count lexical
proposals as behavior-qualified units. TOKEN_FLOOR=40 remains provisional and
T07 remains unfrozen.

## Pre-PR review

Review added refusal of existing queue evidence without its original binding and
of symlinked queue files. Malformed trailing text in an existing span now records
a boundary disagreement instead of aborting corpus classification. Temporary
receipt-path checks also resolve the platform's `/tmp` alias before comparison.

All 123 targeted tests passed after these changes on spark-af42. The regenerated
candidate is byte-identical to the original 960-proposal result. Separate review
receipts are at `/home/delphi/blackdog-span-corpus-review-20261021/`; original
receipts remain unchanged. Full CI is intentionally skipped for the initial PR
because it invokes sudo; the no-sudo targeted results do not replace full CI.

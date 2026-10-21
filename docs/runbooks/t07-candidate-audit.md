# T07 dataset-qualification candidate on spark-af42

## Status and scope

The offline audit on 2026-10-20 PT (2026-10-21 UTC) used main `a414dfd`.
**Candidate audit complete; split NOT FROZEN.** It produced metadata and an
unsigned proposal, not a `DatasetSnapshot`, signed `SplitManifest`, new rights
clearance or training authorization. `stack_pin_allowed=false` remains in force.

The search covered home-directory `.dsp`/`.lib` files, excluding hidden paths,
virtual environments, `node_modules`, model/checkpoint stores and `blackdog-*`
receipt roots. System paths, archives, external mounts and network sources were
outside scope. All 501 discovered source files were read in memory; source text
was not copied into the receipts. Matching Git-blob hashes establish local byte
availability against the pinned inventory, not independent project provenance.

| Audit measure | Result |
|---|---|
| Inventory | 46 entries; 2,259 file/function rows |
| Matching local blobs | 1,993 rows; 266 not found within scope |
| Notice matches | 183 unmatched rows: 144 rejected and 39 needs-human; no cleared row lacks a matching notice |
| Function units | 1,784 rows total; 1,717 available rows excluded pending extraction and unit-rights qualification |
| Whole-file screening | 302 whole-file/fixture items; 252 families; reversing input order preserved assignments |
| Unmapped local blobs | 117 hashes outside the pinned inventory; excluded from the candidate |
| Preservation | 90,351 existing files/symlinks unchanged; Git status unchanged; 14 off-host receipt checksums passed |

Function rows may share a blob; available rows are not independent examples.
Notice matching preserves existing rights decisions and does not establish new
approval or complete attribution. Screening uses existing normalization and
family clustering with provisional `TOKEN_FLOOR=40`; thresholds were unchanged.
It does not implement the full T05/T06 admission state machine or establish
complete leakage qualification, especially for missing sources and function units.

## Proposed project and family splits

| Partition | Proposal | Qualification still needed |
|---|---|---|
| Training pool | 240 whole-file rows in 210 families, all `grame-cncm/faust` | Keep families together; qualify rights/provenance, duplicate handling, DSP tasks and coverage before admission |
| Development | No assignment | An independently qualified project, pinned source availability and cross-project family screening |
| Sealed holdout | No assignment or creation | Newly written independent tasks, separate custody and an exclusion/family manifest |

The training pool contains 159 LGPL, 40 BSD, 35 MIT, four STK and two GPL rows.
Training eligibility does not grant evaluation or redistribution rights. Family
rights are intersected; mixed-license families are held for review. Do not
randomly split Faust files to claim project-disjoint evaluation.

Of these 240 rows, 35 have prior Qwen compiler/signal sanity results only; 205
still need compiler/signal/task qualification. No semantic waveform acceptance
is claimed. All 14 failed smoke-admission examples remain excluded, as do 22
available whole-file rows in fixture/non-cleared comparison families. The original
28 training / 7 diagnostic smoke history is preserved; neither becomes sealed.

| Upstream project | Matching local blob rows / inventory rows |
|---|---|
| `grame-cncm/faust` | 273 / 441 |
| `grame-cncm/faustlibraries` | 1,719 / 1,719 |
| `grame-cncm/faustplayground` | 1 / 90 |
| `CICM/pd-faustgen` | 0 / 9 |

Other inventory entries have no enumerated units. The single matching Playground
blob is not an independently qualified development project. Library function
blobs cannot be promoted into whole-file evaluation units.

No holdout exclusion manifest was supplied. The owner's earlier confirmation
that no sealed holdout existed is historical, not proof of current global
absence. Per spec §9, holdout tasks must be newly written, not mined from public
examples/libraries or reused from exposed smoke diagnostics.

## Freeze blockers and acceptance

1. Qualify real function units using the reviewed-span extraction infrastructure
   merged in #89 (`adee7ae`); [verification and receipts](function-spans.md#merged-main-verification-and-receipts)
   cover 668 full-CI tests and 143 merged-main Spark regressions. No production
   range manifest is approved, and this audit has not been rerun with functions
   admitted. Review boundaries, dependency safety and rights; preserve blob-wide
   quarantine. Complete T06 H2/H3, then FLOOR. Prefer the accepted-floor route.
   A permitted provisional-floor freeze requires an explicit leakage
   caveat and scheduled novelty recheck; later exclusions need removal receipts.
   No P3 exit claim may rely on the holdout before the accepted-floor recheck.
2. Resolve missing pinned sources and qualify an independent development
   project. Recheck rights, notices, upstream copies and cross-project families.
   Local presence alone does not grant rights or prove project independence.
3. Qualify candidate DSP tasks with compiler/signal evidence, semantic references,
   taxonomy coverage and exclusion dispositions. Sanity-only results are not
   reward acceptance; do not silently reinstate failed smoke examples.
4. Arrange independently authored holdout tasks and custody; screen the exclusion
   manifest against all training/development candidates without exposing holdout
   contents to training, prompt tuning or candidate selection.
5. Implement/review T07 `split_frozen` and signed-manifest verification. Require
   deterministic replay and rejection tests for cross-split families, forbidden
   eval rights, holdout contamination and modified manifests. T01/ADR-0001
   remains a project gate. No signing keys or allowed-signers files were accessed.
6. After a qualified freeze, run T08 frozen baselines, then repeated T10
   throughput/memory qualification and stack-pin review. Retain GD-1, live
   A2-PATH/EVAL-SO and P3 audit/triage/grader gates.

The proposal checks passed for candidate blob/notice/rights consistency,
exclusion of function rows and blocked families, retention of prior failures,
one training project, empty development/holdout assignments and cluster order
invariance. These are audit checks, not T07 freeze acceptance or a new test-suite run.

## Receipts and preservation

- Spark: `/home/delphi/blackdog-t07-candidate-20261021T035439Z/`.
- Off-host workspace backup: `outputs/blackdog-t07-candidate/blackdog-t07-candidate-20261021T035439Z/`.
  This path is relative to the outer local workspace, not this Git checkout.
- `corpus-audit.json`: per-row pin, notice, rights, location, family and disposition.
- `family-audit.json`: comparison IDs, thresholds, exclusions and order-invariance check.
- `split-proposal.json`: unsigned assignments and blockers; `discovery.json`: search scope and blob locations.
- `summary.json`, `proposal-checks.json`, `audit.py`, `audit.log` and `REPORT.md`: results and procedure.
- `preservation-before.json`, `preservation-after.json`, status records and `preserve.py`: preservation evidence.
- `SHA256SUMS`: 14 receipt-file hashes verified after backup. This is integrity
  evidence, not a split signature. Both stores remain outside Git and `/tmp`.

No tracked edits, sudo, workload stops, downloads, package installs, GPU work or
training occurred during the audit. Environments, models, checkpoints and prior
receipts were preserved. This documentation update does not authorize any of the
pending actions. See [Spark setup](spark-local-setup.md#next-steps),
[T07 task](../../specs/001-faustcoder/tasks.md) and [Kanban](../../KANBAN.md).

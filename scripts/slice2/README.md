# Slice 2 evidence generators

These two scripts produced Slice 2 evidence that `KANBAN.md`,
`docs/runbooks/qualification-sprint.md` and `docs/runbooks/slice2-readiness.md`
cite. They were run once, on the team Spark, on 2026-10-22 (UTC). Their
outputs are kept off-repo in the Slice 2 evidence bundle (see
[docs/HANDOFF.md](../../docs/HANDOFF.md)).

| Script | Produced | Original SHA-256 (as run) |
|---|---|---|
| `draft_closures_v3.py` | `blackdog-r2-closures-20261022T0424Z-v3` (174 R2 dependency-closure drafts) | `64bdf9ee5d7cfd200632c2f22586744c319ea283722550e4974d262d5dc85436` |
| `seven_dependencies.py` | `blackdog-seven-dependencies-20261022T053421Z` (seven approved-contract dependency checks) | `d5ca9b6c0cb5f4c33baed74f9021fbbd5818cdd98c1a30340ae04e35715c1aeb` |

Each run copied itself into its output folder (`draft_closures.py` and
`driver.py`), and those copies match the hashes above.

## Changes from the run copies

The only edits replace host-specific values with environment variables:

- `BLACKDOG_REPO`: BlackDog checkout. Default: the repo containing this file.
- `BLACKDOG_EVIDENCE_ROOT`: folder that holds the evidence input folders.
  Default: the parent of `BLACKDOG_REPO`.
- `BLACKDOG_EXPECTED_HOST`: optional. If set, the script refuses to run on any
  other hostname. The originals hard-coded this check.
- `BLACKDOG_REVIEWER_NAME` (`seven_dependencies.py` only): required. The named
  independent human reviewer, as recorded in the contract approval record.

Logic, inputs, expected digests and output layout are unchanged. Because of
these edits, the files here no longer byte-match the SHA-256 values above.

## Caveats

- Both scripts write a new timestamped folder under the evidence root and fail
  if their pinned inputs are missing or have different hashes. They are
  replay and audit references, not general tools.
- `draft_closures_v3.py` requires a clean BlackDog working tree, the pinned
  faustlibraries checkout and the S1, R2-return and direct-review input folders.
- `seven_dependencies.py` needs a working Faust toolchain (`faustcoder.compiler`).
- Neither script grants approval, closes a gate or reads holdout material.

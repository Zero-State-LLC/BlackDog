# Slice 2 leakage and split readiness

## Latest human source decision

Danny approved COPY/shared lineage for the exact pinned `filter.lib` / `filters.lib`
pair, candidate `u8ea99a0a7cb570b53333`, for leakage and family handling.
See the [approval bindings, receipt and remaining gates](qualification-sprint.md#superseding-filter-pair-copy-approval--2026-10-22).
The receipt is outside Git at
`/Users/appliedalchemylabs/Documents/Codex/blackdog-s2-backups/blackdog-filter-source-approval-20261022T201616Z/`.
Earlier pending wording for this pair is superseded; other source, dependency,
family/split, two-project FLOOR and independent private custody gates remain open.
Existing seven-file source/MIT and contract approvals remain valid within their
recorded scope. No production admission; PR #110 remains unmerged,
`TOKEN_FLOOR=40` provisional and T07 unfrozen.

## Status

Branch `feat/slice2-leakage-readiness` starts at merged main `7f16258`
(PR #97). Implementation and candidate diagnostics are reviewable; **the
Slice 2 readiness exit is blocked**. `TOKEN_FLOOR=40` remains provisional and
production T07 remains unfrozen. No candidate was promoted to training or eval.

Current human approval and seven-unit execution evidence is recorded in
[Seven-contract approval and scoped dependency checks](#seven-contract-approval-and-scoped-dependency-checks)
and [Seven-file NOT_COPY and MIT decision](#seven-file-not_copy-and-mit-decision).
Earlier corpus/handoff sections retain their historical status at delivery;
they do not override the later owner, seven-contract or seven-file source approvals.

## Shipping comparison changes

T06 clustering combines raw and canonical streams by OR. H2 maps identifiers,
numbers and complete string literals to ID/NUM/STR while retaining qualified
library members as atomic tokens. H3 applies NFKC and removes Cf/Cc for comparison
only. Whitespace controls retain a token boundary; comments are removed before
control removal so a line comment cannot swallow the following line. Stored
source, normalization digests and verified original-byte spans are unchanged.

Both streams use the existing integer thresholds and the selected measurement
floor. Whole-file and verified function-slice snapshot regressions cover renamed
identifiers and U+200B evasion. The low-level `is_near_duplicate` and `is_excerpt`
predicates remain raw-stream measurements; shipping `cluster_families` and
`memorization_hits` combine streams. The FLOOR measurement can explicitly select
40, 30 or 20 without mutating the provisional operating constant. Snapshot
metadata records the comparison version and rejects a measurement-only floor
from the split route.

Three-or-more contributor units whose union covers at least half a comparison
unit's shingles are joined to its family. This conservative H1 unit-level screen
is not proof of independently adjudicated split-file copies. Sub-15 canonical
exact matches remain fail-closed; no idiom exemptions were invented. Existing
upstream-copy rules still apply on the snapshot path. No sandbox limits, signal
tolerances, x86 goldens or rights pins were relaxed.

Comparison features are cached per source. The old identifier-only test controls
were consistently renamed copies under H2; structurally different controls now
exercise nonmatches without suppressing the raw-stream assertions.

## Corpus and development evidence

The offline audit verifies the production inventory/notice pins, candidate span
identities, original bytes and available Git blob hashes. It is a **diagnostic
screen**, not a production DedupManifest: the spans and dependency ledger remain
unapproved, some blobs are unavailable, and reject-class library blobs are
conservatively compared whole. A quarantine candidate is not a human COPY label.

- 1,240 candidate rows: 960 library function spans, 272 Faust rows, one Playground
  row and seven pd-faustgen rows.
- 319 verified blobs; 18 distinct available reject-class comparison blobs;
  191 pinned blobs still unavailable in the supplied locations.
- Floors 40, 30 and 20 each produce 1,123 quarantine candidates and 117 survivors.
  Floor-40 family assignments reproduce exactly with reversed input order.
- All 117 survivors belong to `grame-cncm/faustlibraries`. There are no surviving
  cleared hosts from two different repositories for the ratified FLOOR plants.
- 23 sub-15 canonical collision groups need idiom/copy adjudication. The natural
  review queue retains every flagged floor and leaves all labels UNADJUDICATED.
- The dependency ledger remains an overapproximation, including 362 units with
  external-member references. Zero cross-partition errors in an all-train
  proposal is not closure approval or independent split qualification.

Seven eval-eligible `CICM/pd-faustgen` files and two comparison-only files were
fetched at inventory pin `9e2aaeabe94a7fab6928711050535ac12a1a591a` and Git-blob
verified. Four files passed bounded default-control impulse references at both
sample rates: identity, fixed gain, passive gain product and stereo gain.
All eight corrupted-reference controls were rejected. All seven files compiled;
the dummy mixer clips and the gain/parameter defaults are silent, so their six
renders retain normal harness failures. No checks were disabled. All seven
remain in quarantine candidate families; **none is qualified development data**.

The new FLOOR evidence checker enforces eight fixed 100-item cells, 50 distinct
window identities per cell, two different cleared host repositories per window,
and the same gold denominators at every floor. Synthetic tests cover Wilson
failures and incomplete evidence. No real 800-item gold set was fabricated:
this run records empty, blocked cells because approved windows/hosts and human
natural-copy/FP labels are missing. It makes no floor-acceptance claim.

## Signed split mechanism and custody

`faustcoder.split` builds an explicitly unfrozen candidate and checks complete
assignments, project/family/provenance isolation, dependency links and eval rights.
It verifies detached OpenSSH Ed25519 signatures in namespace
`blackdog-t07-split-v1`, against an **out-of-band trusted public key** supplied by
the evaluator. A key embedded in a proposal cannot establish trust.

The separate `freeze_signed_split` API requires a valid custodian signature,
no unresolved assignment/readiness blockers, source states at DEDUPED, bound
independent review commitments, a newly authored holdout attestation and explicit
provisional-floor authorization with a leakage caveat and future novelty recheck.
It writes a signed SplitManifest, DatasetSnapshot and linked transition receipts.
`verify_frozen_snapshot` rechecks the stored signature and bindings before use.
Both freeze and verification enforce the recheck deadline against the evaluator
host clock, independently of caller-supplied receipt timestamps. Verification
also requires every source to have its exact linked freeze receipt; interrupted
writes cannot turn a partial snapshot into a usable frozen dataset. A retry
may complete missing receipts only when every already-frozen source has the
exact receipt for that candidate, snapshot and timestamp; unrelated freezes
and mismatched receipts are rejected before any writes.
The generic dataset transition API still refuses unsigned `split_frozen` calls.
P3 holdout exit remains forbidden under this provisional route.

Only disposable fixture stores exercise freezing in this slice. Tests cover
wrong keys, altered assignments/snapshots/signatures, stale algorithms,
measurement floors, forbidden eval rights, cross-split dependencies and
reproducible signed snapshot digests. No production signer is configured and no
production FROZEN receipt exists. Signed review attestations remain the trusted
human's responsibility; the library cannot prove independent authorship itself.

Recommended custody: a named human evaluator keeps newly authored private tasks
and the signing key in a private repository or encrypted directory inaccessible
to the Spark training account. Spark receives only approved signed exclusion
metadata, the public verification key and evaluation receipts. Agent-visible
source and disposable keys cannot supply independent holdout custody.

## Receipts and rerun

All evidence lives outside Git and `/tmp` at
`/home/delphi/blackdog-slice2-20261021/`:

- `corpus-audit-verified/`: bound inputs/code, family maps at all floors, natural
  review queue, sub-15 groups, dependency audit and blocked FLOOR readiness.
- `development-acquisition/`: pinned source/comparison blobs and retrieval hashes.
- `development-behavior/`: positive, failed and negative compiler/signal receipts.
- `tests-final-nosudo.log`: 586 passed, 2 skipped; the two sudo-bearing modules
  are excluded, so this is not a full-suite claim. The final signature-helper
  regression also passed all 11 tests (`final-signature-regression.log`).
- Post-review regressions: 58 passed, including stored snapshot tamper cases.
  Receipt: `/home/delphi/blackdog-slice2-review-20261021/regression.log`.
- `code-v1/`, `code-v2/`, retained diagnostic logs and stop receipt: earlier
  attempts. Only the initial Slice 2 diagnostic was stopped, with user permission.
- `REPORT.md`, preservation manifests and `SHA256SUMS`: final handoff/integrity.

Activate with `source ~/BlackDog/activate-local.sh`. The diagnostic commands are
`python -m diagnostics.slice2_readiness --help` and
`python -m diagnostics.development_smoke --help`. Always use a **new** output
directory; the drivers refuse existing evidence. Audit locations must come from
the pinned discovery manifests, never an unverified source directory.

## Subsequent reviewer handoff

The [qualification sprint handoff](qualification-sprint.md#slice-2-reviewer-handoff-and-verified-evidence)
records later evidence on merged main `2dd588a`: 174 hash-bound reviewer rows,
9,918 isolated-pair comparisons, verified Spark/off-host receipts and emails to
Prabu. These supplement the historical audit above and Batch 1's expanded
1,430-unit scope. The original return template remains UNREVIEWED; no gate below was closed.
Prabu subsequently delivered the Forge packet and corrected his identity to AI
agent. Earlier role acceptance and three spot-checks were not human review.
The [verified R2 packet](qualification-sprint.md#forge-first-pass-draft-and-verified-intake)
passes all 18 manifest checks, 174 source/dossier bindings and reproduction of all
18 matches with both supplied tokenizers; regenerated evidence is byte-identical.
Six matches are exactly 40 under tokenizer A; one is 43. These are reproduction
results, not human COPY adjudication or final floor acceptance.

Draft counts remain 18 proposed REJECT, 156 BLOCKED and zero retained; 166 notice
PROPOSED_APPROVE values and eight unresolved after both linearalgebra downgrades.
All dependencies and seven gates remain pending. Human review must resolve
boundary/scaffolding cases, JOS attribution,
routes helper scope within the cited MIT range and the linearalgebra notice
conflict, then complete pinned closures, author/reviewer bindings and private custody.

R2 packet: `/home/delphi/blackdog-s2-forge-draft-return-R2-20261022T035347Z/`.
Verification: `/home/delphi/blackdog-s2-forge-r2-verified-20261022T0356Z/`, with a
verified off-host `.tar.gz` archive and checksum under the local backup root
specified in the sprint runbook (23 archived payloads). R1 and R2 originals
remain intact; both manifests passed after the fresh R2 replay. R2 explicitly
says pending human adjudication and leaves the independent reviewer blank.
Owner-authorized drafting has now produced the 174 manifests described below;
none is a complete or approved closure. Preserve the full
1,430-unit pool, 23 short-collision groups and 19 collective-support sets.
Kickoff remains unconfirmed, `TOKEN_FLOOR=40` provisional and T07 unfrozen.

## Dependency-closure draft handoff

The [174 pinned drafts](qualification-sprint.md#pinned-dependency-closure-drafts-human-review-pending)
cover 46 function slices and 128 whole-file units in 21 groups, with source,
Git-blob/commit and R2 dossier bindings. All 174 manifest checks passed, along
with five tampering controls and ten scanner/path checks. The shared graph has
528 hash-verified file nodes and conservative per-unit envelopes of 1–47 files.
No missing/ambiguous literal import file candidates remain; semantic closure,
actual use and rights are not established. No compiler/signal/full-suite run
was performed for these drafts.

Nineteen qualified-reference occurrences across six units remain unresolved
(`ma.EPSILON` and `bpf.start`/`point`/`end`); six units have selected foreign/resource
references. All drafts retain incomplete/unapproved status and pending human
review of scope, shadowing, overloads, import ordering, foreign resources,
notices and independent contracts. Review the 21-group queue, refine complete
closures, then execute approved sandbox and semantic/negative-control plans.

Spark receipts: `/home/delphi/blackdog-r2-closures-20261022T0424Z-v3/`.
Off-host archive: `/Users/appliedalchemylabs/Documents/Codex/blackdog-s2-backups/blackdog-r2-closures-20261022T0424Z-v3.tar.gz`
with SHA-256 sidecar; all 940 archived payloads passed. The sprint runbook records
the digest, readable report and preservation checks. R1/R2 inputs and environments
remain preserved. All 174 dependency decisions and seven gates remain pending;
`TOKEN_FLOOR=40` remains provisional and T07 remains unfrozen.

## Seven-contract approval and scoped dependency checks

The [latest sprint evidence](qualification-sprint.md#seven-contract-human-approval-and-dependency-validation)
supersedes historical pending-approval statements for seven CICM/pd-faustgen
contracts. Danny Meyer approved all seven, the shared plan and the `.default.dsp`
import correction, attesting no authorship/material coauthorship or conflict.
Codex authored the drafts. Both `.default.dsp` and `gain.dsp` declare
`import("stdfaust.lib")`; the corrected receipt preserves this dependency.
The earlier owner approval of R2/closure packets accepts their blocked dispositions,
not production admission. Original packet files remain unchanged.

On `spark-af42` at `84e0192`, all seven originals compiled on WASM/native paths;
both import-free variants compiled on both paths. Total: 18 successful compiler
cases, 11 expected local-binding-removal rejections and two expected missing-import
rejections. Thirty paired execution cases at 44.1/48 kHz produced byte-identical
import-present/import-free samples and passed a separate analytical replay.
Each variant retained 144,000 float32 samples per case. Tests covered impulse,
alternating and multitone probes, and gain values 0/0.25/0.5/1. Later bounded
behavior/default and compiled-target substitution checks passed;
see the source-approval section below for scope and receipts.
No limits, tolerances or sandbox isolation were relaxed.

Approval: `/home/delphi/blackdog-seven-contract-approval-20261022T053119Z/`.
Results: `/home/delphi/blackdog-seven-dependencies-20261022T053421Z/`.
The matching `.tar.gz` and SHA-256 sidecar under the local `blackdog-s2-backups/`
root passed archive verification and all 498 payload checks. The sprint runbook
records the exact archive digest, corrected contracts and preservation details.
No evidence artifacts enter Git.

Danny is named human custodian and independent private-task reviewer. The private
author arrangement, actual private storage and human-only access remain pending;
iCloud is coordination only. The owner affirms agent/training exclusion. No
private tasks or keys were created. Beyond the seven-file source approval below,
unresolved notice/leakage scope and the remaining 167 units’ closure/contract
evidence, two-project FLOOR inputs and complete
qualification remain open. TOKEN_FLOOR=40 stays provisional; T07 stays unfrozen.

## Seven-file NOT_COPY and MIT decision

Danny Meyer approved NOT_COPY against the reviewed comparison evidence and
repository-level MIT coverage for all seven exact R3b source blobs on
2026-10-22. See [scope, receipts and remaining gates](qualification-sprint.md#seven-file-source-and-mit-approval-2026-10-22).
The approval binds source/dossier hashes and Git blobs at pd-faustgen commit
`9e2aaeabe94a7fab6928711050535ac12a1a591a`; preserve the full Pierre Guillot MIT
notice. It supersedes pending source/notice decisions for these seven only.
Original packets and historical counts remain unchanged. Imported libraries and
third-party scope are excluded; family links and dependency/split gates remain.

Approval: `/home/delphi/blackdog-seven-source-approval-20261022T185548Z/`.
R3b: `/home/delphi/blackdog-s2-r3b-notice-spans-20261022T173051Z/`.
Replay: `/home/delphi/blackdog-r3b-intake-20261022T1733Z/`.
Matching off-host directories under
`/Users/appliedalchemylabs/Documents/Codex/blackdog-s2-backups/` are checksum-verified.
All 31 R3b payloads, seven bindings, 61 replayed pairs and 332 span rows passed.
No production admission; TOKEN_FLOOR=40 provisional and T07 unfrozen.

## Imported-notice handling decision

Danny Meyer approved scoped notice handling for exact `.default.dsp` and
`gain.dsp`, preserving their MIT notice separately from pinned `stdfaust.lib`'s
GRAME LGPL-2.1-or-later notice and complete compiled-code exception.
[Bindings, evidence and remaining gates](qualification-sprint.md#imported-notice-handling-approval--2026-10-22).
Receipt: `/Users/appliedalchemylabs/Documents/Codex/blackdog-s2-backups/blackdog-imported-notice-approval-20261022T221607Z/`;
six payloads checksum-verified. Full LGPL license text must accompany any
redistributed library-source bundle; it is not included in this receipt.

This closes the scoped notice-handling decision only. The 44-file conservative
envelope is not collectively cleared; native filesystem tracing, where required,
is still absent. Human closure/host and family/split review, broader third-party
scope, two-project hosts and fixed-gold FLOOR measurements, development/custody
and integration gates remain open. No host or production admission.
PR #110 stays unmerged; `TOKEN_FLOOR=40` provisional; T07 unfrozen.

## Remaining exit gates

1. Independently approve a useful source/task/dependency subset; adjudicate the
   large conservative quarantine set instead of counting it as proven copying.
2. Qualify two-project cleared hosts and real rejected windows, then perform the
   ratified FLOOR plants, natural-copy and false-positive adjudication. Preserve
   fixed ground truth; obtain an explicit floor decision or provisional route.
3. Qualify project-disjoint development tasks with semantic references and no
   unresolved family conflicts. The recovered files are candidates only.
4. Danny Meyer is named custodian and independent private-task reviewer; confirm
   the independent author arrangement, actual private storage and human-only
   access. iCloud is coordination only. Bind exclusion metadata and completed
   independent reviews before treating private tasks as qualified holdout data.
5. Review the signing implementation and configure trusted public verification
   only after these gates close. Production T07 must remain unfrozen meanwhile.

No sudo, environment installation, model download, unrelated workload stop,
commit or push was used. Prior environments, models, checkpoints and receipts
are preserved. The source downloads above are not model downloads or new rights
grants.

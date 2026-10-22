# Slice 2 leakage and split readiness

## Status

Branch `feat/slice2-leakage-readiness` starts at merged main `7f16258`
(PR #97). Implementation and candidate diagnostics are reviewable; **the
Slice 2 readiness exit is blocked**. `TOKEN_FLOOR=40` remains provisional and
production T07 remains unfrozen. No candidate was promoted to training or eval.

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
The [verified packet](qualification-sprint.md#forge-first-pass-draft-and-verified-intake)
passes all 18 manifest checks, 174 source/dossier bindings and reproduction of all
18 matches with both supplied tokenizers; regenerated evidence is byte-identical.
Six matches are exactly 40 under tokenizer A; one is 43. These are reproduction
results, not human COPY adjudication or final floor acceptance.

Draft counts remain 18 proposed REJECT, 156 BLOCKED and zero retained; 168 notice
APPROVE proposals and six unresolved. All dependencies and seven gates remain
pending. Human review must resolve boundary/scaffolding cases, JOS attribution,
routes section boundaries and the linearalgebra notice conflict, then complete
pinned closures, author/reviewer bindings and private custody.

Packet: `/home/delphi/blackdog-s2-forge-draft-return-20261022T015921Z/`.
Verification: `/home/delphi/blackdog-s2-forge-verified-20261022T0213Z/`, with a
verified off-host archive under the matching local backup directory documented
in the sprint runbook (22 archived payloads). Preserve the full 1,430-unit pool,
23 short-collision groups and 19 collective-support sets. Kickoff remains
unconfirmed, `TOKEN_FLOOR=40` provisional and T07 unfrozen.

## Remaining exit gates

1. Independently approve a useful source/task/dependency subset; adjudicate the
   large conservative quarantine set instead of counting it as proven copying.
2. Qualify two-project cleared hosts and real rejected windows, then perform the
   ratified FLOOR plants, natural-copy and false-positive adjudication. Preserve
   fixed ground truth; obtain an explicit floor decision or provisional route.
3. Qualify project-disjoint development tasks with semantic references and no
   unresolved family conflicts. The recovered files are candidates only.
4. Confirm human evaluator/custodian and independent reviewer assignments after
   the AI-only correction. Document separate human-controlled custody and a
   private review channel before creating independent tasks; bind exclusion
   metadata and completed independent reviews. Agent role assignments cannot
   close this gate.
5. Review the signing implementation and configure trusted public verification
   only after these gates close. Production T07 must remain unfrozen meanwhile.

No sudo, environment installation, model download, unrelated workload stop,
commit or push was used. Prior environments, models, checkpoints and receipts
are preserved. The source downloads above are not model downloads or new rights
grants.

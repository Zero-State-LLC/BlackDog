# BlackDog implementation backlog

## Current milestone: qualification sprint

[Ten-working-day sprint](docs/runbooks/qualification-sprint.md): one consolidated
delivery covering the full 110-packet queue, deep review of the 174-unit scope
(172 initial candidates plus two helpers), semantic validation, two-project
FLOOR evidence, development qualification and custody preparation. Day 3 is the host/rights go-or-block
checkpoint; days 9–10 deliver the reviewed dossier. Missing human approvals or
hosts block milestone completion. No production freeze or training is scheduled.
Hosted [project 29](https://github.com/orgs/Zero-State-LLC/projects/29) mirrors
S1–S7. Its plan-time S1 Ready status is superseded here by verified technical
preparation with human confirmations pending; S1 is not Done. Dependent packages
remain blocked on their stated inputs.
PR #99 is Done. T06 implementation remains Done; qualification is tracked
separately, and T07/T10 remain Backlog.

| Sprint card | Status | Exit |
| --- | --- | --- |
| Batch 1 evidence and hash-format review | Done: #99, `ce8087a` | Eight CI checks; 771 tests passed |
| S1 scope and owner assignment | Technical preparation complete; confirmations pending | 1,430 units / 110 packets / 510 blobs verified; packet/bindings verified; Prabu is an AI agent; human assignments, kickoff, coverage and custody pending |
| S2 source/leakage and S3 closure/behavior | Forge R2 and 174 closure drafts verified structurally; 18/18 matches reproduced; original 18 proposed REJECT / 156 BLOCKED / 0 retained; owner packet approvals, seven contract/source approvals and exact filter-pair COPY approval recorded; no production admission | Hash-bound per-unit decisions, approved closures/contracts and reproducible positive/negative receipts |
| S4 two-project hosts and S5 FLOOR | Blocked on approved inputs | Ratified gold/label protocol and complete measurement result |
| S6 development/custody | Danny named human custodian/reviewer; independent private author and actual isolated storage pending | Document private custody/review channel; disjoint reviewed tasks and custody commitments still required |
| S7 qualification dossier | Planned after S2–S6 | One reviewed delivery; explicit pass or blocked milestone decision |

## Filter pair human approval recorded

**Done: decision receipt. Qualification remains blocked.** Danny approved
COPY/shared lineage for the exact pinned `filter.lib` / `filters.lib` pair
(candidate `u8ea99a0a7cb570b53333`) for leakage and family handling.
[Bindings, evidence and open gates](docs/runbooks/qualification-sprint.md#superseding-filter-pair-copy-approval--2026-10-22).
Receipt: `/Users/appliedalchemylabs/Documents/Codex/blackdog-s2-backups/blackdog-filter-source-approval-20261022T201616Z/`;
five files checksum verified, artifacts outside Git. Original packets unchanged.

Next: bind the decision into family/split review; resolve remaining source/notice
and dependency scope; complete independent behavior qualification, full-pool and
two-project FLOOR evidence, and independent private author/storage/access/review
confirmation. Existing approvals are preserved; this decision grants no
production admission. PR #110 stays unmerged; idiom filtering stays default-off,
`TOKEN_FLOOR=40` stays provisional and T07 stays unfrozen.

## S1 scope verification and reviewer handoff

[S1 evidence and pending confirmations](docs/runbooks/qualification-sprint.md#s1-verified-scope-and-assignments)
come from execution at main `c7977ce`. Deep review covers 174 units across 21 packets,
including two additional helper candidates; 1,256 units remain explicitly
deferred. All 174 retain dependency review gates and 172 remain quarantine
candidates. Every one of the 1,430 units appears in exactly one assigned packet.

Historical assignments name Prabu for review and custody, but he now explicitly
identifies as an AI agent. These assignments and his conditional acceptance do
not establish human review capacity or independent custody. Packet access and
hashes are verified. Name human adjudicators and an independent contract reviewer,
confirm kickoff/coverage, and document private custody before S1 can close.

Receipts: `/home/delphi/blackdog-qualification-sprint-20261021T194809Z/`;
start with `REPORT.md` and `REVIEW-INDEX.md`. The local backup is under
`/Users/appliedalchemylabs/Documents/Codex/blackdog-s1-backups/` with the same
receipt directory name. All 1,680 backup file checks passed; 106,957 pre-existing
Spark entries remained unchanged and 1,659 replay payload files reproduced
exactly. No artifacts enter Git. `TOKEN_FLOOR=40` stays provisional and T07
stays unfrozen; no production qualification gate closed during S1 preparation.

## Slice 2 reviewer handoff: pending independent decisions

[Handoff, verification and gate owners](docs/runbooks/qualification-sprint.md#slice-2-reviewer-handoff-and-verified-evidence)
record Prabu’s conditional acceptance on 2026-10-21 PT. The original return template
remains UNREVIEWED. His initial Spark access failure led to owner-authorized email
delivery; he now reports working access and completed packet/S1 hash checks.
The later Forge draft is not an adjudicated return; agreed day 1 remains pending.
A 15-minute reply monitor is configured, but does not establish approval.

The [verified Forge R2 packet](docs/runbooks/qualification-sprint.md#forge-first-pass-draft-and-verified-intake)
passes all 18 file checksums and 174 source/dossier bindings. All 18 matches
reproduce with both supplied tokenizers and byte-identical evidence. Draft counts
remain 18 COPY/REJECT, 156 BLOCKED, zero retained; 166 PROPOSED_APPROVE notices and
eight unresolved (both linearalgebra notice proposals downgraded). All 174
dependencies and all seven gates remain unresolved/pending.
**Prabu is an AI agent: the three earlier spot-checks were not human checks.**
No human adjudication is established. Six matches are exactly 40 under tokenizer
A; one is 43. Boundary and shared UI/scaffolding cases still need human decisions.

Delivered R2: `/home/delphi/blackdog-s2-forge-draft-return-R2-20261022T035347Z/`.
Verification: `/home/delphi/blackdog-s2-forge-r2-verified-20261022T0356Z/`;
off-host archive is `blackdog-s2-forge-r2-verified-20261022T0356Z.tar.gz` under
the local backup root below, with an adjacent SHA-256 sidecar. All 23 archived
payloads passed. R1 and R2 originals passed post-replay checks and remain intact.
R2 says pending human adjudication; independent contract reviewer stays blank.
No raw artifacts enter Git. See the runbook for hashes and limitations.

The [174 pinned dependency-closure drafts](docs/runbooks/qualification-sprint.md#pinned-dependency-closure-drafts-human-review-pending)
cover 46 function slices and 128 whole-file units across 21 groups. All 174
manifest checks, five tampering controls and ten scanner/path checks passed;
all 940 off-host payload checksums passed. These are structural checks, not
compiler/signal results or human approvals. The 528-node shared file graph
provides conservative envelopes, not complete executable closures. Nineteen
qualified-reference occurrences across six units remain unresolved; six units
have selected foreign/resource references. Every draft still needs semantic,
notice and independent contract review; no unit is admitted.

Final Spark receipts: `/home/delphi/blackdog-r2-closures-20261022T0424Z-v3/`;
start with `REVIEW-INDEX.md` and `human-review-queue.csv`. Off-host archive:
`/Users/appliedalchemylabs/Documents/Codex/blackdog-s2-backups/blackdog-r2-closures-20261022T0424Z-v3.tar.gz`
with checksum sidecar and a standalone `-REPORT.md`. The runbook records the
archive digest, validation scope and remaining gates. Environments and prior
receipts remain preserved; all drafts stay pending human approval.

The supplement on `2dd588a` completed 9,918 isolated-pair comparisons and 12
uncached parity checks. At floor 40: 103 direct-trigger units, 69
indirect-family-only units and two unflagged candidates. These are diagnostic
review routes, not COPY/NOT_COPY labels or quarantine clearance. The complete
1,430-unit natural-copy pool remains required.

Spark receipts: `/home/delphi/blackdog-s2-direct-review-20261021/` and
`/home/delphi/blackdog-s2-review-return-20261021T215913Z/`. Local archives:
`/Users/appliedalchemylabs/Documents/Codex/blackdog-s2-backups/`. Both archive
digests and all 182 + 4 payload checksums passed. This is not a new full-suite run.
No artifacts or private correspondence enter Git.

The emailed `blackdog-s2-review-bundle-20261021T2240Z.tar.xz` contains 2,391
verified payloads and 510 original Git-blob-verified sources. Gmail confirms the
4,741,632-byte attachment was sent. Spark directory/archive: `/home/delphi/` with
the bundle name; local archive: the backup root above. See the runbook for exact
checksums, path mapping, reply/assignment/delivery receipts and limitations. No
private holdout content or keys were included. The earlier Prabu-author/Danny-reviewer
assignment does not establish independent custody after the AI-only correction.
Private task creation waits for a documented human-controlled boundary.

Next: agree human assignments and kickoff/coverage, obtain human identity/hash-bound
source/leakage decisions (including boundary/scaffolding cases and notice conflicts),
review/refine the 174 closure drafts and bind independent contracts, qualify two-project FLOOR hosts and
fixed gold/labels, and establish disjoint development tasks plus separate holdout
custody. S1 remains open for confirmations; S2–S6 prerequisites and S7 completion
remain pending. `TOKEN_FLOOR=40` stays provisional and T07 stays unfrozen.

## Slice 2 Batch 1 merged result

[Batch 1 evidence completion](docs/runbooks/slice2-batch1.md) recovered all 191
missing pinned blobs and assembled 110 review packets for 1,430 candidates.
All 1,240 original candidates remain covered. The expanded audit leaves 1,313
quarantine candidates and 117 unflagged units in one project. The proposed
172-unit first wave prioritizes prior bounded contracts and independent-project
eval candidates, but 170 still require quarantine adjudication. Rights, closure
and behavioral approvals remain separate human gates. `TOKEN_FLOOR=40` remains
provisional and T07 remains unfrozen. Receipts are outside Git at
`/home/delphi/blackdog-batch1-20261021/`; start with `REVIEW-INDEX.md`.

## Slice 2 candidate result

Merged Slice 1 (#97, `7f16258`) is the base. The [Slice 2 readiness runbook](docs/runbooks/slice2-readiness.md)
records H2/H3 comparison streams, explicit floor measurement, conservative union
screening, signed-split guard tests and a 1,240-row corpus audit. All three floors
flag 1,123 quarantine candidates; the 117 survivors occupy one project. Seven
pinned independent-project source candidates were recovered, but all retain
family conflicts. Eight bounded positive renders and eight corrupted-reference
controls passed; six renders correctly retain silence/clipping failures.

**Exit blocked:** real two-project FLOOR hosts/gold windows, human natural/FP
adjudication, independently approved closures/development data and sealed holdout
custody are missing. The signed-freeze API runs only in disposable regression
stores. Production T07 remains unfrozen; `TOKEN_FLOOR=40` remains provisional.
Receipts: `/home/delphi/blackdog-slice2-20261021/`. No setup artifacts enter Git.

Formerly FaustCoder; renamed 2026-10-17 PT.

Status as of 2026-10-21 PT, main `671ce35` (spec 0.3.11). T04's corrected ARM/x86 DSP-bank validation completed in [#79](https://github.com/Zero-State-LLC/BlackDog/pull/79): all 40 renders were finite and byte-identical, as were the five compiled WASM binaries. Full suites: ARM 635 passed, 2 skipped; x86 637 passed. All nine PR checks passed, and merged-main activation, smoke test and golden comparison passed on spark-af42. See [Spark setup, evidence and next steps](docs/runbooks/spark-local-setup.md).

T09 fingerprint evidence is COMPLETE for the repaired candidate on spark-af42 at `1ae20ba` (2026-10-21 00:29:27 UTC / 2026-10-20 PT): exit 0, `env_verified`, both artifact envelopes verified and all 20 off-host file checksums passed. See [candidate receipt IDs and locations](docs/runbooks/spark-local-setup.md#repaired-candidate-t09-fingerprint). The earlier r9venv fingerprint on `0cd3382` remains preserved. This is separate from T04; `stack_pin_allowed=false`, the existing Axolotl/torch conflict remains, and that fingerprint provides no training-throughput or second-Spark receipt. A2-PATH and EVAL-SO remain CODE DONE, LIVE WIRING PENDING; their grader implementation is not proof of production reward-path integration. T01 still waits on proposed ADR-0001. T06 H2, H3 and FLOOR, and D3-H1-N9 through N12 remain separate follow-ups. Existing dependency arrows remain promotion gates; this setup does not authorize training or promotion.

The separate T10 repair candidate is DEPENDENCY/CUDA VALIDATED; TRAINING GATES PENDING. The audited cuSPARSELt 0.8.1 wheel retains vendor payload bytes and dependency pins, uses the audit-supported `manylinux_2_27_aarch64` tag, and passes pip check plus 12/12 sparse comparisons and repeated dense CUDA checks. See [repair, receipt locations and remaining gates](docs/runbooks/spark-local-setup.md#validated-cusparselt-repair-candidate). All 52,333 baseline files/symlinks were preserved and 28 off-host evidence checksums verified. The original T10 venv remains unchanged and blocked. The fresh candidate T09 fingerprint also passes; 89,975 baseline files/symlinks remained unchanged during that run. The [offline synthetic training/checkpoint diagnostic](docs/runbooks/spark-local-setup.md#offline-training-and-checkpoint-diagnostic) now passes: five LoRA steps, exact checkpoint/restart comparisons, 90,014 baseline files/symlinks unchanged and 47 verified backup checksums. This is not an approved-model smoke, stack pin or training-readiness claim.

The [Qwen T10 smoke and merged library-rendering fix](docs/runbooks/spark-local-setup.md#qwen-t10-smoke-and-merged-library-rendering) are COMPLETE: 28 train / 7 diagnostic examples after admission, 20 LoRA steps and exact fresh-process checkpoint/resume checks. PR #86 merged as `e3c9542` with 642 tests passing; merged-main signal verification passed 46 tests. Formal T07/G10, stack-pin review and production training gates remain OPEN. Receipts, models and checkpoints stay outside Git.

The [T07 candidate audit](docs/runbooks/t07-candidate-audit.md) is COMPLETE on `a414dfd`: 2,259 inventory rows audited, 1,993 matching local blob rows and 266 not found within scope. The unsigned proposal reserves 240 whole-file rows / 210 families from Faust for training qualification; development and sealed holdout remain unassigned. T07 is NOT FROZEN. All 90,351 baseline files/symlinks were preserved and 14 backup checksums passed.

Verified function-span extraction is merged in [#89](https://github.com/Zero-State-LLC/BlackDog/pull/89) (`adee7ae`): 668 full-CI tests passed, review found no issues, and merged-main Spark verification passed 143 regressions. All 92,319 existing files/symlinks were unchanged. See [receipts and remaining T06/T07 gates](docs/runbooks/function-spans.md#merged-main-verification-and-receipts). This verifies extraction infrastructure; no production span manifest or new rights clearance is approved. `TOKEN_FLOOR=40` stays provisional and T07 stays unfrozen.

The [partial span candidate](docs/runbooks/function-spans.md#partial-production-candidate-unapproved) on `84c51a3` initially proposed 7 of 965 admitted function spans; 958 were missing at that stage. All 27 source blobs verified, and subset checks pass, but full-inventory validation correctly refuses incomplete coverage. All seven are train-only and unapproved. Preservation: 93,754 files/symlinks unchanged; 13 receipt checksums passed. Independent review, dependency/task qualification and H2/H3/FLOOR remain open; T07 is unfrozen.

The [seven-span validation](docs/runbooks/function-spans.md#seven-span-compiler-and-signal-validation) on `fc1990e` passed 28 sandboxed compiler/signal runs and five negative controls. Dependencies were explicit; all 94,487 baseline files/symlinks remained unchanged and 146 receipt checksum entries passed. This is bounded diagnostic evidence, not independent production approval: at that stage 958 spans remained missing, the candidate remains unapproved, and H2/H3/FLOOR and T07 gates stay open.

The [expanded 13-span candidate](docs/runbooks/function-spans.md#expanded-13-span-candidate-and-batch-two-validation) on `84dd841` adds six interleave/comparator clauses and helpers. All 26 new compiler/signal runs and four negative controls passed; original seven rows and prior receipts are unchanged. All 95,355 baseline files/symlinks were preserved and 139 new receipt checksums verified. Receipts: `/home/delphi/blackdog-span-batch2-20261021/` (outside Git and `/tmp`). At that stage all 13 spans were train-only and unapproved; 952 spans were missing, and full-inventory validation refused incomplete coverage. Independent review, broader task/leakage qualification and H2/H3/FLOOR remain open; `TOKEN_FLOOR=40` stays provisional and T07 stays unfrozen.

The [93-group static review](docs/runbooks/span-corpus-review.md#93-group-review-and-inventory-corrections) is COMPLETE on `0542321`: 960 unapproved proposals, five inventory correction dispositions and 1,318 proposed dependency links. All 960 span hashes verified; no dependency closure was certified and no behavioral test was run in this review. Four commented examples and the ambiguous bare `play` identity have receipt-only inventory/notice corrections; adoption and coordinated T05 repinning subsequently merged in #97; independent qualification remains pending. Review waves: 31 deterministic, 34 scoped/stateful and 28 specialized groups. Receipts: `/home/delphi/blackdog-span-group-review-20261021/`; 100,876 baseline files/symlinks unchanged and 46 new receipt hashes verified. `TOKEN_FLOOR=40` stays provisional; T07 is unfrozen.

Initial Slice 1 diagnostics completed on `feat/slice1-corpus-qualification`: five inventory/notice corrections and admission repinning, 960 proposals across 93 groups, 117 domain contracts, 122/122 initial compiler/signal runs passed, and 567 regressions passed (2 skipped; sudo-bearing modules excluded). The current ledger records 44 bounded-contract passes and 916 specific blocked dispositions; the production-readiness exit remains blocked. See [Slice 1 qualification](docs/runbooks/slice1-qualification.md). PR #97 corrects cross-contract dependency leakage by batching only identical ordered closures; its fresh 210-run validation supersedes the initial run for isolated-closure evidence. Merged in #97 as `7f16258`; production approval, T06 H2/H3/FLOOR and T07 freeze remain open.

## Done

These merges are on main. The commit is the merge commit.

| Item | PR | Commit | What landed |
|---|---|---|---|
| Batch 1 evidence assembly | [#99](https://github.com/Zero-State-LLC/BlackDog/pull/99) | `ce8087a` | 191 blobs recovered; 110 packets / 1,430 candidates; SHA-1/SHA-256 verification; 771 full-CI tests; no qualification approval |
| Slice 2 leakage and split mechanisms | [#98](https://github.com/Zero-State-LLC/BlackDog/pull/98) | `585b188` | H2/H3 comparison streams and signed-split guards; production gates remain open |
| Slice 1 corpus qualification | [#97](https://github.com/Zero-State-LLC/BlackDog/pull/97) | `7f16258` | Five inventory corrections, repinning and isolated closure validation; 44 bounded passes / 916 blocked |
| Corpus-wide span proposals and resumable queue | [#95](https://github.com/Zero-State-LLC/BlackDog/pull/95) | `0542321` | Atomic checkpoints and integrity-bound reuse; 722 full-CI tests passed. Merged-main Spark: 124 tests, 79/79 pilot checks and 41-case reuse; new proposals remain unqualified |
| Verified function-span extraction | [#89](https://github.com/Zero-State-LLC/BlackDog/pull/89) | `adee7ae` | Independently digest-pinned reviewed byte ranges; fail-closed extraction and provenance; rights quarantine preserved; real-corpus qualification remains open |
| Pinned library rendering | [#86](https://github.com/Zero-State-LLC/BlackDog/pull/86) | `e3c9542` | Shared pinned staging, mounted-tree hash verification and read-only library access; sandbox regressions pass |
| T04 finite ARM/x86 DSP-bank validation | [#79](https://github.com/Zero-State-LLC/BlackDog/pull/79) | `bb367c9` | Correct biquad feedback sign/delay, refuse nonfinite bank output, add recurrence/finite regressions, and regenerate verified goldens without widening tolerances; 40/40 exact matches |
| D3-H2-C human triage signatures | [#71](https://github.com/Zero-State-LLC/BlackDog/pull/71) | `cf319f3` | Spec 0.3.11 signature verification and dedicated grader check; follow-ups #68 and #72 remain open |
| Independent contract validation | [#74](https://github.com/Zero-State-LLC/BlackDog/pull/74) | `04146e3` | JSON Schema contract validation in CI |
| ARM64 sandbox capability dropping | [#77](https://github.com/Zero-State-LLC/BlackDog/pull/77) | `19b9184` | Portable libc capset, configured namespace execution, capability and no-new-privileges regression coverage; all eight CI checks passed |
| D3-H1 HMAC-signed reward records | [#55](https://github.com/Zero-State-LLC/BlackDog/pull/55) | `0d68d01` | Signed reward rows and group-aware `rl_batch_from_records`. Blocks T10 |
| D3-H2 sampled rerun audit | [#57](https://github.com/Zero-State-LLC/BlackDog/pull/57) | `63aac31` | Spec §26 0.3.9 audit before P3 |
| D3-H2 halt marker | [#59](https://github.com/Zero-State-LLC/BlackDog/pull/59) | `ac0326f` | Closes [#58](https://github.com/Zero-State-LLC/BlackDog/issues/58). A halt still writes a MAC'd marker when every disagreeing group was already `used` |
| D3-H2 anchor re-verify | [#60](https://github.com/Zero-State-LLC/BlackDog/pull/60) | `24170c3` | Re-check the anchor MAC before rebinding or advancing it |
| D3-H2 claim pin | [#61](https://github.com/Zero-State-LLC/BlackDog/pull/61) | `2f1caba` | Anchor refresh covers only the claim line just written |
| D3-H2 triage identity | [#63](https://github.com/Zero-State-LLC/BlackDog/pull/63) | `75d2bed` | Refuse `fc-grader` and root triage. `rl_batch` is private `_rl_batch` |
| Spec §26 0.3.10 option C | [#66](https://github.com/Zero-State-LLC/BlackDog/pull/66) | `fab50c2` | Human triage credential text, plus the `fc-grader` P3 precondition. Signature verification is not in this commit |
| D3-H2 name and time bounds | [#67](https://github.com/Zero-State-LLC/BlackDog/pull/67) | `665d73b` | Closes [#65](https://github.com/Zero-State-LLC/BlackDog/issues/65). NFKC and casefold on reserved names, `halted_at` bounds, refused triages, and an unusable stamp reported instead of `OverflowError` |

## Next / To do

| ID | Issues | Task |
|---|---|---|
| T05 inventory correction | Five soundfiles identities | Corrections and repinning merged in #97. Verify these pins in sprint S1; independent source/dependency approval remains required, with no new rights grant |
| T06 qualification | H2 / H3 / FLOOR | [Sprint S2–S5](docs/runbooks/qualification-sprint.md) reviews the 172-unit cohort plus helpers within the complete 1,430-unit ledger. H2/H3 implementation is merged in #98; independent rights, closure/behavior qualification and real §25 FLOOR evidence remain open. Keep tolerances and sandbox checks; TOKEN_FLOOR=40 stays provisional |
| T07 qualification | R-003 / T07 | [Audit and freeze blockers](docs/runbooks/t07-candidate-audit.md#freeze-blockers-and-acceptance): qualify function units and T06 H2/H3/FLOOR, use the completed Batch 1 source scope and resolve independent development coverage, validate DSP tasks, arrange newly authored sealed holdout custody, then separately authorize and verify a production freeze using the mechanism merged in #98. No split is frozen |
| T09 / T10 environment follow-up | [#12](https://github.com/Zero-State-LLC/BlackDog/issues/12) | spark-af42 fingerprint complete. The separate repaired direct HF candidate passes dependency and dense/sparse CUDA validation. Candidate fingerprint is complete with `stack_pin_allowed=false`. Qwen actual-model training/checkpoint smoke passed. Recheck workload clearance; complete formal data/split/baseline qualification, repeated representative throughput/memory measurements and stack-pin review. Repeat fingerprinting if the environment changes or a second Spark will train; preserve DSP setup and receipts |
| D3-H2-C follow-ups | [#68](https://github.com/Zero-State-LLC/BlackDog/issues/68), [#72](https://github.com/Zero-State-LLC/BlackDog/issues/72) | Implementation merged in #71; reconcile remaining review items, including OpenSSH feature detection and key-path guard coverage. Do not close issues from merge status alone |
| D3-H2 fail-closed | [#62](https://github.com/Zero-State-LLC/BlackDog/issues/62) | Fail-closed follow-ups from the #61 review (I1–I4). A refused refresh leaves the injected line. An unreadable report is skipped by the no-anchor check. That check reads every sibling file. An unMAC'd or foreign-log report must not block a first claim |
| Triage fail-closed | [#69](https://github.com/Zero-State-LLC/BlackDog/issues/69) | Fail-closed nits from the #67 review. A clock moving backwards can refuse an already-accepted triage on read. The confusable skeleton misses small capitals and combining marks. The r2 note asks for a direct test that `None` means refused, and records that two r1 mutants (NFKC, missing halt) still survive |

Issue #68: the D3-H2-C change reads the drop-file owner with `fstat` on an `O_NOFOLLOW` fd (regular files only), pins OpenSSH >= 8.7 in CI and at startup, and sets the allowed-signers mode to `0644`. Grader-written `appended_at` plus a revoked reviewer key can backdate a triage; that limit is under "not covered" in §26. A ctime bound would not close it, because the same grader writes the MAC and can set `appended_at` to a ctime from when the key was still valid. Item 6, a machine check that Danny's key is hardware-backed, is dropped by the 5:45 PM PT ruling and applied in spec 0.3.11. Item 3, the live `rl_batch` name, was swept by #67 in the signal runbook, data-model, tasks.md and this board. spec.md:728 was left as it stood. Changelog lines written before that rename still say `rl_batch`.

## Immediate execution order

1. Close S1’s pending human confirmations using the verified scope and confirmed human
   assignments, then execute [S2–S7 as one delivery](docs/runbooks/qualification-sprint.md).
   Account for all 1,430 identities; review the 174-unit scope and any additional
   required helpers, with the day-3 two-project checkpoint unchanged.
2. Complete the human review and measurement gates before a separate T07 freeze
   decision. Keep `TOKEN_FLOOR=40` provisional and production T07 unfrozen.
3. After an authorized freeze, measure T08 baselines and close the remaining T10
   live-wiring, stack-pin and representative throughput gates. Existing T09 and
   Qwen smoke receipts do not substitute for these gates.
4. Preserve environments, models, checkpoints and receipts. Do not implicitly
   authorize sudo, workload stops, downloads, signing or training through a plan.

## Backlog

| ID | Milestone | Task | Depends on | Acceptance evidence |
|---|---|---|---|---|
| T01 | v0.1 | Constitution and ADRs | none | Reviewed architectural decisions |
| T02 | v0.1 | DONE in #34, #35: JSON schemas and immutable artifact store | T01 | Schema validation and digest tests |
| T03 | v0.1 | DONE in #38, #40, #42, #46: Sandboxed Faust compiler harness | T02 | Reproducible compiler receipts |
| T04 | v0.1 | DONE in #41, #45, #79 (`bb367c9`): DSP signal harness and finite ARM/x86 golden validation | T03 | Known-good/known-bad fixtures |
| T05 | v0.1 | DONE in #37: Source rights inventory; five identity corrections and coordinated repinning merged in #97 | T01 | Provenance and exclusion receipts |
| T06 | v0.2 | DONE in #39; extraction infrastructure in #89 and H2/H3 implementation in #98 (real-corpus qualification and FLOOR open): Normalization and dedup | T05,T02 | Deterministic snapshot. Dedup uses provisional TOKEN_FLOOR=40. P0 exits only if that floor is accepted by the Q3 protocol or marked provisional with a recorded leakage caveat |
| T07 | v0.2 | CANDIDATE AUDITED; split freeze PENDING | T06 | Leakage checks and signed split manifest. A freeze on the provisional floor records a leakage caveat and a scheduled re-check. Leaked items are removed and the removal is logged. Holdout novelty is re-checked once the floor is accepted, before any P3 exit claim rests on the holdout |
| T08 | v0.2 | Baseline models | T04,T07 | Frozen baseline measurements |
| T09 | v0.2 | HARNESS DONE in #36; spark-af42 repaired-candidate fingerprint COMPLETE on `1ae20ba` (2026-10-20 PT); second machine conditional | T01 | Fingerprint receipt per machine (R-001, amended 0.3.1); throughput at T10. The P0 Spark throughput smoke test is replaced by that fingerprint (Q4) |
| GD-1 | v0.3 | GRPO whole-group drop and group-drop tracking | T04 | A group with a quarantined member is dropped whole from the gradient update, not masked. Rows are held only for triage and receipts and never re-enter. Rate logged per checkpoint and per prompt. Halt pauses P3 for triage instead of resampling. A prompt dropped repeatedly goes to human triage. Prerequisite of T10 |
| T10 | v0.2 | DEPENDENCY/CUDA VALIDATED; candidate T09 fingerprint and Qwen training/checkpoint smoke COMPLETE; FORMAL TRAINING GATES PENDING; training path P1-P3 (ADR-0002, accepted 2026-10-17 7:40 PM PT) | T08,T09,GD-1,A2-PATH,EVAL-SO,D3-H1,D3-H2,D3-H2-C | One pinned run and exit-gate result per phase. P3 reward is the ADR-0006 grader with the Q1 binary ruling, whole-group drop, and A2-T as the only auto-attribution path. P3 exit gate: graded/ungraded split reported; A7 quarantine rate and group-drop rate within pre-registered limits; no frozen auto-attribution signature at exit; audit disagreements = 0 unresolved; consumed log intact. From 0.3.10, P3 also waits on D3-H2-C: a halt clears only with the human triage credential, and the grader process is the dedicated `fc-grader` account. D3-H2 does not block P1 or P2. Only the ~5M-token CPT-skip threshold is ratified. The 2-point loss and compile@10 noise are paired-CI tests |
| T11 | v0.3 | Independent DSP evaluation | T10,T04 | Paired metrics and regression results |
| T12 | v0.3 | Promotion decision | T11 | Human review and decision record |
| T13 | v0.4 | Local serving API | T12 | Contract tests |
| T14 | v0.4 | IDE integration | T13 | End-to-end journey tests |
| T15 | v1.0 | Security and quality review | T14 | Independent audit |
| T16 | v1.0 | Release | T15 | Signed release manifest and rollback test |
| T17 | v0.3 | Language-backend lane (ADR-0004) | T03 | cpp, c, rust, cmajor output compiles and matches host render |
| T18 | v0.3 | Plugin lane: CLAP, VST3, LV2 (ADR-0004) | T04 | Validators and parameter-map check on good and bad fixtures |
| T19 | v0.3 | Embedded lane: Daisy, Teensy 4.x (ADR-0004) | T04 | Builds, memory and CPU budgets, real-time checks |
| T20 | v0.3 | Remix tasks and novelty metric | T08 | Remix dev tasks; novelty reported, not gated |
| T21 | v0.3 | Real-time safety checks | T04 | Bad fixtures rejected on every lane |
| T22 | v0.5-fpga | FPGA F0 spike | T04 | DecisionRecord on the lowering path |
| L1 | v0.3 | DONE in #49: RangeError is stack overflow only for the exact message "Maximum call stack size exceeded" | T03 | Landed in #49 (`f0fcdf9`) on main that includes #46 (`42ee1e4`). Prerequisite for A2-T leaving shadow, already met |
| L2 | v0.3 | DONE in #49: line-start matching on the failing stage, split on newline only | T03 | Landed in #49. This is the r5 L2 fix Jev cited: `_compile_stack_line` splits on `\n` only. Prerequisite for A2-T leaving shadow, already met |
| L3 | v0.3 | Rerun hooks for exits 124 and 125 on compile and render | T03 | Hooks feed A2-T in shadow only (r5 L3). Not quarantine-age tracking. Prerequisite for A2-T leaving shadow. Not landed |
| A7-S | v0.3 | Per-signature attribution-rate tracking, auto-freeze, resolved_by auto, stored evidence | T03 | Provisional thresholds: 20% share, 2× rise, 500-sample window. Distinct from A7's 1%, 500-sample and 2× alarm. Reviewed against shadow data before A2-T goes live. A gold-canary crash freezes its signature. Prerequisite of A2-T |
| A2-T | v0.3 | A2-T shadow mode, then live auto-attribution | L1,L2,L3,A7-S,CANARY | Shadow logs attributions and does not attribute. Shadow mode runs on a separate path that never grades: it may rerun and log attributions, but its output never reaches `reward_value` or a receipt. That path is not a training caller, so needing reruns in shadow does not conflict with A2-PATH. Leaves shadow only when L1–L3 have landed, agreement with human triage is on a sample fixed before shadow starts, the gold canary is clean and any crash there freezes its signature, A7-S thresholds are reviewed, and the go-live is recorded. Crash rows below ~0.1% keep auto-attribution off entirely. That rate is a reason to stay off, never a reason to go live |
| A2-PATH | v0.3 | CODE DONE in #51, live wiring pending: Do not supply the replaced rerun-plus-fixture path | T03 | Until A2-T is live, no training caller supplies `rerun` or `known_good`. `runtime_stack_overflow` and `wasm_trap` stay ungraded without a matching native Faust 2.88.0 failure. Source-class list alone only for a line-start Faust `ERROR` other than `ERROR : stack overflow` (plain or `in eval`; see EVAL-SO), a source over 1 MiB, and a remote import. Shadow mode runs on a separate path that never grades: it may rerun and log attributions, but its output never reaches `reward_value` or a receipt. That path is not a training caller, so needing reruns in shadow does not conflict with A2-PATH. Prerequisite of T10 |
| CANARY | v0.3 | Scheduled gold canary: dev-suite references, cleared-corpus sample, SFT targets, run on a schedule | T04 | A2-T go-live condition: the canary is clean. Any crash there freezes its signature through A7-S. Prerequisite of A2-T |
| EVAL-SO | v0.3 | CODE DONE in #51, live wiring pending: Grader must not tag stack-overflow lines as source without a native match | T03 | After #46 the compiler stores the exact line `ERROR : stack overflow in eval` as exit 126 internal. Acceptance: the grader no longer tags either line as source without the Faust 2.88.0 native match. That is the A2-PATH requirement for the plain line-start `ERROR : stack overflow` and for `ERROR : stack overflow in eval`. Prerequisite of T10 |
| D3-H1 | v0.3 | DONE in #55 (`0d68d01`): HMAC-signed reward records and group-aware `rl_batch_from_records` | T04 | See Done. Prerequisite of T10 |
| D3-H2 | v0.3 | DONE in #57 (`63aac31`), #59 (`ac0326f`), #60 (`24170c3`), #61 (`2f1caba`), #63 (`75d2bed`), #67 (`665d73b`): sampled rerun audit before P3 | D3-H1 | See Done. Does not block P1 or P2. Before P3 |
| D3-H2-C | v0.3 | DONE in #71 (`cf319f3`): signature verification and dedicated grader check, spec 0.3.11 | D3-H2 | Implementation complete; deployment credentials not provisioned by Spark setup. Follow-ups #68 and #72 remain open |
| H2 | v0.2 | H2 (brief: canonical ID/NUM shingle stream; ADVERSARY PR39 r6 adds: keep `lib.fn` qualified names, same 1/2 rule). A second shingle stream with identifiers → `ID` and numbers → `NUM`. The `STR` collapse applies only on this canonical stream. That stream is an extra stream combined with the raw stream by OR and never replaces the raw stream. ADVERSARY r6 addition; not ruled by Jev: `lib.fn`, the 1/2 rule, and the `STR` collapse | T06 | the r6 H2 probe at k = 5, 6, 8 (probe39r6.py 2b) is quarantined. k = 7 was never run. Prerequisite of FLOOR. Jev's output cites H2 and H3 from the brief and does not rule the r6 additions |
| H3 | v0.2 | H3 (brief: NFKC and drop Cf/Cc). Unicode normalization before tokenizing: NFKC and drop category Cf/Cc. The brief's H3 case is the U+200B evasion. ADVERSARY r6 addition; not ruled by Jev: the literal-insertion probe is not an H3 requirement, and the `STR` collapse is not H3 | T06 | Acceptance: the r6 U+200B probe is quarantined. The r6 literal-insertion probe (rev 0.367) is reported and is not an H3 gate, because collapsing to `STR` does not restore 5-gram overlap. Prerequisite of FLOOR |
| FLOOR | v0.2 | TOKEN_FLOOR measurement protocol | T06,H2,H3 | Real slicer and real cleared hosts, including H1-style splitting of one rejected file across 3 or more cleared files. Per-bucket recall with Wilson intervals and hand-labelled FP cost. Danny sets the recall lower bound, zero reject-class copies left in cleared, and the FP blob budget before the run. Spans under 15 tokens stay on exact hash on the ID/NUM stream, and that check needs the brief's idioms allowlisted pairing, or short idioms will be over-flagged. The shipped dedup must use the same streams the FLOOR protocol measures: the raw stream, plus the H2 canonical stream combined with it by OR. The `STR` collapse is only on that canonical stream and never replaces the raw stream. ADVERSARY confirms containment and allowlist fixes on the shipping slicer path. Bounds ratified 2026-10-18 (D6, spec §25). Separate recorded rights ruling, not part of D6: needs_human sources count as reject-class until a human clears them (fail closed). Boof (orchestrator), rights call under Danny's 2026-10-17 BlackDog rights/licensing delegation (rights-inventory.md:21-22), 2026-10-18 ~12:57 AM PT. Ruling on lower-floor detections (Danny, 2026-10-18 2:27 AM PT, "continue as recommended"; spec §25; record: FLOOR-ruling-b-recommendation-2026-10-18.md). This interprets the ratified D6 bounds and does not change their text or numbers. This closes ADVERSARY nit N9. Ground truth is fixed before scoring and does not depend on TOKEN_FLOOR. The same gold set is used for 40, 30 and 20. Every planted item is a positive at every candidate floor. Cells stay at n = 100 planted items. Natural copies: the candidate pool is the union of everything flagged at floors 40, 30 and 20, by the sub-15 exact-hash check, and by the H1 union-coverage check, on the shipping path. Each candidate is adjudicated once, on content, as COPY or NOT_COPY of reject-class text (rights_rejected, or needs_human until cleared), with a 15-token minimum and without regard to which floor flagged it. The adjudicated set is frozen before any floor is scored. Natural copies do not enter the Wilson cells. Item 4's first count counts, at floor F, every adjudicated COPY and every unadjudicated candidate that F's own shipping pipeline leaves in cleared. A copy that only a lower floor detects therefore fails item 4 at every higher floor that leaves it in cleared. Only quarantines produced by F's shipping pipeline count for F. Manual quarantine pins may be applied for corpus hygiene but do not make F pass. Every natural miss is inspected and recorded with its mechanism. Per-floor natural recall (detected / adjudicated COPY) is reported and not gated, and the report states that the pool comes from the detectors themselves. Recommendation from the record, not Danny's ruling and not a clause of the ruling above: "The mitigation is to adjudicate before scoring, and to require a second reviewer for any item whose label decides the floor." "Record which floor flagged each item separately, and require a second reviewer for any floor-deciding item." For SClarinet: "Use two reviewers and record both." |

Proposed T06/T07 requirement (D-013, Danny yes 2026-10-17 1:04 PM PT): an n-gram or AST near-duplicate filter on generated `.dsp` against the training-only set. The threshold is not set. Impulse-test paths already cannot take `eval`.

T04 follow-up (N6, Danny yes 2026-10-17): `nonlinear-suite-v1` is an eight-stimulus float32 suite at the 144000-frame floor. The signed sample check is the gate. THD+N, IMD and the Farina inverse filter are diagnostics. The suite is not in `REWARD_PROFILES`. TaskSpec `effect` is a closed enum; only `linear` and `time_invariant` are rewardable. `require_task_rewardable` is called by `dataset_reward_row` and `_rl_batch` (D5). `nonlinear-suite-fallback-v1` is the four-stimulus fallback. x86 DSP-bank goldens are committed. The corrected ARM/x86 comparison completed in #79: all 40 renders match exactly and are finite. This does not add the nonlinear suite to `REWARD_PROFILES`.

Lane issues (ADR-0004): T17 #25, T18 #26, T19 #27, T20 #28, T21 #29, T22 #30.

Follow-ups from the 2026-10-17 7:40 PM PT amendment (Jev): L1 and L2 are done (#49, on main with #46). A2-PATH and EVAL-SO are done in code (#51) and wait on live reward-path wiring. D3-H1 and D3-H2 are done (see Done). D3-H2-C is complete in #71; its remaining review follow-ups are listed under Next / To do. Still TODO: L3, A7-S, CANARY, A2-T, GD-1, H2, H3, FLOOR, and D3-H1-N9 through D3-H1-N12. A7-S and CANARY precede A2-T. GD-1, A2-PATH, EVAL-SO, D3-H1, D3-H2 and D3-H2-C precede T10. D3-H2 does not block P1 or P2. H2 and H3 precede FLOOR. Crash rows below ~0.1% keep auto-attribution off. That rate is not a reason to go live.

## Decisions

Mirrors the decision items on the [project board](https://github.com/orgs/Zero-State-LLC/projects/29). Log: [spec §18](specs/001-faustcoder/spec.md#18-decision-log).

| ID | Decision | Status | Record |
|---|---|---|---|
| LIC-001 | Split license: Apache-2.0 for specs/ and docs/, Zero State proprietary for the rest | Done (ACCEPTED 2026-10-16) | ADR-0003, #20 |
| D-003 | Sample rates 44.1 and 48 kHz (runtime clause superseded by D-003r2) | ACCEPTED 2026-10-16 | spec §14 |
| D-004 | Corpus allowlist; GPL training-only; unlicensed excluded | ACCEPTED 2026-10-16 | ADR-0003 |
| D-006 | Teacher: Opus via OpenRouter, per-run spend cap | SUPERSEDED 2026-10-16 22:25 PT | ADR-0002 |
| D-006r2 | Teacher: open-weight deepseek-v4.1-flash via OpenRouter, per-run cap; Opus for review and judging only | ACCEPTED 2026-10-16 | ADR-0002, ADR-0003 |
| ORG-001 | Repo moved to Zero-State-LLC; repo and board public for now (revisitable) | Done 2026-10-16 22:32 PT | spec §18 |
| D-003r2 | Runtimes: wasm for eval, native C++ 2.88.0 cross-check, target lanes | ACCEPTED 2026-10-16 23:39 PT | spec §14, ADR-0004 |
| D-007 | Per-function licensing; header-less files inherit repo license; AGPL excluded | ACCEPTED 2026-10-16 23:39 PT | ADR-0003 |
| D-008 | First boards Daisy and Teensy 4.x; no purchase yet | ACCEPTED 2026-10-16 23:39 PT | ADR-0004 |
| D-009 | FPGA path after F0 spike; iCE40 and ECP5; audio-rate throughput | ACCEPTED 2026-10-16 23:39 PT | ADR-0004 |
| D-010 | Remix novelty is a dev metric; faust-rs primitives out | ACCEPTED 2026-10-16 23:39 PT | ADR-0004 |
| D-011 | Upstream Faust fixes under LGPL allowed | ACCEPTED 2026-10-16 23:39 PT | ADR-0003 |
| D-012 | Plugin formats CLAP, VST3 (clap-wrapper), LV2; AU deferred | ACCEPTED 2026-10-16 23:39 PT | ADR-0004 |
| ORG-002 | Board moved to org project 29; user board 8 kept, marked superseded | Done 2026-10-16 | spec §18 |
| R-001 | v0.2 evidence: cited external Spark benchmarks plus a per-machine fingerprint; throughput is T10 on the cleared dedicated Spark | ACCEPTED 2026-10-17 12:54 PM PT | spec §20 |
| D-013 | STK-4.3 permissive with notice; bare BSD not redistributed; notice required; vendored copies deduped; per-function slicing; strictest license; copyleft near-duplicate gate proposed for T06/T07 | ACCEPTED 2026-10-17 1:04 PM PT | spec §22, ADR-0003 |
| ADR-0006 | Source-attributable failures graded at parse_error; env/harness errors (reproducible infra failures and deterministic harness defects) ungraded + quarantined; A1–A7 (A7 numbers provisional). A2 extended 2026-10-17 4:28 PM PT (Danny): untraced timeouts/crashes quarantined. In force in reward code (`grade_receipt`, spec §23) | ACCEPTED 2026-10-17 4:11 PM PT (Danny) | docs/adr/0006, spec §23 |
| Q1 | Binary P3 reward; whole-group drop; ladder is a logged diagnostic; binary-vs-ladder ablation | ACCEPTED 2026-10-17 7:40 PM PT (Jev; Danny "use jev to make decisions" 7:37 PM PT) | docs/adr/0006, spec §24 verbatim |
| Q2 | Auto-attribution only as A2-T after shadow; below ~0.1% stays off; L3 is rerun hooks | ACCEPTED 2026-10-17 7:40 PM PT (Jev; Danny "use jev to make decisions" 7:37 PM PT) | docs/adr/0006, spec §24 verbatim |
| Q3 | TOKEN_FLOOR stays 40 and provisional; protocol after H2/H3 | ACCEPTED 2026-10-17 7:40 PM PT (Jev; Danny "use jev to make decisions" 7:37 PM PT); bounds ratified 2026-10-18 12:34 AM PT; lower-floor detections ruled 2026-10-18 2:27 AM PT; value still provisional | docs/adr/0002, spec §24 verbatim, spec §25 |
| Q4 | ADR-0002 accepted in full (Jev's default; Danny may still choose P3 PROPOSED); only the ~5M-token threshold ratified | ACCEPTED 2026-10-17 7:40 PM PT (Jev; Danny "use jev to make decisions" 7:37 PM PT) | docs/adr/0002, spec §24 verbatim |
| D3-H2 | Sampled rerun audit rules (spec §26 0.3.9) | ACCEPTED 2026-10-18 8:10 AM PT (Danny, "Approve the §26 0.3.9 amendment as recommended"). Implemented in #57 (`63aac31`) and the follow-ups in Done | [danny-d3h2-audit-2026-10-18.md](docs/decisions/danny-d3h2-audit-2026-10-18.md), spec §26 |
| D3-H2-C | Human triage credential (spec §26 0.3.10) | ACCEPTED as spec text 2026-10-18 5:11 PM PT (Danny, "approved the BlackDog §26 option C spec amendment with ADVERSARY's defaults"), #66 (`fab50c2`). Implementation merged in #71 (`cf319f3`); follow-ups remain open. Later ruling 2026-10-18 5:45 PM PT, issue #68: a software key is fine for Danny's key | [danny-d3h2-option-c-2026-10-18.md](docs/decisions/danny-d3h2-option-c-2026-10-18.md), spec §26, issues #64 and #68 |

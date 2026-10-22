# T06/T07 qualification sprint

## Milestone and scope

Proposed duration: ten working days from an agreed kickoff, with an implementation
owner, a human source/leakage reviewer and a separate evaluator/custodian named
on day 1. Prabu conditionally accepts the three human roles and offers S2
days 1–3 for the 174 priority units once the evidence is usable. Danny is assigned
to independently review Prabu-authored private tasks/contracts. Prabu now reports
working access and packet hash verification. Agreed kickoff, coverage and
artifact-level independence/custody remain pending.
Plan merged in PR #100 as `c7977ce` after eight CI checks passed. Its own
[full-suite CI run](https://github.com/Zero-State-LLC/BlackDog/actions/runs/39662227221)
on PR head `1cb975a` passed 771 tests with 63 warnings. This is separate from
PR #99's earlier 771-test result recorded in [Batch 1](slice2-batch1.md), and
from the later 150-test focused Spark check cited below. S1 ran on `c7977ce`;
its evidence verification is not another runtime test-suite run.

The next milestone is a reviewed qualification dossier: a useful bounded cohort
with approved source/dependency/behavior evidence, a project-disjoint development
candidate, and a complete T06 measurement result or explicit blocked decision.
A plan alone does not close a gate. Success requires all acceptance evidence
below; a blocked report is a sprint deliverable, not milestone completion.
Production T07 stays unfrozen and `TOKEN_FLOOR=40` stays provisional throughout.
Floor selection, signing/freezing, T08 baselines and T10 training require a later
explicit decision. This sprint does not claim all 960 functions are qualified.

Use the whole 110-packet / 1,430-unit queue as the accounting scope. The original
plan selected 172 units; S1 expanded that scope to 174 with known helpers, as
recorded below. Deep-review the cohort and every dependency as one delivery,
with individual dispositions and exceptions. Do not restart small manual
batches. The existing 44 bounded passes are evidence inputs, not approvals;
170 of the original 172 units were quarantine candidates. S1 now records 172
quarantine candidates within the expanded 174-unit review scope and 1,256
explicitly deferred candidates. Report further scope additions separately;
no required helper may remain deferred for an accepted unit.

## S1 verified scope and assignments

On 2026-10-21 PT, S1 technical preparation completed on `spark-af42` at
`c7977ce`. **S1 remains open for human confirmations.** No source, contract,
dependency closure or production split was approved by this preparation.

| Verified item | Result |
| --- | --- |
| Full accounting scope | 1,430 unique candidates, each in exactly one of 110 packets |
| Pinned source inputs | 510 verified blobs; no missing inputs in the replay |
| Initial cohort and helper expansion | 172 initial candidates plus two known transitive helper candidates |
| Deep-review scope | 174 units across 21 packets; 172 are quarantine candidates |
| Deferred scope | 1,256 units, each with an explicit deferred disposition |
| Dependency gates | All 174 deep-review units still need scope/closure review; zero referenced helper IDs missing from the ledger |
| Current-main replay | 1,659 payload files exactly match historical Batch 1 outputs |
| Preservation and backup | 106,957 pre-existing files/symlinks unchanged; 1,680 off-host backup file checksums verified, zero failures |

The two helpers extend the proposed review scope; they do not constitute an
approved closure. Whole-file imports, external members, local scope and
unadmitted helpers may require further explicit additions. The full 1,430-unit
ledger remains intact. No required helper can remain deferred for an accepted
unit, and a bounded behavioral pass does not replace dependency review.

All 110 packets have **Prabu** assigned for human source/leakage and independent
contract review. The user also assigned Prabu as the separate evaluator/holdout
custodian. Codex owns S1 preparation and proposed tooling, with no human
adjudication authority. Prabu subsequently conditionally accepted these roles;
this is not evidence that any unit review has occurred. The owner assigned Prabu
as private holdout author and Danny as independent reviewer of his tasks/contracts.

Prabu now reports usable Spark access and completed packet/S1 hash checks.
Pending before S1 closes: agreed kickoff,
confirmation of useful behavior coverage, and artifact-level
independence/custody arrangements. Record authorship and conflicts: Prabu cannot
independently approve contracts he authored; assign another independent
reviewer where needed. Keep private holdout tasks and signing keys outside
agent/training access. One person's assignment to multiple roles does not
establish those boundaries. S1 preparation itself sent no messages; the later
reviewer handoff below was sent with user authorization.

### S1 receipts and verification

Spark receipt root, outside Git and `/tmp`:
`/home/delphi/blackdog-qualification-sprint-20261021T194809Z/`.
Start with `REPORT.md` and `REVIEW-INDEX.md`.

- `input-bindings.json` binds code, inventory/notice, span candidate, prior
  qualification, group plans, baseline and resolved source mappings.
- `scope-ledger.UNAPPROVED.json`, `packet-assignments.PROPOSED.json` and
  `reviewer-roles.PROPOSED.json` record scope, assignments and pending decisions.
- `dependency-gaps.json` and `behavior-coverage.PROPOSED.json` retain unresolved
  closure questions and proposed coverage for human review before S3 execution.
- `current-main-replay/` holds the regenerated packet evidence.
- `preservation-result.json`, `summary.json`, validation logs and `SHA256SUMS`
  record the checks. Earlier scripts and failed diagnostic logs are retained.

Batch 1's original code binding predates PR #99's SHA-256 blob-format fix.
S1 recorded both bindings and verified identical replay payloads on current
main. The first S1 validator stopped because it compared the base source map
with a receipt bound to the map after discovery fallback. The retained v2
validator uses the driver's same resolution rule and verifies the resulting
digest; no upstream receipt was changed to make it pass.

Verified local backup:
`/Users/appliedalchemylabs/Documents/Codex/blackdog-s1-backups/blackdog-qualification-sprint-20261021T194809Z/`.
The adjacent `backup-verification-20261021T194809Z.json` records all 1,680 file
checks and the SHA-256 manifest digest
`cbdbb519508adf1ee9e9f024ef527e2b11e6509364ca991fd6ca61590208e387`.
These are evidence checks, not a new full test-suite run. The preceding
merged-main check passed 150 focused tests; its receipts remain separately at
`/home/delphi/blackdog-main-pr100-20261021/`.

Next: resolve the pending confirmations, then use the 21 prioritized packets
for S2 review of 174 units and required helpers. Keep the other 89 packets
accounted for; retain the complete natural-copy pool for later FLOOR work.
`TOKEN_FLOOR=40` remains provisional and T07 remains unfrozen. S1 used no sudo,
workload stops, environment installations or tracked-file changes.

## Slice 2 reviewer handoff and verified evidence

On 2026-10-21 PT, Prabu replied to the user-authorized handoff with conditional
acceptance of source/leakage review, independent contract review and separate
evaluator/holdout custody. He can cover S2 days 1–3 for the 174 priority units
if the evidence arrives pre-digested. He explicitly approved no units and will
flag authorship conflicts rather than approve his own contracts. The original
174-row return template remains `UNREVIEWED`. The later Forge draft summary below is not an
adjudicated return; its actual files have not yet been received.

Prabu reported that his `spark` alias reached the other Spark and that access
to `spark-af42` failed host-key verification. No SSH trust bypass or key change
was made. The owner subsequently authorized email attachment delivery. The
verified bundle below was sent. Prabu subsequently reported working read-only
access through `spark2` and completed packet hash checks, including S1. That
report supersedes the access blocker; SENT alone was not proof of access. Day 1 is
not set until access, complete evidence and coverage are confirmed and kickoff
is agreed. A 15-minute reply monitor remains configured.

The owner chose **Prabu as private holdout author and Danny as independent
reviewer of Prabu-authored tasks/contracts**. These assignments were communicated
to Prabu. Separate custody, a private reviewer channel, conflict declarations and
a documented authorship plan must precede private task creation. The plan keeps
task contents and signing keys outside Spark and agent/training access; only
approved exclusion metadata, review commitments and public verification may
reach that side. Assignment alone does not establish custody or completed review.
Private correspondence and contact details remain outside Git.

### Verified email bundle and decision receipts

The owner-authorized attachment is
`blackdog-s2-review-bundle-20261021T2240Z.tar.xz` (4,741,632 bytes). Gmail's sent
message metadata confirms that filename and size. Its **2,391 payload checksums**
were verified, including **510 original Git-blob-verified source files**. It
contains the S1 evidence, direct-comparison dossiers, original return template,
authorship assignment, bound inputs and `path-map.json`. Historical absolute
paths and original hashes remain intact; the map locates bundled copies.
This is reviewer evidence, not a complete historical runtime environment.
Rights-rejected comparison material remains private and receives no new rights
clearance through packaging or delivery. No private holdout tasks, keys, models
or environments are included.

- Archive SHA-256: `1df7318302ef7dc3e8c75658fcae3b400351648deb83a2ba601f090c5ed28a30`.
- Top-level `SHA256SUMS` digest: `52251c4b72f5daa8bfd2da1d123762b13a36b68a4837dc8eb90d0fc12ff1210f`.
- Spark bundle directory: `/home/delphi/blackdog-s2-review-bundle-20261021T2240Z/`;
  its `.tar.xz` archive is adjacent.
- Verified local archive and adjacent checksum:
  `/Users/appliedalchemylabs/Documents/Codex/blackdog-s2-backups/`.
- Reply/assessment: `/home/delphi/blackdog-s2-reviewer-reply-1a16087a36cb7dc4/`;
  local backup subdirectory `reviewer-reply-1a16087a36cb7dc4/` under the same
  local backup root. Both receipt checksums passed.
- Owner assignment: `/home/delphi/blackdog-s2-authorship-decision-20261021T223523Z/`;
  also preserved inside the verified bundle.
- Delivery receipt: `/home/delphi/review-bundle-email-1a1609e120e8d85f.json` and
  adjacent `.json.sha256`; matching local files reside in the backup root.

Return decisions as a **new timestamped packet outside Git**, with a checksum
manifest, exact source/dossier bindings, evidence references and unresolved rows.
Do not overwrite the original UNREVIEWED packet or submit raw decisions/receipts
to the public repository. Document summaries may follow verified review results.
Bundle/receipt checks are not new runtime tests or qualification approvals.

### Direct-comparison supplement

The diagnostic on merged main `2dd588a` evaluated 174 scoped units against 19
comparison blobs at measurement floors 40/30/20: **9,918 pair evaluations**.
It uses the shipping clustering implementation on isolated pairs, with in-process
feature caching; 12 uncached parity checks passed. It does not exercise
collective-support joins in isolation or replace the full-corpus family audit.

| Measurement floor | Units with direct triggers | Triggering pairs |
| --- | --- | --- |
| 40 (provisional operating floor) | 103 | 596 |
| 30 (measurement only) | 142 | 1,083 |
| 20 (measurement only) | 156 | 1,531 |

At floor 40 the remaining routes are 69 indirect-family-only units and two
unflagged candidates. These routes are not human COPY/NOT_COPY labels. An absent
direct trigger is not proof of NOT_COPY. No quarantine was removed and no source
or dependency closure was approved. Keep the complete 1,430-unit natural-copy
pool, including relevant short collisions and collective-support evidence.

### Receipt locations and verification

Both Spark roots are outside Git and `/tmp`:

- `/home/delphi/blackdog-s2-direct-review-20261021/`: `REPORT.md`,
  `REVIEW-INDEX.md`, `summary.json`, `bindings.json`, 174 unit dossiers,
  `verification.json` and `SHA256SUMS`. All 182 payload checksums passed.
- `/home/delphi/blackdog-s2-review-return-20261021T215913Z/`: `README.md`,
  `unit-decisions.UNREVIEWED.csv`, `gate-decisions.PENDING.json`,
  `verification.json` and `SHA256SUMS`. All four payload checksums passed;
  174 unique rows bind exact source and dossier hashes. All decisions are blank
  or explicitly unreviewed; this is a proposed return format, not automatic
  production approval input.

Verified off-host archives and adjacent `.tar.gz.sha256` files reside in
`/Users/appliedalchemylabs/Documents/Codex/blackdog-s2-backups/`:

| Archive | SHA-256 |
| --- | --- |
| `blackdog-s2-direct-review-20261021.tar.gz` | `09d29ede8d8408a0583cf96344c5b2e977a8b564301894ae64045dd6101d54b8` |
| `blackdog-s2-review-return-20261021T215913Z.tar.gz` | `8b342f01053fb97076af81d5f17fdf438c736f03de3fc68b792d9a5df3af8d69` |

Archive digests and every archived payload were reverified for this documentation
update: 182 + 4 checks passed. The prior S1 manifest also passed during supplement
verification. These are evidence-integrity and diagnostic checks, not a new
full-suite result or a new whole-environment preservation inventory. Tracked
Spark files remained unchanged; no sudo, workload stops or environment changes
were used. Existing receipts are retained; returned decisions should be saved
as new evidence, never written over the original unreviewed packet.

### Forge first-pass draft and verified intake

On 2026-10-21 PT, the owner forwarded Prabu's first-pass summary. Forge on
`gpt-5.6-sol` produced the draft after the Luna run was interrupted; the reviewer
field is reported as `forge-sol`. **This is agent-generated draft evidence, not
independent human adjudication.** No source, dependency, contract or gate is
approved by this intake.

| Reported draft result | Count / limitation |
| --- | --- |
| Rows and structural validator | 174; reported PASS, IDs/hashes unchanged, allowed values, helper links and gates checked; no UNREVIEWED values left in the draft |
| Disposition | 18 REJECT, 156 BLOCKED, 0 RETAIN_CANDIDATE |
| Copy labels | 18 COPY, 156 UNRESOLVED, 0 NOT_COPY; detector triggers were not treated as labels |
| Raw-match evidence | All 18 reportedly reproduce at least 40 exact raw tokens against Git-blob-verified comparisons; Prabu reports personally rechecking three |
| Source notice | 168 APPROVE, 6 UNRESOLVED; these remain draft judgments |
| Dependency decisions | All 174 UNRESOLVED; complete pinned closure manifests are absent |
| Gates | All seven PENDING; zero adjudicated approvals |

The six unresolved notices comprise two units each from `faust-examples-stk`,
`routes.lib:parameterized` and `routes.lib:simple`. The reported helper links are
`u076896a91f7701b693f8` → `ucc2017a1332ec6436113` and
`u9f0c7ae700a832f1fdaf` → `u9a92732462d9fdc78df5`; links alone do not establish
complete dependency closure. The cohort does not replace the 1,430-unit pool,
23 short-collision groups or 19 collective-support sets.

The actual draft files remain requested: `unit-decisions.FORGE-DRAFT.csv`,
`gate-decisions.FORGE-DRAFT.json`, `REVIEW-NOTES.md`, `validation-output.txt` and
a checksum manifest. Reported CSV SHA-256:
`e89f29e1f91f6bddbf930514931d0356dc8dd723ac3e343a1563d25c155cbe29`.
This expected digest has not yet been checked against received CSV bytes. The
meaning of the separately cited original digest is also awaiting clarification.
Requested match evidence includes blob identities, tokenizer/version, token
ranges, reproduction commands/results and the three human-checked unit IDs.

The **intake receipt**, distinct from the missing draft packet, preserves the
forwarded summary and sent request. Both copies of `intake.json` were checksum
verified again for this documentation update:

- Spark: `/home/delphi/blackdog-s2-forge-draft-intake-20261022T001253Z/`.
- Off-host: `/Users/appliedalchemylabs/Documents/Codex/blackdog-s2-backups/blackdog-s2-forge-draft-intake-20261022T001253Z/`.
- Files: `intake.json` and `SHA256SUMS`; payload SHA-256:
  `8d7adc3bd63bd45ce0f0053393fc01ee77ee40edb635893f8f0ba93b8bfd2638`.

The directory timestamp is UTC (October 21 PT). These two successful checksum
checks verify preservation of the intake, not the draft's validator or matches.
Prabu's correction that S1's 1,680-entry digest check was already complete is
recorded as his report; it is no longer listed as awaiting his verification.

Next, ingest the returned files into a new timestamped receipt directory outside
Git, validate all identities/source/dossier bindings and reproduce the 18 matches.
Obtain human decisions separately from the agent draft. Resolve the six notice
questions and pinned closures before any retained-unit qualification. Existing
bound manifests inspected so far do not establish contract authorship; an
inventory reviewer field is not an authorship attestation. The independent
contract reviewer remains unset in the draft. Bind per-contract authorship and
conflicts before independent review. Prabu authors future private holdout tasks;
Danny independently reviews those tasks/contracts through a documented private
channel. Historical authorship, custody evidence, kickoff and coverage remain
open. `TOKEN_FLOOR=40` stays provisional and T07 stays unfrozen.

### Pending gates and next actions

| Gate | Owner | Evidence required before advancing |
| --- | --- | --- |
| S1 confirmations | Prabu + owner | Conditional acceptance and S2 capacity recorded; access/hash verification now reported; agree kickoff, coverage and independence/custody arrangements |
| S2 source/leakage | Prabu | Receive and independently validate the Forge draft, then obtain human per-unit source/notice and COPY/NOT_COPY/unresolved decisions with exact evidence; relevant short-collision and collective-support adjudication |
| S3 closure/behavior | Implementation owner + independent contract reviewer | Pinned complete closures including external members, independent contracts, semantic references and positive/negative receipts |
| S4/S5 FLOOR | Human reviewer + evaluator | Two cleared host repositories, real rejected windows, fixed gold/labels and the complete ratified measurement protocol |
| S6 development/custody | Prabu as author/custodian; Danny independently reviews his tasks/contracts | Document private custody/reviewer channel and conflicts; qualify disjoint development tasks and independent private tasks; only approved exclusion metadata/public verification reaches Spark |
| S7 integration | Implementation owner + reviewers | Bound reproducible dossier, exception review and an explicit milestone decision after prerequisite gates |

On receipt of decisions, verify identity, source/dossier bindings, completeness,
evidence and authorship conflicts before accepting them. A contract author cannot
provide their own independent approval. Do not import private holdout contents or
signing keys into agent/training access. Production compiler runs wait for reviewed
source/closures/contracts; FLOOR execution waits for approved hosts/windows/labels.
Further diagnostic runs alone cannot close these human gates. Slice 2 remains
blocked on independent inputs, `TOKEN_FLOOR=40` remains provisional and T07 remains
unfrozen. Production signing/freezing still requires a later explicit decision.

## Schedule, owners and acceptance

| Days | Work package | Accountable role | Required output and exit |
| --- | --- | --- | --- |
| 1 | S1: Bind scope and decisions | Implementation owner + human reviewer | Verify receipt hashes, source pins and all 1,430 identities; assign all 110 packets; record reviewer/custodian identities and required availability. Select useful behavior coverage before running tests. |
| 1–3 | S2: Source and leakage adjudication | Human source/leakage reviewer | Review all 174 scoped units and any further required helper closure; record individual source/notice, COPY/NOT_COPY or unresolved decisions with exact evidence. Account for all 23 short collision groups and 19 collective support sets relevant to the cohort; retain the complete corpus-wide queue. |
| 2–5 | S3: Closure and semantic qualification | Implementation owner; independent contract reviewer | Build a pinned, explicit dependency closure for every retained unit, including external members. Validate all approved contracts at 44.1/48 kHz with independent references and negative controls. Each attempted unit ends passed, failed or blocked with receipts. |
| 3–4 | S4: Two-project and gold-set checkpoint | Human reviewer + evaluator | Establish genuinely cleared host repositories and real reject-class windows. By end of day 3, decide whether current sources can meet the two-repository requirement; if not, propose a bounded additional source scope with rights review before acquisition. Do not replace hosts with synthetic fixtures. |
| 5–8 | S5: T06 qualification evidence | Implementation owner + human adjudicator | After S2–S4 gates, run H2/H3 regressions, fixed-ground-truth FLOOR plants and natural/FP review on the shipping pipeline. Report all floors without changing the operating constant. Any incomplete inputs produce a blocked result, not a partial pass. |
| 1–8 | S6: Development and custody preparation | Separate evaluator/custodian | Review project/family/provenance-disjoint development tasks and dependencies; name the private author/custodian and storage boundary. Only public exclusion metadata reaches Spark. Record custody commitments; do not create agent-visible tasks and call them sealed. |
| 9–10 | S7: Integration and milestone decision | Implementation owner + human reviewer + evaluator | Reproduce from bound inputs, review exceptions, validate the split candidate and preservation checks, and deliver one consolidated PR/report. Accept only if every required gate passes; otherwise provide exact blockers, owners and a bounded recovery plan. |

S2, contract preparation in S3 and custody preparation in S6 may proceed in
parallel; production compiler runs wait for reviewed source/closure/contracts.
S5 depends on approved hosts, windows and labels. The day-3 checkpoint prevents
spending the entire sprint rendering a cohort that cannot support qualification.
Human capacity and a second cleared repository are schedule risks; do not invent
approval or quietly extend scope to make the sprint appear successful.

## Measurement and behavioral gates

Preserve the shipping raw/canonical OR comparisons, source pins, sandbox
isolation, tolerances and x86 goldens. Batch execution only across identical
ordered dependency closures; group membership never grants blanket clearance.
Resolve or explicitly block all required local scopes, imports and external
members. Reject corrupted references and dependency substitutions. Compile
success or finite output alone is not semantic qualification. Do not suppress
expected silence/clipping failures to manufacture passes.

Use [spec §25](../../specs/001-faustcoder/spec.md#25-amendments-036-floor-bounds-ratified)
as the controlling FLOOR protocol:

- Eight cells: four length buckets times raw verbatim/canonical rename; 100
  plants per cell, at least 50 real window identities per cell, each in two
  cleared hosts from different repositories. Keep the same gold set at 40/30/20.
- Each cell requires a 95% Wilson lower bound of at least 0.90; inspect every
  miss and block recurring mechanisms. Include H1 split-file coverage probes.
- Fix natural COPY/NOT_COPY ground truth before scoring across the union of
  all floors, sub-15 and H1 detections. The 174-unit cohort is not a substitute
  for this complete measurement pool. Unadjudicated candidates left cleared
  count against the gate. Collective joins are not individual COPY proof.
- Apply the ratified FP budget `ceil(0.05 * N_cleared)` and its full-label or
  seeded-sample rule. Record sample seed, denominator, labels and Wilson bounds.
- Require zero remaining reject-class/unadjudicated copies in cleared,
  unresolved sub-15 exact hits and unresolved H1 union hits as specified.
  Manual quarantine does not improve a floor's measured result.

Recommend a second reviewer for floor-deciding labels, as the recorded guidance
states. Keep recommendations distinct from ratified requirements. Report the
measured eligible floor or blocker; do not edit `TOKEN_FLOOR` in this sprint.

Development acceptance requires reviewed eval rights, independent semantic
references and no unresolved project/family/provenance/dependency crossings.
A fully blocked cohort cannot meet the milestone. Private holdout content and
signing keys remain with the named custodian, outside agent/training access.
Even complete preparation does not authorize production signing or freezing.

## Evidence, delivery and stop conditions

Use a fresh timestamped directory under
`/home/delphi/blackdog-qualification-sprint-<UTC>/`, outside Git and `/tmp`.
Retain input/code digests, full per-unit decisions, closure manifests, compiler
and signal receipts, fixed gold/label manifests, per-floor reports, split-candidate
checks, exception ledger, test logs and a SHA-256 manifest. Verify an off-host
backup before handoff. Never overwrite Batch 1 or earlier receipts.

One delivery covers tooling/regressions and docs; raw sources, receipts, private
data, models, checkpoints and setup artifacts stay out of Git. Run focused
regressions during implementation and the full suite through the existing CI
approval process at review. New sudo, environment changes, model downloads or
workload stops need explicit authorization; preserve existing Spark environments.

Stop promotion on missing hashes, unresolved rights or helpers, invalid semantic
references, incomplete gold/labels, leakage, missing independent custody, or a
failed preservation check. Continue independent preparation where useful.
The final dossier lists gate status, evidence path, owner and next action for
every blocker. Neither a deadline nor a clean test suite is a waiver.

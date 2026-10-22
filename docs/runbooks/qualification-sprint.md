# T06/T07 qualification sprint

## Milestone and scope

Proposed duration: ten working days from an agreed kickoff, with an implementation
owner, a human source/leakage reviewer and a separate evaluator/custodian named
on day 1. Prabu initially accepted the nominated roles, but has since explicitly
identified as an AI agent. That acceptance does not fill any human-review role.
Packet access, hashes and reproduction are now verified. Human adjudicators,
independent contract review, agreed kickoff/coverage and separate custody remain
pending; the earlier author/reviewer assignment is not proof of independence.
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

The historical assignment files name **Prabu** for all 110 packets and for
source/leakage review, contract review and custody. **Correction: Prabu identifies
as an AI agent.** These records do not establish human capacity, independence or
custody. Codex and Forge also provide preparation and evidence, not human
adjudication. The earlier owner assignment of Prabu as private-task author and
Danny as reviewer remains an assignment history, not a qualified custody boundary.

Pending before S1 closes: named human adjudicators and an independent human
contract reviewer, agreed kickoff and useful behavior coverage, and documented
private custody. Bind contract authorship/conflicts before independent review.
Keep private tasks and keys outside all agent/training access; no private task
creation is authorized by this update. S1 preparation itself sent no messages;
the later handoff was sent with user authorization.

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
adjudicated return; its files have now been received and technically verified
as recorded below. Prabu later corrected his identity to AI agent; the earlier
role acceptance and spot-checks were not human review.

Prabu reported that his `spark` alias reached the other Spark and that access
to `spark-af42` failed host-key verification. No SSH trust bypass or key change
was made. The owner subsequently authorized email attachment delivery. The
verified bundle below was sent. Prabu subsequently reported working read-only
access through `spark2` and completed packet hash checks, including S1. That
report supersedes the access blocker; SENT alone was not proof of access. Day 1 is
not set until access, complete evidence and coverage are confirmed and kickoff
is agreed. A 15-minute reply monitor remains configured.

The earlier owner assignment named **Prabu as private holdout author and Danny
as independent reviewer of Prabu-authored tasks/contracts**. After Prabu
identified as an AI agent, that assignment cannot establish the required
human-controlled custody or independent human sign-off. Separate custody, a
private reviewer channel, conflict declarations and
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

On 2026-10-21 PT, the Forge/Sol R2 packet was delivered on `spark-af42`. Verification
used a fresh copy outside Git and `/tmp`, preserving the delivered packet and
its reproduction directory. **Structural validation and match reproduction pass;
no human adjudication or qualification gate is complete.**

| Verified packet result | Count / limitation |
| --- | --- |
| Packet integrity | All 18 manifest payload checks passed; manifest and CSV digests match delivery |
| Rows and bindings | 174 unique rows; original order, columns and ten identity/assignment fields unchanged; all 174 source and dossier hashes verified |
| Structural validator | PASS; allowed values, helper links and pending gates checked |
| Disposition proposals | 18 REJECT, 156 BLOCKED, 0 RETAIN_CANDIDATE |
| Copy-label proposals | 18 COPY, 156 UNRESOLVED, 0 NOT_COPY |
| Raw-match reproduction | 18/18 reproduced with both supplied tokenizers; comparison Git blobs verified; regenerated JSON/CSV byte-identical |
| Source-notice proposals | 166 PROPOSED_APPROVE, 8 UNRESOLVED; agent proposals, not human rights clearance |
| Dependency decisions | All 174 UNRESOLVED; 174 pinned drafts now available, none complete or human-approved |
| Gates | All seven PENDING; zero adjudicated approvals |

**AI-only review correction:** Prabu explicitly states he is an AI agent. The
previously reported three personal spot-checks were agent checks, not human
checks; he extended his cross-check to all 18. Forge on `gpt-5.6-sol` produced
the draft after the interrupted Luna run. R2 now says
`forge-sol (R2 draft, pending human adjudication; source/leakage review)`.
The immutable `assigned_reviewer=Prabu` binding does not confer adjudication
authority. `independent_contract_reviewer` remains blank on all 174 rows.
R1 is preserved unchanged; its earlier “pending Prabu adjudication” wording is
historical, not a human approval. R2 downgrades both `linearalgebra.lib` notice
proposals to UNRESOLVED, correcting R1's 168 proposals / six unresolved to
**166 proposals / eight unresolved**.

Tokenizer A is the supplied comment-stripped, NFKC-normalized raw tokenizer;
B is a separately written tokenization cross-check that retains comments.
Both replays are automated evidence, not independent human review or a new
full-corpus FLOOR measurement. Six freeverb matches against blob
`3448b86afe14d461a26a3aca73f19be9ffbbb134` are exactly 40 under A.
`uff20c5e12cefbb8a9541` is near-boundary at 43 under both tokenizers. Seven
NLFfm matches need human review of shared control/UI scaffolding; five zita-reverb
matches also await human sign-off. Reproduction does not ratify an inclusive
40-token cutoff or settle materiality, provenance or rights.

The original CSV digest is verified as
`32316c1f340cb4eb68596f67ccf866c057a5978d34bbbb7f25a9c4829402c7ec`.
Delivered R2 draft CSV digest:
`ff68a0c2f07e0c95bea35f5af99d06622da7f743b0d53b5f5d0c284594c08c51`.
Delivered R2 `SHA256SUMS` digest:
`e90c78df8d3a1d6c8fc4333e62bbeb7d9f41568967d734dbe35033f7c32b631f`.
All 18 payloads passed. A fresh R2 validator and two-tokenizer replay passed in
an isolated receipt directory; generated JSON/CSV is byte-identical to delivery.
The validator also checked return/direct/S1 manifests (4 + 182 + 1,680 entries).
Both original R1 and R2 manifests passed again after replay.

Receipt locations, all outside Git and `/tmp`:

- Complete R2 packet: `/home/delphi/blackdog-s2-forge-draft-return-R2-20261022T035347Z/`.
- R2 verification: `/home/delphi/blackdog-s2-forge-r2-verified-20261022T0356Z/`.
  Contains `assessment.json`, `REPORT.md`, `validation.log`, `reproduction.log`,
  `original-manifests-after.log`, copied packet and `SHA256SUMS`.
- Off-host R2 archive: `/Users/appliedalchemylabs/Documents/Codex/blackdog-s2-backups/blackdog-s2-forge-r2-verified-20261022T0356Z.tar.gz`.
  All 23 archived payload checksums passed; replay scratch/symlinks are excluded.
  Adjacent `.tar.gz.sha256` digest:
  `c31c2f980f9306fef79551764f0a420959c244583e6dbba058435c643affcf2e`.
- Earlier partial R2 intake: `/home/delphi/blackdog-s2-forge-r2-intake-20261022T0349Z/`
  and matching directory under the local `blackdog-s2-backups/` root. The complete
  delivery supersedes its transport blocker; no further packet request is needed.
- Preserved R1 packet: `/home/delphi/blackdog-s2-forge-draft-return-20261022T015921Z/`.
  R1 CSV digest: `e89f29e1f91f6bddbf930514931d0356dc8dd723ac3e343a1563d25c155cbe29`;
  R1 manifest digest: `5f84bd7bc65177d295f6ac8f9f79353bfe8064310bca06c10af27edbd8716adf`.
  R1 verification remains `/home/delphi/blackdog-s2-forge-verified-20261022T0213Z/`
  with its matching off-host backup directory (22 archived payloads).

Remaining review work is substantive. The two JOS-attributed units
`u669fb3ae2b89fb0d49af` and `uc9ddf0f62f5b6577cb64` need pinned attribution evidence.
R2 records routes.lib commit `2edec0537f536eaa130d42c354884d7db971663c`,
blob `b5e22c181d2f18e1a4548c735df05cddcdf490c9`, file-wide LGPL lines 20–45
and MIT bitonic range 419–470. These packet citations still require human scope
review; all four units remain UNRESOLVED/BLOCKED. Their links remain
`u076896a91f7701b693f8` → `ucc2017a1332ec6436113` and
`u9f0c7ae700a832f1fdaf` → `u9a92732462d9fdc78df5`; links do not establish closure.
Both `linearalgebra.lib` rows now remain UNRESOLVED/BLOCKED because the MIT line
sits under an LGPL header. The 166 PROPOSED_APPROVE values still require notice
re-checks and qualified human review; none establishes rights clearance.

Obtain human decisions on the 18 matches and unresolved cohort, review the
owner-authorized closure drafts below, and bind contract authorship plus independent
human review. Draft production does not approve any dependency decision. Do not
substitute this 174-unit cohort for the 1,430-unit pool, 23 short-collision groups
or 19 collective-support sets.
The proposed October 22 kickoff (America/Denver) is unconfirmed; human capacity
and coverage still need agreement. Custody remains a plan only; no private tasks
or keys exist in the packet. A human-controlled private location and review
channel must be documented before private task creation. `TOKEN_FLOOR=40` stays
provisional and T07 stays unfrozen.

### Pinned dependency-closure drafts: human review pending

Owner-authorized drafting on main `cee7fa6` produced **174 draft manifests**:
46 function slices and 128 whole-file units across 21 review groups. Each binds
R2 unit/source/dossier identity, original Git blob and commit pin, selected source
bytes, proposed local helpers and qualified members, a transitive file/import
envelope, foreign/resource candidates and a validation plan. All remain
`DRAFT_PENDING_HUMAN_REVIEW`, with `closure_complete=false`,
`production_approved=false`, no human approval and no independent reviewer.
The R2 CSV and its disposition/source-notice proposals remain unchanged.

The shared graph contains 528 hash-verified file identity nodes; each unit's
conservative envelope contains 1–47 files. Supporting nodes outside the 174-unit
cohort do not expand admission. Canonical and runtime-share library tree hashes
match the repository pins, including the `old/` and `dx7/` file aliases. No
missing or ambiguous literal import file candidates remain in these envelopes.
This does not establish Faust name resolution, actual use, minimal executable
closure, complete semantic closure or rights clearance.

| Draft validation | Result and scope |
| --- | --- |
| Manifest checks | 174/174 passed; immutable bindings, source bytes and file envelopes checked |
| Function spans | Exact selected byte ranges verified for all 46 function units |
| Tampering controls | 5/5 rejected: invented approval, wrong commit pin, dropped envelope node, altered source binding and frozen T07 |
| Scanner/path checks | 10/10 passed, including comments/strings, malformed syntax, dynamic imports, traversal and foreign-header classification |
| Preservation | 113,301 prior metadata entries unchanged; 870 read-input hashes rechecked; original R1/R2/replay manifests passed |
| Off-host backup | Archive digest and all 940 payload checksums passed |

These are automated structural checks, not human adjudication or new compiler,
signal or full-suite results. Metadata preservation checks are not full content
hashes of every environment. No environment changes or DSP execution occurred.

Remaining observed gaps include **19 qualified-reference occurrences across six
units** (`ma.EPSILON` and `bpf.start`/`point`/`end`). Selected-unit foreign/resource
references occur in six units; C headers are distinguished from Faust members.
Use `member-gaps.json` and `foreign-resource-review.json` for the exact inventory.
Every draft still needs review of local shadowing, parameters, overload dispatch,
environment scope, import ordering, foreign resources and scoped notices.

Start with `REVIEW-INDEX.md` and the 174-row `human-review-queue.csv`, organized
into 21 groups. Human reviewers must refine the conservative envelopes into
complete pinned closures, resolve gaps and notice conflicts, and bind independent
contracts before production compiler/signal validation. The per-unit plans call
for the existing dedicated sandbox, dependency-removal negative controls,
corruption/substitution rejection and independently authored target-exercising
semantic references at 44.1/48 kHz. These planned checks have not run or passed.

Final draft receipts, all outside Git and `/tmp`:

- Spark: `/home/delphi/blackdog-r2-closures-20261022T0424Z-v3/`.
  Includes `units/*.DRAFT.json`, `index.DRAFT.json`, `file-graph.DRAFT.json`,
  review queue/index, gap inventories, pinned input/source snapshots, generator
  and validator, `tests.json`, `validation.json`, `preservation.json`, `REPORT.md`
  and `SHA256SUMS` (940 payloads). Earlier attempts remain preserved; v3 is the
  final draft handoff.
- Off-host archive: `/Users/appliedalchemylabs/Documents/Codex/blackdog-s2-backups/blackdog-r2-closures-20261022T0424Z-v3.tar.gz`,
  with adjacent `.tar.gz.sha256`. SHA-256:
  `8c25300cd26ab025ff0677fe846942dbbff98e3648f439887522fb20bb64b925`.
- Readable report: `/Users/appliedalchemylabs/Documents/Codex/blackdog-s2-backups/blackdog-r2-closures-20261022T0424Z-v3-REPORT.md`,
  with adjacent `.md.sha256`.

No unit was promoted: 18 proposed COPY/REJECT, 156 BLOCKED, zero retained;
166 proposed notice approvals and eight unresolved notices remain agent-only.
All 174 dependency decisions and all seven gates remain pending. Human
assignments, contract authorship/independence, kickoff/coverage and private
custody remain unresolved. The full 1,430-unit pool, 23 short-collision groups
and 19 collective-support sets remain required. `TOKEN_FLOOR=40` stays
provisional and T07 stays unfrozen.

### Pending gates and next actions

| Gate | Owner | Evidence required before advancing |
| --- | --- | --- |
| S1 confirmations | Owner + named humans | Packet access/integrity verified; replace agent role assumptions with human assignments, agree kickoff/coverage and document independence/custody |
| S2 source/leakage | Human adjudicators, to be confirmed | Technical intake/reproduction passed; obtain human source/notice and COPY/NOT_COPY/unresolved decisions, including boundary/scaffolding cases and relevant short/collective adjudication |
| S3 closure/behavior | Implementation owner + independent contract reviewer | Review/refine the 174 drafts into complete pinned closures including external members; bind independent contracts, then obtain semantic references and positive/negative receipts |
| S4/S5 FLOOR | Human reviewer + evaluator | Two cleared host repositories, real rejected windows, fixed gold/labels and the complete ratified measurement protocol |
| S6 development/custody | Owner + named human evaluator/custodian and independent reviewer | Document private custody/reviewer channel and conflicts; qualify disjoint development tasks and independent private tasks; only approved exclusion metadata/public verification reaches Spark |
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

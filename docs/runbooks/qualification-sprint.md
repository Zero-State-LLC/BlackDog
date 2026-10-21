# T06/T07 qualification sprint

## Milestone and scope

Proposed duration: ten working days from an agreed kickoff, with an implementation
owner, a human source/leakage reviewer and a separate evaluator/custodian named
on day 1. Prabu is now user-assigned to the three human roles; acceptance,
availability and independence confirmations remain pending (see S1 below).
Plan merged in PR #100 as `c7977ce`; eight CI checks and 771 tests passed.
S1 ran on that commit. See [Batch 1](slice2-batch1.md) for the input evidence.

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
adjudication authority. These are user-confirmed role assignments, not recorded
acceptance by Prabu or evidence that the reviews have occurred.

Pending before S1 closes: Prabu's acceptance and available review capacity,
an agreed kickoff, confirmation of useful behavior coverage, and artifact-level
independence/custody arrangements. Record authorship and conflicts: Prabu cannot
independently approve contracts he authored; assign another independent
reviewer where needed. Keep private holdout tasks and signing keys outside
agent/training access. One person's assignment to multiple roles does not
establish those boundaries. No messages were sent to Prabu by S1 preparation.

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

## Schedule, owners and acceptance

| Days | Work package | Accountable role | Required output and exit |
| --- | --- | --- | --- |
| 1 | S1: Bind scope and decisions | Implementation owner + human reviewer | Verify receipt hashes, source pins and all 1,430 identities; assign all 110 packets; record reviewer/custodian identities and required availability. Select useful behavior coverage before running tests. |
| 1–3 | S2: Source and leakage adjudication | Human source/leakage reviewer | Review all 172 proposed units and their helper closure; record individual source/notice, COPY/NOT_COPY or unresolved decisions with exact evidence. Account for all 23 short collision groups and 19 collective support sets relevant to the cohort; retain the complete corpus-wide queue. |
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
  all floors, sub-15 and H1 detections. The 172-unit cohort is not a substitute
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

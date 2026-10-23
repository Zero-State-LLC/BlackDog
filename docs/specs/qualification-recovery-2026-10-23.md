# BlackDog qualification recovery specification (2026-10-23)

Status: PROPOSED. Engineering planning only. No training, production admission, spending, or merges authorized by this document.

## Goal and invariants

Unblock reproducible development without weakening the existing constitution, ADRs, immutable evidence DAG, frozen reward profiles, holdout isolation, or human approval gates. Existing qualification sprint S1-S7 remains authoritative. This plan decomposes blockers, not a replacement for its acceptance criteria.

## Journey -> workflow -> state -> contract -> acceptance -> task

### Q1: PR integration readiness

Journey: maintainer reviews #112, #113, #114, #76, #73 and historical #33.
Workflow: fetch latest main and heads -> diff/overlap map -> inspect reviews and checks -> rerun focused, full Linux and mutation tests -> record merge recommendations.
States: DISCOVERED -> REVIEWED -> VERIFIED -> APPROVAL_REQUIRED -> MERGED; failure -> BLOCKED.
Contract: every PR has base/head SHA, checks, failing tests, profile-digest impact, overlap map, reviewer disposition. No auto-merge.
Acceptance: each PR has a hash-bound evidence record; #76 must validate TaskSpec on all reward-bearing paths with negative tests. No change to frozen digests without approved versioning.
Tasks: QR-01, QR-02.

### Q2: Source and dataset eligibility

Journey: source reviewer can account for all 1,430 units, 110 packets, 510 blobs, 23 short groups and 19 collective sets, without silently admitting unresolved material.
Workflow: inventory -> verify digest and provenance -> review licenses and transitive imports -> classify COPY/shared-lineage, NOT_COPY, BLOCKED -> family/split validation -> independent review -> admit or reject.
States: INVENTORIED -> VERIFIED -> REVIEW_REQUIRED -> APPROVED_FOR_SCOPE -> QUALIFIED; unknown or conflicting -> BLOCKED.
Contract: immutable per-unit ledger with unit/packet/blob digests, source URL/revision, notice, dependency closure, family, leakage cluster, evidence path, reviewer, approval scope and admission status. Historical R2 dispositions remain historical. Seven bounded closures are not a production-admission count. Preserve exact approved receipts; never infer approvals.
Acceptance: reconciliation sums and uniqueness checks pass, unknown rights fail closed, no training/evaluation contamination, independent positive and negative receipts reproducible.
Tasks: QR-03, QR-04.

### Q3: Two-host FLOOR and custody

Journey: evaluator can produce leakage-resistant evidence with two cleared host projects, fixed gold and independent custody.
Workflow: select hosts -> rights review -> freeze task/label protocol -> isolate families and private tasks -> execute two-project FLOOR -> independently audit -> qualification dossier.
States: HOST_PENDING -> HOST_CLEARED -> GOLD_RATIFIED -> MEASURED -> REVIEWED; otherwise BLOCKED.
Contract: host rights, exact source hashes, frozen labels, denominator and thresholds, independent task author, private human-only storage, disjoint split proof, replay manifests. No agent access to private holdouts.
Acceptance: full denominator accounted, both hosts independently cleared, receipts independently replayable, S4/S5/S6 signed off. S7 explicitly PASS/FAIL/BLOCKED.
Tasks: QR-05, QR-06.

### Q4: Spark model qualification

Journey: operator evaluates an isolated candidate without treating smoke success as permission to train.
Workflow: preserve baseline -> verify repaired wheel provenance -> check host/workload -> approved local model -> inference and adapter probes -> checkpoint save/reload -> measure memory/throughput -> stack-pin decision.
States: ENV_VERIFIED -> MODEL_APPROVED -> PROBED -> EVIDENCE_REVIEWED -> PIN_APPROVED; no model -> BLOCKED.
Contract: pinned Python/torch/CUDA/wheel digest, hardware, source SHA, model license and digest, commands, peak VRAM, timing, errors, checksum receipts. Existing repaired cuSPARSELt 0.8.1 candidate is a downstream packaging repair, not vendor-supported release.
Acceptance: pip check, sparse/dense regression, representative probes and checkpoint restore, clean isolation, no baseline mutation. No unauthorized downloads, training, sudo or workload stops.
Tasks: QR-07.

### Q5: Evaluation funnel

Journey: reviewer can distinguish syntax, compiler, DSP signal, and independent qualification outcomes.
Workflow: static eligibility -> pinned compiler -> deterministic signal checks -> adversarial/family-disjoint evaluation -> human evidence gate.
States: SUBMITTED -> STATIC_PASS -> COMPILE_PASS -> SIGNAL_PASS -> QUALIFIED, with any failure terminal and attributable.
Contract: immutable task and compiler bindings, all-channel sample comparison, controls/input stimuli and guarded expected-zero companion receipts, stable legacy profile digests. Diagnostic-only results never become reward-bearing.
Acceptance: negative controls catch silent/incorrect output; compiler version pinned; mutation tests cover guard bypasses; evaluation costs and timings recorded; holdouts isolated.
Tasks: QR-08.

## Priority and dependencies

P0: QR-01, QR-03, QR-04, QR-05, QR-06. P1: QR-02, QR-07, QR-08. Security follow-ups #62/#68/#69/#72 remain separate fail-closed work. QR-05 depends on QR-03/04; QR-06 on QR-05; reward admission depends on QR-02/08. No T07 freeze until all governing gates pass.

## Verification and rollout

Implement ledger/reporting on feature branches with fixture-only data. Run schema validation, reconciliation, positive/negative tests, independent replay and Linux CI. Publish hash-bound evidence references without uploading restricted source or private tasks. Require human review before merges, corpus admission, stack pin, training or release.

## Research and decisions

Investigate upstream ARM64 wheel compatibility only if the repaired isolated candidate fails representative probes. Do not bypass PyTorch's exact dependency pins. Prefer existing Faust compiler and DSP harness over proxy-only text metrics. Resolve host rights and custody through actual human approvals, not agent-generated attestations.

## QR-01 live PR reconciliation, 2026-10-23 PT

Read-only GitHub metadata and changed-file inspection (not a test run):

| PR | Head SHA | Mergeable reported | Overlap and disposition |
| --- | --- | --- | --- |
| #112 | e5833deff088a7b45797a996c103d2372cd712e7 | yes | KANBAN overlap with #113/#114/#115; review tests and source documentation |
| #113 | de6e3b37a85d4854dc71053347f2a962e1f52c8b | yes | KANBAN overlap; signal.py overlaps draft #76; inspect Codex review and current-head CI |
| #114 | ced2681c958fde9a198729bf622ae7b71324949e | yes | KANBAN overlap; verify approved source/notice receipt scope |
| #76 | 829b9a7b4580dd1be58e7aafbfdb3d70689f7818 | no, draft | signal.py overlaps #113; TaskSpec completeness and tests required |
| #73 | 8798cb24edca3e9ac4c1fb664ccce9d78910c7ee | yes | separate specs/002 subtree; reconcile canonical 001 and review notes |
| #115 | 301efd965f1e45416d9ff96ffcec2a923e40987e | yes, draft | KANBAN overlap; documentation-only recovery plan |

Recommended integration order: first review #112 and #114 independent content; then #113 harness with focused, full Linux and mutation evidence; reconcile and rebase #115 after those merges; treat #76 as a separate reward-security gate, rebasing onto accepted signal.py changes; resolve #73 normative naming before merge. Do not interpret the order as approval to merge. Each changed head requires refreshed CI, reviewer disposition and updated conflict analysis. Review submissions for #113 and #73 include automated COMMENTED reviews; no approving review was returned for the inspected PRs. Combined commit statuses, review threads, full patches and current test execution remain unverified.

## QR-01 patch, review-thread and workflow evidence, 2026-10-23 PT

Read-only patch and review-thread retrieval completed for #73, #76, #112, #113 and #114. GitHub Actions runs on the inspected head SHAs report successful docs/spec/workflow/secret-scan checks for #73/#76/#112/#114. These four checks are not evidence of full runtime-suite success. #113's latest-head workflow result was not returned by the inspected run lookup; its PR description reports eight successful CI checks and 860 tests at head de6e3b37, but independent current-head confirmation remains open.

**Blocking finding #73:** unresolved, current inline review thread PRRT_kwDOVNCMgs6ufzBB on specs/002-model-quality-hardening/spec.md:17. Review notes the proposal would silently forbid spec 001's accepted provisional T07 freeze option. Repair: preserve provisional freeze with explicit leakage caveat and scheduled re-check; require QH-02/FLOOR before P3 exit/promotion. Update spec, tasks, and traceability, then seek fresh review. Do not resolve thread before verifying correction.

**Blocking finding #76:** draft and not mergeable. Patch adds TaskSpec guard at commit_signal_check and propagates task into reward grading, but only a subset of callers/tests is updated. Require explicit reward/nonreward matrix, invalid/missing TaskSpec rejection before any artifact persistence, sealed native evidence propagation, full test-suite and mutation evidence. Rebase only after #113's accepted signal.py changes; do not merge now.

**#113:** new diagnostic_cases.py and diagnostic-cases.mjs, changes to signal.py/render.mjs, ADR-0008 and test coverage. Verify compiler/runtime receipt binding, all-channel comparisons, nonzero companion execution and preserved legacy profile bytes. Existing COMMENTED automated review requires reading any findings against the current head; no approving review returned. No production/reward admission.

**#112/#114:** bounded tests and approved-source documentation respectively, with no inline review threads returned. Both change KANBAN.md and therefore require conflict-aware integration with #113/#115. #114's historical disposition and new approvals must remain distinct.

Next verification: inspect #113 latest-head CI jobs/logs, full #113/#76 signal.py overlap, #73 exact provisional-freeze wording, and source receipts outside Git where authorized. This audit is not a substitute for executing tests.

## Owner direction: automation-first, minimal-handwork governance (2026-10-23 PT)

Owner requests a practical path to training with minimal manual ceremony. This is a **proposed implementation policy** for reconciliation with canonical spec/constitution; it does not itself supersede higher-priority requirements or grant training admission.

### Three lanes

1. **Green, automated engineering:** fixture generation, provenance extraction, license classification suggestions, dedup, lineage clustering, compiler/signal tests, PR checks, synthetic GPU training diagnostics, and evidence packet assembly. Run without per-item manual approval when read-only, reversible, and within existing resource permissions. Automated reports carry source hashes and failure explanations.
2. **Amber, bounded batch review:** one consolidated review for ambiguous licenses/imports, external-host eligibility, frozen gold selection, private custody configuration, model/download or compute budget. Review only exceptions and final summaries, not every unit. Approve precise scopes, with expiration/change triggers; previously approved source decisions are reused, never repeatedly requested.
3. **Red, explicit authorization:** external redistribution, restricted/private data disclosure, training on unqualified data, promotion/release, irreversible destructive actions, unbudgeted spending, or bypassing reward/holdout integrity. These cannot be automatically cleared by an agent.

### Fast training path

- **Track A: synthetic dry run:** allow CPU/GPU smoke, generated DSP fixtures, synthetic training-step/checkpoint verification, and throughput benchmarking without a production corpus. Label outputs DIAGNOSTIC and prevent model admission.
- **Track B: qualified small pilot:** prepare a tiny rights-cleared, family-disjoint dataset, pinned model and isolated environment. Automate receipts and gates. Submit a single bounded approval for actual pilot training only after canonical required conditions are met. No requirement to finish every broader corpus unit merely to run an independently qualified pilot, unless canonical spec expressly requires it.
- **Track C: full corpus training:** retain complete source/notice/lineage accounting, two-host FLOOR and custody conditions wherever required by the governing specification. Automate batch processing and exception review.

### T07 and reward compatibility

Preserve canonical spec 001's provisional T07 freeze route with documented leakage caveat and scheduled recheck. Do not claim P3 exit or final promotion until the required QH-02/FLOOR evidence. Keep reward TaskSpec binding and frozen-profile digest checks fail-closed. No unapproved modification of canonical normative requirements.

### Acceptance criteria

One command produces a readiness report with machine-readable blockers, waiver-ineligible red gates, owner-action queue, evidence hashes, source/lineage counts and next safe executable action. No per-unit human approval for mechanically verifiable clean items. All ambiguous cases remain quarantined. Synthetic training diagnostics are not presented as qualified model training. A single owner review should cover a coherent batch of exceptions.

## QR-09 implementation slice

Read-only `python -m faustcoder.readiness --repo-root . --json` inventories required documentation, SHA-256 hashes and unverified approval gates. Unit tests cover missing evidence and document-presence-not-approval. This is a first slice only: it does not ingest external receipts, validate rights, enumerate 1,430 units, execute tests or make an authorization decision. Run CI before claiming tests passed. Next implement a typed evidence manifest, immutable receipt verification, machine-readable exceptions and qualified pilot criteria under the canonical gates.

## QR-09 manifest contract and implementation plan

Journey: an operator supplies an external, scope-bound evidence index and gets
one exception queue without copying source data into Git. Workflow: parse strict
JSON -> validate schema -> open beneath an explicit evidence root without following
symlinks -> verify SHA-256 -> classify missing, invalid, duplicate or wrong-scope
references -> report next actions. States: UNVERIFIED -> INTEGRITY_VERIFIED ->
SEMANTIC_REVIEW_REQUIRED; any invalid input -> BLOCKED. Integrity verification
never transitions to AUTHORIZED. No manifest assertion can grant training.

Contract: readiness-manifest.schema.json version 1, exact operating mode and
SHA-256 scope binding, immutable receipt references with unique IDs, paths and
content digests. Reject unknown fields, duplicate JSON keys, nonfinite numbers,
absolute/traversal paths, symlinks, special files and oversized inputs. Every
reference remains a claim until a gate-specific semantic/authority verifier is
integrated. Missing evidence is NOT_VERIFIED; bad evidence is INVALID.

Implementation: add typed frozen reference/manifest records and an fd-relative
no-follow reader; integrate optional --manifest/--evidence-root/--scope-digest/
--mode arguments into the existing read-only command. Emit exception-only output,
receipt hashes and concrete actions. Do not expose private receipt bytes.
Acceptance: positive integrity checks plus malformed, duplicate, tampering,
symlink, traversal, wrong-scope, mode and self-declared PASS refusal tests.
Task: QR-09. New contract is an advisory index, not an admission artifact.

## QR-03 accounting slice plan

Reuse the existing batch1_review output contract. Read its external binding by
an operator-pinned exact-byte SHA-256, verify every indexed payload through the
QR-09 no-follow reader, then reconcile unique candidate units, one packet per
unit, blob identities, family IDs, short collision groups and collective support
sets. Expected full scope is 1,430/110/510/23/19; disagreement blocks accounting.
Produce a canonical advisory source ledger plus exceptions and receipt bindings.
Keep all items quarantined pending gate-specific eligibility checks; intact batch
bytes do not create rights or approval. Do not change historical dispositions.
Tests use generated metadata only: wrong counts, duplicate units/packet members,
missing packets, stale hashes and traversal must fail closed. QR-04 remains open.

## QR-02 implementation contract

Validate and snapshot TaskSpec before reward execution; diagnostic calls remain
task-free. Bind the full task digest on each run, require the same digest during
commit, and preflight all receipt schemas/purposes/provenance before the first
artifact write. Reject mixed diagnostic/reward suites and malformed reward
profiles. Pass sealed native matches through immediate and deferred compiler,
crash and signal grading; absent or mismatched native evidence stays ungraded.
Existing binary reward, quarantine and frozen profile rules remain unchanged.
Tests cover no-write invalid requests, changed tasks, unallowlisted profiles,
compiler 124/125/126, stack matches and raw/wrong-source evidence. A2-PATH/EVAL-SO
remain integration-unverified until the pinned Linux sandbox suite passes.

QR-10 recipe and estimates are in the execution runbook. Null snapshot/split
bindings prevent treating that candidate as an approved runnable training plan.

## QR-08 staged evaluator plan

Journey: evaluator submits a public, rights-cleared whole-file unit and validated
TaskSpec with explicit analytical references. Workflow: canonical pinned inventory
and notice parsing plus blob verification -> pinned compiler -> both-rate signed
signal diagnostics -> independent replay gate. States: SUBMITTED -> STATIC_PASS
-> COMPILE_PASS -> SIGNAL_PASS -> INDEPENDENT_PENDING; any failure is terminal.
No stage result authorizes training or promotes a candidate.

Reuse parse_corpus, compile_source, run_signal_suite and ArtifactStore. Store one
EvaluationRun view per executed stage, chained by immutable parents, with source,
task and reference digests, producer/source identity, timing and failure tokens.
No raw source or private task content enters stage summaries. A compiler failure
must prevent rendering; a signal failure must prevent the independent stage.
Stage four is BLOCKED until an independently verified evaluator adapter exists;
a caller-provided PASS is never accepted. Function units remain blocked until
reviewed-span bindings are supported by this entry point. Tests cover each early
stop, canonical rights refusal, blob mismatch, compiler identity, both rates,
reference failure, and missing independent replay. QR-08 remains partial until
actual sandbox and independent evidence runs pass.

## QR-09 signed-snapshot semantic adapter

Journey: an operator reuses a completed public T07 evidence store instead of
re-approving its decisions. Workflow: pin an external run-scope file by exact
SHA-256 -> verify a strict, explicitly enumerated public evidence bundle ->
replay canonical verify_frozen_snapshot using an out-of-band trusted public key
-> remove only the signed-split or family-separation blocker that was verified.
States: INTEGRITY_VERIFIED -> SEMANTICALLY_VERIFIED; malformed/tampered/incomplete,
wrong-scope, wrong-signer or expired evidence -> BLOCKED. Training authorization
never changes in this adapter. Preserve the explicit provisional-floor route.

Contracts: readiness-scope.schema.json binds mode, dataset snapshot, code revision,
model and recipe digests. readiness-verification.schema.json enumerates exact
canonical object and witness paths; no filesystem discovery and no key supplied
by the bundle. A bounded read-only ArtifactStore view reuses the canonical DAG
and signed-freeze verifier. It refuses private-task entities, duplicate identities
and paths, missing parents/witnesses, symlinks and altered metadata. Only public
source/rights/snapshot/transition records are accepted. No private holdout payloads
are required or allowed. Results remain scoped to the exact snapshot in the plan.

Implementation tasks: schema/fixture tests -> read-only bundle view -> adapter ->
reporter/CLI integration -> negative and mutation tests -> CI. Acceptance includes
real disposable SSH-signed fixture freezes, wrong key and digest, stale recheck,
incomplete freeze, missing parents, tampering and proof that verified split/family
receipts cannot clear pilot-training authorization. Unknown receipt types remain
unverified; do not pretend other technical gates have semantic adapters yet.

The public-store exporter requires the external custodian public key and replays
the existing signed freeze before emitting PASS claims for these two gates.
The receiver repeats the verification. The exporter does not enroll a key,
change an input receipt or approve training. Full-corpus authorization and
dataset approval use distinct gate names from the bounded pilot lane.

## QR-10 bounded public data preparation contract

Journey: prepare the smallest reproducible pilot inputs without accessing private
tasks or claiming that preparation grants permission. Workflow: supply an exact
pilot scope, hash-bound T07 descriptor and external custodian key; replay the
canonical signed freeze; export complete train/development source partitions.
State: verified public snapshot to `PREPARED_NOT_QUALIFIED`, with no training-run
transition or admission effect.

Contract: `faustcoder.pilot_data` accepts only pilot-scoped signed evidence.
It emits at most 28 train and seven development examples, both nonempty, preserving
each selected unit's notice, license, provenance and immutable example/source
references. It never exports holdout examples or truncates a partition to fit
the bound. Recheck normalized text hashes and signed manifest bindings before
writing. Existing output, symlink inputs/parents and outputs inside the checkout
or evidence root are refused. Write private files and a completion manifest last.
Equal verified inputs and exporter code produce byte-identical output files.

Acceptance: `tests/test_pilot_data.py` exercises deterministic replay, holdout
exclusion, notice retention, scope/key/hash/tampering rejection, expired split,
malformed JSON, bounds, source binding, no overwrite and symlink refusals.
Task: QR-10 preparation only. Source/closure semantic qualification, compiler and
signal receipts, instruction-pair definition, baseline, environment, model and
owner authorization are still required before an actual training launcher runs.

## QR-10 completion-only batch contract

Journey: turn explicitly supplied prompt/target pairs into bounded causal-model
batches. Workflow: validate immutable pair bindings, tokenize prompt and target
separately without automatic special tokens, append one EOS, then right-pad
independent example rows. State: pair to encoded diagnostic input, with no
training state transition or semantic/rights approval.

Contract: `faustcoder.sft_batch` masks all prompt and padding labels with -100;
target tokens and EOS remain supervised. Labels use the causal-model unshifted
convention, so the model shifts labels once internally. No packing, truncation,
implicit chat template or cross-example concatenation is permitted. Every row
requires nonempty prompt/target token sequences, in-vocabulary integer IDs and
matching SHA-256 target binding. Bounds are at most 512 tokens and 28 examples,
matching the bounded pilot recipe. EOS in content and any tokenizer automatic
special-token insertion are refused or explicitly disabled.

Acceptance: `tests/test_sft_batch.py` covers the actual shifted-loss positions,
EOS-as-padding, independent rows, no silent target truncation, tampering, invalid
IDs/special tokens, malformed examples, determinism and batch/sequence bounds.
Task: QR-10 infrastructure, synthetic fixtures only. The encoder validates
representation, not the correctness or permission of an instruction pair.

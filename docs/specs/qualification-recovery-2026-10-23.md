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

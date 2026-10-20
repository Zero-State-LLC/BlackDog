# QH-07 implementation audit, pass 1

Scope: read-only targeted source inspection on main at cf319f376161f7c5867aed1080d86d171372a785. NOT a clean-checkout test execution. No CI, hardware, or production reward run executed.

## Finding QH07-F01: task/native evidence is not propagated in production reward paths
Severity: HIGH for P3 readiness. Status: CONFIRMED CODE PATH GAP; existing backlog A2-PATH/EVAL-SO already acknowledges live wiring pending.

Evidence:
- faustcoder/signal.py _hold_compiler_for_reward (approx lines 724-748) invokes grade_receipt with envelope, diagnostics, policy, queue and rates; no task or native receipt.
- _hold_crash_for_reward (approx lines 777-808) likewise passes no task/native receipt.
- commit_signal_check (approx lines 1088, 1112, 1127) calls grade_receipt without task/native evidence.
- faustcoder/reward/grader.py grade_receipt accepts task and handles source attribution, so the absence is at the integration boundary.
- Existing tasks.md A2-PATH explicitly states the same production wiring is pending.

Risk: task-dependent rewardability and native-matched failure attribution cannot be established at these call sites; fail-closed ungraded outcomes may be correct but leave reward coverage incomplete. This does NOT prove that quarantined samples enter training.

Minimal remediation proposal:
1. Introduce an explicit immutable task/native-evidence bundle on the SignalRun/SignalSuite or equivalent canonical path, preserving provenance digests.
2. Pass task and native receipt into every reward-graded grade_receipt call. Never invent native evidence when unavailable.
3. Enforce require_task_rewardable on every reward path, including failed compile and crash paths, without converting diagnostic-only nonlinear tasks into rewards.
4. Preserve fail-closed quarantine for absent or ambiguous native evidence.
5. Add parameterized tests for exit 124/125/126, wasm traps, runtime stack overflow, remote imports, compiler error line classes, unrewardable tasks, and native evidence mismatch.
6. Assert no quarantined row is signed as rewardable or enters rl_batch_from_records; test whole-group drop.
7. Update A2-PATH and EVAL-SO statuses only after live end-to-end tests pass.

## Finding QH07-F02: documentation status drift
Severity: LOW. Status: CONFIRMED DOCUMENTATION MISMATCH.
README advertises spec 0.3.10 while main spec.md declares 0.3.11. Reconcile after checking current PR merges. No version rewrite of accepted decisions.

## Finding QH07-F03: baseline and hardware evidence not established
Severity: RELEASE BLOCKER, not code defect. Status: DOCUMENTED PENDING.
T07, T08, T10, T11, T12 are open in tasks.md. T09 requires a real per-machine Spark fingerprint. T04 ARM goldens remain pending. No claim of trained model quality or hardware throughput is supported.

## Audit remaining
- Inspect grader signature/HMAC and triage path end to end against §26.
- Inspect compiler worker isolation and faustlibraries pins.
- Inspect rights/dedup shipping slicer and FLOOR acceptance.
- Inspect artifact store lineage and invalidation.
- Execute tests in a clean checkout, record exact environment and commands.
- Reconcile live PRs/CI before making any completion claim.

## Required disposition
F01 is already tracked in canonical A2-PATH/EVAL-SO. Do not open a duplicate bug or silently patch in a spec-only PR. Implement on a separate code PR with negative tests and a clear review boundary. F02 may be a docs-only correction. F03 remains a blocked evidence gate.

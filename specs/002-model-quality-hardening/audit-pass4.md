# QH-07 audit pass 4: task-binding scope correction

Static inspection of main cf319f376161f7c5867aed1080d86d171372a785. No test execution.

## Correction to audit pass 3
The existence of an unbound low-level minted receipt is **not evidence that it can be consumed as a production training reward**. faustcoder/reward/grader.py includes _require_receipt_task (approximately lines 422-432), which checks both the task binding digest and full task digest, and raises RewardProvenanceError on missing, altered, or mismatched task. faustcoder/reward/records.py also binds task data when building signed rows. The earlier wording that missing task may create an exploitable path must be treated as an audit hypothesis, not a confirmed vulnerability.

## Verified scope
- grade_receipt's task=None is an intentional compatibility boundary and _grade_signal can mint a receipt with absent task digests.
- _require_receipt_task explicitly rejects a receipt whose task digest is absent or does not match the supplied task. This is an existing positive safeguard.
- Production run_signal/run_signal_suite/commit_signal_check do not take task/native inputs; the A2-PATH/EVAL-SO live integration gap remains.
- The nonlinear diagnostic suite is intentionally excluded from REWARD_PROFILES. Do not add it to the reward allowlist to resolve a task propagation problem.

## Test-first implementation contract (A2-PATH/EVAL-SO)
1. Trace actual consumer of _require_receipt_task and rl_batch_from_records; assert an unbound receipt cannot become a signed consumable reward row. If this already passes, record PASS and do not patch the grader.
2. Add tests for successful linear/time_invariant task-bound receipt on all supported reward paths.
3. Add tests for absent task, malformed effect, task mutation, native evidence mismatch, crash 124/125/126 and non-native stack signatures. Expect fail-closed behavior at the production ingestion boundary.
4. Extend production signal interfaces only as needed to pass a validated task and a sealed native match, preserving existing diagnostic calls and signatures where possible.
5. Verify the signed row and GRPO whole-group drop downstream. Never convert ungraded to reward 0.0.
6. Execute test suite and provide exact command output and SHA; update task/board statuses only afterward.

## Status
Implementation PR NOT YET CREATED. No code changes and no tests executed. QH-07 remains open. Any future code PR must avoid duplicating already enforced task-binding checks.

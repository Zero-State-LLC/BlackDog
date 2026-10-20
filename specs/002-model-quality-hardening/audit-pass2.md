# QH-07 audit pass 2: reward trust-boundary details

Base: main cf319f376161f7c5867aed1080d86d171372a785. Static inspection only. This supersedes no accepted ADR and makes no claim of executed tests.

## Verified observations

1. faustcoder/reward/grader.py grade_receipt (lines 434-480) accepts task and sealed native evidence; explicitly refuses rerun and known_good. This is a positive fail-closed property.

2. _grade_compiler (lines 946 onward) returns Ungraded on mismatched diagnostics, unmatched stack signatures, signal deaths, and ambiguous 124/125/126 outcomes. It can attribute certain intrinsically source-side cases; this is consistent with ADR-0006's conservative approach.

3. _task_marks_unrewardable (lines 930-944) returns False when a task cannot be parsed or task_is_unrewardable raises. The grader docstring says apply_signal refuses marked receipts. This is not by itself a demonstrated exploitable path, but it makes task validation at caller boundaries critical. Audit every call path for a valid canonical TaskSpec and require_task_rewardable before minting.

4. faustcoder/signal.py run_signal (lines 810 onward) accepts no task/native evidence arguments; _hold_compiler_for_reward and _hold_crash_for_reward do not supply them. commit_signal_check (lines 1002 onward) similarly grades without those arguments. This confirms the previously documented A2-PATH/EVAL-SO live wiring gap.

5. commit_signal_check requires COMPILE_CHECKED state and nonempty suite; persists compiler receipts as parents of signal receipts. Positive lineage/state boundary; end-to-end parent integrity is not tested in this audit.

6. PR #71 was merged into main and implements D3-H2-C human signature checks. Earlier audit wording calling that implementation unmerged is stale.

## Required negative test matrix for code PR

- Unrewardable nonlinear TaskSpec + passing signal: no reward minting.

- Missing/malformed task and a reward request: fail closed (do not silently interpret unreadable task as rewardable).

- Native digest mismatch and unsealed native evidence: ungraded.

- Compiler 124, 125, 126; killed exits 137/139/-9; worker crash; wasm trap; stack overflow: no source reward without sanctioned attribution.

- Known source-side remote import and oversized source: source-attributed only when receipt and diagnostics satisfy accepted conditions.

- No queue/ledger on reward-graded failure: explicit refusal.

- HMAC-invalid reward record and invalid human triage signature: no gradient consumption and halt remains.

- One quarantined member in a GRPO group: whole group excluded.

- Replayed or altered receipt parent: reject.

## Priority

HIGH: implement canonical TaskSpec/native evidence propagation with explicit validation at the production boundary. Do not replace conservative grader semantics or introduce a parallel reward API. Follow existing A2-PATH/EVAL-SO tasks.
MEDIUM: add a targeted fail-closed test for unreadable task objects and prove all production reward callers reject them. If tests expose a bypass, fix in the same implementation PR.
LOW: reconcile README version and stale Kanban D3-H2-C status.

## Still unverified

CI runs, actual Spark ARM goldens, library staging on the Spark, data FLOOR acceptance, full artifact store mutation/invalidation behavior, and production end-to-end rollout signing. No merge or training promotion implied.

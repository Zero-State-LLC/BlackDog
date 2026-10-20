# QH-07 audit pass 3: task-binding and reward-minting boundary

Base: main cf319f376161f7c5867aed1080d86d171372a785. Static source inspection only; no tests run.

## Confirmed code facts
- faustcoder/reward/grader.py grade_receipt accepts optional task=None and native=None, rejects rerun/known_good, and delegates to _grade.
- _grade_signal recomputes suite and profile digests, validates dsp-reward-receipt schema, checks full comparison, and requires a digest in REWARD_PROFILES. These are important existing controls.
- _grade_signal then calls _task_digests_for_mint(task) and _mint_receipt(... unrewardable=_task_marks_unrewardable(task)).
- _task_marks_unrewardable returns False for non-Mapping tasks and on parsing errors. This means a syntactically valid reward profile with missing/unreadable task can reach the minting function with task digests absent. Whether a subsequent consumer can accept it without a task is not established here.
- run_signal and run_signal_suite accept reward_graded but not task/native inputs. commit_signal_check likewise does not accept task/native inputs. The already tracked A2-PATH/EVAL-SO live wiring gap therefore affects all these boundaries.

## Required contract decision before code change
Define whether the low-level grade_receipt API must remain capable of minting unbound receipts for diagnostic callers, while production reward ingestion must require a valid TaskSpec. Recommended: preserve existing grader semantics for compatibility, but make the production ingestion boundary fail closed on absent, malformed, unrewardable, or digest-mismatched TaskSpec; require signed native evidence only for the specific source attribution cases authorized by ADR-0006. This is a proposal, not a ratified amendment.

## Minimum test design
1. Valid linear TaskSpec + allowlisted profile + full matching render -> reward may be minted and consumed with matching task digest.
2. Missing/malformed TaskSpec -> production reward ingestion refuses before minting or consuming.
3. Nonlinear or non-time-invariant task -> no reward consumption even if profile passes.
4. Task mutated between grading and application -> digest mismatch refusal.
5. Compiler stack overflow without sealed native match -> Ungraded, with match -> only the authorized source attribution.
6. Compiler exits 124/125/126 and crash signatures without independent attribution -> quarantined, no gradient.
7. GRPO group with one quarantined member -> whole-group drop.
8. Native evidence from wrong source, compiler version, or environment -> not accepted.
9. Test all three production call paths: immediate compiler hold, deferred suite/commit, and successful signal commit.

## Implementation sequencing
A. First add tests around the production reward boundary without changing grading.
B. Add explicit task propagation in SignalRun/SignalSuite and commit call sites, preserving old diagnostic-only APIs.
C. Add native evidence binding where supported, with fail-closed absence.
D. Run the entire reward, signal, candidate, contract, and security test suites.
E. Reconcile A2-PATH/EVAL-SO and QH-07 status only with executable receipts.

No model training, no CI execution, and no production code modification occurred in this pass.

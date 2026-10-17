# ADR-0006: Grade source-attributable compiler failures

Status: ACCEPTED (2026-10-17, Danny)

Accepted 2026-10-17 by Danny. It takes effect in reward code only when the
grader changes that implement A1–A7 land. Until then the reward consumers
keep the ADR-0005 table.

- Date: 2026-10-17
- Related: [ADR-0005](0005-compiler-diagnostic-classes.md), [compiler runbook](../runbooks/compiler-harness.md)

## Context

ADR-0005 keeps exit 124 (`timeout`), 125 (`resource_limit`) and 126
(`internal`) off the R-005 ladder so a policy cannot farm them. Dropping
those samples has the other effect. A failure the source caused becomes a
way out of the parse-error penalty.

The harness already produces those exits for sources:

- a remote `import`, `library` or `component` is exit 126 `internal`
- deep recursion that overflows the V8 stack is exit 126 `internal`
- a source that runs until the wall clock or the resident cap is exit 124
  or 125

A comment that mentions `https://` hits the same pre-filter. That false
positive is benign only while the exit is not a refuge from a penalty.

An infrastructure fault is a different event: the worker crashes, or
returns `internal`, on a source that compiles when the harness is healthy.
That rate is a property of the harness and the policy's traffic, not of
one DSP program.

## Decision

- **A1:** A failure the source caused gets the `parse_error` rung, the lowest graded rung. That covers: a remote import, library or component; recursion or any other stack overflow caused by the source; a timeout or resource kill the source ran into; any `CompilerExclusion` matched by model output; and any non-finite (NaN/Inf), silent, DC or trivial render in a reward-graded run. A timeout or resource kill counts as source-attributable only once triage attributes it to the source.
- **A2:** The grader never penalizes the model for an error attributable to the evaluation environment or the harness. It distinguishes two such cases, and both are ungraded and quarantined for fixing:
  - (a) a **reproducible infrastructure failure**, i.e. a worker crash or an `internal` receipt reproduced on a known-good fixture under the same harness and environment digest within the same batch;
  - (b) a **deterministic harness defect**, i.e. the harness or environment, not the source, deterministically produces the error for a given input (for example a pre-filter false positive or a crash in harness code), as established by triage.
  Any receipt whose cause has not been attributed yet (an `internal` receipt, a timeout or resource kill with exit 124/125/126, or a worker or harness crash) is ungraded and quarantined until triage attributes it. It is graded under A1 only once it is attributed to the source.
- **A3:** Reward-graded runs force `reject_nonfinite=True`.
- **A4:** The signal comparison covers the whole render up to a pinned `max_frames`. It includes sign and timing beyond `head_frames`, not magnitude alone. `max_frames` and `head_frames` are part of the reward profile digest.
- **A5:** A grader accepts a receipt only when it carries `thresholds.reward_graded` and the canonical profile digest. `apply_signal` takes the receipt.
- **A6:** The remote-import pre-filter matches only the string arguments of `import`/`library`/`component`, not comments. This must land before A1, so that a URL in a comment is not penalised.
- **A7:** Track the ungraded rate per policy (including quarantined A2 samples). Alert when it goes above 1% of samples over a 500-sample window, or above 2× the harness baseline on known-good fixtures, whichever comes first. **PROVISIONAL: the 1%, 500-sample and 2× numbers are provisional starting values, to be tuned after the first runs.**

## Consequences

- Once the A1–A7 grader changes land, a policy cannot dodge a parse
  error by importing a URL, recursing, or allocating until the harness
  kills the compile.
- Infrastructure faults stay out of the ladder, and a rising ungraded
  rate is visible instead of being dropped quietly.
- Reward consumers keep the ADR-0005 table in the compiler runbook until
  the grader changes that implement A1–A7 land.
- A2 quarantine entries are tracked as harness or environment bugs to
  fix.
- A4/A5 specify the fix for ADVERSARY PR41 T04 r3 B1/B2/N4, and
  enforcement lands with the grader PR. A3 closes r2 N1, and A1
  (CompilerExclusion) matches the PR40 T03b note.

## Alternatives considered

- Keep every exit at or above 124 ungraded. Rejected as the proposal:
  source-caused timeouts and remote imports are then a refuge. This
  alternative remains the behavior in force.
- Grade every `internal` and `resource_limit` as a model error. Rejected:
  a broken worker on a known-good fixture would punish the policy for the
  harness.

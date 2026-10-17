# ADR-0006: Grade source-attributable compiler failures

Status: PROPOSED

Awaiting Danny. This decision is not in force. Reward behavior is unchanged.
Exit codes 124 and above stay ungraded under
[ADR-0005](0005-compiler-diagnostic-classes.md) until this record is accepted.

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

## Proposed decision

Do not apply this section until Danny accepts it. No reward code reads it
today.

1. Grade a source-attributable failure at or below the `parse_error` rung.
   That set is a remote import, recursion or any other source-caused stack
   overflow, a timeout the source ran into, and a resource kill the source
   ran into.
2. Leave ungraded only a genuine infrastructure fault. The defining case
   is a worker crash, or an `internal` receipt, reproduced on a known-good
   fixture.
3. Track the ungraded rate per policy. Alert when that rate rises.

CompilerReceipt `diagnostic_class`, the exit codes, and the consumer rule
in ADR-0005 stay as they are until a later accepted change. This record
does not add a schema value and does not rescore stored receipts.

## Consequences

- After acceptance, a policy cannot dodge a parse error by importing a
  URL, recursing, or allocating until the harness kills the compile.
- Infrastructure faults stay out of the ladder, and a rising ungraded
  rate is visible instead of being dropped quietly.
- Until acceptance, consumers keep the ADR-0005 table in the compiler
  runbook.

## Alternatives considered

- Keep every exit at or above 124 ungraded. Rejected as the proposal:
  source-caused timeouts and remote imports are then a refuge. This
  alternative remains the behavior in force.
- Grade every `internal` and `resource_limit` as a model error. Rejected:
  a broken worker on a known-good fixture would punish the policy for the
  harness.

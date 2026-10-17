# ADR-0005: Compiler diagnostic classes for harness failures

Status: ACCEPTED

- Date: 2026-10-17
- Provenance: Danny yes 2026-10-17 1:13 PM PT
- Decides: spec 0.3.2, CompilerReceipt `diagnostic_class`
- Related: [ADR-0004](0004-target-lanes-and-faust-tooling.md), [spec §21](../../specs/001-faustcoder/spec.md#21-amendments-032-compilerreceipt-diagnostics-accepted)

## Context

ADR-0004 classified compiler diagnostics as `ok`, `warning`, `type_error`,
`arity_error`, `parse_error`, `timeout` and `other`. T03 then had to put
three different outcomes in `other`: an unbound Faust name, a harness
resource limit, and a JavaScript exception from the faustwasm glue. A
reward that scores `other` above a parse error can treat a resource kill
or a remote import the same as a model mistake.

## Decision

Add three values to CompilerReceipt `diagnostic_class`. The schema version
is 0.3.2. Contracts and `schemas/` stay byte-identical.

| Class | Meaning | Exit |
|---|---|---|
| `unbound_symbol` | libfaust reports `undefined symbol` | 1 |
| `resource_limit` | memory, output size, or source size | 125 |
| `internal` | JS runtime exception, remote URL import rejected before spawn, or worker crash | 126 |

`timeout` stays exit 124. Compiler rejection of the source stays exit 1.
Exit 0 is `ok` or `warning`.

Reward consumers key on `(exit_code, diagnostic_class)`. Exit codes 124
and above are ungraded. They are not rungs on the R-005 ladder. The
operator note is [the compiler runbook](../runbooks/compiler-harness.md).

## Consequences

- A receipt can name an unbound identifier without sharing a class with a
  memory kill or a glue exception.
- Existing receipts that stored those cases as `other` are not rewritten.
  New receipts use the new classes.
- The reward ladder in R-005 is unchanged. Ungraded exits are a consumer
  rule, recorded here and in the runbook, not a new ladder rung.

## Alternatives considered

- Leave the enum and document the exit-code rule only. Rejected: `other`
  would still mix model errors with harness failures, and a consumer that
  reads `diagnostic_class` alone would grade them together.
- Score harness failures as a negative reward. Rejected for this decision:
  exit 124 and above stay ungraded so a policy cannot farm them.

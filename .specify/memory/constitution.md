# FaustCoder constitution

Version: 1.0.0
Ratified: 2026-10-16
Last amended: 2026-10-16

This constitution governs every specification, plan, task and pull request in this
repository. It restates principles already present in
[spec 001](../../specs/001-faustcoder/spec.md) §1, §11 and §15, the
[README](../../README.md), [CONTRIBUTING](../../CONTRIBUTING.md) and
[ADR-0001](../../docs/adr/0001-dag-evidence.md). Where a principle is a synthesis
rather than a restatement, it is labeled INFERRED.

## Core principles

### I. Evidence over confidence

Correctness is established by evidence, never by model confidence or
self-reported judgments. A successful compilation is necessary but not
sufficient: DSP acceptance also requires independent signal-behavior tests.
(Spec §1, R-011, ADR-0001.)

### II. Immutable, acyclic lineage

Every durable artifact carries `schema_version`, `artifact_id`,
`content_digest`, `created_at`, `producer` and `parents`, and its payload is
immutable. Evidence parent links never form cycles. A revision creates a new
node; it never rewrites an ancestor. Invalidating an ancestor invalidates
dependent attestations until they are rerun. (Spec §3, §4.1, ADR-0001.)

### III. Two graphs, kept separate

The evidence DAG is acyclic. The Faust signal-flow graph is a derived analysis
artifact that may contain legal, delayed feedback. Legal recursive Faust
programs are not rejected for containing cycles. The Faust compiler is
authoritative for language validity. (Spec §4.2, ADR-0001.)

### IV. Sealed evaluation

The frozen holdout is never used for training, prompt tuning or candidate
selection. Development work uses a separate development suite. Aggregate rates
are reported with confidence intervals and paired comparisons against the
baseline. (Spec §9.)

### V. Data rights first

No training or evaluation data enters the repository or a dataset snapshot
without provenance and a rights review. Licensed datasets, restricted training
material, model weights, credentials and receipts containing personal data are
never committed. (Spec R-002, R-014, CONTRIBUTING.)

### VI. Untrusted execution is sandboxed

Generated code, retrieved examples and prompts are untrusted. Compiler and test
workers run in restricted containers with no network, bounded CPU, memory and
time, read-only inputs and isolated outputs. Generated code never gets arbitrary
shell execution. (Spec R-013, §11.)

### VII. Bounded loops and explicit abstention

Repair and agent loops have a declared attempt bound. When the bound is reached
the system abstains with a recorded disposition instead of looping. (Spec R-012.)

### VIII. Human-approved release

No release ships without the complete gate in spec §15, including independent
human approval and a rollback artifact. Autonomous publishing is out of scope.
(Spec §2, §15.)

## Development workflow

- Specification first: `spec.md` (what and why), then `plan.md` (how), then
  `tasks.md`, then implementation. Implementation does not start until spec and
  plan exist for the area being changed.
- Stateful features carry an explicit state machine (states, events, a
  `from | event | guard | to | effect` transition table, initial and final
  states, illegal transitions). Implementers treat the transition table as the
  contract.
- Contract changes ship with schema tests and an ADR. (CONTRIBUTING.)
- Every implementation PR names its requirements, dependencies, acceptance
  tests, evidence paths, failure dispositions and security impact.
  (CONTRIBUTING.)
- Facts that are not established are labeled OBSERVED, INFERRED or
  SPECULATIVE. Requirements, metrics and "done" are never invented. (INFERRED
  from the project's Spec Kit workflow.)

## Governance

This constitution supersedes conflicting guidance in other documents. Amendments
need a pull request that updates this file, bumps its version (SemVer: MAJOR for
removed or redefined principles, MINOR for added principles, PATCH for wording)
and records the change in `CHANGELOG.md`. Reviewers check new specs, plans and
PRs against these principles. (INFERRED.)

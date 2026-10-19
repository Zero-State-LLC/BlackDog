# D3-H2 sampled rerun audit: Danny's approval

- **Who:** Danny (owner, Zero State).
- **When:** Sunday 2026-10-18, 8:10 AM PT.
- **Exact words:** "Approve the §26 0.3.9 amendment as recommended".
- **What it ratifies:** the D3-H2 sampled rerun audit, as the subsection under spec §26 (0.3.9). It applies D3 option H. It does not change the H1 text or ADR-0006 A2.
- **Recorded in:** [spec §26](../../specs/001-faustcoder/spec.md) and [ADR-0006](../adr/0006-source-attributable-failures.md).

## Approved choices

- **R.** The fail sample is ceil(5% of the failing rows). When at least one failing row exists, at least one is sampled.
- **F.** Failing rows are every graded `0.0` row: stored outcome `fail` or `source_attributed`.
- **S.** The seed is HMAC-SHA256(run key, "d3-h2-seed" || run id). The audit refuses any other seed.
- **H.** A persisted clear-report gate. P3 must not start or resume unless the latest persisted report for that run is clear. A halt clears only through human triage recorded against each disagreement. Another seed does not clear it.
- **Canaries.** The canary set reuses the §24 gold canary definition (dev-suite references, cleared-corpus sample, SFT targets). The audit reads canaries from the signed rows only.

## Not ruled

Ed25519 and DSSE. The audit cadence after P3 starts. Any numeric halt threshold other than zero disagreements.

## Later

Human-triage Ed25519 is ruled in spec §26 0.3.10 (Danny, 2026-10-18 5:11 PM PT, "approved the BlackDog §26 option C spec amendment with ADVERSARY's defaults"). Record: [danny-d3h2-option-c-2026-10-18.md](danny-d3h2-option-c-2026-10-18.md). Issue #64. A run-key MAC alone does not clear a halt.

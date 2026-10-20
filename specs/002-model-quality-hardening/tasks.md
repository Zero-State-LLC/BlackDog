# Spec 002: implementation task decomposition

Status: PROPOSED. Subtasks use QH identifiers to avoid collision with existing T01-T22 and security task IDs. Not yet mirrored into canonical KANBAN or GitHub Project. No completion claim.

| ID | Existing parent | Dependencies | Deliverable | Acceptance evidence |
|---|---|---|---|---|
| QH-01 | T04/T11 | T04, ARM goldens | Non-reward semantic DSP evaluation task matrix | oscillator/filter/compressor/delay/routing positive and negative fixtures; signed-sample comparisons at 44.1/48 kHz; failures classified per ADR-0006 |
| QH-02 | T07 | H2,H3,FLOOR,T06 | Leakage certification manifest | frozen ground truth, shipping raw+canonical stream results, per-bucket Wilson bounds, cross-split audit, human dispositions; no silent promotion of provisional floor |
| QH-03 | T08 | T07,T04 | Retrieval baseline | fixed prompt and sampling policy; index only from rights-cleared training partition; no eval/holdout content; paired compile@1 and pass@1 |
| QH-04 | T09/T10 | T09 fingerprint | Spark recipe benchmark | actual sequence lengths and training method, tokens/sec, memory peak, restart/recovery receipt; separate from external benchmark |
| QH-05 | T10 | QH-03,QH-04 | SFT selection report | base vs retrieval vs P2, task-family breakdown, paired confidence intervals, repair success, regression tests |
| QH-06 | T11/T12 | QH-01,QH-05 | Promotion quality dossier | immutable suite/model/environment digests, independent evaluation, one-shot holdout compliance, human decision |
| QH-07 | T15 | T03,T04,T06,D3-H1,D3-H2 | Implementation audit | code-path, contract, fixture, CI job, receipt mapping; defects with reproductions, severity and minimal patch proposal |

## Task-level engineering contract
For each QH task, the implementing agent must record: owner, target branch and base SHA, exact inputs, immutable outputs, upstream dependencies, state transition, failure and quarantine disposition, rollback, unit/contract/integration test commands, execution evidence and reviewer. Never mark DONE solely because a spec or mock exists.

## Work allocation and precedence
QH-07 is a read-only audit and can begin now. QH-01 can proceed independently of training, but ARM golden evidence requires the Spark. QH-02 precedes T07 freeze. QH-03 precedes candidate selection. QH-04 runs on the dedicated Spark and does not replace T09's accepted fingerprint-only v0.2 gate. QH-05 follows P2, not necessarily P3. QH-06 follows T11. Do not create an additional release track.

## Regression invariants
- Faust source is the model's only generated target language.
- No LLM judge substitutes for compiler/signal evidence.
- No quarantined GRPO group enters a gradient update.
- No nonlinear diagnostics become rewards by implication.
- No rights-rejected or needs_human source enters the cleared corpus.
- No frozen holdout content enters retrieval or training.
- No schema change bypasses the existing immutable artifact envelope.
- P3's signed triage and fc-grader checks are never weakened.

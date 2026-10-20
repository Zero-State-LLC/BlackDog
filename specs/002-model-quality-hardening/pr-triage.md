# Open PR triage and integration decision (2026-10-20)

Base main: cf319f376161f7c5867aed1080d86d171372a785. Search found three open PRs: #32, #33, #73. No review submissions or threads on #73 at time of check.

## #73: spec 002 model-quality hardening
Disposition: KEEP DRAFT pending implementation audit and spec reconciliation. Four new documents are additive, not normative. The earlier draft's statement that D3-H2-C is unmerged is stale: main HEAD #71 implements D3-H2-C per-human triage signatures and fc-grader startup checks. Recheck source and tests, not old KANBAN status, before asserting the gate is still missing. The live A2-PATH/EVAL-SO evidence propagation remains documented as pending in tasks.md and is independently visible in signal.py. Do not merge before removing status errors in proposal and synchronizing accepted subtask IDs with canonical board.

## #32: older spec 0.2.1 and CI hardening
Disposition: HOLD for rebase/reconciliation, NOT safe to merge wholesale. Modifies canonical spec.md and research.md, which main has subsequently advanced to 0.3.11. Separate non-conflicting CI hardening (SHA-pinned actions and schema validation) from proposals P-01 to P-09; determine which proposals were accepted or superseded by later ADRs. No implicit acceptance from an old PR. Run workflow checks and compare current main before cherry-picking.

## #33: older VST3 evidence and plugin-lane CI
Disposition: HOLD for rebase/reconciliation, NOT safe to merge wholesale. Modifies ADR-0004, spec.md, tasks.md, KANBAN and research.md; later main may have advanced these. Preserve documented known upstream issues and licensing uncertainty. Independently validate plugin-lane CI on current toolchain, and keep expected-failure checks explicitly non-gating until a decision changes that policy. Do not accidentally downgrade canonical 0.3.11 to 0.3.1.

## Cross-PR merge order
1. Correct spec 002 status drift; finish QH-07 source-level and CI audit.
2. Extract compatible CI hardening from #32 as a fresh narrowly scoped change after validation.
3. Rebase #33's evidence and plugin CI on main, resolve upstream and licensing caveats.
4. Reconcile QH tasks into canonical spec/board, then make #73 ready for review.
5. Merge only when CI and review evidence are present, with exact expected head SHA. Avoid merging conflicting stale spec files.

No PR merged or closed by this triage. No training started.

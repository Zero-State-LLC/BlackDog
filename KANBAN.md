# BlackDog implementation backlog

Formerly FaustCoder; renamed 2026-10-17 PT.

Status as of 2026-10-18 12:34 AM PT (Danny ratified the FLOOR bounds, D6). DONE on main: T02 (#34, #35), T03 (#38, #40, #42, #46), T04 (#41, #45), T05 (#37), T06 (#39), L1 and L2 (#49). HARNESS DONE, EVIDENCE PENDING: T09 (#36). Its acceptance needs the per-machine fingerprint receipt from the cleared dedicated Spark, which has not been captured yet. CODE DONE, LIVE WIRING PENDING: A2-PATH and EVAL-SO (#51, `cef8a14`). The grader enforces them, but the production reward path (`run_signal`, `commit_signal_check`) does not yet pass the task or a native receipt to `grade_receipt`. They are fully done only when that wiring lands. Everything else is **TODO**. T01 waits on ADR-0001, which is still PROPOSED. Open follow-ups of done tasks stay on their own rows: H2, H3 and FLOOR for T06; the ARM goldens compare for T04. Dependency arrows are mandatory promotion gates.

| ID | Milestone | Task | Depends on | Acceptance evidence |
|---|---|---|---|---|
| T01 | v0.1 | Constitution and ADRs | none | Reviewed architectural decisions |
| T02 | v0.1 | DONE in #34, #35: JSON schemas and immutable artifact store | T01 | Schema validation and digest tests |
| T03 | v0.1 | DONE in #38, #40, #42, #46: Sandboxed Faust compiler harness | T02 | Reproducible compiler receipts |
| T04 | v0.1 | DONE in #41, #45 (ARM goldens compare pending on the DGX Spark): DSP signal test harness | T03 | Known-good/known-bad fixtures |
| T05 | v0.1 | DONE in #37: Source rights inventory | T01 | Provenance and exclusion receipts |
| T06 | v0.2 | DONE in #39 (H2, H3 and FLOOR follow-ups open): Normalization and dedup | T05,T02 | Deterministic snapshot. Dedup uses provisional TOKEN_FLOOR=40. P0 exits only if that floor is accepted by the Q3 protocol or marked provisional with a recorded leakage caveat |
| T07 | v0.2 | Split freeze | T06 | Leakage checks and signed split manifest. A freeze on the provisional floor records a leakage caveat and a scheduled re-check. Leaked items are removed and the removal is logged. Holdout novelty is re-checked once the floor is accepted, before any P3 exit claim rests on the holdout |
| T08 | v0.2 | Baseline models | T04,T07 | Frozen baseline measurements |
| T09 | v0.2 | HARNESS DONE in #36; fingerprint receipt on the Spark pending: DGX Spark feasibility study | T01 | Fingerprint receipt per machine (R-001, amended 0.3.1); throughput at T10. The P0 Spark throughput smoke test is replaced by that fingerprint (Q4) |
| GD-1 | v0.3 | GRPO whole-group drop and group-drop tracking | T04 | A group with a quarantined member is dropped whole from the gradient update, not masked. Rows are held only for triage and receipts and never re-enter. Rate logged per checkpoint and per prompt. Halt pauses P3 for triage instead of resampling. A prompt dropped repeatedly goes to human triage. Prerequisite of T10 |
| T10 | v0.2 | Training path P1-P3 (ADR-0002, accepted 2026-10-17 7:40 PM PT) | T08,T09,GD-1,A2-PATH,EVAL-SO | One pinned run and exit-gate result per phase. P3 reward is the ADR-0006 grader with the Q1 binary ruling, whole-group drop, and A2-T as the only auto-attribution path. P3 exit gate: graded/ungraded split reported; A7 quarantine rate and group-drop rate within pre-registered limits; no frozen auto-attribution signature at exit. Only the ~5M-token CPT-skip threshold is ratified. The 2-point loss and compile@10 noise are paired-CI tests |
| T11 | v0.3 | Independent DSP evaluation | T10,T04 | Paired metrics and regression results |
| T12 | v0.3 | Promotion decision | T11 | Human review and decision record |
| T13 | v0.4 | Local serving API | T12 | Contract tests |
| T14 | v0.4 | IDE integration | T13 | End-to-end journey tests |
| T15 | v1.0 | Security and quality review | T14 | Independent audit |
| T16 | v1.0 | Release | T15 | Signed release manifest and rollback test |
| T17 | v0.3 | Language-backend lane (ADR-0004) | T03 | cpp, c, rust, cmajor output compiles and matches host render |
| T18 | v0.3 | Plugin lane: CLAP, VST3, LV2 (ADR-0004) | T04 | Validators and parameter-map check on good and bad fixtures |
| T19 | v0.3 | Embedded lane: Daisy, Teensy 4.x (ADR-0004) | T04 | Builds, memory and CPU budgets, real-time checks |
| T20 | v0.3 | Remix tasks and novelty metric | T08 | Remix dev tasks; novelty reported, not gated |
| T21 | v0.3 | Real-time safety checks | T04 | Bad fixtures rejected on every lane |
| T22 | v0.5-fpga | FPGA F0 spike | T04 | DecisionRecord on the lowering path |
| L1 | v0.3 | DONE in #49: RangeError is stack overflow only for the exact message "Maximum call stack size exceeded" | T03 | Landed in #49 (`f0fcdf9`) on main that includes #46 (`42ee1e4`). Prerequisite for A2-T leaving shadow, already met |
| L2 | v0.3 | DONE in #49: line-start matching on the failing stage, split on newline only | T03 | Landed in #49. This is the r5 L2 fix Jev cited: `_compile_stack_line` splits on `\n` only. Prerequisite for A2-T leaving shadow, already met |
| L3 | v0.3 | Rerun hooks for exits 124 and 125 on compile and render | T03 | Hooks feed A2-T in shadow only (r5 L3). Not quarantine-age tracking. Prerequisite for A2-T leaving shadow. Not landed |
| A7-S | v0.3 | Per-signature attribution-rate tracking, auto-freeze, resolved_by auto, stored evidence | T03 | Provisional thresholds: 20% share, 2× rise, 500-sample window. Distinct from A7's 1%, 500-sample and 2× alarm. Reviewed against shadow data before A2-T goes live. A gold-canary crash freezes its signature. Prerequisite of A2-T |
| A2-T | v0.3 | A2-T shadow mode, then live auto-attribution | L1,L2,L3,A7-S,CANARY | Shadow logs attributions and does not attribute. Shadow mode runs on a separate path that never grades: it may rerun and log attributions, but its output never reaches `reward_value` or a receipt. That path is not a training caller, so needing reruns in shadow does not conflict with A2-PATH. Leaves shadow only when L1–L3 have landed, agreement with human triage is on a sample fixed before shadow starts, the gold canary is clean and any crash there freezes its signature, A7-S thresholds are reviewed, and the go-live is recorded. Crash rows below ~0.1% keep auto-attribution off entirely. That rate is a reason to stay off, never a reason to go live |
| A2-PATH | v0.3 | CODE DONE in #51, live wiring pending: Do not supply the replaced rerun-plus-fixture path | T03 | Until A2-T is live, no training caller supplies `rerun` or `known_good`. `runtime_stack_overflow` and `wasm_trap` stay ungraded without a matching native Faust 2.88.0 failure. Source-class list alone only for a line-start Faust `ERROR` other than `ERROR : stack overflow` (plain or `in eval`; see EVAL-SO), a source over 1 MiB, and a remote import. Shadow mode runs on a separate path that never grades: it may rerun and log attributions, but its output never reaches `reward_value` or a receipt. That path is not a training caller, so needing reruns in shadow does not conflict with A2-PATH. Prerequisite of T10 |
| CANARY | v0.3 | Scheduled gold canary: dev-suite references, cleared-corpus sample, SFT targets, run on a schedule | T04 | A2-T go-live condition: the canary is clean. Any crash there freezes its signature through A7-S. Prerequisite of A2-T |
| EVAL-SO | v0.3 | CODE DONE in #51, live wiring pending: Grader must not tag stack-overflow lines as source without a native match | T03 | After #46 the compiler stores the exact line `ERROR : stack overflow in eval` as exit 126 internal. Acceptance: the grader no longer tags either line as source without the Faust 2.88.0 native match. That is the A2-PATH requirement for the plain line-start `ERROR : stack overflow` and for `ERROR : stack overflow in eval`. Prerequisite of T10 |
| H2 | v0.2 | H2 (brief: canonical ID/NUM shingle stream; ADVERSARY PR39 r6 adds: keep `lib.fn` qualified names, same 1/2 rule). A second shingle stream with identifiers → `ID` and numbers → `NUM`. The `STR` collapse applies only on this canonical stream. That stream is an extra stream combined with the raw stream by OR and never replaces the raw stream. ADVERSARY r6 addition; not ruled by Jev: `lib.fn`, the 1/2 rule, and the `STR` collapse | T06 | the r6 H2 probe at k = 5, 6, 8 (probe39r6.py 2b) is quarantined. k = 7 was never run. Prerequisite of FLOOR. Jev's output cites H2 and H3 from the brief and does not rule the r6 additions |
| H3 | v0.2 | H3 (brief: NFKC and drop Cf/Cc). Unicode normalization before tokenizing: NFKC and drop category Cf/Cc. The brief's H3 case is the U+200B evasion. ADVERSARY r6 addition; not ruled by Jev: the literal-insertion probe is not an H3 requirement, and the `STR` collapse is not H3 | T06 | Acceptance: the r6 U+200B probe is quarantined. The r6 literal-insertion probe (rev 0.367) is reported and is not an H3 gate, because collapsing to `STR` does not restore 5-gram overlap. Prerequisite of FLOOR |
| FLOOR | v0.2 | TOKEN_FLOOR measurement protocol | T06,H2,H3 | Real slicer and real cleared hosts, including H1-style splitting of one rejected file across 3 or more cleared files. Per-bucket recall with Wilson intervals and hand-labelled FP cost. Danny sets the recall lower bound, zero reject-class copies left in cleared, and the FP blob budget before the run. Spans under 15 tokens stay on exact hash on the ID/NUM stream, and that check needs the brief's idioms allowlisted pairing, or short idioms will be over-flagged. The shipped dedup must use the same streams the FLOOR protocol measures: the raw stream, plus the H2 canonical stream combined with it by OR. The `STR` collapse is only on that canonical stream and never replaces the raw stream. ADVERSARY confirms containment and allowlist fixes on the shipping slicer path. Bounds ratified 2026-10-18 (D6, spec §25). Reviewer rulings (rights calls delegated to Boof): needs_human sources count as reject-class until a human clears them (fail closed); a copy that only a lower floor detects counts as a recall miss for the higher floors. |

Proposed T06/T07 requirement (D-013, Danny yes 2026-10-17 1:04 PM PT): an n-gram or AST near-duplicate filter on generated `.dsp` against the training-only set. The threshold is not set. Impulse-test paths already cannot take `eval`.

T04 follow-up (N6, Danny yes 2026-10-17): `nonlinear-suite-v1` is an eight-stimulus float32 suite at the 144000-frame floor. The signed sample check is the gate. THD+N, IMD and the Farina inverse filter are diagnostics. The suite is not in `REWARD_PROFILES`. TaskSpec `effect` is a closed enum; only `linear` and `time_invariant` are rewardable. `require_task_rewardable` is called by `dataset_reward_row` and `rl_batch` (D5). `nonlinear-suite-fallback-v1` is the four-stimulus fallback. x86 DSP-bank goldens are committed. The ARM compare is pending on the DGX Spark.

Lane issues (ADR-0004): T17 #25, T18 #26, T19 #27, T20 #28, T21 #29, T22 #30.

Follow-ups from the 2026-10-17 7:40 PM PT amendment (Jev): L1 and L2 are done (#49, on main with #46). A2-PATH and EVAL-SO are done in code (#51) and wait on live reward-path wiring. Still TODO: L3, A7-S, CANARY, A2-T, GD-1, H2, H3 and FLOOR. A7-S and CANARY precede A2-T. GD-1, A2-PATH and EVAL-SO precede T10. H2 and H3 precede FLOOR. Crash rows below ~0.1% keep auto-attribution off. That rate is not a reason to go live.

## Decisions

Mirrors the decision items on the [project board](https://github.com/orgs/Zero-State-LLC/projects/29). Log: [spec §18](specs/001-faustcoder/spec.md#18-decision-log).

| ID | Decision | Status | Record |
|---|---|---|---|
| LIC-001 | Split license: Apache-2.0 for specs/ and docs/, Zero State proprietary for the rest | Done (ACCEPTED 2026-10-16) | ADR-0003, #20 |
| D-003 | Sample rates 44.1 and 48 kHz (runtime clause superseded by D-003r2) | ACCEPTED 2026-10-16 | spec §14 |
| D-004 | Corpus allowlist; GPL training-only; unlicensed excluded | ACCEPTED 2026-10-16 | ADR-0003 |
| D-006 | Teacher: Opus via OpenRouter, per-run spend cap | SUPERSEDED 2026-10-16 22:25 PT | ADR-0002 |
| D-006r2 | Teacher: open-weight deepseek-v4.1-flash via OpenRouter, per-run cap; Opus for review and judging only | ACCEPTED 2026-10-16 | ADR-0002, ADR-0003 |
| ORG-001 | Repo moved to Zero-State-LLC; repo and board public for now (revisitable) | Done 2026-10-16 22:32 PT | spec §18 |
| D-003r2 | Runtimes: wasm for eval, native C++ 2.88.0 cross-check, target lanes | ACCEPTED 2026-10-16 23:39 PT | spec §14, ADR-0004 |
| D-007 | Per-function licensing; header-less files inherit repo license; AGPL excluded | ACCEPTED 2026-10-16 23:39 PT | ADR-0003 |
| D-008 | First boards Daisy and Teensy 4.x; no purchase yet | ACCEPTED 2026-10-16 23:39 PT | ADR-0004 |
| D-009 | FPGA path after F0 spike; iCE40 and ECP5; audio-rate throughput | ACCEPTED 2026-10-16 23:39 PT | ADR-0004 |
| D-010 | Remix novelty is a dev metric; faust-rs primitives out | ACCEPTED 2026-10-16 23:39 PT | ADR-0004 |
| D-011 | Upstream Faust fixes under LGPL allowed | ACCEPTED 2026-10-16 23:39 PT | ADR-0003 |
| D-012 | Plugin formats CLAP, VST3 (clap-wrapper), LV2; AU deferred | ACCEPTED 2026-10-16 23:39 PT | ADR-0004 |
| ORG-002 | Board moved to org project 29; user board 8 kept, marked superseded | Done 2026-10-16 | spec §18 |
| R-001 | v0.2 evidence: cited external Spark benchmarks plus a per-machine fingerprint; throughput is T10 on the cleared dedicated Spark | ACCEPTED 2026-10-17 12:54 PM PT | spec §20 |
| D-013 | STK-4.3 permissive with notice; bare BSD not redistributed; notice required; vendored copies deduped; per-function slicing; strictest license; copyleft near-duplicate gate proposed for T06/T07 | ACCEPTED 2026-10-17 1:04 PM PT | spec §22, ADR-0003 |
| ADR-0006 | Source-attributable failures graded at parse_error; env/harness errors (reproducible infra failures and deterministic harness defects) ungraded + quarantined; A1–A7 (A7 numbers provisional). A2 extended 2026-10-17 4:28 PM PT (Danny): untraced timeouts/crashes quarantined. In force in reward code (`grade_receipt`, spec §23) | ACCEPTED 2026-10-17 4:11 PM PT (Danny) | docs/adr/0006, spec §23 |
| Q1 | Binary P3 reward; whole-group drop; ladder is a logged diagnostic; binary-vs-ladder ablation | ACCEPTED 2026-10-17 7:40 PM PT (Jev; Danny "use jev to make decisions" 7:37 PM PT) | docs/adr/0006, spec §24 verbatim |
| Q2 | Auto-attribution only as A2-T after shadow; below ~0.1% stays off; L3 is rerun hooks | ACCEPTED 2026-10-17 7:40 PM PT (Jev; Danny "use jev to make decisions" 7:37 PM PT) | docs/adr/0006, spec §24 verbatim |
| Q3 | TOKEN_FLOOR stays 40 and provisional; protocol after H2/H3 | ACCEPTED 2026-10-17; bounds ratified 2026-10-18 12:34 AM PT; value still provisional | docs/adr/0002, spec §24 verbatim |
| Q4 | ADR-0002 accepted in full (Jev's default; Danny may still choose P3 PROPOSED); only the ~5M-token threshold ratified | ACCEPTED 2026-10-17 7:40 PM PT (Jev; Danny "use jev to make decisions" 7:37 PM PT) | docs/adr/0002, spec §24 verbatim |

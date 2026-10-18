# ADR-0002: Training path

Status: ACCEPTED (2026-10-17 7:40 PM PT, with amendments)

Amended 2026-10-16 by [ADR-0004](0004-target-lanes-and-faust-tooling.md) (Danny yes 2026-10-16 23:39 PT): the P0 harness is built from faustwasm, and target lanes run beside P1 to P3.

Date: 2026-10-16. Evidence: [research.md](../../specs/001-faustcoder/research.md).

## Context

- FaustCoder is a small specialist model for writing Faust DSP code; the
  owner wants a path measured in weeks, not months. OBSERVED (owner brief).
- "Pretraining" means continued, domain-adaptive pretraining of an existing
  open code model. Training a model from scratch is out of scope. OBSERVED
  (owner brief).
- The official Faust corpus is about 1.4M tokens; licensable GitHub code may add
  a few million more. OBSERVED / SPECULATIVE (research F9, F12).
- On low-resource languages, more natural code helps little, while
  test-validated synthetic data and RL on execution feedback help a lot.
  OBSERVED (research F1, F5, F6).

## Decision

Adapt an open base code model in four gated phases. Each phase has a timebox
and an exit gate. A phase that misses its gate is either dropped (P1) or
re-planned through a decision record; it is never silently extended.

1. **Pick an open base code model.** Apache-2.0 only by default. Shortlist:
   Qwen2.5-Coder-1.5B and -7B, Qwen3.5-4B-Base, Qwen3-4B-Base (research,
   "Base-model shortlist"). Iterate on 1.5B; repeat the winning recipe on one
   4B to 7B model.
2. **P0 — corpus and evaluation harness** (timebox 2 weeks).
   - Build: rights inventory with a permissive-license allowlist, normalized
     and deduplicated corpus with digests, sandboxed compiler harness, signal
     test harness (SUPERSEDED wording; per ADR-0004 both wrap faustwasm with a
     native Faust 2.88.0 cross-check), a dev suite (about 200 tasks) and a sealed holdout of newly
     written tasks (about 100), and one Spark throughput smoke test.
   - Exit gate: another operator reproduces compiler receipts and baseline
     compile@k and pass@k (with confidence intervals) for every shortlisted
     model from a clean checkout, and known-bad fixtures fail the gates.
3. **P1 — continued pretraining on the Faust corpus** (timebox 3 days).
   - Skip rule, decided before any run: if the license-cleared, deduplicated
     Faust corpus is under about 5M tokens (INFERRED threshold), skip P1 and
     feed the raw files into P2 as completion and fill-in-the-middle examples.
     Justification: at that size CPT gave little or negative gain in prior
     work (research F1, F3), and the same tokens are still used in P2.
   - Otherwise run full-parameter CPT (up to about 4B) or LoRA rank 256 (7B)
     with an equal share of general-code replay, at most 2 epochs.
   - Exit gate: the CPT model beats its base on held-out Faust perplexity and
     on dev compile@10, with a paired confidence interval that excludes zero,
     and loses no more than 2 points (INFERRED) on a general-code check. If it
     fails, continue from the base model; the run is recorded, not deleted.
4. **P2 — supervised fine-tuning** (timebox 1.5 weeks).
   - Data: stdlib usage-block pairs, examples, compiler- and signal-validated
     synthetic tasks, and synthetic repair pairs (break a correct program,
     record diagnostics, train the fix). Only validated items enter the set.
   - Method: LoRA rank 64 to 256 with alpha = 2r, or full fine-tuning for
     small models.
   - Exit gate: dev compile@1 and pass@1 beat the better of base and P1 with
     a paired confidence interval excluding zero; abstention and bounded
     repair work.
5. **P3 — compiler-feedback RL** (timebox 2 weeks).
   - GRPO with reward from the sandboxed compiler plus signal tests; repair
     episodes bounded by `max_repair_attempts`.
   - Exit gate: dev pass@1 beats P2 with a paired confidence interval
     excluding zero; compile@10 does not drop beyond noise; a reward-hacking
     audit (silence, DC, NaN, trivial programs) finds nothing.
6. After P3, the sealed holdout is run once and the result goes into a
   `DecisionRecord` (spec §7.3, §7.4).

## Accepted inputs

Provenance: Danny yes 2026-10-16 22:20 PT. Recorded in [spec §18](../../specs/001-faustcoder/spec.md#18-decision-log).

- D-003: signal tests, task suites and RL rewards run at 44.1 kHz and 48 kHz.
- D-003r2 (Danny yes 2026-10-16 23:39 PT): rendering for evaluation and rewards uses faustwasm; the
  native C++ backend of Faust 2.88.0 cross-checks it (ADR-0004). Supersedes the
  open-runtimes clause of D-003.
- D-007 to D-012 (Danny yes 2026-10-16 23:39 PT): see [spec §14](../../specs/001-faustcoder/spec.md#14-open-decisions). Target-lane results may join the P3 reward once each lane exists (R-016).
- D-004: the P0 rights inventory applies the allowlist in
  [ADR-0003](0003-licensing-and-data-rights.md). GPL sources are
  training-only and are kept outside the repository and released data;
  unlicensed sources are excluded.
- D-006 (SUPERSEDED by D-006r2, Danny yes 2026-10-16 22:25 PT): P2 synthetic data uses Opus via OpenRouter as the teacher. Each
  generation run needs its own approved spend cap before it starts, and the
  receipt records the cap and the actual spend. Sealed holdout tasks are never
  sent to the teacher (INFERRED, from spec §9).
- D-006r2 (Danny yes 2026-10-16 22:25 PT): P2 synthetic data and repair targets come from an
  open-weight teacher, by default `deepseek/deepseek-v4.1-flash` via
  OpenRouter with high reasoning effort (DeepSeek-V4.1-Flash, MIT license,
  OBSERVED on Hugging Face 2026-10-16). Each run needs its own approved spend
  cap; the receipt records model id, reasoning setting, cap and actual spend.
  Opus via OpenRouter is used only for review, grading and eval judging and is
  never a source of training targets, because Anthropic's usage terms restrict
  training competing models on its outputs. Judge scores never replace the
  compiler and signal-test gates (R-011, R-016). The holdout rule above still
  applies to both models.

## Consequences

- Expected total: about 4 to 6 weeks and 60 to 150 DGX Spark hours; compute
  is cheap (about $10 to $15 of electricity), engineering time dominates.
  INFERRED.
- The compiler and signal harnesses are the critical path: they validate
  synthetic data, score evaluations and supply the RL reward.
- Typed signal-flow graph analysis (spec §4.2), IDE integration, and the
  serving API move after P3 (spec §17).
- Teacher-model use follows D-006r2 (open-weight teacher, per-run spend cap); corpus licenses follow
  D-004 (ADR-0003).

## Alternatives considered

- Larger students (14B, 30B MoE): rejected for the student; they conflict with
  the small-model goal and fine-tuning gains shrink with size on scarce data
  (research F3). The teacher is fixed by D-006r2.
- Prompting only (few-shot or retrieval, no training): kept as the P0 baseline
  that every phase must beat.
- LoRA-only for every phase: rejected for CPT on small models (research F4).

## Amendment 2026-10-17 7:40 PM PT (Q1, Q2, Q3, Q4)

Jev output sha256 `d9a4632ed29786182ee61e67b7c3a6b1df92c8468f011b8e1331b54e794264df`, run 2026-10-17 7:40 PM PT, authorized by Danny's instruction "use jev to make decisions" (2026-10-17 7:37 PM PT). Record: [jev-output-2026-10-17.txt](../decisions/jev-output-2026-10-17.txt). The fenced blocks are the ruling, copied verbatim from that file. A paraphrase of them is non-normative. The application sentences restate gates from those blocks and do not loosen them. If an application sentence and a fenced block ever diverge, the fenced block wins. This record does not change code.

This section accepts ADR-0002. It does not replace the sections above.
Q4 requires this amendment to cite the Q1–Q3 rulings verbatim. Those
rulings, and Q4, are the fenced blocks. Q1 and Q2 application also lives
in [ADR-0006](0006-source-attributable-failures.md). The same sentences
are repeated here so this amendment does not depend on a paraphrase.

### Q1 Jev ruling (verbatim)

```text
DECISION: MODIFIED: "P3 reward is binary: 1.0 on full pass, 0.0 on every graded failure including A1's lowest rung. Ungraded samples get no value. Any GRPO group containing a quarantined member is dropped whole from the gradient update, not masked. Its rows are held only for triage and receipts and never re-enter training later. Group-drop rate is tracked per prompt and overall with a halt threshold. The R-005 ladder is a logged diagnostic only, and R-005's wording is amended to say so. A graded reward may enter only via the pre-registered binary-vs-ladder ablation."
```

```text
CONDITIONS:
- C1 is preserved: no ungraded or quarantined row ever contributes a reward value or an advantage, including through group normalization.
- Log group-drop rate per checkpoint and per prompt. If the overall rate exceeds an agreed limit, pause P3 for triage instead of resampling indefinitely. Any prompt dropped repeatedly goes to human triage.
- Log the zero-variance (all-0 or all-1) group rate after SFT. The ε two-level variant is tested only through the ablation, and only if that rate approaches the brief's ~70% trigger.
- Pre-register the ablation's margin, seeds and dev metric before P3 starts. Treat any rise in quarantine or ungraded rate under the ladder arm as a failure of that arm.
- Amend R-005 in the same change set that records this ruling. This also clears ADR-0002 B1, together with Q4.
```

### Q1 application

Q1 CONDITIONS in the fenced block are binding. That includes C1 through group normalization; group-drop logged per checkpoint and per prompt; a halt that pauses P3 for triage instead of resampling indefinitely; human triage for a prompt dropped repeatedly; rows of a dropped group held only for triage and receipts; the zero-variance (all-0 or all-1) group rate logged after SFT; the ε two-level variant only through the ablation, and only if that rate approaches the brief's ~70% trigger; the ablation's margin, seeds and dev metric pre-registered before P3 starts; and any rise in quarantine or ungraded rate under the ladder arm as a failure of that arm.

OBSERVED: `reward_value` in `faustcoder/reward/grader.py` already returns 1.0 for a graded pass, 0.0 for a graded failure including an A1 source failure, and no value for an ungraded sample. This record does not change that function.

### Q2 Jev ruling (verbatim)

```text
DECISION: MODIFIED: "Auto-attribution under A2 is allowed only as A2-T, and only after a shadow period. A2-T requires all of the following:
- ≥2 reruns on a quiet worker reproducing the same crash signature;
- both the trivial and a path-matched known-good fixture passing;
- for stack, wasm_trap, timeout and other harness-limit signatures, a matching native Faust 2.88.0 failure (source-class list alone suffices only for inherently source-side signatures: line-start Faust ERROR, >1 MiB source, remote import);
- the signature not frozen by A7-S.

Every auto-attribution is stored with resolved_by=auto and its evidence. Anything else stays ungraded and quarantined."
```

```text
CONDITIONS:
- Shadow mode first: A2-T computes and logs attributions, but humans triage until A2-T agrees with them on an agreed sample and the gold canary is clean.
- If shadow data shows crash rows below ~0.1% of samples, keep auto-attribution off entirely, following the brief's own fallback.
- If native cross-check is unavailable in the loop, harness-limit signatures stay ungraded. The source-class-only fallback is narrowed to the inherently source-side signatures.
- Exit 124 is attributed only with a native or independent-runner timeout at the same limit, not on fixture evidence alone.
- Gold canary (dev-suite references, cleared-corpus sample, SFT targets) runs on a schedule. Any crash there freezes its signature.
- Land the r5 L1 fix (RangeError restricted to stack overflow), the L2 fix (line-start matching on the failing stage) and the L3 fix (rerun hooks for 124 and 125) before A2-T leaves shadow.
- A7-S thresholds (20% share, 2× rise, 500-sample window) are provisional. They are reviewed against shadow data before going live.
```

### Q2 application

Until A2-T leaves shadow mode, no receipt is auto-attributed to the source. The §23 rerun-plus-trivial-fixture path is not sanctioned by Q2 and must not be supplied (`rerun`/`known_good`) by any training caller. A `runtime_stack_overflow` flag or `wasm_trap` kind attributes to the source only with a matching native Faust 2.88.0 failure. Until then those rows are ungraded and quarantined. The source-class list alone suffices only for a line-start Faust `ERROR` other than `ERROR : stack overflow` (plain or `in eval`; see EVAL-SO), a source over 1 MiB, and a remote import. Shadow mode runs on a separate path that never grades: it may rerun and log attributions, but its output never reaches `reward_value` or a receipt. That path is not a training caller, so needing reruns in shadow does not conflict with A2-PATH. Code follow-up: A2-PATH.

A2-T requires all of: (1) at least 2 reruns on a quiet worker with matching environment digests reproducing the same crash signature; (2) both the trivial known-good fixture and a path-matched known-good fixture (same stage and limit) passing in that environment; (3) for stack, wasm_trap, timeout and every other harness-limit signature, a matching native Faust 2.88.0 failure. If that cross-check is unavailable, the row stays ungraded. (4) The signature is not frozen by A7-S. Exit 124 is attributed only with a native or independent-runner timeout at the same limit, never on fixture evidence alone. Anything else stays ungraded and quarantined.

A2-T leaves shadow only when all hold: L1–L3 have landed; A2-T agrees with human triage on a sample size and agreement level fixed before shadow starts; the scheduled gold canary (dev-suite references, cleared-corpus sample, SFT targets) is clean, and any crash there freezes its signature; the A7-S thresholds have been reviewed against shadow data; and Danny (or the delegated decision process) records the go-live. If shadow data shows crash rows below about 0.1% of samples, auto-attribution stays off entirely. That rate is a reason to stay off, never a reason to go live.

L3. Rerun hooks for exits 124 and 125 on the compile and render stages (r5 L3), feeding A2-T in shadow only.

L1 and L2 have landed in #49 (`f0fcdf9`), on main that also includes #46 (`42ee1e4`). L1 is the r5 fix Jev cited: a RangeError counts as stack overflow only when its message is exactly `Maximum call stack size exceeded`. L2 is the r5 fix Jev cited as line-start matching on the failing stage: `_compile_stack_line` splits on `\n` only. L3 has not landed.

A7-S thresholds (20% share, 2× rise, 500-sample window) are provisional. They are reviewed against shadow data before going live. These numbers are not A7's 1%, 500-sample and 2× ungraded-rate alarm.

After #46, the compiler stores a line that is exactly `ERROR : stack overflow in eval` as exit 126 `internal`. The grader's `_COMPILE_STACK_LINES` still tags that line as source, with no native check. EVAL-SO's acceptance is the A2-PATH requirement: the grader no longer tags either line as source without the Faust 2.88.0 native match. That covers `ERROR : stack overflow in eval` and the plain line-start `ERROR : stack overflow`.

### Q3 Jev ruling (verbatim)

```text
DECISION: MODIFIED: "TOKEN_FLOOR stays 40 and provisional. It is accepted or changed only by the measured protocol in Q3, extended as follows:
- the protocol uses the real slicer and real cleared hosts, with mutation operators that include H1-style splitting of one rejected file across 3+ cleared files;
- it reports per-bucket recall with Wilson CIs and hand-labelled FP cost;
- it runs after H2/H3 land;
- spans under 15 tokens remain checked by exact hash on the canonical stream, with their reject-class count reported.

The containment and allowlist preconditions are confirmed by ADVERSARY against the shipping slicer path, not only whole-file code. T07 does not freeze its split on the provisional floor without a recorded leakage caveat and a scheduled re-check."
```

```text
CONDITIONS:
- C2 is binding: no acceptance of 40, or any other value, until containment and allowlist-bypass fixes are confirmed on the slicing path and the measured analysis passes.
- Danny sets the acceptance numbers before the run: recall lower bound, zero reject-class copies left in cleared, and FP blob budget.
- If only the 20–39 bucket fails at 40, a function-unit-only lower floor is allowed. Whole files keep 40.
- Use SemDeDup-style semantic similarity only as an advisory T07 leakage signal, never as a clearance criterion.
- If T07 freezes on the provisional floor, holdout novelty is re-checked when the floor is accepted. Any leaked items are removed and the removal is logged.
```

### Q3 application

The protocol runs only after H2 and H3 land. H2 (brief: canonical ID/NUM shingle stream; ADVERSARY PR39 r6 adds: keep `lib.fn` qualified names, same 1/2 rule). H3 (brief: NFKC and drop Cf/Cc; ADVERSARY PR39 r6 adds: string literals collapse to one `STR` token on the canonical stream). The r6 additions are ADVERSARY recommendations, not Jev rulings. ADVERSARY r6 addition; not ruled by Jev: `lib.fn`, the 1/2 rule, the `STR` collapse, and the literal-insertion probe. The `STR` collapse applies only on the H2 canonical stream. That stream is an extra stream combined with the raw stream by OR and never replaces the raw stream. The shipped dedup must use the same streams the FLOOR protocol measures. Before the run, Danny sets the recall lower bound, requires zero reject-class copies left in cleared, and sets the FP blob budget. Recall is per bucket with Wilson intervals, with hand-labelled FP cost. Sub-15-token spans are exact-hash checked on the ID/NUM stream, and that check needs the brief's idioms allowlisted pairing, or short idioms will be over-flagged. A T07 freeze on the provisional floor records a leakage caveat and a scheduled re-check. Leaked items found later are removed and the removal is logged. SemDeDup-style similarity is advisory for T07 only and never a clearance criterion.

If only the 20–39 bucket fails at 40, a function-unit-only lower floor is allowed. Whole files keep 40.

No ADR text here accepts `TOKEN_FLOOR`. The value stays provisional
until the Q3 protocol accepts or changes it.

#### FLOOR bounds (D6, ratified 2026-10-18)

Danny ratified these bounds on 2026-10-18 12:34 AM PT ("continue as recommended", 5% FP budget). Record: [danny-floor-bounds-2026-10-18.md](../decisions/danny-floor-bounds-2026-10-18.md). Constants: [`faustcoder/floor_protocol.py`](../../faustcoder/floor_protocol.py). This discharges the Q3 condition that the recall lower bound, the zero reject-class rule, and the FP blob budget are set before the run. The value stays 40 and provisional.

> FLOOR acceptance bounds (ratified by Danny 2026-10-18 12:34 AM PT, "continue as recommended", 5% FP budget):
>
> 1. Recall: in each of 8 gated cells, which are 4 buckets (15-19, 20-29, 30-39 and 40+ tokens) times verbatim on the raw stream and consistent rename on the canonical stream, the 95% Wilson lower bound must be at least 0.90. Other operators are reported, not gated.
> 2. n = 100 planted items per cell, from at least 50 distinct real reject-class span windows, each planted in 2 cleared hosts in different repos. That tolerates at most 4 misses per cell. Every planted miss is inspected, and a miss with a recurring mechanism blocks until fixed.
> 3. FP budget B = ceil(0.05 × N_cleared), which is 25 at N_cleared = 491. It counts hand-confirmed non-copy blobs (idiom, boilerplate, header, import, numeric table) added beyond the floor-40 set, after declare-stripping and the idioms allowlist. Label every candidate if a floor adds 100 or fewer. Otherwise use a seeded sample of at least 50 and require Wilson-upper(FP share) × added ≤ B.
> 4. At the chosen floor, three counts must be zero: detected reject-class matches left unquarantined in cleared, unresolved sub-15 exact-hash hits on the ID/NUM stream, and H1 split-file union-coverage hits at 1/2 or more.
> 5. Choose the highest TOKEN_FLOOR in {40, 30, 20} that passes 1, 3 and 4. If only the 20-29 and 30-39 cells fail at 40, use a function-unit-only lower floor, and whole files keep 40.
>
> TOKEN_FLOOR stays 40 and provisional until the FLOOR run applies these bounds.

The figure of at most 4 misses at n = 100 depends on a two-sided Wilson interval with z = 1.96 and no continuity correction.

Separate recorded rights ruling, not part of D6 and not Danny's ratified text: needs_human sources count as reject-class until a human clears them (fail closed). Boof (orchestrator), rights call under Danny's 2026-10-17 BlackDog rights/licensing delegation ([rights-inventory.md](../rights-inventory.md) lines 21-22), 2026-10-18 ~12:57 AM PT.

Ruling on lower-floor detections, recorded at spec 0.3.8. This replaces the open question. Record: [FLOOR-ruling-b-recommendation-2026-10-18.md](../decisions/FLOOR-ruling-b-recommendation-2026-10-18.md).

> Ruling on lower-floor detections (Danny, 2026-10-18 2:27 AM PT, "continue as recommended"; record: FLOOR-ruling-b-recommendation-2026-10-18.md). This interprets the ratified D6 bounds and does not change their text or numbers.
>
> 1. Ground truth for the FLOOR run is fixed before scoring and does not depend on TOKEN_FLOOR. The same gold set is used for 40, 30 and 20.
> 2. Planted items: every planted item is a positive at every candidate floor. A planted item that a floor misses is a miss in that floor's cell, whatever its length. No item leaves a cell's denominator because it is shorter than the floor. Cells stay at n = 100 planted items.
> 3. Natural copies: the candidate pool is the union of everything flagged at floors 40, 30 and 20, by the sub-15 exact-hash check, and by the H1 union-coverage check, on the shipping path. Each candidate is adjudicated once, on content, as COPY or NOT_COPY of reject-class text (rights_rejected, or needs_human until cleared), with a 15-token minimum and without regard to which floor flagged it. The adjudicated set is frozen before any floor is scored. Natural copies do not enter the Wilson cells.
> 4. Item 4's first count ("detected reject-class matches left unquarantined in cleared") counts, at floor F, every adjudicated COPY and every unadjudicated candidate that F's own shipping pipeline leaves in cleared. A copy that only a lower floor detects therefore fails item 4 at every higher floor that leaves it in cleared.
> 5. Only quarantines produced by F's shipping pipeline count for F. Manual quarantine pins may be applied for corpus hygiene but do not make F pass.
> 6. Every natural miss is inspected and recorded with its mechanism. Per-floor natural recall (detected / adjudicated COPY) is reported and not gated, and the report states that the pool comes from the detectors themselves.

Recommendation from the record, not Danny's ruling and not a clause of the ruling above. "The mitigation is to adjudicate before scoring, and to require a second reviewer for any item whose label decides the floor." "Record which floor flagged each item separately, and require a second reviewer for any floor-deciding item." For SClarinet: "Use two reviewers and record both."

### Q4 Jev ruling (verbatim)

```text
DECISION: MODIFIED: "Accept ADR-0002 with an amendment block that:
- (a) makes P3's reward the ADR-0006 grader with the Q1 binary ruling, whole-group drop of quarantined groups, and A2-T (Q2) as the only auto-attribution path;
- (b) replaces the P0 Spark throughput smoke test with R-001 0.3.1 (fingerprint receipt; throughput at T10);
- (c) requires P0 to exit with TOKEN_FLOOR either accepted by the Q3 protocol or marked provisional with a leakage caveat, and requires holdout novelty to be re-checked once the floor is accepted, before any P3 exit claim rests on the holdout;
- (d) adds graded/ungraded split, A7 quarantine and group-drop rates within limits, and no frozen auto-attribution signature at exit to the P3 audit;
- (e) defines compile@10 'does not drop beyond noise' and the 2-point general-code loss as paired-CI tests.

The ~5M-token CPT-skip threshold is ratified as written. Spec §17, the CHANGELOG and the P0 inline note are updated on acceptance."
```

```text
CONDITIONS:
- The amendment block cites the Q1–Q3 rulings verbatim so later readers cannot reinterpret them.
- If Danny prefers, P0–P2 may be accepted now with P3 marked PROPOSED pending A2-T leaving shadow mode. Both paths are acceptable.
- No ADR text may imply TOKEN_FLOOR is accepted (C2).
- P0 completion items (T07/T08, base-model shortlist) are not acceptance blockers but remain exit-gate items.
```

### Q4 application

Full acceptance of ADR-0002, including P3, is Jev's default; Danny may still choose P3 PROPOSED. Jev's Q4 CONDITIONS say that if Danny prefers, P0–P2 may be accepted now with P3 marked PROPOSED pending A2-T leaving shadow mode, and that both paths are acceptable. This record takes full acceptance.

P3's reward is the ADR-0006 grader with the Q1 binary ruling, whole-group
drop of quarantined groups, and A2-T (Q2) as the only auto-attribution
path.

The P0 build list above includes "one Spark throughput smoke test."
That item is replaced by R-001 0.3.1: a fingerprint receipt, with
throughput at T10 on the cleared dedicated Spark (spec §20).

The P3 exit gate also requires: the graded/ungraded split reported; the A7 quarantine rate and the group-drop rate within their pre-registered limits; no frozen auto-attribution signature at exit; audit disagreements = 0 unresolved; and the consumed log intact (D3 option H; the sampled audit is D3-H2, spec §26 0.3.9, before P3). P0 exits only with `TOKEN_FLOOR` accepted by the Q3 protocol or marked provisional with a recorded leakage caveat. No P3 exit claim may rest on the holdout until the holdout novelty re-check under the accepted floor has run.

The ~5M-token threshold in the P1 skip rule is ratified as written. No other INFERRED number is ratified.

The P1 clause "loses no more than 2 points (INFERRED) on a general-code
check" and the P3 clause "compile@10 does not drop beyond noise" are
paired confidence-interval tests. A raw 2-point cap is not a threshold.
An unquantified noise band is not a threshold.

P0 completion items (T07, T08, and the base-model shortlist) are not
acceptance blockers. They remain exit-gate items.

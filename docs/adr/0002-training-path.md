# ADR-0002: Training path

Status: PROPOSED

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
     test harness, a dev suite (about 200 tasks) and a sealed holdout of newly
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
- D-004: the P0 rights inventory applies the allowlist in
  [ADR-0003](0003-licensing-and-data-rights.md). GPL sources are
  training-only and are kept outside the repository and released data;
  unlicensed sources are excluded.
- D-006: P2 synthetic data uses Opus via OpenRouter as the teacher. Each
  generation run needs its own approved spend cap before it starts, and the
  receipt records the cap and the actual spend. Sealed holdout tasks are never
  sent to the teacher (INFERRED, from spec §9).

## Consequences

- Expected total: about 4 to 6 weeks and 60 to 150 DGX Spark hours; compute
  is cheap (about $10 to $15 of electricity), engineering time dominates.
  INFERRED.
- The compiler and signal harnesses are the critical path: they validate
  synthetic data, score evaluations and supply the RL reward.
- Typed signal-flow graph analysis (spec §4.2), IDE integration, and the
  serving API move after P3 (spec §17).
- Teacher-model use follows D-006 (per-run spend cap); corpus licenses follow
  D-004 (ADR-0003).

## Alternatives considered

- Larger students (14B, 30B MoE): rejected for the student; they conflict with
  the small-model goal and fine-tuning gains shrink with size on scarce data
  (research F3). The teacher is fixed by D-006.
- Prompting only (few-shot or retrieval, no training): kept as the P0 baseline
  that every phase must beat.
- LoRA-only for every phase: rejected for CPT on small models (research F4).

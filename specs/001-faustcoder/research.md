# Research: FaustCoder (spec 001)

- Date: 2026-10-16
- Plan: [plan.md](plan.md). Decision record: [ADR-0002](../../docs/adr/0002-training-path.md).
- Question: what is the fastest credible path to a **small** Faust code
  specialist, built by adapting an existing open code model (continued
  pretraining, then SFT, then compiler-feedback RL), never by training from
  scratch?

Evidence labels: **OBSERVED** (measured here or stated in a source that was
read), **INFERRED** (reasoned from observed facts), **SPECULATIVE** (plausible,
unverified), **NOT_COMPUTABLE** (no data). Papers marked "abstract" were read
only at abstract level.

## Method and sources

- Preprints and studies through the box Ask Science tool (OpenAlex) and arXiv
  abstract pages. The arXiv export API returned HTTP 429 for every query on
  2026-10-16, so arXiv papers were reached through OpenAlex DOIs and the
  arXiv HTML pages. OBSERVED.
- OpenAlex metadata was wrong for two records (the abstract for 2107.03374 and
  the title for 2402.03300); both were checked against arXiv. OBSERVED.
- Corpus size measured by cloning `grame-cncm/faustlibraries` and
  `grame-cncm/faust` (shallow, 2026-10-16). Base-model licenses read from the
  Hugging Face model API. Hardware numbers from NVIDIA docs and third-party
  reviews.

## Findings

| # | Finding | Label | Source |
|---|---|---|---|
| F1 | Further training a code model on *natural* low-resource-language code (Lua, OCaml, Racket) "barely" improved and sometimes reduced pass@1; test-validated semi-synthetic data gave large gains (for example Racket 4.7 to 11.3 on StarCoderBase-1B). Unvalidated synthetic data did not help. | OBSERVED (full text) | Cassano et al., arXiv:2308.09895 §3.1, §5.2, Table 9 |
| F2 | Deduplication cut a fine-tuning set from 1.4M to 48K items with the same pass@1 (17.1 vs 17.3) and training time from 12 h to under 30 min. | OBSERVED (full text) | arXiv:2308.09895 §5.4.4 |
| F3 | For low-resource languages, fine-tuning helped most for a ~1B model; at 33B, fine-tuning on scarce data *lowered* pass@1 while in-context examples helped. | OBSERVED (full text) | Giagnorio et al., arXiv:2501.19085 Table III |
| F4 | In continued pretraining, LoRA underperformed full fine-tuning at every rank tested; in instruction tuning, rank 256 with alpha = 2r matched full fine-tuning on code. LoRA forgets less. Authors recommend LoRA for instruction tuning, not continued pretraining. | OBSERVED (full text) | Biderman et al., arXiv:2405.09673 §4.1, §4.7 |
| F5 | GRPO drops PPO's critic and uses group-relative rewards, cutting memory. RL improved Maj@K but not Pass@K: it sharpens the distribution rather than adding capability. | OBSERVED (full text) | Shao et al., arXiv:2402.03300 §4.1, §5.2.2 |
| F6 | RL from compiler feedback and from execution feedback improve code models. | OBSERVED (abstract) | StepCoder arXiv:2402.01391; RLEF arXiv:2410.02089; CodeRL arXiv:2207.01780 |
| F7 | Qwen2.5-Coder comes in 0.5B to 32B and was itself built by continued pretraining on 5.5T tokens. | OBSERVED (abstract) | arXiv:2409.12186 |
| F8 | pass@k should be estimated with the unbiased estimator from n >= k samples. | OBSERVED | Chen et al., arXiv:2107.03374 (formula as restated in arXiv:2405.09673 App. F) |
| F9 | Official Faust sources (faustlibraries + faust repo), deduplicated by content, excluding Windows binaries named `.lib` and generated test files over 500 KB, are 854 `.dsp`/`.lib` files, 5.06 MB (3.3 MB of it faustlibraries), about 1.4M tokens at 3.5 bytes per token. | OBSERVED (size); INFERRED (token ratio) | Local measurement |
| F10 | `declare license` statements in those files: 115 BSD, 29 MIT, 14 STK-4.3, 17 LGPL variants (12 with a Faust exception), 2 GPL v3. 274 files mention no license at all. The faust compiler itself is GPL. | OBSERVED | Local measurement |
| F11 | faustlibraries has about 1,260 `#### Usage` blocks (documented functions); the faust repo has 272 example programs and 111 impulse-test programs with a `reference` output directory. | OBSERVED | Local measurement |
| F12 | GitHub lists 504 repositories whose primary language is Faust (392 non-fork over 10 KB). Of the 50 most-starred non-forks: 15 no license, 17 GPL/AGPL, 15 permissive (MIT, BSD-3, ISC, Apache), 3 unclear. | OBSERVED | GitHub search API, 2026-10-16 |
| F13 | DGX Spark: 128 GB unified memory, 273 GB/s, 240 W supply, about 160 W at the wall under GPU load. Founders Edition list price $4,699 since Feb 2026. | OBSERVED | NVIDIA docs; Tom's Hardware |
| F14 | NVIDIA's headline fine-tuning peaks are 82,739 tok/s (Llama 3.2 3B full) and 53,658 tok/s (Llama 3.1 8B LoRA); its own table, computed as tokens over total training time, gives 13,520 and 6,970 tok/s. Users running NVIDIA's 3B script report about 8k to 11.6k tok/s. | OBSERVED (reported) | NVIDIA technical blog; dgx-spark-playbooks issue #29 |

## Implications

- **I1. The Faust corpus is tiny.** Even with the licensable GitHub
  corpus added it is likely 2M to 10M tokens (SPECULATIVE until P0 measures it).
  Continued pretraining (CPT) on it costs hours, not days, so compute is not the
  reason to skip it; F1 is. CPT must earn its place with a measured gain.
  INFERRED.
- **I2. The real lever is validated synthetic data.** The compiler and the
  signal-test harness are the validator that MultiPL-T needed tests for (F1).
  Build them first; they also become the RL reward. INFERRED.
- **I3. Small models benefit most from fine-tuning** (F3), which supports the
  small-model goal. Start iteration on a 1.5B model (fast cycles), then repeat
  the winning recipe on a 4B to 7B model. INFERRED.
- **I4. Method per phase** (F4): full-parameter CPT for models up to about 4B
  (fits easily in 128 GB); LoRA rank 64 to 256 with alpha = 2r for SFT and for
  7B CPT. QLoRA is unnecessary at or below 8B on 128 GB. INFERRED.
- **I5. RL sharpens, it does not teach** (F5). Expect P3 to raise compile@1 and
  pass@1, not compile@k at large k. Gate on pass@1 and watch pass@k for
  collapse. INFERRED.
- **I6. Contamination risk.** faustlibraries and the faust examples are public
  GitHub code and are likely in every base model's pretraining data. The sealed
  holdout must be newly written tasks, not mined from those repositories.
  INFERRED.

## Base-model shortlist (P0 bake-off)

All are adapted, never trained from scratch.

| Model | Params | License (HF tag) | Notes | Label |
|---|---|---|---|---|
| Qwen2.5-Coder-1.5B (base) | 1.5B | apache-2.0 | Code-specialized, fill-in-the-middle; fast iteration model | OBSERVED license |
| Qwen2.5-Coder-7B (base) | 7.6B | apache-2.0 | Upper bound for "small" | OBSERVED license |
| Qwen3.5-4B-Base | 4.7B | apache-2.0 | Released 2026-02; multimodal architecture, so check TRL/vLLM support on ARM64 first | OBSERVED license; INFERRED risk |
| Qwen3-4B-Base | 4.0B | apache-2.0 | Text-only fallback | OBSERVED license |
| Excluded by default | — | — | Qwen2.5-Coder-3B (license "other"), DeepSeek-Coder (license "other"), StarCoder2 (OpenRAIL-M use restrictions); include only if Danny accepts those terms | OBSERVED tags |

Selection rule (INFERRED): pick the smallest model whose few-shot dev
compile@10 after P2 is within the confidence interval of the largest; prefer
1.5B to 4B for serving speed.

## Compute and cost on one DGX Spark

Throughput assumptions use the time-based figures in F14, not NVIDIA's
headline peaks; 1.5B is assumed about 2x the 3B rate. All figures INFERRED; P0 replaces them with receipts (T09).

| Phase | Work | Tokens | 1.5B | 7B | Wall clock incl. data and eval |
|---|---|---|---|---|---|
| P0 | Corpus, harness, task suites, baselines | Inference only | — | — | 1.5 to 2 weeks (engineering-bound) |
| P1 | CPT: Faust corpus plus equal general-code replay, 2 epochs | ~40M | ~0.6 h (full FT, ~20k tok/s) | ~1.6 h (LoRA r=256, ~7k tok/s) | 1 to 3 days |
| P2 | SFT on 10k to 30k validated pairs, 3 epochs | ~50M | ~0.7 h | ~2 h | 1 to 1.5 weeks (data generation dominates) |
| P3 | GRPO, ~3k prompts, 8 samples each, 2 epochs; reward from sandboxed compile plus signal tests | ~20M generated | 0.5 to 1 day per run | 1 to 2 days per run | 1 to 2 weeks (2 to 3 runs) |

- Total Spark time: roughly 60 to 150 hours across 4 to 6 weeks. INFERRED.
- Electricity: 150 h at 0.24 kW is 36 kWh, about $10 to $15 at $0.30 to
  $0.40/kWh. INFERRED.
- Hardware amortization: $4,699 over 36 months is about $130/month per Spark.
  INFERRED.
- A second Spark runs evaluation and data generation in parallel with
  training; it is not needed for any single job at these sizes. INFERRED.
- Hosted teacher cost (if D-006 allows): NOT_COMPUTABLE until a teacher is
  chosen; needs a spend cap.

## Evaluation design

- Metrics: compile@1, compile@10, pass@1, pass@10 with the unbiased estimator
  (F8), n = 20 samples per task, temperature 0.2 for @1 and 0.8 for @10.
  Repair success within the attempt bound. Paired comparisons with bootstrap
  confidence intervals (spec §9).
- Task sources: dev suite seeded from faustlibraries `#### Usage` blocks and
  the faust impulse tests (F11); sealed holdout of newly written tasks (I6).
  Sizes INFERRED: about 200 dev, about 100 holdout.
- Signal tests reject trivial passes: silence, DC, NaN/Inf, clipping, wrong
  channel count (spec §9). This doubles as the anti-reward-hacking check for
  P3. INFERRED.
- Forgetting check: one general-code benchmark (for example HumanEval) before
  and after each phase, so specialization does not destroy instruction
  following. INFERRED.

## Open decisions (spec §14), updated

| ID | Question | Recommendation | Label |
|---|---|---|---|
| D-001 | Faust language | Confirmed by the owner's brief | OBSERVED |
| D-002 | Student model | Bake-off of the shortlist above; no 14B or 30B student | INFERRED |
| D-003 | Sample rates and runtimes | Default 48 kHz, fixed block size, C++ backend; revisit after P0 | INFERRED |
| D-004 | Redistribution versus training-only | Training-only for v1; no corpus redistribution; permissive-license allowlist; copyleft and unlicensed excluded until the owner decides | INFERRED; not legal advice |
| D-005 | Quality gates | Relative gates against the frozen baseline (ADR-0002) | INFERRED |
| D-006 | Teacher model | Prefer a local Apache-2.0 open-weights teacher (no output-use restrictions); hosted only with a spend cap and ToS review | INFERRED |

## References

- Cassano et al. Knowledge Transfer from High-Resource to Low-Resource
  Programming Languages for Code LLMs. arXiv:2308.09895.
- Giagnorio, Martin-Lopez, Bavota. Enhancing Code Generation for Low-Resource
  Languages: No Silver Bullet. arXiv:2501.19085.
- Biderman et al. LoRA Learns Less and Forgets Less. arXiv:2405.09673.
- Shao et al. DeepSeekMath (GRPO). arXiv:2402.03300.
- Hui et al. Qwen2.5-Coder Technical Report. arXiv:2409.12186.
- Dou et al. StepCoder. arXiv:2402.01391.
- Gehring et al. RLEF. arXiv:2410.02089.
- Le et al. CodeRL. arXiv:2207.01780.
- Chen et al. Evaluating Large Language Models Trained on Code. arXiv:2107.03374.
- NVIDIA DGX Spark hardware guide and technical blog on DGX Spark performance;
  NVIDIA/dgx-spark-playbooks issue #29; Tom's Hardware DGX Spark review and
  price update (2026-02-27).

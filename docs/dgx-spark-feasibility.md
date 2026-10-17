# DGX Spark feasibility study

T09 records whether a FaustCoder training phase can run on one NVIDIA DGX
Spark. This repository does not have access to the two Zero State machines,
so the pages below separate published hardware facts from estimates and from
checks that still have to be run on a Spark.

The training stack is not pinned. No phase is a go for T10 until a Spark
produces an `env_verified` receipt whose probes completed inside the operator
memory cap. A 7.6B full-parameter run does not fit the shared-machine cap
this study uses. 1.5B and about-4B full-parameter runs, and 7B LoRA, are the
configurations to measure.

Contract for the transition: [training machine](state-machines/training.md)
(spec §7.3). Commands: [runbook](runbooks/dgx-spark-env-verified.md).
Method and shortlist: [ADR-0002](adr/0002-training-path.md),
[research.md](../specs/001-faustcoder/research.md).

## What a receipt from this harness is

`faustcoder.spark_probe` writes two artifact-store objects when the R-001
guard passes:

1. An environment-diagnostics payload. `contracts/` has no schema for it.
   The payload sets `contract` to null and says so. That shape is
   SPECULATIVE. It is stored only as an envelope object.
2. A transition receipt whose payload is the existing TransitionReceipt
   schema: `PLANNED` / `env_verified` / `ENV_VERIFIED`, effect text
   "Record environment digest". `input_hashes` and the receipt's parent are
   the diagnostics digest.

`stack_pin_allowed` is true only when both the inference probe and the LoRA
probe return a positive token rate and a peak under the memory cap. The
state can still become `ENV_VERIFIED` when the probes were skipped: the spec
guard is pinned dependencies and hardware diagnostics, not a token rate.
Do not pin PyTorch, TRL, or a student model on a receipt whose flag is false.

Each invocation is a new training-machine subject that starts at `PLANNED`.
Run it once on each Spark. A receipt from one machine does not verify the
other.

## Go / no-go rubric

Thresholds in code: `MIN_UNIFIED_MEMORY_BYTES` (100 GiB),
`MAX_MEMORY_CAP_BYTES` (96 GiB), `MAX_PROBE_SECONDS` (600), default cap
4 GiB. The 96 GiB ceiling is INFERRED policy so a probe on a 128 GB machine
cannot request the whole pool while other jobs are running. It is not an
NVIDIA limit.

| Id | Check | Result when it fails | Label |
|---|---|---|---|
| G1 | `arch` is `aarch64` or `arm64` | No-go. Guard rejects `env_verified` | R-001 |
| G2 | GPU name matches `GB10`, `Grace Blackwell`, or `DGX Spark` | No-go | R-001 |
| G3 | CUDA is available and the CUDA version string is recorded | No-go | R-001 |
| G4 | Torch imported and its version string is recorded | No-go | R-001 |
| G5 | `MemTotal` is at least 100 GiB | No-go | INFERRED floor under the published 128 GB |
| G6 | Declared pins equal the ADR-0004 set copied into the probe | No-go | R-001 |
| G7 | `limits.network` is false, duration is 1..600 s, cap is 1 byte..96 GiB | No-go | Shared-machine policy |
| G8 | Driver version recorded when `nvidia-smi` succeeds; otherwise memory still comes from `/proc/meminfo` | No-go | R-001 |
| G9 | Phase static bytes, using the formulas below, are at most 96 GiB | No-go for that phase | INFERRED |
| G10 | Inference and LoRA probes `completed`, rates > 0, peaks ≤ cap | Do not pin the stack. `stack_pin_allowed` stays false | NOT_MEASURED until a Spark run |
| G11 | Human reads the device name on the first receipt | If the name misses G2, keep the diagnostics and do not force the guard | OBSERVED on that host |

G10 is not a minimum tokens/sec. Spec D-005 has not set a quality bar. The
inferred ranges later in this note are planning context, not pass thresholds.
The smoke probe uses sequence length at most 128, batch 1, and at most two
optimizer steps. Its peak is not the memory of a sequence-2048 training step.
Treat any extrapolation from the smoke peak to a real training step as
SPECULATIVE.

This pull request can satisfy the code behind G1–G8 with a mocked
fingerprint. It cannot satisfy G10.

## Hardware facts

OBSERVED on the [DGX Spark hardware overview](https://docs.nvidia.com/dgx/dgx-spark/hardware.html)
(page fetched 2026-10-17):

| Item | Published value |
|---|---|
| Architecture | NVIDIA Grace Blackwell, integrated CPU and GPU |
| CPU | 20-core Arm: 10 Cortex-X925 and 10 Cortex-A725 |
| Memory | 128 GB LPDDR5x unified system memory, 256-bit, 273 GB/s |
| Memory clock, as printed | Component table: 4266 MHz. Compute section: LPDDR5X 8533 |
| GPU | Blackwell, 5th-generation Tensor Cores, 6144 CUDA cores |
| AI compute | Up to 1 PFLOP FP4 with sparsity; up to 1000 TOPS inference |
| Model support, as printed | Up to 200 billion parameters; 405 billion on two Sparks |
| Form factor | 150 mm × 150 mm × 50.5 mm |

The same page's "200 billion parameters" line is a product claim, not a
training recipe. It is not evidence that a 70B or 200B training job fits.

The component table does not print the string `GB10`. OBSERVED on the
[bitsandbytes 0.50.1 release](https://github.com/bitsandbytes-foundation/bitsandbytes/releases/tag/0.50.1):
that release calls the RTX Spark GPU GB10 and adds an `sm121` tier to its
4-bit GEMM dispatch. INFERRED: the DGX Spark GPU is that GB10 part. The
guard accepts `GB10`, `Grace Blackwell`, and `DGX Spark` so the first real
`torch.cuda.get_device_name` string can match without a guess at the exact
marketing name. `GB100` does not match.

The hardware page prints both 4266 MHz and LPDDR5X 8533. INFERRED: those are
the clock and the DDR data rate for one LPDDR5X part. The harness does not
use either number. It records `MemTotal` from `/proc/meminfo`, because the
pool is unified system memory rather than a discrete framebuffer.

## Memory estimates

Parameter counts are the shortlist in
[research.md](../specs/001-faustcoder/research.md): 1.5B, 4.0B, 4.7B, 7.6B.
Bytes below use decimal GB (1e9) and are INFERRED.

Full-parameter mixed precision, per trainable parameter: bf16 weights 2,
bf16 gradients 2, fp32 Adam first moment 4, fp32 Adam second moment 4, fp32
master weights 4. That is 16 bytes per parameter. LoRA keeps the frozen base
at 2 bytes per parameter. A rank-256 LoRA on attention and MLP is estimated
as at most 10 percent of the base parameter count, then costed at the same
16 bytes. That 10 percent ceiling is INFERRED and is high on purpose.
`tie_word_embeddings` and exact layer shapes are not re-measured here.

| Model | bf16 weights | Full static (16 bytes/param) | LoRA static ceiling (3.6 bytes/param) | Against the 96 GiB cap |
|---|---|---|---|---|
| 1.5B | 3.0 GB | 24 GB | 5.4 GB | Full and LoRA are inside the cap before activations |
| 4.0B | 8.0 GB | 64 GB | 14.4 GB | Full is inside the cap before activations |
| 4.7B | 9.4 GB | 75.2 GB | 16.9 GB | Full is inside the cap before activations |
| 7.6B | 15.2 GB | 121.6 GB | 27.4 GB | Full is over the cap. LoRA is inside it before activations |

121.6 GB is about 113 GiB, which is already over the 96 GiB ceiling, before
activations and before the operating system. G9 is a no-go for 7.6B
full-parameter continued pretraining or SFT. That agrees with R-008: full
parameter updates stop at about 4B, and a 7B student uses LoRA. QLoRA is not
required for these sizes if the LoRA static figure holds. R-008 already says
QLoRA is unnecessary at or below 8B on 128 GB.

4.0B and 4.7B full-parameter static figures fit under 96 GiB and do not fit
comfortably if a long-context activation spike is large. They are conditional
goes: run the smoke probe, then a real training step only with gradient
checkpointing, batch 1, and a cap the operator sets from `MemAvailable`.
Qwen3.5-4B-Base is the 4.7B row. research.md already flags its multimodal
architecture as an extra software risk (INFERRED).

Activation bytes are not computed. They depend on sequence length, batch,
checkpointing, and kernels. NOT_COMPUTABLE from the spec alone.

## Throughput estimates

OBSERVED on the [NVIDIA DGX Spark performance article](https://developer.nvidia.com/blog/how-nvidia-dgx-sparks-performance-enables-intensive-ai-tasks/)
(published 2025-10-24, modified 2026-02-11; fetched 2026-10-17).

The prose states peak rates of 82,739.2 tokens/s for Llama 3.2 3B full
fine-tuning, 53,657.6 tokens/s for Llama 3.1 8B LoRA, and 5,079.4 tokens/s
for Llama 3.3 70B QLoRA.

Table 1 on the same page, for one epoch and 64 steps at sequence length 2048:

| Model | Method | Batch | Table tokens/s |
|---|---|---|---|
| Llama 3.2 3B | Full fine-tuning | 8 | 13,519.54 |
| Llama 3.1 8B | LoRA | 4 | 6,969.59 |
| Llama 3.3 70B | QLoRA | 8 | 759.79 |

The table note defines those rates as
`(batch_size * steps * sequence_length) / total time to train`. The page
does not define the window behind the higher prose peaks. Planning in this
study uses Table 1 only. The prose peaks are not targets.

INFERRED ranges for the FaustCoder shortlist, transferred from those Llama
rows. The transfer is weak: model shape, LoRA rank, and sequence length
differ, and the article does not state the LoRA rank. These ranges are not
G10 thresholds.

| Phase and method | Planning range | Why |
|---|---|---|
| 1.5B full parameter | 14k–27k tokens/s | From the 3B full-FT table rate up to twice that rate. research.md used about 20k as a midpoint |
| 4B full parameter | 10k–16k tokens/s | Near the 3B table rate; a larger model is not assumed to be faster |
| 7.6B LoRA rank 256 | 5k–8k tokens/s | Near the 8B LoRA table rate |
| 7.6B full parameter | No rate | G9 says not to run it |
| QLoRA at these sizes | No rate | Not the R-008 method. The 70B QLoRA row is a different regime |

Worked example, INFERRED, same token count as research.md: 40M tokens at
20k tokens/s is 2000 seconds, about 0.6 hours. Replace that with the receipt
before quoting it as a schedule.

The smoke probe reports prefill-plus-greedy-decode tokens/s and AdamW
tokens/s on whatever local model the operator passes. Those rates are not
the Table 1 configuration (sequence 2048, many steps). Comparing them
directly to the table is SPECULATIVE.

## Software stack on ARM64 and Blackwell

ADR-0002 and spec §10 name Python, PyTorch, Transformers, and PEFT/TRL.
Unsloth, vLLM, and bitsandbytes are constraints on that stack, not extra
required packages. The probe never installs them and never downloads weights.

| Package | What is established | Label |
|---|---|---|
| PyTorch | [PyTorch 2.7](https://pytorch.org/blog/pytorch-2-7/) ships CUDA 12.8 wheels for Linux x86 and arm64, and lists Blackwell support as a prototype in that release | OBSERVED for 2.7. Whether the Spark image is that wheel, a newer build, or an NGC container is NOT_MEASURED |
| Transformers, PEFT, TRL | Spec §10 stack. They are Python packages on top of PyTorch. Import on this GPU is not measured | SPECULATIVE until the receipt's `measured_packages` lists them |
| bitsandbytes | 0.50.1 adds a Windows ARM64 CUDA build for RTX Spark and an `sm121` (GB10) 4-bit GEMM tier. The release notes do not say a Linux aarch64 wheel is shipped for DGX OS | OBSERVED for that release. Linux DGX Spark import is SPECULATIVE. QLoRA stays optional under R-008 |
| vLLM | The NVIDIA performance article names vLLM as an inference backend used on Spark | OBSERVED that NVIDIA used it. A pip wheel for the host CUDA is SPECULATIVE. Serving is T13, not this probe |
| Unsloth | No official Linux aarch64 statement was established for this study. ADR-0002 does not require it | SPECULATIVE. Do not pin it |
| xformers | One report of no prebuilt aarch64 wheel for CUDA 13 on GB10: [unifolm issue 41](https://github.com/unitreerobotics/unifolm-world-model-action/issues/41) | OBSERVED as a single report. Not an ADR-0002 dependency |

Use the torch already on the Spark. A clean virtualenv hides that install
and would tempt a download. The runbook uses `--system-site-packages` and
does not install torch.

Host CUDA and the torch wheel's CUDA can disagree. The fingerprint records
`torch.version.cuda` and, when `nvidia-smi` works, the driver version. It
does not install a toolkit.

## Recommendation

| Question | Answer | Label |
|---|---|---|
| Pin the training stack from this pull request? | No | G10 is open |
| Run the harness on each Spark? | Yes | The code is the T09 deliverable |
| 1.5B full parameter, then the winning recipe at 4B–4.7B | Measure. Static memory is inside the 96 GiB cap | INFERRED |
| 7.6B LoRA for SFT or for CPT above 4B | Measure. Static ceiling is inside the cap | INFERRED, matches R-008 |
| 7.6B full parameter | No-go under G9 | INFERRED |
| QLoRA as the default | No. Revisit only if a measured LoRA peak exceeds the cap and bitsandbytes imports on that Spark | R-008; bitsandbytes on Linux is SPECULATIVE |
| Two Sparks for one sharded job | Not indicated at these sizes. The second machine is a second receipt and, later, parallel eval | INFERRED, same reading as research.md |

## Evidence still required on the machines

1. Fingerprint-only run on each Spark (`stack_pin_allowed` false is expected).
2. Smoke run with a local 1.5B directory and a raised cap, after the operator
   checks `MemAvailable`.
3. Repeat for the 4B or 7B candidate the bake-off still cares about.
4. Paste both content digests into the operations log. Do not commit the
   store. Do not edit `KANBAN.md` from the probe output.

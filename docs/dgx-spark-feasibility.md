# DGX Spark feasibility study

T09 records whether a FaustCoder training phase can run on one NVIDIA DGX
Spark. This repository does not have access to the Zero State machines, so
the pages below separate published hardware facts from estimates and from
checks that still have to be run on a Spark.

Training runs on a dedicated DGX Spark that is cleared of other workloads
before training (OBSERVED, Danny 2026-10-17). The earlier 96 GiB
shared-machine ceiling is withdrawn. The probe's default cap is that
machine's `MemTotal` minus an 8 GiB OS margin, and it cannot be set above
120 GiB.

7.6B full-parameter AdamW does not fit 128 GB unified memory once optimizer
state, a realistic activation residual and that margin are counted. LoRA at
7.6B, and full-parameter AdamW at 1.5B through 4.7B, are the configurations
whose static bytes fit. 8-bit Adam is a conditional alternative for 7.6B and
stays SPECULATIVE until bitsandbytes imports on the machine.

R-001 was amended 0.3.1 (Danny yes 2026-10-17 12:54 PM PT, spec §20). For
v0.2, the benchmarks cited below plus one environment-fingerprint receipt
per machine satisfy R-001. On-hardware FaustCoder throughput is T10, on the
cleared Spark. That amendment does not pin PyTorch: `stack_pin_allowed`
stays false until both probes complete.

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
Under the 0.3.1 amendment, a fingerprint-only receipt (probes skipped,
`stack_pin_allowed` false) is the per-machine half of R-001 for v0.2. Do
not pin PyTorch, TRL, or a student model on a receipt whose flag is false.

Each invocation is a new training-machine subject that starts at `PLANNED`.
Run it once on each Spark that will train. A receipt from one machine does
not verify the other.

## Go / no-go rubric

Thresholds in code: `MIN_UNIFIED_MEMORY_BYTES` (100 GiB),
`NOMINAL_UNIFIED_BYTES` (128 GiB), `OS_HEADROOM_BYTES` (8 GiB, INFERRED),
`MAX_MEMORY_CAP_BYTES` (120 GiB), `MAX_PROBE_SECONDS` (600). When
`--memory-cap-mib` is omitted, the cap is `MemTotal` minus 8 GiB, and not
above 120 GiB. Unknown `MemTotal` falls back to 120 GiB; the identity guard
still rejects a machine under 100 GiB. The operator can set a lower cap.
The 8 GiB margin is for the OS, the driver, page cache and a CUDA context.
It is not an NVIDIA specification. NVIDIA prints "128 GB"; the ceiling
treats that figure as 128 GiB. The decimal reading (128e9 bytes, about
119.2 GiB) is smaller, and a third-party report below lists 121 GB on a
live Spark.

| Id | Check | Result when it fails | Label |
|---|---|---|---|
| G1 | `arch` is `aarch64` or `arm64` | No-go. Guard rejects `env_verified` | R-001 |
| G2 | GPU name matches `GB10`, `Grace Blackwell`, or `DGX Spark` | No-go | R-001 |
| G3 | CUDA is available and the CUDA version string is recorded | No-go | R-001 |
| G4 | Torch imported and its version string is recorded | No-go | R-001 |
| G5 | `MemTotal` is at least 100 GiB | No-go | INFERRED floor under the published 128 GB |
| G6 | Declared pins equal the ADR-0004 set copied into the probe | No-go | R-001 |
| G7 | `limits.network` is false, duration is 1..600 s, cap is 1 byte..120 GiB | No-go | Dedicated-machine policy |
| G8 | Driver version recorded when `nvidia-smi` succeeds; otherwise memory still comes from `/proc/meminfo` | No-go | R-001 |
| G9 | Phase static bytes, using the formulas below, fit in the dedicated budget with room for activations | No-go for that phase | INFERRED |
| G10 | Inference and LoRA probes `completed`, rates > 0, peaks ≤ cap | Do not pin the stack. `stack_pin_allowed` stays false. Not a v0.2 R-001 gate (amended 0.3.1) | NOT_MEASURED until T10 |
| G11 | Human reads the device name on the first receipt | If the name misses G2, keep the diagnostics and do not force the guard | OBSERVED on that host |

G10 is not a minimum tokens/sec. Spec D-005 has not set a quality bar. The
inferred ranges later in this note are planning context, not pass thresholds.
The smoke probe uses sequence length at most 128, batch 1, and at most two
optimizer steps. Its peak is not the memory of a sequence-2048 training step.
Treat any extrapolation from the smoke peak to a real training step as
SPECULATIVE. Running that smoke is T10, after the fingerprint receipt.

This pull request satisfies the code behind G1–G8 with a mocked fingerprint.
It does not satisfy G10. Under amended R-001 it does not have to: the cited
benchmarks plus the fingerprint run are the v0.2 evidence.

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

8-bit Adam, INFERRED, keeping the fp32 master: bf16 weights 2, bf16
gradients 2, fp32 master 4, 8-bit moments 1+1, so 10 bytes per parameter.
Dropping the fp32 master is an implementation choice, not default AdamW, and
is not the planning figure.

| Model | bf16 weights | Full AdamW (16 bytes/param) | 8-bit Adam, fp32 master kept (10 bytes/param) | LoRA ceiling (3.6 bytes/param) |
|---|---|---|---|---|
| 1.5B | 3.0 GB | 24 GB | 15.0 GB | 5.4 GB |
| 4.0B | 8.0 GB | 64 GB | 40.0 GB | 14.4 GB |
| 4.7B | 9.4 GB | 75.2 GB | 47.0 GB | 16.9 GB |
| 7.6B | 15.2 GB | 121.6 GB | 76.0 GB | 27.4 GB |

Three readings of the pool, before activations:

- Published "128 GB" as decimal GB (OBSERVED label on the hardware page).
  7.6B AdamW static is 121.6 GB, leaving 6.4 GB. The 8 GiB margin is about
  8.6 GB, so the static state already exceeds the usable budget.
- The same "128 GB" read as 128 GiB (about 137.4 GB), which is what the
  120 GiB cap assumes. Static leaves about 15.8 GB, and about 7.2 GB after
  the 8 GiB margin. That is not a realistic residual for a sequence-2048
  training step. INFERRED: still a no-go.
- A live Spark environment table reports 121 GB unified memory (OBSERVED in
  [Unsloth issue 4867](https://github.com/unslothai/unsloth/issues/4867),
  fetched 2026-10-17). 121.6 GB of static state is over that reported pool
  before the margin.

Gradient checkpointing reduces activation memory. It does not shrink the
16 bytes per parameter. It does not make 7.6B AdamW fit. INFERRED.

Paged Adam (bitsandbytes) moves optimizer state into host RAM. On unified
memory the host and the GPU share one pool, so paging does not create a
second one. INFERRED from the unified-memory design. SPECULATIVE until a
measurement: no source read for this study reports paged Adam on a DGX Spark.

8-bit Adam at 76.0 GB fits under the 120 GiB ceiling with on the order of
50 GB left, and still fits a 121 GB pool after the 8 GiB margin (on the
order of 35 GB left). That room can hold activations if checkpointing is on.
The method is conditional on bitsandbytes importing on Linux aarch64, which
is SPECULATIVE (see the software table). It is not the R-008 default.

Phase verdicts against G9:

| Phase | Verdict | Why | Label |
|---|---|---|---|
| 1.5B full AdamW | Go for static memory | 24 GB, wide margin under 120 GiB. Activations still NOT_MEASURED | INFERRED |
| 4.0B full AdamW | Conditional go | 64 GB static fits. A sequence-2048 step still needs checkpointing and a measured peak | INFERRED |
| 4.7B full AdamW | Conditional go | 75.2 GB static fits, same activation caveat. Qwen3.5-4B-Base also carries the multimodal software risk already flagged in research.md | INFERRED |
| 7.6B full AdamW | No-go | 121.6 GB static does not leave a realistic activation budget on any of the three pool readings | INFERRED |
| 7.6B full AdamW plus gradient checkpointing only | No-go | Checkpointing does not reduce the static footprint | INFERRED |
| 7.6B full AdamW, paged optimizer | No-go as extra memory | Unified memory is one pool. Whether a paged implementation wastes less is SPECULATIVE | INFERRED / SPECULATIVE |
| 7.6B full, 8-bit Adam, fp32 master kept | Conditional | 76.0 GB fits the budget if bitsandbytes imports on this OS | INFERRED bytes; SPECULATIVE software |
| 7.6B LoRA | Go for static memory | 27.4 GB ceiling. This is the R-008 method above about 4B | INFERRED |
| QLoRA at or below 8B | Not the default | R-008: unnecessary on 128 GB when LoRA fits | R-008 |

4.0B and 4.7B remain conditional goes: static bytes fit, and a long-context
activation spike is not computed here. Activation bytes depend on sequence
length, batch, checkpointing and kernels. NOT_COMPUTABLE from the spec alone.
Qwen3.5-4B-Base is the 4.7B row.

This agrees with R-008: full-parameter updates stop at about 4B, and a 7B
student uses LoRA. The dedicated machine does not overturn that for AdamW.

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
G10 thresholds. They are the external training benchmarks the 0.3.1
amendment cites for v0.2 planning. They are not FaustCoder measurements.

| Phase and method | Planning range | Why |
|---|---|---|
| 1.5B full parameter | 14k–27k tokens/s | From the 3B full-FT table rate up to twice that rate. research.md used about 20k as a midpoint |
| 4B full parameter | 10k–16k tokens/s | Near the 3B table rate; a larger model is not assumed to be faster |
| 7.6B LoRA rank 256 | 5k–8k tokens/s | Near the 8B LoRA table rate |
| 7.6B full AdamW | No rate | G9 says not to run it |
| 7.6B 8-bit Adam | No rate | Conditional method; no published rate was read for that optimizer on Spark |
| QLoRA at these sizes | No rate | Not the R-008 method. The 70B QLoRA row is a different regime |

Worked example, INFERRED, same token count as research.md: 40M tokens at
20k tokens/s is 2000 seconds, about 0.6 hours. That example is planning
context from Table 1, not a T09 receipt. Replace it with a T10 measurement
before quoting it as a schedule.

## Use of established benchmarks

Amended 0.3.1 (Danny yes 2026-10-17 12:54 PM PT). For v0.2, the benchmarks
in this section plus one `env_verified` fingerprint receipt per Spark
satisfy R-001. On-hardware throughput for the FaustCoder recipe is deferred
to T10, on the dedicated Spark after it has been cleared. spec §20 records
the amendment. The fingerprint path is the first command in the runbook.
`stack_pin_allowed` may be false on that receipt.

Links below were fetched on 2026-10-17. A number is OBSERVED only when it
appears on a page read for this note. Workloads listed without a rate are
workloads the page names, not measured tokens/s.

| Source | What it actually reports | Use for v0.2 |
|---|---|---|
| [NVIDIA performance article](https://developer.nvidia.com/blog/how-nvidia-dgx-sparks-performance-enables-intensive-ai-tasks/), Table 1 | Training rates quoted above: Llama 3.2 3B full fine-tune 13,519.54 tokens/s, Llama 3.1 8B LoRA 6,969.59, Llama 3.3 70B QLoRA 759.79. Sequence 2048, 64 steps | OBSERVED. Planning ranges for 1.5B–4B full AdamW and 7.6B LoRA |
| [DGX Spark playbook, performance guide](https://github.com/NVIDIA/dgx-spark-playbooks/blob/main/nvidia/connect-two-sparks/assets/performance_benchmarking_guide.md) | Fine-tuning section names three runs and does not publish a token-rate table: Llama 3 8B LoRA (`Llama3_8B_LoRA_finetuning.py --use_torch_compile`), Llama 3 70B qLoRA, Llama 3 3B full fine-tune. Inference sections name TensorRT-LLM, vLLM, SGLang and llama.cpp. The page says DGX Spark uses an LTS host stack and that newer CUDA belongs in NGC containers; installing CUDA on the host is outside the supported stack | OBSERVED as the workload list and the host-stack rule. No rate taken from this page |
| [LMSYS DGX Spark review](https://www.lmsys.org/blog/2025-10-13-nvidia-dgx-spark/) (Jerry Zhou and Richard Chen, 2025-10-13) | Inference, not training. GPT-OSS 20B MXFP4 in Ollama: 2,053 tps prefill / 49.7 tps decode, against 10,108 / 215 on an RTX Pro 6000 Blackwell and 8,519 / 205 on an RTX 5090. Llama 3.1 8B in SGLang: 7,991 prefill / 20.5 decode at batch 1, and 7,949 / 368 at batch 32. Llama 3.1 70B FP8: 803 prefill / 2.7 decode. The review's hardware recap matches GB10, 128 GB coherent unified memory, 273 GB/s, and up to 405B FP4 on two Sparks. Bandwidth is the limiter they report | OBSERVED inference. Confirms the machine serves an 8B-class model and that bandwidth, not a missing kernel, is the published bottleneck. Not a training rate |
| [Unsloth DGX Spark tutorial](https://unsloth.ai/docs/blog/fine-tuning-llms-with-nvidia-dgx-spark-and-unsloth) | Unsloth claims fine-tuning up to 200B parameters on Spark, and says gpt-oss-120b QLoRA 4-bit uses around 68 GB. The tutorial itself is gpt-oss-20b reinforcement learning. The published Dockerfile starts from `nvcr.io/nvidia/pytorch:25.09-py3` and installs `bitsandbytes==0.48.0` | OBSERVED as Unsloth's claim. It is QLoRA and their container, not full AdamW, and it is not a FaustCoder measurement |
| [Unsloth issue 4867](https://github.com/unslothai/unsloth/issues/4867) | One operator's environment table: DGX Spark GB10, aarch64, 121 GB unified memory, compute capability 12.1, CUDA 13.0, driver 580.x, NGC `nvcr.io/nvidia/pytorch:25.11-py3`, PyTorch 2.10.0a0. Inference needed manual `transformers` patches for `kernels-community/vllm-flash-attn3`. A later comment reports LoRA training of Qwen3-0.6B and a 27B 4-bit run with `attn_implementation="eager"`, again listing 121 GB. Unsloth closed the issue on 2026-10-11, saying current Unsloth loads GPT-OSS without those patches | OBSERVED third-party report. The 121 GB figure is why 121.6 GB AdamW static is a no-go before the policy margin. Unsloth on Linux aarch64 has been fragile; ADR-0002 does not require it |

Nothing in this table is a FaustCoder tokens/s number. T10 measures that
recipe on the cleared machine.

## Software stack on ARM64 and Blackwell

ADR-0002 and spec §10 name Python, PyTorch, Transformers, and PEFT/TRL.
Unsloth, vLLM, and bitsandbytes are constraints on that stack, not extra
required packages. The probe never installs them and never downloads weights.

| Package | What is established | Label |
|---|---|---|
| PyTorch | [PyTorch 2.7](https://pytorch.org/blog/pytorch-2-7/) ships CUDA 12.8 wheels for Linux x86 and arm64, and lists Blackwell support as a prototype in that release. Issue 4867 reports a Spark running an NGC image with PyTorch 2.10.0a0 and CUDA 13.0 | OBSERVED for those two statements. Which image the Zero State Spark has is NOT_MEASURED |
| Transformers, PEFT, TRL | Spec §10 stack. The playbook's fine-tuning section installs them inside an NGC PyTorch container. Import on this GPU is not measured | SPECULATIVE until the receipt's `measured_packages` lists them |
| bitsandbytes | 0.50.1 adds a Windows ARM64 CUDA build for RTX Spark and an `sm121` (GB10) 4-bit GEMM tier. The release notes do not say a Linux aarch64 wheel is shipped for DGX OS. The playbook runs `bitsandbytes==0.49.1` inside `nvcr.io/nvidia/pytorch:25.12-py3` and sets `BNB_CUDA_VERSION=130`. Unsloth's Spark Dockerfile pins 0.48.0 | OBSERVED as those published instructions. Linux import on the Zero State Spark is NOT_MEASURED, so 8-bit Adam and QLoRA stay SPECULATIVE |
| vLLM | The NVIDIA performance article and the LMSYS review both run inference stacks on Spark; LMSYS publishes SGLang numbers, and the playbook names vLLM | OBSERVED that those pages use or name an inference server. A pip wheel for the host CUDA is SPECULATIVE. Serving is T13 |
| Unsloth | The tutorial and issue 4867 above. ADR-0002 does not require Unsloth | OBSERVED that a Spark path exists and has needed workarounds. Do not pin it |
| xformers | One report of no prebuilt aarch64 wheel for CUDA 13 on GB10: [unifolm issue 41](https://github.com/unitreerobotics/unifolm-world-model-action/issues/41). Unsloth's Dockerfile builds xformers from source for `TORCH_CUDA_ARCH_LIST=12.1` | OBSERVED as those two reports. Not an ADR-0002 dependency |

Use the torch already on the Spark, preferably the NGC container the
playbook describes rather than a host CUDA install. A clean virtualenv hides
the machine torch and would tempt a download. The runbook uses
`--system-site-packages` and does not install torch.

Host CUDA and the torch wheel's CUDA can disagree. The fingerprint records
`torch.version.cuda` and, when `nvidia-smi` works, the driver version. It
does not install a toolkit.

## Recommendation

| Question | Answer | Label |
|---|---|---|
| Does amended R-001 need a tokens/s receipt in this pull request? | No. Cited benchmarks plus a fingerprint receipt per machine. Throughput is T10 | spec §20, Danny yes 2026-10-17 12:54 PM PT |
| Pin the training stack from this pull request? | No. `stack_pin_allowed` stays false until probes complete | G10, deferred to T10 |
| Where does the fingerprint run? | On the cleared dedicated Spark, fingerprint-only, before any smoke | OBSERVED operating rule (Danny 2026-10-17) |
| 1.5B full parameter, then the winning recipe at 4B–4.7B | Static memory fits. Measure the real step in T10, with checkpointing for the 4B rows | INFERRED |
| 7.6B LoRA for SFT or for CPT above 4B | Static ceiling fits. This is the R-008 method | INFERRED |
| 7.6B full AdamW | No-go under G9 | INFERRED |
| 7.6B full, 8-bit Adam | Conditional. Revisit only if the fingerprint shows bitsandbytes imported | INFERRED / SPECULATIVE |
| QLoRA as the default | No. Revisit only if a measured LoRA peak exceeds the cap and bitsandbytes imports | R-008 |
| Two Sparks for one sharded job | Not indicated at these sizes. The second machine is a second receipt and, later, parallel eval | INFERRED, same reading as research.md |

## Evidence still required on the machines

1. Fingerprint-only run on the cleared dedicated Spark. Probes skipped and
   `stack_pin_allowed` false are expected. Together with the benchmarks in
   this note, that receipt is the amended R-001 evidence for v0.2.
2. The same fingerprint on the second Spark if that machine will train. One
   receipt does not cover both.
3. On-hardware throughput, including the optional smoke probe, waits for T10
   and still runs only after the machine is cleared.
4. Paste both content digests into the operations log. Do not commit the
   store. Do not edit `KANBAN.md` from the probe output.

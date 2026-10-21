# Spark DSP setup and next steps

Verified 2026-10-20 PT on **spark-af42**, SSH alias `spark2`, checkout
`~/BlackDog`, main `0cd3382` ([PR #80](https://github.com/Zero-State-LLC/BlackDog/pull/80)).
DSP validation and the T09 fingerprint are recorded below; neither establishes training readiness or measured model quality.
The alias did not identify spark-bf46; results apply only to spark-af42.

## Local operation

The following scripts are operator-local, untracked files created during setup.
They are not shipped by a fresh clone. Their backup contains the scripts and
receipts, not the repository, venv, Node installation or system sandbox configuration.

```bash
cd ~/BlackDog
source ./activate-local.sh
./smoke-test-local.sh
```

Activation selects `.venv`, prepends `.local/node/bin`, and sets
`FAUSTCODER_UNSHARE=/opt/faustcoder/bin/fc-unshare`. Installed versions were
Python 3.12, Node 22.23.3, native Faust 2.88.0 and pinned faustwasm 0.19.0.
For a new machine follow the [compiler runbook](compiler-harness.md), including
library pins and the dedicated AppArmor profile. Do not replace that profile
with a host-wide namespace exception.

The smoke script compiles `process = _ * 0.5;` and compares 144,000 samples
against an independently constructed unit-impulse reference (0.5, then zeros)
at 44.1 and 48 kHz. A 0.25-gain negative control must fail the reference check.
It requires no sudo. Full pytest uses sudo for temporary ownership fixtures
and canary directories; obtain operator approval before those operations.
Existing keys and `/etc/faustcoder` were not changed by this setup.

## Validation and evidence

| Check | Observed result |
|---|---|
| Full ARM suite for PR #79 | 635 passed, 2 skipped, 63 warnings; 141.60 seconds |
| Full x86 suite for PR #79 | 637 passed, 63 warnings; 336.89 seconds |
| Node 22.14.0 x86 nonlinear suite | 26 passed, including regenerated-golden test |
| T04 ARM/x86 comparison | 40/40 finite renders match byte-for-byte; all five WASM binaries match |
| Skips | x86 DSP-bank goldens; non-Spark host guard |
| PR #79 CI and review | Nine checks passed; automated review had no findings; merged as `bb367c9` |
| Merged-main readiness | Fresh SSH activation, dependency and namespace checks, both-rate smoke and 40/40 golden comparison passed on `bb367c9` using Node 22.23.3 |
| Saved smoke script | Both rates passed; wrong-gain control rejected |
| Backup restore | Archive SHA-256, 17 manifest file hashes and all 18 archive files verified; temporary restore removed |

The original biquad overflowed; its cross-architecture differences were NaN
sign bits. PR #79 corrected the feedback subtraction and redundant delay,
added finite-output and independent recurrence regressions, and regenerated
the eight biquad hashes only after verifying corrected ARM/x86 outputs.
Tolerances were unchanged. See the [baseline provenance](signal-harness.md#corrected-biquad-baseline-2026-10-20).

Portable CI evidence: [full x86 suite](https://github.com/Zero-State-LLC/BlackDog/actions/runs/39504923383)
and [fresh comparison/capture](https://github.com/Zero-State-LLC/BlackDog/actions/runs/39504915933).
Artifacts have limited retention; the operator-local copies below are the
persistent evidence. Raw DSP output and WASM files are not committed.

Spark evidence is under `~/BlackDog/.local/smoke-receipts/`:

- `blackdog-smoke-j6jk1mbw/`: copied original receipts; its summary retains the original temporary path.
- `20261020T204346Z-qjcra01u/`: saved-script verification.
- Subsequent smoke runs create unique timestamped directories with compiler,
  signal and negative-control receipts, DSP source and summary.

Additional Spark evidence under `~/BlackDog/.local/`:

- `t04-biquad-fix/`: corrected ARM raw samples, WASM and regression evidence.
- `t04-golden-validation/`: fresh ARM comparison and full-suite log.
- `main-update-20261020T221946Z/`: merged-main verification, preservation manifest and checksums; 13,779 pre-existing untracked/ignored files preserved during update (one bytecode cache refreshed during verification).
- `smoke-receipts/20261020T222003Z-9r8b0tsm/`: merged-main smoke receipts.

Operator workspace evidence, outside Git, is under `outputs/`:

- `blackdog-golden-validation/`: final report, fresh ARM/x86 results, full-suite logs and verified checksums.
- `blackdog-biquad-comparison/`: corrected raw ARM/x86 captures and exact comparison.
- `blackdog-biquad-fix/`: patch, corrected ARM capture and negative-control evidence.
- `blackdog-spark-af42/blackdog-fixed-pytest.log` and `.xml`: earlier PR #77 evidence.
- `blackdog-backup-2026-10-20/`: setup guide, two scripts, both receipt sets and manifest.
- `blackdog-backup-2026-10-20.tar.gz` and its `.sha256` sidecar.
- `blackdog-backup-2026-10-20.restore-verification.md` and its `.sha256` sidecar.

These are operator-local paths, not repository artifacts or portable links.
Do not commit setup artifacts, keys, model files or raw local receipts.

The vLLM container `nemo35` was stopped with authorization to free memory;
available RAM was about 118 GiB during validation. Recheck current workloads
before further runs; this historical observation is not a resource reservation.
The Faust installer encountered a pre-existing malformed GitHub CLI APT source.
A temporary installer copy skipped APT commands because build dependencies
were present; the APT source was not repaired. Any repair is a separate,
operator-approved maintenance action.

## T09 fingerprint evidence

On 2026-10-20 at 22:45:32 UTC, spark-af42 completed fingerprint-only execution
on main `0cd338200dc08f0a4ee8e5f41975ba1e58e979f4`: exit **0**, status
**`env_verified`**, transition `PLANNED` → `ENV_VERIFIED`, with no guard
rejection reasons. No model path was supplied. Inference and LoRA probes
were skipped (`no_local_model`), and **`stack_pin_allowed=false`**.

The interpreter was `~/r9venv/bin/python` (Python 3.12.3), using existing
user-site torch `2.15.0.dev20260924+cu130`, CUDA 13.0 and driver 580.178.04
on the NVIDIA GB10. Torch import and a tiny CUDA calculation passed.
BlackDog was installed editable with `rfc3339-validator` 0.1.4; torch was
unchanged. The existing Axolotl 0.19.0 requirement (`torch>=2.11.0,<=2.13.0`)
conflicts with that torch version. `pip check` reported the same conflict
before and after installation. This establishes functional fingerprinting,
not a vendor-supported or training-compatible stack.

Preflight listed no GPU compute jobs, running Docker containers or matching
Python/model/training process names. This observation is not a reservation;
recheck workloads before T10 and ask before stopping any workload or using
sudo. No sudo, workload stop, model load or training occurred in this run.
The separate DSP `.venv` and activation script were preserved. The preceding
merged-main T09 CPU harness check passed 38 tests with one skip.

| Artifact | SHA-256 artifact ID |
|---|---|
| Diagnostics | `sha256:415cfcd5d1ebd26f74ce4f314ec721e71d5bfd532b0f4acaba657ecef3a4bdb1` |
| Transition receipt | `sha256:5c06fdcc1b181c0760b6a8351abadd8757484c7a7990287d519b36c9ab397305` |

Both objects passed `ArtifactStore.get`, including envelope-sidecar checks.
The complete evidence was copied off-host; all 17 manifest file checksums
passed locally. Receipt locations (operator-local, outside Git and `/tmp`):

- Spark: `~/blackdog-t09-20261020T224502Z/`.
- Local workspace: `outputs/blackdog-t09/blackdog-t09-20261020T224502Z/`.
- In both locations: `store/sha256/` contains the two JSON objects and their
  `.envelope_digest` sidecars; `fingerprint.stdout.json`,
  `fingerprint.exit-status.txt`, `artifact-verification.json`, `SHA256SUMS`,
  environment/install logs and `README.md` preserve the execution evidence.
- Spark checkout-readiness evidence:
  `~/blackdog-update-20261020T224321Z/` (13,794 existing artifact files verified
  unchanged through that update and its readiness checks).

This completes the per-machine fingerprint evidence for **spark-af42**.
The cited external benchmarks remain the separate R-001 evidence in the
[feasibility study](../dgx-spark-feasibility.md). No second-Spark receipt is
claimed; fingerprint that machine separately if it will train. T01 and all
training dependency gates remain in force.

## Isolated T10 environment and dependency blocker

Historical baseline: this environment remains unchanged and blocked. The
[separate repaired candidate](#validated-cusparselt-repair-candidate) below
resolves the packaging blocker without replacing this venv.

On 2026-10-20, a separate `~/blackdog-t10-venv` was created on spark-af42
with Python 3.12.3 and editable BlackDog at main `de82d32`. This is the
direct Hugging Face variant: Axolotl, DeepSpeed and optional attention
kernels were not installed. The original `~/r9venv`, its shared user-site
packages, the DSP `.venv` and the original T09 receipts remain unchanged.
The Axolotl/torch conflict remains in r9venv; it is not inherited by this
isolated candidate.

| Component | Installed version |
|---|---|
| PyTorch / CUDA | `2.13.0+cu130` / 13.0 |
| Triton | 3.7.1 |
| Transformers / PEFT / TRL | 5.16.1 / 0.20.0 / 1.9.0 |
| Accelerate / datasets | 1.13.0 / 4.8.4 |
| tokenizers / huggingface-hub | 0.23.1 / 1.17.0 |

Operator-local activation (not an instruction to start training):

```bash
source ~/blackdog-t10-venv/bin/activate
export PYTHONNOUSERSITE=1
```

Do not source the DSP activation script for this environment. Validation
confirmed user-site disabled, no r9venv/DSP path leakage, and all checked
training imports originating inside the new venv. `Trainer`, `SFTTrainer`
and PEFT imports passed. On GB10 (capability 12.1), small generated-tensor
BF16 matmul/backward, SDPA backward and AdamW update checks passed with
finite results; peak allocated CUDA memory was 67,167,744 bytes. These
checks loaded no model and measured no training throughput. They do not
exercise cuSPARSELt sparse matrix operations.

**Dependency validation is blocked.** `pip check` reports:

```text
nvidia-cusparselt-cu13 0.8.1 is not supported on this platform
```

The upstream ARM64 wheel filename declares `manylinux2014_aarch64`, but
its internal `WHEEL` tag is `manylinux2014_sbsa`. Its AArch64 ELF library
loads successfully; that does not make the dependency check pass.
Inspection of the original upstream 0.9.1 wheel confirmed a corrected
`manylinux2014_aarch64` tag. However, official CPython 3.12 ARM64 torch
2.13.0, 2.14.0 and 2.14.1 CUDA 13.0 wheel metadata pins cuSPARSELt 0.8.1
exactly. The inspected CUDA 13.2 builds of 2.13.0 and 2.14.1 have the same
pin. An on-Spark resolver dry run for torch 2.13.0 plus cuSPARSELt 0.9.1
failed with `ResolutionImpossible` (exit 1); it installed nothing.

These are observations as of 2026-10-20, not a claim about future releases.
Sources: [NVIDIA 0.8.1 wheel metadata](https://pypi.org/pypi/nvidia-cusparselt-cu13/0.8.1/json),
[0.9.1 metadata](https://pypi.org/pypi/nvidia-cusparselt-cu13/0.9.1/json), and
[official CUDA 13.0 torch wheels](https://download.pytorch.org/whl/cu130/torch/).
The operator-local investigation retains the wheel URLs, hashes and internal
tags. No installed metadata was rewritten, dependency pin overridden or
validation failure suppressed.

The initial recommendation was to wait for an upstream-compatible wheel or
consider a separately built torch package. The subsequently authorized
[audited wheel repair](#validated-cusparselt-repair-candidate) resolved the
packaging issue in a separate candidate while retaining torch's exact pin.
The original venv still fails dependency validation. Its dense CUDA results
alone did not justify forcing cuSPARSELt 0.9.1 past the resolver. The old T09
receipt describes r9venv with `stack_pin_allowed=false`; it covers neither
T10 environment.

Evidence locations, outside Git and `/tmp`:

- Spark: `~/blackdog-t10-setup-20261020T231900Z/`.
- Local copy: `outputs/blackdog-t10-setup/blackdog-t10-setup-20261020T231900Z/`.
- Both contain requested constraints, resolved package inventory, install
  logs, `pip-check.txt`, CUDA validation script/results, preservation manifests
  and `SHA256SUMS`. All 15 copied evidence file checksums passed.
- Local investigation: `outputs/blackdog-cusparselt-investigation/REPORT.md`,
  `upstream-wheel-tags.json` and `alternate-builds.json`.
- Initial stack assessment: `outputs/blackdog-t10-investigation/`.

All 15,296 inventoried existing setup/r9venv/T09 files and symlinks verified
unchanged. No sudo, workload stop or model download occurred. No custom
build or upstream issue submission was initiated. Keep these artifacts out
of Git and ask before sudo, stopping workloads or downloading models.

## Validated cuSPARSELt repair candidate

On 2026-10-20, the authorized downstream wheel repair was installed into
**`~/blackdog-t10-candidate`** on spark-af42, Python 3.12.3, NVIDIA GB10,
glibc 2.39, with editable BlackDog at `de82d32`. **Packaging and CUDA
validation passed; T10 training qualification remains pending.** This is a
separate candidate, not a replacement for `~/blackdog-t10-venv`, r9venv or
the DSP environment. It retains the package versions listed above.

The audit found two packaging errors: the internal `manylinux2014_sbsa`
tag was invalid for this host, and the binary's GLIBC_2.27 symbols exceeded
the filename's manylinux2014 claim. `auditwheel` supports the corrected
`py3-none-manylinux_2_27_aarch64` tag; Spark's glibc 2.39 meets it.
The repaired wheel is
`nvidia_cusparselt_cu13-0.8.1-1blackdog1-py3-none-manylinux_2_27_aarch64.whl`.
Only `WHEEL` and regenerated `RECORD` changed. The native library, headers,
license, `METADATA` and remaining payload are byte-identical to the vendor
wheel. Version 0.8.1 and torch's exact dependency pin remain intact; the
build tag `1blackdog1` identifies the downstream repair.

| Artifact | SHA-256 |
|---|---|
| Original vendor wheel | `4dca476c50bf4780d46cd0bfbd82e2bc10a08e4fef7950917ce8d7578d22a23f` |
| Repaired wheel | `ba570ca1cdfa6e829b1747e674242f64f9d179a9e02a4f6522f0e379e5f7b34b` |
| Unchanged AArch64 native library | `fbb03bbf8d2238670f24256c5452281c2a660162899b838bb4d0cc06dad027df` |

This is a locally audited packaging repair, not an NVIDIA release. Keep the
wheel internal; redistribution licensing has not been assessed. A normal
pip resolver installed the repaired wheel with the original pinned package
set. No dependency override, `--no-deps`, installed-metadata edit or
validation suppression was used.

| Candidate check | Observed result |
|---|---|
| Dependency validation | `pip check`: No broken requirements found |
| Installed integrity | 9 hashed RECORD entries verified; all 5 original payload members excluding WHEEL/RECORD identical |
| Environment isolation | User-site disabled; checked training imports inside candidate; Trainer/SFTTrainer/PEFT imports pass |
| Dense CUDA | BF16 matmul/backward, SDPA backward and finite AdamW update pass, repeated in a fresh process |
| Actual cuSPARSELt backend | 12/12 `SparseSemiStructuredTensorCUSPARSELT` cases pass; runtime version 801 |
| Sparse comparisons | FP16/BF16, three seeds, 128×128 valid 2:4 inputs; independent CPU float64 reference and dense CUDA comparison; integer cases exact |
| Fixed random-input error budgets | FP16 absolute 0.003, BF16 absolute 0.025, relative 0; maximum reference errors below 0.000974869 and 0.007741333 respectively; no adjustments |
| Preservation | 52,333 baseline files/symlinks unchanged; tracked Spark checkout clean |
| Off-host backup | All 28 evidence file checksums verified |

These are generated-tensor smoke checks, not model training, throughput,
quality measurements or a new fingerprint. No sudo, workload stops or
model downloads occurred. Existing sandbox configuration and T09 receipts
were preserved. No full repository test-suite rerun is claimed for this repair.

Receipt locations, outside Git and `/tmp`:

- Spark: `~/blackdog-wheel-repair-20261020T234819Z/`.
- Local workspace: `outputs/blackdog-wheel-repair/blackdog-wheel-repair-20261020T234819Z/`.
- Both retain `original/` and `repaired/` wheels, `repair.py`,
  `wheel-audit.json`, both `auditwheel-*.txt` reports, install log,
  requirements/freeze/inspect inventories, `pip-check.txt`,
  `installed-verification.json`, dense/repeated/sparse validation scripts
  and results, preservation manifests, checkout revision/status and `README.md`.
- `SHA256SUMS` covers the 28 evidence files, excluding itself. Verify with
  `sha256sum -c SHA256SUMS` from the evidence directory. These are local
  evidence paths, not files included in a clone; do not commit the artifacts.

Candidate activation and optional repeat checks (no training or downloads):

```bash
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
source ~/blackdog-t10-candidate/bin/activate
python -m pip check
python ~/blackdog-wheel-repair-20261020T234819Z/validate_cuda.py
python ~/blackdog-wheel-repair-20261020T234819Z/validate_sparse.py
```

Do not use the DSP activation script for this candidate or replace the
original T10 venv yet. Before further GPU work, recheck workload clearance.
The [fresh candidate fingerprint](#repaired-candidate-t09-fingerprint) below
now passes. Retain its verified artifacts and repeat after stack changes or
on another Spark. Next qualify the approved local model and actual T10
dataset/configuration, run a small training step and checkpoint-save/reload
check, and record inference/LoRA throughput and memory within the existing
probe gates before any stack-pin decision. Model downloads, sudo and workload
stops require separate authorization. Both fingerprints have
`stack_pin_allowed=false`; the project dependency gates remain in force.

## Repaired candidate T09 fingerprint

At **2026-10-21 00:29:27 UTC (2026-10-20 PT)**, spark-af42 completed a fresh
fingerprint using `~/blackdog-t10-candidate/bin/python` from `~/BlackDog`
at merged main **`1ae20bad7dffcbd7e387fd00cb3970de750befb7`** (PR #83).
Exit **0**, status **`env_verified`**, transition `PLANNED` → `ENV_VERIFIED`,
with no guard rejection reasons. `pip check` passed. Python 3.12.3,
torch `2.13.0+cu130`, CUDA 13.0, NVIDIA GB10 and driver 580.178.04 were
recorded. This receipt covers the repaired candidate; the earlier r9venv
receipt remains preserved as historical evidence.

Source selection matters: the candidate's editable install still points to
`~/blackdog-t10-candidate/src/faustcoder` at `de82d32`. Running `python -m`
from `~/BlackDog` selected merged source without reinstalling or altering
that environment; `source.json` records the verified import path.
The recorded invocation was:

```bash
cd ~/BlackDog
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
~/blackdog-t10-candidate/bin/python -m faustcoder.spark_probe \
  --store ~/blackdog-t09-candidate-20261021T002919Z/store \
  --actor spark-operator
```

This is the historical command; use a new evidence directory for a rerun.
No model path was supplied. Inference and LoRA were skipped with
`no_local_model`, and **`stack_pin_allowed=false`**. Fingerprint success
does not establish training throughput, model quality or a pinned stack.

| Artifact | SHA-256 artifact ID |
|---|---|
| Diagnostics | `sha256:693cd6a7d20e9ac6bd01b13f166fc7ea7147b5670d15bb347da18598c1ae510f` |
| Transition receipt | `sha256:5becf23d32e4b864225b7ff80c267da2cca7c93c8bd183739a9f9f73dd96098b` |

Both objects passed `ArtifactStore.get`, including envelope-sidecar checks;
the transition's parent and input hashes reference the new diagnostics.
The off-host copies matched the verified objects and **all 20 file checksums
passed**, including both envelope sidecars. Locations outside Git and `/tmp`:

- Spark: `~/blackdog-t09-candidate-20261021T002919Z/`.
- Local workspace: `outputs/blackdog-t09-candidate/blackdog-t09-candidate-20261021T002919Z/`.
- Both contain `store/sha256/`, `fingerprint.stdout.json`,
  `fingerprint.exit-status.txt`, `artifact-verification.json`, source/revision,
  preflight, dependency and preservation records, `README.md` and `SHA256SUMS`.
- Preceding merged-main readiness receipts:
  `~/blackdog-main-update-20261021T002048Z/` and local
  `outputs/blackdog-main-update/blackdog-main-update-20261021T002048Z/`
  (18 backup checksums verified).

Preflight listed no GPU compute processes or running Docker containers;
recheck current workloads before subsequent GPU work. All **89,975**
inventoried environment/setup/receipt files and symlinks remained unchanged.
No sudo, workload stops, model downloads, package installs or tracked edits
occurred during fingerprinting. Keep these operator-local artifacts out of Git.

## Offline training and checkpoint diagnostic

On 2026-10-21 UTC (2026-10-20 PT), spark-af42 ran the repaired candidate
against checkout `e53bf46`. **Synthetic training/checkpoint validation passed**;
this does not complete representative T10 model qualification or G10.
A fresh `GPT2LMHeadModel` was initialized from the local tiny-random GPT-2
configuration (five layers, width 32, vocabulary 1024). No external model
weights, tokenizer, benchmark or training dataset were consumed. Model seed
was 42; generated token-ID seed was 43.

The diagnostic used five AdamW steps, batch 1, sequence length 64 and learning
rate 0.001; LoRA rank 4, alpha 8, `c_attn` targets, `fan_in_fan_out=true`,
zero dropout and eager attention. The frozen base was BF16; PEFT adapters
were FP32. Results in `attempt-2/result.json`:

| Check | Result |
|---|---|
| Training | Five steps plus a resumed step; finite losses/gradients and nonzero gradient norms |
| Updates | 2,560 trainable parameters; all 10 adapter tensors changed; frozen base unchanged |
| Base reload | No missing, unexpected or mismatched keys, or loader errors |
| Checkpoint fidelity | Reloaded logits and optimizer state matched exactly |
| Resume | Adapter update occurred; loss, gradient-norm summary, parameters and optimizer state exactly matched uninterrupted continuation |
| GPU allocation | Peak 68,704,768 bytes (~65.5 MiB), below the 2 GiB PyTorch allocator cap |
| Bounds | 180-second alarm per attempt; final timed body after imports ~0.889 seconds, not a throughput benchmark |
| Preservation | 90,014 baseline environment/setup/receipt files and symlinks unchanged; tracked checkout clean |
| Backup | All 47 copied file checksums verified |

Attempt 1 reached the final result-writing step but exited 1: loader metadata
contained Python sets that JSON could not serialize. Its script, logs and
checkpoints are retained. Attempt 2 fixed serialization and added an explicit
resumed-parameter-update assertion; exit **0**, status **PASS**. No numerical
assertion, tolerance or isolation check was relaxed. PEFT's dummy-config-path
warning is retained in stderr; local checkpoint loading and equality checks
passed without downloads.

Evidence locations, outside Git and `/tmp`:

- Spark: `~/blackdog-training-smoke-20261021T010653Z/`.
- Local: `outputs/blackdog-training-smoke/blackdog-training-smoke-20261021T010653Z/`.
- Top level retains attempt 1 and the preservation/environment records;
  `attempt-2/` contains the successful corrected script, `result.json`, logs,
  saved initial random base, adapters before/after resume, optimizer states,
  generated IDs and reference logits. Config copies record provenance.
- `README.md` explains both attempts; `SHA256SUMS` covers 47 files excluding
  itself. Verify from the evidence directory with `sha256sum -c SHA256SUMS`.
  Do not commit these artifacts or rerun into an existing receipt directory.

No sudo, workload stops, package installs or model downloads occurred.
This is an infrastructure diagnostic, not a production `TrainingRun`, model
quality result or stack-pin receipt. **`stack_pin_allowed=false`** remains
in force. Next qualify an approved local model and cleared dataset/configuration,
repeat training/checkpoint validation on that actual model, measure inference/LoRA
throughput and memory, and satisfy the data/baseline/reward/P3 gates below.

## Next steps

This is a proposed execution order, not authorization to run training or modify
system configuration. [KANBAN](../../KANBAN.md) retains the dependency gates.

| Order | Work | Acceptance / stop condition |
|---|---|---|
| 1 | T10 environment and per-machine evidence | spark-af42 fingerprint is complete; retain the verified store above. The separate repaired candidate passes dependency, integrity and dense/sparse CUDA checks. The fresh candidate fingerprint passes (see above). Recheck workload clearance and qualify the approved local model/dataset/configuration, training/checkpoint reload on the actual model, and throughput/memory before any stack pin. The synthetic diagnostic above passes but does not clear those gates. Repeat fingerprinting after environment changes and on a second Spark if used. Do not replace the DSP venv or download weights implicitly. |
| 2 | Audit and signature follow-ups (#62, #68, #69, #72) | Reconcile each issue against merged #71, add focused regression/feature-detection evidence, and document remaining risks. Merge status alone does not close follow-up issues. Keep credentials and signing configuration untouched without separate authorization. |
| 3 | Live reward wiring and group handling | Complete A2-PATH/EVAL-SO task/native-receipt plumbing and GD-1 whole-group drop acceptance tests. Keep auto-attribution in shadow until L3, A7-S and CANARY gates are met. |
| 4 | Data and training prerequisites | Resolve T01/ADR-0001, T06 H2/H3 and FLOOR evidence, then T07 split freeze and T08 baseline measurements. Record rights/leakage gates before T10; retain P3 audit, credential and dedicated-grader requirements. |

### T09 checklist for a rerun or another Spark

1. Confirm the target Spark identity, merged revision, available memory/GPU state, and
   operator clearance of other workloads. The earlier `nemo35` stop does not
   establish present clearance; do not stop services or use sudo implicitly.
2. Identify an existing supported torch/CUDA environment and verify torch
   import, CUDA version and availability there. Do not recreate `.venv`,
   install torch/transformers, download weights or repair APT as a shortcut.
   Use that supported environment directly, with its verified interpreter
   selected explicitly as `T09_PYTHON`; do not assume a child venv inherits
   its torch packages. Follow the
   [fingerprint runbook](dgx-spark-env-verified.md#install).
3. Run fingerprint-only with no `--model-path`, storing under the ignored
   `receipts/local/T09`. Capture exit code and JSON stdout outside `/tmp`.
   Exit 0 must produce both digests; exit 2 preserves diagnostics but does
   not complete T09; exit 1 means no artifacts were written.
4. Read both digests through `ArtifactStore.get` to verify their envelope
   sidecars and inspect the machine identity and guard result. Copy the
   entire store, stdout and checksums to off-host per-machine evidence and
   verify the copied objects again. Record revision, environment versions,
   both digests and the result in the T09 operations log.
5. Mark fingerprint evidence complete only after those checks pass and the
   cited external-benchmark portion of R-001 is accounted for. Repeat on a
   second Spark only if it will train; do not reuse this machine's receipt.

The spark-af42 fingerprint above passes the per-machine evidence checks.
The packaging blocker is resolved only in the separate repaired candidate.
The repaired candidate fingerprint passes. T10 still requires
actual-model training/checkpoint and throughput validation (synthetic infrastructure diagnostic passed; no candidate stack-pin receipt yet), T01 and the data/baseline gates,
GD-1 and live A2-PATH/EVAL-SO integration. P3 additionally retains its audit,
human-triage credential and dedicated-grader requirements. No production
signing deployment, training throughput or model-quality result is claimed;
this plan does not authorize training.

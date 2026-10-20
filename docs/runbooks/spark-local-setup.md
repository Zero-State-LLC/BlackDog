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

## Next steps

This is a proposed execution order, not authorization to run training or modify
system configuration. [KANBAN](../../KANBAN.md) retains the dependency gates.

| Order | Work | Acceptance / stop condition |
|---|---|---|
| 1 | T10 environment and per-machine evidence | spark-af42 fingerprint is complete; retain the verified store above. Resolve the Axolotl/torch conflict through an explicitly selected supported training stack, recheck workload clearance, and validate local-model compatibility and throughput before any stack pin. Repeat fingerprinting after environment changes and on a second Spark if used. Do not replace the DSP venv or download weights implicitly. |
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
T10 remains blocked on training-stack compatibility and model/throughput
validation (`stack_pin_allowed=false`), T01 and the data/baseline gates,
GD-1 and live A2-PATH/EVAL-SO integration. P3 additionally retains its audit,
human-triage credential and dedicated-grader requirements. No production
signing deployment, training throughput or model-quality result is claimed;
this plan does not authorize training.

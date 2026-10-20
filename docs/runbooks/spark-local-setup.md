# Spark DSP setup and next steps

Verified 2026-10-20 PT on **spark-af42**, SSH alias `spark2`, checkout
`~/BlackDog`, main `bb367c9` ([PR #79](https://github.com/Zero-State-LLC/BlackDog/pull/79)).
This is DSP compiler/signal readiness, not training readiness or measured model quality.
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

## Next steps

This is a proposed execution order, not authorization to run training or modify
system configuration. [KANBAN](../../KANBAN.md) retains the dependency gates.

| Order | Work | Acceptance / stop condition |
|---|---|---|
| 1 | T09 per-machine fingerprint (#12) | Follow [env_verified](dgx-spark-env-verified.md), confirm workload clearance and locate an existing supported torch/CUDA environment. Preserve the DSP venv; do not recreate it or install torch/weights as a shortcut. Stop if the supported environment is absent. Capture diagnostics and receipt digests, validate store sidecars and copy evidence off-machine. Fingerprint-only evidence does not establish throughput or a model stack pin. |
| 2 | Audit and signature follow-ups (#62, #68, #69, #72) | Reconcile each issue against merged #71, add focused regression/feature-detection evidence, and document remaining risks. Merge status alone does not close follow-up issues. Keep credentials and signing configuration untouched without separate authorization. |
| 3 | Live reward wiring and group handling | Complete A2-PATH/EVAL-SO task/native-receipt plumbing and GD-1 whole-group drop acceptance tests. Keep auto-attribution in shadow until L3, A7-S and CANARY gates are met. |
| 4 | Data and training prerequisites | Resolve T01/ADR-0001, T06 H2/H3 and FLOOR evidence, then T07 split freeze and T08 baseline measurements. Record rights/leakage gates before T10; retain P3 audit, credential and dedicated-grader requirements. |

### T09 execution checklist

1. Confirm `spark-af42`, merged revision, available memory/GPU state, and
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

T09 remains evidence pending. No fingerprint, training throughput, production
signing deployment or model-quality result is claimed here. Fingerprint-only
success may leave `stack_pin_allowed` false; throughput and model-stack
validation remain T10 work. T01 and all training dependency gates remain in
force; this plan does not authorize training.

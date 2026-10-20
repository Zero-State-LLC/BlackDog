# Spark DSP setup and next steps

Verified 2026-10-20 PT on **spark-af42**, SSH alias `spark2`, checkout
`~/BlackDog`, main `19b9184` ([PR #77](https://github.com/Zero-State-LLC/BlackDog/pull/77)).
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
| Full suite on PR #77 branch | 627 passed, 2 skipped, 63 warnings; 94.68 seconds |
| Skips | x86 DSP-bank goldens; non-Spark host guard |
| PR #77 CI and review | Eight checks passed; automated review had no findings; merged as `19b9184` |
| Merged-main readiness | Dependency check and four compiler/isolation tests passed |
| Saved smoke script | Both rates passed; wrong-gain control rejected |
| Backup restore | Archive SHA-256, 17 manifest file hashes and all 18 archive files verified; temporary restore removed |

Spark evidence is under `~/BlackDog/.local/smoke-receipts/`:

- `blackdog-smoke-j6jk1mbw/`: copied original receipts; its summary retains the original temporary path.
- `20261020T204346Z-qjcra01u/`: saved-script verification.
- Subsequent smoke runs create unique timestamped directories with compiler,
  signal and negative-control receipts, DSP source and summary.

Operator workspace evidence, outside Git, is under `outputs/`:

- `blackdog-spark-af42/blackdog-fixed-pytest.log` and `.xml`.
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
| 1 | T04 ARM DSP-bank comparison | Use the existing activation and `scripts/signal_cross_arch.py`; save output outside `/tmp` and compare against committed x86 goldens. Preserve versions and digests. A mismatch is `infra_fault`; investigate without widening tolerances or replacing goldens. The impulse smoke does not satisfy this check. |
| 2 | T09 per-machine fingerprint (#12) | Follow [env_verified](dgx-spark-env-verified.md), confirm workload clearance and locate an existing supported torch/CUDA environment. Preserve the DSP venv; do not recreate it or install torch/weights as a shortcut. Stop if the supported environment is absent. Capture diagnostics and receipt digests, validate store sidecars and copy evidence off-machine. Fingerprint-only evidence does not establish throughput or a model stack pin. |
| 3 | Audit and signature follow-ups (#62, #68, #69, #72) | Reconcile each issue against merged #71, add focused regression/feature-detection evidence, and document remaining risks. Merge status alone does not close follow-up issues. Keep credentials and signing configuration untouched without separate authorization. |
| 4 | Live reward wiring and group handling | Complete A2-PATH/EVAL-SO task/native-receipt plumbing and GD-1 whole-group drop acceptance tests. Keep auto-attribution in shadow until L3, A7-S and CANARY gates are met. |
| 5 | Data and training prerequisites | Resolve T01/ADR-0001, T06 H2/H3 and FLOOR evidence, then T07 split freeze and T08 baseline measurements. Record rights/leakage gates before T10; retain P3 audit, credential and dedicated-grader requirements. |

No T09 fingerprint, ARM golden comparison, training throughput, production
signing deployment or model-quality result was produced by the setup work.

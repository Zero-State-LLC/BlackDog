# Runbook: env_verified on a DGX Spark

Record the R-001 environment digest for one Spark. The study and the
go/no-go rubric are in [the feasibility note](../dgx-spark-feasibility.md).
The transition table is in [the training machine](../state-machines/training.md).

Run this on the dedicated DGX Spark after that machine has been cleared of
other workloads (OBSERVED, Danny 2026-10-17). This repository's CI does not
have the machines. Do the fingerprint path first. The optional smoke probe
is T10 work and is not required for the amended R-001 gate (spec §20, Danny
yes 2026-10-17 12:54 PM PT).

Repeat the fingerprint on the second Spark if that machine will train. The
receipts are not interchangeable.

## Safety

- The process forces Hugging Face offline mode. There is no flag that turns
  the network back on.
- Weights load only from a directory you already have. A hub id or URL is
  rejected.
- The default memory cap is `MemTotal` minus 8 GiB, and it cannot exceed
  120 GiB. Pass `--memory-cap-mib` only to set a lower cap. The 8 GiB margin
  is INFERRED headroom for the OS, the driver, page cache and a CUDA
  context. It is not an NVIDIA limit.
- Default duration is 60 seconds. The hard maximum is 600 seconds.
- The probe does not print environment variables, absolute paths, or
  `nvidia-smi` stderr. The stored fingerprint does include
  `platform.node()` so the two Sparks can be told apart.
- Clear the machine before training. Do not raise the cap to make room for
  another job that is still running.

## Install

Use the Python that already sees the machine's torch. A clean virtualenv
hides that install. From a checkout of this revision:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install --disable-pip-version-check -e .
```

Do not pip-install torch, transformers wheels, or model weights as part of
this run. `pip install -e .` installs FaustCoder and its schema dependencies
only. The NVIDIA playbook cited in the feasibility study runs newer CUDA
from an NGC container and treats a host CUDA install as outside the
supported stack. This runbook does not install that container.

Confirm torch is the one already on the machine:

```bash
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

If that import fails, stop. Installing a wheel is a separate decision and is
outside this runbook.

## Fingerprint only

Run this first, with no model path. It can pass the `env_verified` guard on
a Spark and still leave `stack_pin_allowed` false, because no model was
loaded. That is the receipt amended R-001 asks for. Cited external
benchmarks in the feasibility study are the other half. They are not
produced by this command.

```bash
python -m faustcoder.spark_probe \
  --store receipts/local/T09 \
  --actor spark-operator
```

`faustcoder-spark-probe` is the same entry point. The default store,
`receipts/local/T09`, is gitignored. A store path elsewhere inside the
checkout is refused.

Stdout is one JSON object. Exit 0 means the guard passed and both artifacts
were written. Exit 2 means the diagnostics artifact was written and the guard
rejected the transition. Exit 1 means the arguments were refused and nothing
was written.

Copy the digests off the machine before anyone starts T10. Do not treat a
fingerprint-only receipt as a measured token rate.

## Throughput smoke

Deferred to T10. Do not run this for the v0.2 R-001 gate. When T10 does run
it, the machine is still the cleared dedicated Spark, and `--model-path` is
a local directory that already contains `config.json` and the weight files.
Omit `--memory-cap-mib` to keep the dedicated-machine default, or set a
lower cap. The example below sets 32 GiB only as an explicit lower cap.

```bash
python -m faustcoder.spark_probe \
  --store receipts/local/T09 \
  --actor spark-operator \
  --model-path /local/models/Qwen2.5-Coder-1.5B \
  --memory-cap-mib 32768 \
  --max-seconds 180
```

The probe estimates bf16 weight bytes from `config.json` and skips the load
when the estimate exceeds the cap. Sequence length defaults to 32 and cannot
exceed 128. The LoRA rank defaults to 4 and cannot exceed 8. Those limits
keep the smoke step small; they are not the P2 training rank (ADR-0002).

A skipped probe is still an honest receipt. It does not pin the stack.

## Where the receipt goes

The store writes:

```text
receipts/local/T09/sha256/<artifact_id>.json
receipts/local/T09/sha256/<artifact_id>.envelope_digest
```

The JSON stdout fields `diagnostics_digest` and `receipt_digest` are the
`sha256:` ids. Copy the whole `receipts/local/T09` directory off the Spark
to the operator's evidence location. Do not commit it. Do not put secrets or
home-directory paths into the actor name or the model directory's basename.

Suggested off-machine layout, outside this git checkout:

```text
evidence/T09/<node-name>/<diagnostics_digest>.json
evidence/T09/<node-name>/<receipt_digest>.json
```

Keep the `.envelope_digest` sidecar next to each object. `ArtifactStore.get`
rejects an object whose sidecar does not match.

Record both digests in the operations log for T09. A later training run (T10)
cites the receipt digest as a parent when it measures throughput. It should
cite a receipt whose diagnostics have `stack_pin_allowed` true before anyone
treats the token rate as measured. The fingerprint receipt alone is enough
for the amended R-001 record, together with the benchmarks in the study.

## Read a receipt without the Spark

From any checkout, against a copied store:

```bash
python -c "from faustcoder import ArtifactStore; import json,sys; s=ArtifactStore(sys.argv[1]); print(json.dumps(s.get(sys.argv[2])['payload'], indent=2))" \
  receipts/local/T09 \
  sha256:REPLACE_WITH_DIGEST
```

## CPU check before you carry the checkout to the machine

```bash
python -m pip install --disable-pip-version-check -e ".[test]"
python -m pytest tests/test_training_machine.py tests/test_spark_probe.py
```

Those tests mock the Spark fingerprint and skip the CUDA probes. A green run
does not mean G10 passed, and it does not replace the fingerprint on the
Spark.

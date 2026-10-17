# Runbook: env_verified on a DGX Spark

Record the R-001 environment digest for one Spark, and optionally a short
inference rate and a tiny LoRA step. The study and the go/no-go rubric are
in [the feasibility note](../dgx-spark-feasibility.md). The transition table
is in [the training machine](../state-machines/training.md).

Run this on the Spark. This repository's CI does not have the machines.
Repeat the same commands on the second Spark; the receipts are not
interchangeable.

## Safety

- The process forces Hugging Face offline mode. There is no flag that turns
  the network back on.
- Weights load only from a directory you already have. A hub id or URL is
  rejected.
- Default memory cap is 4096 MiB. The hard maximum is 96 GiB.
- Default duration is 60 seconds. The hard maximum is 600 seconds.
- The probe does not print environment variables, absolute paths, or
  `nvidia-smi` stderr. The stored fingerprint does include
  `platform.node()` so the two Sparks can be told apart.
- Do not raise the cap until `MemAvailable` in `/proc/meminfo` is larger than
  the cap plus the memory the other daily jobs need.

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
only.

Confirm torch is the one already on the machine:

```bash
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

If that import fails, stop. Installing a wheel is a separate decision and is
outside this runbook.

## Fingerprint only

This can pass the `env_verified` guard on a Spark and still leave
`stack_pin_allowed` false, because no model was loaded.

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

## Throughput smoke

Point `--model-path` at a local directory that already contains
`config.json` and the weight files. The example cap is 32 GiB. Change it
only after reading `MemAvailable`.

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
cites the receipt digest as a parent. It should cite a receipt whose
diagnostics have `stack_pin_allowed` true before anyone treats the token rate
as measured.

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
does not mean G10 passed.

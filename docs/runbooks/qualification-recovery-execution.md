# Qualification recovery execution

## Readiness and accounting

The reporter is read-only. Exit 0 means reporting succeeded; it is never a
training permission. Exit 2 means supplied evidence is invalid. Default pilot
requirements retain signed T07, T08 and T10 reward/group gates. Full-corpus
FLOOR and custody work is reported separately, not imposed as an extra pilot gate.
Canonical requirements carried by the signed split still apply.

```bash
python -m faustcoder.readiness --repo-root . --mode pilot --json
```

To index external receipts, add `--manifest`, `--evidence-root` and
`--scope-digest`. The scope digest is SHA-256 of the exact immutable proposed run
configuration including its input bindings. Use the version-1 schema in
`specs/001-faustcoder/contracts/readiness-manifest.schema.json`. Each receipt
reference carries receipt_id, gate, path, sha256, scope_digest and an outcome
claim. Only relative paths below the explicit evidence root are accepted.
Hashes establish integrity; semantic and authority adapters remain pending.
Never include private holdout contents or keys in a manifest or source checkout.

For the preserved full batch, replay the original binding and all payloads:

```bash
python -m faustcoder.eligibility_ledger \
  --batch-root /absolute/path/to/original/batch \
  --binding-sha256 EXACT_64_HEX_DIGEST
```

The full denominator is 1,430 units, 110 packets, 510 distinct candidate/comparison
blobs, 23 short collision groups and 19 collective support sets. Any disagreement
is a blocker. Accounting success never admits sources. The report preserves
historical statuses separately from unresolved eligibility. Feed existing bounded
approval receipts into future semantic adapters; do not request their approval
again when bytes and scope are unchanged. The real off-host batch has not been
replayed by this implementation session.

## Bounded pilot proposal

`train/pilot-qwen-1.5b.json` selects the previously documented, pinned Qwen base
and the existing successful smoke recipe. It is an unapproved configuration
candidate, not a training launcher. Dataset/split digests are deliberately null
until the selected minimum snapshot is qualified. The historical 28/7 diagnostic
split was single-project and is not automatically reused as a formal split.
Canonical T07 requires signed train/development/holdout commitments; private
holdout tasks stay with their human custodian and outside agent access.

INFERRED estimate for the same 20-step, batch-1, accumulation-4, 512-token recipe:
allow 8-12 GiB for allocator/model variation, capped at 16 GiB. The prior Qwen
smoke recorded approximately 5.93 GiB allocated and 6.34 GiB reserved. Those are
historical measurements, not a new qualification. At 2,373 input tokens/second,
20 x 4 x 512 tokens imply roughly 17 seconds of steady-state training; budget
5-15 minutes including loading, baselines, checkpoint/reload and fresh-process
resume, with a hard 30-minute bound. These are planning estimates, not an SLA.
A changed model, sequence length or method requires new measurements.

Do not introduce QLoRA or download another model for this pilot. R-008 explicitly
says QLoRA is unnecessary at this size on Spark. Preserve the known-good
candidate and prior evidence, use a new output directory, offline model loading,
and no package changes. Recheck current host workloads without stopping them.
The existing diagnostic probe can be executed on that host with its explicit
candidate interpreter and approved local model path:

```bash
export PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
~/blackdog-t10-candidate/bin/python -m faustcoder.spark_probe \
  --store /absolute/new/external/probe-store --actor spark-operator \
  --model-path /absolute/existing/approved/model \
  --memory-cap-mib 16384 --max-seconds 180 --seq-len 512 \
  --max-new-tokens 32 --lora-rank 64 --lora-steps 5
```

That command uses generated diagnostic tokens, not qualified dataset training.
It is not a checkpoint/resume test. Preserve and verify the existing checkpoint
probe script from the Qwen receipt for replay against the actual selected model.
No Spark connection or GPU is available in this workspace, so neither ran here.

Acceptance for the eventual pilot: exact model/data/split/toolchain bindings,
compiler and task-specific signal validation at both rates, independent baseline
replay, finite loss/gradients, nonzero adapter updates, unchanged frozen base,
checkpoint/logit/optimizer reload equality, exact resumed continuation, measured
memory/timing within caps, and development compiler/functional metrics against
the same base. Loss reduction alone is not a model-quality claim. Run no sealed
holdout during candidate selection. The pilot has no production admission.

Rollback: terminate only the pilot process, retain failed-attempt evidence and
checkpoints outside Git, return serving/evaluation to the unchanged pinned base,
and quarantine the candidate adapter. Never replace the baseline environment.

## Consolidated external inputs

No fresh owner decision is requested until the package is concrete. Remaining
inputs are the original batch and bounded approval payloads, signed T07 split
and current public custody commitments, independently replayed T08 baseline,
representative Spark receipts, and the exact qualified pilot snapshot. Assemble
those hashes with this bounded recipe into one pilot decision package. Request
actual training authorization only after technical validation; never invent it.

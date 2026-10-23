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

## Diagnostic evaluation funnel

`faustcoder.evaluation_funnel.evaluate` accepts one public whole-file unit from
the canonical pinned inventory, its notice, source bytes, TaskSpec and explicit
analytical reference provider. It verifies blob eligibility before compiling,
then runs full-window diagnostic comparisons at 44.1/48 kHz and persists chained
EvaluationRun stage views plus compiler/signal evidence in the caller's external
ArtifactStore. No private holdouts are loaded. Bad source, compiler failure or
signal failure prevents later stages; infrastructure failures are BLOCKED.

The fourth stage is always `independent_replay_not_verified` until an independent
adapter is implemented and verified. This entry point evaluates admitted public
source-unit diagnostics, not arbitrary model-generated candidates or function
units. It grants no reward, training permission, promotion or corpus admission.
The fixture tests establish early-stop/lineage contracts; they do not establish
real-corpus performance or independently replayed quality.

## Reuse a signed public T07 store

The semantic adapter can now verify `t07_signed_split` and
`family_disjoint_split`. It invokes the canonical signed-freeze verifier,
including exact transition receipts and the scheduled provisional-floor recheck.
It does not clear source qualification, model, baseline, environment, checkpoint
or owner training gates. No self-declared PASS or valid hash authorizes training.

Prepare a JSON scope using `readiness-scope.schema.json`: schema_version 1,
mode, dataset_snapshot_digest, code_revision, model_digest and recipe_digest.
Use the exact frozen snapshot digest and full code commit. Model/recipe digests
bind their immutable manifests; null is permitted for preparation and does not
make a pilot ready. The exact bytes of this scope file determine scope_digest.
Do not put a trusted signer or an approval flag in the scope or bundle.

Export from an explicitly selected **public-only** canonical artifact store:

```bash
python -m faustcoder.readiness_evidence \
  --public-store /absolute/public-snapshot-store \
  --scope-file /absolute/run-scope.json \
  --trusted-split-public-key /absolute/trusted/custodian.pub \
  --output /absolute/new/readiness-bundle
```

The public key must come from the existing trusted custodian channel, outside
the evidence store/bundle. Both CLIs reject a trust-key file inside their evidence
inputs or exported bundle. This reads no private key and enrolls no signer.
Never select a store containing private tasks or evaluation secrets. The exporter
refuses unsupported task/benchmark entities, symlinks, missing witnesses, changed
bytes, incomplete freezes and existing output directories. It preflights the
canonical signature before writing. It does not change the input store or any
prior receipt. Keep generated bundles outside Git.

The result includes an executable `next_command` argv list for the read-only
reporter. That command independently replays the exported evidence using the
out-of-band key. It may remove only the two verified blockers. A mixed valid and
invalid receipt for one gate leaves that gate blocked. No full-corpus FLOOR
completion is added as a prerequisite for an accepted provisional T07 freeze.

No real off-host store has been consumed in this implementation session. Tests
use disposable, generated sources and temporary SSH keys; fixture success is
not evidence that BlackDog's production T07 is frozen or its pilot is authorized.

Full mode names separate `approved_full_dataset` and
`full_training_authorization` gates. A bounded pilot approval cannot satisfy
those full-corpus gates. Neither mode accepts authorization from a self-declared
manifest outcome.

## Prepare bounded public pilot data

After exporting a verified public bundle, use the exact scope hash and T07
descriptor hash recorded in its readiness manifest. The output parent must
already exist outside the checkout and evidence root, with no symlink parents:

```bash
python -m faustcoder.pilot_data \
  --evidence-root /absolute/readiness-bundle \
  --bundle t07_signed_split.json \
  --bundle-sha256 <descriptor-sha256> \
  --scope-file /absolute/readiness-bundle/scope.json \
  --scope-digest <scope-sha256> \
  --trusted-split-public-key /absolute/trusted/custodian.pub \
  --output /absolute/new-pilot-data
```

The command replays the signature and current freeze, then writes train.jsonl,
development.jsonl and preparation.json with private permissions. Output preserves
source text, notices, attribution and immutable provenance. It exports complete
partitions only, at most 28 train and seven development units, with no holdout
examples. A larger snapshot requires a separately reviewed smaller candidate;
the exporter never silently samples or breaks dependency/family coverage.

Exit 0 means `PREPARED_NOT_QUALIFIED`, not training permission. The manifest hashes
every data file and reports all remaining pilot readiness gates plus compiler/
signal qualification and the instruction-pair contract. Source-only rows must
not be treated as completion-only instruction examples without that contract.
Use a fresh output directory for retries. A partial output without preparation.json
is incomplete and must not be consumed. Rollback consists of leaving the fresh
preparation unused; no upstream evidence, source, model or environment is modified.

Published semantic head `0cc1a0c` passed all four workflow runs, including 1,000
runtime tests in 391.14 seconds. This is engineering CI evidence, not source
admission or permission for an actual training run.

## Completion-only batch encoding

`faustcoder.sft_batch.encode_batch` implements the recipe's `completion-only.v1`
encoding for explicit `SupervisedExample` values: example_id, prompt, target and
the exact UTF-8 target's `sha256:` digest. It uses an explicitly supplied local
tokenizer, with `add_special_tokens=False`, and tokenizes prompt and target
separately. The resulting token boundary is part of the contract, even when
tokenizing the concatenated strings would produce different IDs. No implicit
chat template is applied; this codec targets the pilot's base-model prompts.

The immutable result supplies input_ids, attention_mask and labels. A causal
model receives labels unchanged and shifts them once internally. Prompt and
right-padding labels are -100; target and final EOS labels are supervised. EOS
may also be the explicitly configured padding ID, but genuine EOS labels remain
supervised. EOS/padding IDs inside content are refused. Vocabulary, tokenizer
and model identity must be verified through the caller's model manifest.

The builder never packs examples, truncates prompts/targets, invents an
instruction or checks semantic correctness. It rejects sequences over 512 tokens
and batches over 28 examples. The recipe's microbatch remains one. A production
pair must separately bind its prompt provenance and qualified target Example,
and pass compiler/signal checks. A matching target hash proves integrity only.
The source-preparation command still reports `instruction_pair_contract` because
this representation codec cannot establish those semantic/provenance facts.

Run the portable synthetic representation checks without Torch or model access:

```bash
python -m pytest tests/test_sft_batch.py
```

These checks cover labels and masking only. They do not establish model
compatibility, loss convergence, GPU memory use, checkpoint equality or training
authorization. Reuse the preserved Spark environment for those later probes.

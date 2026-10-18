# Runbook: DSP signal harness

T04 renders a compiled Faust program offline and writes a DSPTestReceipt
(spec §8, R-006). The worker is `faust/worker/render.mjs`. Python starts
it with the same sandbox as the compiler: `unshare --net
--map-current-user`, Node's permission model, and no network grant. The
compiler runbook describes that namespace.

Before it compiles, `render.mjs` runs the netns canary exported from
`faust/worker/netns-canary.mjs`, the same module `compile.mjs` uses.
`/proc/net/dev` must list only `lo`, and a connect must fail. The read
of `/proc/net/dev` is granted as a literal path so it is not rewritten
to the parent's pid. A failed canary exits 2 with the marker
`sandbox_canary_failed:`. Python raises `SandboxError` and writes no
DSPTestReceipt. Render starts through `run_in_sandbox`, so the
exported `unshare_executable` checks apply to that process.

## What a run fixes

| Knob | Value |
|---|---|
| Sample rate | 44100 or 48000 (D-003). A suite runs both. |
| Block size | Caller-fixed. Default 64 frames. |
| Frames | Caller-fixed and a multiple of the block size. Sine and noise default to 2048. An impulse at that default is rendered at the cap, or at the reference when the reference is longer. Cap 144000 (3 s at 48 kHz). |
| Head | Exact sample compare. Default 2048, or the whole render when that is shorter. |
| Seed | Caller-fixed integer. Default 1. It feeds the noise stimulus. |
| Stimuli | `impulse`, `sine`, `noise`, in the profile. |
| Renderer | faustwasm offline processor, float32. `-double` is rejected. |
| Buttons | 1 for the first block, then 0. Checkboxes stay at their init. |

The impulse is amplitude 1 at frame 0. The sine is 440 Hz at amplitude
0.5, from a fixed Taylor series, then rounded to float32. The noise is
xorshift64 (`x ^= x<<13; x ^= x>>7; x ^= x<<17`) from the seed, mapped
through the top 24 bits. Python writes those samples. The worker does
not recompute them. The same mono buffer is copied to every input.

## Comparison

The head is an exact prefix of the reference. Each sample passes when
`abs(cand - ref) <= atol + rtol * abs(ref)`. Default `atol` is 2e-6,
the default cited for Faust's `filesCompare` tool. Default `rtol` is
1e-5. This repo did not re-read `filesCompare`, and the relative term
is the one used by `numpy.allclose`. Both citations are INFERRED.
Near zero the absolute term still dominates. That absolute floor is
2e-6 per sample. A sample of 1e-5 against a silent reference fails
it. The coarse check below applies the same floor to a block RMS, so
one 1e-5 spike in a 64-sample block (RMS about 1.25e-6) does not fail
the coarse check.

The whole render, including the head, also gets a coarse check:
per-block RMS and spectral band energies, with the same tolerance.
Those summaries use magnitudes, so a sign flip or a small time shift
past the head can match them. Both sides are compared on the 1e-9
grid stored in the reference document, so the digest binds the values
that were judged.

An impulse reference is built at the 144000-frame cap and trimmed to
the last sample at or above `tail_threshold` (default 1e-8), plus a
64-sample margin, rounded up to the block size. The tail gate scans
every sample of that reference. A silent gap before a delay or echo
is still late energy, and the candidate render has to cover it. A
tail that is still hot at the cap is left to the coarse check. Sine
and noise are sustained and are not tail-gated. A missing reference
fails a profile that requires one.

A receipt marked `reward_graded` forces `reject_nonfinite` and
`require_reference` on before the render. With an impulse reference,
`max_frames` below the 144000 block-aligned cap raises `ValueError`.
The harness does not raise that cap. `head_frames` stays the pinned
profile value (default 2048). The exact signed comparison covers the
whole render up to `max_frames`, including sign and timing past
`head_frames` (spec §23 A4). `metrics.comparison` is
`reward-graded-signed-full` and `signed_frames` equals that render.
Coarse RMS and band checks are recorded and are not a pass or a fail
on a reward-graded run. A receipt that only signs `head_frames` is
not a reward. `thresholds.reward_graded` is always present, so the
reproducible digest changes with the mark. `purpose` is `reward` or
`diagnostic`. ADR-0006 is in force in reward code. `grade_receipt`
(spec §23) accepts a reward receipt only when the profile digest is
in `REWARD_PROFILES`, both digests recompute, and the comparison is
that full signed window. Anything else is `Ungraded` and the reward
is absent, not 0. A reference-free or non-finite run cannot pass
the mark.

`reject_dc` is skipped when the reference carries the same DC. A
different constant, or a candidate that is DC against a moving
reference, still fails. A reference-free DC check is unchanged.

The reference document carries its own sample rate, block size, frame
count, seed and stimulus names. A comparison is refused when any of
those differ from the profile. A non-finite reference sample is
refused when the reference is loaded. A non-finite candidate sample
always fails the comparison. `reject_nonfinite` only governs the
standalone NaN and Inf counts.

CPU wall time is stored only when the caller marks a promotion
candidate, and it is the only field left out of the reproducible
digest.

## Metrics

Counts of NaN, Inf and float32 denormals are exact. RMS, peak, absolute
error and spectral band magnitudes are integers on a 1e-9 grid.
`sample_sha256` is the little-endian float32 bytes, channel then frame.

A legal one-pole (`+ ~ *(0.5)`) decays into denormals. Those samples
are counted and do not fail unless the profile sets
`max_denormal_count`. Silence, DC, clipping, non-finite output and a
channel mismatch fail when the profile enables them. The default
profile enables silence, DC, clipping, non-finite output and the
reference comparison.

## Receipts

The payload validates against `dsp-test-receipt.schema.json`. Frames
and stimulus names are inside `metrics`, because the accepted contract
has no frame field. That placement is INFERRED; see
[data-model.md](../../specs/001-faustcoder/data-model.md). The envelope
parents are the compiler receipt and, when a reference was compared,
the reference document. Store and look up by `reproducible_digest`.
`artifact_id` still includes `cpu_duration_ms` when that field is
present.

## Libraries and fixtures

A source that imports a library raises `SignalLibrariesUnavailable`.
Pinned faustlibraries staging is T03b. This harness does not copy that
tree into the compiler filesystem.

Fixtures under `tests/fixtures/dsp/signal` are harness fixtures. They
are not Faust `tests/impulse-tests` sources, not the development suite,
and not the sealed holdout.

## Reward gates

ADR-0006 is in force in reward code (spec §23). `grade_receipt`
mints a `RewardableSignalReceipt` only for an allowlisted reward
profile. `apply_signal` takes that receipt and checks the private
mint table, so a receipt built with `object.__new__` is refused.
Diagnostic checks use `apply_diagnostic_signal` and are not rewards.
An ungraded sample is dropped from reward (`None`, not 0). A2 rows
(`infra_fault`, `harness_defect`, `unattributed`) stay in the
quarantine queue beside the artifact store (`reward-ledger/quarantine.jsonl`,
append-only). `resolve` requires an attribution (`source`, `harness`,
or `infrastructure`), who triaged the row, and when. `triaged_at` is a
timezone-aware ISO-8601 timestamp and is not in the future. `source`
re-grades the row at `parse_error` and requires non-empty evidence (a
note or a receipt reference). `harness` and `infrastructure` drop the
row and it is never scored. Replay refuses a second resolve for the
same row, and refuses an `outcome` that does not match the attribution
(`parse_error` for source, `drop` for harness or infrastructure). A row
nobody has resolved stays pending and is not a score. A pending row older than 24 hours raises the age alarm.
Those 24 hours are provisional. `rates.json` beside the log is rewritten
under a file lock, so two writers on one store cannot drop each other's
windows.

`commit_signal_check` and a reward-graded `run_signal` pass that queue
and the A7 tracker into `grade_receipt`. A compiler exit 124, 125 or
126, a deferred compiler failure, or a worker or harness crash, is
graded there. An untagged exit 126 whose run still has its source is
recompiled on the same worker beside `process = _;`. The fixture
passing and the same failure reproducing is `parse_error`. The fixture
failing, or the failure not reproducing, stays `unattributed`. A JS
stack overflow and a wasm trap are structured fields on the stage that
failed. Harness prose is not a marker, and a compile warning does not
attribute a later render crash. `triaged_at` is not earlier than the
row's hold. With no ledger the reward path raises `RewardUseRefused`
and does not score the outcome. `compile_source` on its own is not a
reward consumer.

The ungraded-rate alarm uses the provisional A7 numbers and nothing
else: above 1% over a full 500-sample window, or above 2× the
known-good baseline, whichever comes first. Five ungraded samples in
500 do not alarm. Six do. The alarm re-arms after the rate recovers.
`schema_invalid`, `digest_mismatch` and `comparison_not_full` count
in that rate. A reward-graded `run_signal_suite` takes the same ledger.
Compiler exits 124, 125 and 126, and render crashes, are graded when
that suite is committed.

Reward rows are MAC'd records (D3 option H). `grade_receipt` recomputes
digests and does not take `rerun`, `known_good` or `triage`. A load
also checks the MAC and the current pins. The sampled
rerun-from-source audit is spec §26 0.3.9, before P3. The MAC'd report
records the record ids it covered and the consumed log beside it.
Truncating the report file alone does not restore an older clear line.
Not covered: restoring both the report and the consumed log to an older
snapshot, a halt whose groups were all already used (until fixed), and a
crash between the report fsync and the anchor move, which fails closed
with no repair path.
Ed25519 is later. `REWARD_PROFILES` in
`faustcoder/reward/profiles.py` is the only allowlist literal.
`profile_digest` is the only profile digest computation.

v0.2 rewards the impulse profiles `impulse-44100-v1` and
`impulse-48000-v1` only. The gates below are still not a reward
beyond those profiles.

- Controls must be swept before any reward beyond those profiles.
  This harness leaves sliders at their defaults and presses buttons
  only in the first block.
- A reference-free DC or variance check is not rewarded.
  `reject_dc` is exact zero variance. An offset on a moving signal
  gets through it, and a suite with `require_reference` false has no
  sample comparison. `grade_receipt` requires `purpose` `reward`,
  `thresholds.reward_graded` true, and the canonical profile digest
  (`test_suite_digest`) in `REWARD_PROFILES`.
- `cpu_duration_ms` is the wall time of compile plus render. It is
  informational on a promotion candidate. It is not a pass threshold
  and is not a reward term. The reproducible digest drops it.

`harness_digest` hashes `unshare_path` and `unshare_sha256` from
`unshare_identity`, plus the sha256 of `netns-canary.mjs`. The same
path and sha256 are copied onto the receipt metrics. A swapped
wrapper or canary changes the digest. Render and compile both go
through `run_in_sandbox`, which calls `unshare_executable`. The
compiler canary raises `SandboxError` before the renderer starts.

## Nonlinear suite

`nonlinear-suite-v1` is a named profile. It is diagnostic. Its digest
is not in `REWARD_PROFILES`, and v0.2 does not reward nonlinear or
time-variant tasks (D5, 2026-10-17). TaskSpec requires `effect`, one
of `linear`, `time_invariant`, `nonlinear`, `time_variant`. Only
`linear` and `time_invariant` are rewardable. A missing value, or
`Nonlinear`, `non_linear`, `time-variant`, or a tuple, is rejected.
`tag_task_unrewardable(task, reason="nonlinear")` or
`reason="time_variant"` sets that field and `test_profile.rewardable`
to the bool false. The string `"false"` is rejected.

`require_task_rewardable` is the check. `dataset_reward_row` and
`rl_batch` call it. A diagnostic render does not.
`assert_reward_allowed` still refuses the suite digest. Adding that
digest to `REWARD_PROFILES` is a later review.

The profile is 48 kHz, block 64, seed 1, 144000 frames. 144000 is a
multiple of 64. Every stimulus is that long. A shorter suite stimulus, or a
`max_frames` under 144000, raises `ValueError`. The 144000 cap is not
raised. The comparison is the signed per-sample check on every frame
(`suite-signed`). Coarse magnitude checks do not cover those samples.

| Stimulus | Signal | Level |
|---|---|---|
| `impulse` | amplitude 1 at frame 0 | full scale |
| `ess` | 20 Hz to 20 kHz, analytic Farina phase, 2.0 s, then silence | peak −6 dBFS, 10 ms raised-cosine fades |
| `sine_997_m1` | 997 Hz | peak −1 dBFS |
| `sine_997_m20` | 997 Hz | peak −20 dBFS |
| `smpte` | 60 Hz + 7 kHz, amplitude 4:1 | peak −1 dBFS |
| `noise_m12` | xorshift64, seed 1, 64-frame fade-in | RMS −12 dBFS |
| `noise_m30` | xorshift64, seed 2, 64-frame fade-in | RMS −30 dBFS |
| `dc_step` | 0 until frame 4800, 0.25 for 48000 frames, then 0 | 0.25 |

The sweep fade is 10 ms at each end of the 2.0 s sweep (96000 frames).
The unfaded passband is about 20.7 Hz to 19.3 kHz (`passband_millihz`
on the stimulus plan). The remaining 48000 frames are silence. Phase
is `2π f1 L (exp(t/L) - 1)` with `L = T / ln(f2/f1)`, not a running
sum of the instantaneous frequency. Samples are float32. The sine and
`exp` used to build them are series in this process, not libm.
`profile_digest` stays version 2 and does not include those bytes or
the compile flags. The receipt metrics record `stimulus_sha256`,
`stimulus_plan` and `compile_flags`. The two impulse digests stay the
frozen `REWARD_PROFILES` entries.

Every signal render pins `-ftz 0`, diagnostic and reward-graded. `-fm`
is refused before compile, and so is any other `-ftz`. The same source
therefore has one compiler digest on both paths.

Noise levels are RMS, not peak. The generator is uniform, so its raw
range would be a peak. A one-block fade starts at 0 and removes the
frame-0 step. The plan records `level: rms`, `rms_dbfs`, and the
resulting `peak_nano`.

THD+N (997 Hz), SMPTE IMD and the Farina inverse-filter peaks are
stored under `metrics.renders.<name>.diagnostics`. The inverse is the
time-reversed sweep times `(f2/f1)^(-t/T)`. Harmonic orders 2–5 are
read near `T ln(k) / ln(f2/f1)` before the linear peak. They are not
pass gates and they are not part of `reproducible_digest`. Per-stimulus
`render_ms` and the worker toolchain are timing and identity, and they
are dropped the same way.

`nonlinear-suite-fallback-v1` keeps four stimuli: `impulse`,
`sine_997_m1`, `sine_997_m20`, and `noise_m12`. It drops the sweep,
the twin tone, the second noise level and the DC step. It is the
cheaper fallback (4 renders, 576000 frames). It is not in
`REWARD_PROFILES` either. Build it with
`nonlinear_suite_profile(fallback=True)`.

The suite render needs more than the default 8 MiB output cap. When
the caller does not pass a limit, the harness raises the cap enough
for a float32 input and two output channels per stimulus, and it
allows 120 seconds. A limit the caller passes is left as it is.

## Cross-arch digest

Bit-exactness across x86 and ARM is required. The x86 goldens are the
DSP bank in `tests/fixtures/signal/nonlinear-x86-goldens.json`: a
biquad cascade, a feedback comb, a denormal decay (`+ ~ *(0.999)`), a
tanh/sin shaper (`tanh(x) = (exp(2x)-1)/(exp(2x)+1)`, then `sin`),
and an LFO crossfade of two delays. The tanh stage replaced a cubic
that was only named tanh. That program's sample hashes were
recomputed for the new source. The other four programs were not
re-rendered. Each program is
rendered through the eight stimuli. CI is x86 only and checks those
hashes. The ARM run is pending on the DGX Spark.

The script does not need an installed package. It puts the repo root
on `sys.path`. `python -m faustcoder.signal_cross_arch` is the same
entry when the package is already importable.

```bash
python3 scripts/signal_cross_arch.py --out /tmp/signal-arch-arm.json
python3 scripts/signal_cross_arch.py --goldens tests/fixtures/signal/nonlinear-x86-goldens.json
```

Exit 0 prints `match`. Exit 2 prints `infra_fault`. That mismatch is
an infrastructure fault, not a model penalty. Do not widen `atol` or
`rtol` to hide it. Per-arch gold references need a separate decision.
The compare uses the suite digest, the pinned flags and the
per-stimulus sample hashes of each program. A sample hash is SHA-256
of the little-endian binary32 channel bytes, in channel order. Nothing
is rewritten first. `-0.0` and `0.0` hash differently. A NaN is not
folded to one payload: distinct quiet NaN bit patterns that survive
the float32 store stay distinct, and a mismatch of those bytes is
`infra_fault`. The signed compare still treats every NaN as
non-finite. The hash is the golden identity, not the pass gate.
The document also records
Node, faustwasm and V8 versions and the stable Node flags
(`--disallow-code-generation-from-strings`, `--permission`,
`--stack-size`). Those versions are not the compare. `harness_digest`
binds the local `unshare` binary, so it is not part of the compare.
`python3 scripts/signal_cross_arch.py --status` prints
`pending-dgx-spark` on x86 when the ARM document is absent.

On x86 the denormal-decay impulse produced 56706 subnormal samples.
The worker still rendered all eight stimuli of that program in 54 ms
(`render_ms` sum). The 120 s suite cap is not approached. `wall_ms`
on that run was about 5 s and includes compile, sandbox startup and
the Python diagnostics.

## Failure disposition

| Outcome | Receipt | Candidate |
|---|---|---|
| Required check fails | `passed` false, failing metrics | `REJECTED` |
| All checks pass | `passed` true | `SIGNAL_CHECKED` |
| Sandbox, canary, worker, or compile failure | none | stays `COMPILE_CHECKED` |
| Library import | none | stays where it was |

The candidate table is
[the candidate machine](../state-machines/candidate.md).

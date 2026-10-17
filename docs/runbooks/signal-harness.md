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
The harness does not raise that cap. `head_frames` becomes the
trimmed reference length, and the exact signed comparison covers
that reference. Coarse checks cover only the samples past it.
`thresholds.reward_graded` is always present, so the reproducible
digest changes with the mark. A future grader and `apply_signal`
must take the receipt and require `thresholds.reward_graded` true
plus the canonical profile digest (`test_suite_digest`). A
reference-free or non-finite run cannot pass the mark.

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

## Reward gates (INFERRED, not wired)

Nothing in this harness turns a receipt into a reward. The gates below
are recorded so a later reward task does not treat today's checks as
sufficient.

- Controls must be swept before any reward. This harness leaves
  sliders at their defaults and presses buttons only in the first
  block. A sweep is at least the minimum, the default and the maximum
  of each control, plus a check that the UI metadata matches the
  reference.
- A reference-free DC or variance check must never be rewarded.
  `reject_dc` is exact zero variance. An offset on a moving signal
  gets through it, and a suite with `require_reference` false has no
  sample comparison. The future grader and `apply_signal` must take
  the receipt and require `thresholds.reward_graded` true plus the
  canonical profile digest (`test_suite_digest`). That bit is part
  of the receipt and of `reproducible_digest`.
- `cpu_duration_ms` is the wall time of compile plus render. It is
  informational on a promotion candidate. It is not a pass threshold
  and must not be a reward term.

`harness_digest` hashes `unshare_path` and `unshare_sha256` from
`unshare_identity`, plus the sha256 of `netns-canary.mjs`. The same
path and sha256 are copied onto the receipt metrics. A swapped
wrapper or canary changes the digest. Render and compile both go
through `run_in_sandbox`, which calls `unshare_executable`. The
compiler canary raises `SandboxError` before the renderer starts.

## Failure disposition

| Outcome | Receipt | Candidate |
|---|---|---|
| Required check fails | `passed` false, failing metrics | `REJECTED` |
| All checks pass | `passed` true | `SIGNAL_CHECKED` |
| Sandbox, canary, worker, or compile failure | none | stays `COMPILE_CHECKED` |
| Library import | none | stays where it was |

The candidate table is
[the candidate machine](../state-machines/candidate.md).

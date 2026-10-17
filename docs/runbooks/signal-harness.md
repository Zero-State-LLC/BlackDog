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
| Frames | Caller-fixed and a multiple of the block size. Default 2048. Cap 144000 (3 s at 48 kHz). |
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
Near zero the absolute term still dominates.

The whole render, including the head, also gets a coarse check:
per-block RMS and spectral band energies, with the same tolerance.
Both sides are compared on the 1e-9 grid stored in the reference
document, so the digest binds the values that were judged.

An impulse reference must fall below `tail_threshold` (default 1e-8)
in its last block. A hotter tail fails `reference_tail` unless the
render is already at the 144000-frame cap. Sine and noise are
sustained and are not tail-gated. A missing reference fails a profile
that requires one.

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
  sample comparison.
- `cpu_duration_ms` is the wall time of compile plus render. It is
  informational on a promotion candidate. It is not a pass threshold
  and must not be a reward term.

`harness_digest` hashes `unshare_path` and `unshare_sha256` from
`unshare_identity`, plus the sha256 of `netns-canary.mjs`. A swapped
wrapper or canary changes the digest. The harness does not resolve
`unshare` on its own.

## Failure disposition

| Outcome | Receipt | Candidate |
|---|---|---|
| Required check fails | `passed` false, failing metrics | `REJECTED` |
| All checks pass | `passed` true | `SIGNAL_CHECKED` |
| Sandbox, canary, worker, or compile failure | none | stays `COMPILE_CHECKED` |
| Library import | none | stays where it was |

The candidate table is
[the candidate machine](../state-machines/candidate.md).

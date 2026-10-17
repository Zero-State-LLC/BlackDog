# Runbook: DSP signal harness

T04 renders a compiled Faust program offline and writes a DSPTestReceipt
(spec §8, R-006). The worker is `faust/worker/render.mjs`. Python starts
it with the same sandbox as the compiler: `unshare --net
--map-current-user`, Node's permission model, and no network grant. The
compiler runbook describes that namespace.

## What a run fixes

| Knob | Value |
|---|---|
| Sample rate | 44100 or 48000 (D-003). A suite runs both. |
| Block size | Caller-fixed. Default 64 frames. |
| Frames | Caller-fixed and a multiple of the block size. Default 2048. |
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

The candidate is a prefix of the reference. The check is the maximum
absolute sample difference. The default tolerance is 2e-6, the default
cited for Faust's `filesCompare` tool. This repo did not re-read that
file, so the number is INFERRED. A missing reference fails a profile
that requires one. CPU wall time is stored only when the caller marks a
promotion candidate, and it is the only field left out of the
reproducible digest.

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

## Failure disposition

| Outcome | Receipt | Candidate |
|---|---|---|
| Required check fails | `passed` false, failing metrics | `REJECTED` |
| All checks pass | `passed` true | `SIGNAL_CHECKED` |
| Sandbox, worker, or compile failure | none | stays `COMPILE_CHECKED` |
| Library import | none | stays where it was |

The candidate table is
[the candidate machine](../state-machines/candidate.md).

# Dynamic paired-float32 and additional-rate diagnostics — 2026-10-23

Discrete parameter changes now pass with filter and meter state preserved.
Additional fixed-rate fixtures also pass experimental sample comparisons at
8, 32, 88.2, 96 and 192 kHz. These results do not authorize training or extend
the production sample-rate contract.

## Dynamic contract and repair

`paired_dynamic_fixture.py` generates one stateful filter graph whose coefficient
parts are selected from a bank. It does not switch among independent running
filter instances. The bank must preserve sample rate and band count. The tested
three-band bank is:

| Setting | Top Hz | Bands/octave | Tau seconds | Offset dB |
| --- | --- | --- | --- | --- |
| A | 4000 | 3 | .01 | 0 |
| B | 2500 | 2 | .02 | -3 |
| C | 6000 | 4 | .005 | 3 |

Time-varying cascades do not generally commute. The dynamic generator therefore
restores the original low-pass-before-high-pass cascade instead of using the
static repair's reordered cascade. Explicit float32 coefficient splitting and
paired state arithmetic remain in use. The independent reference evaluates
ordinary double-precision difference equations, maintaining filter histories and
meter state across each change. It does not import the paired-arithmetic code.

At both 44.1 and 48 kHz, all sine/noise/impulse cases pass for two schedules:

- 4096 frames / 64-frame blocks: B at block 8, C at 24, A at 40.
- 16384 frames / 128-frame blocks: B/C/A/C/B/A on blocks 1 through 6,
  then C at 32, B at 64 and A at 96.

That is 12 positive dynamic runs and 12 rejected references that reset state
at changes. Local verification checks schemas, source and sample hashes,
reproducible receipt digests, independently replayed reference arrays, and the
exact control events actually applied. Positive and reset-reference executions
produce identical DSP sample hashes. Worst dynamic meter error is 0.000763 dB.
The first attempt failed while binding UI metadata, before dynamic signal tests;
that failure is retained. The fix captures descriptors before normalization and
binds the observed `/input/pair_config` address.

These are discrete, block-boundary changes among three settings. Arbitrary
continuous modulation, fractional bank indices, topology changes, sample-rate
changes during execution and native signal execution are not qualified.

## Additional rates: explicit experimental boundary

The production `SignalProfile` and DSP-test receipt schemas still admit only
44.1/48 kHz. A copied diagnostic worker replaces exactly its known rate guard
with a seven-rate allowlist. An experimental profile wrapper supplies the actual
rate to the sandboxed renderer. It never creates a production DSP-test receipt
for an unsupported rate. `experimental_rate_worker.py` reproduces that exact
worker transformation and rejects unknown or already modified guards.

| Rate Hz | Top cutoff Hz | Frames/block | Worst meter error dB |
| --- | --- | --- | --- |
| 8000 | 1500 | 4096/64 | 0.000048 |
| 32000 | 4000 | 4096/64 | 0.000072 |
| 88200 | 6000 | 4096/64 and 16384/128 | 0.000036 |
| 96000 | 12000 | 4096/64 and 16384/128 | 0.000763 |
| 192000 | 16000 | 4096/64 and 16384/128 | 0.001085 |

Each row uses three bands, three bands/octave, tau=.01 and offset=0. Every profile
covers sine/noise/impulse: 24 experimental renders in total. All samples are
finite, passthrough is exact and comparisons satisfy the unchanged per-sample
absolute 2e-6 plus relative 1e-5 tolerance on serialized dB/200 values. Each
capture also rejects a shifted reference in a counterfactual comparison; those
comparisons are not extra renders. This is sample-equivalence evidence, not the
complete production signal/admission gate at these rates.

Native Faust 2.88.0 compiles the fixtures; WASM Faust 2.90.0 executes them. Sandbox
limits, library pins, production signal code and error thresholds remain
unchanged. All 36 positive sample captures were independently verified. Twenty-five
focused tests pass, including rate/topology rejection, invalid-event rejection,
no-op state preservation and experimental-worker patch guards.

## Family search, licenses and signed readiness

Screened the complete recursive `test_rec` definition from
[faust-wdf-library at 40b16916](https://github.com/droosenb/faust-wdf-library/blob/40b1691689fb733a726458d7d9217ea9d982a3a3/testing-files/functionTesting2.dsp).
Its exact source blob, all pattern alternatives, absence of external dependencies
and pinned repository MIT notice were preserved. It joins the comparison family;
no independent evaluation candidate was qualified. The repository also contains
copied routing code with its own LGPL notice, so its top-level MIT notice was not
applied indiscriminately to other files.

Adding that candidate and the seven complete dynamic/additional-rate repair
closures gives 1495 identities, 12 components and 27863 joining operations.
Edge reconstruction agrees. All seven repair closures connect to the comparison
family. TOKEN_FLOOR=40 remains provisional and H1 collective rules are unchanged.
Different schedules reuse the same source identities rather than adding duplicates.

[Helper-license issue #321](https://github.com/grame-cncm/faustlibraries/issues/321)
still has no comments. The latest `filters.lib` blob remains
`28cf26f1c45c5397b4433959b74e25d320e8234d`, with no new explicit declarations for
`_tanhalf` or `_tpt_df`. Neither helper has been cleared.

The renewed Notion search found existing project/custody records rather than
signed artifacts. All 14 public records in the bounded Spark custody search are
unchanged. Private tasks and keys were not accessed. The original readiness
manifest still has zero verified admission gates, pilot readiness false and
training authorization false. A signed T07 evidence bundle and authenticated
custodian public key remain missing; T07 stays unfrozen.

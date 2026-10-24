# Paired float32 prototype and license request — 2026-10-23

The coefficient-rounding investigation now has a passing arithmetic model and a
specific compiler obstacle. Neither establishes a production repair.

## Numerical findings

A model represents coefficients and filter states as pairs of float32 values.
TwoSum and Dekker operations round every elementary arithmetic operation to
float32. Coefficients are prepared offline in double and split into two floats;
paired states are preserved between sections. All 18 band/stimulus checks pass
the unchanged sample comparison tolerance for the two fixed-rate fixtures.
The maximum meter difference is approximately 9.10e-8 dB.

This model uses double meter smoothing to isolate filter error. It covers only
4096-frame sine, noise and impulse fixtures at 44.1/48 kHz, with fixed cutoffs.
It does not qualify arbitrary sample rates, moving cutoffs or production output.

The corresponding Faust prototype compiles but fails the real float32 signal
checks. Its maximum middle-band sine errors are 0.028205 dB at 44.1 kHz and
1.176488 dB at 48 kHz. All 13 native/signal receipts and six captured sample
arrays were verified. Audio passthrough remains exact.

A minimal compiler probe explains a compensation obstacle: Faust 2.88 compiles
the TwoSum residual expression to literal zero. Explicit finite-range barriers
preserve the residual in a second generated-code probe. The full barrier
prototype, however, times out at the standard 15-second native compilation
limit. A separately labeled 60-second diagnostic also times out, with identical
source bytes and no signal runs. Both timeout receipts were verified. No
production resource limit was raised and no successful qualification is claimed.

The barrier range is +/-1e30. Its use is exploratory and requires domain and
semantic review; it is not a meter clamp or a relaxed comparison tolerance.
Reducing compiler expression complexity while preserving compensated operations
is now a concrete next step. The original numerical failures remain recorded.

## Helper license request

With explicit owner authorization, posted
[faustlibraries issue #321](https://github.com/grame-cncm/faustlibraries/issues/321)
requesting license and author declarations for `_tanhalf` and `_tpt_df` at their
exact introduction commits and downstream pin. The connector lacked issue-write
permission; the locally authenticated GitHub CLI posted the approved text and
the issue was fetched back for verification. No license grant is inferred from
posting the request. Both helpers remain unresolved pending authority.

## Evaluation and signed readiness

Screened complete int_clip_r, relay_hysteron and bitstream_adder closures from
pinned bitDSP sources, retaining their local dependencies and ba.if where used.
All three join the comparison family. The unchanged-policy replay now contains
1,475 identities, 12 components and 27,452 joining operations; reconstruction
agrees. Full family and edge artifacts are preserved. No independent evaluation
candidate was qualified.

Readiness was replayed against its existing scope: pilot_ready=false,
training_authorized=false, and no verified admission gates. Recorded approvals
and iPhone custody remain recognized, but no signed public snapshot bundle or
trusted custodian public key has been added. T07 stays unfrozen and
TOKEN_FLOOR=40 remains provisional. No private tasks or keys were accessed.

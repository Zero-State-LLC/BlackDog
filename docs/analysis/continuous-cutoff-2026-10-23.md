# Continuous cutoff qualification and remaining gates

Twelve full spectral captures passed the paired-float32 repair against an
independent double-precision direct-form reference. Every sample updates the
cutoff. One stateful filter cascade runs, with low-pass-before-high-pass order.
There is no bank crossfade or state reset.

| Sample rate | Top cutoff | Depth | Period | Modulation rate | Captures |
| --- | --- | --- | --- | --- | --- |
| 44100 | 4000 Hz | 50% | 64 samples | 689.0625 Hz | 3 |
| 48000 | 4000 Hz | 10% | 64 samples | 750 Hz | 3 |
| 96000 | 4000 Hz | 50% | 64 samples | 1500 Hz | 3 |
| 192000 | 4000 Hz | 10% | 64 samples | 3000 Hz | 3 |

Each run uses three bands, three bands per octave, tau=0.01 s, offset=0 dB,
16384 frames, 128-frame blocks, and noise, impulse, or sine input. Cutoffs follow
a sampled sine. Coefficients and their paired/split parts are prepared offline
in double precision and read from tables every sample. This isolates recurrence
precision; it does not qualify runtime transcendental/coefficient calculations.

All twelve frozen-cutoff reference comparisons reject on the same captures.
Worst meter error is 0.00109673 dB; native compilation takes 600–655 ms and
sources are about 319 kB. Receipt schemas, source/capture hashes, reference
replay and pointwise tolerances were checked locally. The 53 focused tests pass.
A generated source above 1 MiB is refused before compilation.

Limits: evidence covers these fixed periodic trajectories and block-end meters.
It does not qualify arbitrary live controls, other periods/depths, per-sample
meter observations, all internal arithmetic bounds, or real-time CPU budgets.
Equivalence to the original dynamically switching TPT/default analyzer is not
established: a time-varying direct form and TPT realization can differ even in
double precision. See [upstream PR #303](https://github.com/grame-cncm/faustlibraries/pull/303).
The generator's accepted input range is not a qualified operating envelope.

The complete family replay contains 1503 identities, 12 components, and 28031
joining operations; reconstruction agrees. All four cutoff closures remain
comparison-connected. TOKEN_FLOOR=40 remains provisional, with unchanged family
policy. No independent evaluation candidate or admission is established.

## License research

[Issue #321](https://github.com/grame-cncm/faustlibraries/issues/321) still has
zero comments. Neither `_tanhalf` nor `_tpt_df` has a verified explicit grant.
[Contribution guidance](https://github.com/grame-cncm/faustlibraries/blob/94ed0e81df8193238a2a1420148cd387508af58f/doc/docs/contributing.md)
(blob 9f8e4277550bd1498f259540d2af3bc683d7a916) requires a per-function
license declaration for new functions. Its separate documentation-export
heuristic accepts missing declarations by library fallback; that heuristic is
not a helper-specific grant and does not change BlackDog's admission policy.

## Signing-artifact research

Expanded top-level BlackDog directory filename discovery on Spark returned only
known handoff/proposal files and two older public coordination documents.
HOLDOUT-CUSTODY.R2.md hashes to
0a2c9a39d735e0df611e467325bd3365a8737dcf2f03e5eaf2b6d9207d04a666;
the gate-audit HANDOFF.md hashes to
7dfe10b2915d761ad04351c8bf63b35edfa766cf7b845d50e04e69829b292967.
Both describe incomplete/unsigned custody and readiness, not signing artifacts.
Their old role-assignment wording is superseded by the active Notion custody
record. No private key or private holdout content was read.

Further Notion and non-GitHub-notification Gmail searches found no signed T07
bundle or trusted custodian public-key reference. The newer R3b email describes
notice/span evidence and explicitly keeps T07 unfrozen. Search coverage remains
bounded, not proof of absence across all devices or nested directories.

The actual public signed snapshot, trusted custodian public key and authenticated
trust binding are still required. The verifier also checks gate, scope digest,
and dataset snapshot digest before canonical frozen-snapshot verification.
Readiness replay remains pilot_ready=false and training_authorized=false, with
no verified gates. T07 stays unfrozen; admission remains NOT_GRANTED.

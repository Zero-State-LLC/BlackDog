# Live cutoff qualification and TPT equivalence

The paired repair passed its explicit live interpolation contract at 44100,
48000 and 192000 Hz: nine positive captures and nine frozen-cutoff reference
rejections, verified locally from production-profile receipts and sample hashes.
The maximum meter error was 0.00089407 dB. Native compilation took 1559–1615 ms;
generated sources are about 209 kB. The 63 focused local tests pass.

The control accepts 2000–6000 Hz top cutoffs, including non-grid values. It
smooths the offset from 4000 Hz each sample with explicit float32 0.99/0.01
weights, then linearly interpolates paired coefficients between 65 offline
knots. Three bands, M=3, tau=0.01 and zero meter offset are fixed. Tests use
4096 frames, 64-frame blocks, and controls at blocks 0, 8, 24 and 40 with values
2000, 6000, 2500 and 3333.33 Hz. Noise, impulse and sine were tested. These runs
are not an exhaustive operating-envelope, performance or internal-bound proof.

The first impulse negative check was ineffective because its control change
occurred after the impulse had largely decayed. Moving a change to block zero
made the frozen-cutoff counterfactual reject. Both outcomes remain in the
research artifacts; the first run is not counted as complete qualification.

## TPT equivalence failed

A separate bounded native harness compared original forced-TPT, fixed-2304-Hz
switching, and direct-form realizations in double precision with identical
controls and input samples. The meter floor was fixed to the float32 floor in
all three. TPT versus direct form fails on noise, impulse and sine; the largest
meter difference is 16.59685 dB. Switching versus direct form also fails, up to
4.33078 dB. This is a realization-level behavior difference, not a float32
rounding defect. The paired direct-form repair cannot be promoted as an
equivalent replacement for the original live TPT/default analyzer.

The production renderer refuses -double, as intended. Native comparisons used
Faust 2.88.0 and g++ with -O2 -ffp-contract=off, in isolated Spark directories
with CPU, memory, output-size and wall-time limits. A dynamic UI caption had to
be made constant before the original analyzer could compile with a live cutoff.

Original native float32 TPT passes noise and impulse against double but fails
sine. Feeding single and double filters the identical externally computed
float32 cutoff trajectory does not cure it: TPT sine error reaches 0.00280352 dB
(tolerance ratio 2.06), in channel 2 at block 59, about -97.83 dB. The switching
and direct-form paths also fail sine under that isolation. Control smoothing
alone therefore does not explain the failure; filter/meter computation remains
to be isolated and repaired while preserving TPT state semantics. No tolerance
was weakened, and native measurements are not presented as WASM receipts.

## Family and external evidence

The full replay has 1507 identities, 12 components and 28113 joining operations;
reconstruction agrees. All three live-repair closures join the comparison
family. A newly pinned dependency-free nested maxN helper from
[dariosanfilippo/maximiser](https://github.com/dariosanfilippo/maximiser)
also joins that family. No independent evaluation candidate was qualified.

The latest filters.lib blob remains 28cf26f1c45c5397b4433959b74e25d320e8234d,
with no explicit license declaration naming _tanhalf or _tpt_df.
[Issue #321](https://github.com/grame-cncm/faustlibraries/issues/321) still has
zero comments. Neither helper is cleared.

A fresh non-notification Gmail search after 2026-10-23 for BlackDog/FaustCoder
signing, custody and T07 terms returned no messages. Notion search returned
existing custody/recovery records, not a signed snapshot or trusted public-key
artifact. These are bounded searches, not proof of absence elsewhere.

Readiness replay remains pilot_ready=false and training_authorized=false, with
no verified gates. T07 is unfrozen, TOKEN_FLOOR=40 remains provisional, and
admission is NOT_GRANTED. Remaining work includes TPT-preserving numerical
repair, full live target semantics, both helper grants, independent evaluation
membership and the actual public signed snapshot/trusted custodian-key bundle.

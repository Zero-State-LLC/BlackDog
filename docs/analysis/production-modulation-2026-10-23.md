# BlackDog production-rate and modulation qualification

Production signal profiles and references now accept explicit integer rates
8000, 32000, 44100, 48000, 88200, 96000, and 192000. The default rate pair,
frozen reward profile identities, and 48 kHz nonlinear-suite requirement remain
unchanged. Unsupported rates and floating-point rate values fail closed.

Seven wire renders passed using the production renderer. Fifteen spectral
captures at the five additional rates passed through production profile and
receipt validation with the diagnostic meter-capture module. Each used 16384
frames, 128-frame blocks, and noise, impulse, or sine input. Maximum spectral
meter error was 0.001085 dB. This is bounded fixture evidence, not unrestricted
production admission or a real-time performance guarantee.

Twelve additional captures passed with a per-sample triangle modulation of
meter offset (3 dB depth, 1024-sample period) at 44.1, 48, 96, and 192 kHz.
Maximum error was 0.001109 dB. Filter coefficients stayed fixed. Continuous
cutoff/coefficient modulation, continuous time-constant modulation, and dynamic
sample-rate changes remain unqualified. The reference uses block-end meter
observations and does not establish intermediate per-sample meter accuracy.

The first rate replay failed because archive staging selected the original
capture module and omitted meter channels. Corrected staging passed. Local
render-suite execution was interrupted after missing-faustwasm failures;
runtime evidence came from isolated CPU jobs on Spark. Focused local tests
passed, and production boundary receipts were retained.

The complete family replay contains 1499 identities, 12 components, and 27947
joining operations. Reconstruction agrees. All four modulation closures join
the comparison family. TOKEN_FLOOR=40 remains provisional; no policy was weakened.

A new public candidate, dariosanfilippo/limiterStereo, was pinned by Git tree and
blob hashes. Its stdfaust dependencies still require closure and per-unit rights
review. It is not an independent evaluation candidate yet.

[Helper-license issue 321](https://github.com/grame-cncm/faustlibraries/issues/321)
remains open with zero comments. Neither helper is cleared. The fourteen public
custody records in the six previously checked Spark roots are unchanged. No
signed T07 snapshot or trusted custodian public-key artifact was found there.
Readiness replay remains pilot_ready=false and training_authorized=false, with
no verified gates. T07 stays unfrozen and admission is NOT_GRANTED.

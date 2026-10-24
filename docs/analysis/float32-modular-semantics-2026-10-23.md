# Float32 ladder and modular semantics — 2026-10-23

A separately bound protected normalized-ladder variant passes the low-pass float32 checks at cutoffs 1000, 2304 and 4000 Hz, both 44100/48000 Hz sample rates, and noise/impulse/sine stimuli: 18 positives and 18 wrong-reference controls. All 39 native/signal receipts were schema/hash verified. This sweep uses the unchanged production signal module and worker. It replaces the two tf2s implementation bodies with calls to the pinned tf2snp implementation and includes its lexical dependency closure. It is a repair candidate, not an applied production change. The original source failure remains preserved. The internal arithmetic stays float32, with -ftz 0 and the existing absolute 2e-6 / relative 1e-5 comparison tolerances.

The same ladder approach does not fix end-to-end spectral sine metering: both sample rates still fail. The initial low-pass/spectral run produced 26 verified receipts. Its spectral capture is explicitly instrumented as before; meters are serialized as dB/200, so the absolute meter tolerance is 0.0004 dB. No double mode, relaxed tolerance, or changed precision floor was used. A low-pass numerical pass is not evidence of a spectral fix.

## Modular semantics

All four exact modular target byte strings were inserted unchanged into controlled helper fixtures. Fifteen bounded configurations pass 90 positive cases and 90 wrong-reference controls at both sample rates, with 195 verified native/signal receipts. Analyzer fixtures cover N=1,2,4 with distinct cutoff-dependent branch gains and independently calculated recursive output gains. Low/high-pass fixtures cover L=0, below/at/above L=2304, and L=MAX with distinguishable TPT/direct-form gains. Spectral fixtures cover tau=0.01/offset=0 and tau=0.02/offset=6, independently calculated smoothed absolute levels, reversed band labels and unchanged audio passthrough.

The first fixture run used mock gains above unity; impulse cases correctly hit the unchanged clipping guard. Those 195 receipts and failures are preserved. The rerun bounds mock gains instead of weakening guards. The verified rerun proves these tested wiring/selector/display behaviors under explicit mocked interfaces, not numerical correctness of the real elliptic helpers, dynamic parameter transitions, every legal parameter value, exact UI text, or independent human acceptance of the instruction contract.

Prompts now specify parameter order, the N=1 base case, positive domains, display bounds, and extreme selector behavior. Reconstructed full original harness hashes are unchanged. Pinned completion-only tokenizer totals are analyzer 298, spectral 408, low-pass 196 and high-pass 196; all remain within 512. The full closures remain in family screening even though the model targets are modular.

## Rights and family findings

Reconciled 43 exact dependency spans against original blob hashes, existing per-function notices and ADR-0003 D-013. All four modular targets already have pinned notices (three MIT, spectral STK-4.3). Added five missing notice entries: fir (STK-4.3), tpt_df_fmin (MIT), and maths EPSILON/MIN/MAX (LGPL-2.1-or-later, retaining training-only policy). No GPL/LGPL source text was added to the repository. An existing target notice does not clear its complete closure.

Four internal filters helpers still lack a resolved per-function/section license basis: `_tanhalf`, `_tpt_df`, `_lowpass6e` and `_highpass6e`. These remain unresolved rather than inheriting a neighboring declaration. Every closure also has training-only maths/platform dependencies; spectral additionally contains training-only linear2db. Therefore none of these complete closures is cleared for evaluation or redistribution. The repair variant's additional helpers require their own rights review.

The complete active-policy screen now contains 1464 identities, 12 components and 27232 recorded joining operations. Both full ladder closures remain comparison-connected. No component edge was removed and no independent evaluation family was claimed.

## Readiness

91 focused modular/readiness/evidence/family tests pass. Actual readiness replay remains pilot_ready=false and training_authorized=false, with zero verified admission gates. The supplied manifest contains tokenizer, saved-signal and family diagnostic references only; it supplies no signed split receipt. Operational approval to run on the owned Spark was explicitly confirmed by the user; that permission is recorded separately from cryptographic split membership or dataset admission. No private keys were sought or manufactured, no signature was synthesized, and no training was launched.

Remaining blockers are the spectral float32 failure, production qualification of the separate low-pass repair, unresolved helper rights, real dependency semantics and untested dynamic cases, comparison-connected families, and exact-scope signed split/baseline/reward/environment/model evidence. TOKEN_FLOOR=40 remains provisional and T07 unfrozen. The evidence index binds reports without promoting diagnostics into readiness authority.

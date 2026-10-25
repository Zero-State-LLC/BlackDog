# Spring predelay platform qualification and semantic boundary

The exact nearest-sample predelay target passes **60 recorded platform comparisons**: 14 each on Linux/GCC, macOS/Clang, Chromium offline AudioWorklet and Safari offline AudioWorklet, plus two live histories in each browser. The maximum absolute difference from the shared WASM reference is **9.313225746154785e-10**, within the unchanged 1e-5 absolute / 1e-4 normalized RMS bounds. All captures are finite, within the linked output ceiling and have zero guard faults. All 24 platform/rate endpoint checks place the 200 ms response at the requested sample offset.

## Exact scope

Source SHA-256: `d346cc36e816f5e12bcf1d9531d1d3e0850b05a2ed979f4809e22550b48644ab`. WASM SHA-256: `0cb560e4b433900ab76b6c4fa2012765c5a1bdd7b3741832484c29e4264e14bb`.

Seven dependency hashes match pin `2edec0537f536eaa130d42c354884d7db971663c`. Native code uses Faust 2.88.0, double DSP state and GCC/Apple Clang with contraction disabled; WASM uses Faust 2.90.0, `-double -ftz 0`. No float-delay memory transformation is applied to this target. Float32 input/control fixtures and output conversion, a 64-frame control clock and identical final guard are explicit. The native generated code, harness and executable hashes are retained.

Static checks use 0/200 ms endpoints, three-second block-rounded silent warmup and a four-second impulse at 8, 22.05, 44.1, 48, 96 and 192 kHz. Live histories last 30 seconds at 48 kHz: continuous predelay sweep with other controls default, and all seven controls alternating endpoints every 0.37 seconds. Browser callbacks contain 128 frames. This qualifies bounded replay, not hardware deadline performance, arbitrary controls, indefinite stability or iOS execution.

Safari's second sequential live context initially returned no capture. Its fresh single-case retry completed and is separately retained. The failed attempt remains incomplete; the context-lifecycle cause is not established and the harness does not yet promise reliable unattended sequential live batches.

## Semantic review found a material difference

Rounding before `de.sdelay` changes its equality-based crossfade controller decisions. Same-fixture comparisons with the original module have normalized RMS differences of **1.21899** for the predelay sweep and **0.864424** for all-control switching. Maximum differences are 0.0251952 and 0.8434004 respectively. The original all-control history attenuates 1,032 frames while the rounded-demand target attenuates zero. This is not evidence of perceptual improvement or live equivalence.

The candidate is therefore **platform-qualified within bounds, but not musically accepted as an equivalent repair**. The next bounded alternative is to preserve continuous-demand controller semantics and round only the delay-line read positions. It is not implemented or qualified by this packet. Four actual-gain eight-second original/repair audition files and a provisional technical review are retained. No independent listening approval is claimed. The separate low-rate Q contrast question remains open.

## Rights, families and signed readiness

The [author license issue](https://github.com/monodon-monoceros/modal_spring_reverb/issues/1) remains open with zero comments at this check; no permission grant is recorded. The previous full graph remains 4,685 identities / 44 components. Its latest 22 source files were deduplicated and audited as comparison-connected; the new platform builds remain derivatives of the spring source. A Context.dev follow-up returned known repository leads, including the already inventoried DSP course and FaustMod; no new independent family was qualified.

Fresh checks of the five known public Spark custody directories found no matching signature/public-key filenames. The known Notion custody page remains unverified with blank body and no artifact reference. These are bounded checks, not a global absence claim. Current readiness replay remains `pilot_ready=false`, `training_authorized=false`, `verified_gates=[]`. No admission gate is cleared by this separate target's diagnostics.

## Evidence

- `spring-predelay-platform-review/platform-comparison.json`: all captures, numeric results, endpoint checks and platform receipts.
- `spring-predelay-platform-review/fixtures.json`: input/control/reference hashes and fixed tolerance.
- `spring-predelay-platform-review/SEMANTIC-REVIEW.md`: provisional disposition and next repair boundary.
- `spring-predelay-platform-review/semantic-ab-analysis.json`: original/repair characterization.
- `spring-predelay-platform-review/readiness-with-diagnostics.json`: separate target scope and unchanged readiness.
- `spring-predelay-platform-hashes.json`: immutable packet inventory after completion.

External evidence remains outside Git. The adjacent hash inventory binds the 205 retained packet files; raw capture availability is not implied by the inventory.

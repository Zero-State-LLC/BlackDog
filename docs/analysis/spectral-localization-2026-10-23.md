# Spectral error localization and helper lineage — 2026-10-23

The spectral float32 failure is localized to the middle band in the tested three-band configuration, not audio passthrough. All 48 captured float32 sample arrays were hashed back to the verified signal receipts. Audio passthrough is byte-exact. For the original source, the largest middle-band difference is 2.09198 dB at 44.1 kHz and 6.66101 dB at 48 kHz, near the final blocks where the independent reference is approximately -134 to -138 dB. The protected ladder reduces these maxima to 0.40210 and 2.86814 dB but does not pass. Low/high-band errors are much smaller. These are instrumented meters, serialized as dB/200; physical dB differences are reported here, not normalized audio units.

Tested all six high-pass biquad section permutations against the same independent reference, float32 precision and fixed tolerances. None passes. Their middle-band maximum differences span approximately 2.08–2.67 dB at 44.1 kHz and 6.66–8.01 dB at 48 kHz. The original and ladder capture runs yield 26 verified native/signal receipts, and the permutation sweep yields 78. All failed variants are preserved. No production filter, meter floor or comparison tolerance was changed. This rules out section order as a sufficient repair for these cases; it does not establish that every possible float32 implementation must fail.

## Two helper notices resolved by exact lineage

Public upstream commit [37ac4eec](https://github.com/grame-cncm/faustlibraries/commit/37ac4eec79e5e8e4965aa7ad01e2f2fc465df204) extracted the lowpass6e and highpass6e bodies into parameterized helpers. The parent commit is 25e5f9317ecf5567c9b1cf3bcad57b9edd47db3b; its filters.lib Git blob is 7ef14eee77f1e4829c1b5bcb2208fdb3efc6dd3e. The parent blob identity was verified locally.

After substituting the helper signature and its section parameter t2 with the original tf2s calls, each current helper body is byte-identical to its explicitly STK-4.3-licensed predecessor. Added two INFERRED notice entries under the existing delegated D-013 policy, with named reviewer and exact transformations in elliptic-helper-lineage-2026-10-23.json. This is a source-derivation finding, not an assumption that neighboring functions share a license. No upstream code was copied into the repository.

The unresolved helper list is now `fi._tanhalf` and `fi._tpt_df`. Every complete closure still contains training-only maths/platform code, and spectral also contains training-only linear2db. These notices therefore do not establish evaluation/redistribution eligibility for the full closures or dataset admission.

## Verification and readiness

91 focused modular/readiness/evidence/family tests pass. Pinned markdownlint-cli2 0.23.2 passes all 81 Markdown files locally. Corrected the previous checkpoint's Markdown emphasis errors by formatting underscored helper names as code. Workflow lint and secret scan passed for 52c17e3; its docs failure is the corrected formatting error, and its spec/test workflow was still running when checked.

Readiness replay remains pilot_ready=false, training_authorized=false and zero verified admission gates. No qualified independent family or signed split evidence was added. The failed ordering variants are diagnostics, not newly proposed evaluation candidates. The prior full-family screen and all recorded joining edges remain unchanged. TOKEN_FLOOR=40 stays provisional and T07 stays unfrozen.

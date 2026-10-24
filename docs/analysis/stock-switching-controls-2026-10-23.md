# Stock switching and broader live-control qualification

Admission remains NOT_GRANTED; TOKEN_FLOOR=40 remains provisional and T07 remains unfrozen.

## Result

The paired repair now reproduces the stock analyzer's 2304 Hz TPT/direct-form selection within unchanged numerical tolerances for the tested domain. Both branches retain their own state and advance even while unselected. The direct-form branch uses the original direct-form-II realization with its cutoff clamped to at least 2304 Hz. The low-pass stage precedes the middle-band high-pass stage.

A first hybrid repaired only the TPT path and kept scalar direct form. At 48 kHz its noise and impulse captures passed, but the sine still failed with 0.0030040741 dB maximum error. Extending paired arithmetic to direct-form-II coefficients and state reduced that sine error to 0.0001668930 dB and passed the original schedule. Both results are retained.

The broader matrix passed **48 positive WASM captures and 48 frozen-cutoff rejection checks**: two realizations (TPT-only and stock-switching), two live schedules, four rates (44100, 48000, 96000, 192000), and three stimuli (noise, impulse, 440 Hz sine). Every positive/negative pair has the same DSP sample hash. Audio passthrough is exact and every captured value is finite.

| Target | Control schedule | Positive / frozen rejection | Maximum meter error (dB) | Maximum tolerance ratio |
| --- | --- | ---: | ---: | ---: |
| TPT-only | Threshold crossings | 12 / 12 | 0.000894070 | 0.5394 |
| TPT-only | Dense triangular sweep | 12 / 12 | 0.001132488 | 0.8078 |
| Stock switching | Threshold crossings | 12 / 12 | 0.000882149 | 0.5401 |
| Stock switching | Dense triangular sweep | 12 / 12 | 0.000894070 | 0.5474 |

Tolerance remains 2e-6 absolute plus 1e-5 relative on meter dB/200. A ratio at or below 1 passes; no tolerance was widened.

## Controls and independent reference

Each capture has 4096 frames and 64-sample blocks. Topology is three bands, M=3, tau=0.01, zero offset, with a 2000–6000 Hz top-cutoff control and the existing per-sample float32 0.99/0.01 smoother.

The threshold schedule sets blocks 0/8/16/24/32/40/48/56 to 2000/2400/2200/3000/2800/6000/2000/3333.33 Hz. It crosses the top filter's selector threshold and the lower crossover's threshold. The dense schedule updates all 64 blocks, stepping by 250 Hz through two triangular sweeps from 2000 to 6000 and back. Meter values are captured at block end, not every sample.

`switching_spectral_reference.py` independently implements the TPT recurrence, direct-form-II recurrence, eager branch updates, and selection. It was cross-checked against 24 native stock-analyzer double captures under the exact float32 control trajectory. The largest normalized difference was 2.9644546e-8, including float32 reference serialization. The native double source fixes the selector at the production float32 threshold of 2304; it does not use the double compiler's default threshold of zero.

## Implementation and limits

`paired_switching_df_fixture.py` retains the full captured source closure. It pre-splits the fixed prototype constants, evaluates bilinear coefficients with paired multiply/add and quotient refinement, and carries paired values through direct-form-II feedback and numerator evaluation. TPT arithmetic remains the previously qualified paired recurrence. Both branches are selected with `fc >= 2304` as in stock code.

The final source is 9770 bytes, SHA-256 `40fa58b1ffdbb6537de120959c8ab5797f67c1dd4c4024f63674d05355310d5e`. WASM compilation used 3030–3295 ms and rendering used 39–44 ms for the stock-switching captures. TPT-only compilation used 1122–1180 ms and rendering 17–28 ms. These are bounded diagnostic timings, not a real-time performance qualification. No baseline environment, compiler limits, double-runtime guard, or signal thresholds were changed.

Qualification is limited to the stated rates, fixed topology, input amplitudes, duration, and schedules. Arbitrary modulation, exact threshold-edge stress, longer state histories, other topology/rate combinations, and real-time integration remain unqualified. Finite-domain barriers retain their +/-1e30 intermediate limitation. This establishes numerical behavior for the tested stock algorithm, not bitwise equality to the original failing float32 implementation.

All 79 diagnostic tests pass, including pinned native switching checkpoints, control causality, and invalid-control rejection. Source regeneration is byte-exact. Local verification checks source, runner, reference and receipt hashes; receipt schemas; applied controls; finite outputs; exact passthrough; unchanged sample tolerances; and positive/negative capture identity.

## Family independence audit

The complete hybrid and paired-switching closures both join the comparison-connected family. Full replay and reconstruction agree at 1511 identities, 12 components, and 28196 joining operations, with unchanged OR raw/canonical matching, provisional token floor, and collective H1 policy.

The audit also revisited the 117 raw units outside comparison-connected components. All are four-token aliases, below the provisional floor. Only four have recorded evaluation rights (`goertzel`, `mth_octave_analyzer_default`, `mth_octave_spectral_level_default`, `peak_envelope`); each has comparison-connected dependencies. The remaining 113 lack evaluation eligibility in the recorded inventory. All 117 current source hashes were checked against the ledger, using current top-level inventory records rather than legacy nested qualification metadata. No independent evaluation member is qualified.

## Helper licenses and signed readiness

[Helper issue #321](https://github.com/grame-cncm/faustlibraries/issues/321) has no replies. The current filters.lib blob remains `28cf26f1c45c5397b4433959b74e25d320e8234d`, with no `_tanhalf` or `_tpt_df` helper-specific license declaration. Both helper rights remain unresolved.

The 14 known public Spark custody JSON records are unchanged, and the focused recent Gmail search returned no signing/custody messages. This is a bounded search, not a claim that every device or artifact store was searched. No private holdout task or key was accessed.

Readiness replay still reports `pilot_ready=false`, `training_authorized=false`, and `verified_gates=[]` for scope `08fb16b587cd5b23f7a5be12b234dc89ae24e18ef943b3449e61ed39f4c19516`. The new family graph has not replaced that scope. Signed T07 evidence, authenticated custodian key binding, independent members, rights and the remaining admission gates are still required.

## Evidence

The isolated Spark root remains `/home/delphi/blackdog-pair-qualification-m8e1n43a`. `live_control_matrix.py MODE SCHEDULE RATE...` accepts modes `tpt`/`switch` and schedules `threshold`/`dense`; it uses the included source and reference files with the existing isolated signal harness. `native_switch_crosscheck.py` reproduces the 24 native reference checks against the retained matched-control source. The full captured closure and existing meter adapter are retained.

Local archive: `work/switch-control-evidence.tar`, SHA-256 `32e208422b170136f5892b34b7a2b0a6ad6a2aa90645da3c34a157b4f2ec80b2`. It includes the failed hybrid, repaired original schedule, all broader-matrix receipts/captures, exact source/runner/reference files, and native cross-checks. Summary JSON files accompany this note; none is a cryptographic readiness attestation.

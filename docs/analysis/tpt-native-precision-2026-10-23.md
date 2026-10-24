# Native paired TPT precision diagnosis

Admission remains NOT_GRANTED; TOKEN_FLOOR=40 remains provisional and T07 remains unfrozen.

## Result

A paired-float implementation of the original generated TPT recurrence passes all 12 native captures at 44.1, 48, 96, and 192 kHz (noise, impulse, 440 Hz sine). This preserves the TPT state update and cascade order; it does not substitute the previously qualified direct-form interpolation realization. The unchanged tolerance is 2e-6 absolute plus 1e-5 relative on meter dB/200. Audio passthrough is exact and every captured value is finite.

The original single-precision sine case still fails at 44.1 and 48 kHz. At 48 kHz, maximum meter error falls from 0.0028035208898 dB to 0.00008802309284 dB. Across the paired matrix, the largest error is 0.00088909009031 dB on the 44.1 kHz impulse and remains within the relative tolerance.

## Isolation evidence

The 27-capture precision ablation uses the same externally computed float32 cutoff trajectory for all variants. Targets change at blocks 0, 8, 24, and 40 to 2000, 6000, 2500, and 3333.33 Hz. Each sample advances the 0.99/0.01 float32 smoothing recurrence; every 64-sample block captures the final meter value. There are 4096 frames per stimulus.

Promoting the single-generated arithmetic types while retaining rounded float literals passes all three stimuli. Demoting only filter-state storage in the double realization reproduces a sine failure (0.0014198145 dB); demoting only meter-state storage passes. The double realization with float coefficient storage also passes this schedule. These experiments identify filter arithmetic/state precision as a repair target; they do not prove coefficient precision is harmless for every control trajectory.

The paired variant changes generated fRec and fTemp storage/arithmetic to two floats. Coefficient calculations remain ordinary float32, and the final log meter conversion remains float32. TwoSum/Dekker arithmetic is compiled with `-O2 -ffp-contract=off`, without fast-math. Its bounded domain does not establish safety for arbitrary overflow/subnormal inputs.

## Verification and limits

- 27 ablation captures and 36 rate-matrix captures were retrieved, SHA-256 checked, and checked for finite values and exact frame counts. The rate matrix comprises 12 double references, 12 original float32 comparisons, and 12 paired comparisons.
- Paired and original rate-matrix renders use float32 input/output/control pointers. The double reference receives the identical externally rounded cutoff trajectory. Double values in the driver are used only for reference execution or capture serialization.
- Compiler: Faust 2.88.0 generated C++, g++ with FMA contraction disabled. The double reference is the same TPT algorithm at greater precision, not an independent derivation.
- These are native diagnostics. A Faust/WASM implementation, original in-source live smoothing, broader modulation schedules, render cost, and production compiler-limit qualification remain outstanding. No production double-arithmetic guard or admission rule was changed.
- No new Faust instruction candidate was introduced by the C++ diagnostic. The existing full-closure family replay remains 1507 identities, 12 components, and 28113 joining operations. No independent evaluation member is qualified.

## External blockers rechecked

[Helper license issue #321](https://github.com/grame-cncm/faustlibraries/issues/321) has no comments. The current filters.lib blob remains `28cf26f1c45c5397b4433959b74e25d320e8234d`, with neither helper-specific license declaration. Both helper rights remain unresolved.

The bounded search of 14 known public Spark custody JSON records found no changes. The focused Gmail query for recent BlackDog/FaustCoder signing or custody evidence returned no messages, and the Notion search returned existing project records rather than a signed artifact. This is not an exhaustive search of all devices. No private holdout tasks or signing keys were accessed.

Readiness was replayed against the existing scope `08fb16b587cd5b23f7a5be12b234dc89ae24e18ef943b3449e61ed39f4c19516`: pilot_ready=false, training_authorized=false, verified_gates=[]. A signed T07 snapshot, authenticated custodian public key binding, independent members, and the remaining gate evidence are still required.

## Reproduction

The isolated Spark root is `/home/delphi/blackdog-pair-qualification-m8e1n43a`. It retains the captured complete TPT source, matched-control driver, original reference captures, and inputs from the preceding live-control run. Place the three new diagnostic files at this root, then run `tpt_precision_ablation.py ROOT` followed by `tpt_pair_rate_matrix.py ROOT` using the qualification Python environment. Both scripts apply per-process CPU, address-space, file-size, and wall-time limits. They do not modify the baseline environment.

All 63 existing diagnostic tests passed after adding the harnesses; both Python harnesses compile and the patch passes `git diff --check`.

Evidence archive SHA-256: `2d7b4cc4dfc5a0ebbac3c07a034eba02d6335dfcb95a6490ad77f5efbda881e0`.

Local full evidence is retained in `work/tpt-precision-evidence.tar`; summary JSON files include source, script, driver, header, input, and capture hashes as applicable. This bundle is diagnostic evidence, not a signed readiness receipt.

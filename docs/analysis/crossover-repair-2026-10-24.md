# Low-rate crossover repair investigation — 2026-10-24

The low-rate sine-sweep failures remain unresolved. No new float32 source is qualified and no production or readiness gate was opened. The original WASM result remains 22/24 histories passing, with unchanged tolerance abs(error) <= 2e-6 + 1e-5*abs(reference).

## Numerical isolation

Preserving the lower crossover as a high/low pair through the direct-form coefficient path improves the retained failures but does not pass:

| Variant | 44.1 kHz maximum tolerance ratio | 48 kHz maximum tolerance ratio |
|---|---:|---:|
| Previous WASM source | 2.106328053 | 1.948835612 |
| Paired lower crossover, native float32 | 1.694746710 | 1.862357591 |
| Paired lower crossover plus paired meter | 1.694746710 | 1.862357591 |
| Paired lower crossover plus low×low multiplication term | 1.694746710 | 1.862357591 |
| Modular paired TPT/DF, original float32 meter | 1.460710259 | 1.871423719 |
| Same modular float32 filters, diagnostic double meter | 1.452640037 | 1.855150470 |
| Diagnostic double modules and meter | 0.0 | not run |

All numerical histories above contain 720,000 frames and reuse the recorded chirped controls and input. The last row matches every retained 44.1 kHz stock-reference meter sample exactly. This narrows the issue to precision in the float32 implementation for that case; it does not establish a complete root cause or authorize double precision in production. Meter accumulation and the omitted low×low product do not account for the remaining worst error.

A separate coefficient probe checks 10,001 lower-crossover values at each of four rates. Its largest measured relative cotangent error is 2.4963948662709407e-14. The next unresolved question is how coefficient and state rounding propagate through the time-varying filter. Broader qualification must wait for a repair that passes these retained counterexamples.

## Compiler and modular evidence

Six full-source variants fail with bad_alloc under the retained 1 GiB address-space limit: paired TPT coefficients, direct paired tangent, unit-scaled/shorter-polynomial TPT, explicit coefficient streams, rational tangent, and general TwoSum renormalization. No limit was raised. Five audited variants compile successfully, including the standalone paired TPT module.

The modular HP, LP, and meter sources compile separately. The diagnostic driver keeps both switching branches advancing and carries both signal components between stages. Its lower-control pair is split in host double precision, so this pipeline is an isolation experiment rather than an admitted production interface. The single-source float32 candidates retain the original controller, cutoff range, finite barriers, three bands, M=3, tau=.01, and ftz=0.

The compact [7/6] rational tangent has a proved exact-arithmetic absolute approximation-error bound of 1.3075314506328461e-17 on |x| <= .428. This bound excludes float32 arithmetic error. The rational replacement did not make the full source compile within bounds and was not promoted.

Local verification recomputed all 13 native history comparisons, all 11 source/header compile-audit bindings, and the coefficient-probe error calculations. Native child limits remain 20 CPU seconds, 1 GiB address space, 16 MiB file output, and 30 seconds wall time. No new WASM qualification was attempted after the native candidates failed. Existing checkpoint source pins, worker guards, production limits, and readiness scope remain unchanged.

Repair evidence archive SHA-256: a1add507dd2afe62ea9c3830cdf9a4f741a21f293e80be900745066e612fcf5d.
Reference archive SHA-256: f1ee6a5ba5ae752eaff377d7ccee769e2b14ceee15e1e3d55eeb00d043ca06b2.

## Candidate and signed-readiness research

Two additional complete closures, crossmix and atandist, were pinned from <https://gist.github.com/SpotlightKid/7ec098b497818d40acdb7f45a9b85683/775a594ebafe7901737cf78847373548d880decb>. Both compile, but both join comparison families under the unchanged raw/canonical and collective H1 policy. Reconstruction agrees at 1526 identities, 12 components, and 28498 joining operations. Root MIT declarations are source evidence, not completed per-unit rights review; atandist also cites an external MusicDSP formula. No independent evaluation member was admitted.

Candidate archive SHA-256: 06f63d0f3901273cd8b2c2b4fe4d962ea971afc3bc2877d90fb8fd0b51e562ad.

The helper-license issue <https://github.com/grame-cncm/faustlibraries/issues/321> remains open with zero comments. The fetched filters.lib contains no exact license declaration for `_tanhalf` or `_tpt_df`. Both remain unresolved.

The bounded public Spark metadata check is byte-identical to the preceding check. Focused Gmail search returned zero messages; Notion still supplies the active Danny custody record without signed snapshot/key artifacts. No private task material or signing keys were accessed. No maintainer follow-up was sent.

Readiness replay preserves scope 08fb16b587cd5b23f7a5be12b234dc89ae24e18ef943b3449e61ed39f4c19516: pilot_ready=false, training_authorized=false, verified_gates=[]. Qualified instruction pairs, rights, independent family membership, signed T07/public-key bindings, T08/A2/GD1/environment evidence, and the scoped pilot package remain outstanding. Admission remains NOT_GRANTED.

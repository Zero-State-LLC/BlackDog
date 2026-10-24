# Ribbon Synth and exact-pair domain review — 2026-10-24

The repaired pair gained bounded-domain evidence; no independent evaluation candidate, semantic approval or signed admission was obtained. Source, target, prompt and dependency-context bytes remain unchanged.

## Repaired pair

Replayed capture hashes and independent Decimal80 full-product checks, exact float32 component agreement, structural/context reconstruction and the review-packet binding. Instrumented the separately transcribed prompt model across the same 42 signed coefficient tuples × 984 input pairs:

- 41,328 products; 826,560 observed clamp calls; **zero clamp activations**.
- Largest pre-clamp magnitude: 8,055,029,760, below the approximately 1e30 clamp threshold.
- A separate deliberately over-range value activates the instrumentation, confirming it detects saturation.
- The largest omitted low×low contribution divided by the existing `1e-30 + 1e-12 * abs(full product)` tolerance is **0.003280828814957256**.

These observations support the bounded task's clamp and omitted-term semantics. They are not a proof over arbitrary inputs, coefficients, NaNs/infinities or histories, and the omitted-term check does not bound all other rounding errors. Instrumentation is in the independent Python model; agreement with retained compiled captures was checked separately. No new native compilation or WASM history was run. Existing complete-source rights and family restrictions still apply even though the target's direct helpers use built-ins.

The original exact pair semantic-review packet remains pending. This addendum supplies evidence, not an independent human decision. `mulk-domain-check-2026-10-24.json` binds the source, input, coefficient report and model hashes.

## Ribbon Synth

Pinned [source](https://github.com/simplicit-mc/ribbon-synth/blob/a793afc33dc0b0854e5ca8a34c22e9d98a125b73/faust/mcRibbonSynth.dsp), commit `a793afc33dc0b0854e5ca8a34c22e9d98a125b73`, source Git blob `af146e17caaf28dccbe4ee04cc8d65ae5858576b`, MIT root license blob `ffb96189b85cd5129fa6f967f557f7544c35fb04`.

Extracted the complete `carrierGroup` and `modulatorGroup` closures. Each uses only the built-in `vgroup`; both belong to one project. The unchanged floor-40 provisional H1 collective policy joins both to the comparison family. Replay: **1,536 identities, 12 components, 28,702 joining operations**. Exact spans, hashes and join evidence are in `ribbon-family-2026-10-24.json`. No evaluation eligibility or independent authorship conclusion is inferred from a lexical policy join.

The active full synthesizer references `ba.lin2LogGain`, `ef.cubicnl`, `ma.PI`, `ma.log2`, `no.noise`, `os.lf_triangle`, `os.sawtooth`, `os.triangle` and `si.smoo`, and imports `stdfaust.lib`. The commented AM example is excluded from this inventory. This is a direct reference inventory, not a completed transitive closure. The full source remains unqualified pending library revision pinning, transitive dependency rights, family/lineage review and task semantics. No full-source independence claim was made.

## Other candidates

An ISC-license repository search found [DISTRHO/Fadeli](https://github.com/DISTRHO/Fadeli/blob/300e35009a7c49d33870fae871e32fb3e4b194e5/README.md) and several similarly named forks. Its README explicitly describes the bundled DSP as Faust demos/examples. At the pinned commit, [volume](https://github.com/DISTRHO/Fadeli/blob/300e35009a7c49d33870fae871e32fb3e4b194e5/dsp/dynamic-volume.dsp) and [dbmeter](https://github.com/DISTRHO/Fadeli/blob/300e35009a7c49d33870fae871e32fb3e4b194e5/dsp/analysis-dbmeter.dsp) declare Grame authorship and BSD licenses, with standard-library dependencies. The root ISC grant is not transferred to these files. This lead does not demonstrate an independent source family; upstream example provenance and complete closure review are still needed. It was not added to the family graph or admitted. Pinned blob metadata is retained in `fadeli-candidate-research-2026-10-24.json`.

## Semantic and signed readiness

PR #115 has no issue comments or reviews supplying an exact-pair semantic decision. The expanded scoped Gmail search, including “semantic review,” returned zero matches. Fetching the known Notion custody note confirms only a custody arrangement: its body is blank, native verification is “unverified,” and it contains no signed artifact or exact-pair review. These scoped results do not prove absence everywhere.

The public Spark scan is unchanged (`abe6d64818e92045320a4220dc5276e56371bef6dd0cffa73930233f5349bd25`). No private holdout content was accessed. The original-scope readiness replay still has no verified gates: **pilot_ready=false; training_authorized=false**.

Remaining admission path: independent decision on the exact semantic packet; canonical pair/context rights and admission; independent evaluation families; authenticated signed T07 snapshot/partition and trusted custodian key binding; then scoped baseline, reward/group-drop, environment/model and pilot-package evidence. Operational approval is preserved but does not create absent signatures or semantic-review receipts.

All **37 relevant tests pass**. New scripts are retained in `scripts/diagnostics/`; they use the enclosing recovery workspace and preserved evidence population. No acceptance tolerance, family policy or admission gate was relaxed.

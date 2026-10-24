# Full Ribbon Synth closure — 2026-10-24

Resolved Ribbon Synth's conservative transitive dependency closure for an explicit diagnostic library pin, verified compilation and default-control audio equivalence, and completed exact library-span rights review. **The result is not admitted and is not evaluation eligible.**

## Source and closure

[Ribbon source](https://github.com/simplicit-mc/ribbon-synth/blob/a793afc33dc0b0854e5ca8a34c22e9d98a125b73/faust/mcRibbonSynth.dsp) remains pinned to commit `a793afc33dc0b0854e5ca8a34c22e9d98a125b73`, Git blob `af146e17caaf28dccbe4ee04cc8d65ae5858576b`. The upstream source does not declare a library revision. This diagnostic explicitly selects faustlibraries `2edec0537f536eaa130d42c354884d7db971663c`; it does not claim that was the author's original environment.

The closure has **48 dependency names, 70 exact definition spans, zero unresolved references**, and a 15,693-byte assembled program. Every library blob was checked against the complete Git tree for the pin. Precision variants and overloads are retained in original order. The lexical resolver conservatively includes some inactive/internal branches; minimality is not claimed. The standard import is replaced by exact dependency environments while preserving Ribbon's source body and controls.

`ribbon-full-closure-2026-10-24.json` contains roots, transitive edges, source hashes, byte ranges and Git blob IDs without redistributing the library source text. The complete local assembled source and input manifest remain in the enclosing recovery workspace's `work/ribbon-closure/`.

## Compiler and audio evidence

On isolated Spark, both the original import-based program and the extracted closure compile with `-single -ftz 0`; generated C++ uses `-O1 -ffp-contract=off -fno-fast-math`. Both have zero audio inputs and two audio outputs.

At **44.1, 48, 96 and 192 kHz**, each program renders **24,000 frames** with default controls. All outputs are finite. The two-channel captures are **byte-identical at every rate**. Local verification independently checks the source, runner, generated-header and capture hashes, dimensions, matrix completeness and audio equality. Removing the exact `ma.PI` definition produces the expected undefined-symbol compiler failure.

The first run completed the positive comparisons but stopped because the negative-control setup used a mistyped PI literal. The exact pinned literal was corrected, and the full bounded run then passed. This was a harness setup error, not an audio discrepancy.

Each child retained limits of 20 CPU seconds, 1 GiB address space, 16 MiB file size and 30 seconds wall time. The full archive `work/ribbon-closure-evidence.tar.gz` contains sources, both generated headers/drivers/executables, all eight captures, the negative source, runner and log. Its hash is in `ribbon-closure-verification-2026-10-24.json`.

This verifies closure sufficiency and default-control equivalence for the selected pin. It does not qualify every live-control trajectory, long history, compiler version or library revision.

## Exact rights and family review

All **70 library spans** have resolved notices under delegated ADR-0003 D-013 rules. Five exact notices were added: `_phasor_imp` under the GRAME LGPL section; `_sawN_fix`, `_sawN_imp` and `_sawN_poly` under the Julius O. Smith III STK-4.3 section; `saw2ptr` under its explicit STK-4.3 declaration. Existing notices cover the other 43 dependency names. No blanket clearance of mixed `oscillators.lib` was made, and disputed documentation is excluded from cleared slices.

The library closure remains **training-only** because it includes LGPL members. This is policy eligibility, not dataset or training admission. Ribbon's MIT root provenance is preserved, and canonical admission of its complete source/context remains pending. `ribbon-closure-rights-2026-10-24.json` records all span decisions and the notice-manifest before/after hashes.

The complete assembled closure was added to the existing family replay: **1,537 identities, 12 components, 28,725 joining operations**. It joins the comparison component under the unchanged floor-40 provisional H1 collective policy. The previous wrapper results are retained. Thus neither legal-policy eligibility nor family independence permits evaluation admission.

## Repaired pair and remaining readiness

Replayed the repaired pair's original 43-span rights review against the expanded notice manifest: no rights changed and no unresolved helper licenses returned. Rebuilt its exact review packet with the current rights-report hash. Its source, prompt, target, direct dependencies, 363-token encoding and numerical scope remain unchanged. Independent semantic approval, canonical admission and signed membership remain absent; no synthetic decision or signature was created.

The public Spark custody scan is unchanged; the scoped Gmail search returned zero messages and PR #115 has no reviews. The original-scope readiness replay remains `pilot_ready=false`, `training_authorized=false`, with no verified gates. Remaining prerequisites are the independent exact-pair semantic decision, canonical pair/context admission, independent evaluation families, authenticated signed T07 snapshot/partition and trusted custodian key binding, then scoped baseline/reward/group-drop/environment/model/pilot evidence. No private holdout content was accessed.

Additional searches for MIT physical-model and BSD-2-Clause effects repositories returned no results. A broader search identified [Amati++](https://github.com/Orisu179/AmatiPP/blob/4d54e25053c0f73e31b48630bb7b4a77fdfeb2be/README.md), whose pinned tree has no standalone `.dsp` or `.lib` files and whose README credits Amati and pamplejuce. Embedded strings and submodules have not been qualified; this is an investigated lead, not a new independent evaluation source.

**61 tests pass** across rights, rights policy, exact-pair binding, modular contracts, repaired-closure binding and readiness. Diagnostic builders, runner, verifier and family/rights scripts are retained under `scripts/diagnostics/`, using the existing enclosing recovery workspace inputs. No admission gate, family policy or numerical acceptance threshold was relaxed.

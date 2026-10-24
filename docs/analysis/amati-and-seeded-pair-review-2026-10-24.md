# Amati++ and seeded exact-pair qualification — 2026-10-24

The unchanged repaired pair passes a broader bounded compiled-product probe. Candidate research did not establish a new independent evaluation family. Semantic review, canonical admission and signed readiness remain open.

## Exact repaired pair

The new probe uses deterministic seed **20261024**, **2,048 seeded float32 input pairs plus 36 boundary pairs**, and all **42 signed pinned coefficient tuples**. High parts remain within exponents -20..20; low parts are bounded by half an ulp. Boundary cases cover both signs, exponents -20/0/20, powers of two and the mantissa immediately below two. The source is unchanged (`d4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e`).

Results: **87,528 products per variant**; all six exact batches pass and all twelve corrupted batches reject. Full captures are finite and hash verified. Independent Decimal80 full-product reconstruction passes with worst tolerance ratio **0.015374864251446962** against the unchanged product tolerance `1e-30 + 1e-12 * abs(reference)`. Both float32 output components agree exactly with the independently transcribed prompt model in all 87,528 positive cases.

This is supplemental evidence for the same 363-token pair and exact dependency context. It does not replace the earlier grid, broaden the allowed exponent/coefficient domain, or establish arbitrary-input correctness. Input grids overlap; counts must not be added as distinct coverage. No new WASM histories were run. Automated and agent checks remain distinct from independent human semantic approval.

Native compilation retains `-single -ftz 0`, GCC `-O1 -ffp-contract=off -fno-fast-math`, and the existing 20 CPU second / 1 GiB address space / 16 MiB file / 30 second wall limits per child. The archive `work/mulk-seeded-evidence.tar.gz` includes all DSP variants and captures, the pinned source, runner, bounded harness and original driver dependency. Only the final batch's generated C++ header/driver/executable is retained. The archive and per-capture hashes are recorded in `mulk-seeded-verification-2026-10-24.json`; the supplemental pair binding is `seeded-exact-pair-binding-2026-10-24.json`.

## Amati++ investigation

At [commit 4d54e250](https://github.com/Orisu179/AmatiPP/tree/4d54e25053c0f73e31b48630bb7b4a77fdfeb2be), `PluginProcessor.h` initializes sourceCode to an empty string. The editor accepts caller-supplied source, and `FaustProgram.cpp` compiles that supplied string. The inspected added DSP literal is the identity effect `effect = _;`, not a standalone independent sound-design target.

The [compiler wrapper](https://github.com/Orisu179/AmatiPP/blob/4d54e25053c0f73e31b48630bb7b4a77fdfeb2be/source/Faust/FaustProgram.cpp) explicitly identifies Amati provenance and GPL-3.0-or-later licensing. A repository-level MIT listing cannot override this file header. The submodule manifest names JUCE, melatonin_inspector, clap-juce-extensions and cmake-includes. This targeted inspection found no suitable independent Faust source; it is not an exhaustive audit of every embedded string or submodule. File hashes are retained in `amati-investigation-2026-10-24.json`.

## Other leads

[TTGO Audio Synth](https://github.com/renebohne/ttgo-audio-synth/blob/2486b6463787caab3442709af24cb4200573d8a1/untitled.cpp) contains generated Faust 2.23.10 C++. Its header separates architecture and user licensing, with GPL plus exception in the architecture section. Its pinned tree contains no original `.dsp` or `.lib` file. It therefore has not supplied an independently qualified Faust target.

[Designing Sound Experiments](https://github.com/materializepath/designing-sound-experiments/tree/dacffbddca08a3b16e247fc1453657939be7049e) does contain Faust sources and an MIT root notice. The inspected bitcrush and bouncing-ball files declare `Agent Cooper + Robert`; exact human/teacher provenance and any teacher restrictions are unverified. The README's book-technique attribution does not alone imply copied code. Both files use standard-library dependencies whose full closures still need review. The bouncing-ball source also hardcodes 48,000 in its samples-per-bounce formula, so its rate semantics require an explicit sample-rate restriction or repair; the bitcrush source's integer conversion needs a precise quantization contract. Neither candidate is admitted or counted as independent.

No new family nodes were added this turn. The last full replay remains **1,537 identities / 12 components / 28,725 joins**. Rights, provenance, full closures and project/family independence must all be established before a candidate can supply evaluation data.

## Readiness

The public Spark custody scan remains unchanged. The scoped Gmail query returned zero matches, and PR #115 has no reviews supplying the exact-pair semantic decision. These are bounded searches, not proof of absence everywhere. No private holdout content was accessed.

The exact review packet and original-scope readiness were replayed: **pilot_ready=false; training_authorized=false; no verified gates**. Remaining blockers are independent exact-pair semantic approval, canonical pair/context admission, independent evaluation families, authenticated signed T07 snapshot/partition and trusted custodian key binding, followed by scoped baseline/reward/group-drop/environment/model/pilot evidence. Operational approval does not supply missing cryptographic artifacts or an independent semantic decision.

All **37 exact-pair, modular-contract, closure-binding and readiness tests pass**. New diagnostic scripts and compact reports are retained alongside the prior evidence. No source repair, prompt/context change, acceptance relaxation, policy change or admission promotion was made.

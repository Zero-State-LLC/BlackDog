# Exact repaired instruction pair — 2026-10-24

Diagnostic qualification progressed; admission remains NOT_GRANTED. No training or pilot authorization is inferred.

## Exact target and dependency context

The version 2 prompt spells out q0–q3 residual order, the supplied clamp and renormalization interfaces, and the pinned-coefficient domain. It no longer implies that clamp calls enforce float32 rounding during constant folding. The target bytes are unchanged. Prefix + target + suffix exactly reconstruct the source already verified by the 24 WASM and 24 modular histories (149 retained WASM jobs). This is a byte-identity binding to retained evidence, not a new full-history run.

- Target SHA256: `e53eb44125c66681b6d413aa7578d83cd4d3c15e81eef1ca68d8a7a5632e11da`
- Assembled source SHA256: `d4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e`
- Version 2 pair digest: `5604a3dd5bb97a94728437cc8667e03dd46bc62dcf0137105c788d16ee7a08b6`
- Prompt SHA256: `cd5fdfd76bddb0c8ea91616833191c26e8db4c9c144ffec0a283ff7bc3e01e1e`
- Prefix + suffix context SHA256: `43fab3a0e66bb720813467a32320798c86dce63d00c6e67223429359d26f0db3` (not the older marker-context digest).
- Tokenizer: 255 prompt + 107 target + EOS = **363**, below the unchanged 512-token limit.

The actual version 2 contract passes structural review. Eight changed contracts reject: altered target digest, rehashed changed context, rehashed changed target, missing interface, wrong symbol, target leaked in prompt, traversal path, and an invented admission field. The generic reviewer retains its conservative outstanding-review list; tokenizer success is recorded separately and does not grant admission.

## Direct compiled helper qualification

The bounded native probe extracted all 21 unique prototype coefficient tuples from the pinned source and included their negations: 42 tuples × 984 input pairs = **41,328 products per variant**. Inputs cover both signs, exponents -20 through 20, four mantissas and three low-part values. Six exact batches pass; all twelve corrupted batches reject (wrong pre-split coefficient parts or omitted cross terms). The assertion concerns batches, not every individual negative coefficient.

All captures are finite and hash verified. An independent 80-digit Decimal reconstruction of the complete product passes with a worst exact tolerance ratio of **0.006827347126221196**. This probe uses 1e-30 absolute + 1e-12 relative tolerance; it does not modify analyzer acceptance tolerances. A separately transcribed float32 model of the prompt and supplied renorm matches both output components exactly for all 41,328 positive products. This is agent verification, not independent human semantic approval or arbitrary-range multiplication qualification.

Faust uses `-single -ftz 0`; GCC uses `-O1 -ffp-contract=off -fno-fast-math`. Existing native child limits remain 20 CPU seconds, 1 GiB address space, 16 MiB file size and 30 seconds wall time. Each DSP source and full binary capture is retained. Only the final batch generated C++ header/driver/binary is retained; do not infer a separately archived header for every batch.

The archive hash, source hashes, input hash and capture hashes are in `mulk-constant-verification-2026-10-24.json`. Local archive: `work/mulk-constants-evidence.tar.gz`; full contract bundle: `work/presplit-pair-v2/` in the enclosing recovery workspace. The older proposal remains intact.

## Independent candidate research

No new independent evaluation candidate was admitted. The existing family graph remains 1,531 identities / 12 components / 28,602 joins; the repaired source and prior bitbus candidates remain comparison-connected.

The nominally MIT [amp-sim-faust source](https://github.com/darkoverlordofdata/amp-sim-faust/blob/df478c01ed3763795c11779faa47a4b9d0f6de37/src/amplifier.dsp) explicitly credits Temper. Exact bytes of tanh, tf2s and resonlp match [Temper](https://github.com/creativeintent/temper/blob/3795450eef941a7cc6766c526c77a7b872fd2926/Dsp/temper.dsp), whose root [license](https://github.com/creativeintent/temper/blob/3795450eef941a7cc6766c526c77a7b872fd2926/LICENSE) contains GPL-3.0 text. A root MIT label does not establish upstream eligibility. This lead needs upstream rights/full-closure review and is not admitted; this is not a legal determination. Matching span hashes and pinned Git blob identities are recorded in the companion candidate research JSON.

The fireplace_sim tree has generated C but no original Faust source. Faustus is a compiler/architecture fork, not a demonstrated independent DSP family. Neither lead supplies a qualified evaluation family.

## Signed readiness

The public Spark custody scan is unchanged, SHA256 `abe6d64818e92045320a4220dc5276e56371bef6dd0cffa73930233f5349bd25`. Its T07 material is proposal-only, unsigned and unfrozen. A bounded Gmail search after 2026-10-23 found zero non-GitHub-notification matches for BlackDog/FaustCoder with signed/custodian/public-key/T07 terms. Notion's known collection returned nine BlackDog records but no authenticated signed artifact reference. These are scoped negative searches, not proof that no artifact exists anywhere.

Readiness was replayed on the existing scope `08fb16b587cd5b23f7a5be12b234dc89ae24e18ef943b3449e61ed39f4c19516`: `pilot_ready=false`, `training_authorized=false`, no verified gates. That original scope does not automatically include the new version 2 pair.

Remaining work: independent prompt-semantic review; canonical rights/admission for this exact repaired pair and context; independent evaluation families; signed partition membership and authenticated T07 snapshot with trusted custodian public-key binding; then scope-bound baseline, reward/group-drop, environment/model and pilot-package evidence. Existing owner approval remains recorded but cannot supply absent cryptographic artifacts. The previously resolved helper licenses remain resolved; complete original closures remain training-only under the existing rights policy.

## Validation and reproduction

`tests/test_modular_pairs.py`, `tests/test_repaired_closure_review.py` and `tests/test_readiness.py`: **22 passed**. New scripts are retained under `scripts/diagnostics/`; local verifiers run from the enclosing recovery workspace with its `work/` and `outputs/` inputs. Stage `qualify_mulk_constants.py` beside the pinned source, existing native harness and native-history-soak-fivefold driver on Spark before running it. Its harness/source dependencies are deliberate; it is not a standalone production runner.

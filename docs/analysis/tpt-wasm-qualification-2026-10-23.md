# Paired TPT Faust/WASM qualification

Admission remains NOT_GRANTED. TOKEN_FLOOR=40 remains provisional; T07 remains unfrozen.

## Numerical result

The paired TPT recurrence now passes 12 Faust/WASM captures: noise, impulse, and 440 Hz sine at 44.1, 48, 96, and 192 kHz. All 12 frozen-cutoff reference comparisons are rejected, with identical DSP sample hashes between each positive and negative run. The independent Python TPT reference was cross-checked against all 12 native double captures: maximum difference is below 3e-8 in normalized output, consistent with its final float32 serialization.

| Rate | Noise maximum meter error (dB) | Impulse | Sine |
| --- | ---: | ---: | ---: |
| 44100 | 0.000107289 | 0.000894070 | 0.000482798 |
| 48000 | 0.000035763 | 0.000298023 | 0.000256300 |
| 96000 | 0.000083447 | 0.000280142 | 0.000226498 |
| 192000 | 0.000143051 | 0.000160933 | 0.000172853 |

The tolerance remains 2e-6 absolute plus 1e-5 relative on meter dB/200. Every output is finite; audio passthrough is exact. Each capture has 4096 frames, block size 64, three bands, M=3, tau=0.01, and zero meter offset. Controls change at blocks 0/8/24/40 to 2000/6000/2500/3333.33 Hz. In-source float32 0.99/0.01 smoothing advances every sample; the observed writable control is `/input/cutoff_hz`.

## What changed

`paired_tpt_fixture.py` retains the full captured dependency closure and supplies an explicit TPT analyzer. Paired values persist through the two integrator states per section, six-order cascades, and low-pass-before-high-pass middle-band path. Coefficients remain float32. The original scalar meter follows the paired-to-scalar band output. Sequential paired blocks avoid the expression expansion seen in earlier experiments. Finite-domain barriers preserve residual arithmetic under Faust optimization; the +/-1e30 intermediate domain remains a limitation.

The complete source is 7592 bytes, SHA-256 `bb4f4ba8a120d643666374037cc84dd21157372aed22fc108d5f5f6489dfa957`. Native compilation of the initial matched-control candidate took approximately 0.65 seconds. The final WASM receipts report 1121–1177 ms compilation and 17–28 ms rendering for this short fixture, within existing resource limits. These timings are observations, not a real-time performance guarantee.

The renderer is faustwasm 0.19.0 with libfaust 2.90.0, pinned libraries `2edec0537f53`, options `-ftz 0`. No double-runtime option, production precision guard, or tolerance was changed. The diagnostic meter adapter adds three observed channels and holds each meter at its block-end value; this is not sample-by-sample meter observation.

## Scope and remaining numerical work

This qualifies the explicit **forced-TPT target** for the stated rates and live-control schedule. It does not establish equivalence to the stock analyzer that switches between TPT and direct form at 2304 Hz. The earlier direct-form interpolation repair remains a distinct target. Longer captures, additional modulation schedules, topology/rate combinations, and production integration of a selected target contract remain outstanding.

The initial WASM driver stopped on a tuple-versus-list equality assertion even though every audio sample matched. The assertion was corrected; the final independent-reference run and local replay enforce sample equality, finite values, source/receipt hashes, applied controls, schema validity, and unchanged tolerances. No numerical failure was waived.

All 74 diagnostic tests pass, including new zero-input, control causality, and invalid-domain reference checks. The 24 production-shaped diagnostic receipts are not signed custody artifacts and confer no training admission.

## Family independence

The complete TPT closure joins the existing comparison-connected family. A separate public search found the primitive-only `scale` helper in [georgezachos/b259wf](https://github.com/georgezachos/b259wf/blob/7a5f94688f5f6fff3b3e51761ce8ad93627ee92b/b259wf.dsp). Its exact byte span [263,307) has no external dependencies, but it also joins the comparison family and remains rights-quarantined (repository GPL-3.0 text, no named per-unit grant). It is not an admitted evaluation candidate.

The final full replay contains 1509 identities, 12 components, and 28154 joining operations. Reconstruction agrees. The OR raw/canonical policy, provisional token floor, and collective H1 policy are unchanged. No independent evaluation member is qualified.

## License and signed-readiness research

[Helper issue #321](https://github.com/grame-cncm/faustlibraries/issues/321) still has no replies. `filters.lib` remains blob `28cf26f1c45c5397b4433959b74e25d320e8234d`, with neither `_tanhalf` nor `_tpt_df` carrying a helper-specific license declaration. Both rights blockers remain.

The 14 known public Spark custody JSON records are unchanged. The recent focused Gmail search returned no signing/custody messages; Notion returned existing project records rather than a signed snapshot. The bounded search did not access private holdout tasks or keys and does not claim exhaustive coverage of every device.

Readiness replay against scope `08fb16b587cd5b23f7a5be12b234dc89ae24e18ef943b3449e61ed39f4c19516` still reports `pilot_ready=false`, `training_authorized=false`, `verified_gates=[]`. The new family graph has not been substituted into that scope. Signed T07 evidence, an authenticated custodian public-key binding, family-disjoint members, and the other admission gates remain missing.

## Evidence and reproduction

The isolated Spark directory is `/home/delphi/blackdog-pair-qualification-m8e1n43a`. `tpt_wasm_diagnostics.py 44100 48000 96000 192000` runs there with `tpt-live.dsp`, `tpt_spectral_reference.py`, the existing isolated compiler/worker package, and prior `tpt-pair-rate-matrix` native captures. This does not modify the baseline Spark environment.

Local evidence archive: `work/tpt-wasm-evidence.tar`, SHA-256 `70b4e1498f4658675f1ab6bc13220b6d5e03ae0bd200b27f2a374d5b1c4425e7`. The archive contains the exact source, runner, independent reference, cross-check, 24 receipts, and 12 captures. Source regeneration is byte-exact. Summary reports accompany this note. Full family replay artifacts remain in `work/evaluation-search/b259-families.json` and `b259-edges.json`.

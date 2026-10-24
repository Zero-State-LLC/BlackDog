# Full Shipwright render/export qualification

The exact bounded pluck source was exercised through the pinned Shipwright public `render_spec` and `write_audio` paths at commit `eef7b31e2b82974172d8c562412069624861950a`. Twelve cases cover release, eight-note full-velocity unison, and overlapping same-pitch notes at 44.1, 48, 96 and 192 kHz. Each is 0.6 seconds at block size 64. Seconds and equivalent beats at 120 BPM produce byte-identical renders.

The only integration hook sets `dynamic_voices=False` on processors whose Faust source hash exactly matches this candidate. It runs in one diagnostic process; the upstream checkout remains unchanged. The normal track graph, master summing, final peak scaling and export writer execute from the pinned package. The source-specific hook is not proposed as a general-purpose production API.

All render outputs agree with separately rendered raw adapter output passed through the existing final scaler within 2e-6 absolute error. Natural release persists in the full graph. The normal default 0.97 ceiling and seeded TPDF dither are retained for PCM16 export. All twelve WAV files were read back, their hashes/shapes/rates/subtypes verified, and their decoded peaks remain below 0.9701. Maximum export difference from the pre-export render is 6.06095e-5 under the declared 1e-4 diagnostic bound. No new limiter or gain change was inserted into the DSP.

The verifier initially assumed identical stereo channels after export. Inspection showed the expected independent-channel dither (up to two PCM16 steps between channels), so that assertion was corrected only for decoded exports. Raw and rendered stereo equality, exact WAV/readback correspondence, finite values, peak bounds and sample error checks remain enforced. No audio was rerendered to hide a failure.

The full package needs SciPy >=1.11,<1.15. A separate Python3.12 environment uses DawDreamer0.9.0, NumPy2.2.6, SciPy1.14.1 and SoundFile0.13.1; resolved CFFI and pycparser versions and wheel hashes are recorded in the installation report and freeze file. `pip check` passes. The earlier NumPy2.3.5 diagnostic environment was not modified or relabeled.

The local archive `work/pluck-full-export-evidence.tar.gz` contains 36 raw/render/decoded captures, 12 WAV files, reports, runners, the pinned package source and license, and environment receipts. Its hash is in the compact verification receipt.

Scope limits: valid-note cases only; invalid-note preflight still needs a supported application integration rather than the diagnostic adapter alone. Effects, sidechains, return buses, nondefault ceilings and the broader application API were not qualified here. This closes the tested final-scaling/PCM export path, not all upstream integration. Interim technical recommendations remain separate from tomorrow's independent listening review. Canonical admission, independent evaluation families and signed readiness artifacts remain unresolved.

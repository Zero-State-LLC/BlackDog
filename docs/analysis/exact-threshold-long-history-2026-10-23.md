# Exact switching thresholds and longer histories

Admission remains NOT_GRANTED. TOKEN_FLOOR=40 remains provisional; T07 remains unfrozen.

## Result and repair

The final paired candidate passes 12 exact-threshold WASM captures and 12 longer-history captures across 44100, 48000, 96000 and 192000 Hz. All 24 associated counterexample comparisons are rejected. Noise, impulse and 440 Hz sine are covered at each rate. Tolerances remain 2e-6 absolute plus 1e-5 relative on meter dB/200; no compiler, memory, frame or precision guard was relaxed.

The longer history exposed failures in the preceding candidate: the 44.1 kHz sine reached 0.002074242 dB error and the 48 kHz sine reached 0.002825260 dB. The worst observed 44.1 kHz point was middle-band frame 135488, during the direct-form portion of the schedule. These failures are retained. Native stock double execution cross-checks the independent references for both rates.

`paired_precise_switch_fixture.py` replaces the direct-form coefficient path's scalar cotangent with paired evaluation of sine and cosine polynomials plus quotient refinement. The fixed prototype, direct-form-II state, TPT state, branch selection, state history, and meter are otherwise retained. The polynomial domain is limited to pi*fc/SR < 0.428 radians for the stated cutoff/rate contract. This is a coefficient-precision repair, not a change to the target transfer function or tolerance.

| Rate | Previous long sine error (dB) | Repaired long sine error (dB) |
| --- | ---: | ---: |
| 44100 | 0.002074242 (fail) | 0.000369549 (pass) |
| 48000 | 0.002825260 (fail) | 0.000345707 (pass) |
| 96000 | 0.000905991 (pass) | 0.000292063 (pass) |
| 192000 | 0.000441074 (pass) | 0.000441074 (pass) |

The largest repaired long-history error across all stimuli is 0.001275539 dB on the 192 kHz impulse and remains within the relative tolerance.

## Exact thresholds

The exact diagnostic bypasses smoothing and changes only its diagnostic slider step to zero so float32 neighbors can be supplied without grid rejection. The production-shaped live fixture retains its 0.01 Hz slider step and smoother. Two additional diagnostic meters expose top and lower selector decisions; the adapter still samples meters at block end.

The top-filter triplet is 2303.999755859375, 2304, and 2304.000244140625 Hz. With float32 crossover factor 0.7937005162239075, the lower-filter triplet is reached using top cutoffs 2902.85791015625, 2902.858154296875, and 2902.8583984375 Hz. Their rounded lower crossovers are respectively below, equal to, and above 2304 Hz. Source and reference agree exactly on both selector observations.

The 8192-frame schedule alternates 2000/6000 Hz excitation with the triplets, including returns from both directions and repeated exact equality. Equality selects direct form (`>=`). Counterexample references use the incorrect `>` rule. Noise and sine reject that rule through the original audio/meter channels alone; the decayed impulse cases rely on the explicit selector witnesses. All 12 counterexamples reject when the witness channels are included. This distinction is preserved in the evidence.

## Longer histories

The long fixture uses the existing 144000-frame cap, 64-sample blocks, and one continuously evolving DSP instance per stimulus. That is about 35 times the prior 4096-frame history: 3.27 seconds at 44.1 kHz, 3 seconds at 48 kHz, 1.5 seconds at 96 kHz, and 0.75 seconds at 192 kHz. It does not establish hours-long stability.

Controls dwell at 2000, 6000, 2304, 2902.86 and 2000 Hz at blocks 0, 128, 512, 1024 and 1536, then follow a triangular sweep every eight blocks from block 1792 to 2248. The per-sample float32 0.99/0.01 smoother is retained. Frozen-cutoff references are rejected, and each positive/negative pair has an identical DSP sample hash.

Topology remains three bands, M=3, tau=0.01 and zero offset. Captures retain exact audio passthrough and finite outputs. Final long-history receipts report 3783–4137 ms WASM compilation and 558–584 ms rendering, within existing resource limits. The existing +/-1e30 intermediate-domain restriction remains. Other rates, topologies, arbitrary control modulation and real-time integration remain unqualified; the measured offline render is not a real-time deadline test.

## Verification and provenance

All 85 diagnostic tests pass. New checks cover exact representable neighbors, equality behavior and invalid control domains. The archive retains source, runners, independent references, all original failures, targeted repair probes, final receipts/captures, and native double reference checks. Local verification regenerates the sources byte-for-byte, replays the independent references, validates receipt schemas/hashes and applied controls, and checks finite samples, exact passthrough and unchanged tolerances.

Final live source: 10942 bytes, SHA-256 `40a1342836429fb8969b6737abf226a2b5ccfe19556d1882c4ced37421c1c515`.
Final exact diagnostic source: 11095 bytes, SHA-256 `0a3d45f31bd662fabbb8ad86dc6f720867f6298ee90a60e33efa620be339648e`.

The isolated Spark root remains `/home/delphi/blackdog-pair-qualification-m8e1n43a`. `precise_long_full_diagnostics.py RATE...` reproduces long histories; `precise_exact_diagnostics.py RATE...` reproduces exact boundaries, using the retained source, metadata and reference files. The baseline environment was not changed.

## Family and readiness blockers

Full closure replay and reconstruction agree at 1514 identities, 12 components and 28259 joining operations. All three new diagnostic closures remain comparison-connected. The 117 unconnected raw aliases are unchanged: all are four-token fragments, and the four with recorded evaluation rights have comparison-connected dependencies. No independent evaluation member is qualified. Matching policy and the provisional token floor remain unchanged.

[Helper issue #321](https://github.com/grame-cncm/faustlibraries/issues/321) has no replies. The current filters.lib blob remains `28cf26f1c45c5397b4433959b74e25d320e8234d`; neither `_tanhalf` nor `_tpt_df` has a helper-specific license declaration. Both rights blockers remain.

The 14 known public Spark custody records are unchanged. The focused Gmail search returned no recent signing/custody messages; Notion returned existing project records rather than a signed snapshot. This is a bounded search, not exhaustive device coverage. No private task or key was accessed.

Readiness replay remains `pilot_ready=false`, `training_authorized=false`, `verified_gates=[]` for scope `08fb16b587cd5b23f7a5be12b234dc89ae24e18ef943b3449e61ed39f4c19516`. The diagnostic family graph has not replaced that scope. Signed T07 evidence, authenticated custodian public-key binding, source rights, family independence and the other admission gates remain required.

## Evidence archive

Local archive: `work/exact-long-evidence.tar.gz`. SHA-256: `697e70c65fea22dc575599ad907559ea3d610992859b16859cb27bcafbba7523`.
Summary JSON files accompany this note. Diagnostic receipts are not cryptographic custody attestations.

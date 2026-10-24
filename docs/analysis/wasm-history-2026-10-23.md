# Longer WASM histories through bounded checkpoint continuation

Admission remains NOT_GRANTED. TOKEN_FLOOR=40 remains provisional; T07 remains unfrozen.

The unchanged paired-cotangent fixture passes 24 checkpointed WASM histories of 720000 frames. Each history is five sandboxed jobs of 144000 frames, with the complete qualified DSP state restored between jobs. The production worker and its limits are unchanged; continuation is implemented in an isolated diagnostic worker, not a production admission path.

| History | Passing 720000-frame cases | Reset-reference rejections | Maximum meter error (dB) |
| --- | ---: | ---: | ---: |
| alternating | 12 | 12 | 0.001263618 |
| threshold-walk | 12 | 12 | 0.001263618 |

## Bounds and continuation contract

Each job retains the original 144000-frame cap, 15-second timeout, 768 MiB memory cap, 8 MiB output cap and 1 MiB source cap. Node permissions, network isolation, compiler precision and -ftz 0 remain in force. All 120 long-history jobs completed successfully under those limits.

Inspection of the pinned runtime identifies a 920-byte mono DSP region at offset zero, separate from audio buffers. The adapter copies only that region. It accepts only this exact source hash, float32 mono layout, no soundfiles, 64-sample blocks, four qualified sample rates and the existing compiler options. Each checkpoint is bound to source, rate, sequence, JSON layout and runtime metadata; its parent hash and frame positions must match. Checkpoint hashes provide diagnostic integrity, not trusted signatures or custody attestations.

A prerequisite split probe renders 72000 frames twice in separate sandboxes. Concatenating those resumed captures is byte-equivalent to the existing uninterrupted 144000-frame WASM capture for the 48 kHz threshold-walk sine case. Every one of the 24 longer histories also starts with a chunk matching its saved WASM capture exactly. Eleven adapter checks cover valid restoration and rejection of wrong source, rate, sequence, parent, frame bounds, compiler options, soundfile layout and damaged state. All 85 Python diagnostic regression tests pass.

This adapter deliberately uses private fields in the pinned faustwasm implementation. Its module hash and source are retained. A different source, runtime/layout, soundfile graph or control contract requires new qualification; this is not a general-purpose checkpoint API.

## Numerical qualification

Both previously qualified histories are repeated five times: block-by-block 2000/6000 Hz alternation, and the seeded threshold walk around both switching boundaries. The production float32 smoother is retained. Rates are 44100, 48000, 96000 and 192000 Hz; topology is three bands, M=3, tau=0.01, offset zero, with 2000–6000 Hz cutoff targets.

Noise, impulse and 440 Hz sine inputs are the prior 144000-frame buffers looped five times. The impulse repeats at each buffer boundary; the sine can have a wrap discontinuity. Processor state is restored rather than reset. Total histories are approximately 16.33, 15, 7.5 and 3.75 seconds at the four rates.

All continued meter observations pass against the independently compiled stock-double histories from the preceding native qualification. Tolerance remains 2e-6 absolute plus 1e-5 relative on dB/200. The largest observed tolerance ratio is 0.709956. The live harness checks finite outputs and exact audio passthrough for every chunk.

Local verification reconstructs all 120 checkpoint chains, checks capture and receipt hashes, source/runtime bindings, input hashes, applied controls and unchanged sandbox limits, and recomputes numerical comparisons. It also constructs a WASM reset reference by repeating each exact fresh first-chunk capture five times. All 24 reset references are rejected. The runner's separate native-reset comparisons also reject.

These results qualify checkpointed offline histories for the stated fixture and patterns. They do not establish realtime operation, hours-long stability, arbitrary controls, production checkpoint admission or a single uninterrupted browser instance beyond the existing frame cap. No coefficient source change or tolerance relaxation was needed.

## Candidate and readiness blockers

Two complete closures from [JPC's pinned SmallStone source](https://gist.github.com/jpcima/5f38a16ca61d3996bc488e330966e216/d137594f936bd1b8ffcd3b144ab0d02a6c5eaed6) were screened: lfoTriangle and sineTriWaveform. The latter includes exact pinned ba.if and ba.time definitions. Both compile, but both connect to the comparison family. Root CC0-1.0 metadata does not replace the separate dependency-rights and admission review.

An initial helper extraction matched a documentation example; it was rejected and replaced with anchored definition extraction plus exact-text assertions. The active receipts bind the corrected closures. Replay and reconstruction agree at 1522 identities, 12 components and 28418 joining operations. The same 117 raw aliases remain outside the comparison family; no new independent evaluation member qualifies.

[Helper issue #321](https://github.com/grame-cncm/faustlibraries/issues/321) still has no comments. The filters.lib blob remains 28cf26f1c45c5397b4433959b74e25d320e8234d, without new helper-specific license declarations for _tanhalf or _tpt_df. Both blockers remain.

Known public Spark custody records are unchanged. Focused Gmail research found no signing messages, and active Notion records returned only the existing Danny/iPhone custody arrangement. No signed snapshot or authenticated public-key binding was found in this bounded recheck; no private tasks or signing keys were accessed.

Readiness replay remains pilot_ready=false, training_authorized=false and verified_gates=[] for scope 08fb16b587cd5b23f7a5be12b234dc89ae24e18ef943b3449e61ed39f4c19516. Source rights, family-disjoint selected membership, signed T07 evidence and the other scoped admission gates remain unresolved. The diagnostic family graph and checkpoint hashes do not replace that scope or its signed evidence.

## Evidence and reproduction

WASM archive: work/wasm-history-evidence.tar.gz, SHA-256 4e6d7b073f01bc2d14d3db0181ce4b1d34c7a63f55942eac87741280067f37fc.
Native oracle archive SHA-256: 4ffbc1e257cf9fce1e2c70a835a3b7b3e42bd2dd6732b13e262831bca60c33ca.
Uninterrupted WASM basis archive SHA-256: 80032ee9224709224b3520e7379ee2c2f80bd694cbdfbd356ffb4a837852a31b.
Candidate archive: work/smallstone-family-evidence.tar.gz, SHA-256 426166df0de000e70c6c0665e1502a5eeb39864c28fa84a40af5c172b95890b3.

Use build_history_worker.py and wasm_history_qualification.py in the retained isolated root /home/delphi/blackdog-pair-qualification-m8e1n43a with its pinned runtime, library tree and prior captures. The --probe-only option runs the split prerequisite. Run the standalone adapter checks with node tests/diagnostics/history_checkpoint_checks.mjs and the path to the retained switch-precise-live.dsp. These scripts produce diagnostic evidence, not production readiness receipts.

# Spring predelay repair with the original crossfade controller

A separate candidate fixes nearest-sample read positions while retaining the original continuous-demand crossfade controller. It passes **60 bounded native/browser comparisons**, **24 platform/rate endpoint checks**, and **23 isolated rounding-boundary cases**. The original truncation fails 12 of those boundary cases. No production target or prior evidence packet was replaced.

## Exact target and dependencies

Source SHA-256: `e6c96f71858f15fab891f494b52559b7334ed919a35416290b721830c8ad72de`. WASM SHA-256: `254c93ba33ecd81eaf06fa31cd5dc39009da1af219be1ee2023e1b2fde5e8d7e`.

The source calls a separately named derivative of pinned `delays.lib`. Its only behavioral change is in `ddi`: `int(d0 + 0.5)` and `int(d1 + 0.5)` at the two delay-line reads. The controller body is byte-identical to the original, SHA-256 `c85568756413976e414e4206012565bf36ed43b607712dfd1fd1758d77181a6e`. The complete library notice and Faust exception are preserved and the modification is marked. Spring source rights remain unresolved.

Eight dependency files were initially supplied. The compiler reports **seven used libraries**: stdfaust, modified delays, signals, maths, platform, filters and basics. Removing the unused original `delays.lib` produces the identical WASM hash. Seven isolated omission probes, each preceded by a successful positive compile in a fresh compiler instance, all reject under the strict dependency-path check. Built-in fallback paths are rejected even when compilation succeeds. A prior shared-instance attempt is retained but not used as qualification because a missing-library abort could contaminate later probes. This establishes the bounded compiler-reported file set, not a minimal-token or rights-admitted instruction closure.

## Platform evidence

The unchanged fixture protocol uses float32 inputs/controls, double DSP state, float32 output conversion, a 64-frame control clock and the linked final-output guard. There are 14 comparisons each on Linux/GCC, macOS/Clang, Chromium offline AudioWorklet and Safari offline AudioWorklet, plus two live histories in each browser. Native generation uses Faust 2.88.0; WASM uses 2.90.0, `-double -ftz 0`; native contraction is disabled. All seven used dependency hashes, the extra supplied file, generated code and harness are bound in the packet.

Maximum absolute platform/reference error is **9.313225746154785e-10**, within the fixed 1e-5 absolute / 1e-4 normalized RMS tolerance. All captures are finite, bounded and fault-free; attenuation counts agree with their reference histories. Static endpoints cover 0/200 ms at 8, 22.05, 44.1, 48, 96 and 192 kHz after three-second block-rounded settling. All 24 platform/rate timing checks pass. Zero-delay spring impulse output is byte-identical to the original across all six rates.

The two live histories last 30 seconds at 48 kHz: continuous predelay sweep and all-control endpoint switching. Browser callbacks are 128 frames. Safari offline work paused during an app/tab interruption and completed after returning to the test tab. The test page now provides a separate user action for each live case; both Safari live cases complete without the earlier sequential-context retry. This does not establish unattended batch reliability, hardware deadlines, physical iPhone performance or iOS qualification.

## Semantic disposition

Moving rounding to the read positions avoids the previous integer-demand change to the crossfade controller. Same-fixture normalized RMS differences against the original fall from **1.21899 to 0.0508736** for the predelay sweep, and from **0.864424 to 0.106663** for all-control switching. The new all-control capture attenuates 1,140 frames versus the original's 1,032. Six actual-gain eight-second clips retain original, demand-rounded and read-rounded variants for both histories.

The engineering recommendation is to review this narrower alternative. These waveform differences are not perceptual scores, and preserving the controller does not make audio byte-identical: nearest-sample reads intentionally differ from truncation. Human musical acceptance, wider-duration/rate live histories, mobile execution and the separate low-rate Q/decay-model question remain open. The earlier candidate and its failures remain preserved.

## Family, rights and signed readiness

Both the new source and modified helper have direct raw/canonical floor-40 witnesses to their respective parents. They remain derived members, not independent evaluation candidates. The retained full-population result remains 4,685 identities / 44 components; no new full-population recount or independent family is claimed.

The [spring author issue](https://github.com/monodon-monoceros/modal_spring_reverb/issues/1) remains open with zero comments at this turn's check. No permission grant is inferred. A fresh filename-only check of five known public Spark custody directories found no signature/public-key matches. This is a bounded search, not global absence. Current readiness replay remains `pilot_ready=false`, `training_authorized=false`, `verified_gates=[]`; this separate target clears no canonical gate.

## Evidence

The external packet is `outputs/candidate-batch/spring-readround-review/`:

- `platform-comparison.json`, `fixtures.json`: sample comparisons and exact fixture/module bindings.
- `closure-check.json`, `native-bindings.sha256`, `context.json`, `repair.patch`: exact supplied/used dependency evidence and changes.
- `rounding-boundaries.json`, `zero-delay-compatibility.json`: independent impulse oracle and unchanged zero-delay checks.
- `SEMANTIC-REVIEW.md`, `semantic-ab-analysis.json`: provisional review, live differences and audition bindings.
- `family-derivative-check.json`, `license-status.json`, `public-signatures.json`, `readiness-with-diagnostics.json`: unresolved admission and authority gates.

The adjacent `spring-readround-hashes.json` indexes retained packet files. Raw captures remain outside Git; an inventory does not imply remote availability.

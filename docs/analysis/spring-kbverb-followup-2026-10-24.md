# KBVerb endurance, spring predelay repair, license outreach and family replay

The spring licensing clarification is now posted to the author-linked repository. KBVerb's generated-header repair passes 32 additional long comparisons, with a separately qualified final-output bound. Broader spring semantics exposed and led to a targeted predelay rounding repair. No new independent evaluation family or signed readiness gate is qualified.

## Spring license: alternate route succeeded

The public history of the exact pinned DSP links all five recorded file commits to `monodon-monoceros`. That account's separate project repository has issues enabled and contains the same source blob `bd0e9b057c30b85f91501f650d63603ac143caab` at `bba6fbed15950a89b09df84416557dc7a80b3f97`. After explicit authorization for this new destination, the revised clarification was posted as [issue #1](https://github.com/monodon-monoceros/modal_spring_reverb/issues/1). A read-back verifies the exact body; the last check shows the issue open with zero comments. This resolves the contact-channel blocker, not the missing license. No permission grant is inferred from authorship metadata or public availability.

## KBVerb: longer repair equivalence and output contract

Thirty-two 30-second histories compare the original header with the generated sieve at 8, 22.05, 48 and 192 kHz, scenarios 0–3, and block sizes 64 and 257. Every matched waveform is byte-identical and finite. Different blocks update controls at different times, so cross-block modulation equivalence is not claimed. Temporary waveforms were hashed and measured then removed; the exact command matrix, harness/replacement hashes and all output hashes remain in the evidence packet.

The longer tests expose a raw output peak of **3.31662917137146** at 192 kHz with controls at maximum, identically in both variants. The existing linked final-output guard passes all 32 histories at ceiling **0.8912509083747864** (-1 dBFS), with no nonfinite faults. It preserves internal resonance, uses instantaneous shared attenuation and 60 dB/s recovery, and latches faults to silence until reset. The two worst histories attenuate 4,801,155 of 5,760,000 frames, about 83.4%; perceptual transparency at those settings is not claimed. True-peak, hardware, real-time and indefinite-duration stability remain unqualified. See long comparison (`outputs/candidate-batch/spring-followup-review/kbverb-long-replay.json`), guard replay (`outputs/candidate-batch/spring-followup-review/kbverb-guard-replay.json`) and output contract (`outputs/candidate-batch/spring-followup-review/kbverb-output-contract.json`).

## Spring: broadened semantics found a real timing boundary

Forty-eight eight-second histories (eight scenarios at six rates) retain finite, dual-mono, bounded output, exact settled dry bypass, near-silent zero dwell, and midpoint-mix agreement within 1.87e-9. The original nominal 200 ms predelay is one sample short at 8, 22.05, 44.1 and 96 kHz; 48/192 kHz pass. At 8 kHz, the initial one-second warmup also ends before the 4,096-sample double-delay crossfade fully settles. Repeating with three-second settling removes the early crossfade leakage but retains the one-sample error. Original failures are preserved in broad checks (`outputs/candidate-batch/spring-followup-review/semantic/checks.json`) and settling diagnosis (`outputs/candidate-batch/spring-followup-review/predelay-repair/low-rate-settling-diagnosis.json`).

A separate candidate explicitly rounds the smoothed delay demand: `int(length*boundedSR + 0.5)` before `de.sdelay`. This changes truncation to nearest-sample semantics; it is not silently treated as the old target. All 300 modes, other controls and ranges remain unchanged. The new full module is built with the same seven pinned libraries, Faust 2.90.0, `-double -ftz 0`.

Paired original/repaired tests render 0 and 200 ms endpoints at all six rates after three-second settling. The repaired 200 ms impulse aligns exactly at the requested sample offset at every rate; zero-delay waveforms are unchanged. Twelve further six-second cold-start step/sweep histories pass finite-output, ceiling and zero-fault checks. An independent Python pass verifies their hashes, lengths, finiteness and peaks. See static checks (`outputs/candidate-batch/spring-followup-review/predelay-repair/checks.json`), live checks (`outputs/candidate-batch/spring-followup-review/predelay-repair/live-checks.json`) and new source/context binding (`outputs/candidate-batch/spring-followup-review/predelay-repair/context.json`).

This is targeted offline WASM qualification. Native equivalence, browser AudioWorklet/emulator replay, longer live histories and musical acceptance of the new target remain open. Earlier browser/simulator receipts apply only to the old module. No production module was replaced.

At 8 kHz, the original trial late-tail energy ratio is 76.9 rather than the exploratory >100 criterion; higher Q still increases late energy. A fixed ratio across rates is not an established musical requirement. The broad test remains recorded as FAIL; this observation calls for rate-dependent musical/physical-model review, not an unsupported claim that Q must be numerically “repaired.”

## Evaluation sources and full replay

Four fetched repositories contain 22 source files. One HZ synthesizer source was already retained, so the replay adds **21 source identities**, plus the previously queued ENOBSrc double expansion. Complete replay now contains **4,685 identities, 44 components and 115,032 joining operations**. All 22 screened source files and the ENOBSrc expansion are comparison-connected under the unchanged raw/canonical/collective floor-40 policy. No independent evaluation candidate qualifies. The membership-bound comparison family is `sha256:2a4573dcdf506b3b4e679c1b8f6c5c567a4c5343979cc9fe3962da28a0c2e97c`. This is a membership update, not an authorship/COPY adjudication.

The newly compiled spring repair is an explicitly derived target and is not counted as a new independent source in this replay. Root GPL notice evidence was retained for the granulator; the other three retrieved inventories have no named license file. File-level and teacher provenance admission remain open. Family evidence (`outputs/candidate-batch/spring-followup-review/full-family-screen.json`) and candidate rights inventory (`outputs/candidate-batch/spring-followup-review/candidate-rights.json`) retain the pins and decisions.

## Signed readiness

The current targeted custody-page check remains unverified with a blank body and no signed artifact reference. The known five public Spark custody/T07 directories again contain no matching signature/key artifacts. This is a bounded search, not a global absence claim. Readiness remains pilot_ready=false, training_authorized=false, verified_gates=[]. No private tasks or private keys were accessed; none were generated to substitute for custodian authority.

Remaining blockers (`outputs/candidate-batch/spring-followup-review/remaining-blockers.json`) and evidence hash inventory (`outputs/candidate-batch/spring-followup-hashes.json`) identify the exact continuation state.

## Evidence custody and scope

This checkpoint records October 24, 2026 PT diagnostics. The 221-file external packet was hash-verified during documentation synchronization. Raw captures remain outside Git; the adjacent JSON inventory preserves their paths and SHA-256 digests, not their availability to a remote reviewer. This report does not replace canonical admission receipts or independently attest their authority.

- [Evidence inventory](spring-kbverb-followup-2026-10-24.hashes.json)
- [Structured blockers](spring-kbverb-followup-2026-10-24.blockers.json)

Historical spectral and helper-license checkpoints remain scoped historical evidence; this continuation does not certify those earlier blockers resolved.

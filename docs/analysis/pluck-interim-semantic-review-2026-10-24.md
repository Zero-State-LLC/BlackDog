# Interim review of the bounded-counter pluck

**Recommendation:** retain natural decay after note-off, clean state on retrigger, the bounded epoch counter, and the explicit integer-note input contract for continued controlled evaluation. Preserve Shipwright's existing final-buffer peak scaling when integrating the repair. Eight-voice tail stealing and absolute tuning/timbre still need the planned human review.

This is the requested interim technical review by the same Codex assistant that prepared the repair. I reviewed the exact source, adapter, contract, capture evidence and sample-file integrity. No auditory listening was performed. This does not satisfy the independent semantic-review gate or grant admission.

## Decisions and evidence

- **Natural release: recommend.** The source excites on a rising gate, and the proposed host policy preserves decay after note-off. The exact-source release comparison confirms the expected retained tail. This matches a plucked-string contract.
- **Clean retrigger: recommend within the tested schedules.** New tests cover overlapping same-pitch notes, touching notes, and a retrigger one sample after onset at 48 and 192 kHz. All six mixed renders exactly equal their summed solo renders. Existing longer-history evidence remains applicable to its stated bounds.
- **Bounded epoch counter: recommend within the declared controls.** The retained delay is at most 9,597 samples; at most 4,799 binary-gate rises can occur in that span, below the 65,536-value tag cycle. Instrumented wrap tests and fresh uninstrumented host/native/WASM runs support the implementation under those assumptions.
- **Input contract: recommend.** Integer MIDI 16–119 and velocity 1–127 are explicit. Fractional pitches are rejected instead of silently truncated. The adapter validates all notes before host allocation and rejects nonfinite or unrepresentable sample offsets and collapsed durations.
- **Eight voices: conditionally retain for interim evaluation.** Exhaustion is deterministic but cuts existing tails. Numerical repeatability alone does not establish musical acceptability. Tomorrow's reviewer should assess this tradeoff using the eight-/sixteen-voice comparison.
- **Export headroom: preserve the upstream policy.** Eight full-velocity simultaneous unison notes produce raw peaks of 7.58 and 7.27 at the two tested rates. This is finite linear summation, not an instability. The pinned upstream `render_spec` applies `_limit`, which scales the entire buffer to a configurable ceiling; the documented default is 0.97. Executing that exact function on these captures yields a maximum of 0.97000003 (float32 rounding). The diagnostic adapter bypasses this export step. Integration must preserve it or explicitly review another policy; adding a new limiter inside the DSP would change the proposed instrument.

## Tomorrow's reviewer

Assess the exact candidate's release, retrigger, stealing, tuning and timbre; confirm the integer-only note domain. Account for the fact that upstream peak scaling can change whole-render loudness when a dense chord is present. Record identity, decisions and rationale against the source, adapter and contract hashes. The reviewer is not yet named and no message has been sent.

The JSON review binds the source, adapter, contract and packet hashes. The edge-check receipt binds 36 new captures and the exact pinned upstream limiter/config references. Full application/export integration remains unqualified; the limiter was exercised in isolation. Rights/admission, independent evaluation families and authenticated signed readiness artifacts remain unresolved.

Upstream references: [engine](https://github.com/dinger086/shipwright-audio/blob/eef7b31e2b82974172d8c562412069624861950a/shipwright/engine.py), [default configuration](https://github.com/dinger086/shipwright-audio/blob/eef7b31e2b82974172d8c562412069624861950a/shipwright/config.py).

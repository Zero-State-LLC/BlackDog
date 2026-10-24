# Shipwright bounded-counter pluck semantic review

Status: pending independent review. The proposed behavior is natural decay after note-off, clean retrigger, eight voices, integer MIDI16–119 and velocity1–127. The attached exact source and adapter are bound by the manifest. This packet prepares a decision; it does not grant admission or satisfy signed readiness.

Listening samples use48kHz stereo PCM16 with unchanged gain and no normalization or clipping. They are listening derivatives of hash-verified float32 captures, not replacement numerical evidence. Maximum encoding error is recorded per sample.

1. Compare `release-current.wav` and `release-natural.wav`: MIDI69 starts at0.01s and releases at0.21s. Both use the repaired source; the first uses the host's current dynamic voice policy, the second the proposed natural-release policy. Decide whether natural decay with clean retrigger is the intended instrument behavior.
2. Compare `capacity-eight.wav` and `capacity-sixteen-reference.wav`: twelve notes every60ms with40ms durations. Sixteen voices are a reference only. Decide whether eight-voice tail stealing is musically acceptable, or whether the design needs a different policy.
3. Hear `low-tail.wav` and `rapid-history.wav`: twelve-second MIDI16 decay and256 notes at25ms spacing over MIDI16/69/119/69. Assess timbre, decay and retrigger behavior. Low bass may be inaudible on phone speakers; silence on such a speaker is not evidence of failed synthesis.
4. Review the integer-only input contract and source's20–8000Hz domain. Fractional notes are rejected rather than truncated. Sample-offset overflow and durations shorter than host resolution are rejected before host allocation.

Record decisions against the exact source, adapter and contract hashes, with reviewer identity and rationale. Leave unassessed items unresolved. This same-workflow packet is not independent review. Full-range perceptual quality, qualification beyond the documented control domain, upstream integration, canonical rights/admission, independent evaluation families and authenticated signed readiness artifacts remain outstanding.

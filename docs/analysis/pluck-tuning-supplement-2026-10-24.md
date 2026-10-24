# Supplement for the independent pluck reviewer

This supplements the unchanged bounded-counter listening packet; it does not sign or approve the candidate. Exact DSP SHA-256: 74f7aef25b5c12a0e077bb407ddf491ea920fa015e3a20eef2884aacdf2a56fe.

## Tuning evidence

The stationary-loop model covers all 104 supported MIDI pitches at four rates. High-note capture estimates agree with it within 0.076 cents. Its largest predicted flattening is 2.680 cents at MIDI119/44.1 kHz. This is an observed prediction, not a chosen acceptance threshold.

Twelve fresh four-second captures extend MIDI16/24/36 at 44.1/48/96/192 kHz. All are finite, stereo-identical and bound by hashes. Two windows per capture (0.5–2.0 and 1.0–3.5 seconds) now contain at least 30 cycles. Their largest model difference is 0.0026062171984938464 cents; maximum synthetic damped-sine estimator bias is 0.0013680861080859368 cents. This resolves short-window uncertainty at these three sampled low pitches, not every low-note/control history.

Earlier late-window high-note estimates up to 13 cents were window-sensitive and should not be used as a tuning-failure claim. The pitched high-frequency mode decays much faster than the remaining low-frequency residual. Evaluate that decay/timbre musically; a numerical pitch estimate does not settle it.

## Decisions still requested

Review natural release, clean retrigger, eight-voice tail stealing, integer MIDI16–119 and velocity1–127, tuning and timbre. Preserve the existing whole-buffer peak scaling when comparing dense chords. Record reviewer identity and rationale against the exact source and original packet hashes. No decision has been entered on the reviewer's behalf.

The proposed local API now enforces source identity, eight voices, release policy, qualified rates/block size, note and timestamp validation, and finite positive explicit duration before host allocation. The historical packet's adapter is unchanged; the newer API wrapper is a separate proposed integration.

Independent semantic signoff, canonical rights/admission, independent evaluation families, and authenticated signed readiness remain pending.

# Pluck MIDI-to-frequency mapping qualification

All104 integer MIDI pitches16–119 were compared at44.1/48/96/192kHz. The saved full-velocity MIDI captures were compared with new direct monophonic renders of the same reset DSP, with frequency set to440*2^((note-69)/12), gain1, and gate held high. The MIDI onset offset was removed before comparing the remaining0.49seconds. This tests actual host output rather than an autocorrelation estimate.

All416 comparisons pass the stated2e-6 absolute plus1e-5 relative numerical tolerance. Maximum waveform difference is1.713634e-7. A separate verifier checks every case, source/runner and capture hashes, exact requested frequencies and alignment, finite stereo shapes, and recomputed errors. MIDI captures and direct captures are produced by the same pinned DawDreamer0.9.0 runtime; this is not a cross-runtime or independent-review result.

The MIDI source releases its note at0.03seconds while the direct source holds its gate high. Agreement across the comparison interval also supports natural-release behavior for these isolated-note schedules. It does not qualify overlapping-note behavior or audible stealing beyond prior receipts.

This closes the bounded host MIDI-to-frequency mapping check across the integer input domain. It does not measure the physical loop's absolute fundamental tuning, timbral acceptability, arbitrary modulation or epoch-counter lifetime. The earlier autocorrelation estimator was biased and is not reused as an acceptance gate. Independent semantic review, family independence, canonical admission and signed readiness remain open.

The local archive `work/pluck-mapping-evidence.tar.gz` contains the direct captures, report, runner, verifier and exact DSP. The compact receipt binds its hash and the prior dense MIDI report. Reproduction also requires the dense MIDI evidence archive referenced by that prior receipt. No evidence is transferred to a different source identity.

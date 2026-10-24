# Dense host note-range qualification

The unchanged reset source and time-checked adapter were exercised at every integer MIDI pitch16–119 with velocities1 and127, at44.1/48/96/192kHz. The host graph was reused, MIDI cleared between renders, and each isolated note rendered for0.5seconds. Four start/end reset-repeat controls supplement832 endpoint captures, for836 total captures. The pinned host remains DawDreamer0.9.0 with eight voices and dynamic voice removal disabled.

Every endpoint capture is finite, stereo-equal, nonzero, and peaks below1.00001. The largest difference between velocity127 audio divided by127 and velocity1 audio is9.313226e-10; the existing2e-6 diagnostic threshold was not relaxed. The repeated MIDI16/velocity1 controls are byte-identical after the full pitch sweep at every rate. The separate verifier checks the complete Cartesian-product coverage, capture hashes, shapes, measured peaks, scaling and repeat equality.

This closes the bounded nonzero-output and endpoint-scaling sweep for the declared integer note range. It does not establish pitch accuracy, perceptual timbre, every intermediate velocity, arbitrary simultaneous notes, or epoch-counter lifetime. The semantic-review bundle remains pending and its source/adapter identities remain unchanged. No canonical admission, independent evaluation family or readiness gate is granted.

The JSON receipt binds the source, adapter, runner, full raw-report hash and local archive `work/pluck-dense-evidence.tar.gz`. Raw captures and the full836-capture evidence are kept in that archive; the repository receipt is compact. Verification is same-workflow evidence, not an independent reviewer decision.

The Designing Sound provenance issue remains open with zero comments at this check. A scoped Gmail search for BlackDog/FaustCoder signed, custodian, public-key, T07 or semantic-review messages since2026-10-23 (excluding GitHub notifications) returned zero messages. These checks do not prove global absence of signed artifacts; known readiness blockers remain unresolved.

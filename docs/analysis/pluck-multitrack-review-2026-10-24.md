# Public stems and multi-track qualification

The exact bounded-pluck source and current local API binding were exercised through render_stems and render_spec at 44.1/48/96/192 kHz. Each case has two centered dry tracks with overlapping notes and natural release. No monkeypatch is used.

Eight public stem renders match separately rendered exact-adapter references after the existing per-stem peak scaling. Four full mixes match the raw reference sum followed by the existing whole-buffer peak scaling, within 2e-6. Twenty saved captures were checked for hash integrity and finite values; comparisons were recomputed from saved data.

This closes the dry two-track/stems gap. It does not qualify arbitrary effects, returns, sidechains, nondefault gains/pan, concurrent configuration mutation, or musical acceptance of voice stealing. The local API remains a proposal; independent review, canonical admission, family independence and signed readiness are pending.

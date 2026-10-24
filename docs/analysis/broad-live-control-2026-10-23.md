# Broader live-control qualification of paired coefficients

Admission remains NOT_GRANTED. TOKEN_FLOOR=40 remains provisional and T07 remains unfrozen.

The existing paired-cotangent source passes 24 further WASM captures across 44100, 48000, 96000 and 192000 Hz. Each history covers noise, impulse and 440 Hz sine. All 24 corresponding frozen-cutoff references reject, with identical DSP sample hashes between positive and negative comparisons. No source repair, tolerance change or resource-limit relaxation was needed this turn.

| History | Passing captures | Rejected frozen references | Maximum meter error (dB) | Maximum tolerance ratio |
| --- | ---: | ---: | ---: | ---: |
| alternating | 12 | 12 | 0.001251698 | 0.701468 |
| threshold-walk | 12 | 12 | 0.001263618 | 0.709143 |

## Histories and limits

Both histories retain the production float32 0.99/0.01 smoother, 64-sample blocks and 144000-frame cap. Topology remains three bands, M=3, tau=0.01 and zero offset; target cutoff remains 2000–6000 Hz.

- Alternating: 2250 events, switching the target between 2000 and 6000 Hz every block. Smoothing keeps the actual top cutoff between approximately 3051.19 and 4621.93 Hz. Both selectors stay in direct form. This qualifies sustained coefficient updates, not repeated implementation switching.
- Threshold walk: 322 events, every seven blocks, selected with Python Random seed 70823 from 2000, 6000, 2303.99, 2304, 2304.01, 2902.85, 2902.86, 2902.87 and 3333.33 Hz. Float32 control replay gives 60 top and 96 lower selector transitions, with both implementations occupied. These transition counts are model observations, not additional captured witness channels. Exact equality witnesses remain covered by the preceding exact-threshold qualification.

Each capture is one evolving DSP instance: about 3.27 seconds at 44.1 kHz, 3 seconds at 48 kHz, 1.5 seconds at 96 kHz and 0.75 seconds at 192 kHz. Arbitrary-length operation, different topologies, other cutoff domains and realtime deadlines remain unqualified. The paired polynomial domain remains pi*fc/SR < 0.428 radians and the existing +/-1e30 intermediate restriction remains.

## Verification

All 85 diagnostic tests pass. Independent local replay verifies reference arrays, finite samples, exact audio passthrough, receipt schemas and hashes, source/runner/worker bindings, applied control events, unchanged tolerances (2e-6 absolute plus 1e-5 relative on dB/200), and counterexample rejection.

Two native stock-double sine executions at 48 kHz independently cross-check the broader reference histories. Their largest normalized difference is 2.8900155491e-08. Native driver source is reproducible from the preserved base driver and event list, and its hashes are checked. Native execution is an oracle check; production float32 guards remain intact.

Live source SHA-256: `40a1342836429fb8969b6737abf226a2b5ccfe19556d1882c4ced37421c1c515` (10942 bytes, unchanged).

Archive: `work/broad-control-evidence.tar.gz`, SHA-256 `80032ee9224709224b3520e7379ee2c2f80bd694cbdfbd356ffb4a837852a31b`.
The isolated Spark root remains `/home/delphi/blackdog-pair-qualification-m8e1n43a`. Reproduce with `precise_broad_diagnostics.py alternating 44100 48000 96000 192000` and the same command with `threshold-walk`. The native script uses `broad-control-events.json`. Baseline environment and admission manifests are unchanged.

## Independent evaluation search

Three dependency-free definitions from the pinned [Christopher Arndt PM String source](https://gist.github.com/SpotlightKid/58a0ae69c94c2a2d54d363206ab82d07/3e8c61947e121f1b66f0a7c69ffced211a9f505f)—velocity_gain, key2freq and bridgeFilter—were added to the complete family replay. All are comparison-connected. The bridge filter has a raw-token-identical match with existing unit u7e04dbd3567c7a3c895d (76/76 token intersection/union). The two smaller definitions also join through the unchanged collective H1 policy. The file declares MIT License; per-unit rights were not inferred or admitted.

Replay and independent reconstruction agree at 1517 identities, 12 components and 28319 joining operations. The 117 raw unconnected aliases are unchanged. The four previously rights-eligible aliases still depend on comparison-connected definitions; none qualifies as an independent evaluation member. Full instrument closures from the additional drum/string leads were not admitted merely because their files have license declarations.

## Helper rights and signed readiness

[Helper issue #321](https://github.com/grame-cncm/faustlibraries/issues/321) remains open with zero comments. Current filters.lib blob is unchanged at 28cf26f1c45c5397b4433959b74e25d320e8234d; neither _tanhalf nor _tpt_df has a new helper-specific license declaration. Both blockers remain.

The active [Notion custody record](https://app.notion.com/p/4013e8ba2f5c8181a601f96a9cf82860) supersedes the older task-author-on-hold note: Danny authors, reviews and holds the private tasks on the iPhone; only checksums go to Spark. This clarifies roles but supplies no signed snapshot or authenticated public-key binding. Fourteen known public Spark records are unchanged, and focused Gmail research found no matching signing messages. This was a bounded search; no private task or signing key was accessed.

Readiness replay remains pilot_ready=false, training_authorized=false, verified_gates=[] for scope 08fb16b587cd5b23f7a5be12b234dc89ae24e18ef943b3449e61ed39f4c19516. The exploratory family graph does not replace that signed scope. Source rights, independent selected membership, signed T07 evidence and the remaining scoped admission gates remain unresolved. Operational approval and diagnostic receipts do not replace cryptographic custody artifacts.

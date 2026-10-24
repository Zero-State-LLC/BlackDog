# Closure replay and spectral ordering — 2026-10-23

The complete peak-envelope closure fails family independence. Replaying the
1,464 prior identities plus that closure produces 1,465 identities, 12 components
and 27,253 joining operations. Reconstruction agrees with the computed families.
The seven-member closure has no missing references, but joins the comparison
component. No joins were removed and no idiom exemptions were applied.
TOKEN_FLOOR=40 remains provisional.

## Float32 results

Five additional high-pass section orders were tested with the ladder filters and
high-pass-first analyzer branches. All five fail the fixed signal tolerances.
The 65 native/signal receipts were verified, and all 30 captured sample arrays
were matched to their receipt hashes with maximum-error statistics recomputed.

| Section order (zero-based) | Middle-band error at 44.1 kHz | At 48 kHz |
| --- | ---: | ---: |
| 021 | 0.019300 dB | 0.331533 dB |
| 102 | 0.007784 dB | 0.058448 dB |
| 120 | 0.010574 dB | 0.054383 dB |
| 201 | 0.009155 dB | 0.054121 dB |
| 210 | 0.009155 dB | 0.054133 dB |

These are maximum sine-case differences for the instrumented middle-band meter,
converted from dB/200 to physical dB. Noise and impulse cases and wrong-reference
controls are also retained in the receipts. No production source, tolerance or
meter floor changed. Reordering improves these cases but is insufficient;
dynamic-control equivalence is not established.

## Remaining helper rights

The `_tpt_df` introduction in upstream commit
[37ac4eec](https://github.com/grame-cncm/faustlibraries/commit/37ac4eec79e5e8e4965aa7ad01e2f2fc465df204)
was rechecked. The nearby MIT declaration names `tpt_df_fmin`; it does not name
`_tpt_df`. The helper adds selection behavior and a clamped direct-form cutoff.
This does not provide the exact licensed-predecessor transformation used to
clear the two elliptic helpers previously.

The `_tanhalf` introduction at
[ff4c711d](https://github.com/grame-cncm/faustlibraries/commit/ff4c711d8af452f338d5841a37b8878f98c254f6)
likewise adds a helper without an explicit declaration. Both remain unresolved.
A scoped upstream declaration or other defensible rights evidence is still
needed; proximity to a licensed function is not sufficient. Complete closures
also retain training-only dependencies, independently of these two gaps.

## Signed readiness

The existing readiness manifest was replayed: pilot_ready=false,
training_authorized=false, and zero verified admission gates. This manifest
retains its existing scope; the new diagnostic population is not silently
substituted for its dataset snapshot.

The recent Spark/Notion research found custody decisions and an unsigned T07
proposal, but no signed snapshot or trusted public-key reference in the inspected
records. The newer
[Notion custody record](https://app.notion.com/p/4013e8ba2f5c8181a601f96a9cf82860)
records Danny's iPhone custody arrangement. It does not supply cryptographic
verification material. The search was bounded, not exhaustive.

The existing split verifier requires a schema-valid public evidence bundle,
matching gate, scope and dataset snapshot digests, all referenced public objects,
and a trusted custodian public key for canonical frozen-snapshot verification.
No private task contents or private keys are required for this public verification
step. No signed inputs were fabricated and T07 remains unfrozen.

The evidence index binds local result summaries and full family edge files by
SHA-256. Numerical repair, helper rights, independent evaluation candidates and
the missing signed bundle remain open; none was promoted to a passing gate.

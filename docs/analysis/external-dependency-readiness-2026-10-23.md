# External dependencies and readiness follow-through — 2026-10-23

No admission is granted. TOKEN_FLOOR=40 remains provisional; T07 remains unfrozen.

Exact original source spans were bound for 12 peak-envelope/Goertzel helper definitions. Bounded tests passed peak_envelope at release 0 and .01 and Goertzel at N=64 at both 44.1/48 kHz. Goertzel N=16 failed the unchanged absolute 2e-6 plus relative 1e-5 tolerance at both rates. All eight wrong-reference controls were rejected. Twelve omitted-helper compilations were rejected; four samplerate-member rechecks preserved diagnostics classified as `other`, not `unbound_symbol`.

Thirteen library interfaces compiled on native Faust 2.88 and libfaust WASM 2.90 (26 successful compilations), including analyzer, spectral and elliptic-filter interfaces. Compilation establishes interface availability only. Minimal analyzer/elliptic closures, independent numerical behavior and canonical rights qualification remain unresolved. The selective pinned library archive matches all 30 preserved original blobs; a lexical import audit still reports missing nested dx7 paths and is not a complete dependency proof.

The inventory adapter now intersects recorded permissions across each candidate and its recorded dependency members. Missing permission metadata produces an empty intersection. It exposes unresolved external-member counts and unknown metadata, and always retains dependency_closure_verified=false. The formerly evaluation-marked Goertzel root has only train in its recorded member intersection. The other three roots still have unresolved external members; none is promoted.

All 62 new receipt files passed hash, schema and source-binding checks; saved signal digests and original source spans were checked. These diagnostics are outside the canonical admission manifest and clear no readiness gate.

The active graph still connects all five newly sourced candidates to comparison families. An opt-in marginal-coverage experiment appeared to disconnect silence and cross, but its emitted graph failed independent component reconstruction. That result is unverified and cannot establish independence. The experiment was not activated and no validator checks were weakened. Exact-match derived-edge attempts also failed and are not accepted evidence. Review of canonical component identity/evidence emission remains necessary before relying on this experiment.

Remaining checks: complete minimal external closures and notices; resolve the Goertzel numerical boundary without relaxing tolerance; qualify analyzer/elliptic semantics; independently adjudicate families under the reviewed FLOOR protocol; obtain canonical rights and externally trusted signed split evidence; complete approved baseline, reward/path, environment/model and training-authorization checks. No training or model downloads were performed.

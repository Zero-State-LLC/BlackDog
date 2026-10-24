# Checkpointed WASM live cutoff qualification — 2026-10-23

22/24 nonperiodic 720,000-frame histories pass against the stock-double oracle. 144 bounded WASM jobs include 120 chained continuation jobs and 24 fresh-state reset controls; all 24 resets are rejected. Maximum normalized tolerance ratio is 2.106328053; maximum meter error is 0.003111362457 dB. The criterion remains abs(error) <= 2e-6 + 1e-5*abs(reference), without relaxation.

## Coverage and limits

Two schedules × four rates (44.1, 48, 96, 192 kHz) × noise, impulse, sine. Boundary holds change just before, at, and after chunk boundaries and retain controls across 36 resumptions with no event at local block zero. The other schedule updates every block with a non-repeating chirped sinusoidal cutoff sweep. Both schedules span the complete 11,250-block history rather than replaying one control cycle five times. Each stimulus still repeats its original 144,000-frame buffer.

The exact pinned source remains 40a1342836429fb8969b6737abf226a2b5ccfe19556d1882c4ced37421c1c515: cutoff 2–6 kHz, original float32 smoother, three bands, M=3, tau=.01, offset=0, block=64, ftz=0. Every WASM invocation retains 144,000 frames, 15-second wall limit, 768 MiB memory limit, 8 MiB output limit and the original permission/network guards. The 920-byte DSP checkpoint region and worker/runtime are unchanged from the previous qualification.

Only the passing cases are numerically qualified; the failing sweep cases remain explicit blockers. These results describe the recorded offline continuations only. They do not establish arbitrary parameter ranges, real-time scheduling, unlimited histories, a production checkpoint API, or training admission.

## Verification

The local verifier recomputes every request, capture, input, reference, receipt, and checkpoint hash; replays parent/binding chains and event rebasing; checks runtime identity and resource limits; and independently recomputes numerical and reset comparisons. The stock-double driver now reads global targets for all 11,250 blocks, using the unchanged source/header and float32 external smoother. Full 720,000-frame 48 kHz sine oracle cross-checks: [{"schedule": "boundary-holds", "rate": 48000, "stimulus": "looped-sine", "frames": 720000, "max_absolute_difference": 0.0, "passed": true}, {"schedule": "chirped-sweep", "rate": 48000, "stimulus": "looped-sine", "frames": 720000, "max_absolute_difference": 0.0, "passed": true}].

Evidence archive SHA-256: f1ee6a5ba5ae752eaff377d7ccee769e2b14ceee15e1e3d55eeb00d043ca06b2. Failure-diagnosis archive SHA-256: 6acd55523f4e69168fc4efeb59a85087b2a42eabb4acdda58ecdd74385308ff3. Candidate-family archive SHA-256: 967eb5b8711ae8bc18725d9c8cbb25f575bd735e8a47d52303fd46bcb354899f.

## New numerical blocker

The chirped sine histories at 44.1 and 48 kHz fail the unchanged criterion. At 44.1 kHz, 55 meter samples exceed tolerance, all in the middle band; the worst ratio is 2.1063280534763926 at block 1217, inside the first chunk before checkpoint restore. Native paired-float execution reproduces that ratio, while WASM/native paired disagreement is only 0.028043806519721357 of tolerance. The independent 44.1 kHz Python oracle equals the native stock-double capture exactly.

Rounding the lower crossover in a diagnostic Python oracle reduces the mismatch to 1.452649532676189, but does not eliminate it. This implicates crossover rounding as a contributor, not a complete root cause or accepted semantic change. The pinned source and oracle remain unchanged; no tolerance was relaxed and no new source was admitted. The failure is retained as a regression case for the next coefficient/parameter precision repair.

## Candidate and readiness research

Two complete MIT-declared reverse-delay closures, phasor_phase and indexphasor, include the pinned os.lf_rawsaw helper. Both compile successfully, but both connect to comparison families under the unchanged raw/canonical and collective H1 policy. Full reconstruction: 1524 identities, 12 components, 28456 joining operations. No independent evaluation candidate was admitted. Per-unit rights and semantic qualification remain separate from compilation.

Source: https://gist.github.com/tomoyanonymous/d527fca58e929de6a021565505589406/bb635c138ecc738273745ba13a0ee9f8872c606f

The helper clarification issue https://github.com/grame-cncm/faustlibraries/issues/321 remains open with zero comments. No exact _tanhalf or _tpt_df declaration was found in the fetched filters.lib. Both helper rights remain unresolved.

Public Spark custody metadata is byte-identical to the previous check; the focused Gmail query found no artifacts, and the active Notion record still identifies Danny as custodian without supplying a signed split or trusted public-key binding. Checkpoint hashes are integrity records, not custodian signatures.

Readiness was replayed against the unchanged scope 08fb16b587cd5b23f7a5be12b234dc89ae24e18ef943b3449e61ed39f4c19516: pilot_ready=false, training_authorized=false, verified_gates=[]. Qualified pair/rights/family evidence, signed T07 and matching trusted-key bindings, T08/A2/GD1/environment evidence, and the complete scoped pilot package remain outstanding. No private task material or signing keys were accessed. Admission remains NOT_GRANTED.

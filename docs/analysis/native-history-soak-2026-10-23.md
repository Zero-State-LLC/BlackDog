# Fivefold native float32 history qualification

Admission remains NOT_GRANTED. TOKEN_FLOOR=40 remains provisional; T07 remains unfrozen.

The unchanged paired-cotangent source passes 24 native float32 histories of 720000 frames, with one continuously evolving processor per case. These extend state history fivefold. They do not extend the production WASM renderer's 144000-frame cap, and do not establish long-history WASM qualification.

| History | Native passes | WASM-prefix passes | Reset rejections | Maximum meter error (dB) |
| --- | ---: | ---: | ---: | ---: |
| alternating | 12 | 12 | 12 | 0.001263618 |
| threshold-walk | 12 | 12 | 12 | 0.001263618 |

## Test contract and evidence

The two histories repeat the previously qualified alternating and seeded threshold-walk control patterns five times. Both retain 64-sample blocks, the production float32 smoother, three bands, M=3, tau=0.01, zero offset, and the 2000–6000 Hz target range. Rates are 44100, 48000, 96000 and 192000 Hz. Total durations are approximately 16.33, 15, 7.5 and 3.75 seconds respectively.

Each stimulus is the corresponding previous 144000-frame noise, impulse or 440 Hz sine buffer looped five times. This includes a new impulse at each buffer boundary and any sine discontinuity caused by wrapping; it is not a claim about a continuous-phase oscillator. Processor state is retained across all five chunks.

An independently compiled stock double implementation runs the same inputs and float32 controls. Native float32 output is compared to that oracle at every block-end meter observation. The existing tolerance remains 2e-6 absolute plus 1e-5 relative on dB/200. The driver asserts finite output and exact audio passthrough at every sample. The largest tolerance ratio is 0.709956.

Every opening 144000-frame segment passes comparison with the saved WASM capture. Every stock-double opening segment agrees with the previously independently validated reference within 1e-7 normalized units. These checks connect the new native harness to prior evidence; they do not prove backend equivalence after that opening segment.

A separate native run resets the processor at each chunk boundary. All 24 reset counterexamples are rejected, demonstrating that the retained state history is observable in these cases. No counters, levels or filter state are manually carried into a freshly initialized positive-case processor.

Local verification checks all output and input hashes, compiler/header/driver hashes, exact control buffers, the prior WASM prefixes, stock-reference prefixes, tolerances, finite samples and reset rejection. All 85 diagnostic regression tests pass.

## Resource findings

The initial GCC -O2 build was killed under the existing native limits. Switching to -O1 compiled successfully, but the first tenfold (1440000-frame) execution was killed under the same limits, leaving a partial output. Both configurations and the partial result are preserved as failures; neither is qualified.

The fivefold runs complete with -O1, -ffp-contract=off and -fno-fast-math. Limits remain 20 CPU seconds, 1 GiB address space, 16 MiB output-file size and 30 seconds wall time per child. The native toolchain is Faust 2.88.0 and GCC 13.3.0 on Spark; executable hashes accompany the evidence. Production limits, precision guards and the baseline environment were not modified.

This is bounded native evidence for the stated source, compiler settings and host. Longer histories, arbitrary inputs, realtime deadlines, other topologies and longer WASM execution remain unqualified.

## Candidate and readiness research

Three complete dependency-free easing closures from [the author's AutoBreath example](https://zenn.dev/mogesystem/articles/1af36a38da3bc3) were screened: easeLinear, easeInQuad and easeOutQuad, with the linear helper included where used. The author marks the example Unlicense. All three connect to the comparison family under the unchanged policy; no rights or evaluation admission was inferred from the license text alone.

Full replay and reconstruction agree at 1520 identities, 12 components and 28378 joining operations. The same 117 raw aliases remain outside the comparison family, and no new independent evaluation member qualifies. The source HTML, extracted code, closure hashes and joining evidence are preserved in work/autobreath-family-evidence.tar.gz (SHA-256 cf2dad6c28974977c3c9667cf7aeb8209b311f1088c23c4d32f5bc0904f72050).

[Helper issue #321](https://github.com/grame-cncm/faustlibraries/issues/321) remains open with zero comments. The filters.lib blob is still 28cf26f1c45c5397b4433959b74e25d320e8234d, with no new helper-specific declaration for `_tanhalf` or `_tpt_df`. Both rights blockers remain.

The 14 known public Spark custody records are unchanged. Focused Gmail research found no signing messages; querying active Notion records returned only the existing Danny/iPhone custody arrangement. A bounded filename search of the local work artifacts found no public snapshot, split or verification-key bundle. No private task or signing key was accessed.

Readiness replay remains pilot_ready=false, training_authorized=false and verified_gates=[] for scope 08fb16b587cd5b23f7a5be12b234dc89ae24e18ef943b3449e61ed39f4c19516. Source rights, family-disjoint membership, signed T07 evidence, authenticated custodian public-key binding and the other scoped admission gates remain unresolved. Diagnostic reports and operational approval are not cryptographic custody attestations.

## Provenance

Paired source SHA-256: 40a1342836429fb8969b6737abf226a2b5ccfe19556d1882c4ced37421c1c515 (unchanged).
Native evidence archive: work/native-soak-evidence.tar.gz, SHA-256 4ffbc1e257cf9fce1e2c70a835a3b7b3e42bd2dd6732b13e262831bca60c33ca.
WASM basis archive SHA-256: 80032ee9224709224b3520e7379ee2c2f80bd694cbdfbd356ffb4a837852a31b.
Reproduce with native_history_soak.py in the retained isolated Spark root /home/delphi/blackdog-pair-qualification-m8e1n43a, using the retained source, prior captures, control events and matched double source. This script is diagnostic-only and produces custom native evidence, not production admission receipts.

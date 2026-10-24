# Paired-float32 spectral repair — 2026-10-23

The fixed spectral fixture now passes its float32 end-to-end checks at 44.1 and
48 kHz. Returning both parts of each compensated result together, then composing
operations sequentially, reduces native compilation from a 15-second timeout to
404 milliseconds. Rounding barriers remain in place. No compiler limit, signal
tolerance, meter floor, or production implementation was changed.

## Diagnosis and remedy

The previous unprotected TwoSum expression was simplified to zero by Faust.
Barriers preserved the residual but the scalar high/low functions repeatedly
expanded nested arithmetic expressions. Phase profiling now isolates the cost:
the full graph reaches evaluation and times out there, before propagation or
code generation. One section spends 6.162 seconds evaluating and only 7.3 ms
generating code. This supports source expansion as the bottleneck; it does not
establish a formal complexity bound.

Faust's documented compilation pipeline expands the source into a flat block
diagram before translating it into signals. The repair exploits sequential block
composition: `add` and `mul` each return a pair, `renorm` normalizes that pair,
and the biquad reduces five products through sequential pair additions. Both
parts stay together between stages. See the extracted arithmetic implementation
in `paired-float32-shared-arithmetic.lib` and the exact source hash in the evidence
JSON. The extraction removes only four unused scalar helper definitions; the
full integrated source, rather than a separate library import, was executed.

Sources: [compiler stages](https://faustdoc.grame.fr/manual/errors/) and
[phase timing option](https://faustdoc.grame.fr/manual/options/).
The profiling wrapper appends `-time` to the sandbox command because the standard
receipt API does not allow that diagnostic flag. Its logs are diagnostic phase
evidence, not qualification receipts. The successful validation runs use the
unmodified compiler API and default limits, with `-ftz 0`.

## Validation

| Frames / block | Native compile | Positive runs | Wrong-reference controls | Worst meter error |
| --- | --- | --- | --- | --- |
| 4096 / 64 | 404 ms | 6 pass | 6 rejected | 0.000906 dB |
| 16384 / 128 | 405 ms | 6 pass | 6 rejected | 0.001073 dB |

Each profile covers sine, noise and impulse at both rates. All 26 compiler/signal
receipts and 12 sample captures were locally verified, including hashes, schema,
reference rejection and recomputed channel errors. Audio passthrough is exact.
Native Faust 2.88.0 compiles the graph; Faust WASM 2.90.0 executes the signal tests.
The original absolute/relative acceptance thresholds apply to serialized dB/200
meter values. Independent double-precision references remain unchanged.

This is a validated repair for the fixed three-band fixture, not general library
qualification. Coefficients are precomputed for two sample rates; arbitrary rates,
dynamic parameters, unrestricted input magnitudes and native runtime behavior
remain outside this evidence. Barriers assume intermediates stay within +/-1e30.
The production library and admitted datasets have not been replaced.

## Remaining readiness blockers

[Helper-license issue #321](https://github.com/grame-cncm/faustlibraries/issues/321)
remains open without comments. The two helper licenses remain unresolved.
The latest family population remains 1477 identities in 12 components; this turn
adds no independent evaluation candidate or new family replay.

Readiness was replayed against its existing manifest scope. It still reports no
verified admission gates, pilot readiness false and training authorization false.
No signed T07 snapshot bundle or trusted custodian public key was supplied by
this repair. T07 remains unfrozen and TOKEN_FLOOR=40 provisional. Numerical
success does not close rights, family independence, custody or other signed gates.

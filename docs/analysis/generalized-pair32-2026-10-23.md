# Generalized paired-float32 qualification — 2026-10-23

Seven specialized spectral configurations now pass the unchanged float32 signal
checks. The new diagnostic generator accepts a sample rate, top cutoff, band
count, bands per octave, smoothing time and dB offset. It emits explicit paired
coefficients and retains the complete captured dependency closure. This is
offline specialization, not a runtime-variable analyzer replacement.

## Generalization repair

The first extension exposed constant folding in coefficient splitting. The
previous passing fixture selected coefficients using sample rate. Substituting
fixed literals allowed the coefficient-side Dekker split to be evaluated before
float32 rounding, reintroducing a middle-band sine error at 44.1 kHz. The new
generator computes each coefficient's high/low value and its split components
with explicit float32 rounding. The runtime pair multiplier consumes those
components directly. That same configuration then passes.

The original reciprocal-tangent coefficient transform and the independent
reference filter remain separate implementations. The reference follows the
pinned analyzer's recursive low-pass/high-pass band definition. The generated
processor moves high-pass stages ahead of prior low-pass stages while preserving
paired values. This relies on constant linear filters; it does not establish
equivalence for changing controls.

The diagnostic meter exporter also assumed exactly three meters. It now accepts
two through eight, checks contiguous descriptor ordering, and leaves the
profile's expected-channel validation in place. Production signal code is
unchanged. The generator's runtime-rate guard rejects mismatched specialization;
its parameter guards reject nonfinite values, Nyquist violations and invalid
band counts. Fourteen focused tests pass, including the coefficient-rounding
regression and mismatched-rate rejection.

## Verified configurations

| Rate | Top Hz | Bands | Bands/octave | Tau | Offset dB | Frames/block | Native ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 44100 | 1500 | 3 | 1 | .01 | 0 | 4096/64 | 352 |
| 48000 | 3000 | 2 | 1 | .02 | -3 | 4096/64 | 201 |
| 44100 | 4000 | 3 | 3 | .01 | 0 | 4096/64 | 406 |
| 44100 | 6000 | 4 | 2 | .005 | 3 | 4096/64 | 652 |
| 48000 | 12000 | 5 | 3 | .05 | 0 | 4096/64 | 906 |
| 48000 | 16000 | 8 | 1 | .001 | -6 | 16384/128 | 2417 |
| 44100 | 22000 | 3 | 3 | .2 | 0 | 16384/128 | 348 |

Every row covers sine, noise and impulse, plus deliberately incorrect references.
All 21 positive runs pass and all 21 wrong references are rejected. Local
verification checks 49 receipts and 21 sample captures, exact source hashes,
profile dimensions, schemas, sample digests and recomputed channel errors.
Worst observed meter error is 0.000906 dB; audio passthrough is exact. Native
Faust 2.88.0 compiles; Faust WASM 2.90.0 executes. No tolerances, meter floors or
15-second resource limits were relaxed.

The first attempt also compiled fixtures at 8, 32, 88.2 and 96 kHz, but the
production signal profile correctly rejected those rates. Those configurations
are not signal-qualified. The generator's accepted parameter range is broader
than its tested domain: only the seven rows above are qualified diagnostically.
Dynamic parameters, other rates and native signal execution remain unqualified.
Initial failures are retained rather than relabeled as passes.

## Reproduction interface

`python scripts/diagnostics/paired_spectral_fixture.py --help` describes the
JSON-emitting generator. Supply the preserved complete spectral closure through
`--closure` and `docs/analysis/paired-float32-shared-arithmetic.lib` through
`--arithmetic`. A generated fixture must execute at `required_sample_rate`;
call `require_runtime_rate` before execution. Generation never grants admission.
The adjacent evidence JSON binds the generator, arithmetic and diagnostic worker
hashes to the tested sources and archives.

## Family, rights and signed readiness

Three complete primitive-only DSP candidates from
[CICM/pd-faustgen at 9e2aaeab](https://github.com/CICM/pd-faustgen/tree/9e2aaeabe94a7fab6928711050535ac12a1a591a/tests)
were fetched with the pinned MIT notice and Git-blob checks. All three connect to
the comparison family. The seven repaired full closures also connect. Complete
replay now contains 1487 identities, 12 components and 27697 joining operations;
edge reconstruction agrees. No independent evaluation candidate was admitted,
and neither TOKEN_FLOOR=40 nor the H1 collective policy changed.

[Helper-license issue #321](https://github.com/grame-cncm/faustlibraries/issues/321)
remains open with no comments. Neither unresolved helper is cleared by this
repair; retained dependencies and their rights classifications still apply.

The renewed Notion search found the existing custody and recovery decisions,
not a signed snapshot bundle or trusted public key. Hashes of all 14 public JSON
records in the bounded Spark custody/approval search are unchanged. The T07
proposal remains explicitly unsigned and unfrozen. No private task or key was
accessed. Readiness replay retains its original manifest scope, zero verified
admission gates, pilot readiness false and training authorization false.

The pinned band definition is in
[analyzers.lib](https://github.com/grame-cncm/faustlibraries/blob/2edec0537f536eaa130d42c354884d7db971663c/analyzers.lib).

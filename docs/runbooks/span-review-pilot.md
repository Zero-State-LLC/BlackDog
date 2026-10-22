# Offline span review packets and diagnostic pilot

`diagnostics/span_review.py` prepares unapproved review packets and executes
bounded diagnostic plans. It does not parse Faust, infer boundaries, approve
rights or produce a trusted production digest. ADR-0007 and the production
extractor are unchanged. `TOKEN_FLOOR=40` stays provisional and T07 unfrozen.

## Inputs and private output

Use the pinned inventory and notices, an existing unapproved span candidate,
and a JSON object mapping each admitted function's Git blob SHA to its local
source file. Duplicate JSON object keys are rejected in every input. Every source is verified against its Git blob hash before use.
No fetcher or network download runs. Sources and generated wrappers must remain
outside Git; select a new receipt directory outside `/tmp`. Existing output
folders are refused. Case names that collide at generated receipt paths are
rejected before execution; sparse references expand one case at a time. Run from the checkout with the existing activation script:

```bash
source ./activate-local.sh
export PYTHONDONTWRITEBYTECODE=1
python -m diagnostics.span_review packets \
  --inventory corpus/rights-inventory.v1.json \
  --notice corpus/notice-manifest.v1.json \
  --candidate /absolute/private/function-spans.candidate.json \
  --sources /absolute/private/sources.json \
  --output /absolute/private/new-review-packets
```

`packets.json` includes all admitted function identities, notice/rights metadata,
existing candidate rows, overload siblings and unresolved review questions.
Complete pinned source context is stored once per blob in `sources/`; packets
reference those files. Missing spans are null, not guessed. Existing exclusion
dispositions remain present. Counts distinguish proposed from pending; neither
status means production approval. Historical validation is not inferred from an
existing span: dependency and behavioral status start as not assessed.

## Explicit validation plans

Use `run` instead of `packets` and add `--plan /absolute/private/plan.json`.
The plan has a nonempty `cases` array. Each case has exactly these fields:

- `id`: unique lowercase letters/digits/hyphens, at most 80 characters.
- `unit_ids`: ordered, unique candidate span identities, including explicit dependencies.
- `process`: Faust process expression; the runner supplies the definition and semicolon.
- `expected`: `pass`, `compile_refusal` or `reference_refusal`.
- `reference`: array of sparse channel objects mapping frame numbers to finite sample values; all other frames are zero. Null for compiler refusals.
- `missing_dependency`: expected nonblank compiler diagnostic substring for compiler refusals; otherwise null.

Only exact verified source spans are assembled before the process wrapper.
The wrapper and declared dependencies require review: this runner does not prove
that a wrapper exercises every supplied definition, infer dependency closure,
or certify an oracle's independence. No implicit whole-library import is added.

All signal cases use the existing sandbox harness, default signal checks and
numeric tolerances, 144,000 frames, block size 64, impulse stimulus and both
44.1/48 kHz. This first runner supports sparse impulse references, not a general
step/noise/envelope/analyzer qualification protocol. Such protocols remain future
work; do not convert a passing impulse case into broad semantic acceptance.
No tolerance overrides are exposed. Compiler controls require exit code 1 and
the named diagnostic; reference controls require successful compilation and an
explicit reference mismatch. A harness/sandbox exception records an abort and
stops the run. Ordinary mismatches remain in results and produce CLI exit 1.

The output retains the plan, span evidence, exact DSP, profiles, compiler/signal
receipts, diagnostics and incremental results. Keep an external checksum manifest
and preservation records alongside the run. A computed manifest digest only binds
these diagnostic bytes; independent approval remains required. Full-inventory
coverage, rights quarantine and snapshot validation are never bypassed.

## First Spark pilot

At base `d470f95`, the input candidate contains 16 of 965 units. Packets cover
all 965, including the 949 missing units. The separate pilot selects 25 additional
units across maths, delays and quantizers: arithmetic/constants, ordered
Chebyshev clauses, bounded delays and three tuning tuples. Some delay wrappers
are deprecated and add limited diversity; retain that disposition. Foreign
functions, envelope dependency closures and broad fastmath qualification remain
pending. This pilot is not independent production approval or a T07 freeze.

The pilot passed 72 positive renders, three missing-dependency compiler controls
and four wrong-output reference controls (79/79). The combined unapproved
candidate has 41 spans, with 924 missing; full-inventory validation still refuses.
All 140 targeted regressions passed, packet replay was byte-identical, and all
95,684 pre-existing files/symlinks were unchanged. Earlier 16-span diagnostics
were preserved, not rerun. These results cover only the listed sparse impulse
cases; envelope, continuous-signal, native and cross-architecture qualification
remain open.

Private receipts: `/home/delphi/blackdog-span-pilot-20261021/`. The earlier
16-span receipts remain at `/home/delphi/blackdog-span-batch3-20261021/`.

Review follow-up receipts are separate at
`/home/delphi/blackdog-span-pilot-review-20261021/`. The review corrected receipt
filename collisions and eager reference allocation; 142 targeted regressions
passed after those changes. The same 79-execution pilot passed again there with
unchanged signal checks and tolerances. Prior pilot receipts remain untouched.

## Upstream parser feasibility

Inspection of Faust 2.88.0, commit
`8c00913e44d42f9d25aa3f1a0d500bde5662d7bc`, found definition actions calling
`setDefProp` with filename and line number, and a lexer using `yylineno`.
No byte-offset export hook was found in the inspected grammar/lexer. This is a
bounded source inspection, not proof about every compiler API. A future isolated
prototype would need to track original byte offsets through lexing, preserve
comments/UTF-8/CRLF and ordered overload clauses, and test nested local definitions
and precision variants. Do not infer approved ranges from the line metadata or
substitute expanded DSP/Box IR for original bytes. No compiler patch, installation
or production parser was introduced.

Pinned sources: [grammar](https://github.com/grame-cncm/faust/blob/8c00913e44d42f9d25aa3f1a0d500bde5662d7bc/compiler/parser/faustparser.y),
[lexer](https://github.com/grame-cncm/faust/blob/8c00913e44d42f9d25aa3f1a0d500bde5662d7bc/compiler/parser/faustlexer.l).

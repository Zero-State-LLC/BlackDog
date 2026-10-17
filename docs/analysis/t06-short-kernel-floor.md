# T06 short-kernel floor

Measurement for the length constant in `faustcoder/neardup.py`. Danny
(2026-10-17, 4:11 PM PT) has not accepted the 40-token floor as
clearance policy. This note counts the short rejected and
`needs_human` kernels on the pinned corpus, plants copies of them into
cleared fixtures, and reports detection and extra quarantines at
floors 40, 30, 20 and 15.

The recommended floor is **40**. `TOKEN_FLOOR` stays 40. Lowering it
catches a minority of embedded short kernels and quarantines cleared
files that only share a Grame `declare` header with a rejected
example.

## What the constant does

`TOKEN_FLOOR` is the single length constant. Jaccard 4/5, excerpt
containment, and the verbatim run all read it. `MIN_TOKENS` and
`VERBATIM_RUN` are that same value.

An embedded copy is detected when the cleared text is at least
`TOKEN_FLOOR` tokens and either half of its 5-token shingles sit in
the non-cleared text, or the two texts share a contiguous run of
`TOKEN_FLOOR` tokens. A kernel shorter than the floor cannot supply
that run. Exact normalized-hash equality is a separate pass and does
not consult the floor. Two texts that are not both at least the floor
use the character 5-gram / identifier-skeleton fallback instead of
token Jaccard.

## Corpus

Pinned inventory `sha256:e3938dd19b9456e94f563d446e4994fdd2d3d7f785e9599e02aabad6641c4f26`
and notice `sha256:bbda20fdef13092d010805aa2bc3df65f84250a9241de89292148fdb21b5f4ec`.
Every loaded blob matched its inventory git blob id. Comparison rows:
183 units, 144 `rights_rejected` and 39 `needs_human`. Cleared side of
the quarantine count: 491 distinct blobs. No blob sha is both cleared
and comparison.

T06 still normalizes a function unit as the whole file (the `.lib`
slice is a follow-up). Whole-file length and function-span length are
different populations.

## How a span was cut

For a comparison unit that names a function, the span is that
definition through the semicolon at brace depth 0, after comment
stripping. Strings are skipped, so a `with { }` block stays inside
the span. This cutter is a measurement aid. The dedup code does not
use it, and it is not a Faust parser.

An inventory name `foo@2660` is the definition of `foo` that starts
on that source line. All 178 function-named comparison units produced
a span.

## How many kernels are under 40 tokens

Whole comparison files:

| Tokens | Units |
|---|---|
| under 40 | 1 |
| 40 or more | 182 |

The one short file is rejected `pd-faustgen-mixer`
`external/examples/mixer.dsp`, 38 tokens. After comment stripping it
is the Grame BSD header and `process = _;`:

```text
declare name "mixer";
declare version "1.0";
declare author "Grame";
declare license "BSD";
declare copyright "(c)GRAME 2006";
process = _;
```

Function spans (178 units):

| Tokens | Rejected | needs_human | Units |
|---|---|---|---|
| under 15 | 24 | 8 | 32 |
| 15–19 | 7 | 1 | 8 |
| 20–29 | 27 | 2 | 29 |
| 30–39 | 14 | 1 | 15 |
| 40 or more | 68 | 26 | 94 |

84 spans are under 40 tokens (72 rejected, 12 `needs_human`). Two of
them are the same `_simplexNoise` line, so the planted-copy rates
below use 83 distinct span texts. The shortest spans are 4 tokens
(`aanl.lib` `clip`, `motion.lib` `clamp01`, several pinktrombone
constants).

## Planted copies

Each distinct short text was planted four ways, then scored with the
production predicates at each floor:

- Embedded verbatim: 80 `padN` tokens, then the kernel. This is own
  code plus the rejected kernel.
- Embedded trailing edit: same, after the last identifier in the
  kernel is replaced with `renamed`.
- Embedded middle edit: same, with the middle identifier replaced.
- Whole-text verbatim and the same two edits, with no padding. This
  is the comparison a sliced function unit would see. Verbatim
  whole text is an exact hash at every floor.

Padding is long enough that containment of the padded file inside the
short kernel stays under 1/2. An embedded hit is a verbatim run.

### Short function spans (83 distinct texts)

| Floor | Embedded verbatim | Embedded trailing edit | Embedded middle edit | Whole verbatim | Whole trailing edit | Whole middle edit |
|---|---|---|---|---|---|---|
| 40 | 0/83 (0%) | 0/83 (0%) | 0/83 (0%) | 83/83 (100%) | 36/83 (43.4%) | 19/83 (22.9%) |
| 30 | 15/83 (18.1%) | 10/83 (12.0%) | 0/83 (0%) | 83/83 (100%) | 41/83 (49.4%) | 32/83 (38.6%) |
| 20 | 44/83 (53.0%) | 33/83 (39.8%) | 7/83 (8.4%) | 83/83 (100%) | 56/83 (67.5%) | 57/83 (68.7%) |
| 15 | 52/83 (62.7%) | 45/83 (54.2%) | 19/83 (22.9%) | 83/83 (100%) | 61/83 (73.5%) | 62/83 (74.7%) |

At floor 40 the whole-text light edits that hit do so on the character
/ skeleton path. At lower floors some of those same edits move onto
the token run or containment path, and the net rate rises. A middle
edit of an embedded span still misses 64 of 83 texts at floor 15,
because the edit splits the only run the kernel has.

The 32 spans under 15 tokens are invisible to every run floor tested
once they sit inside other code. A run cannot be longer than the
kernel.

### The one short file (`mixer.dsp`, 38 tokens)

| Floor | Embedded verbatim | Embedded trailing edit | Embedded middle edit | Whole verbatim | Whole light edits |
|---|---|---|---|---|---|
| 40 | 0/1 | 0/1 | 0/1 | 1/1 exact | 1/1 short path |
| 30, 20 | 1/1 run | 1/1 run | 0/1 | 1/1 exact | 1/1 run or containment |
| 15 | 1/1 run | 1/1 run | 1/1 run | 1/1 exact | 1/1 run |

## Extra quarantines on the real cleared corpus

`cluster_families` on the 491 cleared blobs plus the comparison blobs,
at each floor. A cleared blob is quarantined when its family contains
a comparison blob. Counts are blobs, not units. "Added" is blobs
quarantined at that floor and not at floor 40. No floor released a
blob that floor 40 quarantines.

| Floor | Quarantined cleared blobs | Added vs 40 |
|---|---|---|
| 40 | 80 | 0 |
| 30 | 133 | 53 |
| 20 | 170 | 90 |
| 15 | 199 | 119 |

Every addition is a verbatim run. At floor 30 the first matching
comparison blob is:

| Comparison blob | Added cleared blobs |
|---|---|
| `pd-faustgen-mixer` `external/examples/mixer.dsp` | 36 |
| `faustlibraries-agpl-functions` `basics.lib` | 8 |
| `faust-impulse-effect-undeclared` `tests/impulse-tests/dsp/effect.lib` | 4 |
| `faust-examples-copyright-only` `NLFfm.dsp` | 3 |
| `faustlibraries-attribution-gap` `noises.lib` | 1 |
| `faustlibraries-attribution-gap` `demos.lib` | 1 |

Those 36 `mixer.dsp` hits are the Grame `declare` header. The rejected
file is 38 tokens, so a floor of 30 treats that header as a copy.
Floors 20 and 15 add more of the same header matches, plus 20-token
and 15-token runs into `filters.lib`, `demos.lib`, `effect.lib` and
`basics.lib`.

The 80 blobs already quarantined at floor 40 include the 11 STK
examples that share an 89-token `nonLinearity` block with `NLFfm.dsp`.
That set does not grow or shrink inside this table's "added" column;
the column is only the new blobs.

## Recommendation

Keep `TOKEN_FLOOR` at 40.

Floor 30 is the first step down. It detects 15 of 83 embedded verbatim
short spans (18.1%) and none of the embedded middle edits. It also
quarantines 53 more cleared blobs, 36 of them because they share the
BSD `declare` header with `mixer.dsp`. Floors 20 and 15 raise embedded
verbatim detection to 53.0% and 62.7% and add 90 and 119 cleared blobs.
They still miss every embedded kernel shorter than the floor, including
the 32 spans under 15 tokens, and they still miss most embedded middle
edits.

An exact copy of a short span, compared as its own text, is already
detected at every floor by the hash pass. The miss is the embedded
span inside a longer cleared file. Closing that miss by shortening the
run also quarantines ordinary Faust headers. The follow-up that
matches the measurement is slicing function units so the span is the
compared text. That is outside this constant.

40 remains an operating value. It is not an accepted clearance policy.

## Labels

- OBSERVED: the inventory counts, the blob-id checks, the 38-token
  text of `mixer.dsp`, the span length table, the planted-copy rates,
  and the quarantine counts at each floor.
- INFERRED: the depth-0 semicolon cutter, including `name@line`; the
  80-token `padN` prefix; "light edit" as one identifier replaced by
  `renamed`; calling the added quarantines false when the shared run
  is the `declare` header. The 17 floor-30 additions that are not
  `mixer.dsp` are extra quarantines. They were not each proved to be
  a copied short kernel.
- SPECULATIVE: any floor other than the four measured here; treating
  40 as settled policy. Danny has not accepted it.

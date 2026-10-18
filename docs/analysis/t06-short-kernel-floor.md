# T06 short-kernel floor

Measurement for the length constant in `faustcoder/neardup.py`. Danny
(2026-10-17, 4:11 PM PT) has not accepted the 40-token floor as
clearance policy. This note counts the short rejected and
`needs_human` kernels on the pinned corpus, plants copies of them into
cleared fixtures, and reports detection and extra quarantines at
floors 40, 30, 20 and 15.

The recommended floor is **40**. `TOKEN_FLOOR=40` is not accepted by
Danny. That recommendation is SPECULATIVE. At floor 40, 0/83 embedded
short-kernel copies are detected. With the unique padding used below,
that zero is tautological. The meaningful population is the 44 spans
of 20–39 tokens. The proposed follow-up is function-unit slicing.

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

The meaningful population is the 44 spans of 20–39 tokens (29 in
20–29, 15 in 30–39). A floor of 20 or 30 can see a run inside those
spans. The 32 spans under 15 tokens, and the 8 spans of 15–19 tokens,
are shorter than every floor except 15, so a run cannot land in them
once they are the whole compared text.

## Planted copies

Each distinct short text was planted four ways, then scored with the
production predicates at each floor.

The embedded column is a post-slicing model. With unique padding,
detection is tautological. The 80 `padN` tokens share no shingles with
the kernel, so containment of the padded text in the kernel stays under
1/2 by construction. A hit is exactly a verbatim run of `TOKEN_FLOOR`
tokens inside the kernel. A kernel shorter than the floor cannot supply
that run, so the embedded rate at floor 40 is 0/83 because every planted
span is shorter than 40 tokens.

- Embedded verbatim: 80 unique `padN` tokens, then the kernel.
- Embedded trailing edit: same, after the last identifier in the
  kernel is replaced with `renamed`.
- Embedded middle edit: same, with the middle identifier replaced.
- Whole-text verbatim and the same two edits, with no padding. This
  is the span compared as its own text. Verbatim whole text is an
  exact hash at every floor.

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

The embedded zeros follow from the padding. Of the 83 spans, the 44
of 20–39 tokens are the ones a lower floor could newly detect. At
floor 30 that is 15 spans (all of them in the 30–39 bucket). At floor
20 it is 44, which is every span of at least 20 tokens.

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

### The 17 floor-30 additions that are not `mixer.dsp`

The first comparison blob above names the blob, not the function that
owns the run. `basics.lib` is one blob. Its inventory row
`processArray` is the AGPL-3.0-only function, and `tabulateNd` is the
other AGPL function in that file. None of the eight runs land in either
function. The file default outside those two declares is the GRAME
LGPL-2.1 section.

| Cleared file | Run | What it is |
|---|---|---|
| `karplus.dsp`, `karplus32.dsp`, impulse `karplus.dsp`, `SNoiseburst.dsp`, `Granulator.dsp`, bela `granulator.dsp` | `release(n) = + ~ decay(n); trigger(n) = upfront : release(n) : >(0.0);` | Generic idiom. It is the body of GRAME `ba.spulse`, also used by the BSD karplus and granulator examples. Not AGPL leakage. |
| `maxmsp.lib` | `state ~ (_,_) : !,_ with { state(t, c) = nt, nc` | Verbatim `ba.line` ramp. LGPL helper in the same file as the AGPL functions. Not AGPL leakage. Floor 40 misses this copy. |
| `envelopes.lib` | `(b, x) = (x / ((((1.0 / b) - 2.0) * (1.0 - x)) + 1.0))` | Verbatim `ba.bpf._bias_curve`. Same GRAME section, not `processArray`. Not AGPL leakage. Floor 40 misses this copy. |
| `flanger.dsp`, `SAM/flanger/flanger.dsp`, `flangerForBrowser.dsp` | `fdelay(dmax, curdel)) ~ *(fb)` | Verbatim `flanger_mono` from impulse `effect.lib` (declare license STK-4.3). Real copy of that function. Not AGPL. Floor 40 misses the 30-token fragment. |
| `maths.lib` | `2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47` | Prime table shared with `effect.lib` `prime_power_delays` and `ma.primes`. Generic number list, not a DSP kernel. |
| `SClarinet.dsp`, `STinkle.dsp`, `STibetanBowl.dsp` | `declare author "Romain Michon"` plus the copyright and version declares | Declare metadata, same class as the `mixer.dsp` header. |
| `debug.lib` | `ma = library("maths.lib"); ba = library("basics.lib"); fi = library("filters.lib")` | Import boilerplate shared with `noises.lib`. |
| `synths.lib` | `library("filters.lib"); os = library("oscillators.lib"); no = library` | Import boilerplate shared with `demos.lib`. |

No floor-30 addition is a real AGPL function that floor 40 misses.
Two are verbatim LGPL helpers (`ba.line`, `ba.bpf._bias_curve`) and
three are a verbatim STK `flanger_mono` fragment. The other 12 are a
generic idiom, a prime table, declare headers, or import lines.

### Stripping `declare` before the run

Measured option, not the shipped check. `declare` statements are
removed, then the verbatim run is computed again. Containment is
unchanged. This is the false-positive and false-negative change at
floors 30 and 20.

False positives are the cleared blobs added versus floor 40.

| Floor | Added vs 40 | Run survives `declare` stripping | Run lost |
|---|---|---|---|
| 30 | 53 | 14 | 39 |
| 20 | 90 | 26 | 64 |

At floor 30 the 39 lost runs are the 36 `mixer.dsp` headers and the
3 Romain Michon declare headers. The 14 that survive are the idiom,
helper, flanger, prime-table and import rows above.

False negatives are planted embedded copies. None of the 83 short
spans contain a `declare` token, so stripping does not change their
detection: 15/83 at floor 30 and 44/83 at floor 20, with or without
the strip. The one short file, `mixer.dsp`, is the change. Embedded
verbatim is a hit at floors 30 and 20 before the strip and a miss
after it, because the file falls from 38 tokens to `process = _;`
(4 tokens). Floor 40 misses that file either way.

The 80 blobs already quarantined at floor 40 include the 11 STK
examples that share an 89-token `nonLinearity` block with `NLFfm.dsp`.
That set does not grow or shrink inside this table's "added" column;
the column is only the new blobs.

## Recommendation

Keep `TOKEN_FLOOR` at 40. `TOKEN_FLOOR=40` is not accepted by Danny.
The 40 recommendation is SPECULATIVE. At floor 40, 0/83 embedded
short-kernel copies are detected, and with unique padding that zero is
tautological. The meaningful population is the 44 spans of 20–39
tokens. The proposed follow-up is function-unit slicing.

Floor 30 detects 15 of those 44 spans when they are planted after
unique padding, and none of the embedded middle edits. It also
quarantines 53 more cleared blobs. Thirty-six are the `mixer.dsp`
header and 3 more are other `declare` headers. Stripping `declare`
before the run drops those 39 and leaves 14. Those 14 are not AGPL
function bodies. Floor 20 raises the tautological embedded rate to
44/83 and adds 90 cleared blobs; stripping `declare` drops 64 of them.

An exact copy of a short span, compared as its own text, is already
detected at every floor by the hash pass. The follow-up that matches
the measurement is slicing function units so the span is the compared
text. That is outside this constant.

40 remains an operating value. It is not an accepted clearance policy.

## Labels

- OBSERVED: the inventory counts, the blob-id checks, the 38-token
  text of `mixer.dsp`, the span length table, the planted-copy rates,
  the quarantine counts at each floor, the 17 non-header runs quoted
  above, and the declare-stripping counts (39 and 64 runs lost; span
  detection unchanged; `mixer.dsp` embedded detection flips off).
- INFERRED: the depth-0 semicolon cutter, including `name@line`; the
  80-token `padN` prefix; "light edit" as one identifier replaced by
  `renamed`; calling `ba.spulse`, the prime table, the import lines
  and the declare headers generic, and calling `ba.line`,
  `ba.bpf._bias_curve` and `flanger_mono` real copies that are not
  AGPL function bodies. The embedded column is a post-slicing model
  because the unique padding makes detection a run inside the kernel.
- SPECULATIVE: any floor other than the four measured here; the 40
  recommendation. Danny has not accepted it.

## Amendment 2026-10-17 7:40 PM PT (Jev Q3)

The counts above are the 2026-10-17 measurement. They are not an
acceptance of 40. The ruling is the verbatim Q3 block in
[ADR-0002](../adr/0002-training-path.md) and spec §24, from Jev output
sha256 `d9a4632ed29786182ee61e67b7c3a6b1df92c8468f011b8e1331b54e794264df`
([jev-output-2026-10-17.txt](../decisions/jev-output-2026-10-17.txt)),
authorized by Danny's instruction "use jev to make decisions"
(2026-10-17 7:37 PM PT).

`TOKEN_FLOOR` stays 40 and provisional. The protocol runs only after
H2 and H3 land. Before the run, Danny sets the recall lower bound,
requires zero reject-class copies left in cleared, and sets the FP
blob budget. Recall is per bucket with Wilson intervals, with
hand-labelled FP cost. Sub-15-token spans are exact-hash checked on
the ID/NUM stream, and that check needs the brief's idioms allowlisted
pairing, or short idioms will be over-flagged. H3 is NFKC and drop
Cf/Cc. The `STR` collapse is an ADVERSARY r6 addition; not ruled by
Jev. It applies only on the H2 canonical stream, combined with the raw
stream by OR, and never replaces the raw stream. The cutter in "How a span was cut" is a
measurement aid. It is not the real slicer. ADVERSARY confirms
containment and allowlist fixes against the shipping slicer path.

## Amendment 2026-10-18 (labels)

The acceptance bounds are ratified (Danny 2026-10-18 12:34 AM PT; spec §25). The value stays 40 and provisional. Recall is still not measured.

The 14 floor-30 and 26 floor-20 declare-stripped survivors are now labelled. "The 26 are unlabeled survivors, not confirmed FPs" was the correction: those 26 were not confirmed false positives, and the FP count has to come from labels. Reading A is COPY / FP / UNDECIDED.

| Floor | COPY | FP | UNDECIDED |
|---|---|---|---|
| 30 | 0 | 14 | 0 |
| 20 | 1 | 24 | 1 |

The FP budget is not yet decided. There is no idioms allowlist. Floor 20 is at 24 FP + 1 undecided, with no slack. These counts do not show that floors 40, 30, or 20 pass.

The labels file is not in this repository. It quotes `rights_rejected` and `needs_human` source, which ADR-0003 forbids redistributing. This note records the summary counts only.

Separate recorded rights ruling, not part of D6 and not Danny's ratified text: needs_human sources count as reject-class until a human clears them (fail closed). Boof (orchestrator), rights call under Danny's 2026-10-17 BlackDog rights/licensing delegation ([rights-inventory.md](../rights-inventory.md) lines 21-22), 2026-10-18 ~12:57 AM PT.

## Amendment 2026-10-18 2:27 AM PT (lower-floor detections)

Danny ruled option C1 ("continue as recommended"). This interprets the ratified D6 bounds and does not change their text or numbers. It closes ADVERSARY nit N9. Record: [FLOOR-ruling-b-recommendation-2026-10-18.md](../decisions/FLOOR-ruling-b-recommendation-2026-10-18.md). Spec: [§25](../../specs/001-faustcoder/spec.md#lower-floor-detections-038).

> Ruling on lower-floor detections (Danny, 2026-10-18 2:27 AM PT, "continue as recommended"; record: FLOOR-ruling-b-recommendation-2026-10-18.md). This interprets the ratified D6 bounds and does not change their text or numbers.
>
> 1. Ground truth for the FLOOR run is fixed before scoring and does not depend on TOKEN_FLOOR. The same gold set is used for 40, 30 and 20.
> 2. Planted items: every planted item is a positive at every candidate floor. A planted item that a floor misses is a miss in that floor's cell, whatever its length. No item leaves a cell's denominator because it is shorter than the floor. Cells stay at n = 100 planted items.
> 3. Natural copies: the candidate pool is the union of everything flagged at floors 40, 30 and 20, by the sub-15 exact-hash check, and by the H1 union-coverage check, on the shipping path. Each candidate is adjudicated once, on content, as COPY or NOT_COPY of reject-class text (rights_rejected, or needs_human until cleared), with a 15-token minimum and without regard to which floor flagged it. The adjudicated set is frozen before any floor is scored. Natural copies do not enter the Wilson cells.
> 4. Item 4's first count ("detected reject-class matches left unquarantined in cleared") counts, at floor F, every adjudicated COPY and every unadjudicated candidate that F's own shipping pipeline leaves in cleared. A copy that only a lower floor detects therefore fails item 4 at every higher floor that leaves it in cleared.
> 5. Only quarantines produced by F's shipping pipeline count for F. Manual quarantine pins may be applied for corpus hygiene but do not make F pass.
> 6. Every natural miss is inspected and recorded with its mechanism. Per-floor natural recall (detected / adjudicated COPY) is reported and not gated, and the report states that the pool comes from the detectors themselves.

Recommendation from the record, not Danny's ruling and not a clause of the ruling above. "The mitigation is to adjudicate before scoring, and to require a second reviewer for any item whose label decides the floor." "Record which floor flagged each item separately, and require a second reviewer for any floor-deciding item." For SClarinet: "Use two reviewers and record both."

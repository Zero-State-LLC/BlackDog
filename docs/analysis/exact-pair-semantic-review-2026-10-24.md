# Exact pair semantic review packet — 2026-10-24

Status: **prepared for independent review; not approved or admitted**.

Pair digest: `5604a3dd5bb97a94728437cc8667e03dd46bc62dcf0137105c788d16ee7a08b6`.
The target, prompt and complete supplied context are pinned in `exact-review-packet-2026-10-24.json`. No signatures or reviewer decisions are inferred from this packet.

## Exact prompt

Write only mulk(ah,al,asplit,arest,ch,cl) in Faust for the pinned paired-float filter context. Supplied interfaces: r(x) clamps to [-1e30,1e30]; renorm(high,low) returns a normalized pair. Constant (ah,al) has precomputed splitter parts asplit,arest; do not split ah again. Define p=r(ah*ch), cc=r(4097*ch), csplit=r(cc-r(cc-ch)), crest=r(ch-csplit). For the residual, compute q0=r(r(asplit*csplit)-p), q1=r(q0+r(asplit*crest)), q2=r(q1+r(arest*csplit)), q3=r(q2+r(arest*crest)), then err=r(q3+r(r(ah*cl)+r(al*ch))). Inline q0..q3 as nested expressions and return (r(ah*ch),err):renorm. Do not add al*cl or change the operation order. Use the supplied helpers at runtime; do not assume clamps enforce float32 rounding during constant folding. Scope: pinned filter coefficients in the verified analyzer domain, not arbitrary-range multiplication.

## Exact target

```faust
 mulk(ah,al,asplit,arest,ch,cl)=(r(ah*ch),err):renorm with {
  p=r(ah*ch); cc=r(4097*ch); csplit=r(cc-r(cc-ch)); crest=r(ch-csplit);
  err=r(r(r(r(r(r(asplit*csplit)-p)+r(asplit*crest))+r(arest*csplit))+r(arest*crest))+r(r(ah*cl)+r(al*ch)));
 };
```

## Supplied helper semantics

The target resolves `r` and `renorm` in the `ds` environment, not the identically named `cutctl.r`. Exact byte spans and hashes are in `exact-dependency-context-2026-10-24.json`:

```faust
r(x)=max(-1e30,min(1e30,x));
renorm(s,e)=r(s+e),r(e-r(r(s+e)-s));
```

There are four `mulk` integration call sites in the pinned filter. The direct helper closure uses built-ins only; the entire supplied prefix/suffix includes the analyzer dependencies and retains its broader rights/family restrictions. A short target does not remove those restrictions.

## Review evidence and limits

- Exact reconstruction of the retained verified source; 363 tokens including EOS.
- 41,328 bounded products agree exactly in both float32 components with an independently transcribed prompt model. Independent Decimal80 full-product checks pass; six positive batches pass and twelve corrupted batches reject.
- Full source remains bound to the retained 24 WASM and 24 modular histories and 149 bounded WASM jobs. These histories were not rerun this turn.
- The pinned source has a historical comment mentioning only 44.1/48 kHz. The later evidence covers 44.1/48/96/192 kHz under the recorded two schedules; source bytes were preserved.
- Product probe coverage is both signs, exponents -20..20, four mantissas and three low-part values for 42 signed coefficient tuples. It is not proof over arbitrary float32 values, saturation, NaNs, infinities, all possible histories, or different coefficient sets.

An independent reviewer must determine whether this exact prompt and bounded task are semantically appropriate and record that decision against the pair and context hashes. Automated consistency checks and agent review do not satisfy that decision. Canonical rights/admission and signed membership remain separate requirements even after semantic approval.

## New candidate research

Pinned [Arcturus effects](https://github.com/Lef-F/arcturus/blob/21f4b3105dbd5a76359adf9d1c8907c25b50532d/src/audio/effects.dsp) and [synth](https://github.com/Lef-F/arcturus/blob/21f4b3105dbd5a76359adf9d1c8907c25b50532d/src/audio/synth.dsp) have an MIT root license. Extracted complete selected closures: cubicNL (no external dependencies), envShape (built-ins only), widenStereo (built-ins plus the exact stereo_width slider declaration). Git blob hashes, byte spans and closure hashes were verified before screening.

The unchanged floor-40 provisional H1 collective replay now contains **1,534 identities, 12 components and 28,662 joining operations**. All three candidates join the existing comparison component. They also share one project and cannot count as three independent projects. No evaluation candidate was admitted, and no numerical qualification was attempted after this family blocker was established. These results do not claim copied authorship; collective policy joins are admission constraints.

[Ribbon Synth](https://github.com/simplicit-mc/ribbon-synth/blob/a793afc33dc0b0854e5ca8a34c22e9d98a125b73/faust/mcRibbonSynth.dsp) is a second MIT-root lead (source blob af146e17caaf28dccbe4ee04cc8d65ae5858576b). The full source uses oscillator, smoothing, noise, gain and effect library dependencies. It remains an unqualified lead requiring complete closure and lineage review; it was not added to this family replay.

## Readiness and validation

Spark's public custody scan remains unchanged. The scoped Gmail search returned zero matches; the known Notion collection returned nine records without a new authenticated signed artifact reference. Search details and limits are recorded in `signed-artifact-packet-search-2026-10-24.json`. No private holdout content was accessed.

The original-scope readiness replay still has no verified gates: `pilot_ready=false`, `training_authorized=false`. The new pair must receive canonical admission before it can be included in a newly scoped signed dataset. Remaining prerequisites include independent semantic review, exact context rights/admission, independent evaluation families, authenticated signed T07 snapshot/partition and trusted custodian key binding, followed by scoped baseline, reward/group-drop, environment/model and pilot-package evidence.

**37 tests pass**, including 15 new exact-packet tests. Mutations cover changed prompt/context, invented promotion, wrong tokenizer binding or length, cross-source histories, missing/duplicate products, changed control coefficients, incomplete signed coefficient coverage, accepted negative controls, NaN results and missing samples. The binder is a local consistency check; hashes are not cryptographic authentication of report claims. Structural, tokenizer, capture/model and retained full-history binding checks were replayed separately before building the packet.

Reproduction scripts are retained under `scripts/diagnostics/`. They use the existing enclosing recovery workspace `work/` inputs; candidate screening also uses the preserved prior comparison population. No active policy, source bytes, signatures, dataset admission or training authorization changed.

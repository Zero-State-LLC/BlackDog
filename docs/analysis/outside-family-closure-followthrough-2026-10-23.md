# Outside-family closure follow-through

## Observed results

The `decimal` alias was tested with its exact original `frac` definition from
the pinned maths library. Both source spans were checked against their original
Git blob and accounting hashes. The explicit two-member closure compiled and
passed numerical diagnostics at 44.1 and 48 kHz; omission of `frac` failed with
`unbound_symbol`. Its helper belongs to the existing comparison-connected family,
and its recorded rights remain training-only. Technical closure resolution does
not make it an independent evaluation candidate.

For the four evaluation-eligible aliases, the recorded local members were bound
to exact original spans and Git blobs. The next unresolved external members are:

| Alias | Bound local members | External review frontier |
| --- | ---: | --- |
| peak_envelope | 2 | ba.tau2pole |
| goertzel | 5 | ba.sAndH, ba.time, ma.SR, ma.PI, plus platform SR |
| mth_octave_analyzer_default | 3 | fi.tpt_df_fmin, fi.lowpass6e_tpt_df, fi.highpass6e_tpt_df |
| mth_octave_spectral_level_default | 4 | Analyzer dependencies plus si.smooth, ba.tau2pole, ma.EPSILON, ba.linear2db |

These are recorded dependency frontiers, not complete compiler-proven closures.
The samplerate and PI members have partial recorded mappings; platform and
per-member source/rights evidence still must be reconciled. No external helper
was admitted merely because its containing file was available.

## Independent evaluation search

The 111 evaluation-eligible Faust examples in the preserved inventory were
Git-blob verified and reconciled with the existing ledger. All already belong
to the large selected family. A different example filename is not new coverage.

Two additional public repositories were inspected at immutable commits:

- [bitDSP-faust](https://github.com/rottingsounds/bitDSP-faust/tree/d70843492b65bb2cb9cf97c2240905fefacc7383):
  full_adder, silence, and bitrot_flip with its coin helper.
- [dsp-course-faust](https://github.com/Fr0stbyteR/dsp-course-faust/tree/67f45a31a510513116c4839b3b654a60b485a715):
  cross and panner programs.

Repository MIT notices and selected source files were fetched at those commits
and Git-blob verified. This is notice evidence, not canonical T05 admission or
an independent rights ruling. Extracted bitDSP definitions preserve exact spans;
the local helper closure has no external imports. Original files and notices
remain outside Git.

All five candidates passed bounded native and signal diagnostics. One first
attempt had a harness input-count error; explicit harness arguments fixed it in
a separate run. Original target bytes were unchanged and both attempts retained.
Across the five candidates and decimal: six final native passes, 12 positive
signal runs, 12 wrong-reference rejections and one omitted-helper rejection.
All 32 receipt files, including the initial harness attempt's native receipt,
were hash-verified; compiler/signal schemas and signal digests checked.
The full-adder harness cycles all eight binary input triples. Panner diagnostics
cover the default pan setting only; none of these results claims full contract
coverage or independent semantic approval.

## Remaining blocker

Shipping raw/canonical clustering was rerun on all 1,430 original candidates,
19 public comparisons and five new closures. All five new candidates join the
comparison-connected component. Direct containment applies to full_adder and
panner; collective membership also connects the new candidates. This does not
adjudicate authorship or COPY. The expanded graph contains 1,454 identities and
12 components. Components and normalized-content family digests were independently
reconstructed; no prior family was split. The canonical recorded graph was not
modified or replaced.

No independently admissible evaluation candidate was established. Public
source review and FLOOR/family adjudication remain prerequisites to a trustworthy
split. The evidence packet distinguishes direct containment from collective
membership; it must not be converted into an automatic exemption. TOKEN_FLOOR=40
remains provisional, T07 unfrozen, admission NOT_GRANTED. Baseline, task-bound
reward and representative environment evidence do not substitute for these gates.

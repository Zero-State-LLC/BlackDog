# Source rights inventory

T05 records candidate Faust corpora as metadata. No source tree and no
program text is in this repository. The machine-readable rows are
[corpus/rights-inventory.v1.json](../corpus/rights-inventory.v1.json).
Cleared files and functions also have a row in
[corpus/notice-manifest.v1.json](../corpus/notice-manifest.v1.json)
(path, blob id, copyright, license). The rights transitions are
[dataset-lifecycle.md](dataset-lifecycle.md).

Counts at this pin: **30 cleared**, **14 rejected**, **2 need a human**.
A cleared copyleft row is training-only. It is not permission to commit
the files or to ship model output that copies them. Bare BSD is cleared
for training and eval and is not redistributed.

Policy is [ADR-0003](adr/0003-licensing-and-data-rights.md) (D-004,
D-007, D-013). This document is not legal advice. Every claim in the
JSON is OBSERVED or INFERRED. No row is SPECULATIVE: the GitHub long
tail was left out instead of guessed.

Rows backed by license text read at the pin name
`Boof (delegated by Danny 2026-10-17)` as reviewer. These two rows
rest on inferred evidence and keep a null reviewer. They are not
cleared:

- `faust-examples-copyright-only`
- `faustlibraries-attribution-gap`

## How the rows were read

On 2026-10-17 the pinned trees were checked out outside this repository
and classified. File bodies were not written into the repo. The Faust
checkout used for examples and impulse tests is commit `8c00913e`
(tag 2.88.0). Content-hash dedupe of vendored copies used every
`.dsp` and `.lib` blob at that commit, not only `examples/`.

The GitHub long tail in research F12 was not re-surveyed repository by
repository. It is not a row, and nothing from it is cleared.

Header-less, after D-013, means the leading comment has no license or
copyright text and the file has no `declare` of license or copyright
under any prefix. A comment that only repeats the GRAME or INRIA LGPL
boilerplate does not by itself take a file out of the header-less set.
`declare author` alone does not either.

## Decisions

| Id | Decision | License class | Files or functions |
| --- | --- | --- | --- |
| faust-examples-headerless | rights_cleared | LGPL-2.1-or-later, train only | 159 |
| faust-impulse-headerless | rights_cleared | LGPL-2.1-or-later, train only | 59 |
| faust-examples-mit | rights_cleared | MIT, redistribute | 49 |
| faust-examples-bsd | rights_cleared | bare BSD, no redistribute | 40 |
| faust-examples-stk | rights_cleared | STK-4.3, redistribute | 22 |
| faust-examples-guitarix | rights_cleared | GPL-2.0-or-later, train only | 1 |
| faust-impulse-bsd | rights_cleared | bare BSD, train only | 30 |
| faust-impulse-deprecated-libs | rights_cleared | LGPL-2.1-or-later, train only | 3 |
| faust-impulse-mixed | rights_cleared | LGPL-2.1-or-later, train only | 3 |
| faust-impulse-stk | rights_cleared | STK-4.3, train only | 4 |
| faust-gpl-midi-tester | rights_cleared | GPL v3, train only | 2 |
| faust-gpl-thru-zero-flanger | rights_cleared | GPL, train only | 1 |
| faust-examples-copyright-only | needs_human | NLFfm, no license in the file | 1 |
| faustlibraries-bsd-3-clause | rights_cleared | BSD-3-Clause, redistribute | 1 |
| faustlibraries-gpl-2.0-or-later | rights_cleared | GPL-2.0-or-later, train only | 2 |
| faustlibraries-gpl-3.0-only | rights_cleared | GPL-3.0-only, train only | 38 |
| faustlibraries-isc | rights_cleared | ISC, redistribute | 1 |
| faustlibraries-lgpl-2.1-only | rights_cleared | LGPL-2.1-only, train only | 6 |
| faustlibraries-lgpl-2.1-or-later | rights_cleared | LGPL-2.1-or-later, train only | 742 |
| faustlibraries-lgpl-3.0-only | rights_cleared | LGPL-3.0-only, train only | 2 |
| faustlibraries-licenseref-lgpl-2.1-or-later-with-faust-exception | rights_cleared | LGPL with Faust exception, train only | 29 |
| faustlibraries-mit | rights_cleared | MIT, redistribute | 170 |
| faustlibraries-stk-4.3 | rights_cleared | STK-4.3, redistribute | 533 |
| faustlibraries-unlicense | rights_cleared | Unlicense, quantizers.lib | 16 |
| faustlibraries-attribution-gap | needs_human | license text, no copyright string | 38 |
| faustlibraries-agpl-functions | rights_rejected | AGPL-3.0-only | 2 |
| faustlibraries-undeclared | rights_rejected | no declare and no header | 137 |
| faustlibraries-tubes | rights_rejected | unlicensed | 1 |
| faustlibraries-mi | rights_rejected | unlicensed | 1 |
| faust-impulse-effect-mit | rights_cleared | MIT, train only | 1 |
| faust-impulse-effect-stk-4.3 | rights_cleared | STK-4.3, train only | 65 |
| faust-impulse-effect-undeclared | rights_rejected | unlicensed | 1 |
| faustplayground-headerless | rights_cleared | LGPL-2.1-or-later, train only | 73 |
| faustplayground-stk | rights_cleared | STK-4.3, redistribute | 10 |
| faustplayground-bsd | rights_cleared | bare BSD, train only | 5 |
| faustplayground-blow | rights_cleared | LGPL-2.1-or-later, train only | 2 |
| pd-faustgen-mixer | rights_rejected | vendored-duplicate | 1 |
| pd-faustgen-resonator | rights_rejected | unlicensed | 1 |
| pd-faustgen-mit | rights_cleared | MIT, redistribute | 7 |
| faustide-examples | rights_rejected | vendored-duplicate | 227 hashed |
| faustlive-examples | rights_rejected | vendored-duplicate | 102 hashed |
| faustwasm-tests | rights_rejected | vendored-duplicate | 18 hashed |
| faustgen-supercollider | rights_rejected | vendored-duplicate | 1 hashed |
| syfala-examples | rights_rejected | unlicensed, plus one CC-BY-NC-SA-4.0 file | 59 |
| fausteditor | rights_rejected | out of scope, zero Faust files | 0 |
| faust-architecture | rights_rejected | C++ architecture, not the DSP corpus | 2 dsp noted |

Pins:

- `grame-cncm/faust` tag 2.88.0, commit `8c00913e44d42f9d25aa3f1a0d500bde5662d7bc`.
- `grame-cncm/faustlibraries` commit `2edec0537f536eaa130d42c354884d7db971663c` (no tag; research F26 recorded this commit).
- Sister repositories are pinned to the commits named in the JSON.

## Where the recount differs from the briefing

`faust-examples-headerless` is 159 files. The previous 181 minus 20
smartKeyboard MIT files, `harmonicExciter.dsp`, and `NLFfm.dsp` is 159.
The note's 158 is a unique-content count: `examples/smartKeyboard/associatedEffects/reverb.dsp`
is a byte-identical copy of `myEffect.dsp`, so one path is the extra
file. `elecGuitarEffect.dsp` also has no MIT header and stays. Both
copies stay in the row. `faust-impulse-headerless` is 59, which matches
the briefing. `constant`, `echo_bug`, `grain3`, and `priority` carry
only flattened GRAME LGPL declares and stay in that set. `echo_bug`
also names Guillot, which is why attribution is incomplete.

No Apache-2.0 function declare exists at the faustlibraries pin. The
earlier "8 Apache" count is not in this tree.

`motion.lib` has 23 undeclared functions out of 27 non-import
definitions (4 MIT). `aanl.lib` has 13 undeclared out of 50 (37 MIT).
The briefing's 29/33 and 15/52 counted import aliases as functions.
Those undeclared functions are rejected. `tubes.lib` (55 definitions)
and `mi.lib` (15) are rejected as whole files; their prose is not a
grant.

Playground has 90 Faust files: 73 header-less (training-only under
COPYING), 5 bare BSD (training only), 2 Blow-bottle files (training
only), and 10 STK cleared with a notice. The two Blow-bottle files
also carry STK text, so 12 files mention STK and 10 are the cleared
STK row. Exact content-hash matches against faust and faustlibraries:
0. Near-duplicates remain a T06/T07 requirement.

faustide: 26 exact content matches and 201 stale files, out of 227.
The briefing's 143 exact and 83 stale was not reproduced against sha256
of the file bytes at these pins. faustlive: 34 exact and 68 stale, out
of 102 `.dsp`/`.lib` blobs, including `Resources/Examples_bckp`. Some
of those blobs are libmicrohttpd and PortAudio `.lib` binaries, not
Faust. faustwasm tests: 0 exact, 18 stale. faustgen-supercollider:
0 exact, 1 stale. pd-faustgen `mixer.dsp` does not hash-match
`examples/misc/mixer.dsp`; it is still rejected as a vendored copy.

Pattern-match overloads (`take`, `parallelOp`, and the rest) share a
name. Their inventory ids add `@` and the source line so one definition
is one unit.

## Copyleft

GPL and LGPL rows that are cleared are training-only. D-004 forbids
redistributing that source, including in a released dataset. The Faust
exception in `examples/README.md` and in several library headers lets a
larger Faust program distribute the compiler's compiled output under
another license. That sentence does not mention model output. Reading
it as permission to emit Faust source is INFERRED and is not accepted
here.

`examples/misc/guitarix.dsp` is cleared as GPL-2.0-or-later because the
header beats the LGPL declare. It is training-only. Do not emit it.

STK-4.3 is other-permissive under D-013. Cleared STK rows redistribute
only when the row is not an impulse test. A redistributed STK unit
bundles the STK-4.3 permission notice: each notice row says so, and
the licence text is stored once under `license_texts`. Impulse rows,
including `effect.lib` functions, are training only and do not carry
that redistribution duty.

Bare BSD rows in `examples/` may train and eval. They may not be
redistributed. Impulse BSD is training only.

## Signed header-less rows

`faust-examples-headerless` cites `examples/README.md` at `8c00913e`,
section "## Licence" (LGPL-2.1-or-later, copyright 2003-2023 GRAME,
plus the compiled-code exception). The evidence label is OBSERVED.
Boof signed it. The row is training-only and is not redistributed.
About 70 files name a non-GRAME author, so `attribution_complete` stays
false.

`faust-impulse-headerless` cites root `COPYING.txt` at the same commit,
which is LGPL. Boof signed it. The row is training-only, not
redistributed, and the eval guard refuses `eval` and `holdout`.

## Unsigned rows

`faust-examples-copyright-only` is `NLFfm.dsp`: a Romain Michon
copyright declare and no license. D-013 allows STK or training-only.
The file states neither, so the row stays unsigned.

`faustlibraries-attribution-gap` is functions whose license text was
read and whose copyright string is empty. The reviewer stays null.

`FFT.dsp` and `DNN.dsp` sit in the cleared STK row. The holder string
adds "Julius O. Smith III (INFERRED from author JOS)". The license text
on those files was observed, so the row reviewer is Boof.

## Risks

- Clearing a whole faustlibraries file would copy AGPL functions
  (`processArray`, `tabulateNd` in `basics.lib`) into a snapshot. Those
  functions are rejected. The rest of the file is sliced.
- `tubes.lib` names Guitarix and has no license line. It is rejected as
  unlicensed. The project name is not treated as a GPL grant.
- Syfala has no repository license. One example is CC-BY-NC-SA-4.0.
  The tree is rejected.
- Impulse tests are an upstream numerical reference suite. Cleared
  impulse rows are training-only and the transition guard rejects
  `eval` and `holdout` for those paths.
- Faust IDE, Playground, FaustLive, faustwasm tests, and the
  SuperCollider faustgen example vendor overlapping programs. They are
  rejected as sources. Exact hashes are recorded. A byte-level miss can
  still be a near copy; that filter is not built yet.
- A full git clone of Faust pulls submodules this inventory did not
  read. Ingest must use the pinned paths, not a recursive clone.
- `debian/copyright` in the Faust repo still says GPL-2. `COPYING.txt`
  at tag 2.88.0 says LGPL-2.1-or-later. The root COPYING file is the
  grant used here.
- fausteditor has both COPYING (LGPL) and LICENSE (GPL-3.0) and zero
  Faust files. It is rejected as out of scope. Do not pick the GitHub
  license badge over those two files.
- Architecture files stay out of the DSP corpus. ADR-0003 still
  requires a separate review before a plugin release that compiles one
  in.
- SPECULATIVE evidence cannot move a source. An unrecognized license
  stays `DISCOVERED`.

## What a later task still has to do

T06 and T07 own normalization, deduplication of normalized examples,
and the split. This inventory does not freeze a snapshot. D-013 adds a
proposed gate for those tasks: an n-gram or AST near-duplicate filter
on generated `.dsp` against the training-only set. The threshold is
not set. Playground's zero exact matches do not retire that gate.

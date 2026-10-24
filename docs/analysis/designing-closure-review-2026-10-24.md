# Designing Sound candidate closure and provenance review — 2026-10-24

Resolved and compiler-checked the Bitcrush and Bouncing Ball dependency closures for an explicit library pin. Both remain **not admitted, training-only by library rights, and comparison-connected**. No independent evaluation family was obtained.

## Provenance

Both files are pinned to [Designing Sound Experiments commit dacffbdd](https://github.com/materializepath/designing-sound-experiments/tree/dacffbddca08a3b16e247fc1453657939be7049e). The root notice is MIT, and both sources declare `Agent Cooper + Robert`. GitHub path history at that pin returns the same initial commit, `7a9e41ec882ec2e54f4a1074bac64efaf49d3e38`, for both DSP files.

The initial commit and README attribute the demonstrations to techniques from Andy Farnell's Designing Sound. That alone does not establish copied code. AGENTS.md, CLAUDE.md, PLANNING.md and ARCHITECTURE.md were inspected as provenance evidence, not adopted as instructions for this project. They document agent workflows but do not identify which exact model, if any, produced either DSP file or supply a source-specific teacher-use receipt. Exact teacher provenance and independent source lineage remain unverified. Presence of CLAUDE.md is not proof of a particular Claude model or its use on these files.

`designing-provenance-2026-10-24.json` retains the inspected context-file hashes and research limits. No maintainer attestation is inferred from repository metadata.

## Complete pinned closures

The original sources import stdfaust without specifying its revision. These diagnostics explicitly select faustlibraries `2edec0537f536eaa130d42c354884d7db971663c`; they do not reconstruct the author's historical environment.

| Candidate | Dependency names | Exact definition spans | Missing references |
|---|---:|---:|---:|
| Bitcrush | 20 | 26 | 0 |
| Bouncing Ball | 9 | 12 | 0 |

Every library blob is checked against the pinned Git tree. The conservative lexical closure retains overloads and precision variants; minimality is not claimed. Exact bytes, transitive edges and hashes are recorded in the two closure JSON reports. Full source text remains in the enclosing recovery workspace, not committed as cleared corpus material.

Both original import-based programs and extracted closures compile with Faust `-single -ftz 0` and GCC `-O1 -ffp-contract=off -fno-fast-math`. They each have zero audio inputs and two outputs. At 44.1, 48, 96 and 192 kHz, the extracted versions produce **byte-identical default-control audio** to their originals for **24,000 frames per rate**. All samples are finite. Removing PI from each closure correctly fails compilation. Local replay verifies every capture hash, matrix, dimension and byte comparison.

Each child retains the existing 20 CPU second, 1 GiB address-space, 16 MiB file and 30 second wall limits. The complete local archive is `work/designing-closure-evidence.tar.gz`; its hash is in each compiler-verification report. It contains both sources and closures, generated headers/drivers/executables, all captures, negative sources, runner scripts, driver dependency and logs.

This establishes closure sufficiency and default-control equivalence for the selected pin. It is not an arbitrary-control, long-history or cross-version guarantee.

## Semantic finding: Bouncing Ball rate

A derivative diagnostic exports the existing `trig` signal from the unchanged closure. Local binary replay confirms a 12,000-frame interval at the default rate control of 4:

| Sample rate | Measured trigger rate | Labeled rate |
|---:|---:|---:|
| 44,100 Hz | 3.675 Hz | 4 Hz |
| 48,000 Hz | 4 Hz | 4 Hz |
| 96,000 Hz | 8 Hz | 4 Hz |
| 192,000 Hz | 16 Hz | 4 Hz |

The cause is the literal 48,000 in the samples-per-bounce calculation. A general sample-rate contract would require a repair; a 48 kHz-only contract could preserve the original target. Neither was silently substituted or admitted. `designing-rate-verification-2026-10-24.json` binds the derivative probe source and captures to the original closure.

Bitcrush's integer-conversion quantizer still needs an explicit task contract for its intended quantization semantics. Compiler equivalence alone does not decide that semantic question.

## Rights and independence

Existing exact notices resolve all 38 library spans across the two closures; **no new notices were required**. Both library closures remain training-only because they contain LGPL members. Root MIT provenance does not override those dependency restrictions, establish teacher-output rights, or grant canonical admission.

The full closure family replay now contains **1,539 identities, 12 components and 28,769 joining operations**. Both candidates join the comparison component under the unchanged floor-40 provisional H1 collective policy. They also share one upstream project and cannot count as separate independent projects. No evaluation eligibility or authorship conclusion is inferred from a lexical policy join.

## Exact repaired pair and readiness

The repaired pair's exact review packet and original-scope readiness were replayed. Its source, target, prompt, dependency context and 363-token encoding are unchanged. Its earlier 87,528-product seeded qualification remains supplemental evidence; no new numerical claims were transferred from these unrelated candidates.

The public Spark custody scan is unchanged; the scoped Gmail search returns no relevant messages and PR #115 has no reviews supplying the semantic decision. These are bounded searches, not proof that no artifact exists anywhere. No private holdout content was accessed.

**pilot_ready=false; training_authorized=false; no verified gates.** Remaining blockers: independent exact-pair semantic approval; canonical pair/context admission; independent evaluation families; authenticated signed T07 snapshot/partition and trusted custodian key binding; then scoped baseline, reward/group-drop, environment/model and pilot-package evidence.

All **37 binding, modular-contract, closure and readiness tests pass**. Builders, bounded runners, independent capture verifiers, provenance metadata and family/rights reports are retained. No active policy, acceptance threshold, target contract or signed gate was relaxed.

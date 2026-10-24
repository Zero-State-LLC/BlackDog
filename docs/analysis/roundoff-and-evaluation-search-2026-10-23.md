# Roundoff isolation and evaluation search — 2026-10-23

Seven additional complete source candidates from tai-studio/faust-sc were screened
against the preserved population. All join the existing comparison family under
the unchanged raw/canonical and collective policy. The replay contains 1,472
identities, 12 components and 27,392 joining operations; reconstruction agrees.
No independent evaluation candidate was qualified.

## Pinned candidate evidence

The source is pinned to
[cfe98cc1](https://github.com/tai-studio/faust-sc/tree/cfe98cc1758475bef07512d57fbe15ff8a7abbbe).
The LICENSE and three library files were fetched and their Git blob hashes
verified. The repository carries an MIT notice from TAI Studio (2020), but
per-unit lineage and semantic review remain separate requirements.

Candidates are map, ms, rotate2, linexp, rotate_ins, gate and wrap. These extracted
closures use intrinsic operations; wrap includes its local wrap2 dependency.
Foreign-function and unresolved-dependency candidates were not promoted.
The new source bodies remain outside Git; the evidence index binds their exact
spans, closure hashes and join witnesses.

Canonical forward-containment witnesses include ms (29/42 shingles), rotate2
(32/35) and wrap (37/53) against a preserved comparison source. Collective joins
also include these candidates. No marginal-coverage option, boilerplate exemption
or policy change was used to manufacture independence.

## Spectral roundoff model

A separate Python diagnostic isolates filter coefficient and intermediate-state
rounding while holding meter smoothing in double precision. It reuses the
existing independent mathematical filter reference and float32 stimulus.
Coefficients are calculated in double and then rounded; this is not an exact
simulation of Faust expression evaluation or a compiler qualification result.

At 48 kHz, rounded coefficients with double accumulation alone produce a maximum
middle-band sine-meter error of about 0.02595 dB. Reversing the branch order does
not remove that coefficient-only error. Float32 direct-form-I accumulation with
high-pass first produces approximately 1.07658 dB; summing double products and
rounding only each output reduces that model's error to 0.02519 dB. At 44.1 kHz,
the corresponding coefficient-only error is about 0.000551 dB.

This evidence motivates work on coefficient representation and accumulation
rather than another ordering-only sweep. It is not proof that float32 cannot
meet the contract, and the double-product diagnostic is not a production repair.
The production failure, fixed tolerances and original sources remain intact.

## Rights and signed readiness

Public issue searches found no additional license authority for `_tanhalf` or
`_tpt_df`. Both remain unresolved. An unsent clarification draft records the
exact introduction commits and downstream pin; nothing was sent upstream.

A separate public-artifact handoff checklist distinguishes the signed snapshot,
public evidence objects, matching scope digests and trusted public-key binding
from the already-recorded owner approvals and iPhone custody decision. No private
keys or holdout contents were accessed. No signatures were fabricated.

T07 remains unfrozen, TOKEN_FLOOR=40 provisional, and no admission gate is cleared
by this diagnostic checkpoint. Numerical repair, defensible helper rights,
independent evaluation membership and signed evidence remain open.

# Paired-float32 compilation isolation — 2026-10-23

Five standard-limit compiler probes narrow the remaining obstacle without
qualifying a repair. Fixed-rate full graphs at 44.1 and 48 kHz both time out at
15 seconds. A single compensated section compiles in 6.310 seconds. Thus the
problem persists after sample-rate selection is removed, while an isolated
section can compile within the current limit.

A fixed-48-kHz full graph with fewer barriers in the compensation expressions
also times out (15.090 seconds). A further variant using only an upper-bound
barrier likewise times out. Neither reaches signal validation. The original
barrier source and prior standard/extended timeouts are preserved. No resource
limit, reference tolerance, production source or meter floor was changed.

These compiler receipts were verified against exact source hashes and schemas.
The full-graph timeout remains a blocker. A single-section compile pass does not
prove numerical equivalence or authorize replacing the spectral implementation.
The next engineering question is whether bounded separately compiled sections
can preserve paired states and the full meter contract, or whether a different
representation can compile as one graph within the existing limit. Neither path
is claimed complete here.

## Evaluation candidates

Fetched pinned bitDSP_conversion.lib at commit
[d7084349](https://github.com/rottingsounds/bitDSP-faust/blob/d70843492b65bb2cb9cf97c2240905fefacc7383/lib/bitDSP_conversion.lib)
and verified Git blob f6e11f6bdad22fee13ca3528ae2ce52cfce9d9c5.
Screened complete dec2bitBus and bit_to_int32 definitions, including all their
pattern alternatives and recursive definition where applicable. Neither has
external dependencies. Both join the existing comparison family under the
unchanged policy. No independent evaluation candidate was qualified.

The replay now contains 1,477 identities, 12 components and 27,485 joining
operations; reconstruction agrees. Exact source spans, closure hashes and full
family/edge artifacts are retained. MIT source notices do not override family
independence or the remaining semantic qualification requirements.

## Licenses and signed readiness

[Upstream issue #321](https://github.com/grame-cncm/faustlibraries/issues/321)
was checked and remains open with no comments at this checkpoint. The two helper
licenses remain unresolved; posting a clarification request is not a grant.

No new signed public snapshot bundle or trusted custodian public key has become
available. Existing owner approvals and iPhone custody decisions remain
recognized. The latest readiness replay still has no verified admission gates;
this diagnostic checkpoint does not replace its dataset scope with the expanded
candidate population. T07 remains unfrozen, TOKEN_FLOOR=40 provisional, and
training is not authorized.

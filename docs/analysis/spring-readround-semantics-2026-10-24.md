# Controller-preserving predelay: provisional technical review

The previous demand-rounded target changes the equality/change decisions inside `de.sdelay` and therefore its crossfade schedule. This alternative keeps the original continuous demand and the entire pinned controller body unchanged. It changes only the two integer read positions in `ddi` to `int(d0 + 0.5)` and `int(d1 + 0.5)`.

The copied library is clearly marked as modified and retains the full original LGPL notice and Faust exception. Its unchanged controller body has SHA-256 `c85568756413976e414e4206012565bf36ed43b607712dfd1fd1758d77181a6e`. This is structural evidence: the delay outputs do not feed back into the control state. It is not a separate runtime trace of controller internals.

## Supported contract

For finite nonnegative demands within the configured maximum, read offsets use nearest-sample rounding with half ties upward. The existing delay primitive bounds the reads. The underlying continuous-demand crossfade state machine and its 4,096-sample interpolation remain unchanged. This preserves the controller's source-level behavior, not byte-identical audio: read offsets can intentionally differ from truncation by one sample.

All 23 isolated impulse-oracle cases pass, including half-sample boundaries and the maximum offset. Twelve corresponding cases reject the original truncation against the nearest-sample contract. Full spring zero-delay impulse captures are byte-identical to the original at six sample rates after three-second settling. The separate platform report determines which other fixed-fixture runs have completed; this review does not imply missing platform cases passed.

## Live characterization

Same-input/control 30-second histories at 48 kHz give:

| History | Prior demand-rounded NRMS vs original | Read-rounded NRMS vs original | Read-rounded maximum difference |
| --- | --- | --- | --- |
| Predelay sweep | 1.21899 | 0.0508736 | 0.00123861 |
| All-control switching | 0.864424 | 0.106663 | 0.0988222 |

These are waveform differences, not perceptual scores or acceptance thresholds. The all-control read-rounded reference attenuates 1,140 frames; the original attenuates 1,032. The six eight-second audition clips preserve actual gain. No listening acceptance or click-free claim is made.

## Disposition

Prefer this narrower alternative for further review because it fixes read-position rounding without changing the controller expression. Keep both earlier targets and their failures immutable. Do not silently replace a previously qualified source/module. Exact audio equivalence is not the proposed contract; human musical acceptance of the intentional sample-position change is still open, as are wider-duration/rate live testing, mobile execution, hardware deadline guarantees and the low-rate Q/decay-model question.

The copied full helper library is an explicit supplied dependency, not a minimal closure claim. Canonical closure/admission and instruction-pair review must include it. Source rights remain blocked on the spring author response; retaining the helper's notice does not license the parent DSP. Both the source and helper have direct floor-40 family witnesses to their parents; neither is an independent evaluation candidate. No signed readiness gate is cleared.

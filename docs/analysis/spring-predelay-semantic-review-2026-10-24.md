# Provisional spring predelay semantic review

This is an agent technical review, not independent listening acceptance or production admission.

## Contract supported by evidence

The target rounds the smoothed nonnegative delay demand to the nearest sample **before** the pinned `de.sdelay` controller. Settled 0/200 ms impulse endpoints use a three-second block-rounded warmup. Cross-platform replay tests the exact target, a 64-frame control clock, float32 fixture inputs/controls, double DSP state, float32 output conversion and the linked final guard. There are still 300 modes and dual-mono outputs.

## Material live-control change

The unchanged library `delays.lib`, pinned at `2edec0537f536eaa130d42c354884d7db971663c`, lines 152–210, compares the incoming demand with stored delay demands (`d!=d0`, `d!=d1`) to trigger its 4,096-sample crossfade. Integer rounding before this state machine changes the sequence of equality/change decisions. Consequently a one-sample settled correction is **not** evidence of a one-sample-only live behavioral change.

Two 30-second same-fixture comparisons at 48 kHz characterize the difference:

| History | Normalized RMS difference from original | Largest absolute difference |
| --- | --- | --- |
| Continuous predelay sweep, other controls default | 1.21899 | 0.0251952 |
| All seven controls alternate endpoints every 0.37 seconds | 0.864424 | 0.8434004 |

The all-control original attenuates 1,032 frames; the repaired target attenuates zero in this fixture. This change is not a transparency improvement claim. Neither a waveform difference nor sample-step magnitude establishes audible clicking or preference. The retained actual-gain audition WAVs cover the first eight seconds of each variant; no listening acceptance is asserted.

## Disposition and next bounded repair

- Accept the recorded platform comparisons only for the exact rounded-demand target and fixed fixtures.
- Keep musical/legacy live equivalence **OPEN**. Do not replace the production target on this evidence.
- Investigate a separate wrapper that preserves the original continuous-demand controller and rounds only the two delay-line read positions. Bind its derived code, retained library notices, source hash and new receipts independently. That alternative has not been implemented or qualified here.
- Keep the original 8 kHz late-tail contrast result (76.9 versus exploratory >100) as rate-dependent physical-model review, not a confirmed numerical defect.
- Human acceptance still needs transition behavior, decay/Q labeling and dual-mono presentation review. Source rights, independent families and signed readiness are separate gates.

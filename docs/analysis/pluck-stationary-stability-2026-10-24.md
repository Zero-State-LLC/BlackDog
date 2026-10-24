# Constant-control loop stability argument

For fixed n and a with |a| < 1, A(z) = (a + z^-1)/(1 + a z^-1) is a stable allpass. The delay z^(-(n+1)) is stable and has unit magnitude on the unit circle. The averaging term has magnitude |0.499(1 + exp(-jω))| = 0.998|cos(ω/2)| ≤ 0.998.

Consequently the complete stable open-loop transfer L has H-infinity norm at most 0.998 < 1. The feedback inverse 1/(1-L) is stable by the convergent small-gain argument. This covers all closed-loop modes, rather than only the fundamental root. It applies to the constant-control ideal linear model after reset transients.

The saved model grid contains exactly all 104 supported integer notes at four rates. Every allpass coefficient satisfies |a| < 1; the largest absolute value is 0.44519180428265775. Every delay n is at least 3. Thus all 416 analyzed stationary models meet the sufficient condition. This is not an exhaustive continuous-control domain claim.

This proof concerns exact arithmetic. It does not certify floating-point limit cycles, arbitrary coefficient modulation, or reset/tag transitions; those require their own numerical evidence. It does not set musical acceptance criteria or supply independent review, provenance, admission or signed readiness. The provenance issue remains open with zero replies at this refresh.

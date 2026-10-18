"""FLOOR protocol acceptance bounds (D6, ratified 2026-10-18 12:34 AM PT).

These are the acceptance bounds for choosing TOKEN_FLOOR. They do not
accept a floor value; see faustcoder.neardup.TOKEN_FLOOR_STATUS.

``NEEDS_HUMAN_REJECT_CLASS`` is a separate recorded rights ruling. It
is not part of D6 and it is not Danny's ratified text.
"""

from __future__ import annotations

from math import sqrt
from typing import NamedTuple

FLOOR_BOUNDS_STATUS = "ratified"
FLOOR_CANDIDATES = (40, 30, 20)  # highest passing wins
FLOOR_BUCKETS = ((15, 19), (20, 29), (30, 39), (40, None))
FLOOR_GATED_OPERATORS = ("verbatim_raw", "rename_canonical")
FLOOR_RECALL_LOWER_BOUND = 0.90  # 95% Wilson lower bound, per cell
FLOOR_CELL_N = 100
FLOOR_MIN_DISTINCT_WINDOWS = 50
FLOOR_HOSTS_PER_WINDOW = 2
FLOOR_FP_BUDGET_FRACTION = (1, 20)  # 5%
FLOOR_FP_FULL_LABEL_MAX = 100
FLOOR_FP_MIN_SAMPLE = 50
FLOOR_UNION_COVERAGE = (1, 2)
# 95% two-sided normal quantile, the usual z = 1.96.
# ``max_misses(100) == 4`` ("at most 4 misses at n = 100") depends on
# this z and on the Wilson score interval with no continuity correction.
_Z = 1.959963984540054


class NeedsHumanRejectClass(NamedTuple):
    """A rights ruling stored apart from the D6 bounds."""

    text: str
    who: str
    authority: str
    record: str
    when: str
    part_of_d6: bool


# Separate recorded rights ruling. Not part of D6. Not Danny's ratified text.
NEEDS_HUMAN_REJECT_CLASS = NeedsHumanRejectClass(
    text=(
        "needs_human sources count as reject-class until a human "
        "clears them (fail closed)"
    ),
    who="Boof (orchestrator)",
    authority=(
        "rights call under Danny's 2026-10-17 BlackDog "
        "rights/licensing delegation"
    ),
    record="rights-inventory.md:21-22",
    when="2026-10-18 ~12:57 AM PT",
    part_of_d6=False,
)


def _require_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    return value


def _clamp_unit(value: float) -> float:
    """Clamp a Wilson endpoint onto ``[0, 1]``."""
    return min(1.0, max(0.0, value))


def _wilson_bounds(k: int, n: int) -> tuple[float, float]:
    """Return the 95% Wilson interval for ``k`` successes in ``n`` trials.

    Two-sided, z = 1.96, with no continuity correction. Each endpoint
    is clamped to ``[0, 1]``.
    """
    k = _require_int(k, "k")
    n = _require_int(n, "n")
    if n < 1:
        raise ValueError("n must be positive")
    if k < 0 or k > n:
        raise ValueError("k must be between 0 and n")
    z2 = _Z * _Z
    phat = k / n
    denom = 1.0 + z2 / n
    center = (phat + z2 / (2.0 * n)) / denom
    margin = _Z * sqrt(phat * (1.0 - phat) / n + z2 / (4.0 * n * n)) / denom
    return _clamp_unit(center - margin), _clamp_unit(center + margin)


def wilson_lower(k: int, n: int) -> float:
    """Return the 95% Wilson lower bound on ``k`` successes in ``n`` trials.

    The result is clamped to ``[0, 1]``.
    """
    return _wilson_bounds(k, n)[0]


def wilson_upper(k: int, n: int) -> float:
    """Return the 95% Wilson upper bound on ``k`` successes in ``n`` trials.

    The result is clamped to ``[0, 1]``.
    """
    return _wilson_bounds(k, n)[1]


def fp_budget(n_cleared: int) -> int:
    """Return ``ceil(n_cleared / 20)`` with integer division.

    ``FLOOR_FP_BUDGET_FRACTION`` is 1/20. The expression
    ``-(-n_cleared // 20)`` is ceil division under Python's
    toward-minus-infinity ``//``, so a float cannot land one off.
    """
    n_cleared = _require_int(n_cleared, "n_cleared")
    if n_cleared < 0:
        raise ValueError("n_cleared must be non-negative")
    numer, denom = FLOOR_FP_BUDGET_FRACTION
    return -(-(n_cleared * numer) // denom)


def max_misses(n: int = FLOOR_CELL_N) -> int:
    """Return the most misses whose Wilson lower bound is still at least 0.90.

    At n = 100 that count is 4. The 4 depends on a two-sided Wilson
    interval with z = 1.96 and no continuity correction. A perfect cell
    that misses the bound returns -1, so the comparison fails closed.
    """
    n = _require_int(n, "n")
    if n < 1:
        raise ValueError("n must be positive")
    misses = 0
    while misses <= n and wilson_lower(n - misses, n) >= FLOOR_RECALL_LOWER_BOUND:
        misses += 1
    return misses - 1

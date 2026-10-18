"""FLOOR protocol acceptance bounds (D6, ratified 2026-10-18 12:34 AM PT).

These are the acceptance bounds for choosing TOKEN_FLOOR. They do not
accept a floor value; see faustcoder.neardup.TOKEN_FLOOR_STATUS.

Reviewer rulings (rights calls delegated to Boof): a ``needs_human``
source counts as reject-class until a human clears it (fail closed).
A copy that only a lower floor detects counts as a recall miss for
the higher floors.
"""

from __future__ import annotations

from math import sqrt

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
# Standard-normal quantile for a 95% two-sided interval.
_Z = 1.959963984540054


def _require_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    return value


def _wilson_bounds(k: int, n: int) -> tuple[float, float]:
    """Return the 95% Wilson interval for ``k`` successes in ``n`` trials."""
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
    return center - margin, center + margin


def wilson_lower(k: int, n: int) -> float:
    """Return the 95% Wilson lower bound on ``k`` successes in ``n`` trials."""
    return _wilson_bounds(k, n)[0]


def wilson_upper(k: int, n: int) -> float:
    """Return the 95% Wilson upper bound on ``k`` successes in ``n`` trials."""
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

    A perfect cell that misses the bound returns -1, so the comparison
    fails closed.
    """
    n = _require_int(n, "n")
    if n < 1:
        raise ValueError("n must be positive")
    misses = 0
    while misses <= n and wilson_lower(n - misses, n) >= FLOOR_RECALL_LOWER_BOUND:
        misses += 1
    return misses - 1

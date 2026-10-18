"""FLOOR acceptance bounds. Ratifying the bounds does not accept a floor."""

from __future__ import annotations

from faustcoder.floor_protocol import (
    FLOOR_BUCKETS,
    FLOOR_BOUNDS_STATUS,
    FLOOR_CANDIDATES,
    FLOOR_CELL_N,
    FLOOR_FP_BUDGET_FRACTION,
    FLOOR_FP_FULL_LABEL_MAX,
    FLOOR_FP_MIN_SAMPLE,
    FLOOR_GATED_OPERATORS,
    FLOOR_HOSTS_PER_WINDOW,
    FLOOR_MIN_DISTINCT_WINDOWS,
    FLOOR_RECALL_LOWER_BOUND,
    FLOOR_UNION_COVERAGE,
    NEEDS_HUMAN_REJECT_CLASS,
    fp_budget,
    max_misses,
    wilson_lower,
    wilson_upper,
)
from faustcoder.neardup import TOKEN_FLOOR, TOKEN_FLOOR_STATUS


def test_bounds_are_ratified_and_the_floor_value_is_not() -> None:
    """Ratifying D6 must not accept the provisional length constant."""
    assert FLOOR_BOUNDS_STATUS == "ratified"
    assert TOKEN_FLOOR == 40
    assert TOKEN_FLOOR_STATUS == "provisional"


def test_fp_budget_is_ceil_of_five_percent() -> None:
    assert FLOOR_FP_BUDGET_FRACTION == (1, 20)
    assert fp_budget(491) == 25
    assert fp_budget(480) == 24
    assert fp_budget(481) == 25


def test_four_misses_pass_and_five_miss() -> None:
    """4 misses at n = 100 is the plain two-sided Wilson interval, z = 1.96."""
    assert FLOOR_CELL_N == 100
    assert FLOOR_RECALL_LOWER_BOUND == 0.90
    assert max_misses(100) == 4
    assert wilson_lower(96, 100) >= 0.90
    assert wilson_lower(95, 100) < 0.90
    assert abs(wilson_lower(96, 100) - 0.9016) < 1e-4
    assert abs(wilson_lower(95, 100) - 0.8882) < 1e-4
    assert wilson_lower(96, 100) < wilson_upper(96, 100)


def test_perfect_cell_needs_35_trials() -> None:
    assert wilson_lower(34, 34) < 0.90
    assert wilson_lower(35, 35) >= 0.90
    smallest = min(n for n in range(1, 80) if wilson_lower(n, n) >= 0.90)
    assert smallest == 35


def test_candidates_and_buckets() -> None:
    assert FLOOR_CANDIDATES == (40, 30, 20)
    assert FLOOR_GATED_OPERATORS == ("verbatim_raw", "rename_canonical")
    assert len(FLOOR_BUCKETS) * len(FLOOR_GATED_OPERATORS) == 8
    assert FLOOR_BUCKETS[-1][1] is None
    previous_end = 14
    for index, (start, end) in enumerate(FLOOR_BUCKETS):
        assert start == previous_end + 1
        if end is None:
            assert index == len(FLOOR_BUCKETS) - 1
        else:
            assert end >= start
            previous_end = end

    def bucket(count: int) -> tuple[int, int | None] | None:
        for start, end in FLOOR_BUCKETS:
            if count < start:
                continue
            if end is None or count <= end:
                return (start, end)
        return None

    assert bucket(14) is None
    for count in range(15, 120):
        assert bucket(count) is not None


def test_sample_and_coverage_constants() -> None:
    assert FLOOR_MIN_DISTINCT_WINDOWS == 50
    assert FLOOR_HOSTS_PER_WINDOW == 2
    assert FLOOR_FP_FULL_LABEL_MAX == 100
    assert FLOOR_FP_MIN_SAMPLE == 50
    assert FLOOR_UNION_COVERAGE == (1, 2)


def test_wilson_bounds_stay_inside_the_unit_interval() -> None:
    for n in (1, 2, 35, 100):
        for k in (0, n // 2, n):
            lower = wilson_lower(k, n)
            upper = wilson_upper(k, n)
            assert 0.0 <= lower <= upper <= 1.0


def test_needs_human_reject_class_is_a_separate_rights_ruling() -> None:
    """Boof's fail-closed call is data on the protocol, not a docstring scrape."""
    ruling = NEEDS_HUMAN_REJECT_CLASS
    assert ruling.text == (
        "needs_human sources count as reject-class until a human "
        "clears them (fail closed)"
    )
    assert ruling.who == "Boof (orchestrator)"
    assert ruling.authority == (
        "rights call under Danny's 2026-10-17 BlackDog "
        "rights/licensing delegation"
    )
    assert ruling.record == "rights-inventory.md:21-22"
    assert ruling.when == "2026-10-18 ~12:57 AM PT"
    assert ruling.part_of_d6 is False

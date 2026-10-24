"""Exact float32 cutoff boundaries and the stock greater-or-equal selector."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).parents[2]/'scripts/diagnostics'))
from exact_switch_fixture import boundary_values, events, f32
from exact_switch_reference import exact_switch_reference


def test_top_and_lower_boundary_neighbors_straddle_equality():
    b=boundary_values()
    assert b['top'][0]<2304==b['top'][1]<b['top'][2]
    lower=[f32(x*b['ratio']) for x in b['lower_top']]
    assert lower[0]<2304==lower[1]<lower[2]


def test_exact_equality_selects_direct_form_and_strict_counterexample_does_not():
    b=boundary_values()
    controls=[(0,2304),(1,b['lower_top'][1])]
    actual=exact_switch_reference([0.]*128,48000,controls)
    strict=exact_switch_reference([0.]*128,48000,controls,strict=True)
    assert actual[4][0]==f32(1/200) and strict[4][0]==0
    assert actual[5][64]==f32(1/200) and strict[5][64]==0
    assert actual[0]==strict[0]==[0.]*128


def test_exact_event_schedule_is_ordered_and_float32_exact():
    e=events()
    assert [b for b,_ in e]==list(range(0,128,8))
    assert all(v==f32(v) for _,v in e)


@pytest.mark.parametrize('value',[1999,6001,float('nan')])
def test_exact_controls_respect_domain(value):
    with pytest.raises(ValueError):exact_switch_reference([0.]*64,48000,[(0,value)])

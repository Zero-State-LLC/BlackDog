"""Reference contract and causal control checks, without a Faust installation."""
import importlib.util
from pathlib import Path
import pytest

path = Path(__file__).parents[2] / 'scripts/diagnostics/tpt_spectral_reference.py'
spec = importlib.util.spec_from_file_location('tpt_reference_under_test',path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_zero_input_stays_at_exact_meter_floor():
    result = m.tpt_reference([0.]*128,48000,[(0,2000),(1,6000)])
    assert result[0] == [0.]*128
    assert all(ch == [m.f32(20*m.math.log10(2**-23)/200)]*128 for ch in result[1:])


def test_cutoff_change_is_causal_and_not_ignored():
    x = [m.f32(.25*m.math.sin(2*m.math.pi*440*i/48000)) for i in range(1024)]
    changed = m.tpt_reference(x,48000,[(4,6000)])
    frozen = m.tpt_reference(x,48000,[(4,6000)],frozen=True)
    assert changed[0] == frozen[0] == x
    assert all(a[:256] == b[:256] for a,b in zip(changed,frozen))
    assert any(a[256:] != b[256:] for a,b in zip(changed[1:],frozen[1:]))


@pytest.mark.parametrize('events', [[(0,1999)],[(0,float('nan'))],[(2,3000)],[(1,3000),(0,4000)],[(0,3000),(0,4000)]])
def test_invalid_controls_rejected(events):
    with pytest.raises(ValueError):m.tpt_reference([0.]*128,48000,events)


@pytest.mark.parametrize('rate,block,samples',[(True,64,[0.]*128),(48000,0,[0.]*128),(48000,64,[0.]*65),(48000,64,[float('nan')]*64)])
def test_invalid_reference_domain_rejected(rate,block,samples):
    with pytest.raises(ValueError):m.tpt_reference(samples,rate,[],block)

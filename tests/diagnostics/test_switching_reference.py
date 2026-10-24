"""Stock selector regression against pinned native double evidence."""
import importlib.util
from pathlib import Path
import pytest

path = Path(__file__).parents[2]/'scripts/diagnostics/switching_spectral_reference.py'
spec = importlib.util.spec_from_file_location('switch_ref',path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_matches_native_switching_impulse_checkpoints():
    # Captured Faust 2.88.0 double, fixed stock L=2304, matched f32 controls.
    # Source SHA256 e20aea8091786c0113ce6c9a102fae9a549f431ffd92780bbd8feb46e2f9220b.
    expected = [
        [-.24591315641519476,-.28181184345872656,-.3744611831508547,-.46711067262354816,-.6002943137405451],
        [-.26160479298886696,-.29295280666925994,-.385601870514039,-.47825135998673246,-.6114350011037294],
        [-.22516541868449863,-.26905032239798315,-.36169979101104976,-.4543492804837434,-.5875329216007401],
    ]
    actual = m.switching_reference([1.]+[0.]*4095,48000,[(0,2000),(8,6000),(24,2500),(40,3333.33)])
    for channel,values in zip(actual[1:],expected):
        assert [channel[i] for i in (0,512,1536,2560,4032)] == pytest.approx(values,abs=1e-7,rel=0)


def test_switching_control_is_causal():
    x = [m.f32(.25*m.math.sin(2*m.math.pi*440*i/48000)) for i in range(1024)]
    a=m.switching_reference(x,48000,[(4,2000)])
    b=m.switching_reference(x,48000,[(4,2000)],frozen=True)
    assert a[0]==b[0]==x
    assert all(c[:256]==d[:256] for c,d in zip(a,b))
    assert any(c[256:]!=d[256:] for c,d in zip(a[1:],b[1:]))


@pytest.mark.parametrize('events',[[(0,6001)],[(0,float('nan'))],[(0,2000),(0,3000)]])
def test_invalid_switch_controls_rejected(events):
    with pytest.raises(ValueError):m.switching_reference([0.]*128,48000,events)

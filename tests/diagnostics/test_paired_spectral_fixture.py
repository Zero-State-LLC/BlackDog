"""Contract guards and the constant-folding regression in offline specialization."""
import importlib.util
from pathlib import Path
import struct
import sys
import pytest

path = Path(__file__).resolve().parents[2] / 'scripts/diagnostics/paired_spectral_fixture.py'
spec = importlib.util.spec_from_file_location('paired_spectral_fixture', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


@pytest.mark.parametrize('kwargs', [
    {'sample_rate': True}, {'sample_rate': 0}, {'sample_rate': 48000.0},
    {'top_hz': 24000}, {'top_hz': float('nan')}, {'bands': 1},
    {'bands': 9}, {'bands_per_octave': 0}, {'tau': 0},
    {'offset_db': float('inf')}, {'top_hz': .5},
])
def test_rejects_unsupported_parameters(kwargs):
    values = dict(sample_rate=48000, top_hz=4000)
    values.update(kwargs)
    with pytest.raises(ValueError):
        module.Config(**values).validate()


def test_rate_mismatch_is_rejected():
    fixture = {'required_sample_rate': 44100}
    module.require_runtime_rate(fixture, 44100)
    with pytest.raises(ValueError):
        module.require_runtime_rate(fixture, 48000)


def test_coefficient_split_preserves_float32_rounding():
    # Exact constant-folding would return hi as the high split and zero as low.
    hi, lo, split_hi, split_lo = module.coefficient_parts(1.234567890123)
    assert split_lo != 0
    assert split_hi + split_lo == hi
    assert abs((hi + lo) - 1.234567890123) < 2e-15
    for x in (hi, lo, split_hi, split_lo):
        assert struct.unpack('<f', struct.pack('<f', x))[0] == x


def test_nyquist_guard_and_lowest_band_guard():
    module.Config(48000, 23900, 8, 3).validate()
    with pytest.raises(ValueError):
        module.Config(48000, 24000, 8, 3).validate()
    with pytest.raises(ValueError):
        module.Config(48000, 100, 8, .1).validate()

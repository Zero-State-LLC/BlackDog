import pytest
from faustcoder.signal import SignalProfile, SignalReference, SAMPLE_RATES, SUPPORTED_SAMPLE_RATES

@pytest.mark.parametrize('rate', SUPPORTED_SAMPLE_RATES)
def test_explicit_rate_has_matching_reference_identity(rate):
    profile = SignalProfile(rate, frames=64, max_frames=64, stimuli=('impulse',))
    reference = SignalReference(rate,64,64,profile.seed,('impulse',),1,{'impulse':[[0.0]*64]})
    assert reference.sample_rate == profile.sample_rate

@pytest.mark.parametrize('rate', [True,48000.0,22050,0,192001])
def test_invalid_rate_refused_in_both_boundaries(rate):
    with pytest.raises(ValueError, match='SUPPORTED_SAMPLE_RATES'):
        SignalProfile(rate)
    with pytest.raises(ValueError, match='SUPPORTED_SAMPLE_RATES'):
        SignalReference(rate,64,64,1,('impulse',),1,{'impulse':[[0.0]*64]})

def test_default_rates_remain_frozen():
    assert SAMPLE_RATES == (44100,48000)

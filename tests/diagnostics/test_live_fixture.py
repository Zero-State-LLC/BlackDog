import sys
from pathlib import Path
from dataclasses import asdict
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/diagnostics'))
from paired_spectral_fixture import Config
from paired_live_fixture import build_live
from live_spectral_reference import live_reference
from dynamic_spectral_reference import reference

@pytest.mark.parametrize('events',[[(0,1999)],[(0,6001)],[(0,float('nan'))],[(2,3000)],[(0,3000),(0,4000)],[(1,3000),(0,4000)]])
def test_invalid_live_controls_rejected(events):
    with pytest.raises(ValueError):live_reference([.1]*128,asdict(Config(48000,4000)),events,64)

def test_no_control_change_matches_static_reference():
    config=asdict(Config(48000,4000));samples=[.125]*128
    assert live_reference(samples,config,[],64)==reference(samples,[config],[],64)

@pytest.mark.parametrize('config',[Config(8000,3000),Config(48000,3000),Config(48000,4000,bands=4)])
def test_live_generator_refuses_changed_domain(config):
    with pytest.raises(ValueError):build_live('',config,'')

import sys
from pathlib import Path
from dataclasses import asdict
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/diagnostics'))
from paired_spectral_fixture import Config
from paired_cutoff_fixture import build_cutoff
from dynamic_spectral_reference import reference

@pytest.mark.parametrize('period,depth',[(0,.1),(True,.1),(129,.1),(64,0),(64,float('nan')),(64,.6)])
def test_invalid_trajectory_rejected(period,depth):
    with pytest.raises(ValueError):build_cutoff('',Config(48000,4000),'',period,depth)

def test_constant_sample_schedule_matches_static_reference():
    bank=[asdict(Config(48000,4000))];x=[.125]*128
    assert reference(x,bank,[],64,sample_bank_indices=[0]*128)==reference(x,bank,[],64)

@pytest.mark.parametrize('indices',[[0]*127,[1]*128,[True]*128])
def test_sample_schedule_refuses_bad_dimensions_or_indices(indices):
    with pytest.raises(ValueError):reference([.1]*128,[asdict(Config(48000,4000))],[],64,sample_bank_indices=indices)

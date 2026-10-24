import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/diagnostics'))
from paired_continuous_fixture import reference_offset, build_continuous_offset
from paired_spectral_fixture import Config

def test_reference_uses_end_of_block_phase_and_preserves_audio():
    channels=[[.25]*8,[0.0]*8]
    result=reference_offset(channels,0,8,2,2)
    assert result[0]==channels[0]
    assert result[1]==pytest.approx([-.005,-.005,.005,.005,.005,.005,-.005,-.005])

@pytest.mark.parametrize('period',[0,3,65538,True])
def test_invalid_period_rejected(period):
    with pytest.raises(ValueError):
        build_continuous_offset('',Config(48000,4000),'',period)

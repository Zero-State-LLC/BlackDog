import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/diagnostics'))
from paired_spectral_fixture import Config
from paired_dynamic_fixture import build_dynamic
from dynamic_spectral_reference import reference
from dataclasses import asdict


@pytest.mark.parametrize('bank', [
    [Config(44100,4000)],
    [Config(44100,4000),Config(48000,4000)],
    [Config(44100,4000),Config(44100,4000,bands=4)],
])
def test_bank_rejects_topology_and_rate_changes_before_generation(bank):
    with pytest.raises(ValueError):
        build_dynamic('',bank,'')


@pytest.mark.parametrize('events', [[(0,0),(0,0)],[(2,0),(1,0)],[(8,0)],[(-1,0)],[(1,1)],[(1,True)]])
def test_reference_rejects_invalid_events(events):
    with pytest.raises(ValueError):
        reference([.125]*512,[asdict(Config(44100,4000))],events,64)


def test_noop_event_does_not_reset_state():
    bank=[asdict(Config(44100,4000))]
    x=[.125]*512
    baseline=reference(x,bank,[],64)
    assert reference(x,bank,[(2,0)],64)==baseline
    assert reference(x,bank,[(2,0)],64,reset_on_change=True)!=baseline


def test_experimental_worker_refuses_unknown_or_repeated_patches():
    from experimental_rate_worker import prepare_renderer, PRODUCTION_GUARD
    prepared = prepare_renderer(PRODUCTION_GUARD)
    for source in ('', prepared, PRODUCTION_GUARD + PRODUCTION_GUARD):
        with pytest.raises(ValueError):
            prepare_renderer(source)

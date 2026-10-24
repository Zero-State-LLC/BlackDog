from pathlib import Path
import pytest

from bounded_pluck_host_contract import create_pluck_graph, validate_notes

SOURCE = (Path(__file__).resolve().parent / "pluck-bounded-epoch.dsp").read_text()


@pytest.mark.parametrize("note", [
    (0, 1, 69.5, 100), (0, 1, 15, 100), (0, 1, 120, 100),
    (0, 1, 69, 0), (0, 1, 69, 128), (0, 1, 69, 90.5),
    (-1, 1, 69, 100), (0, 0, 69, 100), (0, -1, 69, 100),
    (0, float("nan"), 69, 100), (0, 1, float("inf"), 100),
    (1e308, 1e308, 69, 100), (False, 1, 69, 100), (0, 1, "69", 100),
    (0, 1, 69),
])
def test_bad_late_note_cannot_partially_mutate_host(note):
    calls = []
    with pytest.raises(ValueError):
        create_pluck_graph(lambda *args: calls.append(args), SOURCE,
                          [(0, 1, 69, 100), note], 48000)
    assert calls == []


@pytest.mark.parametrize("rate,source", [(48000.0, SOURCE), (32000, SOURCE), (48000, SOURCE + "\n")])
def test_unqualified_rate_or_source_cannot_create_host(rate, source):
    calls = []
    with pytest.raises(ValueError):
        create_pluck_graph(lambda *args: calls.append(args), source, [], rate)
    assert not calls


def test_all_supported_integer_pitches_and_velocity_endpoints_are_preserved():
    notes = [(0, 1, pitch, velocity) for pitch in range(16, 120) for velocity in (1, 127)]
    assert validate_notes(notes) == tuple(notes)


def test_adapter_installs_natural_release_policy_and_exact_note_order():
    class Processor:
        def set_dsp_string(self, source): self.source = source
        def add_midi_note(self, *args): events.append(args)
    class Engine:
        def make_faust_processor(self, name):
            assert name == "pluck"
            return processor
        def load_graph(self, graph): self.graph = graph
    events = []
    processor, engine = Processor(), Engine()
    def factory(rate, block):
        assert (rate, block) == (48000, 64)
        return engine
    actual = create_pluck_graph(factory, SOURCE, [(0.25, 0.5, 69, 100)], 48000)
    assert actual == (engine, processor)
    assert events == [(69, 100, 0.25, 0.5)]
    assert processor.num_voices == 8 and processor.dynamic_voices is False
    assert processor.source == SOURCE
    assert engine.graph == [(processor, [])]


@pytest.mark.parametrize("rate", [44100, 48000, 96000, 192000])
@pytest.mark.parametrize("kind", ["overflow", "huge", "subsample", "rounding"])
def test_host_sample_offsets_rejected_before_allocation(rate, kind):
    cases = {
        "overflow": (0, 2**31 / rate, 69, 100),
        "huge": (1e308, 1, 69, 100),
        "subsample": (0, 0.25 / rate, 69, 100),
        "rounding": (100, 1e-20, 69, 100),
    }
    calls = []
    with pytest.raises(ValueError):
        create_pluck_graph(lambda *args: calls.append(args), SOURCE,
                          [(0, 1, 69, 100), cases[kind]], rate)
    assert calls == []


@pytest.mark.parametrize("rate", [44100, 48000, 96000, 192000])
def test_representable_sample_boundary_reaches_host_factory(rate):
    class ReachedFactory(Exception):
        pass
    def factory(*args):
        raise ReachedFactory
    # A one-sample event and an end near the largest signed sample offset
    # must remain valid. No giant audio allocation is needed for this check.
    with pytest.raises(ReachedFactory):
        create_pluck_graph(factory, SOURCE,
                          [(0, 1 / rate, 69, 100),
                           (0, (2**31 - 1) / rate, 69, 100)], rate)

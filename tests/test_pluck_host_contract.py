from pathlib import Path
import pytest

from diagnostics.pluck_host_contract import create_pluck_graph, validate_notes

SOURCE = (Path(__file__).resolve().parents[1] / "scripts/diagnostics/pluck-reset-loop.dsp").read_text()


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

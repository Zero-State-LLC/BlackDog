"""Proposed reset-pluck host adapter; diagnostic only, never admission."""
from __future__ import annotations

import hashlib
import math
from numbers import Real

SOURCE_SHA256 = "74f7aef25b5c12a0e077bb407ddf491ea920fa015e3a20eef2884aacdf2a56fe"
SAMPLE_RATES = (44100, 48000, 96000, 192000)


def validate_notes(notes):
    """Validate seconds-based (start, duration, MIDI pitch, velocity) tuples.

    Reject fractional pitches rather than reproducing Shipwright's silent
    truncation. MIDI 16..119 is the integer subset of the DSP's 20..8000 Hz
    range. Velocity zero is a note-off event, not a Note in this contract.
    """
    result = []
    for index, note in enumerate(notes):
        if not isinstance(note, (tuple, list)) or len(note) != 4:
            raise ValueError(f"note {index}: expected four fields")
        if any(isinstance(v, bool) or not isinstance(v, Real) for v in note):
            raise ValueError(f"note {index}: fields must be real numbers")
        try:
            start, duration, pitch, velocity = map(float, note)
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"note {index}: invalid number") from exc
        if not all(math.isfinite(v) for v in (start, duration, pitch, velocity, start + duration)):
            raise ValueError(f"note {index}: nonfinite time or control")
        if start < 0 or duration <= 0:
            raise ValueError(f"note {index}: invalid start or duration")
        if not pitch.is_integer() or not 16 <= pitch <= 119:
            raise ValueError(f"note {index}: pitch must be integer MIDI 16..119")
        if not velocity.is_integer() or not 1 <= velocity <= 127:
            raise ValueError(f"note {index}: velocity must be integer 1..127")
        result.append((start, duration, int(pitch), int(velocity)))
    return tuple(result)


def create_pluck_graph(engine_factory, source: str, notes, sample_rate: int):
    """Validate the whole request before allocating or mutating host objects."""
    if type(sample_rate) is not int or sample_rate not in SAMPLE_RATES:
        raise ValueError("sample rate is outside the qualified diagnostic set")
    if hashlib.sha256(source.encode()).hexdigest() != SOURCE_SHA256:
        raise ValueError("source does not match the reset-pluck contract")
    checked = validate_notes(notes)
    # DawDreamer 0.9.0 addMidiNote computes these doubles separately, then
    # casts each timestamp to a signed 32-bit sample offset. Match that order.
    for index, (start, duration, _, _) in enumerate(checked):
        on = start * sample_rate
        off = on + duration * sample_rate
        if not math.isfinite(off) or off >= 2**31:
            raise ValueError(f"note {index}: time exceeds host sample-offset range")
        if int(off) <= int(on):
            raise ValueError(f"note {index}: duration collapses at host sample resolution")
    engine = engine_factory(sample_rate, 64)
    processor = engine.make_faust_processor("pluck")
    processor.set_dsp_string(source)
    processor.num_voices = 8
    processor.dynamic_voices = False
    for start, duration, pitch, velocity in checked:
        processor.add_midi_note(pitch, velocity, start, duration)
    engine.load_graph([(processor, [])])
    return engine, processor

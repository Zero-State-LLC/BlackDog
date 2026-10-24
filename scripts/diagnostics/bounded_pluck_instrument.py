"""Exact bounded-pluck binding for the proposed local Shipwright API.

Diagnostic qualification only; does not confer rights or admission.
"""
import hashlib
import math
from numbers import Real
from bounded_pluck_host_contract import SOURCE_SHA256, SAMPLE_RATES, validate_notes
from shipwright import config, engine
from shipwright.registry import Instrument


def preflight(spec, track, sample_rate):
    inst = track.instrument
    if (inst.kind != 'faust' or type(inst.num_voices) is not int or
            inst.num_voices != 8 or inst.dynamic_voices is not False):
        raise ValueError('bounded pluck requires Faust, eight voices and natural release')
    if not isinstance(inst.dsp, str) or hashlib.sha256(inst.dsp.encode()).hexdigest() != SOURCE_SHA256:
        raise ValueError('bounded pluck source changed')
    if type(sample_rate) is not int or sample_rate not in SAMPLE_RATES:
        raise ValueError('unqualified sample rate')
    if type(config.BLOCK) is not int or config.BLOCK != 64:
        raise ValueError('unqualified block size')
    if spec.duration is not None:
        duration = spec.duration
        if isinstance(duration, bool) or not isinstance(duration, Real):
            raise ValueError('render duration must be finite positive seconds')
        try:
            duration = float(duration)
        except (OverflowError, ValueError) as exc:
            raise ValueError('invalid render duration') from exc
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError('render duration must be finite positive seconds')
    raw = validate_notes([(n.start, n.dur, n.pitch, n.vel) for n in track.notes])
    if spec.time_unit == 'seconds':
        notes = raw
    elif spec.time_unit == 'beats':
        tempo = spec.tempo
        if isinstance(tempo, bool) or not isinstance(tempo, Real):
            raise ValueError('tempo must be a finite positive number')
        try:
            tempo = float(tempo)
        except (OverflowError, ValueError) as exc:
            raise ValueError('invalid tempo') from exc
        if not math.isfinite(tempo) or tempo <= 0:
            raise ValueError('tempo must be a finite positive number')
        # Match the engine's conversion before add_midi_note casts to float.
        notes = validate_notes(engine._notes_seconds(spec, track))
    else:
        raise ValueError('unsupported time unit')
    for index, (start, duration, _, _) in enumerate(notes):
        on = start * sample_rate
        off = on + duration * sample_rate
        if not math.isfinite(off) or off >= 2**31:
            raise ValueError(f'note {index}: time exceeds host sample-offset range')
        if int(off) <= int(on):
            raise ValueError(f'note {index}: duration collapses at host sample resolution')


def bounded_pluck(source):
    if not isinstance(source, str) or hashlib.sha256(source.encode()).hexdigest() != SOURCE_SHA256:
        raise ValueError('bounded pluck source changed')
    return Instrument.faust('bounded-pluck', source, 8,
                            dynamic_voices=False, preflight=preflight)

"""Prepare an isolated experimental renderer; never change admission profiles."""
EXPERIMENTAL_RATES = (8000, 32000, 44100, 48000, 88200, 96000, 192000)
PRODUCTION_GUARD = 'if (sampleRate !== 44100 && sampleRate !== 48000) failClosed("sample_rate is not 44100 or 48000");'


def prepare_renderer(source):
    """Replace exactly the known rate guard in a staged diagnostic worker copy."""
    if source.count(PRODUCTION_GUARD) != 1:
        raise ValueError('expected one unmodified production rate guard')
    rates = ','.join(map(str, EXPERIMENTAL_RATES))
    guard = f'if (![{rates}].includes(sampleRate)) failClosed("unsupported experimental diagnostic rate");'
    return source.replace(PRODUCTION_GUARD, guard)

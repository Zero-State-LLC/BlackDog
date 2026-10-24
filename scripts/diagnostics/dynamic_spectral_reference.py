"""Double direct-form reference for time-varying cascades; no paired arithmetic."""
import math
import struct


def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


def coefficients(rate, fc, high):
    prototype = ((.000099999997055, 0, .000433227200555, .782413046821645, .245291508706160),
                 (1, 0, 7.621731298870603, .512478641889141, .689621364484675),
                 (1, 0, 53.536152954556727, .168404871113589, 1.069358407707312))
    values = []
    for b2,b1,b0,a1,a0 in prototype:
        if high:
            b2,b1,b0,a1,a0 = b0/a0,b1/a0,b2/a0,a1/a0,1/a0
        c = 1/math.tan(math.pi*fc/rate)
        d = a0+a1*c+c*c
        values.append(((b0+b1*c+b2*c*c)/d, 2*(b0-b2*c*c)/d,
                       (b0-b1*c+b2*c*c)/d, 2*(a0-c*c)/d,
                       (a0-a1*c+c*c)/d))
    return values


def reference(samples, bank, events, block_size, *, reset_on_change=False):
    if type(block_size) is not int or block_size < 1 or not samples or len(samples) % block_size:
        raise ValueError('samples must contain whole positive blocks')
    if not bank or any(not math.isfinite(x) for x in samples):
        raise ValueError('finite input and nonempty bank required')
    if any((c['sample_rate'], c['bands']) != (bank[0]['sample_rate'], bank[0]['bands']) for c in bank):
        raise ValueError('reference bank must preserve rate and topology')
    previous = -1
    for block, index in events:
        if type(block) is not int or not previous < block < len(samples)//block_size:
            raise ValueError('events must have unique increasing in-range blocks')
        if type(index) is not int or not 0 <= index < len(bank):
            raise ValueError('bank index out of range')
        previous = block
    bands = bank[0]['bands']
    rate = bank[0]['sample_rate']
    tables = []
    for config in bank:
        cutoffs = [config['top_hz']*2**(-i/config['bands_per_octave']) for i in range(bands-1)]
        tables.append([[coefficients(rate,fc,high) for high in (False,True)] for fc in cutoffs])
    state = {}
    meter = [0.0]*bands
    channels = [list(samples)] + [[] for _ in range(bands)]
    changes = dict(events)
    active = 0

    def filt(x, crossover, high):
        for section, (b0,b1,b2,a1,a2) in enumerate(tables[active][crossover][int(high)]):
            key = (crossover,high,section)
            x1,x2,y1,y2 = state.get(key,(0,0,0,0))
            y = b0*x+b1*x1+b2*x2-a1*y1-a2*y2
            state[key] = (x,x1,y,y1)
            x = y
        return x

    for n,x in enumerate(samples):
        block = n//block_size
        if n % block_size == 0 and block in changes:
            active = changes[block]
            if reset_on_change:
                state.clear()
                meter = [0.0]*bands
        config = bank[active]
        pole = math.exp(-1/(config['tau']*rate))
        values = []
        for i in range(bands-1):
            values.append(filt(x,i,True))
            x = filt(x,i,False)
        values.append(x)
        for i,v in enumerate(reversed(values)):
            meter[i] = (1-pole)*abs(v)+pole*meter[i]
        if (n+1) % block_size == 0:
            for i,v in enumerate(meter):
                level = f32((20*math.log10(max(2**-23,v))+config['offset_db'])/200)
                channels[i+1].extend([level]*block_size)
    return [[f32(v) for v in c] for c in channels]

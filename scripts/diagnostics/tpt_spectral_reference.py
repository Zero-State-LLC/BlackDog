"""Independent double TPT recurrence with an explicitly float32 control path.

Fixed three-band, M=3 elliptic analyzer. Meter outputs are held at block end.
The coefficient constants are the original captured sixth-order prototype.
"""
import math
import struct

PROTOTYPE = (
    (.000099999997055, .000433227200555, .782413046821645, .245291508706160),
    (1., 7.621731298870603, .512478641889141, .689621364484675),
    (1., 53.536152954556727, .168404871113589, 1.069358407707312),
)


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def tpt_reference(samples, rate, events, block_size=64, *, frozen=False):
    if type(rate) is not int or rate not in (44100,48000,96000,192000):
        raise ValueError('unsupported reference rate')
    if type(block_size) is not int or block_size <= 0 or len(samples) % block_size:
        raise ValueError('whole positive-size blocks required')
    changes = {}
    previous = -1
    for block,value in events:
        if type(block) is not int or block <= previous or not 0 <= block < len(samples)//block_size:
            raise ValueError('ordered unique in-range control blocks required')
        if not math.isfinite(value) or not 2000 <= value <= 6000:
            raise ValueError('cutoff outside reference domain')
        changes[block] = f32(value)
        previous = block
    if not all(math.isfinite(x) for x in samples):
        raise ValueError('finite input required')
    states = [[[0.,0.] for _ in PROTOTYPE] for _ in range(4)]
    levels = [0.,0.,0.]
    result = [list(samples),[],[],[]]
    pole = math.exp(-100./rate)
    target = f32(4000)
    smooth = f32(0)

    def cascade(value, cutoff, high, state):
        tangent = math.tan(max(0., min(math.pi*cutoff/rate, .499*math.pi)))
        for (b2,b0,a1,a0),memory in zip(PROTOTYPE,state):
            if high:
                b2,b0,a1,a0 = b0/a0,b2/a0,a1/a0,1./a0
            w = max(abs(a1),math.sqrt(abs(a0)))
            w2 = w*w
            g = w*tangent
            s1,s0 = memory
            u = (value-a1/w*s1-a0/w2*(g*s1+s0))/(1.+g*(a1/w+g*a0/w2))
            v1 = g*u+s1
            v0 = g*v1+s0
            memory[:] = [2*v1-s1,2*v0-s0]
            value = b2*u+b0/w2*v0
        return value

    for frame,value in enumerate(samples):
        block = frame//block_size
        if frame % block_size == 0 and block in changes and not frozen:
            target = changes[block]
        smooth = f32(f32(f32(.99)*smooth)+f32(f32(.01)*f32(target-4000.)))
        cutoff = min(6000.,max(2000.,f32(4000.+smooth)))
        high = cascade(value,cutoff,True,states[0])
        base = cascade(value,cutoff,False,states[1])
        lower = cutoff*2**(-1./3.)
        middle = cascade(base,lower,True,states[2])
        low = cascade(base,lower,False,states[3])
        for i,band in enumerate((low,middle,high)):
            levels[i] = (1.-pole)*abs(band)+pole*levels[i]
        if (frame+1) % block_size == 0:
            for i,level in enumerate(levels):
                result[i+1].extend([f32(20.*math.log10(max(2**-23,level))/200.)]*block_size)
    return result

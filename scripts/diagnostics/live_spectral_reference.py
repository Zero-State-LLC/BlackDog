"""Double direct-form recurrence with independent live coefficient interpolation."""
import math
from dynamic_spectral_reference import coefficients, reference, f32


def live_reference(samples, config, events, block_size, *, frozen=False):
    if type(block_size) is not int or block_size < 1 or not samples or len(samples)%block_size:
        raise ValueError('whole positive blocks required')
    if config['bands'] != 3 or config['bands_per_octave'] != 3 or config['top_hz'] != 4000:
        raise ValueError('live reference requires the fixed three-band topology')
    previous=-1
    for block,value in events:
        if type(block) is not int or not previous < block < len(samples)//block_size:
            raise ValueError('control blocks must be unique, ordered and in range')
        if not math.isfinite(value) or not 2000 <= value <= 6000:
            raise ValueError('cutoff must be in [2000,6000]')
        previous=block
    rate=config['sample_rate'];states=[];target=4000.;smooth=0.;changes=dict(events)
    tables=[[[coefficients(rate,(2000+k*62.5)*2**(-i/3),high)
              for high in (False,True)] for i in range(2)] for k in range(65)]
    for n in range(len(samples)):
        if n%block_size==0 and n//block_size in changes:target=f32(changes[n//block_size])
        smooth=f32(f32(f32(.99)*smooth)+f32(f32(.01)*f32(target-4000)))
        fc=max(2000,min(6000,f32(4000+smooth)))
        pos=f32(f32(fc-2000)/62.5);j=min(63,max(0,int(pos)));t=f32(pos-j)
        if frozen:j,t=32,0
        states.append((j,t))
    def trajectory(n):
        j,t=states[n]
        return [[ [tuple(a+t*(b-a) for a,b in zip(sa,sb))
                    for sa,sb in zip(ha,hb)] for ha,hb in zip(ca,cb)]
                 for ca,cb in zip(tables[j],tables[j+1])]
    return reference(samples,[config],[],block_size,coefficient_trajectory=trajectory)

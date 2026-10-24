"""Live smoothed cutoff with paired interpolation of offline coefficient knots.

Contract: 2--6 kHz top cutoff, 65 uniform knots, fixed rate and topology.
Interpolation defines a new direct-form target; TPT equivalence is not assumed.
"""
import hashlib
import re
from paired_spectral_fixture import build, filter_code


def build_live(closure, config, arithmetic):
    config.validate()
    if config.top_hz != 4000 or config.bands != 3 or config.bands_per_octave != 3:
        raise ValueError('live fixture requires top=4000, bands=3, M=3')
    if 6000 >= .499*config.sample_rate:
        raise ValueError('live range exceeds Nyquist domain')
    fixture=build(closure,config,arithmetic)
    source=fixture['source'];start=source.index('ds = environment {');end=source.index('\nan = environment {')
    defs=['ds = environment {',arithmetic,
          'lerp(ah,al,bh,bl,t) = add(bh,bl,-ah,-al) : mul(t,0) : add(ah,al);']
    for i in range(2):
        for high in (False,True):
            name=f'{"hp" if high else "lp"}{i}'
            tables=[re.findall(r'biquad\(([^)]+)\)',filter_code(config.sample_rate,
                    (2000+n*62.5)*2**(-i/3),high)) for n in range(65)]
            sections=[]
            for section in range(3):
                coefs=[]
                for arg in range(5):
                    names=[]
                    for part in range(2):
                        symbol=f'c_{name}_{section}_{arg}_{part}'
                        values=[t[section].split(',')[arg*4+part] for t in tables]
                        defs.append(symbol+'(j) = waveform{'+','.join(values)+'},j : rdtable;');names.append(symbol)
                    coefs.append(f'lerp({names[0]}(cutctl.j),{names[1]}(cutctl.j),{names[0]}(cutctl.j+1),{names[1]}(cutctl.j+1),cutctl.t)')
                sections.append('('+','.join(coefs)+',_,_ : biquad)')
            defs.append(name+' = '+':'.join(sections)+';')
    defs.append('};')
    source=source[:start]+'\n'.join(defs)+source[end:]
    source=source.replace('ds.hp1 : ds.lp0','ds.lp0 : ds.hp1')
    control='''cutctl = environment {
 r(x)=max(-1e30,min(1e30,x));
 target=hslider("cutoff_hz",4000,2000,6000,0.01);
 smooth(x)=loop ~ _ with {loop(fb)=r(r(0.99*fb)+r(0.01*x));};
 fc=max(2000,min(6000,r(4000+(r(target-4000):smooth))));
 pos=r(r(fc-2000)/62.5);
 j=min(63,max(0,int(pos)));
 t=r(pos-j);
};
'''
    source=control+source
    if len(source.encode())>1024*1024:raise ValueError('source exceeds 1 MiB')
    fixture.update(source=source,source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                   closure_sha256=hashlib.sha256(source.rsplit('process =',1)[0].encode()).hexdigest(),
                   live=dict(min_hz=2000,max_hz=6000,knots=65,smoothing=[.99,.01],initial_hz=4000,control_label='cutoff_hz'))
    return fixture

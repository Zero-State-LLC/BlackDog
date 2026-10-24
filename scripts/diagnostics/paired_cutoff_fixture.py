"""Offline periodic, per-sample cutoff trajectory for paired spectral qualification.

A coefficient table is not a general runtime cutoff API. No interpolation,
coefficient-bank crossfade, or independently running filter bank is used.
"""
import hashlib
import math
import re
from paired_spectral_fixture import build, filter_code


def build_cutoff(closure, config, arithmetic, period=64, depth=.1):
    config.validate()
    if type(period) is not int or not 8 <= period <= 128:
        raise ValueError('period must be an integer in [8,128]')
    if not math.isfinite(depth) or not 0 < depth <= .5:
        raise ValueError('depth must be in (0,.5]')
    if config.top_hz*(1+depth) >= .499*config.sample_rate or config.cutoffs[-1]*(1-depth)<1:
        raise ValueError('trajectory leaves validated cutoff domain')
    fixture=build(closure,config,arithmetic)
    source=fixture['source'];definitions=[]
    for i,cutoff in enumerate(config.cutoffs):
        for high in (False,True):
            name=f'{"hp" if high else "lp"}{i}'
            tables=[re.findall(r'biquad\(([^)]+)\)',filter_code(config.sample_rate,
                    cutoff*(1+depth*math.sin(2*math.pi*n/period)),high)) for n in range(period)]
            sections=[]
            for section in range(3):
                args=[];cache={}
                for arg in range(20):
                    values=tuple(t[section].split(',')[arg] for t in tables)
                    if values not in cache:
                        symbol=f'c_{name}_{section}_{arg}'
                        definitions.append(symbol+' = waveform{'+','.join(values)+'},cutctl.phase : rdtable;')
                        cache[values]=symbol
                    args.append(cache[values])
                sections.append('biquad('+','.join(args)+')')
            source,n=re.subn(r'(?m)^'+name+r' = [^\n]+;$',name+' = '+':'.join(sections)+';',source)
            assert n==1
    # Original recursive cascade order matters for time-varying coefficients.
    for i in range(1,config.bands-1):
        source=source.replace(' : '.join([f'ds.hp{i}']+[f'ds.lp{j}' for j in range(i)]),
                              ' : '.join([f'ds.lp{j}' for j in range(i)]+[f'ds.hp{i}']))
    source=source.replace('ds = environment {','ds = environment {\n'+'\n'.join(definitions))
    source=f'cutctl = environment {{ phase = (+(1) ~ %( {period} )) - 1; }};\n'+source
    if len(source.encode()) > 1024*1024:
        raise ValueError('generated source exceeds the 1 MiB qualification limit')
    fixture.update(source=source,source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        closure_sha256=hashlib.sha256(source.rsplit('process =',1)[0].encode()).hexdigest(),
        modulation=dict(parameter='top_hz',period=period,depth=depth,shape='sine',update='every-sample',coefficient_preparation='offline-double',runtime_control='none'))
    return fixture

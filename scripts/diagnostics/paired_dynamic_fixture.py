"""Discrete block-boundary coefficient bank with continuous filter state.

This does not qualify arbitrary continuous controls or topology changes.
"""
from dataclasses import asdict
import hashlib
import re
from paired_spectral_fixture import build


def select_bank(expressions):
    result = expressions[0]
    for i, expression in enumerate(expressions[1:], 1):
        result = f'select2(ctl.mode>={i},{result},{expression})'
    return result


def build_dynamic(closure, configs, arithmetic):
    if not 2 <= len(configs) <= 8:
        raise ValueError('bank must contain two through eight configurations')
    for c in configs:
        c.validate()
        if (c.sample_rate, c.bands) != (configs[0].sample_rate, configs[0].bands):
            raise ValueError('bank must preserve rate and topology')
    variants = [build(closure, c, arithmetic) for c in configs]
    pattern = r'(?m)^(?:lp|hp)\d+ = ([^\n]+);$'
    filters = [list(re.finditer(pattern, v['source'])) for v in variants]
    source = variants[0]['source']
    # Select corresponding coefficient parts, never independently running filter banks.
    for index in reversed(range(len(filters[0]))):
        terms = [re.findall(r'biquad\(([^)]+)\)', fs[index][1]) for fs in filters]
        sections = []
        for section in range(3):
            args = [t[section].split(',') for t in terms]
            sections.append('biquad(' + ','.join(select_bank([a[j] for a in args])
                                                for j in range(20)) + ')')
        match = filters[0][index]
        source = source[:match.start(1)] + ':'.join(sections) + source[match.end(1):]
    # Time-varying cascades do not commute. Preserve original LP-before-HP order.
    for i in range(1, configs[0].bands-1):
        old = ' : '.join([f'ds.hp{i}'] + [f'ds.lp{j}' for j in range(i)])
        new = ' : '.join([f'ds.lp{j}' for j in range(i)] + [f'ds.hp{i}'])
        source = source.replace(old, new)
    source = f'ctl = environment {{ mode=hslider("pair_config",0,0,{len(configs)-1},1); }};\n' + source
    source = source.rsplit('process =', 1)[0]
    c = configs[0]
    source += (f'process = an.mth_octave_spectral_level_default({c.bands_per_octave:.17g},'
               f'{c.top_hz:.17g},{c.bands},'
               f'{select_bank([format(x.tau,".17g") for x in configs])},'
               f'{select_bank([format(x.offset_db,".17g") for x in configs])});\n')
    return dict(source=source,source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                closure_sha256=hashlib.sha256(source.rsplit('process =',1)[0].encode()).hexdigest(),
                required_sample_rate=c.sample_rate,parameters=asdict(c),
                bank=[asdict(x) for x in configs],control_label='pair_config',
                semantics='block-boundary-bank-switch-preserve-states',admission='NOT_GRANTED')

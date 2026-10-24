"""Per-sample triangle modulation of meter offset with fixed filter coefficients.

This explicitly does not qualify continuous cutoff or coefficient modulation.
"""
import hashlib
from paired_spectral_fixture import build


def build_continuous_offset(closure, config, arithmetic, period=1024, depth_db=3):
    if type(period) is not int or period < 4 or period > 65536 or period % 2:
        raise ValueError('period must be an even integer in [4,65536]')
    if type(depth_db) is not int or not 1 <= depth_db <= 12:
        raise ValueError('depth_db must be an integer in [1,12]')
    fixture = build(closure, config, arithmetic)
    source = fixture['source'].rsplit('process =',1)[0]
    # Integer counter is exact in float32 over this bounded period. First phase is 0.
    source += f'phase = ((+(1) ~ _) - 1) % {period};\n'
    source += f'modoffset = {config.offset_db:.17g} + {depth_db}*(1-4*abs(float(phase)/{period}-0.5));\n'
    source += f'process = an.mth_octave_spectral_level_default({config.bands_per_octave:.17g},{config.top_hz:.17g},{config.bands},{config.tau:.17g},modoffset);\n'
    fixture.update(source=source,source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                   closure_sha256=hashlib.sha256(source.rsplit('process =',1)[0].encode()).hexdigest(),
                   modulation=dict(parameter='offset_db',period=period,depth_db=depth_db,
                                   update='every-sample',filter_coefficients='fixed'))
    return fixture


def reference_offset(channels, base_offset, period, depth_db, block_size):
    from dynamic_spectral_reference import f32
    result=[list(channels[0])]
    for channel in channels[1:]:
        out=[]
        for n,x in enumerate(channel):
            sample=(n//block_size+1)*block_size-1
            delta=depth_db*(1-4*abs((sample%period)/period-.5))
            out.append(f32(x+delta/200))
        result.append(out)
    return result

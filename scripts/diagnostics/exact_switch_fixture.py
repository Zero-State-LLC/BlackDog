"""Exact float32 selector boundary diagnostic; smoothing intentionally bypassed."""
import hashlib
import struct
from paired_switching_df_fixture import build_switching_pair


def f32(x):
    return struct.unpack('<f',struct.pack('<f',x))[0]


def neighbor(x, offset):
    bits=struct.unpack('<I',struct.pack('<f',x))[0]
    return struct.unpack('<f',struct.pack('<I',bits+offset))[0]


def boundary_values():
    ratio=f32(2**(-1/3))
    center=f32(2304/ratio)
    candidates=[neighbor(center,i) for i in range(-4,5)]
    equality=[x for x in candidates if f32(x*ratio)==2304]
    if not equality:raise ValueError('lower crossover equality not representable')
    exact=min(equality)
    return dict(ratio=ratio,top=[neighbor(2304.,-1),2304.,neighbor(2304.,1)],
                lower_top=[neighbor(exact,-1),exact,neighbor(max(equality),1)])


def events():
    b=boundary_values();lo,eq,hi=b['top'];ll,le,lh=b['lower_top']
    values=[2000,6000,lo,eq,hi,6000,ll,le,lh,2000,le,eq,lo,eq,ll,le]
    return [(i*8,value) for i,value in enumerate(values)]


def build_exact(closure, arithmetic, *, precise=False):
    if precise:
        from paired_precise_switch_fixture import build_precise_switch
        fixture=build_precise_switch(closure,arithmetic)
    else:
        fixture=build_switching_pair(closure,arithmetic)
    source=fixture['source'].replace('hslider("cutoff_hz",4000,2000,6000,0.01)', 'hslider("cutoff_hz",4000,2000,6000,0)')
    prefix,process=source.rsplit('process =',1)
    process=process.replace('cutctl.fc','cutctl.target')
    source=prefix+'core ='+process+'''process = core : attach(_,((cutctl.target>=2304):vbargraph("vbargraph3",0,1))+((cutctl.target*2^(-1.0/3)>=2304):vbargraph("vbargraph4",0,1)));\n'''
    fixture.update(source=source,source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                   diagnostic_only=True,matched_control=True,smoothing_bypassed=True,boundaries=boundary_values())
    return fixture

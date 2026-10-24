"""Experimental stock selector with paired TPT and paired direct-form-II branches."""
import hashlib
import struct
from paired_tpt_fixture import build_tpt

DF = r'''
 divide(dh,dl,nh,nl)=mul(-q,0,dh,dl):add(nh,nl):correct with {
  q=r(nh/dh); correct(rh,rl)=renorm(q,r(r(rh/dh)+r(rl/dh)));
 };
 dfsection(fc,b2h,b2l,b0h,b0l,a1h,a1l,a0h,a0l,xh,xl)=mul(c,0,c,0):havec2 with {
  c=1/fi._tanhalf(2*ma.PI*fc);
  havec2(c2h,c2l)=mul(a1h,a1l,c,0):add(c2h,c2l):add(a0h,a0l):haved(c2h,c2l);
  haved(c2h,c2l,dh,dl)=(
   (mul(b2h,b2l,c2h,c2l):add(b0h,b0l):divide(dh,dl)),
   (mul(-b2h,-b2l,c2h,c2l):add(b0h,b0l):mul(2,0):divide(dh,dl)),
   (add(a0h,a0l,-c2h,-c2l):mul(2,0):divide(dh,dl)),
   (mul(-a1h,-a1l,c,0):add(c2h,c2l):add(a0h,a0l):divide(dh,dl)),xh,xl):dfbiquad;
 };
 dfbiquad(b0h,b0l,b1h,b1l,a1h,a1l,a2h,a2l,xh,xl)=loop ~ (_,_,_,_) : !,!,!,!,_,_ with {
  loop(v1h,v1l,v2h,v2l)=(mul(-a1h,-a1l,v1h,v1l),mul(-a2h,-a2l,v2h,v2l),xh,xl):(add,_,_):add:finish with {
   finish(vh,vl)=vh,vl,v1h,v1l,((mul(b0h,b0l,vh,vl),mul(b1h,b1l,v1h,v1l),mul(b0h,b0l,v2h,v2l)):(add,_,_):add);
  };
 };
 switch(fc,tpt,df,xh,xl)=(tpt(xh,xl),df(xh,xl)):choose with {
  choose(th,tl,dh,dl)=select2(fc>=2304,th,dh),select2(fc>=2304,tl,dl);
 };
'''


def split(value):
    high = struct.unpack('<f',struct.pack('<f',value))[0]
    low = struct.unpack('<f',struct.pack('<f',value-high))[0]
    return f'{high:.17g},{low:.17g}'


def build_switching_pair(closure, arithmetic):
    fixture = build_tpt(closure,arithmetic)
    prototype = (
        (.000099999997055,.000433227200555,.782413046821645,.245291508706160),
        (1.,7.621731298870603,.512478641889141,.689621364484675),
        (1.,53.536152954556727,.168404871113589,1.069358407707312),
    )
    definitions = []
    for high in (False,True):
        terms = []
        for b2,b0,a1,a0 in prototype:
            if high:b2,b0,a1,a0=b0/a0,b2/a0,a1/a0,1/a0
            terms.append('dfsection(fc,'+','.join(split(v) for v in (b2,b0,a1,a0))+')')
        definitions.append(('dfhp' if high else 'dflp')+'(fc)='+':'.join(terms)+';')
    source=fixture['source']
    source=source.replace('hp(fc)=fi._highpass6e(tpt,fc);','hp(fc)=switch(fc,fi._highpass6e(tpt,fc),dfhp(max(fc,2304)));')
    source=source.replace('lp(fc)=fi._lowpass6e(tpt,fc);','lp(fc)=switch(fc,fi._lowpass6e(tpt,fc),dflp(max(fc,2304)));'+DF+'\n'.join(definitions))
    if len(source.encode())>1024*1024:raise ValueError('source exceeds 1 MiB')
    fixture.update(source=source,source_sha256=hashlib.sha256(source.encode()).hexdigest(),semantics='stock-2304-selector-paired-tpt-and-direct-form-II',diagnostic_only=True)
    return fixture

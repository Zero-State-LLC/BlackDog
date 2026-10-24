"""Experimental paired trigonometric coefficients for the stock switching target.

The polynomial domain is pi*fc/SR <= pi*6000/44100 < 0.428 radians.
No claim is made for cutoffs/rates outside the diagnostic contract.
"""
import hashlib
import math
from paired_switching_df_fixture import build_switching_pair, split


def build_precise_switch(closure, arithmetic):
    fixture=build_switching_pair(closure,arithmetic)
    polynomials=[]
    for name,shift in [('cosine',0),('sine_ratio',1)]:
        terms=[split((-1.)**i/math.factorial(2*i+shift)) for i in range(8)]
        expression='('+terms[-1]+')'
        for term in reversed(terms[:-1]):expression+=':mul(zh,zl):add('+term+')'
        polynomials.append(name+'(zh,zl)='+expression+';')
    trig='''
 cot(fc)=divide(ma.SR,0,PI_PAIR):mul(fc,0):angle with {
  angle(xh,xl)=mul(xh,xl,xh,xl):square(xh,xl);
  square(xh,xl,zh,zl)=(cosine(zh,zl),(sine_ratio(zh,zl):mul(xh,xl))):ratio;
  ratio(ch,cl,sh,sl)=divide(sh,sl,ch,cl);
 };
'''.replace('PI_PAIR',split(math.pi))+'\n'.join(polynomials)
    source=fixture['source']
    old='''dfsection(fc,b2h,b2l,b0h,b0l,a1h,a1l,a0h,a0l,xh,xl)=mul(c,0,c,0):havec2 with {
  c=1/fi._tanhalf(2*ma.PI*fc);
  havec2(c2h,c2l)=mul(a1h,a1l,c,0):add(c2h,c2l):add(a0h,a0l):haved(c2h,c2l);
  haved(c2h,c2l,dh,dl)=('''
    new='''dfsection(fc,b2h,b2l,b0h,b0l,a1h,a1l,a0h,a0l,xh,xl)=cot(fc):havec with {
  havec(ch,cl)=mul(ch,cl,ch,cl):havec2(ch,cl);
  havec2(ch,cl,c2h,c2l)=mul(a1h,a1l,ch,cl):add(c2h,c2l):add(a0h,a0l):haved(ch,cl,c2h,c2l);
  haved(ch,cl,c2h,c2l,dh,dl)=('''
    if source.count(old)!=1:raise ValueError('unexpected base fixture')
    source=source.replace(old,new).replace('mul(-a1h,-a1l,c,0)','mul(-a1h,-a1l,ch,cl)')
    source=source.replace(' dfsection(',trig+'\n dfsection(',1)
    if len(source.encode())>1024*1024:raise ValueError('source exceeds cap')
    fixture.update(source=source,source_sha256=hashlib.sha256(source.encode()).hexdigest(),semantics='paired-stock-switching-with-paired-cotangent',diagnostic_only=True)
    return fixture

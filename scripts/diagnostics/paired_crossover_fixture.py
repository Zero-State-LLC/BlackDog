"""Experimental paired lower-crossover control; pinned predecessor is preserved."""
from pathlib import Path
import hashlib,sys
from paired_switching_df_fixture import split
BASE='40a1342836429fb8969b6737abf226a2b5ccfe19556d1882c4ced37421c1c515'
def build(source):
 if hashlib.sha256(source.encode()).hexdigest()!=BASE:raise ValueError('unexpected predecessor')
 s=source.replace('cot(fc)=','cot(fh,fl)=').replace(':mul(fc,0):angle',':mul(fh,fl):angle')
 s=s.replace('dfsection(fc,','dfsection(fh,fl,').replace('=cot(fc):havec','=cot(fh,fl):havec')
 s=s.replace('dflp(fc)=','dflp(fh,fl)=').replace('dfhp(fc)=','dfhp(fh,fl)=')
 for name,kind in [('hp','highpass'),('lp','lowpass')]:
  old=f'{name}(fc)=switch(fc,fi._{kind}6e(tpt,fc),df{name}(max(fc,2304)));'
  new=f'{name}(fh,fl)=switchpair(fh,fl,fi._{kind}6e(tpt,fh+fl),df{name}(select2(above(fh,fl),2304,fh),select2(above(fh,fl),0,fl)));'
  assert s.count(old)==1;s=s.replace(old,new)
 s=s.replace(' switch(fc,tpt,df,xh,xl)=',' above(fh,fl)=(fh>2304)|((fh==2304)&(fl>=0));\n switchpair(fh,fl,tpt,df,xh,xl)=')
 s=s.replace('select2(fc>=2304,','select2(above(fh,fl),')
 s=s.replace('process = _ <: _, ((_,0 <: ds.hp(cutctl.fc), (ds.lp(cutctl.fc) <: ds.hp(cutctl.fc*2^(-1.0/3)),ds.lp(cutctl.fc*2^(-1.0/3))))', 'lower=ds.mul(cutctl.fc,0,'+split(2**(-1/3))+');\nlowerh=lower:_,!; lowerl=lower:!,_;\nprocess = _ <: _, ((_,0 <: ds.hp(cutctl.fc,0), (ds.lp(cutctl.fc,0) <: ds.hp(lowerh,lowerl),ds.lp(lowerh,lowerl)))')
 assert 'ds.hp(lowerh,lowerl)' in s and 'dfsection(fc,' not in s
 return s


def build_full(source):
 """Carry paired coefficients through both continuously advancing branches."""
 import math
 s=build(source)
 tpt=r'''
 tptsection(fh,fl,b2h,b2l,b0h,b0l,a1h,a1l,a0h,a0l,wh,wl,xh,xl)=tangent(fh,fl):haveg with {
  haveg(gh,gl)=(mul(gh,gl,a0h,a0l):add(a1h,a1l):mul(gh,gl):add(1,0)):reciprocal:haved(gh,gl);
  reciprocal(h,l)=divide(h,l,1,0);
  haved(gh,gl,dh,dl)=(gh,gl,dh,dl,xh,xl):(tick ~ (_,_,_,_) : !,!,!,!,_,_) with {
   tick(s1h,s1l,s0h,s0l,gh,gl,dh,dl,xh,xl)=
    ((mul(gh,gl,s1h,s1l):add(s0h,s0l):mul(-a0h,-a0l)),mul(-a1h,-a1l,s1h,s1l),xh,xl)
    :(add,_,_):add:mul(dh,dl):haveu
   with {
    haveu(uh,ul)=mul(gh,gl,uh,ul):add(s1h,s1l):havev1(uh,ul);
    havev1(uh,ul,v1h,v1l)=mul(gh,gl,v1h,v1l):add(s0h,s0l):havev0(uh,ul,v1h,v1l);
    havev0(uh,ul,v1h,v1l,v0h,v0l)=
     (mul(2,0,v1h,v1l):add(-s1h,-s1l)),
     (mul(2,0,v0h,v0l):add(-s0h,-s0l)),
     ((mul(b2h,b2l,uh,ul),mul(b0h,b0l,v0h,v0l)):add);
   };
  };
 };
'''
 prototype=((.000099999997055,.000433227200555,.782413046821645,.245291508706160),(1.,7.621731298870603,.512478641889141,.689621364484675),(1.,53.536152954556727,.168404871113589,1.069358407707312))
 for high in (False,True):
  terms=[]
  for b2,b0,a1,a0 in prototype:
   if high:b2,b0,a1,a0=b0/a0,b2/a0,a1/a0,1/a0
   w=1.;w2=1.
   terms.append('tptsection(fh,fl,'+','.join(split(v) for v in (b2,b0/w2,a1/w,a0/w2,w))+')')
  tpt+=('tpthp' if high else 'tptlp')+'(fh,fl)='+':'.join(terms)+';\n'
 a=s.index(' tpt(');b=s.index(' hp(',a);s=s[:a]+tpt+s[b:]
 a=s.index(' cot(fh,fl)=');b=s.index('cosine(zh,zl)=',a)
 tangent=s[a:b].replace('cot(fh,fl)=','tangent(fh,fl)=').replace('divide(sh,sl,ch,cl)','divide(ch,cl,sh,sl)')
 tangent=tangent.replace('cosine(zh,zl)','tcos(zh,zl)').replace('sine_ratio(zh,zl)','tsin(zh,zl)')
 for name,shift in [('tcos',0),('tsin',1)]:
  terms=[split((-1.)**i/math.factorial(2*i+shift)) for i in range(6)]
  expression='('+terms[-1]+')'
  for term in reversed(terms[:-1]):expression+=':mul(zh,zl):add('+term+')'
  tangent+=name+'(zh,zl)='+expression+';\n'
 s=s[:a]+tangent+s[a:]
 s=s.replace('fi._highpass6e(tpt,fh+fl)','tpthp(fh,fl)').replace('fi._lowpass6e(tpt,fh+fl)','tptlp(fh,fl)')
 return s

def build_rational(source):
 """Use a [7/6] Padé tangent on the fixed angle domain below .428 radians."""
 s=build_full(source)
 a=s.index(' tangent(fh,fl)=');b=s.index(' dfsection(',a)
 rational='''
 angle(fh,fl)=divide(ma.SR,0,3.1415927410125732,-8.7422776573475858e-08):mul(fh,fl);
 numerator(zh,zl)=(-1,0):mul(zh,zl):add(378,0):mul(zh,zl):add(-17325,0):mul(zh,zl):add(135135,0);
 denominator(zh,zl)=(-28,0):mul(zh,zl):add(3150,0):mul(zh,zl):add(-62370,0):mul(zh,zl):add(135135,0);
 tangent(fh,fl)=angle(fh,fl):square with {
  square(xh,xl)=mul(xh,xl,xh,xl):polys(xh,xl);
  polys(xh,xl,zh,zl)=((numerator(zh,zl):mul(xh,xl)),denominator(zh,zl)):quotient;
  quotient(nh,nl,dh,dl)=divide(dh,dl,nh,nl);
 };
 cot(fh,fl)=angle(fh,fl):square with {
  square(xh,xl)=mul(xh,xl,xh,xl):polys(xh,xl);
  polys(xh,xl,zh,zl)=((numerator(zh,zl):mul(xh,xl)),denominator(zh,zl)):quotient;
  quotient(nh,nl,dh,dl)=divide(nh,nl,dh,dl);
 };
'''
 return s[:a]+rational+s[b:]

def build_meter(source):
 """Pair the meter pole and envelope state at the four supported diagnostic rates."""
 import math
 s=build(source)
 rates=(44100,48000,96000,192000)
 poles=[split(math.exp(-100./rate)).split(',') for rate in rates]
 complements=[split(1.-math.exp(-100./rate)).split(',') for rate in rates]
 defs=[]
 for name,values,col in [('polehi',poles,0),('polelo',poles,1),('gainhi',complements,0),('gainlo',complements,1)]:
  expression=values[-1][col]
  for rate,valuesrow in reversed(list(zip(rates[:-1],values[:-1]))):expression=f'select2(ma.SR=={rate},{expression},{valuesrow[col]})'
  defs.append(name+'='+expression+';')
 new="""
 abs_pair(a,b)=select2(negative,a,-a),select2(negative,b,-b) with {negative=(a<0)|((a==0)&(b<0));};
 meter_level=tick ~ (_,_) with {
  tick(h,l,xh,xl)=(mul(polehi,polelo,h,l),mul(gainhi,gainlo,xh,xl)):add;
 };
 meter(i)=abs_pair:meter_level:+:max(1.1920928955078125e-7):ba.linear2db:vbargraph("vbargraph%i",-50,10);
"""
 old=' meter(i)=+ : abs : si.smooth(ba.tau2pole(.01)) : max(1.1920928955078125e-7) : ba.linear2db : vbargraph("vbargraph%i",-50,10);'
 assert s.count(old)==1
 return s.replace(old,'\n'.join(defs)+new)

if __name__=='__main__':
 factory=build_meter if '--meter' in sys.argv else build_rational if '--rational' in sys.argv else build_full if '--full' in sys.argv else build
 Path(sys.argv[2]).write_text(factory(Path(sys.argv[1]).read_text()))

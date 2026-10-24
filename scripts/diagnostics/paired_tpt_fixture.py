"""Experimental paired TPT recurrence, preserving the complete captured closure."""
import hashlib

TPT = r'''
ds = environment {
ARITHMETIC
 tpt(b2,b1,b0,a1,a0,w1) = tick ~ (_,_,_,_) : !,!,!,!,_,_ with {
  w=max(abs(a1),sqrt(abs(a0))); w2=w*w;
  g=w*fi._tanhalf(w1);
  d=min(ma.MAX,1/(1+g*(a1/w+g*a0/w2)));
  tick(s1h,s1l,s0h,s0l,xh,xl) =
   ((mul(g,0,s1h,s1l):add(s0h,s0l):mul(-a0/w2,0)),mul(-a1/w,0,s1h,s1l),xh,xl)
   : (add,_,_) : add : mul(d,0) : haveu
  with {
   haveu(uh,ul) = mul(g,0,uh,ul):add(s1h,s1l):havev1(uh,ul);
   havev1(uh,ul,v1h,v1l) = mul(g,0,v1h,v1l):add(s0h,s0l):havev0(uh,ul,v1h,v1l);
   havev0(uh,ul,v1h,v1l,v0h,v0l) =
    (mul(2,0,v1h,v1l):add(-s1h,-s1l)),
    (mul(2,0,v0h,v0l):add(-s0h,-s0l)),
    ((mul(b2,0,uh,ul),mul(b1/w,0,v1h,v1l),mul(b0/w2,0,v0h,v0l)):(add,_,_):add);
  };
 };
 hp(fc)=fi._highpass6e(tpt,fc);
 lp(fc)=fi._lowpass6e(tpt,fc);
 meter(i)=+ : abs : si.smooth(ba.tau2pole(.01)) : max(1.1920928955078125e-7) : ba.linear2db : vbargraph("vbargraph%i",-50,10);
};
'''
CONTROL = '''cutctl = environment {
 r(x)=max(-1e30,min(1e30,x));
 target=hslider("cutoff_hz",4000,2000,6000,0.01);
 smooth(x)=loop ~ _ with {loop(fb)=r(r(0.99*fb)+r(0.01*x));};
 fc=max(2000,min(6000,r(4000+(r(target-4000):smooth))));
};
'''

def build_tpt(closure, arithmetic, *, matched_control=False):
    if closure.count('process =') != 1:
        raise ValueError('expected one complete process declaration')
    original = closure.rsplit('process =', 1)[0]
    arithmetic = arithmetic.split('\nbiquad(', 1)[0]
    cutoff = 'cutctl.target' if matched_control else 'cutctl.fc'
    process = f'''process = _ <: _, ((_,0 <: ds.hp({cutoff}), (ds.lp({cutoff}) <: ds.hp({cutoff}*2^(-1.0/3)),ds.lp({cutoff}*2^(-1.0/3)))) : ds.meter(2),ds.meter(1),ds.meter(0) :> _) : attach;\n'''
    source = CONTROL + TPT.replace('ARITHMETIC',arithmetic) + original + process
    if len(source.encode()) > 1024*1024:
        raise ValueError('source exceeds 1 MiB')
    return dict(source=source,source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                original_closure_sha256=hashlib.sha256(original.encode()).hexdigest(),
                matched_control=matched_control,diagnostic_only=True)

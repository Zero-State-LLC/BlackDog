// Separate proposal: reset note state using integer epoch tags on the delay line.
sr=min(192000.0,max(50.0,fconstant(int fSamplingFreq,<math.h>)));
freq=hslider("freq",440,20,8000,0.01);
gain=hslider("gain",0.5,0,1,0.01);
gate=button("gate");
impulse(x)=max(0,x-x');
tagged(n,epoch,x)=(x@n)*((epoch@n)==epoch);
ap(a,reset,x)=step ~ _ with {step(previous)=a*x+(1-reset)*(x'-a*previous);};
pluck(f,g,exc)=body ~ _
with {
 reset=impulse(g);
 epoch=(+(int(reset)) : &(65535)) ~ _;
 period=sr/f;
 n=max(1,int(floor(period-1.5))-1);
 d=period-1.5-n;
 w=6.283185307179586*f/sr;
 a=sin((1-d)*w/2)/sin((1+d)*w/2);
 body(prev)=(exc+0.499*(1-reset)*(1-reset')*(prev+prev')) : tagged(n,epoch) : ap(a,reset);
};
process=pluck(freq,gate,impulse(gate))*gain <: _,_;
effect=_,_;

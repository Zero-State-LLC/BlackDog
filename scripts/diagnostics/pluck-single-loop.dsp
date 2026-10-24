// Proposed single-loop derivative; original Shipwright source is retained separately.
sr = min(192000.0,max(50.0,fconstant(int fSamplingFreq,<math.h>)));
freq=hslider("freq",440,20,8000,0.01);
gain=hslider("gain",0.5,0,1,0.01);
gate=button("gate");
impulse(x)=max(0,x-x');
ap(a,x)=(a*x+x') : (+ ~ *(-a));
pluck(f)=(+ : @(n) : ap(a)) ~ (mean * 0.998)
with {
    period=sr/f;
    n=max(1,int(floor(period-1.5))-1);
    d=period-1.5-n;
    w=6.283185307179586*f/sr;
    a=sin((1-d)*w/2)/sin((1+d)*w/2);
    mean(x)=(x+x')/2;
};
process=impulse(gate) : pluck(freq) : *(gain) <: _,_;
effect=_,_;

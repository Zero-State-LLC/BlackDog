from pathlib import Path
import numpy as np,cmath,math,json
rows=[]
for sr in (44100,48000,96000,192000):
 for f in (20,50,110,440,1000,4000,8000):
  period=sr/f;n=max(1,math.floor(period-1.5)-1);d=period-1.5-n;w=2*math.pi*f/sr;a=math.sin((1-d)*w/2)/math.sin((1+d)*w/2);z=cmath.exp(complex(math.log(.998*math.cos(w/2))/period,w))
  def fun(z):return .998*.5*(1+1/z)*(a+1/z)/(1+a/z)*z**(-n-1)-1
  for _ in range(40):
   v=fun(z);dz=1e-7;der=(fun(z+dz)-fun(z-dz))/(2*dz);z-=v/der
   if abs(v)<1e-11:break
  measured=cmath.phase(z)*sr/(2*math.pi)
  rows.append(dict(sample_rate=sr,frequency=f,integer_delay=n,fractional_delay=d,allpass_coefficient=a,pole_radius=abs(z),pole_hz=measured,cents_error=1200*math.log2(measured/f),residual=abs(fun(z))))
print('max ideal loop-pole pitch error cents',max(abs(r['cents_error']) for r in rows));print([r for r in rows if r['frequency']==8000])
Path('outputs/blackdog-pluck-single-loop-poles.json').write_text(json.dumps(dict(scope='Double-precision mathematical loop model, not compiled coefficient verification; damped fundamental root near requested frequency',rows=rows),indent=2)+'\n')

from pathlib import Path
import numpy as np,cmath,math,json,struct,hashlib
evidence=Path('work/pluck-coefficients/pluck-coefficient-check');report=json.loads((evidence/'report.json').read_text());assert report['source_sha256']==hashlib.sha256(Path('work/pluck-single-loop.dsp').read_bytes()).hexdigest();coeff={(r['sample_rate'],r['frequency']):r for r in report['rows']};rows=[]
for sr in (44100,48000,96000,192000):
 for f in (20,50,110,440,1000,4000,8000):
  period=sr/f;n=max(1,math.floor(period-1.5)-1);d=period-1.5-n;w=2*math.pi*f/sr;a=math.sin((1-d)*w/2)/math.sin((1+d)*w/2);raw=(evidence/f'{sr}-{f}.bin').read_bytes();assert hashlib.sha256(raw).hexdigest()==coeff[sr,f]['capture_sha256'];cn,ca=struct.unpack('<ff',raw);assert cn==n; a=ca;z=cmath.exp(complex(math.log(.998*math.cos(w/2))/period,w))
  def fun(z):return .998*.5*(1+1/z)*(a+1/z)/(1+a/z)*z**(-n-1)-1
  for _ in range(40):
   v=fun(z);dz=1e-7;der=(fun(z+dz)-fun(z-dz))/(2*dz);z-=v/der
   if abs(v)<1e-11:break
  measured=cmath.phase(z)*sr/(2*math.pi)
  rows.append(dict(sample_rate=sr,frequency=f,integer_delay=n,fractional_delay=d,allpass_coefficient=a,pole_radius=abs(z),pole_hz=measured,cents_error=1200*math.log2(measured/f),residual=abs(fun(z))))
print('max compiled-coefficient loop-pole pitch error cents',max(abs(r['cents_error']) for r in rows));print([r for r in rows if r['frequency']==8000])
Path('outputs/blackdog-pluck-compiled-coefficient-poles.json').write_text(json.dumps(dict(scope='Double-precision pole analysis using independently verified compiled float32 n/a captures; probe output can affect compiler optimization, so not a full audio pitch acceptance proof',rows=rows),indent=2)+'\n')

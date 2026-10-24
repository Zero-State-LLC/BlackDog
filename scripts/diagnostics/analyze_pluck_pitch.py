from pathlib import Path
import numpy as np,json,hashlib,math
root=Path('work/pluck-repair-evidence/pluck-repair-check');rows=[]
for sr in (44100,48000,96000,192000):
 for f in (20,50,110,440,1000,4000,8000):
  p=root/f'{sr}-{f}-0.5-1.bin';raw=p.read_bytes();x=np.frombuffer(raw,dtype='<f4').reshape(-1,2)[:,0].astype(float)[:sr//2]
  # Autocorrelation from zero-padded FFT, search one-cycle neighborhood; diagnostic, not a pitch acceptance gate.
  n=1<<(2*len(x)-1).bit_length();spec=np.fft.rfft(x,n);ac=np.fft.irfft(spec*spec.conj(),n)[:len(x)];lo=max(1,int(sr/f*.6));hi=min(len(ac)-2,int(sr/f*1.5));k=lo+int(np.argmax(ac[lo:hi+1]));den=ac[k-1]-2*ac[k]+ac[k+1];delta=.5*(ac[k-1]-ac[k+1])/den if den else 0.;period=k+delta;measured=sr/period;cents=1200*math.log2(measured/f)
  rows.append(dict(sample_rate=sr,requested_hz=f,period_samples=period,estimated_hz=measured,cents_error=cents,normalized_correlation=float(ac[k]/ac[0]),boundary_peak=k in (lo,hi),capture_sha256=hashlib.sha256(raw).hexdigest()))
r=dict(status='DIAGNOSTIC_NOT_ACCEPTANCE',method='FFT autocorrelation, first 0.5 seconds, 0.6–1.5 nominal-period search and parabolic peak interpolation; not independent fundamental identification',rows=rows)
Path('outputs/blackdog-pluck-pitch-diagnostic.json').write_text(json.dumps(r,indent=2)+'\n')
for r in rows:print(r['sample_rate'],r['requested_hz'],round(r['estimated_hz'],3),round(r['cents_error'],2),round(r['normalized_correlation'],4),r['boundary_peak'])

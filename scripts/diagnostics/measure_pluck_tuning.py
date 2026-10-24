from pathlib import Path
import json,hashlib
import numpy as np
from scipy.fft import rfft,rfftfreq,next_fast_len
root=Path('work/bounded-pluck-dense-evidence');report=json.loads((root/'report.json').read_text());rows=[]
def estimate(x,sr,f):
 n=len(x);nfft=next_fast_len(n*8);w=np.hanning(n);y=np.abs(rfft((x-np.mean(x))*w,nfft));freq=rfftfreq(nfft,1/sr);ids=np.flatnonzero((freq>=f*.85)&(freq<=f*1.15));i=int(ids[np.argmax(y[ids])]);assert 0<i<len(y)-1
 a,b,c=np.log(np.maximum(y[i-1:i+2],1e-300));d=.5*(a-c)/(a-2*b+c);return (i+d)*sr/nfft, bool(i in (ids[0],ids[-1]))
for r in report['rows']:
 if r['velocity']!=127:continue
 raw=(root/r['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==r['capture_sha256'];sr=r['sample_rate'];x=np.frombuffer(raw,dtype='<f4').reshape(-1,2)[:,0];f=440*2**((r['pitch']-69)/12);start=int(.05*sr);end=int(.45*sr);xx=x[start:end].astype(float);measured,boundary=estimate(xx,sr,f);t=np.arange(len(xx))/sr;reference,_=estimate(np.sin(2*np.pi*f*t),sr,f)
 rows.append({'sample_rate':sr,'pitch':r['pitch'],'expected_hz':f,'estimated_hz':measured,'cents_error':1200*np.log2(measured/f),'sine_estimator_cents_error':1200*np.log2(reference/f),'window_cycles':len(xx)*f/sr,'peak_on_search_boundary':boundary,'capture_sha256':r['capture_sha256']})
out=Path('outputs/pluck-tuning-diagnostic.json');out.write_text(json.dumps({'method':'Hann-windowed FFT, 8x zero padding, log-parabolic peak interpolation within 85–115% expected fundamental; window 0.05–0.45 seconds; full-velocity captures','source_sha256':report['source_sha256'],'rows':rows,'scope':'Diagnostic frequency estimate, not an auditory or semantic acceptance decision; short low-note windows and damped/multimode spectra limit accuracy','admission':'NOT_GRANTED'},indent=2)+'\n')
for sr in (44100,48000,96000,192000):
 rr=[x for x in rows if x['sample_rate']==sr];worst=max(rr,key=lambda x:abs(x['cents_error']));print(sr,'worst',worst,'median abs cents',np.median([abs(x['cents_error']) for x in rr]))

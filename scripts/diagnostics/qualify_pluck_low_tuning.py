from pathlib import Path
import json,hashlib,sys
sys.path.insert(0,'work')
from bounded_pluck_host_contract import create_pluck_graph
from pluck_modal_model import fundamental
import dawdreamer as daw
s=Path('work/measure_pluck_tuning.py').read_text();exec(compile(s[:s.index('for r in report')],'estimator','exec'))
out=Path('work/pluck-low-tuning-evidence');out.mkdir(exist_ok=True);source=Path('work/pluck-bounded-epoch.dsp').read_text();rows=[]
for sr in (44100,48000,96000,192000):
 for p in (16,24,36):
  host,_=create_pluck_graph(daw.RenderEngine,source,[(.01,.2,p,127)],sr);host.render(4.0);x=host.get_audio().T;assert x.shape==(4*sr,2) and np.isfinite(x).all() and np.array_equal(x[:,0],x[:,1]);raw=x.astype('<f4').tobytes();name=f'{sr}-{p}.bin';(out/name).write_bytes(raw);f=440*2**((p-69)/12);model=fundamental(sr,f);windows=[]
  for a,b in ((.5,2.),(1.,3.5)):
   y=x[int(a*sr):int(b*sr),0].astype(float);hz,edge=estimate(y,sr,f);t=np.arange(len(y));control=np.exp(model['decay_per_sample']*t)*np.sin(2*np.pi*model['hz']*t/sr);chz,_=estimate(control,sr,f)
   windows.append({'start':a,'end':b,'cycles':len(y)*f/sr,'estimated_hz':float(hz),'error_cents':float(1200*np.log2(hz/f)),'model_error_cents':float(1200*np.log2(hz/model['hz'])),'synthetic_bias_cents':float(1200*np.log2(chz/model['hz'])),'boundary':edge})
  rows.append({'sample_rate':sr,'pitch':p,'file':name,'capture_sha256':hashlib.sha256(raw).hexdigest(),'model':model,'windows':windows})
 print(sr,'three four-second captures pass',flush=True)
(out/'report.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'host':'DawDreamer 0.9.0','rows':rows,'scope':'MIDI16/24/36 at four rates, stationary full-velocity notes, natural release; diagnostic pitch estimation only','admission':'NOT_GRANTED'},indent=2)+'\n')
print('max model difference cents',max(abs(w['model_error_cents']) for r in rows for w in r['windows']))

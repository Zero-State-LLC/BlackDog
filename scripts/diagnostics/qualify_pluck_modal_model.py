from pathlib import Path
import json,hashlib
from pluck_modal_model import fundamental
s=Path('work/measure_pluck_tuning.py').read_text();exec(compile(s[:s.index('for r in report')],'estimator','exec'))
rows=[]
for r in report['rows']:
 if r['velocity']!=127:continue
 sr=r['sample_rate'];p=r['pitch'];f=440*2**((p-69)/12);model=fundamental(sr,f);assert 0<model['pole_radius']<1
 row={'sample_rate':sr,'pitch':p,'expected_hz':f,'model':model,'model_cents':float(1200*np.log2(model['hz']/f))}
 if f>=1000:
  raw=(root/r['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==r['capture_sha256'];x=np.frombuffer(raw,dtype='<f4').reshape(-1,2)[:,0];a=int(.01*sr);b=int(.02*sr);hz,edge=estimate(x[a:b].astype(float),sr,f);t=np.arange(b-a);synthetic=np.exp(model['decay_per_sample']*t)*np.sin(2*np.pi*model['hz']*t/sr);control,_=estimate(synthetic,sr,f)
  row.update(early_estimated_hz=float(hz),early_vs_model_cents=float(1200*np.log2(hz/model['hz'])),synthetic_estimator_cents=float(1200*np.log2(control/model['hz'])),boundary=edge,capture_sha256=r['capture_sha256'])
 rows.append(row)
result={'source_sha256':report['source_sha256'],'method':'Stationary constant-coefficient linear loop root near requested fundamental, float64 arithmetic; actual float32 source untouched','characteristic_equation':'1 = 0.499*z^(-(n+1))*(1+z^-1)*(a+z^-1)/(1+a*z^-1)','rows':rows,'admission':'NOT_GRANTED','limits':'No reset transient model, no exhaustive pole stability proof, no float32 coefficient reconstruction; low-note capture precision and listening acceptance remain pending'}
Path('outputs/pluck-modal-model.json').write_text(json.dumps(result,indent=2)+'\n')
for sr in (44100,48000,96000,192000):
 rr=[r for r in rows if r['sample_rate']==sr];worst=max(rr,key=lambda r:abs(r['model_cents']));measured=[r for r in rr if 'early_vs_model_cents' in r];print(sr,'max model cents',worst['pitch'],worst['model_cents'],'max early/model cents',max(abs(r['early_vs_model_cents']) for r in measured),'max synthetic bias',max(abs(r['synthetic_estimator_cents']) for r in measured))

from pathlib import Path
import json
s=Path('work/measure_pluck_tuning.py').read_text();exec(compile(s[:s.index('for r in report')],'estimator','exec'))
r=json.loads(Path('outputs/pluck-tuning-diagnostic.json').read_text())
for row in r['rows']:
 sr=row['sample_rate'];p=row['pitch'];f=row['expected_hz'];x=np.fromfile(root/f'{sr}-{p}-127.bin',dtype='<f4').reshape(-1,2)[:,0];windows=[]
 for start,end in ((.01,.02),(.01,.05),(.05,.45)):
  if (end-start)*f<10:continue
  y=x[int(start*sr):int(end*sr)].astype(float);hz,boundary=estimate(y,sr,f);t=np.arange(len(y))/sr;control,_=estimate(np.sin(2*np.pi*f*t),sr,f)
  windows.append({'start':start,'end':end,'cycles':len(y)*f/sr,'cents':float(1200*np.log2(hz/f)),'sine_control_cents':float(1200*np.log2(control/f)),'boundary':boundary})
 row['window_checks']=windows
r['scope']='Window sensitivity diagnostic only. Late high-note estimates can follow weak residual spectra rather than the pitched transient. No acceptance threshold or independent listening approval.'
Path('outputs/pluck-tuning-windows.json').write_text(json.dumps(r,indent=2)+'\n')
print('416 capture window checks saved')

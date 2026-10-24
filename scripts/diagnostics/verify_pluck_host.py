from pathlib import Path
import json,hashlib
import numpy as np
sha=lambda b:hashlib.sha256(b).hexdigest();summaries=[]
for name,source,solos,expect in [('pluck-host-evidence','pluck-single-loop.dsp',3,False),('pluck-reset-host-evidence','pluck-reset-loop.dsp',3,True),('pluck-reset-host-range-evidence','pluck-reset-loop.dsp',6,True),('pluck-natural-policy-host-evidence','pluck-reset-loop.dsp',3,True)]:
 d=Path('work',name);r=json.loads((d/'report.json').read_text());assert r['source_sha256']==sha(Path('work',source).read_bytes());assert r['host_version']=='0.9.0';by={(x['sample_rate'],x['label']):x for x in r['rows']};assert len(by)==4*(solos+2)
 errors=[];tails=[]
 for sr in (44100,48000,96000,192000):
  vals={}
  for label in ['mixed','silence']+['solo'+str(i) for i in range(solos)]:
   row=by[sr,label];raw=(d/f'{sr}-{label}.bin').read_bytes();assert sha(raw)==row['capture_sha256'];x=np.frombuffer(raw,dtype='<f4').reshape(-1,2);assert x.shape==(sr,2) and np.isfinite(x).all() and np.array_equal(x[:,0],x[:,1]);assert float(np.max(np.abs(x)))==row['peak'];assert row['inputs']==0 and row['outputs']==2;vals[label]=x
  assert not np.any(vals['silence']);wanted=sum(vals['solo'+str(i)] for i in range(solos));error=float(np.max(np.abs(vals['mixed']-wanted)));assert error==by[sr,'mixed']['superposition_max_error'];assert (error<2e-6)==expect;errors.append(error);tail=float(np.max(np.abs(vals['solo0'][int(.22*sr):int(.3*sr)])));assert tail==by[sr,'mixed']['release_tail_peak'];tails.append(tail)
  if name=='pluck-natural-policy-host-evidence':assert tail>0 and by[sr,'mixed']['dynamic_voices']==0
 summaries.append(dict(evidence=name,source_sha256=r['source_sha256'],captures=len(by),superposition_max_error=max(errors),release_tail_peaks=tails,expected_superposition_pass=expect,report_sha256=sha((d/'report.json').read_bytes())))
Path('outputs/blackdog-pluck-host-verification.json').write_text(json.dumps(dict(status='BOUNDED_HOST_VERIFICATION_PASS',host='DawDreamer0.9.0 macOS arm64 Python3.12',rows=summaries,admission='NOT_GRANTED'),indent=2)+'\n');print([(x['evidence'],x['captures'],x['superposition_max_error']) for x in summaries])

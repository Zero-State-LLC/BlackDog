from pathlib import Path
import json,hashlib
import dawdreamer as daw
import numpy as np
from bounded_pluck_host_contract import create_pluck_graph
source=Path('work/pluck-bounded-epoch.dsp').read_text();out=Path('work/pluck-review-edges');out.mkdir(exist_ok=True);sha=lambda b:hashlib.sha256(b).hexdigest();rows=[]
for sr in (48000,192000):
 schedules={'overlap_same_pitch':[(.01,.2,69,100),(.1,.2,69,80)],'touching_same_pitch':[(.01,.2,69,100),(.21,.2,69,80)],'same_sample_retrigger':[(.01,1/sr,69,100),(.01+1/sr,.2,69,80)],'eight_unison':[(.01,.2,69,127)]*8}
 for label,notes in schedules.items():
  captures=[]
  for i,seq in enumerate([notes]+[[n] for n in notes]):
   e,p=create_pluck_graph(daw.RenderEngine,source,seq,sr);e.render(.6);x=e.get_audio();assert x.shape==(2,int(.6*sr)) and np.isfinite(x).all();raw=x.T.astype('<f4').tobytes();file=f'{sr}-{label}-{i}.bin';(out/file).write_bytes(raw);captures.append(x)
  difference=float(np.max(np.abs(captures[0]-sum(captures[1:]))));row=dict(sample_rate=sr,schedule=label,notes=notes,peak=float(np.max(np.abs(captures[0]))),solo_sum_difference=difference,captures=[{'file':f'{sr}-{label}-{i}.bin','sha256':sha((out/f'{sr}-{label}-{i}.bin').read_bytes())} for i in range(len(captures))]);rows.append(row);print(sr,label,row['peak'],difference,flush=True)
(out/'report.json').write_text(json.dumps(dict(source_sha256=sha(source.encode()),adapter_sha256=sha(Path('work/bounded_pluck_host_contract.py').read_bytes()),runner_sha256=sha(Path(__file__).read_bytes()),review_type='INTERIM_SAME_AGENT_TECHNICAL_REVIEW',rows=rows,admission='NOT_GRANTED'),indent=2)+'\n')

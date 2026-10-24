from pathlib import Path
import json,hashlib
import numpy as np
p=Path('work/bounded-pluck-time-preflight-evidence');r=json.loads((p/'report.json').read_text());sha=lambda b:hashlib.sha256(b).hexdigest();assert r['source_sha256']==sha(Path('work/pluck-bounded-epoch.dsp').read_bytes());assert r['adapter_sha256']==sha(Path('work/bounded_pluck_host_contract.py').read_bytes());seen=set();summary=[]
for row in r['rows']:
 sr,label=row['sample_rate'],row['label'];assert (sr,label) not in seen;seen.add((sr,label));raw=(p/f'{sr}-{label}.bin').read_bytes();assert sha(raw)==row['sha256'];x=np.frombuffer(raw,dtype='<f4').reshape(-1,2);assert x.shape==(int(sr*1.5),2) and np.isfinite(x).all() and np.array_equal(x[:,0],x[:,1]);assert float(np.max(np.abs(x)))==row['peak']
for sr in (44100,48000,96000,192000):
 load=lambda label:np.fromfile(p/f'{sr}-{label}.bin',dtype='<f4').reshape(-1,2)
 a,b=load('eight'),load('sixteen');assert np.array_equal(a,load('eight-repeat'));total=sum(load('solo'+str(i)) for i in range(12));err=float(np.max(np.abs(b-total)));diff=float(np.max(np.abs(a-b)));assert err<2e-6 and diff>2e-6;summary.append(dict(sample_rate=sr,superposition_error=err,capacity_difference=diff))
assert len(seen)==60
r['independent_verification']={'status':'PASS','captures':60,'rows':summary};Path('outputs/blackdog-bounded-pluck-exhaustion-verification.json').write_text(json.dumps(r,indent=2)+'\n');print('60 captures verified; deterministic stealing and exact 16-voice superposition')

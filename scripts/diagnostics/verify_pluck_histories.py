from pathlib import Path
import json,hashlib
import numpy as np
p=Path('work/pluck-history-evidence');r=json.loads((p/'report.json').read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
assert r['source_sha256']==sha(Path('work/pluck-reset-loop.dsp').read_bytes())
assert r['adapter_sha256']==sha(Path('work/BlackDog/diagnostics/pluck_host_contract.py').read_bytes())
assert r['runner_sha256']==sha(Path('work/qualify_pluck_histories.py').read_bytes())
expected={(sr,label) for sr in (44100,48000,96000,192000) for label in ('silence','low_tail','high_tail','rapid','rapid_repeat')};seen=set()
for row in r['rows']:
 sr,label=row['sample_rate'],row['label'];assert (sr,label) in expected and (sr,label) not in seen;seen.add((sr,label))
 raw=(p/f'{sr}-{label}.bin').read_bytes();assert sha(raw)==row['capture_sha256'];x=np.frombuffer(raw,dtype='<f4').reshape(-1,2)
 assert x.shape==(12*sr,2) and np.isfinite(x).all() and np.array_equal(x[:,0],x[:,1])
 assert row['peak']==float(np.max(np.abs(x)))
 for name,part in [('first_second_rms',x[:sr,0]),('last_second_rms',x[-sr:,0])]:assert row[name]==float(np.sqrt(np.mean(part.astype('float64')**2)))
 if label=='silence':assert not np.any(x)
 if label=='rapid_repeat':assert raw==(p/f'{sr}-rapid.bin').read_bytes()
assert seen==expected
r['verification']={'status':'PASS','captures':20,'scope':'Same-workflow capture replay; not independent semantic review'}
Path('outputs/blackdog-pluck-history-verification.json').write_text(json.dumps(r,indent=2)+'\n')
print('20 captures verified')

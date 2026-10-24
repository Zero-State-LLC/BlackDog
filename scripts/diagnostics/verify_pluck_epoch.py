from pathlib import Path
import json,hashlib
import numpy as np
p=Path('work/pluck-epoch-evidence');r=json.loads((p/'report.json').read_text());sha=lambda b:hashlib.sha256(b).hexdigest();old=Path('work/pluck-reset-loop.dsp').read_bytes();new=Path('work/pluck-bounded-epoch.dsp').read_bytes();assert r['previous_source_sha256']==sha(old) and r['production_source_sha256']==sha(new);assert new==old.replace(b'epoch=+(int(reset)) ~ _;',b'epoch=(+(int(reset)) : &(65535)) ~ _;');assert r['runner_sha256']==sha(Path('work/qualify_pluck_epoch.py').read_bytes());seen=set();nonzero=0
for row in r['rows']:
 sr,f,label=row['sample_rate'],row['frequency'],row['variant'];assert (sr,f,label) not in seen;seen.add((sr,f,label));raw=(p/row['file']).read_bytes();assert sha(raw)==row['capture_sha256'];assert sha((p/f'{label}-seeded.dsp').read_bytes())==row['source_sha256'];x=np.frombuffer(raw,dtype='<f4').reshape(-1,2);assert x.shape==(sr//2,2) and np.isfinite(x).all() and np.array_equal(x[:,0],x[:,1]);assert row['peak']==float(np.max(np.abs(x)));nonzero+=row['peak']>0
 if label=='bounded':assert raw==(p/f'{sr}-{f}-unbounded.bin').read_bytes()
assert seen=={(sr,f,label) for sr in (44100,48000,96000,192000) for f in (20.,440.,7902.132820097988) for label in ('bounded','unbounded')}
raw=(p/'counter.bin').read_bytes();assert sha(raw)==r['counter_capture_sha256'];x=np.frombuffer(raw,dtype='<f4');assert len(x)==131200;assert np.array_equal(x,((np.arange(len(x))+1)//2)%65536);assert sha((p/'counter-probe.dsp').read_bytes())==r['counter_probe_sha256']
r['verification']={'status':'PASS','audio_captures':24,'nonzero_audio_captures':nonzero,'counter_samples':len(x),'counter_every_sample_matches_integer_oracle':True,'scope':'Instrumented boundary diagnostics; production qualification remains separate'};Path('outputs/blackdog-pluck-epoch-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(r['verification'])

from pathlib import Path
import json,hashlib
import numpy as np
p=Path('work/bounded-pluck-dense-evidence');r=json.loads((p/'report.json').read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
for key,file in [('source_sha256','work/pluck-bounded-epoch.dsp'),('adapter_sha256','work/bounded_pluck_host_contract.py'),('runner_sha256','work/qualify_bounded_pluck_dense.py')]:assert r[key]==sha(Path(file).read_bytes())
expected={(sr,n,v) for sr in (44100,48000,96000,192000) for n in range(16,120) for v in (1,127)};seen=set();rows=[]
for row in r['rows']:
 sr,n,v=row['sample_rate'],row['pitch'],row['velocity'];assert (sr,n,v) in expected and (sr,n,v) not in seen;seen.add((sr,n,v));assert row['file']==f'{sr}-{n}-{v}.bin'
 raw=(p/row['file']).read_bytes();assert sha(raw)==row['capture_sha256'];x=np.frombuffer(raw,dtype='<f4').reshape(-1,2);assert x.shape==(sr//2,2) and np.isfinite(x).all() and np.array_equal(x[:,0],x[:,1]);assert 0<float(np.max(np.abs(x)))<=1.00001 and row['peak']==float(np.max(np.abs(x)))
assert seen==expected
for sr in (44100,48000,96000,192000):
 errors=[]
 for n in range(16,120):
  a=np.fromfile(p/f'{sr}-{n}-1.bin',dtype='<f4');b=np.fromfile(p/f'{sr}-{n}-127.bin',dtype='<f4');err=float(np.max(np.abs(b/127-a)));assert err<2e-6;errors.append(err)
 assert (p/f'{sr}-reset-repeat.bin').read_bytes()==(p/f'{sr}-16-1.bin').read_bytes()
 rows.append(dict(sample_rate=sr,integer_pitches=104,endpoint_captures=208,max_velocity_scaling_error=max(errors),reset_repeat_exact=True))
result={k:r[k] for k in ('source_sha256','adapter_sha256','runner_sha256','scope','admission')};result.update(status='BOUNDED_DENSE_HOST_PASS',capture_count=836,report_sha256=sha((p/'report.json').read_bytes()),rates=rows,verification_scope='Same-workflow replay of hashes, finite stereo output, nonzero response, linear velocity scaling and reset repeat; not independent semantic review')
Path('outputs/blackdog-bounded-pluck-dense-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

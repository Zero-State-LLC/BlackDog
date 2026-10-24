from pathlib import Path
import json,hashlib,struct,math
b=Path('work/pluck-wasm-evidence');d=b/'pluck-wasm-check';r=json.loads((d/'report.json').read_text());sha=lambda b:hashlib.sha256(b).hexdigest();assert r['source_sha256']==sha((b/'pluck-single-loop.dsp').read_bytes())==sha(Path('work/pluck-single-loop.dsp').read_bytes());assert r['runner_sha256']==sha((b/'pluck-entry/qualify_pluck_wasm.py').read_bytes());assert {x['sample_rate'] for x in r['rows']}=={44100,48000,96000,192000}
for row in r['rows']:
 sr=row['sample_rate'];a=(d/f'{sr}-native.bin').read_bytes();b2=(d/f'{sr}-wasm.bin').read_bytes();assert len(a)==len(b2)==131072*8;assert sha(a)==row['native_sha256'] and sha(b2)==row['wasm_sha256'];maxerr=0
 for x,y in zip(struct.iter_unpack('<ff',a),struct.iter_unpack('<ff',b2)):
  assert x[0]==x[1] and y[0]==y[1] and all(map(math.isfinite,x+y));maxerr=max(maxerr,abs(x[0]-y[0]));assert abs(x[0]-y[0])<=2e-6+1e-5*abs(x[0])
 assert maxerr==row['max_absolute_error'] and row['passed'] and not row['failures']
r['independent_verification']={'status':'PASS','samples_per_channel_per_rate':131072,'archive_sha256':sha(Path('work/pluck-wasm-evidence.tar.gz').read_bytes()),'comparison_tolerance':'2e-6 absolute + 1e-5 relative, unchanged from earlier numerical diagnostics'};Path('outputs/blackdog-pluck-wasm-verification.json').write_text(json.dumps(r,indent=2)+'\n');print('Four rates verified; maximum difference',max(x['max_absolute_error'] for x in r['rows']))

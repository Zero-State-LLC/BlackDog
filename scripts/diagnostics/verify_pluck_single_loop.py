from pathlib import Path
import json,hashlib,struct,math,re
b=Path('work/pluck-single-loop-evidence');d=b/'pluck-single-loop-check';r=json.loads((d/'report.json').read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha((b/'pluck-single-loop.dsp').read_bytes())==r['source_sha256']==sha(Path('work/pluck-single-loop.dsp').read_bytes());assert sha((b/'qualify_pluck_single_loop.py').read_bytes())==r['runner_sha256']
h=(d/'generated.hpp').read_text();assert re.search(r'getNumInputs\(\)\s*\{\s*return 0;',h) and re.search(r'getNumOutputs\(\)\s*\{\s*return 2;',h)
seen=set()
for row in r['rows']:
 key=(row['sample_rate'],row['frequency'],row['gain'],row['gate_mode']);assert key not in seen;seen.add(key);raw=(d/row['file']).read_bytes();assert len(raw)==row['sample_rate']*16 and sha(raw)==row['sha256'];pairs=list(struct.iter_unpack('<ff',raw));assert all(a==b and math.isfinite(a) for a,b in pairs);peak=max(abs(a) for a,b in pairs);assert peak==row['peak'];assert bool(peak)==bool(row['gain'] and row['gate_mode']);assert pairs[0]==(0.,0.)
expected={(sr,f,g,m) for sr in (44100,48000,96000,192000) for f,g,m in [(f,.5,1) for f in (20,50,110,440,1000,4000,8000)]+[(110,.25,1),(110,0.,1),(110,.5,0)]};assert seen==expected
for sr in (44100,48000,96000,192000):
 a=struct.iter_unpack('<f',(d/f'{sr}-110-0.5-1.bin').read_bytes());b2=struct.iter_unpack('<f',(d/f'{sr}-110-0.25-1.bin').read_bytes());assert all(struct.unpack('<f',struct.pack('<f',x[0]*.5))[0]==y[0] for x,y in zip(a,b2))
r['independent_verification']={'status':'PASS','cases':40,'archive_sha256':sha(Path('work/pluck-single-loop-evidence.tar.gz').read_bytes()),'oracle_precision':'Half-amplitude comparison explicitly rounds to float32, including subnormals.'}
Path('outputs/blackdog-pluck-single-loop-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(r['independent_verification'])

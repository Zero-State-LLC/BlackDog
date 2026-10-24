from pathlib import Path
import json,hashlib,struct,math
b=Path('work/pluck-live-evidence');d=b/'pluck-live-check';r=json.loads((d/'report.json').read_text());sha=lambda b:hashlib.sha256(b).hexdigest();assert r['source_sha256']==sha(Path('work/pluck-single-loop.dsp').read_bytes());assert r['runner_sha256']==sha((b/'qualify_pluck_live.py').read_bytes());seen=set()
for row in r['rows']:
 sr,m,a=row['sample_rate'],row['schedule'],row['active'];key=(sr,m,a);assert key not in seen;seen.add(key);raw=(d/f'{sr}-{m}-{a}.bin').read_bytes();assert len(raw)==sr*32 and sha(raw)==row['capture_sha256'];peak=0.
 for x,y in struct.iter_unpack('<ff',raw):assert x==y and math.isfinite(x);peak=max(peak,abs(x))
 assert peak==row['peak'] and (a or peak==0)
assert seen=={(sr,m,a) for sr in (44100,48000,96000,192000) for m in range(3) for a in (0,1)}
r['independent_verification']={'status':'PASS','archive_sha256':sha(Path('work/pluck-live-evidence.tar.gz').read_bytes())};Path('outputs/blackdog-pluck-live-verification.json').write_text(json.dumps(r,indent=2)+'\n');print('Verified24 finite live cases, 12 silence controls; peak',max(row['peak'] for row in r['rows']))

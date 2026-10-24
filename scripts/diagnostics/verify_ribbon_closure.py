from pathlib import Path
import json,tarfile,hashlib,struct,math
b=Path('work');archive=b/'ribbon-closure-evidence.tar.gz';root=b/'ribbon-closure-evidence'
with tarfile.open(archive) as t:t.extractall(root,filter='data')
sha=lambda x:hashlib.sha256(x).hexdigest();p=root/'ribbon-closure-check';r=json.loads((p/'report.json').read_text());spec=json.loads((b/'ribbon-closure/inputs.json').read_text());assert not spec['missing'];assert len(r['rows'])==2
assert r['runner_sha256']==sha((root/'qualify_ribbon_closure.py').read_bytes())==sha((b/'qualify_ribbon_closure.py').read_bytes())
assert {x['variant'] for x in r['rows']}=={'original','closed'}
for row in r['rows']:
 variant=row['variant'];source=(root/('ribbon.dsp' if variant=='original' else 'ribbon-closed.dsp')).read_bytes();assert sha(source)==row['source_sha256']==spec['ribbon_sha256' if variant=='original' else 'source_sha256'];assert row['compile']['returncode']==row['gcc']['returncode']==0
 assert sha((p/variant/'generated.hpp').read_bytes())==row['header_sha256'];assert len(row['captures'])==4 and {x['rate'] for x in row['captures']}=={44100,48000,96000,192000}
 for c in row['captures']:
  raw=(p/variant/(str(c['rate'])+'.bin')).read_bytes();assert len(raw)==192000 and sha(raw)==c['sha256'];assert c['frames']==24000 and c['run']['returncode']==0;assert all(math.isfinite(x[0]) for x in struct.iter_unpack('<f',raw));assert raw==(p/'original'/(str(c['rate'])+'.bin')).read_bytes()
assert r['negative_omit_pi']['returncode']!=0 and 'PI' in r['negative_omit_pi']['stderr'];assert r['exact_audio_equal'] is True
r.update(archive_sha256=sha(archive.read_bytes()),local_verification='All capture hashes, finite float32 outputs, exact two-channel bytes and full matrix independently replayed',member_count=len(spec['members']),span_count=sum(map(len,spec['members'].values())))
Path('outputs/blackdog-ribbon-closure-verification.json').write_text(json.dumps(r,indent=2)+'\n');print('Four rates x 24000 frames x two channels exactly equal; omit-PI rejected');print(r['negative_omit_pi']['stderr'])

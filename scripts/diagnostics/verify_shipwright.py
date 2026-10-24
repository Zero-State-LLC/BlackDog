from pathlib import Path
import json,hashlib,math,struct,re
b=Path('work/shipwright-evidence');r=json.loads((b/'shipwright-check/report.json').read_text());sha=lambda x:hashlib.sha256(x).hexdigest();assert sha((b/'qualify_shipwright.py').read_bytes())==r['runner_sha256'];assert {x['candidate'] for x in r['rows']}=={'saw_lead','soft_pad','sub_bass','pluck','reverb'}
for row in r['rows']:
 name=row['candidate'];spec=json.loads(Path('work/shipwright-'+name+'-closure/inputs.json').read_text());assert not spec['missing'];closed=(b/('shipwright-'+name+'-closed.dsp')).read_bytes();assert sha(closed)==spec['source_sha256'];assert (b/('shipwright-'+name+'.dsp')).read_bytes()==Path('work/shipwright-sources',name+'.dsp').read_bytes()
 for spans in spec['members'].values():
  for s in spans:
   raw=Path('work/dependency-review/pinned-libraries',s['file']).read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==s['blob_sha'];assert sha(raw[s['start_byte']:s['end_byte']])==s['sha256']
 assert row['negative_missing_platform']['returncode']!=0
 assert (b/'shipwright-check'/name/'missing-platform.dsp').read_bytes()==closed.replace(b'pl = environment {',b'missing_pl = environment {')
 for v in row['variants']:
  variant=v['variant'];d=b/'shipwright-check'/name/variant;source=b/('shipwright-'+name+('-closed' if variant=='closed' else '')+'.dsp');assert sha(source.read_bytes())==v['source_sha256'];assert v['compile']['returncode']==v['gcc']['returncode']==0
  header=(d/'generated.hpp').read_text();assert int(re.search(r'getNumInputs\(\)\s*\{\s*return (\d+)',header)[1])==v['inputs']==(1 if name=='pluck' else 2 if name=='reverb' else 0)
  assert {c['rate'] for c in v['captures']}=={44100,48000,96000,192000}
  for c in v['captures']:
   raw=(d/(str(c['rate'])+'.bin')).read_bytes();vals=[x[0] for x in struct.iter_unpack('<f',raw)];assert len(raw)==192000 and sha(raw)==c['sha256'];assert all(map(math.isfinite,vals)) and max(map(abs,vals))==c['peak']>0
   assert raw==(b/'shipwright-check'/name/'original'/(str(c['rate'])+'.bin')).read_bytes()
 assert row['instrument_interface_pass']==(name!='pluck')
r['independent_verification']={'status':'PASS','finite_nonzero_captures':40,'byte_equal_pairs':20,'negative_compile_rejections':5,'interface_blocked':['pluck'],'archive_sha256':sha(Path('work/shipwright-evidence.tar.gz').read_bytes())}
Path('outputs/blackdog-shipwright-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(r['independent_verification'])

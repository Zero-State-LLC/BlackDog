from pathlib import Path
import json,copy,hashlib,re
p=Path('work/BlackDog/corpus/notice-manifest.v1.json');before=p.read_bytes();n=json.loads(before);added=[]
for name,member,file,template in [('soft_pad','ro.interleave','routes.lib','cross'),('pluck','pm.chain','physmodels.lib','speedOfSound')]:
 s=json.loads(Path('work/shipwright-'+name+'-closure/inputs.json').read_text());raw=Path('work/dependency-review/pinned-libraries',file).read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();spans=s['members'][member];assert all(x['blob_sha']==blob for x in spans)
 assert b'either version 2.1 of the' in raw[:6000] and b'License, or (at your option) any later version.' in raw[:6000]
 function=member.split('.')[1];assert not re.search(rb'declare\s+'+function.encode()+rb'\s+(?:license|copyright)',raw)
 for x in spans:
  assert hashlib.sha256(raw[x['start_byte']:x['end_byte']]).hexdigest()==x['sha256'];assert x['end_byte']<30000
 hits=[e for e in n['entries'] if e['path']==file and e['blob_sha']==blob and e['function']==function]
 if not hits:
  e=copy.deepcopy(next(e for e in n['entries'] if e['path']==file and e['blob_sha']==blob and e['function']==template));e['function']=function;n['entries'].append(e);added.append(e)
p.write_text(json.dumps(n,indent=2)+'\n')
Path('outputs/blackdog-shipwright-added-notices.json').write_text(json.dumps(dict(added=added,authority='ADR-0003 D-013 exact per-row notices; not corpus admission',before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_scope='Pinned library headers and exact overload spans; LGPL source training-only policy retained'),indent=2)+'\n');print('Added',len(added),'exact notices')

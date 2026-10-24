from pathlib import Path
import json,hashlib
sha=lambda b:hashlib.sha256(b).hexdigest();notice=json.loads(Path('work/BlackDog/corpus/notice-manifest.v1.json').read_text());rows=[]
for name in ('saw_lead','soft_pad','sub_bass','pluck','reverb'):
 s=json.loads(Path('work/shipwright-'+name+'-closure/inputs.json').read_text());records=[];missing=[]
 for member,spans in s['members'].items():
  for span in spans:
   raw=Path('work/dependency-review/pinned-libraries',span['file']).read_bytes();assert sha(raw[span['start_byte']:span['end_byte']])==span['sha256']
   hits=[n for n in notice['entries'] if n['repo']=='grame-cncm/faustlibraries' and n['commit']==s['library_pin'] and n['path']==span['file'] and n['blob_sha']==span['blob_sha'] and n['function']==member.split('.')[1]]
   if len(hits)!=1:missing.append(member)
   records.append(dict(member=member,**{k:v for k,v in span.items() if k!='text'},license=hits[0]['license'] if len(hits)==1 else None))
 rows.append(dict(candidate=name,source_sha256=s['source_sha256'],roots=s['roots'],members=len(s['members']),spans=len(records),missing_dependencies=s['missing'],unresolved_notices=sorted(set(missing)),records=records,admission='NOT_GRANTED',teacher_provenance='UNVERIFIED',library_pin=s['library_pin']))
Path('outputs/blackdog-shipwright-closure-review.json').write_text(json.dumps(dict(rows=rows,origin_commit='eef7b31e2b82974172d8c562412069624861950a',origin_blob='bbb0a0d2fe0256de0ebedc1c42c715f734250d63',scope='Default Python arguments, statically extracted without executing upstream code; explicit diagnostic library pin, not claimed original environment'),indent=2)+'\n')
print([(r['candidate'],r['unresolved_notices']) for r in rows])

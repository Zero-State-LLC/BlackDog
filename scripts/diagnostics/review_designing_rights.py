from pathlib import Path
import json,hashlib
b=Path('work');p=b/'BlackDog/corpus/notice-manifest.v1.json';notice=json.loads(p.read_text());sha=lambda x:hashlib.sha256(x).hexdigest();results=[]
for kind in ('bitcrush','bouncing-ball'):
 spec=json.loads((b/('designing-'+kind+'-closure')/'inputs.json').read_text());rows=[]
 for member,spans in spec['members'].items():
  for s in spans:
   blob=(b/'dependency-review/pinned-libraries'/s['file']).read_bytes();assert hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()==s['blob_sha'];assert sha(blob[s['start_byte']:s['end_byte']])==s['sha256'];assert b'TODO: if/when Romain agrees' not in blob[s['start_byte']:s['end_byte']]
   hits=[n for n in notice['entries'] if n['repo']=='grame-cncm/faustlibraries' and n['commit']==spec['library_pin'] and n['path']==s['file'] and n['blob_sha']==s['blob_sha'] and n['function']==member.split('.')[1]];assert len(hits)==1;n=hits[0]
   rows.append(dict(member=member,**{k:v for k,v in s.items() if k!='text'},license=n['license'],eligible_for=['train'] if 'LGPL' in n['license'] else ['train','eval','redistribute']))
 results.append(dict(candidate=kind,source_sha256=spec['source_sha256'],members=len(spec['members']),spans=len(rows),records=rows,unresolved=[],library_closure_eligible_for=['train'],training_only_members=sorted({r['member'] for r in rows if r['eligible_for']==['train']}),candidate_provenance='MIT root and Agent Cooper + Robert declaration; exact teacher provenance unverified',admission='NOT_GRANTED'))
Path('outputs/blackdog-designing-closure-rights.json').write_text(json.dumps(dict(status='EXACT_LIBRARY_RIGHTS_REVIEW_NOT_ADMISSION',notice_manifest_sha256=sha(p.read_bytes()),added_notices=[],rows=results),indent=2)+'\n');print([(r['candidate'],r['members'],r['spans'],r['library_closure_eligible_for']) for r in results])

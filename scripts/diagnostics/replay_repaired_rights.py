from pathlib import Path
import hashlib,json,re
b=Path('work');repo=b/'BlackDog';sha=lambda x:hashlib.sha256(x).hexdigest();pin='2edec0537f536eaa130d42c354884d7db971663c'
p=repo/'corpus/notice-manifest.v1.json';notice=json.loads(p.read_bytes());before=sha(p.read_bytes());records=json.loads(Path('outputs/blackdog-analyzer-closure-verification.json').read_bytes())['member_records'];rows=[];added=[]
for m in records:
 raw=(b/'dependency-review/original-blobs'/m['file']).read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==m['blob_sha'];span=raw[m['start_byte']:m['end_byte']];assert sha(span)==m['source_sha256'];assert b'TODO: if/when Romain agrees' not in span
 function=m['member'].split('.')[1];hits=[n for n in notice['entries'] if n['repo']=='grame-cncm/faustlibraries' and n['commit']==pin and n['path']==m['file'] and n['blob_sha']==m['blob_sha'] and n['function']==function]
 declarations='\n'.join(m['direct_declarations']);lic=re.search(r' license "([^"]+)"',declarations);attr=re.search(r' (?:copyright|author) "([^"]+)"',declarations);lic=lic[1].replace('LicenseRef-','') if lic else None
 if not hits and lic in ('MIT','STK-4.3') and attr:
  n=dict(repo='grame-cncm/faustlibraries',commit=pin,path=m['file'],blob_sha=m['blob_sha'],function=function,copyright=attr[1],license=lic,evidence_label='OBSERVED')
  if lic=='STK-4.3':n['license_notice']='Redistribution bundles the STK-4.3 permission notice recorded in license_texts.'
  notice['entries'].append(n);added.append(n);hits=[n]
 if not hits and m['file']=='maths.lib' and function in ('EPSILON','MIN','MAX'):
  n=dict(repo='grame-cncm/faustlibraries',commit=pin,path=m['file'],blob_sha=m['blob_sha'],function=function,copyright='Copyright (C) 2003-2016 GRAME, Centre National de Creation Musicale',license='LGPL-2.1-or-later',evidence_label='OBSERVED');notice['entries'].append(n);added.append(n);hits=[n]
 assert len(hits)<=1
 if hits:
  n=hits[0]
  if lic:assert lic==n['license']
  eligible=['train'] if 'LGPL' in n['license'] else ['train','eval','redistribute']
  status='NOTICE_BOUND_POLICY_REVIEWED'
 else:n=None;eligible=[];status='UNRESOLVED_SECTION_LICENSE'
 rows.append(dict(member=m['member'],file=m['file'],blob_sha=m['blob_sha'],start_byte=m['start_byte'],end_byte=m['end_byte'],source_sha256=m['source_sha256'],notice=n,status=status,eligible_for=eligible,reviewer='Codex, applying existing ADR-0003 D-013; no new owner decision'))
assert not added, 'Unexpected missing notice; review before mutation'
closures=json.loads((b/'analyzer-closures/inputs.json').read_text())['rows'];out=[]
for c in closures:
 members=[r for r in rows if r['member'] in c['members']];eligible=set(['train','eval','redistribute'])
 for r in members:eligible &=set(r['eligible_for'])
 out.append(dict(name=c['name'],eligible_for=sorted(eligible),unresolved=sorted(set(r['member'] for r in members if not r['eligible_for'])),training_only_members=sorted(set(r['member'] for r in members if r['eligible_for']==['train']))))
Path('outputs/blackdog-repaired-closure-rights.json').write_text(json.dumps(dict(status='EXACT_SPAN_POLICY_REVIEW_NOT_ADMISSION',policy='docs/adr/0003-licensing-and-data-rights.md#d-013',notice_manifest_sha256=sha(p.read_bytes()),prior_notice_manifest_sha256=before,added_notices=added,member_records=rows,closures=out,admission='NOT_GRANTED'),indent=2)+'\n');print('added',len(added),'notices; reviewed',len(rows),'spans');print(out)

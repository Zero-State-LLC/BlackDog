from pathlib import Path
import json,hashlib,re,copy
b=Path('work');r=json.loads((b/'ribbon-closure/inputs.json').read_text());p=b/'BlackDog/corpus/notice-manifest.v1.json';raw=p.read_bytes();notice=json.loads(raw);sha=lambda x:hashlib.sha256(x).hexdigest();added=[];rows=[]
osc=(b/'dependency-review/pinned-libraries/oscillators.lib').read_bytes();jos=osc.index(b'FAUST library file, jos section');endgrame=osc.index(b'// end GRAME section');header=osc[jos:osc.index(b'************************************************************************/',jos)]
assert b'(MIT-style) [STK-4.3]' in header and b'Copyright (C) 2003-2022 by Julius O. Smith III' in header
for key,spans in r['members'].items():
 function=key.split('.')[1];first=spans[0];hits=[n for n in notice['entries'] if n['repo']=='grame-cncm/faustlibraries' and n['commit']==r['library_pin'] and n['path']==first['file'] and n['blob_sha']==first['blob_sha'] and n['function']==function]
 if not hits:
  assert function in ('_phasor_imp','_sawN_fix','_sawN_imp','_sawN_poly','saw2ptr') and first['file']=='oscillators.lib'
  template='_phasor_fix' if function=='_phasor_imp' else ('sawN' if function=='saw2ptr' else '_sawN_flt')
  if function=='_phasor_imp':assert all(x['end_byte']<endgrame for x in spans)
  else:assert all(x['start_byte']>jos for x in spans)
  if function=='saw2ptr':assert b'declare saw2ptr license "LicenseRef-STK-4.3";' in osc and b'declare saw2ptr author "Julius O. Smith III";' in osc
  n=copy.deepcopy(next(n for n in notice['entries'] if n['function']==template and n['path']=='oscillators.lib' and n['blob_sha']==first['blob_sha']));n['function']=function;notice['entries'].append(n);added.append(n);hits=[n]
 assert len(hits)==1;n=hits[0]
 for s in spans:
  blob=(b/'dependency-review/pinned-libraries'/s['file']).read_bytes();span=blob[s['start_byte']:s['end_byte']];assert sha(span)==s['sha256'];assert b'TODO: if/when Romain agrees' not in span
  rows.append(dict(member=key,**{k:v for k,v in s.items() if k!='text'},license=n['license'],eligible_for=['train'] if 'LGPL' in n['license'] else ['train','eval','redistribute']))
# D-013 delegates exact per-row notices. This does not admit a dataset unit.
if added:p.write_text(json.dumps(notice,indent=2)+'\n')
out=dict(status='EXACT_LIBRARY_SPAN_RIGHTS_REVIEW_NOT_ADMISSION',library_pin=r['library_pin'],source_sha256=r['source_sha256'],member_count=len(r['members']),span_count=len(rows),unresolved=[],member_records=rows,added_notices=added,notice_manifest_before_sha256=sha(raw),notice_manifest_after_sha256=sha(p.read_bytes()),library_closure_eligible_for=['train'],training_only_members=sorted({x['member'] for x in rows if x['eligible_for']==['train']}),ribbon_source_rights='MIT root; canonical full-source admission remains pending',reviewer='Codex applying delegated ADR-0003 D-013 per-row rules',mixed_blob_guard='No blanket oscillators.lib clearance; disputed documentation excluded from exact slices',admission='NOT_GRANTED')
Path('outputs/blackdog-ribbon-closure-rights.json').write_text(json.dumps(out,indent=2)+'\n');print('spans',len(rows),'added',len(added),'training-only',out['training_only_members'])

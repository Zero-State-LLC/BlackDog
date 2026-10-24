from pathlib import Path
import json,hashlib
exec(compile(Path('work/screen_pluck_single_loop.py').read_text().split('\nedges=[];f=')[0],'population','exec'))
raw=Path('work/stratus-tester.dsp').read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='de744540f1b9f3be7e06fb57fe2cd59911cefe8b'
rows=[]
for name,path in [('pluck_reset','work/pluck-reset-loop.dsp'),('stratus_tester','work/stratus-tester.dsp')]:
 raw=Path(path).read_bytes();uid='new:'+name;text[uid]=normalize_bytes(raw).text;rows.append(dict(candidate=name,unit_id=uid,source_sha256=sha(raw)))
edges=[];f=cluster_families(sorted(text.items()),[x for x in text if x.startswith('comparison:')],evidence=edges);counts=reconstruct(f,edges);comp={f[x] for x in f if x.startswith('comparison:')}
for r in rows:
 uid=r['unit_id'];hits=[e for e in edges if uid in (e.get('left'),e.get('right')) or uid in e.get('contributors',[])];r.update(family=f[uid],comparison_connected=f[uid] in comp,joining_evidence_count=len(hits),joining_evidence=[{k:v for k,v in e.items() if k!='contributors'} for e in hits[:3]])
Path('outputs/blackdog-reset-stratus-family.json').write_text(json.dumps(dict(graph=counts,rows=rows,admission='NOT_GRANTED',policy='unchanged floor40 provisional H1 collective'),indent=2)+'\n');print(counts,[(r['candidate'],r['comparison_connected']) for r in rows])

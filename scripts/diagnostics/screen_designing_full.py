from pathlib import Path
import json
s=Path('work/screen_ribbon_full.py').read_text().split('\nedges=[];f=')[0];exec(compile(s,'verified-population','exec'))
rows=[]
for kind in ('bitcrush','bouncing-ball'):
 raw=Path('work/designing-'+kind+'-closure/'+kind+'-closed.dsp').read_bytes();spec=json.loads(Path('work/designing-'+kind+'-closure/inputs.json').read_text());assert sha(raw)==spec['source_sha256'];uid='new:designing:'+kind;text[uid]=normalize_bytes(raw).text;rows.append(dict(unit_id=uid,candidate=kind,source_sha256=sha(raw)))
edges=[];f=cluster_families(sorted(text.items()),[x for x in text if x.startswith('comparison:')],evidence=edges);counts=reconstruct(f,edges);comp={f[x] for x in f if x.startswith('comparison:')}
for row in rows:
 uid=row['unit_id'];hits=[e for e in edges if uid in (e.get('left'),e.get('right')) or uid in e.get('contributors',[])];row.update(family=f[uid],comparison_connected=f[uid] in comp,joining_evidence_count=len(hits),joining_evidence=[{k:v for k,v in e.items() if k!='contributors'} for e in hits[:3]])
Path('outputs/blackdog-designing-full-family.json').write_text(json.dumps(dict(graph=counts,rows=rows,policy='unchanged floor40 provisional H1 collective',admission='NOT_GRANTED'),indent=2)+'\n');Path('work/designing-sources/edges.json').write_text(json.dumps(edges,sort_keys=True));Path('work/designing-sources/families.json').write_text(json.dumps(f,sort_keys=True));print(counts,[(r['candidate'],r['comparison_connected']) for r in rows])

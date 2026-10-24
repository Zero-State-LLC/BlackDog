from pathlib import Path
import json
exec(compile(Path('work/screen_designing_full.py').read_text().split('\nedges=[];f=')[0],'population','exec'))
raw=Path('work/bouncing-rate-repair-evidence/bouncing-rate-repair/fixed-closed.dsp').read_bytes();text['new:designing:bouncing-ball-rate-repair']=normalize_bytes(raw).text
rows=[]
for name in ('saw_lead','soft_pad','sub_bass','pluck','reverb'):
 raw=Path('work/shipwright-'+name+'-closure/'+name+'-closed.dsp').read_bytes();uid='new:shipwright:'+name;text[uid]=normalize_bytes(raw).text;rows.append(dict(candidate=name,unit_id=uid,source_sha256=sha(raw)))
edges=[];f=cluster_families(sorted(text.items()),[x for x in text if x.startswith('comparison:')],evidence=edges);counts=reconstruct(f,edges);comp={f[x] for x in f if x.startswith('comparison:')}
for r in rows:r.update(family=f[r['unit_id']],comparison_connected=f[r['unit_id']] in comp)
Path('outputs/blackdog-shipwright-family.json').write_text(json.dumps(dict(graph=counts,rows=rows,admission='NOT_GRANTED',policy='unchanged floor40 provisional H1 collective'),indent=2)+'\n');print(counts,rows)

from pathlib import Path
import json
s=Path('work/screen_ribbon.py').read_text().split('\nedges=[];f=')[0];exec(compile(s,'verified-population','exec'))
source=Path('work/ribbon-closure/ribbon-closed.dsp').read_bytes();r=json.loads(Path('work/ribbon-closure/inputs.json').read_text());assert sha(source)==r['source_sha256'];uid='new:ribbon:full-pinned-closure';text[uid]=normalize_bytes(source).text
edges=[];f=cluster_families(sorted(text.items()),[x for x in text if x.startswith('comparison:')],evidence=edges);counts=reconstruct(f,edges);comp={f[x] for x in f if x.startswith('comparison:')};hits=[e for e in edges if uid in (e.get('left'),e.get('right')) or uid in e.get('contributors',[])]
out=dict(graph=counts,unit_id=uid,source_sha256=sha(source),family=f[uid],comparison_connected=f[uid] in comp,joining_evidence_count=len(hits),joining_evidence=[{k:v for k,v in e.items() if k!='contributors'} for e in hits[:4]],policy='unchanged floor40 provisional H1 collective',admission='NOT_GRANTED')
Path('outputs/blackdog-ribbon-full-family.json').write_text(json.dumps(out,indent=2)+'\n');Path('work/ribbon-closure/families.json').write_text(json.dumps(f,sort_keys=True));Path('work/ribbon-closure/edges.json').write_text(json.dumps(edges,sort_keys=True));print(out)

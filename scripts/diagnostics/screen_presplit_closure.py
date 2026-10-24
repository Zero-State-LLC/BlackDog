from pathlib import Path
import json
s=Path('work/screen_omi.py').read_text().split('\nedges=[];f=')[0];exec(compile(s,'verified-population','exec'))
raw=Path('work/paired-presplit-coefficients.dsp').read_bytes();assert sha(raw)=='d4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e'
uid='repair:presplit-complete';text[uid]=normalize_bytes(raw).text
edges=[];f=cluster_families(sorted(text.items()),[x for x in text if x.startswith('comparison:')],evidence=edges);counts=reconstruct(f,edges);comp={f[x] for x in f if x.startswith('comparison:')}
hits=[x for x in edges if uid in (x.get('left'),x.get('right')) or uid in x.get('contributors',[])]
result=dict(graph=counts,source_sha256=sha(raw),unit_id=uid,family=f[uid],comparison_connected=f[uid] in comp,joining_evidence_count=len(hits),joining_evidence=[{k:v for k,v in x.items() if k!='contributors'} for x in hits[:3]],admission='NOT_GRANTED',policy='unchanged floor40 provisional H1 collective',scope='Prior 1528 identities plus complete repaired source')
Path('outputs/blackdog-presplit-closure-family.json').write_text(json.dumps(result,indent=2)+'\n');Path('work/evaluation-search/presplit-families.json').write_text(json.dumps(f,sort_keys=True));Path('work/evaluation-search/presplit-edges.json').write_text(json.dumps(edges,sort_keys=True));print(json.dumps(result,indent=2))

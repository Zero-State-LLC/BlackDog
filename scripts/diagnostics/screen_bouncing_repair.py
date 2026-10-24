from pathlib import Path
import json
exec(compile(Path('work/screen_designing_full.py').read_text().split('\nedges=[];f=')[0],'population','exec'))
raw=Path('work/bouncing-rate-repair-evidence/bouncing-rate-repair/fixed-closed.dsp').read_bytes();uid='new:designing:bouncing-ball-rate-repair';text[uid]=normalize_bytes(raw).text
edges=[];f=cluster_families(sorted(text.items()),[x for x in text if x.startswith('comparison:')],evidence=edges);counts=reconstruct(f,edges);comp={f[x] for x in f if x.startswith('comparison:')}
r=dict(graph=counts,unit_id=uid,source_sha256=sha(raw),family=f[uid],comparison_connected=f[uid] in comp,policy='unchanged floor40 provisional H1 collective',admission='NOT_GRANTED')
Path('outputs/blackdog-bouncing-rate-repair-family.json').write_text(json.dumps(r,indent=2)+'\n');print(r)

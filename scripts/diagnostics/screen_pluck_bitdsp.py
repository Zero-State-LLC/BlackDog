from pathlib import Path
import json
exec(compile(Path('work/screen_shipwright.py').read_text().split('\nedges=[];f=')[0],'population','exec'))
rows=[]
for name,path in [('pluck_repair','work/shipwright-pluck_repair-closure/pluck_repair-closed.dsp'),('bitdsp_full_adder','work/bitdsp-source/full_adder-closed.dsp'),('bitdsp_bitstream_adder','work/bitdsp-source/bitstream_adder-closed.dsp')]:
 raw=Path(path).read_bytes();uid='new:'+name;text[uid]=normalize_bytes(raw).text;rows.append(dict(candidate=name,unit_id=uid,source_sha256=sha(raw)))
edges=[];f=cluster_families(sorted(text.items()),[x for x in text if x.startswith('comparison:')],evidence=edges);counts=reconstruct(f,edges);comp={f[x] for x in f if x.startswith('comparison:')}
for r in rows:r.update(family=f[r['unit_id']],comparison_connected=f[r['unit_id']] in comp)
Path('outputs/blackdog-pluck-bitdsp-family.json').write_text(json.dumps(dict(graph=counts,rows=rows,admission='NOT_GRANTED',policy='unchanged floor40 provisional H1 collective'),indent=2)+'\n');print(counts,rows)

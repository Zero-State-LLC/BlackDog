from pathlib import Path
import json,re,hashlib
s=Path('work/screen_arcturus.py').read_text().split('\nedges=[];f=')[0];exec(compile(s,'verified-population','exec'))
raw=Path('work/evaluation-search/ribbon.dsp').read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='af146e17caaf28dccbe4ee04cc8d65ae5858576b'
rows=[]
for name in ('carrierGroup','modulatorGroup'):
 m=re.search(rb'(?m)^'+name.encode()+rb'\([^;]+;',raw);assert m;uid='new:ribbon:'+name;text[uid]=normalize_bytes(m[0]).text
 rows.append(dict(unit_id=uid,symbol=name,span=list(m.span()),closure_sha256=sha(m[0]),external_dependencies=[],primitive_dependencies=['vgroup'],project='simplicit-mc/ribbon-synth'))
# Mask comments before listing active qualified references; this is a direct inventory, not a transitive closure.
active=re.sub(rb'/\*.*?\*/|//[^\n]*',lambda m:b' '*len(m[0]),raw,flags=re.S)
refs=sorted({m[0].decode() for m in re.finditer(rb'\b[a-z]+\.[A-Za-z_]\w*',active)}-{'stdfaust.lib'})
edges=[];f=cluster_families(sorted(text.items()),[x for x in text if x.startswith('comparison:')],evidence=edges);counts=reconstruct(f,edges);comp={f[x] for x in f if x.startswith('comparison:')}
for row in rows:
 uid=row['unit_id'];hits=[x for x in edges if uid in (x.get('left'),x.get('right')) or uid in x.get('contributors',[])];row.update(family=f[uid],comparison_connected=f[uid] in comp,joining_evidence_count=len(hits),joining_evidence=[{k:v for k,v in x.items() if k!='contributors'} for x in hits[:2]])
r=dict(graph=counts,rows=rows,source_commit='a793afc33dc0b0854e5ca8a34c22e9d98a125b73',source_blob='af146e17caaf28dccbe4ee04cc8d65ae5858576b',license_blob='ffb96189b85cd5129fa6f967f557f7544c35fb04',rights='MIT root; canonical unit rights not admitted',full_source_imports=['stdfaust.lib'],full_source_direct_library_references=refs,full_source_transitive_closure_complete=False,admission='NOT_GRANTED',policy='unchanged floor40 provisional H1 collective',limitations=['Both wrappers belong to one project','Complete wrapper closures only; full synthesizer transitive closure remains incomplete','Commented AM example excluded from active reference inventory','No semantic approval, evaluation admission or signed membership inferred'])
Path('outputs/blackdog-ribbon-family.json').write_text(json.dumps(r,indent=2)+'\n');Path('work/evaluation-search/ribbon-edges.json').write_text(json.dumps(edges,sort_keys=True));Path('work/evaluation-search/ribbon-families.json').write_text(json.dumps(f,sort_keys=True));print(json.dumps(r,indent=2))

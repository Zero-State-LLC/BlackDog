from pathlib import Path
import json,re,hashlib
s=Path('work/screen_presplit_closure.py').read_text().split('\nedges=[];f=')[0];exec(compile(s,'verified-population','exec'))
p=Path('work/evaluation-search/bitbus');p.mkdir(exist_ok=True)
raw=Path('work/evaluation-search/bitDSP_conversion.lib').read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='f6e11f6bdad22fee13ca3528ae2ce52cfce9d9c5'
lib=Path('work/dependency-review/original-blobs/signals.lib').read_bytes();assert hashlib.sha1(b'blob '+str(len(lib)).encode()+b'\0'+lib).hexdigest()=='25679491349e746ee528d11a1cae23635a0524b3'
bus=list(re.finditer(rb'(?m)^bus\([^;]+;',lib));assert len(bus)==4
context=b'si = environment {\n'+b'\n'.join(m[0] for m in bus)+b'\n};\n';rows=[]
for name in ['bitBus_to_int','int32_to_bitBus']:
 m=re.search(rb'(?m)^'+name.encode()+rb'\([^;]+;',raw);assert m;closure=context+m[0];uid='new:bitbus:'+name;assert uid not in text;text[uid]=normalize_bytes(closure).text;(p/(name+'.dsp')).write_bytes(closure)
 rows.append(dict(unit_id=uid,source_commit='d70843492b65bb2cb9cf97c2240905fefacc7383',source_blob='f6e11f6bdad22fee13ca3528ae2ce52cfce9d9c5',source_url='https://github.com/rottingsounds/bitDSP-faust/blob/d70843492b65bb2cb9cf97c2240905fefacc7383/lib/bitDSP_conversion.lib',target_span=list(m.span()),target_sha256=sha(m[0]),closure_sha256=sha(closure),dependencies=[dict(name='si.bus',blob='25679491349e746ee528d11a1cae23635a0524b3',spans=[list(x.span()) for x in bus])],external_unresolved=[],rights='Root MIT; pinned si.bus is LGPL-2.1-or-later with Faust compiled-code exception; closure remains training-only under D-013, no admission'))
edges=[];f=cluster_families(sorted(text.items()),[x for x in text if x.startswith('comparison:')],evidence=edges);counts=reconstruct(f,edges);comp={f[x] for x in f if x.startswith('comparison:')}
for row in rows:
 uid=row['unit_id'];row.update(family=f[uid],comparison_connected=f[uid] in comp,eligible_for=['train'],evaluation_eligible=False);hits=[x for x in edges if uid in (x.get('left'),x.get('right')) or uid in x.get('contributors',[])];row['joining_evidence_count']=len(hits);row['joining_evidence']=[{k:v for k,v in x.items() if k!='contributors'} for x in hits[:2]]
result=dict(graph=counts,rows=rows,admission='NOT_GRANTED',policy='unchanged floor40 provisional H1 collective')
Path('outputs/blackdog-bitbus-family.json').write_text(json.dumps(result,indent=2)+'\n');(p/'families.json').write_text(json.dumps(f,sort_keys=True));(p/'edges.json').write_text(json.dumps(edges,sort_keys=True));print(json.dumps(result,indent=2))

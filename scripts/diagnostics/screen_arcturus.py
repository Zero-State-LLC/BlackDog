from pathlib import Path
import json,re,hashlib
s=Path('work/screen_bitbus_candidates.py').read_text().split('\nedges=[];f=')[0];exec(compile(s,'verified-population','exec'))
root=Path('work/evaluation-search');blobs={'arcturus-effects.dsp':'75fadbb415de3b73ec60f4b152cee1ef9c318f86','arcturus-synth.dsp':'a1ac7eb0bd4ce73a79cd6901e0100b77fc529e98','ribbon.dsp':'af146e17caaf28dccbe4ee04cc8d65ae5858576b','arcturus-LICENSE':'c1f9f5dddc8a62c21ca43d12a3554dac59918d35','ribbon-LICENSE':'ffb96189b85cd5129fa6f967f557f7544c35fb04'}
raws={}
for file,blob in blobs.items():
 raw=(root/file).read_bytes()
 def gitsha(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
 if gitsha(raw)!=blob and gitsha(raw[:-1])==blob:raw=raw[:-1];(root/file).write_bytes(raw)
 assert gitsha(raw)==blob,(file,gitsha(raw));raws[file]=raw
rows=[]
for name,file in [('cubicNL','arcturus-effects.dsp'),('envShape','arcturus-synth.dsp'),('widenStereo','arcturus-effects.dsp')]:
 raw=raws[file];start=raw.index(name.encode()+b'(');end=raw.index(b'};',start)+2 if name=='widenStereo' else raw.index(b';',start)+1;target=raw[start:end];context=b'';deps=[]
 if name=='widenStereo':
  m=re.search(rb'(?m)^stereo_width\s*=.*?;',raw);assert m;context=m[0]+b'\n';deps=[{'symbol':'stereo_width','span':list(m.span()),'sha256':sha(m[0]),'kind':'built-in hslider'}]
 closure=context+target;uid='new:arcturus:'+name;text[uid]=normalize_bytes(closure).text;(root/(name+'-closure.dsp')).write_bytes(closure)
 rows.append(dict(unit_id=uid,symbol=name,source_file=file,source_blob=blobs[file],commit='21f4b3105dbd5a76359adf9d1c8907c25b50532d',project='Lef-F/arcturus',target_span=[start,end],target_sha256=sha(target),closure_sha256=sha(closure),dependencies=deps,external_library_dependencies=[],rights='MIT root; canonical unit-rights review pending',admission='NOT_GRANTED'))
edges=[];f=cluster_families(sorted(text.items()),[x for x in text if x.startswith('comparison:')],evidence=edges);counts=reconstruct(f,edges);comp={f[x] for x in f if x.startswith('comparison:')}
for row in rows:
 uid=row['unit_id'];hits=[x for x in edges if uid in (x.get('left'),x.get('right')) or uid in x.get('contributors',[])];row.update(family=f[uid],comparison_connected=f[uid] in comp,joining_evidence_count=len(hits),joining_evidence=[{k:v for k,v in x.items() if k!='contributors'} for x in hits[:3]])
r=dict(graph=counts,rows=rows,admission='NOT_GRANTED',policy='unchanged floor40 provisional H1 collective',limitations=['All three candidates share one project and cannot count as separate independent projects','This is a lexical family screen, not canonical project/lineage admission','Full synthesizer library dependencies are not the dependency closures of these selected functions','No evaluation eligibility granted; prompt semantics, numerical testing, source rights, project lineage and signed membership still required'],source_blobs=blobs)
Path('outputs/blackdog-arcturus-family.json').write_text(json.dumps(r,indent=2)+'\n');(root/'arcturus-families.json').write_text(json.dumps(f,sort_keys=True));(root/'arcturus-edges.json').write_text(json.dumps(edges,sort_keys=True));print(json.dumps(r,indent=2))

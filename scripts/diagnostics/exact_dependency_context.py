from pathlib import Path
import hashlib,json,re
raw=Path('work/paired-presplit-coefficients.dsp').read_bytes();sha=lambda b:hashlib.sha256(b).hexdigest();assert sha(raw)=='d4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e'
start=raw.index(b'ds = environment {');target=Path('work/presplit-pair-v2/target.dsp').read_bytes();end=raw.index(target);rows=[]
for name in ('r','renorm'):
 m=re.search(rb'(?m)^'+name.encode()+rb'\([^;]+;',raw[start:end]);assert m
 a=start+m.start();b=start+m.end();rows.append(dict(symbol='ds.'+name,span=[a,b],source_sha256=sha(raw[a:b]),text=raw[a:b].decode(),scope='ds environment, not cutctl'))
calls=[{'byte':m.start(),'line':raw[:m.start()].count(b'\n')+1} for m in re.finditer(rb'\bmulk\(',raw) if not end<=m.start()<end+len(target)]
assert len(calls)==4
r=dict(source_sha256=sha(raw),target_sha256=sha(target),direct_dependency_spans=rows,library_dependencies_of_target=[],primitive_dependencies=['max','min','arithmetic and composition operators'],integration_calls=calls,limitations=['Direct helper dependency closure is not the full supplied context rights closure','Pinned source contains an historical comment naming 44100/48000 only; retained later four-rate evidence governs diagnostic scope, and source bytes are unchanged','Native product probes do not replace compiler provenance or independent human semantic review'],admission='NOT_GRANTED')
Path('outputs/blackdog-exact-dependency-context.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

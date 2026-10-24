from pathlib import Path
import json,hashlib,ast,types
import numpy as np
sha=lambda b:hashlib.sha256(b).hexdigest();p=Path('work/pluck-review-edges');r=json.loads((p/'report.json').read_text());assert r['source_sha256']==sha(Path('work/pluck-bounded-epoch.dsp').read_bytes());assert r['adapter_sha256']==sha(Path('work/bounded_pluck_host_contract.py').read_bytes());assert r['runner_sha256']==sha(Path('work/review_bounded_pluck_edges.py').read_bytes())
engine=Path('work/shipwright-engine.py').read_bytes();assert hashlib.sha1(b'blob '+str(len(engine)).encode()+b'\0'+engine).hexdigest()=='526864e97e865f509453340fd071aaa9bcad79e7';tree=ast.parse(engine);fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='_limit');ns={'np':np,'config':types.SimpleNamespace(MASTER_CEILING=.97)};exec(compile(ast.Module(body=[fn],type_ignores=[]),'pinned-shipwright-limit','exec'),ns)
seen=set();count=0
for row in r['rows']:
 sr,label=row['sample_rate'],row['schedule'];assert (sr,label) not in seen;seen.add((sr,label));arrays=[]
 for c in row['captures']:
  raw=(p/c['file']).read_bytes();assert sha(raw)==c['sha256'];x=np.frombuffer(raw,dtype='<f4').reshape(-1,2);assert x.shape==(int(.6*sr),2) and np.isfinite(x).all() and np.array_equal(x[:,0],x[:,1]);arrays.append(x);count+=1
 assert len(arrays)==len(row['notes'])+1;assert float(np.max(np.abs(arrays[0])))==row['peak'];assert float(np.max(np.abs(arrays[0]-sum(arrays[1:]))))==row['solo_sum_difference']==0
 limited=ns['_limit'](arrays[0]);assert np.isfinite(limited).all() and np.max(np.abs(limited))<=.9700001;row['existing_export_peak']=float(np.max(np.abs(limited)));row['existing_export_scale']=.97/row['peak'] if row['peak']>.97 else 1.
assert seen=={(sr,label) for sr in (48000,192000) for label in ('overlap_same_pitch','touching_same_pitch','same_sample_retrigger','eight_unison')}
r['verification']={'capture_count':count,'status':'PASS','same_pitch_superposition':'exact in all six timing cases','unison_superposition':'exact in both eight-voice cases','engine_blob':'526864e97e865f509453340fd071aaa9bcad79e7','config_blob':'38e1fa3f3fd7a3d0355428356cde7f4b472e6c3b','export_scope':'Executed pinned _limit AST in isolation at documented default ceiling0.97; not full engine/export integration'};Path('outputs/blackdog-pluck-interim-edge-verification.json').write_text(json.dumps(r,indent=2)+'\n');print('Verified',count,'captures; raw max',max(x['peak'] for x in r['rows']),'limited max',max(x['existing_export_peak'] for x in r['rows']))

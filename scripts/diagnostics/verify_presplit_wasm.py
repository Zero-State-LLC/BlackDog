from pathlib import Path
import base64,hashlib,itertools,json,math,struct,sys
sys.path.insert(0,'work/BlackDog')
from faustcoder.diagnostic_cases import DiagnosticCase,ControlEvent
root=Path('work/presplit-wasm-evidence');out=root/'presplit-controls';report=json.loads((out/'report.json').read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
source=(root/'paired-presplit-coefficients.dsp').read_text();assert sha(source.encode())==report['source_sha256']=='d4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e'
for key,path in [('runner_sha256','presplit_wasm_qualification.py'),('harness_sha256','wasm_history_qualification.py'),('oracle_driver_sha256','presplit-controls/stock/driver.cpp'),('oracle_header_sha256','presplit-controls/stock/generated.hpp')]:assert sha((root/path).read_bytes())==report[key]
native_prior=Path('work/native-soak-evidence/native-history-soak-fivefold/stock')
assert (out/'stock/generated.hpp').read_bytes()==(native_prior/'generated.hpp').read_bytes()
assert (out/'stock/driver.cpp').read_text()==(native_prior/'driver.cpp').read_text().replace('targets(2250)','targets(11250)').replace('targets[block%2250]','targets[block]')
prior=Path('work/wasm-history-evidence/faust/worker')
for name in ['render.mjs','diagnostic-cases.mjs','node_modules/@grame/faustwasm/dist/esm/index.js']:
 assert (root/'faust/worker'/name).read_bytes()==(prior/name).read_bytes(),name
assert (root/'faust/worker/presplit-render.mjs').read_text()==(prior/'history-render.mjs').read_text().replace('./history-checkpoint.mjs','./presplit-checkpoint.mjs')
assert (root/'faust/worker/presplit-checkpoint.mjs').read_text()==(prior/'history-checkpoint.mjs').read_text().replace('40a1342836429fb8969b6737abf226a2b5ccfe19556d1882c4ced37421c1c515',report['source_sha256'])
assert len(report['rows'])==24
assert {(r['schedule'],r['rate'],r['stimulus']) for r in report['rows']}==set(itertools.product(('boundary-holds','chirped-sweep'),(44100,48000,96000,192000),('noise','impulse','sine')))
events=json.loads((out/'events.json').read_text());rat=lambda a,b:max(abs(x-y)/(2e-6+1e-5*abs(y)) for x,y in zip(a,b));jobs=0;rows=[]
expected_limits=dict(memory_bytes=805306368,output_bytes=8388608,poll_interval_s=.05,source_bytes=1048576,timeout_s=15.)
def check_receipt(receipt,rate,stim,controls,sequence,index,start,parent,inputhash,frames=144000):
 global jobs
 body=receipt['body'];assert body['compile_ok'] and body['frames']==frames and body['sample_rate']==rate and body['block_size']==64 and body['outputs']==4
 assert receipt['limits']==expected_limits and receipt['input_sha256']==inputhash
 assert set(body['toolchain']['node_flags'])=={'--permission','--disallow-code-generation-from-strings','--stack-size=8192'}
 assert body['diagnostic_case']['applied_controls'][stim]==controls
 assert receipt['sandbox']['returncode']==0 and not receipt['sandbox']['stop_reason'] and not receipt['sandbox']['stdout_truncated'] and not receipt['sandbox']['stderr_truncated']
 dc=DiagnosticCase('checkpoint-history',tuple(ControlEvent(c['block'],c['address'],c['value']) for c in controls),(stim,))
 request=dict(source=source,options=['-ftz','0'],sample_rate=rate,block_size=64,frames=frames,stimuli=[stim],press_buttons_first_block=False,diagnostic_case=dc.worker_payload(),history=dict(sequence_id=sequence,chunk_index=index,start_frame=start,parent_sha256=parent))
 assert sha(json.dumps(request).encode())==receipt['request_sha256'];jobs+=1
for row in report['rows']:
 schedule,rate,stim=row['schedule'],row['rate'],row['stimulus'];tag=f'{schedule}-{rate}-{stim}';values=[];parent=None;binding=None
 rawinput=(out/(tag+'-input.bin')).read_bytes();assert len(rawinput)==576000 and sha(rawinput)==row['input_sha256']
 controlraw=(out/(schedule+'-controls.bin')).read_bytes();assert sha(controlraw)==row['controls_sha256'];target=4000;targets=[];changes=dict(events[schedule])
 for b in range(11250):target=changes.get(b,target);targets.append(target)
 assert controlraw==struct.pack('<11250f',*targets)
 for i,c in enumerate(row['chunks']):
  raw=(out/f'{tag}-{i}.bin').read_bytes();assert len(raw)==27000 and sha(raw)==c['capture_sha256'];v=struct.unpack('<6750f',raw);assert all(map(math.isfinite,v));values+=v
  rb=(out/f'{tag}-{i}-receipt.json').read_bytes();assert sha(rb)==c['receipt_sha256'];receipt=json.loads(rb);body=receipt['body']
  local=[(b-i*2250,v) for b,v in events[schedule] if i*2250<=b<(i+1)*2250]
  assert [list(x) for x in local]==c['events'];address=body['diagnostic_case']['applied_controls'][stim][0]['address']
  controls=[dict(block=b,address=address,value=v) for b,v in local]
  check_receipt(receipt,rate,stim,controls,sha(tag.encode()),i,i*144000,parent,sha(rawinput))
  rawcp=(out/f'{tag}-{i}-checkpoint.json').read_bytes();assert sha(rawcp)==c['checkpoint_sha256']==body['history']['checkpoint_sha256'];cp=json.loads(rawcp);state=base64.b64decode(cp['state_base64'],validate=True);assert len(state)==916 and sha(state)==cp['state_sha256']==body['history']['state_sha256']
  assert cp['parent_sha256']==parent and cp['chunk_index']==i and cp['start_frame']==i*144000 and cp['end_frame']==(i+1)*144000
  assert cp['binding']['source_sha256']==report['source_sha256'] and cp['binding']['sample_rate']==rate and cp['binding']['block_size']==64 and cp['binding']['sequence_id']==sha(tag.encode())
  if binding is None:binding=cp['binding']
  assert binding==cp['binding'];parent=sha(rawcp)
  assert cp['binding']['size']==body['history']['state_bytes']==916 and cp['binding']['runtime']['libraries']==body['library_tree_sha256']
  if i==1:
   negative=struct.unpack('<6750f',(out/f'{tag}-reset.bin').read_bytes());rr=json.loads((out/f'{tag}-reset-receipt.json').read_text())
   check_receipt(rr,rate,stim,controls,sha((tag+'-reset').encode()),0,0,None,sha(rawinput))
   assert rat(v,negative)==row['reset_ratio']>1 and row['reset_rejected']
 refraw=(out/f'{tag}-stock.bin').read_bytes();assert sha(refraw)==row['reference_sha256'];reference=struct.unpack('<33750f',refraw)
 assert max(abs(x-y)*200 for x,y in zip(values,reference))==row['max_meter_error_db']
 q=rat(values,reference);assert q==row['max_tolerance_ratio'] and (q<=1)==row['passed']
 rows.append({k:v for k,v in row.items() if k!='chunks'})
# Executed after the 144 primary receipt checks by verify_presplit_wasm.py.
import tarfile
splitarchive=Path('work/presplit-split-evidence.tar.gz')
splitroot=Path('work/presplit-split-evidence')
with tarfile.open(splitarchive) as t:t.extractall(splitroot,filter='data')
sp=splitroot/'presplit-split-replay';sr=json.loads((sp/'report.json').read_text())
assert sr['passed'] and sr['source_sha256']==report['source_sha256']
assert sha((splitroot/'presplit_split_replay.py').read_bytes())==sr['runner_sha256']
tag='chirped-sweep-48000-sine';original=(out/(tag+'-input.bin')).read_bytes()
full_events=events['chirped-sweep'][:2250]
def cpcheck(path,receipt,sequence,index,start,frames,parent):
 raw=path.read_bytes();cp=json.loads(raw);body=receipt['body'];state=base64.b64decode(cp['state_base64'],validate=True)
 assert sha(raw)==body['history']['checkpoint_sha256']
 assert len(state)==916 and sha(state)==cp['state_sha256']==body['history']['state_sha256']==body['history']['state_sha256']
 assert cp['binding']['source_sha256']==report['source_sha256'] and cp['binding']['sample_rate']==48000 and cp['binding']['block_size']==64 and cp['binding']['size']==916
 assert cp['binding']['sequence_id']==sequence
 assert cp['binding']['runtime']==json.loads((out/(tag+'-0-checkpoint.json')).read_text())['binding']['runtime']
 assert cp['chunk_index']==index and cp['start_frame']==start and cp['end_frame']==start+frames and cp['parent_sha256']==parent
 return cp,sha(raw)
# Two original split-probe jobs embedded in the matrix.
parent=None
for j in range(2):
 receipt=json.loads((out/f'split-{j}-receipt.json').read_text());address=receipt['body']['diagnostic_case']['applied_controls']['sine'][0]['address'];controls=[dict(block=b-j*1125,address=address,value=v) for b,v in full_events if j*1125<=b<(j+1)*1125];sequence=sha((tag+'-split').encode())
 check_receipt(receipt,48000,'sine',controls,sequence,j,j*72000,parent,sha(original[j*288000:(j+1)*288000]),72000)
 cp,parent=cpcheck(out/f'split-{j}-checkpoint.json',receipt,sequence,j,j*72000,72000,parent)
assert cp['state_sha256']==json.loads((out/(tag+'-0-checkpoint.json')).read_text())['state_sha256']
# Three additional replay jobs retaining every sample in all four channels.
arrays={};parent=None
for row in sr['rows']:
 name=row['name'];raw=(sp/(name+'.bin')).read_bytes();assert sha(raw)==row['capture_sha256'];frames=144000 if name=='full' else 72000;assert len(raw)==frames*4*4
 a=struct.unpack('<'+str(frames*4)+'f',raw);assert all(map(math.isfinite,a));arrays[name]=[a[ch*frames:(ch+1)*frames] for ch in range(4)]
 rb=(sp/(name+'-receipt.json')).read_bytes();assert sha(rb)==row['receipt_sha256'];receipt=json.loads(rb);address=receipt['body']['diagnostic_case']['applied_controls']['sine'][0]['address']
 if name=='full':index=0;start=0;sequence=sha(b'presplit-full-replay');rawinput=original;ev=full_events;pa=None
 else:
  index=int(name[-1]);start=index*72000;sequence=sha(b'presplit-parts-replay');rawinput=original[index*288000:(index+1)*288000];ev=[(b-index*1125,v) for b,v in full_events if index*1125<=b<(index+1)*1125];pa=parent
 controls=[dict(block=b,address=address,value=v) for b,v in ev]
 check_receipt(receipt,48000,'sine',controls,sequence,index,start,pa,sha(rawinput),frames)
 cp,cpdigest=cpcheck(sp/(name+'-checkpoint.json'),receipt,sequence,index,start,frames,pa);assert cpdigest==row['checkpoint_sha256']
 if name=='full':fullstate=cp['state_sha256']
 else:parent=cpdigest
assert cp['state_sha256']==fullstate
assert all(arrays['full'][ch]==arrays['part0'][ch]+arrays['part1'][ch] for ch in range(4))
main=struct.unpack('<6750f',(out/(tag+'-0.bin')).read_bytes())
assert tuple(arrays['full'][ch+1][b*64] for b in range(2250) for ch in range(3))==main
assert jobs==149

result=dict(passed=sum(r['passed'] for r in rows),cases=len(rows),bounded_jobs=jobs,reset_rejections=sum(r['reset_rejected'] for r in rows),max_tolerance_ratio=max(r['max_tolerance_ratio'] for r in rows),max_meter_error_db=max(r['max_meter_error_db'] for r in rows),rows=rows,archive_sha256=sha(Path('work/presplit-wasm-evidence.tar.gz').read_bytes()),admission='NOT_GRANTED',split_full_audio_exact=True,split_archive_sha256=sha(splitarchive.read_bytes()))
Path('outputs/blackdog-presplit-wasm-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))

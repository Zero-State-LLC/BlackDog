"""Five chained sandbox jobs, each within the original 144000-frame limit."""
from pathlib import Path
import dataclasses,hashlib,json,math,struct,sys,tempfile
import faustcoder.signal as signal
from faustcoder.compiler import worker_directory,share_directory,node_command
from faustcoder.sandbox import ResourceLimits,run_in_sandbox
from faustcoder.diagnostic_cases import DiagnosticCase,ControlEvent
from faustcoder.signal import SignalProfile
root=Path(__file__).resolve().parent;out=root/'wasm-history';out.mkdir(exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest();source=(root/'switch-precise-live.dsp').read_text();limits=ResourceLimits()
assert sha(source.encode())=='40a1342836429fb8969b6737abf226a2b5ccfe19556d1882c4ced37421c1c515'
def render(mono,rate,stim,events,address,sequence,index,start,checkpoint=None):
 profile=SignalProfile(rate,frames=len(mono),head_frames=len(mono),max_frames=len(mono),block_size=64,stimuli=(stim,),expected_channels=4,press_buttons_first_block=False,diagnostic_case=DiagnosticCase('checkpoint-history',tuple(ControlEvent(b,address,v) for b,v in events),(stim,)))
 request=dict(source=source,options=['-ftz','0'],sample_rate=rate,block_size=64,frames=len(mono),stimuli=[stim],press_buttons_first_block=False,diagnostic_case=profile.diagnostic_case.worker_payload(),history=dict(sequence_id=sequence,chunk_index=index,start_frame=start,parent_sha256=sha(checkpoint) if checkpoint else None))
 with tempfile.TemporaryDirectory(prefix='faust-history-') as tmp:
  wd=Path(tmp);signal._stage_runtime(wd);(wd/'inputs').mkdir();raw=struct.pack('<'+'f'*len(mono),*mono)
  for name in (stim,'channel-0'):(wd/'inputs'/f'{name}.f32').write_bytes(raw)
  if checkpoint:(wd/'checkpoint-in.json').write_bytes(checkpoint)
  worker=worker_directory();libraries=share_directory()
  command=node_command(worker/'history-render.mjs',[str(wd),str(libraries)],read_paths=[worker,wd,libraries],write_paths=[wd],literal_reads=('/proc/net/dev',))
  run=run_in_sandbox(command,stdin=json.dumps(request).encode(),workdir=wd,limits=limits);signal._raise_if_canary_failed(run)
  assert not run.stop_reason and run.returncode==0,(run.stop_reason,run.stderr.decode()[-1500:])
  body=json.loads((wd/'result.json').read_text());assert body['compile_ok'],body
  assert body['faustwasm_version']==signal.FAUSTWASM_VERSION and body['library_tree_sha256']==signal.FAUSTLIBRARIES_SHARE_SHA256
  samples=signal._read_outputs(wd,body,profile)[stim]
  assert len(samples)==4 and samples[0]==tuple(mono) and all(math.isfinite(v) for ch in samples for v in ch)
  assert body['diagnostic_case']['applied_controls'][stim]==request['diagnostic_case']['controls']
  cp=(wd/'checkpoint-out.json').read_bytes();assert sha(cp)==body['history']['checkpoint_sha256']
  receipt=dict(body=body,request_sha256=sha(json.dumps(request).encode()),input_sha256=sha(raw),limits=dataclasses.asdict(limits),sandbox=dataclasses.asdict(run))
  # Sandbox stdout/stderr are bytes; encode them explicitly for the retained record.
  for k,v in list(receipt['sandbox'].items()):
   if isinstance(v,bytes):receipt['sandbox'][k]=v.decode(errors='replace')
  return samples,cp,receipt

def put(name,obj):
 raw=(json.dumps(obj,indent=2,sort_keys=True)+'\n').encode();(out/name).write_bytes(raw);return sha(raw)

def prefix_probe():
 report=json.loads((root/'live-controls-switch-threshold-walk/report.json').read_text());row=next(r for r in report['rows'] if r['rate']==48000);cap=json.loads((root/'live-controls-switch-threshold-walk/48000-sine-capture.json').read_text());events=report['events'];seq=sha(b'split-probe-48000-sine');pieces=[];cp=None
 for i in range(2):
  local=[(b-i*1125,v) for b,v in events if i*1125<=b<(i+1)*1125]
  samples,cp,receipt=render(cap['input'][i*72000:(i+1)*72000],48000,'sine',local,row['control_address'],seq,i,i*72000,cp);pieces.append(samples);put(f'split-probe-{i}-receipt.json',receipt);(out/f'split-probe-{i}-checkpoint.json').write_bytes(cp)
 joined=[list(pieces[0][c])+list(pieces[1][c]) for c in range(4)];assert joined==cap['actual'],'split continuation differs from uninterrupted WASM'
 result=dict(passed=True,comparison='byte-equivalent float32 arrays to prior uninterrupted 144000-frame WASM capture',sample_sha256=signal._sample_digest(joined));put('split-probe.json',result);print('split probe passed',flush=True)

prefix_probe()
if '--probe-only' in sys.argv:sys.exit(0)
rows=[]
for schedule in ('alternating','threshold-walk'):
 basis=json.loads((root/('live-controls-switch-'+schedule)/'report.json').read_text());events=basis['events']
 for rate in (44100,48000,96000,192000):
  address=next(r['control_address'] for r in basis['rows'] if r['rate']==rate)
  for stim in ('noise','impulse','sine'):
   tag=f'{schedule}-{rate}-{stim}';cap=json.loads((root/('live-controls-switch-'+schedule)/f'{rate}-{stim}-capture.json').read_text());native=root/'native-history-soak-fivefold';reference=struct.unpack('<33750f',(native/(tag+'-stock.bin')).read_bytes());reset=struct.unpack('<33750f',(native/(tag+'-reset.bin')).read_bytes());cp=None;values=[];chunks=[];seq=sha(tag.encode())
   for i in range(5):
    samples,cp,receipt=render(cap['input'],rate,stim,events,address,seq,i,i*144000,cp)
    if i==0:assert [list(ch) for ch in samples]==cap['actual'],'opening WASM capture changed'
    compact=[samples[ch+1][b*64] for b in range(2250) for ch in range(3)];values+=compact
    raw=struct.pack('<6750f',*compact);(out/f'{tag}-{i}.bin').write_bytes(raw);(out/f'{tag}-{i}-checkpoint.json').write_bytes(cp);rh=put(f'{tag}-{i}-receipt.json',receipt)
    chunks.append(dict(index=i,capture_sha256=sha(raw),checkpoint_sha256=sha(cp),receipt_sha256=rh,history=receipt['body']['history']))
   ratio=lambda a,b:max(abs(x-y)/(2e-6+1e-5*abs(y)) for x,y in zip(a,b))
   q=ratio(values,reference);n=ratio(values,reset);r=dict(schedule=schedule,rate=rate,stimulus='looped-'+stim,frames=720000,passed=q<=1,reset_rejected=n>1,max_tolerance_ratio=q,reset_ratio=n,max_meter_error_db=max(abs(a-b)*200 for a,b in zip(values,reference)),chunks=chunks);rows.append(r)
   put('report.json',dict(admission='NOT_GRANTED',diagnostic_only=True,source_sha256=sha(source.encode()),runner_sha256=sha(Path(__file__).read_bytes()),checkpoint_module_sha256=sha((worker_directory()/'history-checkpoint.mjs').read_bytes()),worker_sha256=sha((worker_directory()/'history-render.mjs').read_bytes()),base_worker_sha256=sha((worker_directory()/'render.mjs').read_bytes()),runtime_module_sha256=sha((worker_directory()/'node_modules/@grame/faustwasm/dist/esm/index.js').read_bytes()),rows=rows));print(tag,r['passed'],r['reset_rejected'],r['max_meter_error_db'],flush=True)

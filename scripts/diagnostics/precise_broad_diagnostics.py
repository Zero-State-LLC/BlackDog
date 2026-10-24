from pathlib import Path
import dataclasses,hashlib,json,math,struct,sys,traceback
from faustcoder.compiler import compile_native,runtime_pin
from faustcoder.signal import SignalProfile,SignalReference,run_signal,_render,_sample_digest,f32
from faustcoder.diagnostic_cases import DiagnosticCase,ControlEvent,input_buffers
from faustcoder.sandbox import ResourceLimits
from faustcoder.schemas import validate
import faustcoder.signal as signal
from tpt_spectral_reference import tpt_reference
from switching_spectral_reference import switching_reference
mode='switch'
schedule=sys.argv[1]
assert schedule in ('alternating','threshold-walk')
ref_fn=switching_reference
# Both schedules retain the production smoother and the existing 144000-frame cap.
if schedule == 'alternating':
 events=[(i,2000 if i%2==0 else 6000) for i in range(2250)]
else:
 import random
 rng=random.Random(70823)
 values=(2000,6000,2303.99,2304,2304.01,2902.85,2902.86,2902.87,3333.33)
 events=[(0,2000)]+[(i,rng.choice(values)) for i in range(7,2250,7)]
root=Path(__file__).resolve().parent;out=root/('live-controls-'+mode+'-'+schedule);out.mkdir(exist_ok=True)
source=(root/('tpt-live.dsp' if mode=='tpt' else 'switch-precise-live.dsp')).read_text();rows=[]
sha=lambda b:hashlib.sha256(b).hexdigest()
def put(name,obj):
 data=(json.dumps(obj,indent=2,sort_keys=True)+'\n').encode();(out/name).write_bytes(data);return dict(path=name,sha256=sha(data))
original=signal._read_outputs;captured={};descriptors=[]
def capture(*a,**k):
 result=original(*a,**k);descriptors[:]=a[1].get('diagnostic_case',{}).get('descriptors',[]);captured.clear();captured.update(result);return result
signal._read_outputs=capture
c=compile_native(source,options=('-ftz','0'));validate(c.receipt,'compiler-receipt.schema.json');put('native.json',c.receipt);assert c.receipt['exit_code']==0,c.receipt
for rate in map(int,sys.argv[2:] or ['48000']):
 row=dict(rate=rate,runs=[])
 try:
  def profile(stim,controls=()):return SignalProfile(rate,frames=144000,head_frames=144000,max_frames=144000,block_size=64,stimuli=(stim,),noise_amplitude=.125,expected_channels=4,press_buttons_first_block=False,diagnostic_case=DiagnosticCase('paired-'+mode+'-'+schedule,controls,(stim,)))
  probe=_render(source,profile('noise'),options=('-ftz','0'),limits=ResourceLimits());put(str(rate)+'-probe.json',{k:v for k,v in probe.items() if k!='samples'})
  def find(items):
   found=[]
   for d in items:
    if d.get('label')=='cutoff_hz':found.append(d['address'])
    found+=find(d.get('items',[]))
   return found
  addresses=find(descriptors);assert len(addresses)==1,descriptors
  row['control_address']=addresses[0];controls=tuple(ControlEvent(b,addresses[0],v) for b,v in events)
  for stim in ('noise','impulse','sine'):
   tag=str(rate)+'-'+stim;p=profile(stim,controls);x=input_buffers(p)[0]
   wanted=ref_fn(x,rate,events)
   reference=SignalReference(rate,64,144000,p.seed,p.stimuli,4,{stim:wanted})
   result=run_signal(source,p,reference,options=('-ftz','0'));validate(result.receipt,'dsp-test-receipt.schema.json')
   actual=captured[stim];ratio=0.;maxdb=0.;worst=None
   for ch in range(4):
    for frame,(a,r) in enumerate(zip(actual[ch],wanted[ch])):
     assert math.isfinite(a) and math.isfinite(r);err=abs(a-r);q=err/(2e-6+1e-5*abs(r));maxdb=max(maxdb,err*200 if ch else 0)
     if q>ratio:ratio=q;worst=dict(channel=ch,frame=frame,actual=a,reference=r)
   put(tag+'-capture.json',dict(input=x,actual=actual,reference=wanted,sample_sha256=_sample_digest(actual)))
   assert tuple(actual[0])==tuple(x), str([(i,a,b) for i,(a,b) in enumerate(zip(actual[0],x)) if a!=b][:3])
   receipt=put(tag+'-receipt.json',dict(compiler=result.compilation.receipt,signal=result.receipt,signal_digest=result.reproducible_digest,reference=result.reference_payload))
   put(tag+'-capture.json',dict(input=x,actual=actual,reference=wanted,sample_sha256=_sample_digest(actual)))
   frozen=ref_fn(x,rate,events,frozen=True)
   negative=run_signal(source,p,SignalReference(rate,64,144000,p.seed,p.stimuli,4,{stim:frozen}),options=('-ftz','0'))
   validate(negative.receipt,'dsp-test-receipt.schema.json')
   assert _sample_digest(captured[stim])==_sample_digest(actual)
   negative_receipt=put(tag+'-frozen-receipt.json',dict(compiler=negative.compilation.receipt,signal=negative.receipt,signal_digest=negative.reproducible_digest,reference=negative.reference_payload))
   rejected=not negative.receipt['passed'] and any(':reference' in f for f in negative.failures)
   row['runs'].append(dict(stimulus=stim,passed=result.receipt['passed'],frozen_rejected=rejected,negative_receipt=negative_receipt,max_meter_error_db=maxdb,max_tolerance_ratio=ratio,worst=worst,receipt=receipt,failures=list(result.failures)))
  row['status']='DIAGNOSTIC_PASS' if all(r['passed'] and r['frozen_rejected'] for r in row['runs']) else 'DIAGNOSTIC_FAIL'
 except Exception as exc:
  row.update(status='BLOCKED',error=str(exc)[:500]);put(str(rate)+'-error.json',dict(trace=traceback.format_exc()))
 rows.append(row);print(rate,row['status'],row.get('error',''),[(r['stimulus'],r['passed'],r['frozen_rejected'],r['max_meter_error_db']) for r in row['runs']],flush=True)
put('report.json',dict(diagnostic_only=True,admission='NOT_GRANTED',source_sha256=sha(source.encode()),mode=mode,schedule=schedule,events=events,reference_sha256=sha((root/('tpt_spectral_reference.py' if mode=='tpt' else 'switching_spectral_reference.py')).read_bytes()),runner_sha256=sha(Path(__file__).read_bytes()),runtime_pin=dataclasses.asdict(runtime_pin()),worker_sha256=sha((root/'faust/worker/render.mjs').read_bytes()),rows=rows))

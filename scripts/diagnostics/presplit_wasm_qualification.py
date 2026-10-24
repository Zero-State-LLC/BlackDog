"""Nonperiodic cutoff histories using the unchanged bounded checkpoint harness.

Run beside the staged diagnostic fixtures on the isolated qualification host.
"""
from pathlib import Path
import hashlib,json,math,struct,subprocess
root=Path(__file__).resolve().parent
# Reuse only definitions; do not execute the earlier qualification matrix.
harness=root/'wasm_history_qualification.py'
text=harness.read_text(); marker='\nprefix_probe()\n'
assert text.count(marker)==1
definitions=text.split(marker)[0].replace('switch-precise-live.dsp','paired-presplit-coefficients.dsp').replace('40a1342836429fb8969b6737abf226a2b5ccfe19556d1882c4ced37421c1c515','d4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e').replace("'history-render.mjs'","'presplit-render.mjs'")
exec(compile(definitions,str(harness),'exec'))
out=root/'presplit-controls';out.mkdir(exist_ok=True)
# Build the stock-double oracle with global, non-repeating targets.
prior=root/'native-history-soak-fivefold/stock/driver.cpp'
driver=prior.read_text().replace('targets(2250)','targets(11250)').replace('targets[block%2250]','targets[block]')
assert driver!=prior.read_text() and 'targets[block%2250]' not in driver
folder=out/'stock';folder.mkdir(exist_ok=True)
(folder/'generated.hpp').write_bytes((prior.parent/'generated.hpp').read_bytes())
(folder/'driver.cpp').write_text(driver)
# Retain the native harness's original resource limits.
native=root/'native_history_soak.py';ns={"__file__":str(native)}
exec(compile(native.read_text().split("base=(root/")[0],str(native),'exec'),ns)
ns['run'](['g++','-O1','-ffp-contract=off','-fno-fast-math',str(folder/'driver.cpp'),'-o',str(folder/'render')])
schedules={
 'boundary-holds':[(0,2000),(2249,6000),(2251,2304),(4498,2902.86),(4501,2000),(6749,6000),(6750,2304),(6751,2902.86),(8999,2000),(9001,6000),(11249,2000)],
 'chirped-sweep':[(b,round(4000+2000*math.sin(2*math.pi*(b/997+(b/11250)**2*25)),2)) for b in range(11250)]}
put('events.json',schedules);rows=[]
for schedule,events in schedules.items():
 changes=dict(events);target=4000;targets=[]
 for b in range(11250):
  target=changes.get(b,target);targets.append(target)
 control=out/(schedule+'-controls.bin');control.write_bytes(struct.pack('<11250f',*targets))
 for rate in (44100,48000,96000,192000):
  basis=json.loads((root/'live-controls-switch-threshold-walk/report.json').read_text())
  address=next(r['control_address'] for r in basis['rows'] if r['rate']==rate)
  for stim in ('noise','impulse','sine'):
   tag=f'{schedule}-{rate}-{stim}'
   cap=json.loads((root/'live-controls-switch-threshold-walk'/f'{rate}-{stim}-capture.json').read_text())
   inp=out/(tag+'-input.bin');inp.write_bytes(struct.pack('<144000f',*cap['input']))
   ref=out/(tag+'-stock.bin');ms=ns['run']([str(folder/'render'),str(rate),str(inp),str(control),str(ref),'0'])
   reference=struct.unpack('<33750f',ref.read_bytes());values=[];chunks=[];cp=None
   for i in range(5):
    local=[(b-i*2250,v) for b,v in events if i*2250<=b<(i+1)*2250]
    samples,cp,receipt=render(cap['input'],rate,stim,local,address,sha(tag.encode()),i,i*144000,cp)
    if i==0 and schedule=='chirped-sweep' and rate==48000 and stim=='sine':
     parts=[];probe_cp=None
     for j in range(2):
      pe=[(b-j*1125,v) for b,v in local if j*1125<=b<(j+1)*1125]
      ps,probe_cp,pr=render(cap['input'][j*72000:(j+1)*72000],rate,stim,pe,address,sha((tag+'-split').encode()),j,j*72000,probe_cp)
      parts.append(ps);put(f'split-{j}-receipt.json',pr);(out/f'split-{j}-checkpoint.json').write_bytes(probe_cp)
     assert all(parts[0][ch]+parts[1][ch]==samples[ch] for ch in range(4))
     put('split-probe.json',dict(passed=True,sample_sha256=signal._sample_digest(samples),comparison='all four channels exactly equal across uninterrupted 144k and 72k+72k'))
    compact=[samples[ch+1][b*64] for b in range(2250) for ch in range(3)];values+=compact
    raw=struct.pack('<6750f',*compact);(out/f'{tag}-{i}.bin').write_bytes(raw);(out/f'{tag}-{i}-checkpoint.json').write_bytes(cp)
    rh=put(f'{tag}-{i}-receipt.json',receipt)
    chunks.append(dict(index=i,capture_sha256=sha(raw),checkpoint_sha256=sha(cp),receipt_sha256=rh,events=local))
    if i==1:
     reset,_,rr=render(cap['input'],rate,stim,local,address,sha((tag+'-reset').encode()),0,0)
     neg=[reset[ch+1][b*64] for b in range(2250) for ch in range(3)]
     nr=struct.pack('<6750f',*neg);(out/f'{tag}-reset.bin').write_bytes(nr);put(f'{tag}-reset-receipt.json',rr)
     reset_ratio=max(abs(a-b)/(2e-6+1e-5*abs(b)) for a,b in zip(compact,neg))
   q=max(abs(a-b)/(2e-6+1e-5*abs(b)) for a,b in zip(values,reference))
   row=dict(schedule=schedule,rate=rate,stimulus=stim,frames=720000,passed=q<=1,max_tolerance_ratio=q,max_meter_error_db=max(abs(a-b)*200 for a,b in zip(values,reference)),reset_rejected=reset_ratio>1,reset_ratio=reset_ratio,chunks=chunks,reference_sha256=sha(ref.read_bytes()),input_sha256=sha(inp.read_bytes()),controls_sha256=sha(control.read_bytes()),oracle_ms=ms)
   rows.append(row)
   put('report.json',dict(admission='NOT_GRANTED',diagnostic_only=True,source_sha256=sha(source.encode()),runner_sha256=sha(Path(__file__).read_bytes()),harness_sha256=sha(harness.read_bytes()),oracle_driver_sha256=sha(driver.encode()),oracle_header_sha256=sha((folder/'generated.hpp').read_bytes()),rows=rows))
   print(tag,q,reset_ratio,flush=True)

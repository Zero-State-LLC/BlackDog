from pathlib import Path
import hashlib,json,math,resource,struct,subprocess,sys
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root));out=root/'native-long-crosscheck';out.mkdir(exist_ok=True)
from switching_spectral_reference import switching_reference
from faustcoder.signal import SignalProfile
from faustcoder.diagnostic_cases import DiagnosticCase,input_buffers
sha=lambda b:hashlib.sha256(b).hexdigest()
def limits():
 resource.setrlimit(resource.RLIMIT_CPU,(20,20));resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
def run(args):subprocess.run(args,check=True,capture_output=True,timeout=30,preexec_fn=limits)
source=root/'matched-double/live-default-double-48000.dsp';run(['faust','-double','-ftz','0',str(source),'-o',str(out/'generated.hpp')])
base=(root/'matched-double/driver.cpp').read_text();old='if(block==0)target=2000;if(block==8)target=6000;if(block==24)target=2500;if(block==40)target=3333.33f;';assert old in base
rows=[]
for schedule in ('long',):
 events=[(0,2000),(128,6000),(512,2304),(1024,2902.86),(1536,2000)]
 events += [(i,round(2000+4000*(1-abs(((i-1792)//8%32)/16-1)),2)) for i in range(1792,2250,8)]
 for rate in (44100,48000):
  commands=''.join(f'if(block=={b})target={v:.8f}f;' for b,v in events)
  driver=base.replace('block<64','block<2250').replace(old,commands).replace('processor.init(48000)',f'processor.init({rate})');(out/'driver.cpp').write_text(driver);run(['g++','-O2','-ffp-contract=off',str(out/'driver.cpp'),'-o',str(out/'render')])
  for stim in ('sine',):
   p=SignalProfile(rate,frames=144000,head_frames=144000,max_frames=144000,block_size=64,stimuli=(stim,),noise_amplitude=.125,diagnostic_case=DiagnosticCase('switch-reference',(),(stim,)))
   x=input_buffers(p)[0];inp=struct.pack('<'+'f'*len(x),*x);(out/'input.bin').write_bytes(inp);dest=out/(f'{schedule}-{rate}-{stim}.bin');run([str(out/'render'),str(out/'input.bin'),str(dest)])
   data=dest.read_bytes();v=struct.unpack('<'+'d'*(len(data)//8),data);actual=[list(v[i::4]) for i in range(4)];wanted=switching_reference(x,rate,events);assert all(math.isfinite(z) for ch in actual for z in ch)
   diff=max(abs(a-b) for ac,bc in zip(actual,wanted) for a,b in zip(ac,bc));assert diff<1e-7,(schedule,rate,stim,diff)
   rows.append(dict(schedule=schedule,rate=rate,stimulus=stim,max_abs_error=diff,capture_sha256=sha(data),input_sha256=sha(inp),driver_sha256=sha(driver.encode())))
  print(schedule,rate,'reference cross-check passed',flush=True)
(out/'report.json').write_text(json.dumps(dict(source_sha256=sha(source.read_bytes()),header_sha256=sha((out/'generated.hpp').read_bytes()),reference_sha256=sha((root/'switching_spectral_reference.py').read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),rows=rows),indent=2))

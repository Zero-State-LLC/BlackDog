"""Native-only paired TPT rate matrix with unchanged matched cutoff trajectory."""
from pathlib import Path
import hashlib,json,math,resource,struct,subprocess,sys
ROOT=Path(sys.argv[1]).resolve();sys.path.insert(0,str(ROOT))
from faustcoder.signal import SignalProfile
from faustcoder.diagnostic_cases import DiagnosticCase,input_buffers
BASE=ROOT/'tpt-precision-ablation';OUT=ROOT/'tpt-pair-rate-matrix';OUT.mkdir(exist_ok=True)
def limits():
 resource.setrlimit(resource.RLIMIT_CPU,(20,20));resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
def run(args):subprocess.run(args,check=True,capture_output=True,timeout=30,preexec_fn=limits)
def sha(b):return hashlib.sha256(b).hexdigest()
original=(BASE/'driver.cpp').read_text();rows=[]
for rate in (44100,48000,96000,192000):
 refs={}
 for variant in ('double','single','single_paired_filter_and_meter'):
  header=(BASE/(variant+'.hpp')).read_bytes();(OUT/'generated.hpp').write_bytes(header)
  driver=original.replace('processor.init(48000)','processor.init('+str(rate)+')')
  if variant!='double':
   driver=driver.replace('double','float').replace('float row[]={','double row[]={').replace('/200,','/200.0,').replace('/200};','/200.0};')
  (OUT/'driver.cpp').write_text(driver)
  run(['g++','-O2','-ffp-contract=off',str(OUT/'driver.cpp'),'-o',str(OUT/'render')])
  for stim in ('noise','impulse','sine'):
   profile=SignalProfile(rate,frames=4096,head_frames=4096,max_frames=4096,block_size=64,stimuli=(stim,),noise_amplitude=.125,diagnostic_case=DiagnosticCase('native-live',(),(stim,)))
   x=input_buffers(profile)[0];inp=struct.pack('<'+'f'*len(x),*x);(OUT/'input.bin').write_bytes(inp)
   dest=OUT/(str(rate)+'-'+variant+'-'+stim+'.bin');run([str(OUT/'render'),str(OUT/'input.bin'),str(dest)])
   data=dest.read_bytes();values=struct.unpack('<'+'d'*(len(data)//8),data);actual=[list(values[i::4]) for i in range(4)]
   assert len(actual[0])==4096
   assert all(math.isfinite(v) for ch in actual for v in ch)
   assert actual[0]==x
   if variant=='double':refs[stim]=actual
   ref=refs[stim];worst=0;maxdb=0;where=None
   for c in range(4):
    for frame,(a,b) in enumerate(zip(actual[c],ref[c])):
     error=abs(a-b);ratio=error/(2e-6+1e-5*abs(b));maxdb=max(maxdb,error*200 if c else 0)
     if ratio>worst:worst=ratio;where=dict(channel=c,frame=frame,actual=a,reference=b)
   rows.append(dict(rate=rate,variant=variant,stimulus=stim,passed=worst<=1,max_tolerance_ratio=worst,max_meter_error_db=maxdb,worst=where,capture_sha256=sha(data),header_sha256=sha(header),input_sha256=sha(inp),driver_sha256=sha(driver.encode()),float_io=variant!='double'))
  print(rate,variant,[(r['stimulus'],r['passed'],r['max_meter_error_db']) for r in rows if r['rate']==rate and r['variant']==variant],flush=True)
(OUT/'report.json').write_text(json.dumps(dict(diagnostic_only=True,compiler='Faust 2.88.0 generated recurrence; g++ -O2 -ffp-contract=off',frames=4096,block_size=64,script_sha256=sha(Path(__file__).read_bytes()),rows=rows),indent=2))

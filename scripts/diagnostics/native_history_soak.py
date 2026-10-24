"""Bounded native-only five-chunk history qualification; production frame cap unchanged."""
from pathlib import Path
import hashlib,json,math,resource,struct,subprocess,time
root=Path(__file__).resolve().parent;out=root/'native-history-soak-fivefold';out.mkdir(exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
def limits():
 resource.setrlimit(resource.RLIMIT_CPU,(20,20));resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
def run(args):
 t=time.monotonic();r=subprocess.run(args,capture_output=True,timeout=30,preexec_fn=limits)
 if r.returncode:raise RuntimeError((r.returncode,r.stderr.decode()[-1000:]))
 return round((time.monotonic()-t)*1000)
base=(root/'matched-double/driver.cpp').read_text().split('int main(')[0]
body=r'''
int main(int argc,char**argv){
 if(argc!=6)return 2;
 int rate=std::stoi(argv[1]);bool reset=std::stoi(argv[5]);
 if(rate!=44100&&rate!=48000&&rate!=96000&&rate!=192000)return 6;
 std::ifstream in(argv[2],std::ios::binary),controls(argv[3],std::ios::binary);
 std::ofstream out(argv[4],std::ios::binary);
 std::vector<float> pattern(144000),targets(2250);
 in.read((char*)pattern.data(),pattern.size()*4);controls.read((char*)targets.data(),targets.size()*4);
 if(!in||!controls)return 4;
 mydsp processor;processor.init(rate);UI ui;processor.buildUserInterface(&ui);
 if(processor.getNumInputs()!=1||processor.getNumOutputs()!=1||!ui.control||ui.meters.size()!=3)return 3;
 std::sort(ui.meters.begin(),ui.meters.end());float smooth=0;
 for(int block=0;block<11250;block++){
  if(reset&&block>0&&block%2250==0){processor.init(rate);smooth=0;}
  float target=targets[block%2250];SAMPLE input[64],output[64];
  for(int i=0;i<64;i++)input[i]=pattern[(block%2250)*64+i];
  COMPUTE
  for(int i=0;i<64;i++)if(output[i]!=input[i]||!std::isfinite(output[i]))return 7;
  float row[3];for(int i=0;i<3;i++){row[i]=float(*ui.meters[i].second/200);if(!std::isfinite(row[i]))return 8;}
  out.write((char*)row,sizeof(row));
 }
 return out.good()?0:5;
}
'''
float_compute='*ui.control=target;float* ins[]={input};float* outs[]={output};processor.compute(64,ins,outs);'
double_compute='for(int i=0;i<64;i++){smooth=0.99f*smooth+0.01f*(target-4000.f);*ui.control=std::min(6000.f,std::max(2000.f,4000.f+smooth));double* ins[]={input+i};double* outs[]={output+i};processor.compute(1,ins,outs);}'
builds={}
for mode,source,flag,compute in [('paired',root/'switch-precise-live.dsp','-single',float_compute),('stock',root/'matched-double/live-default-double-48000.dsp','-double',double_compute)]:
 folder=out/mode;folder.mkdir(exist_ok=True)
 run(['faust',flag,'-ftz','0',str(source),'-o',str(folder/'generated.hpp')])
 pre=base.replace('double','float') if mode=='paired' else base
 driver='#include <cmath>\n'+pre+body.replace('SAMPLE','float' if mode=='paired' else 'double').replace('COMPUTE',compute)
 (folder/'driver.cpp').write_text(driver);ms=run(['g++','-O1','-ffp-contract=off','-fno-fast-math',str(folder/'driver.cpp'),'-o',str(folder/'render')])
 builds[mode]=dict(source_sha256=sha(source.read_bytes()),header_sha256=sha((folder/'generated.hpp').read_bytes()),driver_sha256=sha(driver.encode()),binary_sha256=sha((folder/'render').read_bytes()),compile_ms=ms)
events=json.loads((root/'broad-control-events.json').read_text());rows=[]
for schedule in ('alternating','threshold-walk'):
 targets=[];changes=dict(events[schedule]);value=4000
 for block in range(2250):
  value=changes.get(block,value);targets.append(value)
 controls=out/(schedule+'-controls.bin');controls.write_bytes(struct.pack('<2250f',*targets))
 for rate in (44100,48000,96000,192000):
  for stim in ('noise','impulse','sine'):
   tag=f'{schedule}-{rate}-{stim}'
   cap=json.loads((root/('live-controls-switch-'+schedule)/(f'{rate}-{stim}-capture.json')).read_text())
   inp=out/(tag+'-input.bin');inp.write_bytes(struct.pack('<144000f',*cap['input']))
   results={};timings={};digests={}
   for mode,reset,label in [('paired',0,'paired'),('stock',0,'stock'),('paired',1,'reset')]:
    dest=out/(tag+'-'+label+'.bin');timings[label]=run([str(out/mode/'render'),str(rate),str(inp),str(controls),str(dest),str(reset)])
    b=dest.read_bytes();assert len(b)==11250*3*4;results[label]=struct.unpack('<33750f',b);digests[label]=sha(b)
   actual,reference,reset=(results[k] for k in ('paired','stock','reset'))
   ratios=[abs(a-b)/(2e-6+1e-5*abs(b)) for a,b in zip(actual,reference)];idx=max(range(len(ratios)),key=ratios.__getitem__)
   prefix=[cap['actual'][ch+1][block*64] for block in range(2250) for ch in range(3)]
   prefix_ratio=max(abs(a-b)/(2e-6+1e-5*abs(b)) for a,b in zip(actual,prefix))
   reset_ratio=max(abs(a-b)/(2e-6+1e-5*abs(b)) for a,b in zip(actual,reset))
   row=dict(schedule=schedule,rate=rate,stimulus='looped-'+stim,frames=720000,seconds=720000/rate,passed=max(ratios)<=1,prefix_wasm_passed=prefix_ratio<=1,prefix_wasm_ratio=prefix_ratio,reset_rejected=reset_ratio>1,reset_ratio=reset_ratio,max_tolerance_ratio=max(ratios),max_meter_error_db=max(abs(a-b)*200 for a,b in zip(actual,reference)),worst=dict(block=idx//3,channel=idx%3,actual=actual[idx],reference=reference[idx]),capture_sha256=digests,input_sha256=sha(inp.read_bytes()),controls_sha256=sha(controls.read_bytes()),render_ms=timings)
   rows.append(row);print(tag,row['passed'],row['prefix_wasm_passed'],row['reset_rejected'],row['max_meter_error_db'],flush=True)
   (out/'report.json').write_text(json.dumps(dict(diagnostic_only=True,backend='native float32; separate from production WASM frame-limited admission',admission='NOT_GRANTED',builds=builds,runner_sha256=sha(Path(__file__).read_bytes()),events_sha256=sha((root/'broad-control-events.json').read_bytes()),rows=rows),indent=2)+'\n')

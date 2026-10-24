from pathlib import Path
import sys,json,hashlib,struct,math
root=Path(__file__).resolve().parent
sys.argv=['qualify_designing_closures.py','bouncing-ball'];ns={'__file__':str(root/'qualify_designing_closures.py')};exec((root/'qualify_designing_closures.py').read_text().split('rows=[]')[0],ns);run=ns['run'];out=root/'bouncing-rate-repair';out.mkdir(exist_ok=True);sha=lambda b:hashlib.sha256(b).hexdigest()
original=(root/'bouncing-ball-closed.dsp').read_text();old='int(48000.0 / max(rate, 0.5))';assert original.count(old)==1
fixed=original.replace(old,'int(ma.SR / max(rate, 0.5))');(out/'fixed-closed.dsp').write_text(fixed)
base=ns['base'].replace('void addHorizontalSlider(const char*,float* p,float,float,float,float){control=p;}','void addHorizontalSlider(const char* name,float* p,float,float,float,float){if(std::string(name).find("rate")==0)control=p;}')
rows=[]
for variant,full in [('original',original),('fixed',fixed)]:
 d=out/variant;d.mkdir(exist_ok=True);source=full.replace('process = impact * gain <: _, _;','process = trig <: _, _;');(d/'probe.dsp').write_text(source)
 run(['faust','-single','-ftz','0','-cn','Probe',str(d/'probe.dsp'),'-o',str(d/'generated.hpp')])
 driver=base+'''\n#include "generated.hpp"
int main(int argc,char**argv){if(argc!=5)return 2;Probe dsp;dsp.init(std::stoi(argv[1]));UI ui;dsp.buildUserInterface(&ui);if(!ui.control||dsp.getNumInputs()!=0||dsp.getNumOutputs()!=2)return 3;*ui.control=std::stof(argv[2]);int frames=std::stoi(argv[3]);std::ofstream out(argv[4],std::ios::binary);float pair[2];float* outputs[]={pair,pair+1};for(int i=0;i<frames;i++){dsp.compute(1,nullptr,outputs);out.write((char*)pair,8);}return out.good()?0:4;}
'''
 (d/'driver.cpp').write_text(driver);run(['g++','-O1','-ffp-contract=off','-fno-fast-math',str(d/'driver.cpp'),'-o',str(d/'render')])
 for sr in (44100,48000,96000,192000):
  for control in (.5,4.,7.3,15.):
   c=struct.unpack('<f',struct.pack('<f',control))[0];expected=int((sr if variant=='fixed' else 48000)/c);frames=2*max(int(sr/c),int(48000/c))+2;path=d/(str(sr)+'-'+str(control)+'.bin');run([str(d/'render'),str(sr),str(control),str(frames),str(path)]);raw=path.read_bytes();assert len(raw)==frames*8;values=list(struct.iter_unpack('<ff',raw));assert all(a==b and a in (0.,1.) for a,b in values);positions=[i for i,(a,b) in enumerate(values) if a>0];intervals={b-a for a,b in zip(positions,positions[1:])};assert len(positions)>=2 and intervals=={expected},(variant,sr,c,positions,expected);matched=abs(expected-sr/c)<1.;assert matched==(variant=='fixed' or sr==48000)
   rows.append(dict(variant=variant,sample_rate=sr,requested_rate=control,float32_control=c,frames=frames,interval=expected,observed_hz=sr/expected,ideal_period_frames=sr/c,rate_contract_pass=matched,capture_sha256=sha(raw),positions=positions,probe_source_sha256=sha(source.encode())))
r=dict(status='BOUNDED_RATE_REPAIR_PASS',original_closed_sha256=sha(original.encode()),fixed_closed_sha256=sha(fixed.encode()),change='Replace fixed 48000 divisor with existing ma.SR; no new dependency',rows=rows,runner_sha256=sha(Path(__file__).read_bytes()),scope='Static controls .5,4,7.3,15 Hz at four sample rates; interval within one sample of ideal; derivative trigger output',admission='NOT_GRANTED',limitations=['No live-control history guarantee','Original source identity preserved separately; repaired variant is a different target/context','Does not resolve teacher provenance, full audio semantics or family independence'])
(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print('16 repaired cases pass; 12 off-48k original cases reject; four 48k controls pass')

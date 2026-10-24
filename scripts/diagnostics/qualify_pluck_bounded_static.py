from pathlib import Path
import sys,json,hashlib,struct,math
root=Path(__file__).resolve().parent;sys.argv=['qualify_designing_closures.py','bitcrush'];ns={'__file__':str(root/'qualify_designing_closures.py')};exec((root/'qualify_designing_closures.py').read_text().split('rows=[]')[0],ns);run=ns['run'];sha=lambda b:hashlib.sha256(b).hexdigest();out=root/'pluck-bounded-static-check';out.mkdir(exist_ok=True)
source=root/'pluck-bounded-epoch.dsp';run(['faust','-single','-ftz','0','-cn','Probe',str(source),'-o',str(out/'generated.hpp')])
base=ns['base'].replace('float* control=nullptr;', 'float* control=nullptr; float* gate=nullptr; float* freq=nullptr; float* gain=nullptr; void addButton(const char*,float* p){gate=p;}')
base=base.replace('void addHorizontalSlider(const char*,float* p,float,float,float,float){control=p;}','void addHorizontalSlider(const char* name,float* p,float,float,float,float){if(std::string(name)=="freq")freq=p;if(std::string(name)=="gain")gain=p;}')
driver=base+'''\n#include "generated.hpp"
int main(int argc,char**argv){if(argc!=6)return 2;int sr=std::stoi(argv[1]);Probe dsp;dsp.init(sr);UI ui;dsp.buildUserInterface(&ui);if(dsp.getNumInputs()!=0||dsp.getNumOutputs()!=2||!ui.gate||!ui.freq||!ui.gain)return 3;*ui.freq=std::stof(argv[2]);*ui.gain=std::stof(argv[3]);int mode=std::stoi(argv[4]);std::ofstream out(argv[5],std::ios::binary);float pair[2];float* outs[]={pair,pair+1};for(int i=0;i<2*sr;i++){*ui.gate=mode?((i>=1&&i<sr/2)||(i>=sr&&i<3*sr/2)):0;dsp.compute(1,nullptr,outs);out.write((char*)pair,8);}return out.good()?0:4;}
'''
(out/'driver.cpp').write_text(driver);run(['g++','-O1','-ffp-contract=off','-fno-fast-math',str(out/'driver.cpp'),'-o',str(out/'render')]);rows=[]
for sr in (44100,48000,96000,192000):
 for f,g,mode in [(f,.5,1) for f in (20,50,110,440,1000,4000,8000)]+[(110,.25,1),(110,0.,1),(110,.5,0)]:
  path=out/(f'{sr}-{f}-{g}-{mode}.bin');run([str(out/'render'),str(sr),str(f),str(g),str(mode),str(path)]);raw=path.read_bytes();assert len(raw)==sr*16;pairs=list(struct.iter_unpack('<ff',raw));assert all(a==b and math.isfinite(a) for a,b in pairs);peak=max(abs(a) for a,b in pairs);assert (peak>0)==bool(g and mode);assert pairs[0]==(0.,0.)
  rows.append(dict(sample_rate=sr,frequency=f,gain=g,gate_mode=mode,frames=sr*2,file=path.name,sha256=sha(raw),peak=peak))
 a=list(struct.iter_unpack('<f',(out/f'{sr}-110-0.5-1.bin').read_bytes()));b=list(struct.iter_unpack('<f',(out/f'{sr}-110-0.25-1.bin').read_bytes()));assert all(struct.unpack('<f',struct.pack('<f',x[0]*.5))[0]==y[0] for x,y in zip(a,b))
(out/'report.json').write_text(json.dumps(dict(status='BOUNDED_ZERO_INPUT_REPAIR_PASS',source_sha256=sha(source.read_bytes()),runner_sha256=sha(Path(__file__).read_bytes()),rows=rows,gain_linearity='float32-rounded half amplitude at110Hz across four rates',scope='two-second two-gate histories; seven static frequencies including original endpoints; native single precision only',admission='NOT_GRANTED'),indent=2)+'\n');print('40 cases pass; zero-input stereo, silence controls, gate retrigger histories and gain linearity')

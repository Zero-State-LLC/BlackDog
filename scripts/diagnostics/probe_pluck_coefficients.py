from pathlib import Path
import sys,json,struct,hashlib
root=Path(__file__).resolve().parent;sys.argv=['qualify_designing_closures.py','bitcrush'];ns={'__file__':str(root/'qualify_designing_closures.py')};exec((root/'qualify_designing_closures.py').read_text().split('rows=[]')[0],ns);run=ns['run'];out=root/'pluck-coefficient-check';out.mkdir(exist_ok=True)
s=(root/'pluck-single-loop.dsp').read_text();s=s.replace('pluck(f)=(+ : @(n) : ap(a)) ~ (mean * 0.998)','pluck(f)=n,a');s=s.replace('process=impulse(gate) : pluck(freq) : *(gain) <: _,_;','process=pluck(freq);');(out/'probe.dsp').write_text(s);run(['faust','-single','-ftz','0','-cn','Probe',str(out/'probe.dsp'),'-o',str(out/'generated.hpp')])
base=ns['base'];driver=base+'''\n#include "generated.hpp"
int main(int argc,char**argv){if(argc!=4)return 2;Probe dsp;dsp.init(std::stoi(argv[1]));UI ui;dsp.buildUserInterface(&ui);if(!ui.control||dsp.getNumInputs()!=0||dsp.getNumOutputs()!=2)return 3;*ui.control=std::stof(argv[2]);float pair[2];float* outs[]={pair,pair+1};dsp.compute(1,nullptr,outs);std::ofstream out(argv[3],std::ios::binary);out.write((char*)pair,8);return out.good()?0:4;}
''';(out/'driver.cpp').write_text(driver);run(['g++','-O1','-ffp-contract=off','-fno-fast-math',str(out/'driver.cpp'),'-o',str(out/'render')]);rows=[]
for sr in (44100,48000,96000,192000):
 for f in (20,50,110,440,1000,4000,8000):
  p=out/f'{sr}-{f}.bin';run([str(out/'render'),str(sr),str(f),str(p)]);n,a=struct.unpack('<ff',p.read_bytes());rows.append(dict(sample_rate=sr,frequency=f,n=n,a=a,capture_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(out/'report.json').write_text(json.dumps(dict(rows=rows,source_sha256=hashlib.sha256((root/'pluck-single-loop.dsp').read_bytes()).hexdigest(),probe_sha256=hashlib.sha256(s.encode()).hexdigest()),indent=2)+'\n')

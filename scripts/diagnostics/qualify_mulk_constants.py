"""Bounded native probe of every pinned prototype coefficient and its negation."""
from pathlib import Path
import hashlib,json,re,struct,math
root=Path(__file__).resolve().parent;p=root/'mulk-constants';p.mkdir(exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
source=(root/'paired-presplit-coefficients.dsp').read_text();assert sha(source.encode())=='d4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e'
ns={'__file__':str(root/'native_history_soak.py')};exec((root/'native_history_soak.py').read_text().split('base=(root/')[0],ns)
coeff=[]
for line in source.splitlines():
 if line.startswith(('dflp(','dfhp(')):
  for arg in re.findall(r'dfsection\(fh,fl,([^)]*)\)',line):
   nums=list(map(float,arg.split(',')));assert len(nums)==16;coeff.extend(tuple(nums[i:i+4]) for i in range(0,16,4))
coeff=sorted(set(coeff)|{tuple(-v for v in c) for c in coeff});assert len(coeff)==42
f=lambda x:struct.unpack('<f',struct.pack('<f',x))[0]
inputs=[]
for sign in (-1,1):
 for e in range(-20,21):
  for m in (1.,1.125,1.5,1.875):
   c=f(sign*math.ldexp(m,e));ulp=math.ldexp(1.,e-23)
   for l in (-.5,0.,.5):inputs.append((c,f(l*ulp)))
(p/'inputs.bin').write_bytes(b''.join(struct.pack('<ff',*x) for x in inputs))
base=(root/'native-history-soak-fivefold/paired/driver.cpp').read_text().split('#include "generated.hpp"')[0]
rows=[]
for batch in range(6):
 cs=coeff[batch*7:(batch+1)*7]
 for variant in ('exact','bad-split','omit-cross'):
  name=f'b{batch}-{variant}';body=source.rsplit('process =',1)[0]
  if variant=='omit-cross':
   old='r(r(ah*cl)+r(al*ch))';assert body.count(old)==1;body=body.replace(old,'0.0')
  calls=[]
  for ah,al,hi,lo in cs:
   if variant=='bad-split':hi,lo=ah,0.
   calls.append('ds.mulk('+','.join(format(v,'.17g') for v in (ah,al,hi,lo))+',c,d)')
  body+='probe(c,d)='+','.join(calls)+';\nprocess=probe;\n';src=p/(name+'.dsp');src.write_text(body)
  compilems=ns['run'](['faust','-single','-ftz','0','-cn','Probe',str(src),'-o',str(p/'generated.hpp')])
  driver=base+'''\n#include "generated.hpp"
int main(int argc,char** argv){if(argc!=3)return 2;Probe dsp;dsp.init(48000);if(dsp.getNumInputs()!=2||dsp.getNumOutputs()!=14)return 3;std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);float pair[2],result[14];float* inputs[]={pair,pair+1};float* outputs[14];for(int i=0;i<14;i++)outputs[i]=result+i;while(in.read((char*)pair,8)){dsp.compute(1,inputs,outputs);out.write((char*)result,56);}return out.good()?0:4;}\n'''
  (p/'driver.cpp').write_text(driver);gccms=ns['run'](['g++','-O1','-ffp-contract=off','-fno-fast-math',str(p/'driver.cpp'),'-o',str(p/'render')]);capture=p/(name+'.bin');runms=ns['run']([str(p/'render'),str(p/'inputs.bin'),str(capture)])
  values=struct.unpack('<'+str(len(inputs)*14)+'f',capture.read_bytes());assert all(map(math.isfinite,values));errors=[]
  for i,(c,d) in enumerate(inputs):
   for j,(ah,al,_,_) in enumerate(cs):
    ref=(ah+al)*(c+d);actual=values[i*14+2*j]+values[i*14+2*j+1];errors.append(abs(actual-ref)/(1e-30+1e-12*abs(ref)))
  q=max(errors);rows.append(dict(batch=batch,variant=variant,coefficients=cs,samples=len(inputs),ratio=q,passed=q<=1,source_sha256=sha(body.encode()),capture_sha256=sha(capture.read_bytes()),compile_ms=compilems,gcc_ms=gccms,run_ms=runms));print(name,q,flush=True)
(p/'report.json').write_text(json.dumps(dict(rows=rows,coefficient_count=len(coeff),input_count=len(inputs),source_sha256=sha(source.encode()),input_sha256=sha((p/'inputs.bin').read_bytes()),runner_sha256=sha(Path(__file__).read_bytes()),admission='NOT_GRANTED',scope='finite signed normalized pairs, exponent -20..20; 1e-30 absolute + 1e-12 relative product probe only'),indent=2)+'\n')

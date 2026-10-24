from pathlib import Path
import sys,subprocess,resource,json,hashlib,time,struct,math
kind=sys.argv[1];assert kind in ('bitcrush','bouncing-ball')
root=Path(__file__).resolve().parent;out=root/('designing-'+kind+'-check');out.mkdir(exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
def limits():
 resource.setrlimit(resource.RLIMIT_CPU,(20,20));resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
def run(args,expect=True):
 t=time.monotonic();r=subprocess.run(args,capture_output=True,timeout=30,preexec_fn=limits)
 if expect and r.returncode:raise RuntimeError(r.stderr.decode()[:3000])
 return {'returncode':r.returncode,'stderr':r.stderr.decode()[:3000],'elapsed_ms':round((time.monotonic()-t)*1000)}
base=(root/'native-history-soak-fivefold/paired/driver.cpp').read_text().split('#include "generated.hpp"')[0]
rows=[]
for variant,filename in [('original',kind+'.dsp'),('closed',kind+'-closed.dsp')]:
 d=out/variant;d.mkdir(exist_ok=True);source=(root/filename).read_bytes()
 row={'variant':variant,'source_sha256':sha(source)}
 row['compile']=run(['faust','-single','-ftz','0','-I','/home/delphi/BlackDog/faust/libraries/2edec0537f53','-cn','Probe',str(root/filename),'-o',str(d/'generated.hpp')])
 driver=base+'''\n#include "generated.hpp"
int main(int argc,char**argv){if(argc!=3)return 2;Probe dsp;dsp.init(std::stoi(argv[1]));if(dsp.getNumInputs()!=0||dsp.getNumOutputs()!=2)return 3;std::ofstream out(argv[2],std::ios::binary);float pair[2];float* outputs[]={pair,pair+1};for(int i=0;i<24000;i++){dsp.compute(1,nullptr,outputs);out.write((char*)pair,8);}return out.good()?0:4;}
'''
 (d/'driver.cpp').write_text(driver);row['gcc']=run(['g++','-O1','-ffp-contract=off','-fno-fast-math',str(d/'driver.cpp'),'-o',str(d/'render')]);row['header_sha256']=sha((d/'generated.hpp').read_bytes());row['captures']=[]
 for rate in (44100,48000,96000,192000):
  path=d/(str(rate)+'.bin');timing=run([str(d/'render'),str(rate),str(path)]);raw=path.read_bytes();assert len(raw)==24000*8;assert all(math.isfinite(x[0]) for x in struct.iter_unpack('<f',raw));row['captures'].append({'rate':rate,'frames':24000,'sha256':sha(raw),'run':timing})
 rows.append(row)
for rate in (44100,48000,96000,192000):assert (out/'original'/f'{rate}.bin').read_bytes()==(out/'closed'/f'{rate}.bin').read_bytes(),rate
source=(root/(kind+'-closed.dsp')).read_text();assert source.count('PI = 3.14159265358979323846;')==1
negative=out/'omit-pi.dsp';negative.write_text(source.replace('PI = 3.14159265358979323846;',''))
neg=run(['faust','-single','-ftz','0',str(negative),'-o',str(out/'negative.hpp')],False);assert neg['returncode']!=0
result={'status':'COMPILE_AND_DEFAULT_AUDIO_EQUIVALENCE_PASS','rows':rows,'negative_omit_pi':neg,'sample_rates':[44100,48000,96000,192000],'frames_per_rate':24000,'exact_audio_equal':True,'runner_sha256':sha(Path(__file__).read_bytes()),'limits':'20 CPU seconds, 1 GiB AS, 16 MiB file, 30 seconds wall per child','admission':'NOT_GRANTED','scope':'Default controls only; not all live controls or arbitrary library versions'}
(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

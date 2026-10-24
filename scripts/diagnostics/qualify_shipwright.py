from pathlib import Path
import sys,json,hashlib,struct,math,re
root=Path(__file__).resolve().parent
sys.argv=['qualify_designing_closures.py','bitcrush'];ns={'__file__':str(root/'qualify_designing_closures.py')};exec((root/'qualify_designing_closures.py').read_text().split('rows=[]')[0],ns);run=ns['run'];sha=lambda b:hashlib.sha256(b).hexdigest()
base=ns['base'];base=base.replace('float* control=nullptr;','float* control=nullptr; float* gate=nullptr; void addButton(const char*,float* p){gate=p;} void addCheckButton(const char*,float* p){gate=p;}')
out=root/'shipwright-check';out.mkdir(exist_ok=True);results=[]
for name in ('saw_lead','soft_pad','sub_bass','pluck','reverb'):
 result={'candidate':name,'variants':[],'admission':'NOT_GRANTED'}
 for variant in ('original','closed'):
  d=out/name/variant;d.mkdir(parents=True,exist_ok=True);source=root/('shipwright-'+name+('-closed' if variant=='closed' else '')+'.dsp');row={'variant':variant,'source_sha256':sha(source.read_bytes())};result['variants'].append(row)
  row['compile']=run(['faust','-single','-ftz','0','-I','/home/delphi/BlackDog/faust/libraries/2edec0537f53','-cn','Probe',str(source),'-o',str(d/'generated.hpp')],False)
  if row['compile']['returncode']:continue
  header=(d/'generated.hpp').read_text();row['inputs']=int(re.search(r'getNumInputs\(\)\s*\{\s*return (\d+)',header)[1]);row['outputs']=int(re.search(r'getNumOutputs\(\)\s*\{\s*return (\d+)',header)[1])
  driver=base+'''\n#include "generated.hpp"
int main(int argc,char**argv){if(argc!=3)return 2;Probe dsp;dsp.init(std::stoi(argv[1]));UI ui;dsp.buildUserInterface(&ui);int n=dsp.getNumInputs();if((n<0||n>2)||dsp.getNumOutputs()!=2)return 3;std::ofstream out(argv[2],std::ios::binary);float pair[2],in[2];float* ins[]={in,in+1};float* outs[]={pair,pair+1};for(int i=0;i<24000;i++){if(ui.gate)*ui.gate=(i>=1&&i<12000)?1.f:0.f;in[0]=(i==0?1.f:0.f)+.1f*std::sin(i*.031f);in[1]=.1f*std::sin(i*.043f);dsp.compute(1,n?ins:nullptr,outs);out.write((char*)pair,8);}return out.good()?0:4;}
'''
  (d/'driver.cpp').write_text(driver);row['gcc']=run(['g++','-O1','-ffp-contract=off','-fno-fast-math',str(d/'driver.cpp'),'-o',str(d/'render')],False)
  if row['gcc']['returncode']:continue
  row['captures']=[]
  for rate in (44100,48000,96000,192000):
   path=d/(str(rate)+'.bin');timing=run([str(d/'render'),str(rate),str(path)],False)
   if timing['returncode']:
    row['runtime_failure']=timing;break
   raw=path.read_bytes();vals=[x[0] for x in struct.iter_unpack('<f',raw)];assert len(raw)==192000 and all(map(math.isfinite,vals)) and max(map(abs,vals))>0
   row['captures'].append(dict(rate=rate,sha256=sha(raw),peak=max(map(abs,vals))))
 if all(len(r.get('captures',[]))==4 for r in result['variants']):
  for rate in (44100,48000,96000,192000):assert (out/name/'original'/f'{rate}.bin').read_bytes()==(out/name/'closed'/f'{rate}.bin').read_bytes()
  result['status']='BOUNDED_AUDIO_EQUIVALENCE_PASS'
 else:result['status']='COMPILE_OR_INTERFACE_BLOCKED'
 source=(root/('shipwright-'+name+'-closed.dsp')).read_text();assert source.count('pl = environment {')==1
 neg=out/name/'missing-platform.dsp';neg.write_text(source.replace('pl = environment {','missing_pl = environment {'))
 result['negative_missing_platform']=run(['faust','-single','-ftz','0',str(neg),'-o',str(out/name/'negative.hpp')],False);assert result['negative_missing_platform']['returncode']!=0
 result['instrument_interface_pass']=all(r.get('inputs')==(2 if name=='reverb' else 0) and r.get('outputs')==2 for r in result['variants'])
 results.append(result)
(out/'report.json').write_text(json.dumps(dict(rows=results,runner_sha256=sha(Path(__file__).read_bytes()),scope='24000 frames, four sample rates; default sliders, gate on frame1/off12000; reverb impulse plus deterministic sine input; single/ftz0; native only'),indent=2)+'\n');print([(r['candidate'],r['status']) for r in results])

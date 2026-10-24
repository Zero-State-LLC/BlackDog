from pathlib import Path
import json,struct,hashlib
root=Path(__file__).resolve().parent;p=root/'presplit-modular-native';p.mkdir(exist_ok=True)
ns={'__file__':str(root/'native_history_soak.py')};exec((root/'native_history_soak.py').read_text().split('base=(root/')[0],ns)
source=(root/'paired-presplit-coefficients.dsp').read_text().rsplit('process =',1)[0]
for name,process in [('HP','ds.hp'),('LP','ds.lp'),('Meter','ds.meter(0)')]:
 src=p/(name+'.dsp');src.write_text(source+'process = '+process+';\n');print('faust',name,ns['run'](['faust','-single','-ftz','0','-cn',name,str(src),'-o',str(p/(name+'.hpp'))]),flush=True)
base=(root/'native-history-soak-fivefold/paired/driver.cpp').read_text().split('#include "generated.hpp"')[0]
body=r'''
#include "HP.hpp"
#include "LP.hpp"
#include "Meter.hpp"
template<class T> void filter(T& dsp,float h,float l,float a,float b,float* result){
 float* ins[]={&h,&l,&a,&b};float* outs[]={result,result+1};dsp.compute(1,ins,outs);
}
int main(int argc,char**argv){
 if(argc!=5)return 2;int rate=std::stoi(argv[1]);
 std::ifstream in(argv[2],std::ios::binary),controls(argv[3],std::ios::binary);std::ofstream out(argv[4],std::ios::binary);
 std::vector<float> pattern(144000),targets(11250);in.read((char*)pattern.data(),576000);controls.read((char*)targets.data(),45000);if(!in||!controls)return 4;
 HP topHP,lowerHP;LP topLP,lowerLP;Meter meters[3];UI uis[3];
 topHP.init(rate);lowerHP.init(rate);topLP.init(rate);lowerLP.init(rate);
 for(int j=0;j<3;j++){meters[j].init(rate);meters[j].buildUserInterface(&uis[j]);if(uis[j].meters.size()!=1)return 3;}
 if(topHP.getNumInputs()!=4||topHP.getNumOutputs()!=2)return 5;
 float smooth=0;
 for(int block=0;block<11250;block++){
  for(int i=0;i<64;i++){
   smooth=0.99f*smooth+0.01f*(targets[block]-4000.f);float fc=std::min(6000.f,std::max(2000.f,4000.f+smooth));
   double low=double(fc)*std::pow(2.,-1./3.);float lh=float(low),ll=float(low-double(lh));
   float high[2],base[2],mid[2],bottom[2];float value=pattern[(block%2250)*64+i];
   filter(topHP,fc,0,value,0,high);filter(topLP,fc,0,value,0,base);
   filter(lowerHP,lh,ll,base[0],base[1],mid);filter(lowerLP,lh,ll,base[0],base[1],bottom);
   float* bands[]={bottom,mid,high};
   for(int j=0;j<3;j++){float v=0;float* ins[]={bands[j],bands[j]+1};float* outs[]={&v};meters[j].compute(1,ins,outs);if(!std::isfinite(v))return 7;}
  }
  float row[3];for(int j=0;j<3;j++)row[j]=*uis[j].meters[0].second/200.f;out.write((char*)row,12);
 }
 return out.good()?0:8;
}
'''
(p/'driver.cpp').write_text(base+body);print('g++',ns['run'](['g++','-O1','-ffp-contract=off','-fno-fast-math',str(p/'driver.cpp'),'-o',str(p/'render')]),flush=True)
rows=[]
for rate in (44100,48000):
 tag=f'chirped-sweep-{rate}-sine';dest=p/(tag+'.bin');ms=ns['run']([str(p/'render'),str(rate),str(root/'checkpoint-controls'/(tag+'-input.bin')),str(root/'checkpoint-controls/chirped-sweep-controls.bin'),str(dest)]);a=struct.unpack('<33750f',dest.read_bytes());b=struct.unpack('<33750f',(root/'checkpoint-controls'/(tag+'-stock.bin')).read_bytes());q=max(abs(x-y)/(2e-6+1e-5*abs(y)) for x,y in zip(a,b));rows.append(dict(rate=rate,ratio=q,passed=q<=1,ms=ms));print(rows[-1],flush=True);(p/'report.json').write_text(json.dumps(rows,indent=2))

from pathlib import Path
import json
ns={'__file__':str(Path('native_history_soak.py').resolve())};exec(Path('native_history_soak.py').read_text().split('base=(root/')[0],ns)
p=Path('crossover-coefficient-probe');p.mkdir(exist_ok=True)
s=Path('paired-crossover-live.dsp').read_text().rsplit('process =',1)[0]+'process = ds.cot;\n';(p/'probe.dsp').write_text(s);ns['run'](['faust','-single','-ftz','0',str(p/'probe.dsp'),'-o',str(p/'generated.hpp')])
base=Path('native-history-soak-fivefold/paired/driver.cpp').read_text().split('int main(')[0]
body=r'''
#include <iostream>
#include <iomanip>
int main(){for(int rate:{44100,48000,96000,192000}){mydsp p;p.init(rate);double worst=0,wh=0,wl=0,wa=0,wb=0;for(int i=0;i<=10000;i++){double value=(2000.+i*.4)*std::pow(2.,-1./3.);float h=value,l=value-double(h),a=0,b=0;float* in[]={&h,&l};float* out[]={&a,&b};p.compute(1,in,out);double actual=double(a)+b,reference=1/std::tan(std::acos(-1.)*(double(h)+l)/rate);double err=std::abs(actual-reference)/reference;if(err>worst){worst=err;wh=h;wl=l;wa=actual;wb=reference;}}std::cout<<std::setprecision(17)<<rate<<" "<<worst<<" "<<wh<<" "<<wl<<" "<<wa<<" "<<wb<<"\n";}}
'''
(p/'driver.cpp').write_text(base+body);ns['run'](['g++','-O1','-ffp-contract=off','-fno-fast-math',str(p/'driver.cpp'),'-o',str(p/'render')])
import subprocess
r=subprocess.run([str(p/'render')],capture_output=True,text=True,timeout=30,preexec_fn=ns['limits']);assert r.returncode==0;(p/'result.txt').write_text(r.stdout);print(r.stdout)

from pathlib import Path
import json,subprocess
root=Path(__file__).resolve().parent;p=root/'static-split-probe';p.mkdir(exist_ok=True)
ns={'__file__':str(root/'native_history_soak.py')};exec((root/'native_history_soak.py').read_text().split('base=(root/')[0],ns)
s=(root/'paired-presplit-coefficients.dsp').read_text().rsplit('process =',1)[0]
for name,process in [('Static','probe(c,d)=ds.mul(0.7824130654335022,-1.8611856944517058e-08,c,d);process=probe;'),('Dynamic','process=ds.mul;'),('Fixed','probe(c,d)=ds.mulk(0.7824130654335022,-1.8611856944517058e-08,0.782470703125,-0.000057637691497802734,c,d);process=probe;')]:
 src=p/(name+'.dsp');src.write_text(s+process+'\n');ns['run'](['faust','-single','-ftz','0','-cn',name,str(src),'-o',str(p/(name+'.hpp'))])
base=(root/'native-history-soak-fivefold/paired/driver.cpp').read_text().split('#include "generated.hpp"')[0]
body=r'''
#include "Static.hpp"
#include "Dynamic.hpp"
#include "Fixed.hpp"
#include <iostream>
#include <iomanip>
int main(){Static s;Dynamic d;Fixed f;s.init(44100);d.init(44100);f.init(44100);double errors[3]={0,0,0};for(int i=1;i<=10000;i++){float a=.7824130654335022f,b=-1.8611856944517058e-08f,c=.01f*i,h=0,l=0,z=0;float* in2[]={&c,&z};float* in4[]={&a,&b,&c,&z};float* out[]={&h,&l};double ref=(double(a)+b)*c;s.compute(1,in2,out);errors[0]=std::max(errors[0],std::abs(double(h)+l-ref)/ref);d.compute(1,in4,out);errors[1]=std::max(errors[1],std::abs(double(h)+l-ref)/ref);f.compute(1,in2,out);errors[2]=std::max(errors[2],std::abs(double(h)+l-ref)/ref);}for(double e:errors)std::cout<<std::setprecision(17)<<e<<"\n";}
'''
(p/'driver.cpp').write_text(base+body);ns['run'](['g++','-O1','-ffp-contract=off','-fno-fast-math',str(p/'driver.cpp'),'-o',str(p/'render')]);r=subprocess.run([str(p/'render')],capture_output=True,text=True,timeout=30,preexec_fn=ns['limits']);assert r.returncode==0;values=list(map(float,r.stdout.split()));report=dict(zip(['static_relative_error','dynamic_relative_error','presplit_relative_error'],values));(p/'report.json').write_text(json.dumps(report,indent=2));print(report)

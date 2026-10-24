from pathlib import Path
import re,json,struct
root=Path(__file__).resolve().parent;p=root/'presplit-coefficient-isolation';p.mkdir(exist_ok=True)
ns={'__file__':str(root/'native_history_soak.py')};exec((root/'native_history_soak.py').read_text().split('base=(root/')[0],ns)
s=(root/'paired-presplit-coefficients.dsp').read_text();base=s.rsplit('process =',1)[0];assert base.count('):dfbiquad;')==1;base=base.replace('):dfbiquad;','):_,_,_,_,_,_,_,_,!,!;')
names=[]
for high in (False,True):
 line=next(x for x in s.splitlines() if x.startswith('dfhp(' if high else 'dflp('));args=re.findall(r'dfsection\(fh,fl,([^)]*)\)',line);assert len(args)==3
 for i,arg in enumerate(args):
  name=('H' if high else 'L')+str(i);names.append(name);src=p/(name+'.dsp');src.write_text(base+'coefs(fh,fl)=ds.dfsection(fh,fl,'+arg+',0,0);\nprocess=coefs;\n');ns['run'](['faust','-single','-ftz','0','-cn',name,str(src),'-o',str(p/(name+'.hpp'))])
cpp=(root/'independent_pair_probe.cpp').read_text();pre=(root/'native-history-soak-fivefold/paired/driver.cpp').read_text().split('#include "generated.hpp"')[0]
cpp=pre+'\n'.join('#include "'+n+'.hpp"' for n in names)+'\n'+cpp
cpp=cpp.replace('struct Filter {','struct Filter {'+' '.join(n+' c'+n+';' for n in names)+'bool initialized=false;')
cpp=cpp.replace('R tv=x,dv=x;','if(!initialized){'+''.join('c'+n+'.init(rate);' for n in names)+'initialized=true;}R tv=x,dv=x;')
old='R v=dv-R(a1d)*d[i][0]-R(a2d)*d[i][1];dv=R(b0d)*v+R(b1d)*d[i][0]+R(b0d)*d[i][1];'
new='float ch=std::max(fc,2304.),cl=std::max(fc,2304.)-double(ch),values[8];float* ins[]={&ch,&cl};float* outs[]={values,values+1,values+2,values+3,values+4,values+5,values+6,values+7};'
new+='if(high){'+''.join(('if' if i==0 else 'else if')+f'(i=={i})cH{i}.compute(1,ins,outs);' for i in range(3))+'}else{'+''.join(('if' if i==0 else 'else if')+f'(i=={i})cL{i}.compute(1,ins,outs);' for i in range(3))+'}'
new+='R cb0=R(double(values[0])+values[1]),cb1=R(double(values[2])+values[3]),ca1=R(double(values[4])+values[5]),ca2=R(double(values[6])+values[7]);R v=dv-ca1*d[i][0]-ca2*d[i][1];dv=cb0*v+cb1*d[i][0]+cb0*d[i][1];'
assert old in cpp;cpp=cpp.replace(old,new);(p/'driver.cpp').write_text(cpp)
rows=[]
for mode,opts in [('double-state',['-DDOUBLE_STATE']),('paired-state',[])]:
 ns['run'](['g++','-O1','-ffp-contract=off','-fno-fast-math',*opts,str(p/'driver.cpp'),'-o',str(p/mode)])
 for rate in (44100,48000):
  tag=f'chirped-sweep-{rate}-sine';dest=p/(mode+'-'+str(rate)+'.bin');ms=ns['run']([str(p/mode),str(rate),str(root/'checkpoint-controls'/(tag+'-input.bin')),str(root/'checkpoint-controls/chirped-sweep-controls.bin'),str(dest)]);a=struct.unpack('<6750f',dest.read_bytes());b=struct.unpack('<33750f',(root/'checkpoint-controls'/(tag+'-stock.bin')).read_bytes())[:6750];q=max(abs(x-y)/(2e-6+1e-5*abs(y)) for x,y in zip(a,b));rows.append(dict(mode=mode,rate=rate,ratio=q,ms=ms));print(rows[-1],flush=True);(p/'report.json').write_text(json.dumps(rows,indent=2))

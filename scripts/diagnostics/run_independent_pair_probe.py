from pathlib import Path
import struct,json
root=Path(__file__).resolve().parent;p=root/'independent-pair-probe';p.mkdir(exist_ok=True)
ns={'__file__':str(root/'native_history_soak.py')};exec((root/'native_history_soak.py').read_text().split('base=(root/')[0],ns)
rows=[]
for mode,opts in [('double',['-DDOUBLE_STATE']),('pair',[])]:
 ns['run'](['g++','-O1','-ffp-contract=off','-fno-fast-math',*opts,str(root/'independent_pair_probe.cpp'),'-o',str(p/mode)])
 for rate in (44100,48000):
  tag=f'chirped-sweep-{rate}-sine';dest=p/(mode+'-'+str(rate)+'.bin');ms=ns['run']([str(p/mode),str(rate),str(root/'checkpoint-controls'/(tag+'-input.bin')),str(root/'checkpoint-controls/chirped-sweep-controls.bin'),str(dest)]);a=struct.unpack('<6750f',dest.read_bytes());b=struct.unpack('<33750f',(root/'checkpoint-controls'/(tag+'-stock.bin')).read_bytes())[:6750];q=max(abs(x-y)/(2e-6+1e-5*abs(y)) for x,y in zip(a,b));rows.append(dict(mode=mode,rate=rate,ratio=q,ms=ms));print(rows[-1],flush=True);(p/'report.json').write_text(json.dumps(rows,indent=2))

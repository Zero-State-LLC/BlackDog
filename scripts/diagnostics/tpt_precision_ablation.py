"""Bounded native TPT precision diagnostic; never production qualification."""
from pathlib import Path
import hashlib,json,math,re,resource,struct,subprocess,sys
ROOT=Path(sys.argv[1]).resolve()
OUT=ROOT/'tpt-precision-ablation';OUT.mkdir(exist_ok=True)
def limits():
 resource.setrlimit(resource.RLIMIT_CPU,(20,20));resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
def run(args): subprocess.run(args,check=True,capture_output=True,timeout=30,preexec_fn=limits)
def sha(data): return hashlib.sha256(data).hexdigest()
src=ROOT/'matched-single/live-tpt-double-48000.dsp'
headers={}
for precision in ('single','double'):
 p=OUT/(precision+'.hpp');run(['faust','-'+precision,'-ftz','0',str(src),'-o',str(p)]);headers[precision]=p.read_text()
single,double=headers['single'],headers['double']
meters=re.findall(r'(fRec\d+)\[0\] = .*std::fabs',single)
assert meters==['fRec0','fRec7','fRec20'],meters
variants={'single':single,'double':double,
 'single_promoted_types':re.sub(r'\bfloat\b','double',single),
 'double_float_filter_states':re.sub(r'\bdouble (fRec\d+)\[',lambda m:('double ' if m[1] in meters else 'float ')+m[1]+'[',double),
 'double_float_meter_states':re.sub(r'\bdouble (fRec\d+)\[',lambda m:('float ' if m[1] in meters else 'double ')+m[1]+'[',double),
 'double_float_all_states':re.sub(r'\bdouble (fRec\d+)\[',r'float \1[',double),
 'double_float_coefficients':re.sub(r'\bdouble (f(?:Const|Slow)\d+)\b',r'float \1',double)}
pair=(ROOT/'tpt_pair.hpp').read_text()
variants['single_paired_filter_and_meter']=pair+'\n'+re.sub(r'\bfloat (f(?:Rec|Temp)\d+)\b',r'TptPair \1',single).replace('std::fabs(', 'tpt_abs(')
variants['single_double_filter_and_meter']=re.sub(r'\bfloat (f(?:Rec|Temp)\d+)\b',r'double \1',single)
driver=(ROOT/'matched-single/driver.cpp').read_bytes();(OUT/'driver.cpp').write_bytes(driver)
rows=[]
for name,header in variants.items():
 (OUT/'generated.hpp').write_text(header);(OUT/(name+'.hpp')).write_text(header)
 run(['g++','-O2','-ffp-contract=off',str(OUT/'driver.cpp'),'-o',str(OUT/'render')])
 for stim in ('noise','impulse','sine'):
  ref=json.loads((ROOT/('matched-double/live-tpt-double-48000-'+stim+'.json')).read_text())
  inp=struct.pack('<'+'f'*len(ref['input']),*ref['input']);(OUT/'input.bin').write_bytes(inp)
  dest=OUT/(name+'-'+stim+'.bin');run([str(OUT/'render'),str(OUT/'input.bin'),str(dest)])
  data=dest.read_bytes();vals=struct.unpack('<'+'d'*(len(data)//8),data);actual=[list(vals[i::4]) for i in range(4)]
  assert all(math.isfinite(v) for ch in actual for v in ch)
  assert actual[0]==ref['input']
  worst=(0,None);maxdb=0
  for c in range(4):
   for frame,(a,b) in enumerate(zip(actual[c],ref['actual'][c])):
    error=abs(a-b);ratio=error/(2e-6+1e-5*abs(b));maxdb=max(maxdb,error*200 if c else 0)
    if ratio>worst[0]:worst=(ratio,dict(channel=c,frame=frame,actual=a,reference=b))
  rows.append(dict(variant=name,stimulus=stim,passed=worst[0]<=1,max_tolerance_ratio=worst[0],max_meter_error_db=maxdb,worst=worst[1],capture_sha256=sha(data),header_sha256=sha(header.encode()),input_sha256=sha(inp)))
 print(name,[(r['stimulus'],r['passed'],r['max_meter_error_db']) for r in rows if r['variant']==name],flush=True)
report=dict(diagnostic_only=True,source_sha256=sha(src.read_bytes()),driver_sha256=sha(driver),script_sha256=sha(Path(__file__).read_bytes()),sample_rate=48000,frames=4096,block_size=64,meters=meters,compiler='Faust 2.88.0; g++ -O2 -ffp-contract=off',rows=rows)
(OUT/'report.json').write_text(json.dumps(report,indent=2))

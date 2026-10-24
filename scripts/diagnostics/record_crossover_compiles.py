from pathlib import Path
import subprocess,json,time,resource,hashlib
root=Path(__file__).resolve().parent;out=root/'crossover-compile-audit';out.mkdir(exist_ok=True)
def limits():
 resource.setrlimit(resource.RLIMIT_CPU,(20,20));resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();rows=[]
for label in ('live','full-live','tangent-live','unit-live','stream-live','rational-live','hybrid-live','meter-live','product-live','twosum-live','module'):
 source=root/('paired-crossover-'+label+'.dsp');dest=out/(label+'.hpp');cmd=['faust','-single','-ftz','0',str(source),'-o',str(dest)];t=time.monotonic()
 try:
  r=subprocess.run(cmd,capture_output=True,timeout=30,preexec_fn=limits);row=dict(returncode=r.returncode,stdout=r.stdout.decode(errors='replace'),stderr=r.stderr.decode(errors='replace'))
 except subprocess.TimeoutExpired:row=dict(returncode=None,timeout=True)
 row.update(label=label,source_sha256=sha(source),command=cmd,elapsed_s=time.monotonic()-t,header_sha256=sha(dest) if dest.exists() else None,limits=dict(cpu_s=20,address_space_bytes=1024**3,file_bytes=16*1024**2,wall_s=30));rows.append(row);print(label,row['returncode'],flush=True);(out/'report.json').write_text(json.dumps(rows,indent=2)+'\n')

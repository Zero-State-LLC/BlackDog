from pathlib import Path
import struct,json,hashlib,math
root=Path('work/pluck-single-loop-evidence/pluck-single-loop-check');coef=json.loads(Path('work/pluck-coefficients/pluck-coefficient-check/report.json').read_text());rows=[]
for row in coef['rows']:
 sr,f,n,a=row['sample_rate'],row['frequency'],int(row['n']),row['a'];p=root/f'{sr}-{f}-0.5-1.bin';raw=p.read_bytes();observed=[v[0] for v in struct.iter_unpack('<ff',raw)];ring=[0.]*n;yprev=yprev2=uprev=0.;maxerr=ss=refss=0.;worsti=0
 # Independent double arithmetic model using compiled float32 coefficient captures.
 for i in range(sr//2):
  v=(1. if i==1 else 0.)+.998*.5*(yprev+yprev2);u=ring[i%n];ring[i%n]=v;y=a*u+uprev-a*yprev;uprev=u;yprev2=yprev;yprev=y;ref=.5*y;err=abs(ref-observed[i]);ss+=err*err;refss+=ref*ref
  if err>maxerr:maxerr=err;worsti=i
 rows.append(dict(sample_rate=sr,frequency=f,frames=sr//2,max_absolute_error=maxerr,worst_frame=worsti,rms_error=math.sqrt(ss/(sr//2)),relative_rms_error=math.sqrt(ss/refss) if refss else None,capture_sha256=hashlib.sha256(raw).hexdigest()))
Path('outputs/blackdog-pluck-audio-model-comparison.json').write_text(json.dumps(dict(status='DIAGNOSTIC_REFERENCE_COMPARISON',scope='First0.5seconds of each static-frequency capture; independent double recurrence using probed float32 n/a; feedback0.998 modeled mathematically; not perceptual or full-production acceptance',rows=rows),indent=2)+'\n');print('max absolute',max(r['max_absolute_error'] for r in rows),'max relative RMS',max(r['relative_rms_error'] for r in rows));print(sorted(rows,key=lambda r:r['max_absolute_error'],reverse=True)[:2])

from pathlib import Path
import tarfile,json,hashlib,struct,math
from decimal import Decimal,localcontext
root=Path('work/mulk-constants-evidence');archive=Path('work/mulk-constants-evidence.tar.gz')
with tarfile.open(archive) as t:t.extractall(root,filter='data')
p=root/'mulk-constants';r=json.loads((p/'report.json').read_text());sha=lambda b:hashlib.sha256(b).hexdigest();assert sha((root/'qualify_mulk_constants.py').read_bytes())==r['runner_sha256'];assert sha((root/'paired-presplit-coefficients.dsp').read_bytes())==r['source_sha256'];raw=(p/'inputs.bin').read_bytes();assert sha(raw)==r['input_sha256'];inputs=list(struct.iter_unpack('<ff',raw));assert len(inputs)==984
assert len(r['rows'])==18 and {(x['batch'],x['variant']) for x in r['rows']}=={(b,v) for b in range(6) for v in ('exact','bad-split','omit-cross')}
for row in r['rows']:
 tag=f"b{row['batch']}-{row['variant']}";assert sha((p/(tag+'.dsp')).read_bytes())==row['source_sha256'];raw=(p/(tag+'.bin')).read_bytes();assert sha(raw)==row['capture_sha256'];vals=struct.unpack('<'+str(len(inputs)*14)+'f',raw);assert all(map(math.isfinite,vals));q=0;dq=Decimal(0)
 with localcontext() as ctx:
  ctx.prec=80
  for i,(c,d) in enumerate(inputs):
   for j,(ah,al,_,_) in enumerate(row['coefficients']):
    h,l=vals[i*14+j*2:i*14+j*2+2];actual=h+l;ref=(ah+al)*(c+d);q=max(q,abs(actual-ref)/(1e-30+1e-12*abs(ref)))
    D=Decimal.from_float;dr=(D(ah)+D(al))*(D(c)+D(d));da=D(h)+D(l);dq=max(dq,abs(da-dr)/(Decimal('1e-30')+Decimal('1e-12')*abs(dr)))
 assert q==row['ratio'];assert (dq<=1)==(row['variant']=='exact');row['decimal80_ratio']=float(dq)
r.update(positive_batches=6,negative_batches_rejected=12,products_per_variant=42*984,archive_sha256=sha(archive.read_bytes()),independent_reference='Decimal.from_float with precision 80; full high+low product')
Path('outputs/blackdog-mulk-constant-verification.json').write_text(json.dumps(r,indent=2)+'\n');print('42 coefficients; 984 inputs; 41328 products/variant; six positive and twelve negative batches verified');print('worst exact Decimal80 ratio',max(x['decimal80_ratio'] for x in r['rows'] if x['variant']=='exact'))

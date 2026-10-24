from pathlib import Path
import struct,json,hashlib
b=Path('work/bitdsp-evidence');r=json.loads((b/'bitdsp-check/report.json').read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
for row in r['rows']:
 name=row['candidate'];raw=(b/'bitdsp-check'/name/'capture.bin').read_bytes();assert sha(raw)==row['capture_sha256'];assert sha((b/(name+'-closed.dsp')).read_bytes())==row['source_sha256'];values=[x[0] for x in struct.iter_unpack('<f',raw)];expected=[]
 if name=='full_adder':
  for i in range(8):
   total=i.bit_count();expected.extend([total%2,total//2])
 else:
  for seq in range(256):
   state=0
   for i in range(4):
    symbol=(seq>>(2*i))&3;total=(symbol&1)+(symbol>>1)+state;expected.append(total//2);state=total%2
 assert values==expected
r['independent_verification']={'status':'PASS','archive_sha256':sha(Path('work/bitdsp-evidence.tar.gz').read_bytes())};Path('outputs/blackdog-bitdsp-verification.json').write_text(json.dumps(r,indent=2)+'\n');print('Verified complete binary truth table and 256 four-frame sequences')

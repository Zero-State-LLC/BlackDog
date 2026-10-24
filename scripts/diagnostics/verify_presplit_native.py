from pathlib import Path
import json,struct,math,hashlib
root=Path('work/presplit-native-evidence');prior=Path('work/checkpoint-controls-evidence/checkpoint-controls');rows=[]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for folder in ['independent-pair-probe','faust-coefficient-isolation','normalized-coefficient-isolation','presplit-coefficient-isolation','modular-twosum-native','presplit-native','presplit-modular-native']:
 for row in json.loads((root/folder/'report.json').read_text()):
  rate=row['rate'];name=f"{row['mode']}-{rate}.bin" if 'mode' in row else f'chirped-sweep-{rate}-sine.bin';f=root/folder/name;raw=f.read_bytes();assert len(raw) in (27000,135000);a=struct.unpack('<'+str(len(raw)//4)+'f',raw);ref=prior/f'chirped-sweep-{rate}-sine-stock.bin';b=struct.unpack('<33750f',ref.read_bytes())[:len(a)];assert all(map(math.isfinite,a));q=max(abs(x-y)/(2e-6+1e-5*abs(y)) for x,y in zip(a,b));assert q==row['ratio'];rows.append(dict(experiment=folder,**row,capture_sha256=sha(f),reference_sha256=sha(ref),frames=len(a)//3*64))
report=dict(rows=rows,verified_histories=len(rows),source_sha256=sha(root/'paired-presplit-coefficients.dsp'),archive_sha256=sha(Path('work/presplit-native-evidence.tar.gz')),admission='NOT_GRANTED')
Path('outputs/blackdog-presplit-native-verification.json').write_text(json.dumps(report,indent=2)+'\n');print('Verified histories:',len(rows))

from pathlib import Path
import hashlib,json,math,struct,tarfile,itertools
archive=Path('work/presplit-modular-evidence.tar.gz');root=Path('work/presplit-modular-evidence')
with tarfile.open(archive) as t:t.extractall(root,filter='data')
p=root/'presplit-modular-matrix';r=json.loads((p/'report.json').read_text());prior=Path('work/checkpoint-controls-evidence/checkpoint-controls');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert len(r['rows'])==24
assert {(x['schedule'],x['rate'],x['stimulus']) for x in r['rows']}==set(itertools.product(('boundary-holds','chirped-sweep'),(44100,48000,96000,192000),('noise','impulse','sine')))
assert sha(root/'presplit_modular_matrix.py')==r['runner_sha256']
assert sha(root/'presplit-modular-native/driver.cpp')==r['driver_sha256']
assert sha(root/'presplit-modular-native/render')==r['binary_sha256']
src=Path('work/paired-presplit-coefficients.dsp').read_text().rsplit('process =',1)[0]
for name,proc in [('HP','ds.hp'),('LP','ds.lp'),('Meter','ds.meter(0)')]:assert (root/'presplit-modular-native'/(name+'.dsp')).read_text()==src+'process = '+proc+';\n'
for row in r['rows']:
 tag=f"{row['schedule']}-{row['rate']}-{row['stimulus']}";f=p/(tag+'.bin');assert sha(f)==row['capture_sha256'];raw=f.read_bytes();assert len(raw)==135000;a=struct.unpack('<33750f',raw);ref=prior/(tag+'-stock.bin');b=struct.unpack('<33750f',ref.read_bytes());assert sha(ref)==row['reference_sha256'];assert sha(prior/(tag+'-input.bin'))==row['input_sha256'];assert sha(prior/(row['schedule']+'-controls.bin'))==row['controls_sha256'];assert all(map(math.isfinite,a));q=max(abs(x-y)/(2e-6+1e-5*abs(y)) for x,y in zip(a,b));assert q==row['ratio'] and (q<=1)==row['passed']
r.update(archive_sha256=sha(archive),verified_cases=24,passed=sum(x['passed'] for x in r['rows']),max_tolerance_ratio=max(x['ratio'] for x in r['rows']),source_sha256=sha(Path('work/paired-presplit-coefficients.dsp')))
Path('outputs/blackdog-presplit-modular-verification.json').write_text(json.dumps(r,indent=2)+'\n');print({k:v for k,v in r.items() if k!='rows'})

"""Retain full captures for independent 144k versus 72k+72k comparison."""
from pathlib import Path
import json,math,struct,hashlib
root=Path(__file__).resolve().parent
harness=root/'wasm_history_qualification.py'
s=harness.read_text().split('\nprefix_probe()\n')[0].replace('switch-precise-live.dsp','paired-presplit-coefficients.dsp').replace('40a1342836429fb8969b6737abf226a2b5ccfe19556d1882c4ced37421c1c515','d4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e').replace("'history-render.mjs'","'presplit-render.mjs'")
exec(compile(s,str(harness),'exec'))
out=root/'presplit-split-replay';out.mkdir(exist_ok=True)
cap=json.loads((root/'live-controls-switch-threshold-walk/48000-sine-capture.json').read_text())
address=next(r['control_address'] for r in json.loads((root/'live-controls-switch-threshold-walk/report.json').read_text())['rows'] if r['rate']==48000)
events=[(b,round(4000+2000*math.sin(2*math.pi*(b/997+(b/11250)**2*25)),2)) for b in range(2250)]
rows=[]
def save(name,samples,cp,receipt):
 raw=struct.pack('<'+str(sum(map(len,samples)))+'f',*(v for ch in samples for v in ch));(out/(name+'.bin')).write_bytes(raw);(out/(name+'-checkpoint.json')).write_bytes(cp);rh=put(name+'-receipt.json',receipt);rows.append(dict(name=name,capture_sha256=sha(raw),checkpoint_sha256=sha(cp),receipt_sha256=rh))
full,cp,r=render(cap['input'],48000,'sine',events,address,sha(b'presplit-full-replay'),0,0);save('full',full,cp,r)
parts=[];parent=None
for j in range(2):
 ev=[(b-j*1125,v) for b,v in events if j*1125<=b<(j+1)*1125]
 vals,parent,r=render(cap['input'][j*72000:(j+1)*72000],48000,'sine',ev,address,sha(b'presplit-parts-replay'),j,j*72000,parent);parts.append(vals);save('part'+str(j),vals,parent,r)
assert all(full[ch]==parts[0][ch]+parts[1][ch] for ch in range(4))
assert json.loads(cp)['state_sha256']==json.loads(parent)['state_sha256']
put('report.json',dict(passed=True,rows=rows,runner_sha256=sha(Path(__file__).read_bytes()),source_sha256=sha(source.encode()),admission='NOT_GRANTED'));print('full split replay passed',flush=True)

"""Replay already compiled modular analyzer against all 24 retained stock histories."""
from pathlib import Path
import hashlib,json,struct,math
root=Path(__file__).resolve().parent
ns={'__file__':str(root/'native_history_soak.py')}
exec((root/'native_history_soak.py').read_text().split('base=(root/')[0],ns)
p=root/'presplit-modular-native'; out=root/'presplit-modular-matrix';out.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for schedule in ('boundary-holds','chirped-sweep'):
 for rate in (44100,48000,96000,192000):
  for stim in ('noise','impulse','sine'):
   tag=f'{schedule}-{rate}-{stim}'; prior=root/'checkpoint-controls'; inp=prior/(tag+'-input.bin');control=prior/(schedule+'-controls.bin');ref=prior/(tag+'-stock.bin');dest=out/(tag+'.bin')
   ms=ns['run']([str(p/'render'),str(rate),str(inp),str(control),str(dest)])
   raw=dest.read_bytes();assert len(raw)==135000;a=struct.unpack('<33750f',raw);b=struct.unpack('<33750f',ref.read_bytes());assert all(map(math.isfinite,a))
   q=max(abs(x-y)/(2e-6+1e-5*abs(y)) for x,y in zip(a,b))
   rows.append(dict(schedule=schedule,rate=rate,stimulus=stim,frames=720000,ratio=q,passed=q<=1,ms=ms,capture_sha256=sha(dest),reference_sha256=sha(ref),input_sha256=sha(inp),controls_sha256=sha(control)))
   (out/'report.json').write_text(json.dumps(dict(rows=rows,runner_sha256=sha(Path(__file__)),driver_sha256=sha(p/'driver.cpp'),binary_sha256=sha(p/'render'),admission='NOT_GRANTED'),indent=2));print(tag,q,flush=True)

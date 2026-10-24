from pathlib import Path
import sys, json, hashlib
import numpy as np
import dawdreamer as daw
sys.path.insert(0,'work')
from bounded_pluck_host_contract import create_pluck_graph
source=Path('work/pluck-bounded-epoch.dsp').read_text()
out=Path('work/bounded-pluck-history-evidence');out.mkdir(exist_ok=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
schedules={'silence':[], 'low_tail':[(.01,.02,16,127)], 'high_tail':[(.01,.02,119,127)], 'rapid':[(.01+i*.025,.01,[16,69,119,69][i%4],1+(i*37)%127) for i in range(256)]}
rows=[]
for sr in (44100,48000,96000,192000):
 previous=None
 for label in ('silence','low_tail','high_tail','rapid','rapid_repeat'):
  notes=schedules['rapid' if label=='rapid_repeat' else label]
  engine,proc=create_pluck_graph(daw.RenderEngine,source,notes,sr)
  engine.render(12.0); x=engine.get_audio()
  assert x.shape==(2,12*sr) and np.isfinite(x).all() and np.array_equal(x[0],x[1])
  if label=='silence':assert not np.any(x)
  if label=='rapid':previous=x.copy()
  if label=='rapid_repeat':assert np.array_equal(previous,x)
  raw=x.T.astype('<f4').tobytes();(out/f'{sr}-{label}.bin').write_bytes(raw)
  row=dict(sample_rate=sr,label=label,frames=12*sr,capture_sha256=sha(raw),peak=float(np.max(np.abs(x))),first_second_rms=float(np.sqrt(np.mean(x[0,:sr].astype('float64')**2))),last_second_rms=float(np.sqrt(np.mean(x[0,-sr:].astype('float64')**2))),notes=len(notes))
  rows.append(row); print(sr,label,row['peak'],row['last_second_rms'],flush=True)
(out/'report.json').write_text(json.dumps(dict(source_sha256=sha(source.encode()),adapter_sha256=sha(Path('work/bounded_pluck_host_contract.py').read_bytes()),runner_sha256=sha(Path(__file__).read_bytes()),duration_seconds=12,schedules=schedules,rows=rows,scope='Pinned macOS arm64 DawDreamer0.9.0, eight voices, natural-release policy; bounded finite output, silence, repeatability and measured tails only; no perceptual acceptance or global stability proof',admission='NOT_GRANTED'),indent=2)+'\n')

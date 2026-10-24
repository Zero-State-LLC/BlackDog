from pathlib import Path
import hashlib,json
import numpy as np
import dawdreamer as daw
from bounded_pluck_host_contract import create_pluck_graph
source=Path('work/pluck-bounded-epoch.dsp').read_text();sha=lambda b:hashlib.sha256(b).hexdigest()
for label,dynamic in [('current',True),('natural',False)]:
 out=Path('work/bounded-pluck-release-'+label);out.mkdir(exist_ok=True);engine,proc=create_pluck_graph(daw.RenderEngine,source,[(.01,.2,69,100)],48000);proc.dynamic_voices=dynamic;engine.render(1.0);x=engine.get_audio();assert x.shape==(2,48000) and np.isfinite(x).all() and np.array_equal(x[0],x[1]);raw=x.T.astype('<f4').tobytes();(out/'48000-solo0.bin').write_bytes(raw)
 (out/'report.json').write_text(json.dumps(dict(source_sha256=sha(source.encode()),adapter_sha256=sha(Path('work/bounded_pluck_host_contract.py').read_bytes()),runner_sha256=sha(Path(__file__).read_bytes()),host_version='0.9.0',dynamic_voices=dynamic,rows=[dict(label='solo0',sample_rate=48000,capture_sha256=sha(raw),peak=float(np.max(np.abs(x))))],admission='NOT_GRANTED'),indent=2)+'\n')
 print(label,float(np.max(np.abs(x[:,10560:14400]))))

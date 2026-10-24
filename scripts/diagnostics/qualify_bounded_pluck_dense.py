from pathlib import Path
import json,hashlib,sys
import numpy as np
import dawdreamer as daw
sys.path.insert(0,'work')
from bounded_pluck_host_contract import create_pluck_graph,validate_notes
out=Path('work/bounded-pluck-dense-evidence');out.mkdir(exist_ok=True);source=Path('work/pluck-bounded-epoch.dsp').read_text();sha=lambda b:hashlib.sha256(b).hexdigest();rows=[];comparisons=[]
for sr in (44100,48000,96000,192000):
 engine,proc=create_pluck_graph(daw.RenderEngine,source,[],sr)
 first=None
 for pitch in range(16,120):
  captures={}
  for velocity in (1,127):
   proc.clear_midi()
   for start,duration,note,vel in validate_notes([(.01,.02,pitch,velocity)]):proc.add_midi_note(note,vel,start,duration)
   engine.render(.5);x=engine.get_audio();assert x.shape==(2,sr//2) and np.isfinite(x).all() and np.array_equal(x[0],x[1]);peak=float(np.max(np.abs(x)));assert 0<peak<=1.00001
   raw=x.T.astype('<f4').tobytes();name=f'{sr}-{pitch}-{velocity}.bin';(out/name).write_bytes(raw);captures[velocity]=x.copy();rows.append(dict(file=name,sample_rate=sr,pitch=pitch,velocity=velocity,frames=sr//2,peak=peak,capture_sha256=sha(raw)))
   if pitch==16 and velocity==1:first=raw
  error=float(np.max(np.abs(captures[127]/127-captures[1])));assert error<2e-6;comparisons.append(dict(sample_rate=sr,pitch=pitch,velocity_scaling_error=error))
 proc.clear_midi();proc.add_midi_note(16,1,.01,.02);engine.render(.5);raw=engine.get_audio().T.astype('<f4').tobytes();assert raw==first;(out/f'{sr}-reset-repeat.bin').write_bytes(raw)
 print(sr,'208 captures, velocity scaling pass, reset repeat exact',flush=True)
(out/'report.json').write_text(json.dumps(dict(source_sha256=sha(source.encode()),adapter_sha256=sha(Path('work/bounded_pluck_host_contract.py').read_bytes()),runner_sha256=sha(Path(__file__).read_bytes()),host_version='0.9.0',rows=rows,comparisons=comparisons,scope='All104 integer MIDI pitches16..119 at velocities1/127; 0.5second renders, four rates, same host graph reused with clear_midi between renders; four start/end reset repeat controls; bounded finiteness/nonzero output and linear velocity scaling, not pitch accuracy or timbral acceptance',admission='NOT_GRANTED'),indent=2)+'\n')

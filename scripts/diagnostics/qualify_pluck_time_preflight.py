from pathlib import Path
import json,hashlib,sys
import numpy as np
import dawdreamer as daw
sys.path.insert(0,'work/BlackDog')
from diagnostics.pluck_host_contract import create_pluck_graph
source=Path('work/pluck-reset-loop.dsp').read_text();out=Path('work/pluck-time-preflight-evidence');out.mkdir(exist_ok=True);sha=lambda b:hashlib.sha256(b).hexdigest();notes=[(.01+i*.06,.04,60+i,100) for i in range(12)];rows=[]
def render(sr,label,seq,voices=8):
 engine,proc=create_pluck_graph(daw.RenderEngine,source,seq,sr);proc.num_voices=voices;engine.render(1.5);x=engine.get_audio();assert x.shape==(2,int(sr*1.5)) and np.isfinite(x).all();p=out/f'{sr}-{label}.bin';p.write_bytes(x.T.astype('<f4').tobytes());return x,dict(label=label,sample_rate=sr,voices=voices,sha256=sha(p.read_bytes()),peak=float(np.max(np.abs(x))))
for sr in (44100,48000,96000,192000):
 a,ra=render(sr,'eight',notes);b,rb=render(sr,'sixteen',notes,16);again,rr=render(sr,'eight-repeat',notes);assert np.array_equal(a,again)
 solos=[]
 for i,note in enumerate(notes):
  s,r=render(sr,'solo'+str(i),[note]);solos.append(s);rows.append(r)
 total=sum(solos);rb['superposition_error']=float(np.max(np.abs(b-total)));assert rb['superposition_error']<2e-6
 ra['difference_from_unstolen']=float(np.max(np.abs(a-b)));assert ra['difference_from_unstolen']>2e-6;ra['repeat_exact']=True;rows.extend([ra,rb,rr]);print(sr,ra['difference_from_unstolen'],rb['superposition_error'],flush=True)
(out/'report.json').write_text(json.dumps(dict(rows=rows,source_sha256=sha(source.encode()),runner_sha256=sha(Path(__file__).read_bytes()),adapter_sha256=sha(Path('work/BlackDog/diagnostics/pluck_host_contract.py').read_bytes()),scope='12 distinct short MIDI notes; eight voices compared with 16-voice diagnostic reference and independent solo sum; 1.5seconds; dynamic_voices=False',conclusion='Eight-voice stealing is deterministic and changes tails; 16-voice reference agrees with solo superposition',admission='NOT_GRANTED'),indent=2)+'\n')

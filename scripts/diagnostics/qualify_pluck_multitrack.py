from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path('work/shipwright-integration').resolve()));sys.path.insert(0,str(Path('work').resolve()))
import numpy as np
import dawdreamer as daw
from shipwright import engine,config
from shipwright.registry import Note,Track,RenderSpec
from bounded_pluck_instrument import bounded_pluck
from bounded_pluck_host_contract import create_pluck_graph
source=Path('work/pluck-bounded-epoch.dsp').read_text();out=Path('work/pluck-multitrack-evidence');out.mkdir(exist_ok=True);sha=lambda x:hashlib.sha256(x).hexdigest();rows=[]
schedules=[[(.01,.2,69,127),(.15,.1,72,100)],[(.01,.2,69,127),(.3,.1,48,80)]]
for sr in (44100,48000,96000,192000):
 config.SR=sr;config.BLOCK=64;config.MASTER_CEILING=.97
 tracks=[Track(bounded_pluck(source),[Note(p,s,d,v) for s,d,p,v in notes],name=f'voice{i}') for i,notes in enumerate(schedules)]
 spec=RenderSpec(tracks,duration=.8);stems=engine.render_stems(spec);mix=engine.render_spec(spec);refs=[];errors=[]
 for i,notes in enumerate(schedules):
  h,_=create_pluck_graph(daw.RenderEngine,source,notes,sr);h.render(.8);raw=h.get_audio().T;refs.append(raw)
  expected=engine._limit(raw);errors.append(float(np.max(abs(stems[f'voice{i}']-expected))));assert errors[-1]<=2e-6
 expected_mix=engine._limit(refs[0]+refs[1]);err=float(np.max(abs(mix-expected_mix)));assert err<=2e-6
 captures={}
 for name,x in [('stem0',stems['voice0']),('stem1',stems['voice1']),('mix',mix),('reference0',refs[0]),('reference1',refs[1])]:
  assert x.shape==(int(.8*sr),2) and np.isfinite(x).all();raw=x.astype('<f4').tobytes();file=f'{sr}-{name}.bin';(out/file).write_bytes(raw);captures[file]=sha(raw)
 rows.append({'sample_rate':sr,'stem_errors':errors,'mix_error':err,'raw_sum_peak':float(np.max(abs(refs[0]+refs[1]))),'mix_peak':float(np.max(abs(mix))),'captures':captures})
 print(sr,'stems and two-track mix pass',flush=True)
(out/'report.json').write_text(json.dumps({'source_sha256':sha(source.encode()),'factory_sha256':sha(Path('work/bounded_pluck_instrument.py').read_bytes()),'runner_sha256':sha(Path(__file__).read_bytes()),'rows':rows,'scope':'two dry centered tracks, default gains, overlapping notes, public stems and mix; no effects/returns/sidechains','admission':'NOT_GRANTED'},indent=2)+'\n')

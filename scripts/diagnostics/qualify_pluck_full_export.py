from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path('work/shipwright-integration').resolve()));sys.path.insert(0,str(Path('work').resolve()))
import numpy as np, soundfile as sf
import dawdreamer as daw
from shipwright import engine,config
from shipwright.registry import Instrument,Track,Note,RenderSpec
from bounded_pluck_host_contract import create_pluck_graph
source=Path('work/pluck-bounded-epoch.dsp').read_text();sha=lambda b:hashlib.sha256(b).hexdigest();source_hash=sha(source.encode());out=Path('work/pluck-full-export-evidence');out.mkdir(exist_ok=True);original=engine._make_source
# Diagnostic-only hook in this one process; the upstream checkout stays unchanged.
def make_source(host,name,track,notes,dur):
 p=original(host,name,track,notes,dur)
 if track.instrument.kind=='faust' and sha(track.instrument.dsp.encode())==source_hash:p.dynamic_voices=False
 return p
engine._make_source=make_source
schedules={'release':[(.01,.2,69,100)],'eight_unison':[(.01,.2,69,127)]*8,'overlap':[(.01,.2,69,100),(.1,.2,69,80)]};rows=[]
for sr in (44100,48000,96000,192000):
 config.SR=sr;config.BLOCK=64;config.MASTER_CEILING=.97;config.EXPORT_SUBTYPE='PCM_16';config.DITHER=True
 for label,notes in schedules.items():
  inst=Instrument.faust('bounded-review',source,8)
  def spec(unit):return RenderSpec(tracks=[Track(inst,[Note(p,start*(2 if unit=='beats' else 1),dur*(2 if unit=='beats' else 1),v) for start,dur,p,v in notes])],duration=.6,tempo=120,time_unit=unit)
  public=engine.render_spec(spec('seconds'));beats=engine.render_spec(spec('beats'));assert public.shape==(int(.6*sr),2) and np.isfinite(public).all();assert np.array_equal(public,beats)
  direct,_=create_pluck_graph(daw.RenderEngine,source,notes,sr);direct.render(.6);raw=direct.get_audio().T;expected=engine._limit(raw);error=float(np.max(np.abs(public-expected)));assert error<=2e-6
  if label=='release':assert np.max(np.abs(public[int(.22*sr):int(.3*sr)]))>0
  engine.set_thread_seed(0);path=out/f'{sr}-{label}.wav';engine.write_audio(path,public,sr);read,rate=sf.read(path,dtype='float32',always_2d=True);assert rate==sr and read.shape==public.shape and np.isfinite(read).all();assert sf.info(path).subtype=='PCM_16';export_error=float(np.max(np.abs(read-public)));assert export_error<1e-4 and np.max(np.abs(read))<=.9701
  for kind,x in [('raw',raw),('render',public),('decoded',read)]: (out/f'{sr}-{label}-{kind}.bin').write_bytes(x.astype('<f4').tobytes())
  rows.append(dict(sample_rate=sr,label=label,frames=len(public),raw_peak=float(np.max(np.abs(raw))),render_peak=float(np.max(np.abs(public))),decoded_peak=float(np.max(np.abs(read))),render_reference_error=error,export_error=export_error,beat_seconds_exact=True,wav_sha256=sha(path.read_bytes()),raw_sha256=sha((out/f'{sr}-{label}-raw.bin').read_bytes()),render_sha256=sha((out/f'{sr}-{label}-render.bin').read_bytes()),decoded_sha256=sha((out/f'{sr}-{label}-decoded.bin').read_bytes())))
 print(sr,'three full render/export cases passed',flush=True)
(out/'report.json').write_text(json.dumps(dict(source_sha256=source_hash,adapter_sha256=sha(Path('work/bounded_pluck_host_contract.py').read_bytes()),runner_sha256=sha(Path(__file__).read_bytes()),upstream_commit='eef7b31e2b82974172d8c562412069624861950a',engine_sha256=sha(Path('work/shipwright-integration/shipwright/engine.py').read_bytes()),install_report_sha256=sha(Path('work/shipwright-integration-install.json').read_bytes()),numpy_version=np.__version__,rows=rows,scope='Full public render_spec, seconds/beats equivalence at120BPM, existing final scaling, seeded dither and write_audio PCM16; diagnostic source-specific release hook only, no production API patch or full effects/sidechain coverage',admission='NOT_GRANTED'),indent=2)+'\n')

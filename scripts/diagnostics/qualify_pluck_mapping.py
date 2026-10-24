from pathlib import Path
import json,hashlib
import numpy as np
import dawdreamer as daw
source=Path('work/pluck-reset-loop.dsp').read_text();sha=lambda b:hashlib.sha256(b).hexdigest();dense=Path('work/pluck-dense-evidence');prior=json.loads((dense/'report.json').read_text());assert prior['source_sha256']==sha(source.encode());index={(r['sample_rate'],r['pitch']):r for r in prior['rows'] if r['velocity']==127};out=Path('work/pluck-mapping-evidence');out.mkdir(exist_ok=True);rows=[]
for sr in (44100,48000,96000,192000):
 engine=daw.RenderEngine(sr,64);proc=engine.make_faust_processor('probe');proc.set_dsp_string(source);proc.num_voices=0;proc.get_parameters_description();proc.set_parameter('/dawdreamer/gain',1.0);proc.set_parameter('/dawdreamer/gate',1.0);engine.load_graph([(proc,[])])
 for pitch in range(16,120):
  freq=440.0*2**((pitch-69)/12);proc.set_parameter('/dawdreamer/freq',freq);engine.render(.5);x=engine.get_audio();assert x.shape==(2,sr//2) and np.isfinite(x).all();raw=x.T.astype('<f4').tobytes();file=f'{sr}-{pitch}.bin';(out/file).write_bytes(raw)
  old=(dense/f'{sr}-{pitch}-127.bin').read_bytes();assert sha(old)==index[sr,pitch]['capture_sha256'];y=np.frombuffer(old,dtype='<f4').reshape(-1,2).T;offset=int(.01*sr);a=x[:,:y.shape[1]-offset];b=y[:,offset:];err=float(np.max(np.abs(a-b)));passed=bool(np.all(np.abs(a-b)<=2e-6+1e-5*np.abs(b)))
  rows.append(dict(sample_rate=sr,pitch=pitch,frequency_hz=freq,alignment_samples=offset,file=file,direct_capture_sha256=sha(raw),midi_capture_sha256=sha(old),max_abs_error=err,pass_tolerance=passed))
 print(sr,'max error',max(r['max_abs_error'] for r in rows if r['sample_rate']==sr),'failures',sum(not r['pass_tolerance'] for r in rows if r['sample_rate']==sr),flush=True)
(out/'report.json').write_text(json.dumps(dict(source_sha256=sha(source.encode()),runner_sha256=sha(Path(__file__).read_bytes()),dense_report_sha256=sha((dense/'report.json').read_bytes()),rows=rows,tolerance={'absolute':2e-6,'relative':1e-5},scope='Pinned host direct monophonic frequency control vs eight-voice MIDI output, all integer pitches, full gain, 0.5seconds minus MIDI onset; direct gate held high vs MIDI note-off natural decay; no pitch-estimator or perceptual acceptance',admission='NOT_GRANTED'),indent=2)+'\n')

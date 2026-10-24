from pathlib import Path
import ast,json,hashlib,sys,types,importlib.metadata,time
import numpy as np
import dawdreamer as daw
root=Path('work');out=root/'pluck-reset-host-evidence';out.mkdir(exist_ok=True);sha=lambda b:hashlib.sha256(b).hexdigest();raw=(root/'shipwright-engine.py').read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=='526864e97e865f509453340fd071aaa9bcad79e7'
tree=ast.parse(raw);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_make_source');ns={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'pinned-shipwright-_make_source','exec'),ns);make=ns['_make_source'];source=(root/'pluck-reset-loop.dsp').read_text();notes=[(.01,.2,69,100),(.1,.2,72,80),(.4,.1,69,100)]
def render(sr,label,seq,source=source):
 engine=daw.RenderEngine(sr,64);track=types.SimpleNamespace(instrument=types.SimpleNamespace(kind='faust',name='pluck',dsp=source,num_voices=8));proc=make(engine,'pluck',track,seq,1.0);engine.load_graph([(proc,[])]);engine.render(1.0);audio=engine.get_audio();assert audio.shape==(2,sr) and np.isfinite(audio).all();path=out/f'{sr}-{label}.bin';path.write_bytes(audio.T.astype('<f4').tobytes());return audio,dict(label=label,sample_rate=sr,shape=list(audio.shape),source_sha256=sha(source.encode()),capture_sha256=sha(path.read_bytes()),peak=float(np.max(np.abs(audio))),inputs=proc.get_num_input_channels(),outputs=proc.get_num_output_channels(),release_length=proc.release_length,n_midi_events=proc.n_midi_events)
rows=[]
for sr in (44100,48000,96000,192000):
 mixed,m=render(sr,'mixed',notes);silence,s=render(sr,'silence',[]);assert s['peak']==0 and m['peak']>0 and m['inputs']==0 and m['outputs']==2
 solos=[]
 for i,note in enumerate(notes):
  audio,row=render(sr,'solo'+str(i),[note]);solos.append(audio);rows.append(row)
 wanted=sum(solos);m['superposition_max_error']=float(np.max(np.abs(mixed-wanted)));m['pre_note_peak']=float(np.max(np.abs(mixed[:,:int(.009*sr)])));m['release_tail_peak']=float(np.max(np.abs(solos[0][:,int(.22*sr):int(.3*sr)])));rows.extend([m,s]);print(sr,m,flush=True)
(out/'report.json').write_text(json.dumps(dict(rows=rows,source_sha256=sha(source.encode()),runner_sha256=sha(Path(__file__).read_bytes()),engine_blob='526864e97e865f509453340fd071aaa9bcad79e7',host_version=importlib.metadata.version('dawdreamer'),numpy_version=np.__version__,scope='Exact pinned _make_source faust branch, eight voices, three MIDI notes with overlap and retrigger; one-second offline audio, block64; no mixer effects or clipping/normalization',admission='NOT_GRANTED'),indent=2)+'\n')

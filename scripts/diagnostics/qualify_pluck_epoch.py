from pathlib import Path
import json,hashlib
import dawdreamer as daw
import numpy as np
old=Path('work/pluck-reset-loop.dsp').read_text();oldline='epoch=+(int(reset)) ~ _;';newline='epoch=(+(int(reset)) : &(65535)) ~ _;';assert old.count(oldline)==1
new=old.replace(oldline,newline);Path('work/pluck-bounded-epoch.dsp').write_text(new)
out=Path('work/pluck-epoch-evidence');out.mkdir(exist_ok=True);sha=lambda b:hashlib.sha256(b).hexdigest();rows=[]
def render(source,sr,frames,freq):
 engine=daw.RenderEngine(sr,64);proc=engine.make_faust_processor('epoch');proc.set_dsp_string(source);proc.num_voices=0;desc=proc.get_parameters_description()
 for d in desc:
  if d['label']=='freq':proc.set_parameter(d['name'],freq)
 engine.load_graph([(proc,[])]);engine.render(frames/sr);return engine.get_audio()
# Audio comparison through an early tag rollover using a first-sample seed.
# Both variants receive identical seed and internal gate schedule; production
# source remains unseeded and uses the normal gate control.
for sr in (44100,48000,96000,192000):
 for freq in (20.,440.,7902.132820097988):
  outputs=[]
  for label,source in [('unbounded',old),('bounded',new)]:
   source=source.replace('gate=button("gate");',"ticks=+(1) ~ _; gate=(int(ticks)%1024)<512; first=1-(1)';")
   source=source.replace('+(int(reset))','+(int(reset)+65530*int(first))')
   (out/f'{label}-seeded.dsp').write_text(source)
   x=render(source,sr,sr//2,freq);assert x.shape==(2,sr//2) and np.isfinite(x).all() and np.array_equal(x[0],x[1]);raw=x.T.astype('<f4').tobytes();file=f'{sr}-{freq}-{label}.bin';(out/file).write_bytes(raw);outputs.append(x)
   rows.append(dict(sample_rate=sr,frequency=freq,variant=label,file=file,source_sha256=sha(source.encode()),capture_sha256=sha(raw),peak=float(np.max(np.abs(x)))))
  assert np.array_equal(*outputs)
 print(sr,'three seeded audio rollover pairs exact',flush=True)
probe="ticks=+(1) ~ _; reset=(int(ticks)%2)==0; epoch=(+(int(reset)) : &(65535)) ~ _; process=epoch;"
(out/'counter-probe.dsp').write_text(probe);frames=131200;x=render(probe,48000,frames,440);assert x.shape==(1,frames) and np.isfinite(x).all();raw=x.T.astype('<f4').tobytes();(out/'counter.bin').write_bytes(raw);values=x[0];assert values.min()==0 and values.max()==65535;rolls=np.flatnonzero(np.diff(values)<0);assert len(rolls)==1 and values[rolls[0]]==65535 and values[rolls[0]+1]==0
(out/'report.json').write_text(json.dumps(dict(status='SEEDED_AUDIO_AND_COUNTER_WRAP_PASS',production_source_sha256=sha(new.encode()),previous_source_sha256=sha(old.encode()),runner_sha256=sha(Path(__file__).read_bytes()),rows=rows,counter_probe_sha256=sha(probe.encode()),counter_capture_sha256=sha(raw),counter_wrap_index=int(rolls[0]+1),counter_frames=frames,scope='24 instrumented half-second audio captures, 12 bit-identical pairs; seeded early tag rollover, plus unseeded counter-only wrap probe. Does not transfer prior production source validation.',admission='NOT_GRANTED'),indent=2)+'\n');print('Unseeded counter wrap verified',int(rolls[0]+1))

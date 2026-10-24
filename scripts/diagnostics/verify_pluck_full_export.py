from pathlib import Path
import json,hashlib
import numpy as np,soundfile as sf
p=Path('work/pluck-full-export-evidence');r=json.loads((p/'report.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for field,path in [('source_sha256','work/pluck-bounded-epoch.dsp'),('adapter_sha256','work/bounded_pluck_host_contract.py'),('runner_sha256','work/qualify_pluck_full_export.py'),('engine_sha256','work/shipwright-integration/shipwright/engine.py'),('install_report_sha256','work/shipwright-integration-install.json')]:assert r[field]==sha(Path(path))
seen=set()
for row in r['rows']:
 sr,label=row['sample_rate'],row['label'];assert (sr,label) not in seen;seen.add((sr,label));arrays={}
 for kind in ('raw','render','decoded'):
  f=p/f'{sr}-{label}-{kind}.bin';assert sha(f)==row[kind+'_sha256'];x=np.fromfile(f,dtype='<f4').reshape(-1,2);assert x.shape==(int(.6*sr),2) and np.isfinite(x).all() and (kind=='decoded' or np.array_equal(x[:,0],x[:,1]));arrays[kind]=x;assert float(np.max(np.abs(x)))==row[{'raw':'raw_peak','render':'render_peak','decoded':'decoded_peak'}[kind]]
 expected=arrays['raw'];peak=np.max(np.abs(expected))
 if peak>.97:expected=expected*(.97/float(peak))
 assert float(np.max(np.abs(expected-arrays['render'])))==row['render_reference_error']<=2e-6
 f=p/f'{sr}-{label}.wav';assert sha(f)==row['wav_sha256'];audio,rate=sf.read(f,dtype='float32',always_2d=True);assert rate==sr and sf.info(f).subtype=='PCM_16' and np.array_equal(audio,arrays['decoded']);assert float(np.max(np.abs(audio-arrays['render'])))==row['export_error']<1e-4;assert np.max(np.abs(audio))<=.9701
 if label=='release':assert np.max(np.abs(arrays['render'][int(.22*sr):int(.3*sr)]))>0
assert seen=={(sr,label) for sr in (44100,48000,96000,192000) for label in ('release','eight_unison','overlap')}
r['verification']={'status':'PASS','render_export_cases':12,'raw_render_decoded_captures':36,'wav_files':12,'scope':'Same-workflow capture and PCM readback verification; beat/seconds equality also asserted during execution; not independent semantic review'};Path('outputs/blackdog-pluck-full-export-verification.json').write_text(json.dumps(r,indent=2)+'\n');print('12 full export cases verified; max PCM error',max(x['export_error'] for x in r['rows']))

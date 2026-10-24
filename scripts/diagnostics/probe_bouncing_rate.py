from pathlib import Path
import sys,json,hashlib,struct
root=Path(__file__).resolve().parent
ns={'__file__':str(root/'qualify_designing_closures.py')};exec((root/'qualify_designing_closures.py').read_text().split('rows=[]')[0],ns);run=ns['run'];out=root/'designing-rate-probe';out.mkdir(exist_ok=True)
raw=(root/'bouncing-ball-closed.dsp').read_text();old='process = impact * gain <: _, _;';assert raw.count(old)==1
source=raw.replace(old,'process = trig <: _, _;');(out/'trigger.dsp').write_text(source)
run(['faust','-single','-ftz','0','-cn','Probe',str(out/'trigger.dsp'),'-o',str(out/'generated.hpp')]);(out/'driver.cpp').write_bytes((root/'designing-bouncing-ball-check/closed/driver.cpp').read_bytes());run(['g++','-O1','-ffp-contract=off','-fno-fast-math',str(out/'driver.cpp'),'-o',str(out/'render')])
rows=[]
for rate in (44100,48000,96000,192000):
 path=out/(str(rate)+'.bin');run([str(out/'render'),str(rate),str(path)]);raw=path.read_bytes();values=list(struct.iter_unpack('<ff',raw));positions=[i for i,(a,b) in enumerate(values) if a>0];assert len(positions)>=2;intervals=[b-a for a,b in zip(positions,positions[1:])];assert set(intervals)=={12000};rows.append(dict(rate=rate,positions=positions,interval_frames=12000,observed_hz=rate/12000,declared_default_rate_hz=4,source_rate_semantics_match=(rate==48000),capture_sha256=hashlib.sha256(raw).hexdigest()))
r=dict(status='SOURCE_RATE_MISMATCH_CONFIRMED',original_closed_source_sha256=hashlib.sha256((root/'bouncing-ball-closed.dsp').read_bytes()).hexdigest(),probe_source_sha256=hashlib.sha256(source.encode()).hexdigest(),rows=rows,scope='Default 4 Hz control; derivative diagnostic exports existing trig signal, without modifying candidate source',admission='NOT_GRANTED');(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

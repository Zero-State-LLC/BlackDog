from pathlib import Path
import json,hashlib,struct
p=Path('work/designing-closure-evidence/designing-rate-probe');r=json.loads((p/'report.json').read_text());assert len(r['rows'])==4 and {x['rate'] for x in r['rows']}=={44100,48000,96000,192000};source=p/'trigger.dsp';assert hashlib.sha256(source.read_bytes()).hexdigest()==r['probe_source_sha256']
for row in r['rows']:
 raw=(p/(str(row['rate'])+'.bin')).read_bytes();assert len(raw)==192000 and hashlib.sha256(raw).hexdigest()==row['capture_sha256'];frames=list(struct.iter_unpack('<ff',raw));assert all(a==b and a in (0.,1.) for a,b in frames);positions=[i for i,(a,b) in enumerate(frames) if a>0];assert positions==row['positions'];assert len(positions)>=2 and set(b-a for a,b in zip(positions,positions[1:]))=={12000};assert row['observed_hz']==row['rate']/12000
r['local_capture_replay']='PASS';Path('outputs/blackdog-designing-rate-verification.json').write_text(json.dumps(r,indent=2)+'\n');print([(x['rate'],x['observed_hz']) for x in r['rows']])

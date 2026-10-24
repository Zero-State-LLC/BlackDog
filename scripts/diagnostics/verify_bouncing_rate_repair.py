from pathlib import Path
import json, hashlib, struct
root=Path('work/bouncing-rate-repair-evidence'); d=root/'bouncing-rate-repair'; r=json.loads((d/'report.json').read_text()); sha=lambda b:hashlib.sha256(b).hexdigest()
a=(root/'bouncing-ball-closed.dsp').read_bytes(); b=(d/'fixed-closed.dsp').read_bytes()
assert a.count(b'int(48000.0 / max(rate, 0.5))')==1
assert b==a.replace(b'int(48000.0 / max(rate, 0.5))',b'int(ma.SR / max(rate, 0.5))')
assert sha(a)==r['original_closed_sha256'] and sha(b)==r['fixed_closed_sha256']
assert sha((root/'qualify_bouncing_rate_repair.py').read_bytes())==r['runner_sha256']
seen=set(); passes=0
for row in r['rows']:
 v,s,c=row['variant'],row['sample_rate'],row['requested_rate']; key=(v,s,c); assert key not in seen; seen.add(key)
 raw=(d/v/(str(s)+'-'+str(c)+'.bin')).read_bytes(); assert sha(raw)==row['capture_sha256'] and len(raw)==row['frames']*8
 positions=[]
 for i,(x,y) in enumerate(struct.iter_unpack('<ff',raw)):
  assert x==y and x in (0.,1.)
  if x: positions.append(i)
 assert positions==row['positions'] and len(positions)>=2
 cf=struct.unpack('<f',struct.pack('<f',c))[0]; interval=int((s if v=='fixed' else 48000)/cf)
 assert all(y-x==interval for x,y in zip(positions,positions[1:]))
 passed=abs(interval-s/cf)<1
 assert passed==row['rate_contract_pass']==(v=='fixed' or s==48000)
 assert sha((d/v/'probe.dsp').read_bytes())==row['probe_source_sha256']
 passes+=passed
assert seen=={(v,s,c) for v in ('fixed','original') for s in (44100,48000,96000,192000) for c in (.5,4.,7.3,15.)}
r['independent_verification']={'captures':len(seen),'repaired_passes':16,'original_passes':4,'original_rejections':12,'archive_sha256':sha(Path('work/bouncing-rate-repair-evidence.tar.gz').read_bytes())}
Path('outputs/blackdog-bouncing-rate-repair-verification.json').write_text(json.dumps(r,indent=2)+'\n')
print('Verified 32 captures: 16 repaired passes, 4 original passes, 12 original rate-contract rejections')

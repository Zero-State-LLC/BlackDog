from pathlib import Path
import json,hashlib,tarfile,shutil
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
repo=Path('work/BlackDog');source=Path('work/pluck-bounded-epoch.dsp');adapter=Path('work/bounded_pluck_host_contract.py');original=(repo/'diagnostics/pluck_host_contract.py').read_text();assert adapter.read_text()==original.replace('83cd856eaf46228903180244b2e5002e139f87decb39d2235a6df980d0b85ab8',sha(source))
sets=[]
for name,newdir,olddir,runner in [('dense','bounded-pluck-dense-evidence','pluck-dense-evidence','qualify_bounded_pluck_dense.py'),('histories','bounded-pluck-history-evidence','pluck-history-evidence','qualify_bounded_pluck_histories.py'),('exhaustion','bounded-pluck-time-preflight-evidence','pluck-time-preflight-evidence','qualify_bounded_pluck_time_preflight.py')]:
 p=Path('work')/newdir;q=Path('work')/olddir;r=json.loads((p/'report.json').read_text());old=json.loads((q/'report.json').read_text());assert r['source_sha256']==sha(source) and r['adapter_sha256']==sha(adapter) and r['runner_sha256']==sha(Path('work')/runner);assert r['rows']==old['rows']
 files=sorted(p.glob('*.bin'));assert {x.name for x in files}=={x.name for x in q.glob('*.bin')}
 for f in files:assert f.read_bytes()==(q/f.name).read_bytes()
 sets.append(dict(name=name,captures=len(files),new_report_sha256=sha(p/'report.json'),prior_report_sha256=sha(q/'report.json'),byte_identical_to_previous_source=True))
assert sum(x['captures'] for x in sets)==916
names=['bounded_pluck_host_contract.py','test_bounded_pluck_host_contract.py','qualify_bounded_pluck_dense.py','qualify_bounded_pluck_histories.py','qualify_bounded_pluck_time_preflight.py','verify_bounded_pluck_dense.py','verify_bounded_pluck_histories.py','verify_bounded_pluck_exhaustion.py','package_bounded_pluck_host.py']
archive=Path('work/pluck-bounded-host-evidence.tar.gz')
with tarfile.open(archive,'w:gz') as t:
 for p in [source]+[Path('work')/n for n in names]+[Path('work')/d for d in ['bounded-pluck-dense-evidence','bounded-pluck-history-evidence','bounded-pluck-time-preflight-evidence']]:t.add(p,arcname=p.name)
r=dict(status='BOUNDED_CANDIDATE_HOST_PASS',source_sha256=sha(source),adapter_sha256=sha(adapter),input_contract_tests=40,test_sha256=sha(Path('work/test_bounded_pluck_host_contract.py')),captures=916,sets=sets,archive_sha256=sha(archive),host='DawDreamer0.9.0, macOS arm64, Python3.12, block64, eight voices with dynamic_voices=False; sixteen-voice exhaustion reference only',admission='NOT_GRANTED',remaining=['Exact new-source native/WASM and live-control qualification','Absolute pitch and musical review','Family and canonical admission review','Signed readiness artifacts'])
(repo/'docs/analysis/pluck-bounded-host-verification-2026-10-24.json').write_text(json.dumps(r,indent=2)+'\n')
for n in names:shutil.copyfile(Path('work')/n,repo/'scripts/diagnostics'/n)
print('Verified and archived916 candidate host captures',sha(archive))

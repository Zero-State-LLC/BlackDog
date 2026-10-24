from pathlib import Path
import json,hashlib,re
exec(compile(Path('work/screen_reset_stratus.py').read_text().split('\nedges=[];f=')[0],'population','exec'))
source=Path('work/faustmod-blocks.mjs').read_bytes();assert hashlib.sha1(b'blob '+str(len(source)).encode()+b'\0'+source).hexdigest()=='daca6aff99551ecda542a7491d953e23a9c3ba62'
s=source.decode(); rows=[]; out=Path('work/faustmod-candidates');out.mkdir(exist_ok=True)
for name,args,body in [('mod-matrix-2x2','a,b,aa,ab,ba,bb','a*aa + b*ba, a*ab + b*bb'),('cv-mix-4','a,b,c,d,ga,gb,gc,gd','a*ga + b*gb + c*gc + d*gd'),('math-smoothstep','x',r'(max(0,min(1,x)) : \\(t).(t*t*(3 - 2*t)))')]:
 start=s.index('B("'+name+'"');end=s.index('\n',s.index(');',start))+1;span=s[start:end];assert body in span
 # JS string contains escaped backslashes; decode the literal without executing JS.
 body=json.loads('"'+body+'"');closed='process('+args+') = '+body+';\n';raw=closed.encode();(out/(name+'.dsp')).write_bytes(raw)
 uid='new:faustmod:'+name;text[uid]=normalize_bytes(raw).text
 rows.append(dict(candidate=name,unit_id=uid,source_commit='8f068ddc5851c48c377a025c69a2838c69f68169',source_blob='daca6aff99551ecda542a7491d953e23a9c3ba62',source_lines=[s[:start].count('\n')+1,s[:end].count('\n')],closure_sha256=sha(raw),external_dependencies=[],closure_method='Named process arguments from catalog; exact primitive-only expression; no library calls',teacher_provenance='UNRESOLVED: recent repository commit has AI coauthor; no source-specific generation record',rights='QUARANTINED: repository reports GPL-3.0-or-later; no canonical admission'))
raw=Path('work/pluck-bounded-epoch.dsp').read_bytes();uid='new:pluck_bounded_epoch';text[uid]=normalize_bytes(raw).text;rows.append(dict(candidate='pluck_bounded_epoch',unit_id=uid,source_sha256=sha(raw),external_dependencies=[],admission='NOT_GRANTED'))
raw=Path('work/sk-filter-closure/sk-filter-closed.dsp').read_bytes();uid='new:sk_filter_closed';text[uid]=normalize_bytes(raw).text;rows=[dict(candidate='sk_filter_closed',unit_id=uid,source_sha256=sha(raw),admission='NOT_GRANTED')]

rows=[]
for name in ('single','bounce'):
 raw=Path('work/pm-'+name+'-closure/pm-'+name+'-closed.dsp').read_bytes();uid='new:pm_'+name;text[uid]=normalize_bytes(raw).text;rows.append(dict(candidate='pm_'+name,unit_id=uid,source_sha256=sha(raw),admission='NOT_GRANTED'))

edges=[];f=cluster_families(sorted(text.items()),[x for x in text if x.startswith('comparison:')],evidence=edges);counts=reconstruct(f,edges);comp={f[x] for x in f if x.startswith('comparison:')}
for r in rows:
 uid=r['unit_id'];hits=[e for e in edges if uid in (e.get('left'),e.get('right')) or uid in e.get('contributors',[])];r.update(family=f[uid],comparison_connected=f[uid] in comp,joining_evidence_count=len(hits),joining_evidence=[{k:v for k,v in e.items() if k!='contributors'} for e in hits[:3]])
Path('outputs/blackdog-pm-family.json').write_text(json.dumps(dict(graph=counts,rows=rows,admission='NOT_GRANTED',policy='unchanged floor40 provisional H1 collective'),indent=2)+'\n');print(counts,[(r['candidate'],r['comparison_connected']) for r in rows])

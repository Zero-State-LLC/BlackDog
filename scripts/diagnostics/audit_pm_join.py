from pathlib import Path
import json,difflib,hashlib
exec(compile(Path('work/screen_pm.py').read_text().split('\nedges=[];f=')[0],'population','exec'))
from faustcoder.neardup import tokens
comparison='comparison:2981ea911dcc456b3a154030f3556cc040484857'
b=tokens(text[comparison]);rows=[]
for name in ('single','bounce'):
 uid='new:pm_'+name;a=tokens(text[uid]);match=difflib.SequenceMatcher(None,a,b,autojunk=False).find_longest_match();assert match.size>=40
 closure=json.loads(Path('work/pm-'+name+'-closure/inputs.json').read_text());members=[]
 for symbol,spans in closure['members'].items():
  for span in spans:
   ts=tokens(span['text']);m=difflib.SequenceMatcher(None,ts,b,autojunk=False).find_longest_match()
   if m.size>=40:members.append({'symbol':symbol,'longest_run':m.size,'span_sha256':span['sha256'],'file':span['file'],'start_byte':span['start_byte'],'end_byte':span['end_byte']})
 rows.append({'candidate':uid,'comparison':comparison,'longest_exact_token_run':match.size,'candidate_offset':match.a,'comparison_offset':match.b,'run_sha256':hashlib.sha256(json.dumps(a[match.a:match.a+match.size]).encode()).hexdigest(),'independently_sufficient_dependency_spans':members})
Path('outputs/blackdog-pm-join-audit.json').write_text(json.dumps({'rows':rows,'method':'Longest contiguous raw token matches with autojunk disabled; unchanged 40-token threshold','policy_changed':False},indent=2)+'\n');print(json.dumps(rows,indent=2))

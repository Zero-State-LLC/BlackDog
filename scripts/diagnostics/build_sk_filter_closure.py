from pathlib import Path
import re,json,hashlib
b=Path('work');lib=b/'dependency-review/pinned-libraries';out=b/'sk-filter-closure';out.mkdir(exist_ok=True)
sha=lambda x:hashlib.sha256(x).hexdigest();gitsha=lambda x:hashlib.sha1(b'blob '+str(len(x)).encode()+b'\0'+x).hexdigest();pins=json.loads((b/'ribbon-library-blobs.json').read_text())
def mask(s):return re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"',lambda m:' '*len(m[0]),s)
std=(lib/'stdfaust.lib').read_bytes();assert gitsha(std)==pins['stdfaust.lib']
files=dict(re.findall(r'(\w+)\s*=\s*library\("([^"\n]+)"\)',std.decode()));files['pl']='platform.lib'
index={};raws={};bad=[]
for ns,file in files.items():
 if not (lib/file).exists():continue
 raw=(lib/file).read_bytes()
 if gitsha(raw)!=pins.get(file):bad.append(file);continue
 raws[ns]=raw;s=raw.decode();m=mask(s);depth=0;start=0
 for i,c in enumerate(m):
  if c in '({[':depth+=1
  elif c in ')}]':depth-=1
  elif c==';' and depth==0:
   chunk=m[start:i+1];hit=re.match(r'\s*(?:(?:single|double|quad|fixedpoint)precision\s+)?([A-Za-z_]\w*)\s*(?:\([^;]*|=)',chunk)
   if hit and hit[1] not in ('declare','import','component','library'):
    first=start+len(chunk)-len(chunk.lstrip());text=s[first:i+1]
    if not re.search(r'=\s*library\(',text):
     a=len(s[:first].encode());z=len(s[:i+1].encode());index.setdefault(ns+'.'+hit[1],[]).append(dict(file=file,start_byte=a,end_byte=z,sha256=sha(raw[a:z]),blob_sha=pins[file],text=text))
   start=i+1
source=(b/'sk-filter.dsp').read_bytes();assert gitsha(source)=='3b1a332e63120272cf488186478dc1c20a4f463a'
roots=sorted(set(re.findall(r'\b(?:'+'|'.join(files)+r')\.[A-Za-z_]\w*',mask(source.decode()))));todo=roots[:];seen=set();edges={}
while todo:
 key=todo.pop()
 if key in seen:continue
 seen.add(key)
 if key not in index:continue
 ns=key.split('.')[0];m=mask('\n'.join(x['text'] for x in index[key]));deps=set(re.findall(r'\b(?:'+'|'.join(files)+r')\.[A-Za-z_]\w*',m));names=set(re.findall(r'(?<![.\w])([A-Za-z_]\w*)',m));deps|={ns+'.'+n for n in names if ns+'.'+n in index};deps.discard(key);edges[key]=sorted(deps);todo.extend(deps-seen)
missing=sorted(seen-set(index));pieces=[]
for ns in files:
 defs=[d['text'] for k in sorted(seen) if k.startswith(ns+'.') and k in index for d in index[k]]
 if defs:pieces.append(ns+' = environment {\n'+'\n'.join(defs)+'\n};')
body=source.replace(b'import("stdfaust.lib");',b'// Standard import replaced by exact pinned dependency environments.').decode();assembled='\n'.join(pieces)+'\n'+body
(out/'sk-filter-closed.dsp').write_text(assembled)
r=dict(library_pin='2edec0537f536eaa130d42c354884d7db971663c',pin_selection='Explicit diagnostic pin; upstream sk-engines source did not declare this library revision',origin_commit='d3f6599f76917e98a67992288895395a929598ec',origin_blob=gitsha(source),origin_sha256=sha(source),source_sha256=sha(assembled.encode()),roots=roots,missing=missing,unverified_local_library_files=bad,members={k:index[k] for k in sorted(seen) if k in index},edges=edges,admission='NOT_GRANTED',status='LEXICAL_CLOSURE_PENDING_COMPILER_CHECK')
(out/'inputs.json').write_text(json.dumps(r,indent=2)+'\n');print('members',len(seen),'spans',sum(len(index[k]) for k in seen if k in index),'missing',missing,'unverified',bad,'bytes',len(assembled.encode()));print(sorted(seen))

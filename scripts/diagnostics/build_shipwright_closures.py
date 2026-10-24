from pathlib import Path
import ast,hashlib,json
p=Path('work/shipwright-instruments.py');raw=p.read_bytes();gitsha=lambda x:hashlib.sha1(b'blob '+str(len(x)).encode()+b'\0'+x).hexdigest();assert gitsha(raw)=='bbb0a0d2fe0256de0ebedc1c42c715f734250d63'
tree=ast.parse(raw);out=Path('work/shipwright-sources');out.mkdir(exist_ok=True)
# Interpret only string constants, concatenation and numeric default substitutions; never execute upstream Python.
def value(n,env):
 if isinstance(n,ast.Constant) and isinstance(n.value,(str,int,float)):return n.value
 if isinstance(n,ast.Name):return env[n.id]
 if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Add):return value(n.left,env)+value(n.right,env)
 if isinstance(n,ast.JoinedStr):return ''.join(str(value(x.value,env)) if isinstance(x,ast.FormattedValue) else value(x,env) for x in n.values)
 raise ValueError(ast.dump(n))
base=Path('work/build_ribbon_closure.py').read_text()
for f in tree.body:
 if not isinstance(f,ast.FunctionDef) or f.name not in ('saw_lead','soft_pad','sub_bass','pluck','reverb'):continue
 env={'_HEAD':'import("stdfaust.lib");\n'};env.update({a.arg:value(v,{}) for a,v in zip(f.args.args[-len(f.args.defaults):],f.args.defaults)})
 if f.name=='reverb':source=value(f.body[0].value,env)
 else:source=value(next(n.value for n in f.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='dsp' for t in n.targets)),env)
 raw=source.encode();(out/(f.name+'.dsp')).write_bytes(raw)
 code=base.replace("out=b/'ribbon-closure'","out=b/'shipwright-"+f.name+"-closure'").replace("b/'evaluation-search/ribbon.dsp'","b/'shipwright-sources/"+f.name+".dsp'").replace('af146e17caaf28dccbe4ee04cc8d65ae5858576b',gitsha(raw)).replace('a793afc33dc0b0854e5ca8a34c22e9d98a125b73','eef7b31e2b82974172d8c562412069624861950a').replace('ribbon-closed.dsp',f.name+'-closed.dsp').replace('upstream Ribbon source','upstream Shipwright source').replace('ribbon_commit','origin_commit').replace('ribbon_blob','extracted_dsp_blob').replace('ribbon_sha256','extracted_dsp_sha256')
 exec(compile(code,'closure-'+f.name,'exec'),{})

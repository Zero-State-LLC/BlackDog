from pathlib import Path
import hashlib,json,re
p=Path('work/bitdsp-source/bitDSP.lib');raw=p.read_bytes();gitsha=lambda b:hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();sha=lambda b:hashlib.sha256(b).hexdigest();assert gitsha(raw)=='070e285172c27aa355a00cccbf16b8819882c380'
rows=[];definitions={}
for name in ('full_adder','bitstream_adder'):
 a=raw.index((name+'(x1, x2').encode());z=raw.index(b'\n// ---',a);span=raw[a:z].rstrip();definitions[name]=span;rows.append(dict(name=name,start_byte=a,end_byte=a+len(span),sha256=sha(span),source_blob=gitsha(raw)))
for name in definitions:
 body=definitions['full_adder']+(b'\n'+definitions[name] if name!='full_adder' else b'');Path('work/bitdsp-source/'+name+'-closed.dsp').write_bytes(body+b'\nprocess = '+name.encode()+b';\n')
Path('outputs/blackdog-bitdsp-candidates.json').write_text(json.dumps(dict(repo='rottingsounds/bitDSP-faust',commit='d70843492b65bb2cb9cf97c2240905fefacc7383',file='lib/bitDSP.lib',rows=rows,dependencies='full_adder: Faust builtins only; bitstream_adder: exact full_adder plus builtins',license='MIT root with per-function Dario Sanfilippo author comments; canonical rights review pending',admission='NOT_GRANTED'),indent=2)+'\n');print(rows)

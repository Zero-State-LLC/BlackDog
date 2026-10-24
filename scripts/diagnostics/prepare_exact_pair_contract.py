from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,'work/BlackDog')
from faustcoder.modular_pairs import review
from faustcoder.pair_preflight import LocalTokenizer,TOKENIZER_HASHES,inspect_encodings
from faustcoder.canonical import canonical_bytes
sha=lambda b:hashlib.sha256(b).hexdigest()
old=json.loads(Path('work/presplit-pair-proposal/pair.json').read_text());source=Path('work/paired-presplit-coefficients.dsp').read_bytes();target=old['target'].encode();assert source.count(target)==1;a=source.index(target)
prompt='''Write only mulk(ah,al,asplit,arest,ch,cl) in Faust for the pinned paired-float filter context. Supplied interfaces: r(x) clamps to [-1e30,1e30]; renorm(high,low) returns a normalized pair. Constant (ah,al) has precomputed splitter parts asplit,arest; do not split ah again. Define p=r(ah*ch), cc=r(4097*ch), csplit=r(cc-r(cc-ch)), crest=r(ch-csplit). For the residual, compute q0=r(r(asplit*csplit)-p), q1=r(q0+r(asplit*crest)), q2=r(q1+r(arest*csplit)), q3=r(q2+r(arest*crest)), then err=r(q3+r(r(ah*cl)+r(al*ch))). Inline q0..q3 as nested expressions and return (r(ah*ch),err):renorm. Do not add al*cl or change the operation order. Use the supplied helpers at runtime; do not assume clamps enforce float32 rounding during constant folding. Scope: pinned filter coefficients in the verified analyzer domain, not arbitrary-range multiplication.\n'''
out=Path('work/presplit-pair-v2');out.mkdir(exist_ok=True);parts={'prompt':prompt.encode(),'target':target,'prefix':source[:a],'suffix':source[a+len(target):]}
contract=dict(kind='modular-public-pair.v1',unit_id='repair-module:ds.mulk',target_symbol='mulk',dependency_interfaces=['r(x)','renorm(high,low)'])
for k,v in parts.items():
 name=k+('.txt' if k=='prompt' else '.dsp');(out/name).write_bytes(v);contract[k]=dict(path=name,sha256=sha(v))
raw=json.dumps(contract,indent=2).encode()+b'\n';(out/'contract.json').write_bytes(raw);result=review(raw,out,expected_harness_sha256='d4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e')
pair=dict(example_id=contract['unit_id'],prompt=prompt,target=target.decode(),prompt_digest='sha256:'+sha(prompt.encode()),target_digest='sha256:'+sha(target));pair['pair_digest']='sha256:'+sha(canonical_bytes({k:pair[k] for k in ('example_id','prompt','target_digest')}));(out/'pair.json').write_text(json.dumps(pair,indent=2)+'\n')
assets={n:(Path('work/qwen-tokenizer')/n).read_bytes() for n in TOKENIZER_HASHES};assert all(sha(v)==TOKENIZER_HASHES[n] for n,v in assets.items());result['tokenizer']=inspect_encodings((pair,),LocalTokenizer(assets));result['contract_sha256']=sha(raw);result['previous_prompt_sha256']=old['prompt_digest'];result['semantic_review']='Agent-reviewed exact operation-order clarification; not independent human approval';result['target_unchanged']=pair['target_digest']==old['target_digest'];Path('outputs/blackdog-exact-pair-contract.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

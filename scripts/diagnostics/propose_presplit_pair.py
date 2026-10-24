from pathlib import Path
import sys,hashlib,json
sys.path.insert(0,'work/BlackDog')
from faustcoder.pair_preflight import LocalTokenizer,TOKENIZER_HASHES,inspect_encodings
from faustcoder.canonical import canonical_bytes
sha=lambda x:hashlib.sha256(x).hexdigest()
source=Path('work/paired-presplit-coefficients.dsp').read_bytes();assert sha(source)=='d4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e'
a=source.index(b' mulk(');b=source.index(b'\n };',a)+4;target=source[a:b].decode();marker=b'/* EXACT_REPAIRED_TARGET */';assert marker not in source
context=source[:a]+marker+source[b:];assert context.replace(marker,target.encode())==source
prompt='''Write the Faust helper mulk(ah,al,asplit,arest,ch,cl) for the pinned paired-float elliptic-filter context. Helpers r(x) (finite float32 rounding barrier) and renorm(high,low) are supplied. The constant operand is (ah,al); asplit and arest are its precomputed float32 Dekker split. Split the variable high operand ch at runtime using factor 4097. Compute the high product ah*ch and its residual from the four split products, then add ah*cl and al*ch with the supplied rounding barriers and renormalize. Preserve the reference operation order; do not split ah again or add an al*cl term. Return this helper definition only. Scope is the pinned filter coefficients and tested analyzer domain, not arbitrary-range paired multiplication.\n'''
pair=dict(example_id='repair-module:ds.mulk',prompt=prompt,target=target,prompt_digest='sha256:'+sha(prompt.encode()),target_digest='sha256:'+sha(target.encode()));pair['pair_digest']='sha256:'+sha(canonical_bytes({k:pair[k] for k in ('example_id','prompt','target_digest')}))
assets={n:(Path('work/qwen-tokenizer')/n).read_bytes() for n in TOKENIZER_HASHES};assert all(sha(v)==TOKENIZER_HASHES[n] for n,v in assets.items());enc=inspect_encodings((pair,),LocalTokenizer(assets))
out=Path('work/presplit-pair-proposal');out.mkdir(exist_ok=True);(out/'pair.json').write_text(json.dumps(pair,indent=2)+'\n');(out/'context.dsp').write_bytes(context)
report=dict(status='PROPOSED_EXACT_REPAIR_TARGET_NOT_QUALIFIED',unit_id=pair['example_id'],target_sha256=sha(target.encode()),prompt_sha256=sha(prompt.encode()),dependency_context_sha256=sha(context),assembled_sha256=sha(source),target_span=[a,b],reconstruction_exact=True,tokenizer=enc,numerical_scope='Full assembled source verified by retained 149-job matrix; standalone generic multiplication not qualified',full_closure_family_report='presplit-closure-family-2026-10-24.json',remaining=['independent prompt semantic review','canonical repaired-source rights and admission','signed partition membership','comparison-connected complete closure'],admission='NOT_GRANTED',training_authorized=False)
Path('outputs/blackdog-presplit-pair-proposal.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

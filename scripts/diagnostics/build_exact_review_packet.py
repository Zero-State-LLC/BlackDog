from pathlib import Path
import json,sys,hashlib
sys.path.insert(0,'work/BlackDog')
from diagnostics.exact_pair_review import bind_exact_pair
from diagnostics.repaired_closure_review import bind_review
from faustcoder.modular_pairs import review
root=Path('work/BlackDog/docs/analysis');names=dict(rights='repaired-closure-rights',family='presplit-closure-family',wasm='presplit-wasm-verification',modular='presplit-modular-verification',contracts='original-modular-target-bindings')
raw={k:(root/(v+'-2026-10-24.json')).read_bytes() for k,v in names.items()};closure=bind_review(**{k:json.loads(v) for k,v in raw.items()})
contract=json.loads(Path('outputs/blackdog-exact-pair-contract.json').read_bytes());path=Path('work/presplit-pair-v2').resolve();replayed=review((path/'contract.json').read_bytes(),path,expected_harness_sha256=closure['source_sha256'])
assert all(contract[k]==v for k,v in replayed.items())
products=json.loads(Path('outputs/blackdog-mulk-constant-verification.json').read_bytes());packet=bind_exact_pair(contract,products,closure)
raw.update(exact_contract=(path/'contract.json').read_bytes(),contract_report=Path('outputs/blackdog-exact-pair-contract.json').read_bytes(),product_verification=Path('outputs/blackdog-mulk-constant-verification.json').read_bytes(),prompt_order=Path('outputs/blackdog-prompt-order-verification.json').read_bytes())
packet['input_sha256']={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
dependency=Path('outputs/blackdog-exact-dependency-context.json').read_bytes()
assert json.loads(dependency)['source_sha256']==packet['assembled_sha256']
packet['input_sha256']['direct_dependency_context']=hashlib.sha256(dependency).hexdigest()
packet['source_of_semantic_approval']='ABSENT; automated consistency and agent review cannot populate this field'
Path('outputs/blackdog-exact-review-packet.json').write_text(json.dumps(packet,indent=2)+'\n');print(packet['status'])

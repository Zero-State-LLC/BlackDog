from pathlib import Path
import tempfile,shutil,json,sys,hashlib
sys.path.insert(0,'work/BlackDog')
from faustcoder.modular_pairs import review
from faustcoder.readiness_manifest import ManifestError
base=Path('work/presplit-pair-v2');expected='d4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e';rows=[]
for mutation in ['identity','digest','rebind_context','target','interface','symbol','leak','path','admitted']:
 with tempfile.TemporaryDirectory() as td:
  root=Path(td).resolve();shutil.copytree(base,root,dirs_exist_ok=True);v=json.loads((root/'contract.json').read_text())
  def replace(k,data):
   (root/v[k]['path']).write_bytes(data);v[k]['sha256']=hashlib.sha256(data).hexdigest()
  if mutation=='digest':v['target']['sha256']='0'*64
  if mutation=='rebind_context':replace('prefix',(root/'prefix.dsp').read_bytes()+b'// rebound\n')
  if mutation=='target':replace('target',(root/'target.dsp').read_bytes().replace(b'4097',b'4096'))
  if mutation=='interface':v['dependency_interfaces']=['other(x)']
  if mutation=='symbol':v['target_symbol']='other'
  if mutation=='leak':replace('prompt',(root/'prompt.txt').read_bytes()+(root/'target.dsp').read_bytes())
  if mutation=='path':v['prefix']['path']='../outside'
  if mutation=='admitted':v['admitted']=True
  try:
   result=review(json.dumps(v).encode(),root,expected_harness_sha256=expected)
   assert mutation=='identity' and not result['qualified'] and not result['training_authorized'];rows.append({'case':mutation,'result':'STRUCTURALLY_VERIFIED_NOT_QUALIFIED'})
  except (ManifestError,ValueError) as exc:
   assert mutation!='identity';rows.append({'case':mutation,'result':'REJECTED','reason':str(exc)})
Path('outputs/blackdog-exact-contract-mutations.json').write_text(json.dumps(rows,indent=2)+'\n');print('Identity passes; eight altered contracts rejected')

import json,hashlib,datetime,sys,re,shutil,socket,os
from pathlib import Path
# Parameterized for the public repo (original ran with fixed host paths).
# BLACKDOG_REPO: BlackDog checkout (default: two levels above this file).
# BLACKDOG_EVIDENCE_ROOT: folder holding the Slice 2 evidence dirs (default: parent of BLACKDOG_REPO).
# BLACKDOG_EXPECTED_HOST: optional; if set, refuse to run on any other hostname.
# BLACKDOG_REVIEWER_NAME: required; the named independent human reviewer recorded in approval.json.
REPO=Path(os.environ.get("BLACKDOG_REPO",Path(__file__).resolve().parents[2]))
ROOT=Path(os.environ.get("BLACKDOG_EVIDENCE_ROOT",REPO.parent))
sys.path.insert(0,str(REPO))
import faustcoder.compiler as compiler
from faustcoder.sandbox import ResourceLimits
base=ROOT/"blackdog-pdfaustgen-review-20261022T051034Z"
approval=ROOT/"blackdog-seven-contract-approval-20261022T053119Z"/"approval.json"
out=(ROOT/("blackdog-seven-dependencies-"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")));out.mkdir()
if os.environ.get("BLACKDOG_EXPECTED_HOST"): assert socket.gethostname()==os.environ["BLACKDOG_EXPECTED_HOST"]
a=json.loads(approval.read_text());shutil.copy2(approval,out/"approval.json")
orig=compiler._build; current=None
def capture(*args,**kwargs):
 for name,data in kwargs.get("outputs",[]):
  (current/Path(name).name).write_bytes(data)
 return orig(*args,**kwargs)
compiler._build=capture
def run(src,label,native=False,ok=True):
 global current
 current=out/label;current.mkdir();(current/"source.dsp").write_bytes(src.encode())
 result=(compiler.compile_native if native else compiler.compile_source)(src,limits=ResourceLimits(timeout_s=60))
 (current/"compiler.json").write_text(json.dumps(result.receipt,indent=2))
 (current/"diagnostics.txt").write_text(result.diagnostics)
 actual=result.receipt["exit_code"]==0
 assert actual==ok,(label,result.receipt,result.diagnostics)
 print(label,"PASS" if actual else "EXPECTED_REJECTION",flush=True)
 return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in current.iterdir() if p.name not in ["source.dsp","compiler.json","diagnostics.txt"]}
results=[]
for binding in a["contracts"]:
 uid=binding["unit_id"];cpath=base/binding["contract_filename"];cb=cpath.read_bytes()
 assert hashlib.sha256(cb).hexdigest()==binding["contract_sha256"]
 c=json.loads(cb);raw=(base/"sources"/(uid+".dsp")).read_bytes()
 assert "sha256:"+hashlib.sha256(raw).hexdigest()==binding["source_sha256"]
 assert hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==binding["source_blob"]
 source=raw.decode()
 corrected=dict(c);corrected["independent_human_reviewer"]=os.environ["BLACKDOG_REVIEWER_NAME"];corrected["status"]="HUMAN_APPROVED_BEHAVIOR_PENDING_TECHNICAL_VALIDATION"
 if uid=="u017e8346c741c864edc1":corrected["declared_import_scope"]='stdfaust.lib declared; no member referenced in target; import-removal equivalence required'
 corrected["approval_binding"]=hashlib.sha256(approval.read_bytes()).hexdigest()
 (out/(uid+".contract.CORRECTED.json")).write_text(json.dumps(corrected,indent=2))
 original=run(source,uid+"-original")
 run(source,uid+"-native",native=True)
 imports=re.findall(r'import\("([^"]+)"\);',source)
 helpers=re.findall(r'(?m)^\s*(gain[1-4]?|param[1-4])\s*=.*?;',source)
 negatives=[]
 for helper in helpers:
  altered,n=re.subn(r'(?m)^\s*'+re.escape(helper)+r'\s*=.*?;',"",source);assert n==1
  run(altered,uid+"-remove-"+helper,ok=False);negatives.append(helper)
 equivalence=None
 if imports:
  assert imports==["stdfaust.lib"]
  removed=source.replace('import("stdfaust.lib");',"",1)
  other=run(removed,uid+"-without-import")
  run(removed,uid+"-without-import-native",native=True)
  run(source.replace('import("stdfaust.lib");','import("blackdog_missing_dependency_control.lib");',1),uid+"-missing-import",ok=False)
  equivalence={"original_artifacts":original,"removed_artifacts":other,"exact_artifact_equality":bool(original) and original==other,"semantic_render":"PENDING","missing_import_rejected":True}
 results.append({"unit_id":uid,"path":binding["path"],"imports":imports,"local_helpers":helpers,"helper_removal_rejected":negatives,"import_equivalence":equivalence,"external_members":[],"foreign_resources":[],"production_approved":False})
(out/"summary.json").write_text(json.dumps({"units":results,"rights_and_leakage":"UNRESOLVED","TOKEN_FLOOR":40,"floor_status":"provisional","T07_frozen":False},indent=2))
shutil.copy2(__file__,out/"driver.py")
print("OUTPUT",out,flush=True)


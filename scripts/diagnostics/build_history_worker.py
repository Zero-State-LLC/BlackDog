"""Create an isolated diagnostic worker; never edit the production render worker."""
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]);worker=root/'faust/worker';base=(worker/'render.mjs').read_text();s=base
s="import {beginCheckpoint, finishCheckpoint} from './history-checkpoint.mjs';\n"+s
s=s.replace('  let diagnosticInfo;','  let diagnosticInfo;\n  let historyInfo;')
old='      const processor = await generator.createOfflineProcessor(sampleRate, blockSize);'
assert s.count(old)==1
s=s.replace(old,old+"\n      const historyHandle=beginCheckpoint(processor,request,workdir,{faustwasm:FAUSTWASM_VERSION,libfaust:libfaustVersion,libraries:libraryTreeSha256,node:process.version,v8:process.versions.v8});")
old='      const fileName = `out-${name}.f32`;';assert s.count(old)==1
s=s.replace(old,'      historyInfo=finishCheckpoint(historyHandle,workdir);\n'+old)
s=s.replace('    frames,\n    stimuli: written,','    frames,\n    history: historyInfo,\n    stimuli: written,')
assert s.count('history: historyInfo')==1
(worker/'history-render.mjs').write_text(s)
sha=lambda b:hashlib.sha256(b).hexdigest()
print(json.dumps(dict(base_sha256=sha(base.encode()),history_worker_sha256=sha(s.encode()))))

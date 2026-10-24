import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {beginCheckpoint,finishCheckpoint,digest} from '../../scripts/diagnostics/history-checkpoint.mjs';
const source=readFileSync(process.argv[2],'utf8'),dir=mkdtempSync(join(tmpdir(),'checkpoint-check-'));
const proc=()=>({fDSPCode:{fDSP:0,fSampleSize:4,fSoundfiles:[],fJSONDsp:{size:32},fInstance:{json:'{"size":32}',memory:new WebAssembly.Memory({initial:1})}}});
const initial=()=>({source,options:['-ftz','0'],sample_rate:48000,block_size:64,frames:64,stimuli:['sine'],history:{sequence_id:'a'.repeat(64),chunk_index:0,start_frame:0,parent_sha256:null}});
let checks=0;const reject=(fn,pattern)=>{assert.throws(fn,pattern);checks++;};
try {
 const a=proc();new Uint8Array(a.fDSPCode.fInstance.memory.buffer,0,32).fill(17);finishCheckpoint(beginCheckpoint(a,initial(),dir,{version:'pinned'}),dir);
 const raw=readFileSync(join(dir,'checkpoint-out.json'));writeFileSync(join(dir,'checkpoint-in.json'),raw);
 const next=()=>({...initial(),history:{sequence_id:'a'.repeat(64),chunk_index:1,start_frame:64,parent_sha256:digest(raw)}});
 const b=proc();beginCheckpoint(b,next(),dir,{version:'pinned'});assert.deepEqual([...new Uint8Array(b.fDSPCode.fInstance.memory.buffer,0,32)],Array(32).fill(17));checks++;
 reject(()=>beginCheckpoint(proc(),{...next(),sample_rate:44100},dir,{version:'pinned'}),/binding mismatch/);
 reject(()=>beginCheckpoint(proc(),{...next(),history:{...next().history,sequence_id:'b'.repeat(64)}},dir,{version:'pinned'}),/binding mismatch/);
 reject(()=>beginCheckpoint(proc(),{...next(),history:{...next().history,parent_sha256:'0'.repeat(64)}},dir,{version:'pinned'}),/chain mismatch/);
 reject(()=>beginCheckpoint(proc(),{...initial(),frames:144064},dir,{}),/invalid history contract/);
 reject(()=>beginCheckpoint(proc(),{...initial(),source:'process=_;'},dir,{}),/invalid history contract/);
 reject(()=>beginCheckpoint(proc(),{...initial(),options:['-ftz','1']},dir,{}),/invalid history contract/);
 reject(()=>beginCheckpoint(proc(),{...initial(),sample_rate:32000},dir,{}),/invalid history contract/);
 reject(()=>beginCheckpoint(proc(),{...next(),history:{...next().history,start_frame:128}},dir,{version:'pinned'}),/binding mismatch/);
 const bad=proc();bad.fDSPCode.fSoundfiles=['external'];reject(()=>beginCheckpoint(bad,initial(),dir,{}),/unsupported checkpoint layout/);
 const corrupted=JSON.parse(raw);corrupted.state_base64=Buffer.alloc(32).toString('base64');const changed=Buffer.from(JSON.stringify(corrupted));writeFileSync(join(dir,'checkpoint-in.json'),changed);
 reject(()=>beginCheckpoint(proc(),{...next(),history:{...next().history,parent_sha256:digest(changed)}},dir,{version:'pinned'}),/state mismatch/);
 console.log(JSON.stringify({passed:checks}));
} finally {rmSync(dir,{recursive:true,force:true});}

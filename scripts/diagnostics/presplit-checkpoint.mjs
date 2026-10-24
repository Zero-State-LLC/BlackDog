// Diagnostic-only adapter for the pinned mono, float32, soundfile-free fixture.
import {readFileSync, writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
export const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const SOURCE = 'd4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e';
export function beginCheckpoint(proc, request, workdir, runtime) {
  const h=request.history, dsp=proc.fDSPCode;
  if (!h || !/^[a-f0-9]{64}$/.test(h.sequence_id) || !Number.isInteger(h.chunk_index) || h.chunk_index<0 || h.chunk_index>4 || !Number.isInteger(h.start_frame) || h.start_frame<0 || h.start_frame%64 || request.block_size!==64 || ![44100,48000,96000,192000].includes(request.sample_rate) || JSON.stringify(request.options)!=='["-ftz","0"]' || request.stimuli.length!==1 || request.frames<64 || request.frames>144000 || request.frames%64 || digest(request.source)!==SOURCE) throw Error('invalid history contract');
  const size=dsp?.fJSONDsp?.size;
  if (dsp?.fDSP!==0 || dsp.fSampleSize!==4 || !Array.isArray(dsp.fSoundfiles) || dsp.fSoundfiles.length || !Number.isInteger(size) || size<1 || size>1024*1024 || !(dsp.fInstance.memory instanceof WebAssembly.Memory)) throw Error('unsupported checkpoint layout');
  const binding={source_sha256:SOURCE,sample_rate:request.sample_rate,block_size:64,sequence_id:h.sequence_id,json_sha256:digest(dsp.fInstance.json),size,runtime};
  let parent=null;
  if (h.chunk_index===0) {
    if(h.start_frame!==0 || h.parent_sha256!==null) throw Error('invalid initial checkpoint');
  } else {
    const raw=readFileSync(join(workdir,'checkpoint-in.json'));
    if(raw.length>2*1024*1024 || digest(raw)!==h.parent_sha256) throw Error('checkpoint chain mismatch');
    const cp=JSON.parse(raw);
    if(JSON.stringify(cp.binding)!==JSON.stringify(binding) || cp.chunk_index!==h.chunk_index-1 || cp.end_frame!==h.start_frame) throw Error('checkpoint binding mismatch');
    const state=Buffer.from(cp.state_base64,'base64');
    if(state.length!==size || digest(state)!==cp.state_sha256) throw Error('checkpoint state mismatch');
    new Uint8Array(dsp.fInstance.memory.buffer,0,size).set(state);parent=digest(raw);
  }
  return {binding,dsp,history:h,frames:request.frames,parent};
}
export function finishCheckpoint(handle,workdir) {
  const {binding,dsp,history:h,frames,parent}=handle;
  const state=Buffer.from(new Uint8Array(dsp.fInstance.memory.buffer,0,binding.size));
  const cp={binding,chunk_index:h.chunk_index,start_frame:h.start_frame,end_frame:h.start_frame+frames,parent_sha256:parent,state_sha256:digest(state),state_base64:state.toString('base64')};
  const raw=Buffer.from(JSON.stringify(cp));writeFileSync(join(workdir,'checkpoint-out.json'),raw);
  return {chunk_index:cp.chunk_index,start_frame:cp.start_frame,end_frame:cp.end_frame,parent_sha256:parent,state_sha256:cp.state_sha256,checkpoint_sha256:digest(raw),state_bytes:binding.size};
}

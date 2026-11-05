import assert from 'node:assert/strict';
import {validateDiagnostic,renderDiagnostic} from '../faust/worker/diagnostic-cases.mjs';
const desc=[{type:'hslider',address:'/g',min:0,max:1,step:.25},{type:'button',address:'/b'}];
const make=(controls=[])=>({version:1,case_id:'c',controls,input_stimuli:['sine','noise','alternating'],zero_companion:null});
const event=(block,address,value)=>({block,address,value});
for(const e of [event(-1,'/g',0),event(.5,'/g',0),event(3,'/g',0),event(0,'/g',NaN),event(0,'/g',Infinity),event(0,'/g',.3),event(0,'/g',2),event(0,'/bad',0),event(0,'/b',1)]) assert.throws(()=>validateDiagnostic(make([e]),desc,12,4,3,true));
assert.throws(()=>validateDiagnostic(make([event(0,'/g',0),event(0,'/g',1)]),desc,12,4,3,false));
assert.throws(()=>validateDiagnostic(make(),desc,12,4,2,false));
let g=1,b=0,stopped=false;
const proc={getNumInputs:()=>3,getNumOutputs:()=>1,start(){},stop(){stopped=true;},setParamValue(a,v){if(a==='/g')g=v;else b=v;},compute(ins,outs){for(let i=0;i<4;i++)outs[0][i]=(ins[0][i]+ins[2][i])*g+b;return true;}};
const events=[event(0,'/b',1),event(0,'/g',.25),event(2,'/g',.5)];
validateDiagnostic(make(events),desc,12,4,3,false);
const inputs=[new Float32Array(12).fill(1),new Float32Array(12).fill(99),new Float32Array(12).fill(3)];
const result=renderDiagnostic(proc,inputs,12,4,['/b'],false,events);
assert.deepEqual(Array.from(result.channels[0]),[...Array(8).fill(2),...Array(4).fill(3)]);
assert.deepEqual(result.applied,events);assert.ok(stopped);
inputs[0][0]=NaN;assert.throws(()=>renderDiagnostic(proc,inputs,12,4,[],false,[]));
const generator={...proc,getNumInputs:()=>0,compute(ins,outs){assert.equal(ins.length,0);outs[0].fill(.25);return true;}};
validateDiagnostic({...make(),input_stimuli:[]},[],12,4,0,false);
assert.equal(renderDiagnostic(generator,[],12,4,[],false,[]).channels[0][0],.25);
console.log('worker controls, persistence, boundary rejection, routing and zero-input checks passed');

// Compiler-valid fixture checks are portable; Linux Python integration separately
// exercises the real namespace/resource boundary and paired-case receipt gate.
const {fileURLToPath}=await import('node:url');
const {FaustCompiler,LibFaust,FaustMonoDspGenerator,instantiateFaustModuleFromFile}=await import('../faust/worker/node_modules/@grame/faustwasm/dist/esm/index.js');
const runtime=fileURLToPath(new URL('../faust/worker/node_modules/@grame/faustwasm/libfaust-wasm/libfaust-wasm.js',import.meta.url));
const compiler=new FaustCompiler(new LibFaust(await instantiateFaustModuleFromFile(runtime)));
for(const rate of [44100,48000]) {
  for(const [source,controlEvents,inputNames,expected] of [
    ['process=_*hslider("gain",1,0,1,.25);',[event(0,'/input/gain',.25),event(2,'/input/gain',.5),event(3,'/input/gain',.75)],['alternating'],i=>(i%2?-.25:.25)*(i<128?.25:i<192?.5:.75)],
    ['process=_*button("gate");',[event(0,'/input/gate',1),event(1,'/input/gate',0),event(3,'/input/gate',1)],['alternating'],i=>(i<64||i>=192)?(i%2?-.25:.25):0],
    ['g=hslider("gain",1,0,1,.25); process=attach(_*0,g);',[event(0,'/input/gain',.5)],['alternating'],()=>0],
    ['process=_,!,_:+;',[],['sine','noise','alternating'],i=>(i%2?-.25:.25)*4],
    ['process=.25;',[],[],()=>.25],
  ]) {
    const generator=new FaustMonoDspGenerator();
    assert.ok(await generator.compile(compiler,'input',source,'-ftz 0'));
    const processor=await generator.createOfflineProcessor(rate,64);
    try {
      const spec={version:1,case_id:'compiled',controls:controlEvents,input_stimuli:inputNames,zero_companion:null};
      validateDiagnostic(spec,processor.getDescriptors(),256,64,processor.getNumInputs(),false);
      const channels=inputNames.map((_,index)=>Float32Array.from({length:256},(_,i)=>(i%2?-.25:.25)*(index+1)));
      const result=renderDiagnostic(processor,channels,256,64,[],false,controlEvents);
      assert.ok(result.channels[0].every((value,i)=>value===expected(i)), "compiled output differs from arithmetic reference");
      if(source.includes('attach')) assert.notDeepEqual(Array.from(result.channels[0]),Array.from({length:256},(_,i)=>(i%2?-.125:.125)));
    } finally {processor.destroy();}
  }
}
console.log('10 compiler-valid fixtures passed at both rates, including preserved-UI always-zero mutant');

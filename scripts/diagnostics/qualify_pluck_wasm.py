from pathlib import Path
import sys,json,hashlib,struct,math,dataclasses
from faustcoder.signal import SignalProfile,SignalReference,run_signal,_render
from faustcoder.diagnostic_cases import DiagnosticCase,ControlEvent
from faustcoder.compiler import runtime_pin
from faustcoder.sandbox import ResourceLimits
import faustcoder.signal as signal
root=Path('/home/delphi/blackdog-pair-qualification-m8e1n43a');sys.argv=['qualify_designing_closures.py','bitcrush'];ns={'__file__':str(root/'qualify_designing_closures.py')};exec((root/'qualify_designing_closures.py').read_text().split('rows=[]')[0],ns);run=ns['run'];out=root/'pluck-wasm-check';out.mkdir(exist_ok=True);source=(root/'pluck-single-loop.dsp').read_text();sha=lambda b:hashlib.sha256(b).hexdigest();run(['faust','-single','-ftz','0','-cn','Probe',str(root/'pluck-single-loop.dsp'),'-o',str(out/'generated.hpp')])
base=(root/'pluck-single-loop-check/driver.cpp').read_text().split('int main(')[0];driver=base+'''int main(int argc,char**argv){if(argc!=3)return 2;Probe dsp;dsp.init(std::stoi(argv[1]));UI ui;dsp.buildUserInterface(&ui);if(!ui.freq||!ui.gain||!ui.gate||dsp.getNumInputs()!=0||dsp.getNumOutputs()!=2)return 3;std::ofstream out(argv[2],std::ios::binary);float x[64],y[64];float* outs[]={x,y};for(int b=0;b<2048;b++){*ui.freq=b<1280?440.f:b<1536?8000.f:20.f;*ui.gain=b<1024?.5f:.25f;*ui.gate=(b>=1&&b<512)||(b>=1024&&b<1792);dsp.compute(64,nullptr,outs);for(int i=0;i<64;i++){out.write((char*)(x+i),4);out.write((char*)(y+i),4);}}return out.good()?0:4;}
''';(out/'driver.cpp').write_text(driver);run(['g++','-O1','-ffp-contract=off','-fno-fast-math',str(out/'driver.cpp'),'-o',str(out/'render')])
captured={};descriptors=[];original=signal._read_outputs
def capture(*a,**k):
 result=original(*a,**k);captured.clear();captured.update(result);descriptors[:]=a[1].get('diagnostic_case',{}).get('descriptors',[]);return result
signal._read_outputs=capture
p=SignalProfile(48000,frames=64,head_frames=64,max_frames=64,block_size=64,stimuli=('impulse',),expected_channels=2,press_buttons_first_block=False,diagnostic_case=DiagnosticCase('pluck-probe',(),()))
_render(source,p,options=('-ftz','0'),limits=ResourceLimits())
def leaves(items):
 for d in items:
  if 'address' in d:yield d
  yield from leaves(d.get('items',[]))
addresses={d['label']:d['address'] for d in leaves(descriptors)};assert all(k in addresses for k in ('freq','gain','gate')),descriptors
controls=tuple(ControlEvent(b,addresses[k],v) for k,events in {'freq':[(0,440),(1280,8000),(1536,20)],'gain':[(0,.5),(1024,.25)],'gate':[(0,0),(1,1),(512,0),(1024,1),(1792,0)]}.items() for b,v in events);controls=tuple(sorted(controls,key=lambda e:e.block))
rows=[]
for sr in (44100,48000,96000,192000):
 path=out/f'{sr}-native.bin';run([str(out/'render'),str(sr),str(path)]);raw=path.read_bytes();vals=struct.unpack('<'+'f'*(len(raw)//4),raw);wanted=[list(vals[c::2]) for c in (0,1)]
 p=SignalProfile(sr,frames=131072,head_frames=131072,max_frames=131072,block_size=64,stimuli=('impulse',),expected_channels=2,press_buttons_first_block=False,diagnostic_case=DiagnosticCase('pluck-live-wasm',controls,()))
 result=run_signal(source,p,SignalReference(sr,64,131072,p.seed,p.stimuli,2,{'impulse':wanted}),options=('-ftz','0'));actual=captured['impulse'];(out/f'{sr}-wasm.bin').write_bytes(b''.join(struct.pack('<ff',x,y) for x,y in zip(*actual)));maxerr=max(abs(x-y) for a,b in zip(actual,wanted) for x,y in zip(a,b));rows.append(dict(sample_rate=sr,passed=result.receipt['passed'],failures=list(result.failures),max_absolute_error=maxerr,native_sha256=sha(raw),wasm_sha256=sha((out/f'{sr}-wasm.bin').read_bytes()),receipt=result.receipt,compiler=result.compilation.receipt));print(sr,rows[-1]['passed'],maxerr,flush=True)
(out/'report.json').write_text(json.dumps(dict(rows=rows,source_sha256=sha(source.encode()),runner_sha256=sha(Path(__file__).read_bytes()),runtime_pin=dataclasses.asdict(runtime_pin()),admission='NOT_GRANTED'),indent=2)+'\n')

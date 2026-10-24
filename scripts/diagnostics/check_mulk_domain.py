"""Check probe intermediates and omitted low-low term; not arbitrary-domain proof."""
from pathlib import Path
import json,runpy,hashlib,math
from decimal import Decimal,localcontext
assert hashlib.sha256(Path('work/paired-presplit-coefficients.dsp').read_bytes()).hexdigest()=='d4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e'
ns=runpy.run_path('work/check_prompt_order.py');model=ns['model'];original=model.__globals__['barrier'];peak=0.;clamps=0;calls=0
# Instrument the separately transcribed prompt model without changing compiled source.
def observed(x):
 global peak,clamps,calls
 assert math.isfinite(x);peak=max(peak,abs(x));clamps+=abs(x)>ns['f'](1e30);calls+=1
 return original(x)
model.__globals__['barrier']=observed;omitted=Decimal(0);count=0
with localcontext() as ctx:
 ctx.prec=80;D=Decimal.from_float
 for row in ns['r']['rows']:
  if row['variant']!='exact':continue
  for c,d in ns['inputs']:
   for ah,al,a,b in row['coefficients']:
    model(ah,al,a,b,c,d);ref=(D(ah)+D(al))*(D(c)+D(d));omitted=max(omitted,abs(D(al)*D(d))/(Decimal('1e-30')+Decimal('1e-12')*abs(ref)));count+=1
assert count==41328 and clamps==0 and omitted<1
saved=(peak,clamps,calls);observed(1e31);assert clamps==1
peak,clamps,calls=saved
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=dict(status='BOUNDED_PROBE_DOMAIN_CHECK_PASS',products=count,observed_clamp_calls=calls,clamp_activations=clamps,instrumentation_overrange_control_detected=True,max_preclamp_magnitude=peak,omitted_low_low_max_tolerance_ratio=float(omitted),source_sha256=sha('work/paired-presplit-coefficients.dsp'),prompt_model_sha256=sha('work/check_prompt_order.py'),input_sha256=sha('work/mulk-constants-evidence/mulk-constants/inputs.bin'),coefficient_report_sha256=sha('work/mulk-constants-evidence/mulk-constants/report.json'),limits=['Instrumented independent Python float32 model; compiled captures were separately checked for exact component agreement','Only existing 42 coefficient tuples and 984 input pairs','Omitted low-low term bound does not bound every other rounding error','No arbitrary input, coefficient or live-history guarantee; no independent semantic approval'],admission='NOT_GRANTED')
Path('outputs/blackdog-mulk-domain-check.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

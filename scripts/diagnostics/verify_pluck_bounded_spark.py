from pathlib import Path
jobs=[('verify_pluck_single_loop.py',[('pluck-single-loop-evidence','pluck-bounded-evidence'),('pluck-single-loop-check','pluck-bounded-static-check'),('qualify_pluck_single_loop.py','qualify_pluck_bounded_static.py'),('pluck-single-loop-verification','pluck-bounded-static-verification')]),('verify_pluck_live.py',[('pluck-live-evidence','pluck-bounded-evidence'),('pluck-live-check','pluck-bounded-live-check'),('qualify_pluck_live.py','qualify_pluck_bounded_live.py'),('pluck-live-verification','pluck-bounded-live-verification')]),('verify_pluck_wasm.py',[('pluck-wasm-evidence','pluck-bounded-evidence'),('pluck-wasm-check','pluck-bounded-wasm-check'),('qualify_pluck_wasm.py','qualify_pluck_bounded_wasm.py'),('pluck-wasm-verification','pluck-bounded-wasm-verification')])]
for file,replacements in jobs:
 s=Path('work',file).read_text().replace('pluck-single-loop.dsp','pluck-bounded-epoch.dsp')
 for a,b in replacements:s=s.replace(a,b)
 s=s.replace('independent_verification','capture_verification')
 exec(compile(s,'verify-bounded-'+file,'exec'),{})

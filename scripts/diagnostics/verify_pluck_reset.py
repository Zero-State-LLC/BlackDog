from pathlib import Path
jobs=[('verify_pluck_single_loop.py',[('pluck-single-loop-evidence','pluck-reset-evidence'),('pluck-single-loop-check','pluck-reset-static-check'),('qualify_pluck_single_loop.py','qualify_pluck_reset_static.py'),('pluck-single-loop-verification','pluck-reset-static-verification')]),('verify_pluck_live.py',[('pluck-live-evidence','pluck-reset-evidence'),('pluck-live-check','pluck-reset-live-check'),('qualify_pluck_live.py','qualify_pluck_reset_live.py'),('pluck-live-verification','pluck-reset-live-verification')]),('verify_pluck_wasm.py',[('pluck-wasm-evidence','pluck-reset-evidence'),('pluck-wasm-check','pluck-reset-wasm-check'),('qualify_pluck_wasm.py','qualify_pluck_reset_wasm.py'),('pluck-wasm-verification','pluck-reset-wasm-verification')])]
for file,replacements in jobs:
 s=Path('work',file).read_text().replace('pluck-single-loop.dsp','pluck-reset-loop.dsp')
 for a,b in replacements:s=s.replace(a,b)
 exec(compile(s,'verify-reset-'+file,'exec'),{})

from pathlib import Path
base=Path('work/verify_ribbon_closure.py').read_text()
for kind in ('bitcrush','bouncing-ball'):
 code=base.replace('ribbon-closure-evidence','designing-closure-evidence').replace("p=root/'ribbon-closure-check'","p=root/'designing-"+kind+"-check'").replace("b/'ribbon-closure/inputs.json'","b/'designing-"+kind+"-closure/inputs.json'").replace('qualify_ribbon_closure.py','qualify_designing_closures.py').replace('ribbon-closed.dsp',kind+'-closed.dsp').replace('ribbon.dsp',kind+'.dsp').replace('ribbon_sha256','origin_sha256').replace('blackdog-ribbon-closure-verification','blackdog-designing-'+kind+'-verification')
 exec(compile(code,'verify-designing-'+kind,'exec'))

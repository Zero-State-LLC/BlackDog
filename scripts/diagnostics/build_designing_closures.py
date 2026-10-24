from pathlib import Path
base=Path('work/build_ribbon_closure.py').read_text()
for name,blob in [('bitcrush','4d3cf45ab3da845db172224af4ad5b2ff90237f3'),('bouncing-ball','c72d745cd6a64b6c1048ec1f74a82a61af356dcf')]:
 code=base.replace("out=b/'ribbon-closure'", "out=b/'designing-"+name+"-closure'").replace("b/'evaluation-search/ribbon.dsp'", "b/'designing-sources/"+name+".dsp'").replace('af146e17caaf28dccbe4ee04cc8d65ae5858576b',blob).replace('a793afc33dc0b0854e5ca8a34c22e9d98a125b73','dacffbddca08a3b16e247fc1453657939be7049e').replace('ribbon-closed.dsp',name+'-closed.dsp').replace('upstream Ribbon source','upstream Designing Sound source').replace('ribbon_commit','origin_commit').replace('ribbon_blob','origin_blob').replace('ribbon_sha256','origin_sha256')
 exec(compile(code,'build-designing-'+name,'exec'))

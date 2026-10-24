from pathlib import Path
import json,struct
p=Path('work/mulk-constants-evidence/mulk-constants')
r=json.loads((p/'report.json').read_text())
f=lambda x:struct.unpack('<f',struct.pack('<f',x))[0]
def barrier(x):return max(f(-1e30),min(f(1e30),f(x)))
def model(ah,al,a,b,ch,cl):
 R=barrier
 p=R(ah*ch);cc=R(4097*ch);c=R(cc-R(cc-ch));d=R(ch-c)
 q0=R(R(a*c)-p);q1=R(q0+R(a*d));q2=R(q1+R(b*c));q3=R(q2+R(b*d))
 err=R(q3+R(R(ah*cl)+R(al*ch)))
 h=R(p+err);return h,R(err-R(h-p))
inputs=list(struct.iter_unpack('<ff',(p/'inputs.bin').read_bytes()));count=0
for row in r['rows']:
 if row['variant']!='exact':continue
 values=list(struct.iter_unpack('<ff',(p/f"b{row['batch']}-exact.bin").read_bytes()))
 for i,(c,d) in enumerate(inputs):
  for j,coef in enumerate(row['coefficients']):
   actual=values[i*7+j];expected=model(*coef,c,d)
   assert actual==expected,(row['batch'],i,j,actual,expected)
   count+=1
out={'status':'PASS','compared_pairs':count,'comparison':'Exact numerical equality of both float32 components against independently transcribed prompt q0..q3 and supplied renorm','independent_human_semantic_approval':False}
Path('outputs/blackdog-prompt-order-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(out)

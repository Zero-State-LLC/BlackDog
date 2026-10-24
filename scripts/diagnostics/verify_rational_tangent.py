from fractions import Fraction as F
from math import factorial
from pathlib import Path
import json,sys
# Exact polynomial residual x*P(x^2)*cos(x)-Q(x^2)*sin(x).
x=F(428,1000);P=[135135,-17325,378,-1];Q=[135135,-62370,3150,-28];coeff={}
for i,p in enumerate(P):
 for j in range(16):
  n=2*i+1+2*j;coeff[n]=coeff.get(n,F(0))+F(p*(-1)**j,factorial(2*j))
for i,q in enumerate(Q):
 for j in range(16):
  n=2*i+2*j+1;coeff[n]=coeff.get(n,F(0))-F(q*(-1)**j,factorial(2*j+1))
polybound=sum(abs(c)*x**n for n,c in coeff.items())
pbound=sum(abs(p)*x**(2*i) for i,p in enumerate(P));qbound=sum(abs(q)*x**(2*i) for i,q in enumerate(Q))
remainder=x*pbound*x**32/factorial(32)+qbound*x**33/factorial(33)
qmin=F(135135)-62370*x*x-28*x**6;cosmin=1-x*x/2
bound=(polybound+remainder)/(qmin*cosmin)
assert bound<F(1,10**14)
r=dict(domain_abs_x_max=float(x),first_nonzero_residual_power=min(n for n,c in coeff.items() if c),denominator_lower_bound=float(qmin),cosine_lower_bound=float(cosmin),absolute_tangent_approximation_error_bound=float(bound),scope='Exact rational approximation only; paired-float implementation requires separate numerical validation',passed=True)
if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))

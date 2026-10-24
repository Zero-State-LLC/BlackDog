"""Diagnostic stationary-loop poles; excludes reset/gate transients."""
import numpy as np
from scipy.optimize import root

def fundamental(sr,f):
    period=sr/f;n=max(1,int(np.floor(period-1.5))-1);d=period-1.5-n
    w=2*np.pi*f/sr;a=np.sin((1-d)*w/2)/np.sin((1+d)*w/2)
    # body~_ contributes one sample, tagged adds n; averaging adds
    # (1+z^-1), and ap contributes (a+z^-1)/(1+a*z^-1).
    def equation(v):
        s=v[0]+1j*v[1];q=np.exp(-s)
        value=.499*np.exp(-(n+1)*s)*(1+q)*(a+q)/(1+a*q)-1
        return [value.real,value.imag]
    guess=[np.log(.998*abs(np.cos(w/2)))/period,w]
    solution=root(equation,guess,tol=1e-11)
    residual=float(np.linalg.norm(equation(solution.x)))
    if residual>1e-8:raise ValueError((sr,f,solution.message,residual))
    decay,angle=solution.x
    return {'hz':float(angle*sr/(2*np.pi)),'decay_per_sample':float(decay),'pole_radius':float(np.exp(decay)),'residual':residual,'n':n,'a':float(a),'d':float(d)}
if __name__=='__main__':
    for sr,p in [(44100,116),(48000,115),(96000,119),(192000,16)]:
        f=440*2**((p-69)/12);r=fundamental(sr,f);print(sr,p,r,'cents',1200*np.log2(r['hz']/f))

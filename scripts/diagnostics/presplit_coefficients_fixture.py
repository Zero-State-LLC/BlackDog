"""Pre-split pinned float32 prototype constants before Faust constant folding.

Diagnostic fixture only. Keep runtime splitting for variable operands.
"""
from pathlib import Path
import hashlib
import re
import struct

SOURCE_SHA256 = "f2b8c4f511cff6d234fe97b74785b31efd9912fa36f47590bd67677813329c97"
RESULT_SHA256 = "d4fdfcc5b44cb5d9d4a5ecf98fdec76c88376410dcc574811b2b4e45f10e075e"


def build(s: str) -> str:
    if hashlib.sha256(s.encode()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Expected the pinned paired-crossover predecessor")
    f = lambda x: struct.unpack("<f", struct.pack("<f", x))[0]
    helper='''
 mulk(ah,al,asplit,arest,ch,cl)=(r(ah*ch),err):renorm with {
  p=r(ah*ch); cc=r(4097*ch); csplit=r(cc-r(cc-ch)); crest=r(ch-csplit);
  err=r(r(r(r(r(r(asplit*csplit)-p)+r(asplit*crest))+r(arest*csplit))+r(arest*crest))+r(r(ah*cl)+r(al*ch)));
 };
'''
    a=s.index(' dfsection(');b=s.index(' dfbiquad(',a);part=s[a:b]
    for name in ['b2','b0','a1','a0']:
     part=part.replace(name+'h,'+name+'l,',name+'h,'+name+'l,'+name+'split,'+name+'rest,',1)
     part=part.replace('mul('+name+'h,'+name+'l,','mulk('+name+'h,'+name+'l,'+name+'split,'+name+'rest,')
     part=part.replace('mul(-'+name+'h,-'+name+'l,','mulk(-'+name+'h,-'+name+'l,-'+name+'split,-'+name+'rest,')
    s=s[:a]+helper+part+s[b:]
    for name in ['dflp','dfhp']:
     line=next(x for x in s.splitlines() if x.startswith(name+'('));new=line
     for arg in re.findall(r'dfsection\(fh,fl,([^)]*)\)',line):
      nums=list(map(float,arg.split(',')));assert len(nums)==8;expanded=[]
      for h,l in zip(nums[::2],nums[1::2]):
       ca=f(4097*h);hh=f(ca-f(ca-h));hl=f(h-hh);expanded.extend([h,l,hh,hl])
      new=new.replace(arg,','.join(format(x,'.17g') for x in expanded),1)
     s=s.replace(line,new)
    assert hashlib.sha256(s.encode()).hexdigest() == RESULT_SHA256
    return s


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(build(args.source.read_text()))

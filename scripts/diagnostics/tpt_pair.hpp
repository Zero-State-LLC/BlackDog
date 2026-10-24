// Diagnostic paired-float arithmetic. Compile without fast-math and FMA contraction.
#include <cmath>
struct TptPair {
 float hi,lo;
 TptPair():hi(0),lo(0){}
 TptPair(float x):hi(x),lo(0){}
 TptPair(float h,float l):hi(h),lo(l){}
 operator float() const {return hi+lo;}
 static TptPair sum(float a,float b) {
  float s=a+b,v=s-a,e=(a-(s-v))+(b-v);return {s,e};
 }
 friend TptPair operator+(TptPair a,TptPair b) {
  TptPair s=sum(a.hi,b.hi);float e=s.lo+(a.lo+b.lo);
  return sum(s.hi,e);
 }
 friend TptPair operator-(TptPair a,TptPair b) {return a+TptPair(-b.hi,-b.lo);}
 friend TptPair operator*(TptPair a,TptPair b) {
  float p=a.hi*b.hi;
  float ca=4097.0f*a.hi,cb=4097.0f*b.hi;
  float ah=ca-(ca-a.hi),al=a.hi-ah,bh=cb-(cb-b.hi),bl=b.hi-bh;
  float e=((ah*bh-p)+ah*bl+al*bh)+al*bl;
  e=e+(a.hi*b.lo+a.lo*b.hi);e=e+a.lo*b.lo;
  return sum(p,e);
 }
 friend TptPair operator+(float a,TptPair b){return TptPair(a)+b;}
 friend TptPair operator+(TptPair a,float b){return a+TptPair(b);}
 friend TptPair operator-(float a,TptPair b){return TptPair(a)-b;}
 friend TptPair operator-(TptPair a,float b){return a-TptPair(b);}
 friend TptPair operator*(float a,TptPair b){return TptPair(a)*b;}
 friend TptPair operator*(TptPair a,float b){return a*TptPair(b);}
};
inline TptPair tpt_abs(TptPair a){return a.hi<0 || (a.hi==0 && a.lo<0) ? TptPair(-a.hi,-a.lo):a;}

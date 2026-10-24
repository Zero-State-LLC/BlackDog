#include <cmath>
#include <fstream>
#include <vector>
#include <algorithm>
struct Pair {float h,l;Pair(double x=0):h(x),l(x-double(h)){} Pair(float a,float b):h(a),l(b){} double value()const{return double(h)+l;} };
Pair sum(float a,float b){float s=a+b,v=s-a;return Pair(s,(a-(s-v))+(b-v));}
Pair operator+(Pair a,Pair b){Pair s=sum(a.h,b.h);Pair t=sum(a.l,b.l);Pair u=sum(s.l,t.h);Pair v=sum(s.h,u.h);return sum(v.h,(v.l+u.l)+t.l);}
Pair operator-(Pair a,Pair b){return a+Pair(-b.h,-b.l);}
Pair operator*(Pair a,Pair b){float p=a.h*b.h;float e=std::fma(a.h,b.h,-p);Pair r=sum(p,e);return r+Pair(double(a.h)*b.l)+Pair(double(a.l)*b.h)+Pair(double(a.l)*b.l);}
#ifdef DOUBLE_STATE
using R=double;double value(double x){return x;}
#else
using R=Pair;double value(Pair x){return x.value();}
#endif
const double proto[3][4]={{.000099999997055,.000433227200555,.782413046821645,.245291508706160},{1,7.621731298870603,.512478641889141,.689621364484675},{1,53.536152954556727,.168404871113589,1.069358407707312}};
struct Filter {R t[3][2]{},d[3][2]{};bool high;Filter(bool h):high(h){} R tick(R x,double fc,int rate){R tv=x,dv=x;double tangent=std::tan(std::acos(-1.)*fc/rate),c=1./std::tan(std::acos(-1.)*std::max(fc,2304.)/rate),c2=c*c;
 for(int i=0;i<3;i++){double b2=proto[i][0],b0=proto[i][1],a1=proto[i][2],a0=proto[i][3];if(high){b2=proto[i][1]/a0;b0=proto[i][0]/a0;a1/=a0;a0=1/a0;}double w=std::max(std::abs(a1),std::sqrt(std::abs(a0))),w2=w*w,g=w*tangent;
 R u=(tv-R(a1/w)*t[i][0]-R(a0/w2)*(R(g)*t[i][0]+t[i][1]))*R(1/(1+g*(a1/w+g*a0/w2)));
 R v1=R(g)*u+t[i][0],v0=R(g)*v1+t[i][1];t[i][0]=R(2)*v1-t[i][0];t[i][1]=R(2)*v0-t[i][1];tv=R(b2)*u+R(b0/w2)*v0;
 double den=a0+a1*c+c2,b0d=(b0+b2*c2)/den,b1d=2*(b0-b2*c2)/den,a1d=2*(a0-c2)/den,a2d=(a0-a1*c+c2)/den;
 R v=dv-R(a1d)*d[i][0]-R(a2d)*d[i][1];dv=R(b0d)*v+R(b1d)*d[i][0]+R(b0d)*d[i][1];d[i][1]=d[i][0];d[i][0]=v;
 }return fc>=2304?dv:tv;}};
int main(int argc,char**argv){if(argc!=5)return 2;int rate=std::stoi(argv[1]);std::ifstream in(argv[2],std::ios::binary),ct(argv[3],std::ios::binary);std::ofstream out(argv[4],std::ios::binary);std::vector<float> pattern(144000),targets(11250);in.read((char*)pattern.data(),576000);ct.read((char*)targets.data(),45000);if(!in||!ct)return 3;Filter hp(true),lp(false),mh(true),ll(false);float smooth=0;double levels[3]={0,0,0},pole=std::exp(-100./rate);
 for(int block=0;block<2250;block++){for(int i=0;i<64;i++){smooth=.99f*smooth+.01f*(targets[block]-4000.f);float fc=std::min(6000.f,std::max(2000.f,4000.f+smooth));R x=R(pattern[block*64+i]),h=hp.tick(x,fc,rate),base=lp.tick(x,fc,rate);double lower=double(fc)*std::pow(2.,-1./3.);R m=mh.tick(base,lower,rate),l=ll.tick(base,lower,rate);double bands[]={value(l),value(m),value(h)};for(int j=0;j<3;j++)levels[j]=(1-pole)*std::abs(bands[j])+pole*levels[j];}float row[3];for(int j=0;j<3;j++){row[j]=20*std::log10(std::max(std::pow(2.,-23.),levels[j]))/200;if(!std::isfinite(row[j]))return 7;}out.write((char*)row,12);}return 0;}

#include <algorithm>
#include <fstream>
#include <vector>
#include <string>
#include <stdexcept>
#define FAUSTFLOAT double
struct dsp {};
struct Meta { void declare(const char*,const char*) {} };
struct UI {
 double* control=nullptr;
 std::vector<std::pair<std::string,double*>> meters;
 void openHorizontalBox(const char*) {} void openVerticalBox(const char*) {} void openTabBox(const char*) {} void closeBox() {}
 void declare(double*,const char*,const char*) {}
 void addHorizontalSlider(const char*,double* p,double,double,double,double){control=p;}
 void addVerticalSlider(const char*,double* p,double,double,double,double){control=p;}
 void addNumEntry(const char*,double* p,double,double,double,double){control=p;}
 void addVerticalBargraph(const char* s,double* p,double,double){meters.push_back({s,p});}
 void addHorizontalBargraph(const char* s,double* p,double,double){meters.push_back({s,p});}
};
#include "generated.hpp"
int main(int argc,char**argv){
 if(argc!=3)return 2;
 std::ifstream in(argv[1],std::ios::binary);std::ofstream out(argv[2],std::ios::binary);
 mydsp processor;processor.init(48000);UI ui;processor.buildUserInterface(&ui);
 if(processor.getNumInputs()!=1||processor.getNumOutputs()!=1||!ui.control||ui.meters.size()!=3)return 3;
 std::sort(ui.meters.begin(),ui.meters.end());
 float smooth=0; float target=4000;
 for(int block=0;block<64;block++){
  if(block==0)target=2000;if(block==8)target=6000;if(block==24)target=2500;if(block==40)target=3333.33f;
  float raw[64];double input[64],output[64];in.read((char*)raw,sizeof(raw));if(!in)return 4;
  for(int i=0;i<64;i++)input[i]=raw[i];for(int i=0;i<64;i++){smooth=0.99f*smooth+0.01f*(target-4000.f);*ui.control=std::min(6000.f,std::max(2000.f,4000.f+smooth));double* ins[]={input+i};double* outs[]={output+i};processor.compute(1,ins,outs);}
  for(int i=0;i<64;i++){double row[]={output[i],*ui.meters[0].second/200,*ui.meters[1].second/200,*ui.meters[2].second/200};out.write((char*)row,sizeof(row));}
 }
 return out.good()?0:5;
}

"""Diagnostic stock selector: paired TPT with unchanged scalar direct-form branch."""
import hashlib
from paired_tpt_fixture import build_tpt


def build_switching(closure, arithmetic):
    fixture = build_tpt(closure, arithmetic)
    source = fixture['source']
    source = source.replace('hp(fc)=fi._highpass6e(tpt,fc);', '''hp(fc)=switch(fc,fi._highpass6e(tpt,fc),fi._highpass6e(fi.tf2s_df,max(fc,2304)));''')
    source = source.replace('lp(fc)=fi._lowpass6e(tpt,fc);', '''lp(fc)=switch(fc,fi._lowpass6e(tpt,fc),fi._lowpass6e(fi.tf2s_df,max(fc,2304)));
 switch(fc,tpt,df,xh,xl)=(tpt(xh,xl),(xh+xl:df),0):choose with {
  choose(th,tl,dh,dl)=select2(fc>=2304,th,dh),select2(fc>=2304,tl,dl);
 };''')
    fixture.update(source=source,source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                   semantics='stock-2304-selector-paired-tpt-scalar-direct-form',diagnostic_only=True)
    return fixture

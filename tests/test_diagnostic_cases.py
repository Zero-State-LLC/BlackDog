"""Issue 108 extension: adversarial validation and unchanged legacy identities."""
from dataclasses import replace
from types import SimpleNamespace
import subprocess
import sys
from pathlib import Path

import pytest

from faustcoder.canonical import canonical_bytes, content_digest_for
from faustcoder.diagnostic_cases import (ControlEvent, DiagnosticCase, input_buffers,
    run_diagnostic_cases, validate_controls, validate_worker_result)
from faustcoder.signal import (SignalProfile, SignalReference, SignalRun, profile_payload,
    profile_digest, run_signal, _measure_stimulus, reproducible_signal_digest)
from faustcoder.reward.profiles import reward_profiles, reward_signal_profiles, REWARD_PROFILES


def profile(case=None, **kwargs):
    return SignalProfile(48000, frames=256, block_size=64, stimuli=("sine",), diagnostic_case=case, **kwargs)


def reference(p, values=None):
    return SignalReference(p.sample_rate,p.block_size,p.frames,p.seed,p.stimuli,1,
                           {"sine": [values if values is not None else [0.0]*p.frames]})


DESC = [{"type":"hslider","address":"/gain","min":0,"max":1,"step":0.25},
        {"type":"button","address":"/gate"}, {"type":"hbargraph","address":"/meter"}]


@pytest.mark.parametrize('block', [-1, True, 1.5])
def test_bad_block_type(block):
    with pytest.raises(ValueError): ControlEvent(block,"/gain",0)


@pytest.mark.parametrize('value', [float('nan'),float('inf'),True,'1'])
def test_bad_value(value):
    with pytest.raises(ValueError): ControlEvent(0,"/gain",value)


@pytest.mark.parametrize('events', [
    (ControlEvent(0,'/gain',.25),ControlEvent(0,'/gain',.5)),
    (ControlEvent(1,'/gain',.25),ControlEvent(0,'/gain',.5)),
])
def test_duplicate_or_unsorted(events):
    with pytest.raises(ValueError): DiagnosticCase('c',events)


@pytest.mark.parametrize('event,press', [
    (ControlEvent(4,'/gain',.5),False), (ControlEvent(0,'/missing',.5),False),
    (ControlEvent(0,'/meter',.5),False), (ControlEvent(0,'/gain',1.1),False),
    (ControlEvent(0,'/gain',.3),False), (ControlEvent(0,'/gate',1),True),
])
def test_compiled_boundary(event,press):
    with pytest.raises(ValueError): validate_controls(DiagnosticCase('c',(event,)),DESC,256,64,press)


def test_immutable_and_frozen_profiles():
    assert reward_profiles() == REWARD_PROFILES
    for p in reward_signal_profiles().values():
        assert 'diagnostic_case' not in profile_payload(p)
        assert canonical_bytes(profile_payload(p)) == canonical_bytes(profile_payload(replace(p,diagnostic_case=None)))
        assert profile_digest(p) in REWARD_PROFILES
        c = replace(p,diagnostic_case=DiagnosticCase('c'))
        assert profile_digest(c) not in REWARD_PROFILES
    events = [ControlEvent(0,'/gain',.5)]
    case = DiagnosticCase('c',events,['sine'])
    events.clear()
    assert len(case.controls)==1 and case.input_stimuli == ('sine',)
    with pytest.raises(Exception): case.case_id='changed'


def test_each_extension_field_binds():
    cases = [DiagnosticCase('a'), DiagnosticCase('b'), DiagnosticCase('a',input_stimuli=()),
        DiagnosticCase('a',input_stimuli=('sine',)), DiagnosticCase('a',zero_companion='b'),
        DiagnosticCase('a',(ControlEvent(0,'/gain',.5),)),
        DiagnosticCase('a',(ControlEvent(1,'/gain',.5),)),
        DiagnosticCase('a',(ControlEvent(0,'/other',.5),)),
        DiagnosticCase('a',(ControlEvent(0,'/gain',.50000000001),))]
    assert len({profile_digest(profile(c)) for c in cases}) == len(cases)


def test_stimuli_and_worker_receipt_binding():
    c = DiagnosticCase('a',input_stimuli=('multitone','alternating','noise'))
    p = profile(c)
    values = input_buffers(p)
    assert values == input_buffers(p) and values[0] != values[1] != values[2]
    body = {'inputs':3,'diagnostic_case':{'spec':c.worker_payload(),'descriptors':DESC,'applied_controls':{'sine':[]}}}
    buffers = {f'channel-{i}':v for i,v in enumerate(values)}
    receipt = validate_worker_result(p,body,buffers)
    buffers['channel-1'][0] *= -1
    assert receipt != validate_worker_result(p,body,buffers)
    body['diagnostic_case']['applied_controls']['sine'] = [{}]
    with pytest.raises(ValueError): validate_worker_result(p,body,buffers)


def test_full_signed_compare_past_head_and_ordinary_silence():
    p=profile(DiagnosticCase('a'),head_frames=1)
    values=[0.0]*256;values[-1]=.01
    _,failures,_=_measure_stimulus('sine',[values],p,reference(p))
    assert 'sine:reference' in failures
    _,failures,_=_measure_stimulus('sine',[[0.0]*256],profile(),reference(profile()))
    assert 'sine:silence' in failures


def test_reward_and_promotion_refused_before_compile():
    p=profile(DiagnosticCase('a'))
    for kw in ({'reward_graded':True},{'promotion_candidate':True}):
        with pytest.raises(ValueError,match='not admitted'): run_signal('process=0;',p,reference(p),**kw)


@pytest.mark.parametrize('which', ['missing','cycle','nonzero_reference','setup'])
def test_bad_companions_before_compile(which):
    a=profile(DiagnosticCase('a',zero_companion='b'))
    b=profile(DiagnosticCase('b',zero_companion='a' if which=='cycle' else None))
    if which=='setup': b=replace(b,seed=b.seed+1)
    ps=[a] if which=='missing' else [a,b]
    refs=[reference(p) for p in ps]
    if which=='nonzero_reference': refs[0]=reference(a,[.1]*256)
    with pytest.raises(ValueError): run_diagnostic_cases('process=0;',ps,refs)


@pytest.mark.parametrize('defect', ['none','failed','silent','compile','harness','zero_output_wrong'])
def test_pair_only_removes_silence_after_own_execution(monkeypatch,defect):
    import faustcoder.signal as signal
    zero=profile(DiagnosticCase('zero',zero_companion='live'))
    live=profile(DiagnosticCase('live'))
    calls=[]
    def render(source,p,ref,**kw):
        name=p.diagnostic_case.case_id;calls.append(name)
        failures=['diagnostic:companion_pending','sine:silence'] if name=='zero' else []
        if name=='zero' and defect=='zero_output_wrong': failures.append('sine:reference')
        if name=='live' and defect=='failed': failures.append('sine:reference')
        receipt={'passed':not failures,'harness_digest': 'changed' if name=='live' and defect=='harness' else 'h',
                 'metrics':{'failures':failures,'renders':{'sine':{'finite':True,'silence':name=='zero' or defect=='silent'}},'diagnostic_case':{}}}
        compilation=SimpleNamespace(reproducible_digest='changed' if name=='live' and defect=='compile' else 'c')
        return SignalRun(compilation,receipt,content_digest_for(receipt),tuple(failures),{})
    monkeypatch.setattr(signal,'run_signal',render)
    runs=run_diagnostic_cases('process=0;',[zero,live],[reference(zero),reference(live,[.2]*256)])
    assert calls==['zero','live']
    assert runs[0].receipt['passed'] == (defect=='none')
    assert runs[0].reproducible_digest==reproducible_signal_digest(runs[0].receipt)
    assert runs[0].receipt['metrics']['diagnostic_case']['companion_receipt_digest']==runs[1].reproducible_digest


def test_worker_boundaries_and_channel_order():
    script=Path(__file__).with_name('diagnostic_worker_checks.mjs')
    subprocess.run(['node',str(script)],check=True,capture_output=True,text=True,timeout=60)


@pytest.mark.skipif(sys.platform != 'linux', reason='production sandbox requires Linux namespaces')
def test_real_compiler_controls_routing_and_always_zero_mutant():
    # Same compiled program; silent gain=0 must have a nonzero passing companion.
    live=profile(DiagnosticCase('live',(ControlEvent(0,'/input/gain',.5),),('alternating',)))
    zero=profile(DiagnosticCase('zero',(ControlEvent(0,'/input/gain',0),),('alternating',),'live'))
    live_ref=reference(live,[v*.5 for v in input_buffers(live)[0]])
    source='process = _ * hslider("gain", 1, 0, 1, 0.25);'
    runs=run_diagnostic_cases(source,[live,zero],[live_ref,reference(zero)])
    assert all(r.receipt['passed'] for r in runs)
    mutant=run_diagnostic_cases('g=hslider("gain",1,0,1,.25); process = attach(_ * 0,g);', [live,zero],[live_ref,reference(zero)])
    assert not any(r.receipt['passed'] for r in mutant)
    p=profile(DiagnosticCase('routing',input_stimuli=('sine','noise','alternating')))
    channels=input_buffers(p)
    from faustcoder.signal import f32
    out=[f32(a+b) for a,b in zip(channels[0],channels[2])]
    assert run_signal('process = _,!,_ : +;',p,reference(p,out)).receipt['passed']
    p=profile(DiagnosticCase('generator',input_stimuli=()))
    assert run_signal('process=0.25;',p,reference(p,[.25]*256)).receipt['passed']


def test_legacy_request_bytes_have_no_extension(monkeypatch):
    import json
    import faustcoder.signal as signal
    p=profile()
    class Captured(Exception): pass
    monkeypatch.setattr(signal,'share_directory',lambda: Path('/unused'))
    monkeypatch.setattr(signal,'_stage_runtime',lambda workdir: None)
    monkeypatch.setattr(signal,'node_command',lambda *args,**kwargs: [])
    seen=[]
    def capture(*args,**kwargs):
        seen.append(kwargs['stdin']);raise Captured()
    monkeypatch.setattr(signal,'run_in_sandbox',capture)
    with pytest.raises(Captured): signal._render('process=_;',p,options=(),limits=None)
    expected={'source':'process=_;','options':[],'sample_rate':48000,'block_size':64,
              'frames':256,'stimuli':['sine'],'press_buttons_first_block':True}
    assert seen==[json.dumps(expected,ensure_ascii=False,separators=(',',':')).encode()]


@pytest.mark.parametrize("kwargs", [{"block_size":0},{"block_size":True},{"frames":64.5}])
def test_diagnostic_render_dimensions_fail_closed(kwargs):
    with pytest.raises(ValueError):
        SignalProfile(48000,diagnostic_case=DiagnosticCase("bad"),**kwargs)


def test_companion_reference_must_itself_be_nonzero():
    live=profile(DiagnosticCase("live"))
    zero=profile(DiagnosticCase("zero",zero_companion="live"))
    with pytest.raises(ValueError,match="non-silent reference"):
        run_diagnostic_cases("process=0;",[live,zero],[reference(live),reference(zero)])


def test_diagnostic_harness_binds_all_new_code(monkeypatch):
    import hashlib
    import faustcoder.signal as signal
    monkeypatch.setattr(signal,"_harness_preimage",lambda:{"unshare_path":"/stub","unshare_sha256":"a"*64})
    p=profile(DiagnosticCase("case"))
    samples=[.1 if i%2 else -.1 for i in range(p.frames)]
    source="process=_;"
    compilation=SimpleNamespace(receipt={"source_sha256":hashlib.sha256(source.encode()).hexdigest()},reproducible_digest="sha256:"+"b"*64)
    body={"inputs":1,"outputs":1,"samples":{"sine":[samples]},"diagnostic_case":{}}
    def judge():
        return signal._judge(source,p,reference(p,samples),compilation,body,
                             promotion_candidate=False,cpu_duration_ms=None,reward_graded=False)
    baseline=judge().receipt
    original=signal._file_sha256
    for name in ("signal.py","diagnostic_cases.py","diagnostic-cases.mjs"):
        monkeypatch.setattr(signal,"_file_sha256",lambda path,n=name: "c"*64 if path.name==n else original(path))
        assert judge().receipt["harness_digest"] != baseline["harness_digest"]
    assert baseline["thresholds"]["reward_allowlisted"] is False
    assert baseline["metrics"]["diagnostic_case"]["compiler_digest"]==compilation.reproducible_digest


def test_routed_input_files_fit_automatic_sandbox_budget():
    from faustcoder.signal import _limits_for
    case = DiagnosticCase('wide', input_stimuli=('noise',)*16)
    p = SignalProfile(48000, frames=144000, block_size=64, stimuli=('sine',),
                      expected_channels=1, diagnostic_case=case)
    limits = _limits_for(p)
    staged_and_rendered = (16 + 1 + 1) * 144000 * 4
    assert limits.output_bytes >= staged_and_rendered + 1024*1024
    assert _limits_for(profile()).output_bytes == 8*1024*1024


def test_diagnostic_cases_cannot_disable_clipping():
    with pytest.raises(ValueError, match='clipping'):
        profile(DiagnosticCase('clipped'), reject_clipping=False)


def test_zero_input_result_requires_explicit_empty_route():
    p = profile(DiagnosticCase('generator'))
    body = {'inputs':0, 'diagnostic_case':{'spec':p.diagnostic_case.worker_payload(),
            'descriptors':[], 'applied_controls':{'sine':[]}}}
    with pytest.raises(ValueError, match='empty routing'):
        validate_worker_result(p, body, {})

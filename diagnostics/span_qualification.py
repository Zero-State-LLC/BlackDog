"""Reproducible bounded contracts and exhaustive, non-approval dispositions.

Private source maps, candidates and receipts are explicit CLI inputs. This driver
never changes production signal limits, TOKEN_FLOOR, or T07 split state.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import fcntl
import copy
from pathlib import Path

from diagnostics import span_corpus as bulk
from diagnostics import span_review as review


def build_plan(rows):
    """Independent contracts for a deliberately bounded domain, not all inputs."""
    by_name = {(r['path'], r['function']): uid for uid, r in rows.items()}
    cases, contracts = [], []

    def add(path, name, suffix, expression, values, domain, helpers=(), sparse=None):
        uid = by_name[(path, name)]
        ids = [by_name[(path, helper)] for helper in helpers] + [uid]
        ids = list(dict.fromkeys(ids))
        cid = 'q-' + path.removesuffix('.lib') + '-' + name.replace('@', '-').replace('_', '-').strip('-').lower() + '-' + suffix
        case = dict(id=cid, unit_ids=ids, process=expression, expected='pass',
                    reference=sparse if sparse is not None else [{'0': v} for v in values], missing_dependency=None)
        cases.append(case)
        contracts.append(dict(case=cid, target=uid, closure_unit_ids=ids, domain=domain,
                              closure_scope='exact standalone slice for this contract; no ambient library imports',
                              qualification='bounded_behavior_only', production_approved=False))

    def scalar(path, name, args, values, domain):
        for i, (arg, value) in enumerate(zip(args, values, strict=True)):
            add(path, name, str(i), f'_ * (({name}({arg})+4.0)/32.0)', [(value+4)/32], domain)

    scalar('compressors.lib', 'ratio2strength', ['1','2','4','8'], [0,.5,.75,.875], 'ratio in {1,2,4,8}; zero excluded')
    scalar('compressors.lib', 'strength2ratio', ['0','.5','.75','.875'], [1,2,4,8], 'strength in {0,.5,.75,.875}; one excluded')
    scalar('maths.lib', 'log2', ['.25','.5','1','2','4','8'], [-2,-1,0,1,2,3], 'positive exact powers of two')
    scalar('maths.lib', 'nextpow2', ['1','1.5','3','5','9'], [0,1,2,3,4], 'ceiling base-two exponent, not power value')
    scales = {'ionian':[0,2,4,5,7,9,11], 'dorian':[0,2,3,5,7,9,10],
              'phrygian':[0,1,3,5,7,8,10], 'lydian':[0,2,4,6,7,9,11],
              'mixo':[0,2,4,5,7,9,10], 'eolian':[0,2,3,5,7,8,10],
              'locrian':[0,1,3,5,6,8,10], 'penta':[0,3,5,7,10],
              'dimin':[0,1,3,4,6,7,9,10], 'dodeca':list(range(12))}
    for name, semitones in scales.items():
        n=len(semitones)
        # Constants feed one input of each multiplication; a single pulse is broadcast.
        add('quantizers.lib', name, 'temperament', f'_ <: par(i,{n},*(baTake(i+1,({name}))/4.0)) with {{ baTake(i, xs)=xs : route({n},1,i,1); }}',
            [2**(s/12)/4 for s in semitones], 'equal-tempered pitch ratios, pulse scaled by 1/4')
    for n in (1,2,3):
        values=[.25 if i==j else 0 for i in range(n) for j in range(n)]
        add('linearalgebra.lib','identity',str(n),f'_ <: par(k,{n*n},*(take(k+1)/4.0)) with {{ take(k)=identity({n}):route({n*n},1,k,1); }}',values,'row-major Kronecker delta, N=1..3')
        add('linearalgebra.lib','diag',str(n),f'_ <: par(i,{n},*((i+1)/16.0)) : diag({n})',
            [(i+1)/16 if i==j else 0 for i in range(n) for j in range(n)],'distinct diagonal amplitudes; off-diagonal zero')
    for name, helper, reverse in [('comparatorAsc','_comparatorAsc',False),('comparatorDes','_comparatorDes',True)]:
        for i,pair in enumerate([(.2,-.1),(-.1,.2),(.2,.2)]):
            add('routes.lib',name,str(i),f'_ <: (*({pair[0]}),*({pair[1]})) : {name}',sorted(pair,reverse=reverse),
                'ordered, reversed and tied finite pairs',helpers=(helper,))
    for n in (2,3,4,8):
        add('routes.lib','cross',str(n),f'_ <: par(i,{n},*((i+1)/32.0)) : cross({n})',
            [(i+1)/32 for i in reversed(range(n))],'channel reversal with distinguishable amplitudes')
    for n,m in ((1,2),(2,3),(3,2)):
        # route sends input i to ((i+M) mod (N+M)); invert this permutation for output order.
        total=n+m
        add('routes.lib','crossNM',f'{n}-{m}',f'_ <: par(i,{total},*((i+1)/32.0)) : crossNM({n},{m})',
            [((j-m)%total+1)/32 for j in range(total)],'two bus rotation with distinct channel amplitudes')
    for name in ('interpolate_linear','interpolate_power','interpolate_logarithmic','interpolate_smoothstep','interpolate_smootherstep'):
        args=[]; vals=[]
        for t in (0,.25,.5,.75,1):
            args.append(f'{2 if name=="interpolate_power" else ""}{"," if name=="interpolate_power" else ""}{t},1,4')
            if name=='interpolate_logarithmic': v=4**t
            elif name=='interpolate_power': v=1+3*t*t
            elif name=='interpolate_smoothstep': v=1+3*(3*t*t-2*t**3)
            elif name=='interpolate_smootherstep': v=1+3*(6*t**5-15*t**4+10*t**3)
            else: v=1+3*t
            vals.append(v)
        scalar('interpolators.lib',name,args,vals,'interpolation endpoints 1,4; t=0,.25,.5,.75,1; power=2')
    scalar('interpolators.lib','remap',['0,4,-1,1,0','0,4,-1,1,2','0,4,-1,1,4'],[-1,0,1],'nondegenerate affine interval and endpoints')
    scalar('analyzers.lib','window_rect',['-.25','0','.5','1','1.25'],[0,1,1,1,0],'closed unit interval support')
    scalar('analyzers.lib','window_bartlett',['-.25','0','.25','.5','.75','1','1.25'],[0,0,.5,1,.5,0,0],'triangular unit-support window')
    for name in ('rtorv','rtorv_chrono','rtocv','rtocv_chrono'):
        for n in (2,4):
            indices=list(reversed(range(n))) if name.endswith('chrono') else list(range(n))
            sparse=[]
            for i in indices:
                sparse.append({str(i):.25})
                if name.startswith('rtoc'): sparse.append({})
            add('analyzers.lib',name,str(n),f'*(.25):{name}({n})',[], 'real delay vector; complex imaginary channels zero',sparse=sparse)
    for n in (1,2):
        for name,count in [('optimBasic',2*n+1),('optimBasic3D',(n+1)**2)]:
            add('hoa.lib',name,str(n),f'_ <: par(i,{count},*((i+1)/32.0)) : {name}({n})',
                [(i+1)/32 for i in range(count)],'unity optimization weights and channel count')
    for g in (0,.25,.5,1):
        add('spats.lib','panner',str(int(g*100)),f'*(.25):panner({g})',[.25*(1-g),.25*g],'linear pan at endpoints and interior')
    for name,values in [('ms_enc',[.1875,.0625]),('ms_dec',[.375,.125])]:
        add('misceffects.lib',name,'stereo',f'_ <: (*(.25),*(.125)) : {name}',values,'left=.25 right=.125; sum/difference channel convention')
    for name in ('basicBlock','guitarBody'):
        add('physmodels.lib',name,'routing',f'_ <: (*(.125),*(.25),*(.375)) : {name}',[.125,.25,.375],'three-channel passthrough contract')
    for name,values in [('out',[.125,.25,.75]),('outLeftWave',[.125,.25,.5]),('outRightWave',[.125,.25,.625])]:
        add('physmodels.lib',name,'routing',f'_ <: (*(.125),*(.25),*(.375)) : {name}',values,'three-channel traveling-wave sum')
    add('physmodels.lib','ksReflexionFilter','impulse','*(.25):ksReflexionFilter',[], 'two-tap averaging FIR',sparse=[{'0':.125,'1':.125}])
    for x in (-.5,-.25,0,.25,.5):
        add('physmodels.lib','fluteJetTable',str(int((x+1)*100)),f'_ <: (*({x}):fluteJetTable),*(.125) : +',[x**3-x+.125],'bounded cubic jet transfer, no saturation')
    cases, contracts = batch_contracts(cases, contracts)
    # Every batch gets an independent wrong-reference control. A passing
    # positive plus rejecting control guards accidental constant/dead outputs.
    for positive in list(cases):
        negative=copy.deepcopy(positive);negative['id'] += '-wrong'
        negative['expected']='reference_refusal'
        for ref in negative['reference']:
            ref['0']=ref.get('0',0)+.125
        cases.append(negative)
    # Required helper omission tests exercise actual compiler dependency resolution.
    for name in ('comparatorAsc','comparatorDes'):
        uid=by_name[('routes.lib',name)]
        cases.append(dict(id='q-missing-'+name.lower(),unit_ids=[uid],process=name,
                          expected='compile_refusal',reference=None,missing_dependency='_'+name))
    return {'cases':cases}, contracts


def batch_contracts(cases, contracts, max_channels=12):
    """Pack one-input contracts with explicit channel ranges; preserve every oracle.

The shared negative control corrupts all output channels. It tests rejection
of that batch's reference, not independent rejection of every component.
    """
    if not 1 <= max_channels <= 12:
        raise ValueError('invalid batch channel bound')
    if [c['id'] for c in cases] != [c['case'] for c in contracts]:
        raise ValueError('contract order must match cases')
    batches=[]; mapped=[]; pending=[]; channels=0
    def flush():
        if not pending:return
        name=f'q-batch-{len(batches):03d}'
        unit_ids=list(dict.fromkeys(uid for c,_ in pending for uid in c['unit_ids']))
        reference=[v for c,_ in pending for v in c['reference']]
        expression='_ <: (' + ','.join('('+c['process']+')' for c,_ in pending) + ')'
        batches.append(dict(id=name,unit_ids=unit_ids,process=expression,expected='pass',
                            reference=reference,missing_dependency=None))
        offset=0
        for case,contract in pending:
            mapped.append(dict(contract,original_case=contract['case'],case=name,
                               channel_start=offset,channel_end=offset+len(case['reference']),
                               control_scope='batch-wide corrupted reference'))
            offset+=len(case['reference'])
    for case,contract in zip(cases,contracts,strict=True):
        count=len(case['reference'])
        if not 1<=count<=max_channels:raise ValueError('contract exceeds batch channel bound')
        if channels+count>max_channels:
            flush();pending=[];channels=0
        pending.append((case,contract));channels+=count
    flush()
    return batches,mapped


def validate_coverage(rows, groups, closures):
    """Validate exact group and dependency coverage before any execution."""
    ids=set(rows)
    members=[uid for g in groups for uid in g['unit_ids']]
    if len(members)!=len(set(members)) or set(members)!=ids:
        raise ValueError('group coverage must partition candidate identities')
    by_closure={d['unit']['unit_id']:d for d in closures}
    if len(by_closure)!=len(closures) or set(by_closure)!=ids:
        raise ValueError('closure coverage must equal candidate identities')
    for uid,d in by_closure.items():
        if d['span']!={k:v for k,v in rows[uid].items() if k!='manifest_digest'}:
            raise ValueError('stale dependency span')
    return by_closure


def ledger(rows, groups, closures, contracts, plan, results):
    """Never infer approval or full-function coverage from bounded diagnostics."""
    ids=set(rows)
    by_closure=validate_coverage(rows,groups,closures)
    expected={(c['id'],r) for c in plan['cases'] for r in ((None,) if c['expected']=='compile_refusal' else review.RATES)}
    observed=[(r['case'],r['rate']) for r in results]
    if len(observed)!=len(set(observed)) or set(observed)!=expected:
        raise ValueError('incomplete or duplicate result matrix')
    passed={r['case']:True for r in results}
    for r in results: passed[r['case']] &= r['passed'] is True
    targets={c['target'] for c in contracts}
    if not targets<=ids: raise ValueError('unknown contract target')
    output=[]
    for uid in sorted(ids):
        d=by_closure[uid]; own=[c for c in contracts if c['target']==uid]
        checks=[n for c in own for n in (c['case'],c['case']+'-wrong')]
        if rows[uid]['function'] in ('comparatorAsc','comparatorDes'):
            checks.append('q-missing-'+rows[uid]['function'].lower())
        ok=bool(own) and all(passed.get(n,False) for n in checks)
        blockers=[]
        if not ok:
            blockers.append('behavioral_contract_failed' if own else 'independent_executable_contract_required')
            if d['qualified_references']: blockers.append('external_member_source_and_rights_closure_required')
            if d['unadmitted_local_names']: blockers.append('unadmitted_helper_review_required')
            if d['local_candidates'] or d['includes_self_cycle']: blockers.append('scope_or_overload_resolution_required')
            if d['special_forms']: blockers.append('special_form_contract_required')
        output.append(dict(unit_id=uid,span=rows[uid],status='bounded_contract_pass' if ok else 'blocked',
                           blockers=blockers,contract_cases=checks,
                           dependency_evidence=d,production_approved=False,
                           admission_blockers=['independent_manifest_approval','T06_H2_H3_FLOOR','T07_split_freeze']))
    return dict(format='span-qualification.v1',units=output,counts=dict(Counter(x['status'] for x in output)),
                groups=len(groups),production_approved=False,token_floor=40,token_floor_status='provisional',t07_frozen=False)


@contextmanager
def qualification_output(out, binding):
    """Bind all qualification inputs before writes; serialize outer reports too."""
    if any(p.is_symlink() for p in (out,*out.parents)) or (out.exists() and any(p.is_symlink() for p in out.rglob('*'))):
        raise ValueError('qualification output must not contain symlinks')
    out.mkdir(parents=True,exist_ok=True)
    with (out/'qualification.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        metadata=out/'qualification-binding.json'
        if metadata.exists():
            if review.read_json(metadata)!=binding:
                raise ValueError('qualification binding changed; use a new output directory')
        else:
            if any(p.name!='qualification.lock' for p in out.iterdir()):
                raise ValueError('missing qualification binding for existing evidence')
            bulk.atomic_json(metadata,binding)
        yield


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for option in ('candidate','sources','groups','closures','output'):
        p.add_argument('--'+option,type=Path,required=True)
    a=p.parse_args();out=a.output.absolute()
    if Path('/tmp').resolve() in (out.resolve(),*out.resolve().parents) or any((x/'.git').exists() for x in (out.resolve(),*out.resolve().parents)):
        p.error('receipts must be outside Git and /tmp')
    corpus=review.parse_corpus(review.read_json('corpus/rights-inventory.v1.json'),review.read_json('corpus/notice-manifest.v1.json'))
    blobs=review.load_sources(corpus,review.read_json(a.sources))
    rows=review.candidate_rows(corpus,review.read_json(a.candidate),blobs)
    if set(rows)!={u.unit_id for u in corpus.units if u.function}:
        raise ValueError('qualification requires the complete admitted function corpus')
    groups=review.read_json(a.groups);closures=review.read_json(a.closures)
    validate_coverage(rows,groups,closures)
    plan,contracts=build_plan(rows)
    review.prepare_cases(plan,rows,blobs)
    identity=bulk.runtime_identity()
    binding=dict(rows=rows,groups=groups,closures=closures,plan=plan,contracts=contracts,identity=identity)
    with qualification_output(out,binding):
        review.write_json(out/'contracts.json',contracts)
        review.write_json(out/'plan.json',plan)
        summary=bulk.run_queue(plan,rows,blobs,out/'queue',identity)
        results=[]
        for case in plan['cases']:
            attempts=sorted((out/'queue'/case['id']).glob('attempt-*/complete.json'))
            results.extend(review.read_json(attempts[-1].parent/'results.json'))
        report=ledger(rows,groups,closures,contracts,plan,results)
        review.write_json(out/'qualification.json',report)
    print({'queue':summary,'qualification':report['counts']},flush=True)
    return int(summary['passed']!=summary['runs'])


if __name__=='__main__': raise SystemExit(main())

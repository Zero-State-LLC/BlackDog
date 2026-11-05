"""Draft-only lexical dependency envelopes. Never grants approval or runs DSP."""
import csv, hashlib, json, os, re, sys, collections, posixpath, shutil, subprocess
from pathlib import Path
# Parameterized for the public repo (original ran with fixed host paths).
# BLACKDOG_REPO: BlackDog checkout (default: two levels above this file).
# BLACKDOG_EVIDENCE_ROOT: folder holding the Slice 2 evidence dirs (default: parent of BLACKDOG_REPO).
# BLACKDOG_EXPECTED_HOST: optional; if set, refuse to run on any other hostname.
REPO=Path(os.environ.get('BLACKDOG_REPO', Path(__file__).resolve().parents[2]))
sys.path.insert(0,str(REPO))
from diagnostics.span_corpus import statements, definitions
from faustcoder.libraries import canonical_tree_sha256, share_layout_sha256, FAUSTLIBRARIES_TREE_SHA256, FAUSTLIBRARIES_SHARE_SHA256
HOME=Path(os.environ.get('BLACKDOG_EVIDENCE_ROOT', REPO.parent))
S1=HOME/'blackdog-qualification-sprint-20261021T194809Z'
R2=HOME/'blackdog-s2-forge-draft-return-R2-20261022T035347Z'
DIRECT=HOME/'blackdog-s2-direct-review-20261021'
LIBPIN='2edec0537f536eaa130d42c354884d7db971663c'
LIBROOT=REPO/'faust/libraries/2edec0537f53'
EXPECTED_CSV='ff68a0c2f07e0c95bea35f5af99d06622da7f743b0d53b5f5d0c284594c08c51'
def sha(b): return hashlib.sha256(b).hexdigest()
def blob(b): return hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()
def write(p,x): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def scan(raw):
    try:
        sts=statements(raw);ds=definitions(raw)
    except (ValueError,UnicodeError) as e:
        return dict(status='BLOCKED_PARSE',error=str(e),definitions=[],imports=[],qualified=[],special_forms=[])
    toks=[t for s in sts for t in s];imports=[];qualified=[];special=[]
    for i,(tok,start,end) in enumerate(toks):
        text=tok.decode(errors='replace')
        if tok in (b'import',b'library',b'component'):
            lit=None
            if i+3<len(toks) and toks[i+1][0]==b'(' and toks[i+2][0].startswith(b'"') and toks[i+3][0]==b')':
                try: lit=json.loads(toks[i+2][0].decode())
                except ValueError: pass
            alias=toks[i-2][0].decode() if i>=2 and toks[i-1][0]==b'=' and re.fullmatch(rb'[A-Za-z_]\w*',toks[i-2][0]) else None
            imports.append(dict(kind=text,literal=lit,alias_hint=alias,start_byte=start,end_byte=end,status='LEXICAL_ONLY'))
        if i+2<len(toks) and re.fullmatch(rb'[A-Za-z_]\w*',tok) and toks[i+1][0]==b'.' and re.fullmatch(rb'[A-Za-z_]\w*',toks[i+2][0]):
            if i>0 and i+3<len(toks) and toks[i-1][0]==b'<' and toks[i+3][0]==b'>':
                special.append(dict(form='foreign_header',start_byte=toks[i-1][1],end_byte=toks[i+3][2],literal_arguments=[text+'.'+toks[i+2][0].decode()]))
            else:
                qualified.append(dict(prefix=text,member=toks[i+2][0].decode(),start_byte=start))
        if tok in (b'ffunction',b'fconstant',b'fvariable',b'soundfile',b'environment',b'with',b'letrec',b'case'):
            end_call=end; strings=[]
            if i+1<len(toks) and toks[i+1][0]==b'(':
                depth=0
                for val,cs,ce in toks[i+1:]:
                    if val==b'(':depth+=1
                    if val==b')':depth-=1
                    if val.startswith(b'\"'): strings.append(val.decode(errors='replace'))
                    end_call=ce
                    if depth==0:break
            special.append(dict(form=text,start_byte=start,end_byte=end_call,literal_arguments=strings))
    return dict(status='LEXICAL_ONLY',definitions=ds,imports=imports,qualified=qualified,special_forms=special)
def safe_rel(parent,lit):
    if not lit or '\\' in lit or '://' in lit or lit.startswith('/'):return None
    p=posixpath.normpath(posixpath.join(posixpath.dirname(parent),lit))
    return None if p=='..' or p.startswith('../') else p

def tests():
    a=scan(b'// import("bad.lib");\nma=library("maths.lib"); f(x)=ma.sin(x) with { y=1; }; process=f(0);')
    assert len(a['imports'])==1 and a['imports'][0]['literal']=='maths.lib'
    assert a['qualified'][0]['member']=='sin'
    assert len(scan(b'declare name "library(\\"bad.lib\\")"; process=1;')['imports'])==0
    assert scan(b'process = (1;')['status']=='BLOCKED_PARSE'
    assert scan(b'import(name);')['imports'][0]['literal'] is None
    assert safe_rel('x.dsp','../../etc/passwd') is None
    assert safe_rel('dir/x.dsp','../helper.lib')=='helper.lib'
    assert len(scan(b'f(x)=x; f(x,y)=x+y;')['definitions'])==2
    assert not scan(b'f = ffunction(float f(float), <piano.h>, \"\");')['qualified']
    assert any(x['form']=='foreign_header' for x in scan(b'f = ffunction(float f(float), <piano.h>, \"\");')['special_forms'])
    return 10

def main(out):
    expected_host=os.environ.get('BLACKDOG_EXPECTED_HOST')
    if expected_host:
        assert subprocess.check_output(['hostname'],text=True).strip()==expected_host
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=REPO,text=True)
    out.mkdir(exist_ok=False);(out/'blobs').mkdir();(out/'units').mkdir();(out/'inputs/dossiers').mkdir(parents=True)
    shutil.copy2(__file__,out/'draft_closures.py')
    input_files=[R2/'SHA256SUMS',R2/'unit-decisions.FORGE-DRAFT.R2.csv',R2/'gate-decisions.FORGE-DRAFT.R2.json',S1/'input-bindings.json',S1/'scope-ledger.UNAPPROVED.json',S1/'dependency-gaps.json']
    assert sha(input_files[1].read_bytes())==EXPECTED_CSV
    inputs=[]
    for i,p in enumerate(input_files):
        dest=out/'inputs'/f'{i}-{p.name}';shutil.copy2(p,dest);inputs.append(dict(path=str(p),sha256=sha(p.read_bytes()),snapshot=str(dest.relative_to(out))))
    # Verify delivered packet before using its decisions as draft labels.
    with (out/'input-integrity.log').open('w') as f:subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=R2,stdout=f,check=True)
    assert canonical_tree_sha256(LIBROOT)==FAUSTLIBRARIES_TREE_SHA256
    assert share_layout_sha256(LIBROOT)==FAUSTLIBRARIES_SHARE_SHA256
    write(out/'library-pin.json',dict(commit=LIBPIN,canonical_tree_sha256=FAUSTLIBRARIES_TREE_SHA256,share_layout_sha256=FAUSTLIBRARIES_SHARE_SHA256,flat_alias_dirs=['old','dx7'],verification='BOTH_DIGESTS_MATCH_REPOSITORY_CONSTANTS'))
    bindings=json.loads((S1/'input-bindings.json').read_text());ledger=json.loads((S1/'scope-ledger.UNAPPROVED.json').read_text())['units'];byuid={u['unit_id']:u for u in ledger}
    rows=list(csv.DictReader((R2/'unit-decisions.FORGE-DRAFT.R2.csv').open()));assert len(rows)==174
    nodes={};raws={};lookup=collections.defaultdict(set);analyses={};read_hashes={}
    def add(raw,repo,pin,path,origin,binding):
        bid=blob(raw);nid=sha((repo+'\0'+pin+'\0'+path+'\0'+bid).encode())
        if nid not in nodes:
            snap='blobs/'+sha(raw);(out/snap).write_bytes(raw)
            nodes[nid]=dict(repo=repo,pin=pin,path=path,git_blob_sha1=bid,sha256=sha(raw),snapshot=snap,origin=origin,pin_binding=binding,approval='PENDING_HUMAN_REVIEW')
            raws[nid]=raw;analyses[nid]=scan(raw)
            lookup[(repo,pin,path)].add(nid)
        return nid
    for u in ledger:
        b=bindings['verified_blobs'].get(u['blob_sha'])
        if not b:continue
        p=Path(b['path']);raw=p.read_bytes();assert sha(raw)==b['sha256'] and blob(raw)==u['blob_sha'];read_hashes[str(p)]=sha(raw)
        add(raw,u['repo'],u['pin'],u['path'],str(p),'S1_LEDGER_AND_VERIFIED_GIT_BLOB')
    # Add local library files not represented in the scope ledger, explicitly flagging
    # directory-label provenance instead of claiming a verified upstream tree binding.
    for p in sorted(LIBROOT.rglob('*.lib')):
        raw=p.read_bytes();read_hashes[str(p)]=sha(raw)
        add(raw,'grame-cncm/faustlibraries',LIBPIN,str(p.relative_to(LIBROOT)),str(p),'REPOSITORY_PINNED_CANONICAL_TREE_DIGEST_VERIFIED')
    # Build one shared conservative file graph. Include all lexical library calls,
    # even unused environments; this is deliberately not a minimal semantic closure.
    edges={}
    for nid,n in nodes.items():
        edges[nid]=[]
        for imp in analyses[nid]['imports']:
            targets=set();lit=imp['literal'];rel=safe_rel(n['path'],lit)
            if rel:targets.update(lookup.get((n['repo'],n['pin'],rel),set()))
            if lit and safe_rel('root',lit)==lit:
                targets.update(lookup.get(('grame-cncm/faustlibraries',LIBPIN,lit),set()))
                for flat in ['old','dx7']:
                    targets.update(lookup.get(('grame-cncm/faustlibraries',LIBPIN,flat+'/'+lit),set()))
            edges[nid].append(dict(imp,candidates=sorted(targets),resolution='UNIQUE_FILE_CANDIDATE' if len(targets)==1 else 'AMBIGUOUS_FILE_CANDIDATES' if targets else 'UNRESOLVED_IMPORT',search_policy='same-repo-relative plus digest-verified library-root and old/dx7 flat aliases; lexical scope and compiler search order unverified'))
    shared=dict(schema='blackdog-dependency-file-graph.draft.v1',production_approved=False,nodes=nodes,analysis=analyses,edges=edges)
    write(out/'file-graph.DRAFT.json',shared)
    graph_sha=sha((out/'file-graph.DRAFT.json').read_bytes());index=[];blocker_counts=collections.Counter()
    for row in rows:
        uid=row['unit_id'];u=byuid[uid];dp=DIRECT/'units'/f'{uid}.json';db=dp.read_bytes();assert sha(db)==row['dossier_sha256'];d=json.loads(db);(out/'inputs/dossiers'/dp.name).write_bytes(db);read_hashes[str(dp)]=sha(db)
        sp=S1/'current-main-replay/sources'/f'{uid}.dsp';raw=sp.read_bytes();assert 'sha256:'+sha(raw)==row['source_sha256'];read_hashes[str(sp)]=sha(raw);ss='blobs/'+sha(raw);(out/ss).write_bytes(raw)
        roots=sorted(lookup[(u['repo'],u['pin'],u['path'])]);roots=[n for n in roots if nodes[n]['git_blob_sha1']==u['blob_sha']];assert len(roots)==1;root=roots[0]
        selected=scan(raw);dep=d['dependency_evidence'];span=dep.get('span');span_status='WHOLE_FILE_SELECTED_SOURCE'
        if span:
            assert sha(raws[root][span['start_byte']:span['end_byte']])==row['source_sha256'].removeprefix('sha256:');span_status='EXACT_RAW_BYTE_RANGE_VERIFIED'
        reachable=set();todo=[root]
        while todo:
            n=todo.pop()
            if n in reachable:continue
            reachable.add(n);todo.extend(t for e in edges[n] for t in e['candidates'])
        # Overapproximate local helper references with same-file lexical names.
        defs=analyses[root]['definitions'];defsby=collections.defaultdict(list)
        for z in defs:defsby[z['name']].append(z)
        starting=[z for z in defs if not span or (span['start_byte']<=z['start_byte'] and z['end_byte']<=span['end_byte'])]
        refs=set();todo=list(starting);chosen={}
        while todo:
            z=todo.pop();key=str(z['start_byte'])+':'+str(z['end_byte'])
            if key in chosen:continue
            chosen[key]=z;refs.update(z['identifier_hints'])
            for name in z['identifier_hints']:todo.extend(defsby.get(name,[]))
        # Alias candidates can be declared in imported stdfaust environments.
        alias=collections.defaultdict(set)
        for n in reachable:
            for e in edges[n]:
                if e.get('alias_hint'):alias[e['alias_hint']].update(e['candidates'])
        members=[]
        for q in selected['qualified']:
            candidates=[]
            for n in sorted(alias.get(q['prefix'],[])):
                for z in analyses[n]['definitions']:
                    if z['name']==q['member']: candidates.append(dict(node=n,definition=z))
            members.append(dict(q,candidate_definitions=candidates,status='LEXICAL_SCOPE_UNVERIFIED' if candidates else 'UNRESOLVED_MEMBER'))
        unresolved_edges=[dict(from_node=n,edge=e) for n in sorted(reachable) for e in edges[n] if e['resolution']!='UNIQUE_FILE_CANDIDATE']
        parse_fail=[n for n in reachable if analyses[n]['status']=='BLOCKED_PARSE']
        unverified=[n for n in reachable if nodes[n]['pin_binding'].startswith('LOCAL_')]
        blockers=['HUMAN_SOURCE_AND_LEAKAGE_ADJUDICATION','HUMAN_CLOSURE_REVIEW','NAME_SCOPE_OVERLOAD_AND_IMPORT_ORDER','INDEPENDENT_CONTRACT_AND_NEGATIVE_CONTROLS','EXTERNAL_MEMBER_RIGHTS_AND_FOREIGN_RESOURCES']
        if unresolved_edges:blockers.append('UNRESOLVED_OR_AMBIGUOUS_FILE_IMPORTS')
        if parse_fail or selected['status']=='BLOCKED_PARSE':blockers.append('LEXER_CANNOT_COVER_ALL_SYNTAX')
        if unverified:blockers.append('ADDITIONAL_LIBRARY_TREE_BINDINGS_NEEDED')
        if span and not starting:blockers.append('SELECTED_DEFINITION_BOUNDARY_NOT_MAPPED')
        blocker_counts.update(blockers)
        candidate_spans=[]
        for z in sorted(chosen.values(),key=lambda z:z['start_byte']):
            candidate_spans.append(dict(z,sha256=sha(raws[root][z['start_byte']:z['end_byte']]),root_node=root,scope_status='OVERAPPROXIMATION_LOCAL_SHADOWING_UNRESOLVED'))
        manifest=dict(schema='blackdog-dependency-closure.draft.v1',unit_id=uid,status='DRAFT_PENDING_HUMAN_REVIEW',closure_complete=False,production_approved=False,human_approval=None,independent_contract_reviewer=None,token_floor=40,token_floor_status='provisional',t07_frozen=False,
          identity={k:row[k] for k in ['unit_id','repo','path','function','group','source_sha256','dossier_path','dossier_sha256','assigned_reviewer']},pin=u['pin'],source_blob=u['blob_sha'],selected_source_snapshot=ss,selected_source_binding=span_status,source_span=span,
          R2_binding=dict(csv_sha256=EXPECTED_CSV,source_notice_proposal=row['source_notice_decision'],copy_proposal=row['copy_label'],disposition_proposal=row['disposition'],dependency_decision='UNRESOLVED'),
          file_graph=dict(path='../file-graph.DRAFT.json',sha256=graph_sha,root_node=root,transitive_file_envelope=sorted(reachable),envelope_not_minimal=True,compiler_search_order_verified=False,cycles_allowed_in_envelope=True),
          local_definition_candidates=candidate_spans,unclassified_identifier_hints=sorted(refs-set(defsby)),selected_imports=selected['imports'],qualified_member_candidates=members,selected_special_forms=selected['special_forms'],transitive_foreign_resource_candidates=[dict(node=n,reference=z) for n in sorted(reachable) for z in analyses[n]['special_forms'] if z['form'] in ['ffunction','fconstant','fvariable','soundfile','foreign_header']],prior_dependency_evidence=dep,
          unresolved_imports=unresolved_edges,parse_failure_nodes=sorted(parse_fail),unverified_upstream_tree_nodes=sorted(unverified),blockers=blockers,
          validation_plan=dict(status='NOT_RUN_PENDING_REVIEW',steps=['Human confirms exact target, dependency ordering, scope, overload dispatch and external members','Bind per-member source and scoped notice decisions; no whole-library rights inference','After source/closure/contract approval compile explicit slice with dedicated existing sandbox','Remove each expected helper/import and require expected failure; reject substitutions and corrupted hashes','Use independently authored semantic reference and target-exercising nonzero cases at 44100/48000 Hz; retain negative-control failures'],no_compiler_or_signal_pass_claimed=True))
        dest=out/'units'/f'{uid}.DRAFT.json';write(dest,manifest)
        index.append(dict(unit_id=uid,manifest=str(dest.relative_to(out)),sha256=sha(dest.read_bytes()),kind='function' if span else 'whole_file',local_definition_candidates=len(candidate_spans),file_envelope_nodes=len(reachable),qualified_members=len(members),unresolved_import_edges=len(unresolved_edges),blockers=blockers))
    summary=dict(units=len(index),kinds=dict(collections.Counter(x['kind'] for x in index)),file_nodes=len(nodes),blocker_counts=dict(blocker_counts),human_approved=0,complete_closures=0,token_floor=40,token_floor_status='provisional',t07_frozen=False)
    write(out/'index.DRAFT.json',dict(summary=summary,units=index));write(out/'input-bindings.json',dict(inputs=inputs,read_hashes=read_hashes,repo_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),scanner_sha256=sha((REPO/'diagnostics/span_corpus.py').read_bytes()),library_verifier_sha256=sha((REPO/'faustcoder/libraries.py').read_bytes()),script_sha256=sha(Path(__file__).read_bytes())))
    write(out/'tests.json',{'synthetic_scanner_and_path_checks_passed':tests()})
    print(json.dumps(summary),flush=True)
if __name__=='__main__': main(Path(sys.argv[1]))

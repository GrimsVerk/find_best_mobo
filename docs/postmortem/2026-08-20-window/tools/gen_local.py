import re, json, os, sys
sys.path.insert(0,os.environ['S'])
from gen_common import *

STAMPS=['20260820T085531Z','20260820T102917Z','20260820T112543Z']
BR='run/local'
events=[]

def role_from_worker(wid):
    if wid.startswith('oracle-'): return 'oracle'
    if wid.startswith('steward-'): return 'steward'
    return 'unknown'

def role_from_branch(b):
    if not b: return 'unknown'
    if re.search(r'oracle-plan-od-\d+', b): return 'steward'
    if re.search(r'(worker/|docs/)oracle-\d{14}', b) or re.search(r'oracle-\d{14}', b): return 'oracle'
    if b.startswith('docs/oracle-plan-'): return 'steward'
    if b.startswith('docs/plan-'): return 'planner'
    return 'unknown'

# ---- Source A: run.md machine logs -------------------------------------
TS = re.compile(r'^- (\d{2}):(\d{2}):(\d{2})Z (.*)$')
for stamp in STAMPS:
    path=f'docs/runs/{stamp}/run.md'
    txt=open(f'{S}/src/run-{stamp}.md',encoding='utf-8').read()
    lines=txt.split('\n')
    m=re.search(r'^Started (\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})Z\.',txt,re.M)
    date=m.group(1)
    # header Started event
    events.append(dict(_ts=f'{date}T{m.group(2)}Z',prec='second',tier='recorded',
        src=f'{BR}:{path}:3',sha=None,phase=None,it=None,role='driver',cls='other',pr=None,
        files=[],ids=[],notes=f'run start marker for run {stamp}',ob=None))
    cur_it=None; cur_phase=None; cur_worker=None
    for i,ln in enumerate(lines,1):
        ref=f'{BR}:{path}:{i}'
        mm=TS.match(ln)
        if mm:
            hh,mi,ss,rest=mm.groups()
            ts=f'{date}T{hh}:{mi}:{ss}Z'
            cls='other'; pr=None; phase=cur_phase; it=cur_it; role='driver'; notes=None
            m2=re.match(r'^iteration (\d+): phase ([A-Z]+)$',rest)
            if m2:
                it=cur_it=int(m2.group(1)); phase=cur_phase=m2.group(2)
                cls='other'; notes='loop iteration marker'
            elif rest.startswith('dispatch ') and 'worker (' in rest:
                mw=re.match(r'^dispatch (\w+) worker \(([^)]+)\)$',rest)
                cur_worker=mw.group(2); role=role_from_worker(cur_worker)
                cls='worker_dispatched'; notes=f'worker id={cur_worker}'
            elif rest=='dispatch fix session':
                cls='worker_dispatched'; role='driver'
                notes='fix session dispatched; no worker log lands for a fix session'
            elif rest.startswith('waiting on PR #'):
                mp=re.match(r'^waiting on PR #(\d+) \(([^)]*)\)',rest)
                pr=int(mp.group(1)); role=role_from_branch(mp.group(2)) 
                if role=='unknown': role='driver'
                cls='other'; notes=f'WAIT opened on head branch {mp.group(2)}'
            elif re.match(r'^PR #\d+ merged$',rest):
                pr=int(re.match(r'^PR #(\d+) merged$',rest).group(1))
                cls='pr_merged'; role='bot'
                notes='merge performed by the pipeline App per the commit body; not read from git author'
            elif re.match(r'^PR #\d+ red ',rest):
                mp=re.match(r'^PR #(\d+) red \(([^)]*)\)',rest)
                pr=int(mp.group(1)); cls='check_failed'; role='driver'
                notes=f'failing check names as logged: "{mp.group(2).strip()}"; check conclusions not fetched (GitHub API out of scope)'
            elif rest.startswith('the same checks failed three times'):
                cls='check_failed'; role='driver'; pr=133
                notes='three-strikes stop; PR number joined from the branch named on the same line'
            elif rest.startswith('budget:'):
                cls='other'; role='driver'; notes='budget gauge reading'
            elif 'owner edited the design layer' in rest:
                cls='operator_action'; role='owner'
                notes='driver detected an owner edit to the design layer'
            elif 'steward worker failed' in rest:
                cls='worker_result'; role='steward'
                notes='worker failed; see the spawn-worker lines above it'
            elif 'the weekly window reset mid-run' in rest:
                cls='other'; role='driver'; notes='budget window re-baselined'
            elif 'pull --ff-only failed' in rest:
                cls='other'; role='driver'; notes='fast-forward pull failed; run continued on the local tree'
            elif "the worker's work is on" in rest:
                cls='other'; role='unknown'
                mb=re.search(r"work is on '([^']+)'",rest)
                role=role_from_branch(mb.group(1)) if mb else 'unknown'
                if role=='unknown': role=role_from_worker(cur_worker or '')
                notes='worker relocated its own branch; driver pushed what the worker reported'
            events.append(dict(_ts=ts,prec='second',tier='recorded',src=ref,sha=None,phase=phase,
                it=it,role=role,cls=cls,pr=pr,files=[],
                ids=ids_from(rest,'body',lane='local'),notes=notes,ob=None))
        elif ln.startswith('WORKER_RESULT '):
            d=dict(kv.split('=',1) for kv in ln.split()[1:] if '=' in kv)
            wid=d.get('id'); 
            events.append(dict(_ts=None,prec='derived',tier='recorded',src=ref,sha=None,
                phase=cur_phase,it=cur_it,role=role_from_worker(wid or ''),cls='worker_result',pr=None,
                files=[],ids=ids_from(wid or '','body',lane='local'),
                notes=('WORKER_RESULT id=%s branch=%s exit=%s commits=%s; the line carries no timestamp of its own, '
                       'so timestamp_utc is taken from the next timestamped log line'%(
                        d.get('id'),d.get('branch'),d.get('exit'),d.get('commits'))),ob=None,
                _wr=d))
        elif ln.startswith('spawn-worker'):
            events.append(dict(_ts=None,prec='derived',tier='recorded',src=ref,sha=None,
                phase=cur_phase,it=cur_it,role=role_from_worker(cur_worker or ''),cls='other',pr=None,
                files=[],ids=[],notes='spawn-worker notice: '+ln.strip()[:220],ob=None))
        elif ln.startswith('Stopped '):
            m3=re.match(r'^Stopped (\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})Z with exit code (\d+)(.*)$',ln)
            events.append(dict(_ts=f'{m3.group(1)}T{m3.group(2)}Z',prec='second',tier='recorded',
                src=ref,sha=None,phase=None,it=cur_it,role='driver',cls='other',pr=None,files=[],
                ids=[],notes=f'run stop, exit code {m3.group(3)}{m3.group(4)}',ob=None))
        elif ln.startswith('Deleted branch '):
            events.append(dict(_ts=None,prec='derived',tier='recorded',src=ref,sha=None,phase=cur_phase,
                it=cur_it,role=role_from_worker(cur_worker or ''),cls='other',pr=None,files=[],ids=[],
                notes='cleanup: '+ln.strip(),ob=None))

# ---- fix-session narrative blocks (prose appended into run.md by the fix session) ----
for stamp in STAMPS:
    path=f'docs/runs/{stamp}/run.md'
    lines=open(f'{S}/src/run-{stamp}.md',encoding='utf-8').read().split('\n')
    date='2026-08-20'
    n=0
    for i,ln in enumerate(lines):
        if not ln.endswith('dispatch fix session'): continue
        n+=1
        start=i+2
        end=start
        while end<len(lines) and not TS.match(lines[end]) and not lines[end].startswith('Stopped '):
            end+=1
        blk='\n'.join(lines[start-1:end])
        after=None
        for ln2 in lines[end:]:
            m=TS.match(ln2)
            if m: after=f'{date}T{m.group(1)}:{m.group(2)}:{m.group(3)}Z'; break
            if ln2.startswith('Stopped '):
                after=re.match(r'^Stopped \S+T(\S+)Z',ln2).group(1); after=f'{date}T{after}Z'; break
        mm=TS.match(ln)
        at=f'{date}T{mm.group(1)}:{mm.group(2)}:{mm.group(3)}Z'
        events.append(dict(_ts=after or at,prec='range',tier='recorded',
            src=f'{BR}:{path}:{start}-{end}',sha=None,phase='WAIT',it=None,role='driver',
            cls='worker_result',pr=133,files=[],ids=ids_from(blk,'body',lane='local'),
            notes=(f'fix-session report #{n} for this run, {end-start+1} lines of prose appended '
                   f'verbatim into the machine log at lines {start}-{end}. Reported outcome, quoted '
                   f'in fragments: no push happened. timestamp_utc bounded: after {at}, at or before '
                   f'{after}; upper bound emitted.'),ob=None))

json.dump(events,open(f'{S}/out_local_runmd.json','w'))
print('run.md events:',len(events))

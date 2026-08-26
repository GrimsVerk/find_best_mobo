import re,json,os,sys
sys.path.insert(0,os.environ['S'])
from gen_common import *
STAMPS=['20260820T085531Z','20260820T102917Z','20260820T112543Z']
ev=[]; report={}
for stamp in STAMPS:
    txt=open(f'{S}/src/run-{stamp}.md',encoding='utf-8').read()
    dispatched=[m.group(1) for m in re.finditer(r'dispatch \w+ worker \(([^)]+)\)',txt)]
    fixes=len(re.findall(r'dispatch fix session',txt))
    logs=[os.path.basename(p) for p in sh('git','ls-tree','-r','--name-only',PIN,
          f'docs/runs/{stamp}/workers').split()]
    logids=[l[:-4] for l in logs]
    revs=sorted({p.split('/')[-2] for p in sh('git','ls-tree','-r','--name-only',PIN,
          f'docs/runs/{stamp}/reviews').split() if '/reviews/' in p and p.count('/')>4})
    # worker logs with no dispatch event
    orphan_logs=[w for w in logids if w not in dispatched]
    dispatch_no_log=[w for w in dispatched if w not in logids]
    dup_dispatch={w:dispatched.count(w) for w in set(dispatched) if dispatched.count(w)>1}
    # reviews vs workers
    rev_worker=[]
    for r in revs:
        m=re.match(r'docs-oracle-(\d{14})--run-local-([0-9a-f]+)$',r)
        if m: rev_worker.append(('oracle-'+m.group(1),r,m.group(2)))
        else:
            m2=re.match(r'docs-oracle-plan-od-(\d+)--run-local-([0-9a-f]+)$',r)
            if m2: rev_worker.append(('steward-od-'+m2.group(1),r,m2.group(2)))
            else:
                m3=re.match(r'docs-(.+)-([0-9a-f]{12})$',r)
                rev_worker.append((None,r,m3.group(2) if m3 else None))
    revd=[w for w,_,_ in rev_worker]
    workers_no_review=[w for w in logids if w not in revd]
    reviews_no_worker=[r for w,r,_ in rev_worker if w not in logids]
    report[stamp]=dict(dispatched=dispatched,fix_sessions=fixes,worker_logs=sorted(logids),
        reviews=revs,orphan_logs=orphan_logs,dispatch_without_log=dispatch_no_log,
        repeat_dispatch=dup_dispatch,workers_without_review=workers_no_review,
        reviews_without_worker_log=reviews_no_worker)
    # emit an event per worker log (independent enumeration)
    for w in sorted(logids):
        p=f'docs/runs/{stamp}/workers/{w}.log'
        body=sh('git','show',f'{PIN}:{p}')
        m=re.search(r'^=== (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) ===',body,re.M)
        role='oracle' if w.startswith('oracle-') else ('steward' if w.startswith('steward-') else 'unknown')
        flag = w in orphan_logs
        ev.append({'_ts':(m.group(1) if m else None),'prec':('second' if m else 'derived'),
            'tier':'derived','src':f'run/local:{p}:1','sha':None,'phase':None,'it':None,
            'role':role,'cls':'worker_dispatched','pr':None,'files':[p],
            'ids':ids_from(w,'body',lane='local'),'ob':None,'engine':None,
            'notes':('worker log, enumerated independently of the event walk'
                     + (' | engine=claude per the log header; engine_model stays null because the '
                        'schema takes it from a Co-Authored-By trailer and a worker log carries none'
                        if 'engine=claude' in body else '')
                     + (' | RECONCILIATION MISMATCH: no dispatch line in run.md names this log'
                        if flag else '')
                     + (f' | run.md dispatches this id {report[stamp]["repeat_dispatch"][w]} times '
                        f'but only ONE log file exists — the later dispatches overwrite or reuse it'
                        if w in report[stamp]['repeat_dispatch'] else ''))})
    for w in sorted(revd):
        pass
    # emit an event per review dir
    for wname,r,headsha in rev_worker:
        p=f'docs/runs/{stamp}/reviews/{r}/verdict.txt'
        v=sh('git','show',f'{PIN}:{p}').strip().split('\n')[0] if r else ''
        meta=sh('git','show',f'{PIN}:docs/runs/{stamp}/reviews/{r}/meta.txt')
        head=re.search(r'^head:\s+(\S+)',meta,re.M)
        headfull=head.group(1) if head else None
        cd=sh('git','log','-1','--date=format-local:%Y-%m-%dT%H:%M:%SZ','--format=%cd',
              headfull).strip() if headfull else ''
        role='oracle' if (wname or '').startswith('oracle-') else (
             'steward' if (wname or '').startswith('steward-') else 'unknown')
        bm=re.search(r'^branch:\s+(\S+)',meta,re.M)
        bn=bm.group(1) if bm else '?'
        note=('review artefact for branch '+bn+'; verdict='+(v or 'null')
              +'; timestamp_utc is the committer date of the reviewed head commit'
              +' (the review files carry no timestamp of their own)')
        if wname not in logids:
            note += ' | RECONCILIATION MISMATCH: no worker log in this run matches this review slug'
        ev.append({'_ts':(cd or None),'prec':'derived','tier':'derived',
            'src':f'run/local:docs/runs/{stamp}/reviews/{r}/meta.txt:1','sha':headfull,
            'phase':None,'it':None,'role':role,'cls':'other','pr':None,
            'files':[f'docs/runs/{stamp}/reviews/{r}/'+x for x in
                     ['meta.txt','payload.txt','reply.txt','verdict.txt']],
            'ids':ids_from(r,'body',lane='local'),'ob':None,'engine':None,'notes':note})
json.dump({'events':ev,'report':report},open(f'{S}/out_recon.json','w'))
print(json.dumps(report,indent=1)[:3000])
print('recon events',len(ev))

import re,json,os,sys
sys.path.insert(0,os.environ['S'])
from gen_common import *
DATE='2026-08-20'
ROW=re.compile(r'^\|\s*(?:(\d{4}-\d{2}-\d{2})T)?(\d{2}:\d{2}(?::\d{2})?)(?:-\d{2}:\d{2})?Z?\s*\|(.*)$')

def classify(text):
    t=text.lower()
    if 'merged' in t and 'pr #' in t: return 'pr_merged'
    if re.search(r'pr #\d+ opened|opened by',t): return 'pr_opened'
    if 'ruling' in t or re.search(r'\bod-\d+\b.*rul|rules bl',t): return 'ruling_issued'
    if 'dispatch' in t or 'worker via' in t: return 'worker_dispatched'
    if 'worker returned' in t or 'worker finished' in t or 'worker_result' in t: return 'worker_result'
    if 'plan' in t and ('wrote' in t or 'slug' in t or 'covers:' in t): return 'plan_written'
    if 'refused' in t or 'failed' in t or 'red' in t or 'blocked' in t: return 'check_failed'
    if 'uncertaint' in t or re.search(r'\bfiling\b|\bfiled\b',t): return 'uncertainty_opened'
    if 'copier update' in t or 'template' in t and 'v0.4' in t: return 'template_update'
    return 'operator_action'

def rows(branch,path,lane,srcfile,role_default):
    lines=open(f'{S}/src/{srcfile}',encoding='utf-8').read().split('\n')
    ev=[]
    for i,ln in enumerate(lines,1):
        m=ROW.match(ln)
        if not m: continue
        d,t,rest=m.groups()
        if rest.strip().startswith('---'): continue
        cells=[c.strip() for c in rest.split('|')]
        prec='second' if t.count(':')==2 else 'minute'
        if '-' in ln[:30] and re.search(r'\d{2}:\d{2}-\d{2}:\d{2}',ln): prec='range'
        ts=f'{d or DATE}T{t if t.count(":")==2 else t+":00"}Z'
        text=' | '.join(cells)
        it=None; phase=None; role=role_default
        if len(cells)>=3 and re.fullmatch(r'\d+',cells[0]):
            it=int(cells[0])
        if len(cells)>=3:
            p=cells[1].replace('*','').strip()
            if re.fullmatch(r'[A-Z]{3,12}',p): phase=p
        if phase is None:
            p0=cells[0].replace('*','').strip()
            if re.fullmatch(r'[A-Z][A-Z/ \-]{2,30}',p0): phase=p0
        tl=text.lower()
        if 'oracle' in tl and 'worker' in tl: role='oracle'
        elif 'steward' in tl and 'worker' in tl: role='steward'
        elif 'planner' in tl or phase=='PLAN': role='planner'
        elif 'autogrims[bot]' in tl: role='bot'
        prm=re.search(r'PR #(\d+)|`?#(\d+)`?',text)
        pr=int(prm.group(1) or prm.group(2)) if prm else None
        ev.append({'_ts':ts,'prec':prec,'tier':'reconstructed','src':f'{branch}:{path}:{i}',
            'sha':None,'phase':phase,'it':it,'role':role,'cls':classify(text),'pr':pr,
            'files':[path],'ids':ids_from(text,'body',lane=lane),'ob':None,'engine':None,
            'notes':'hand-typed ledger table row: '+re.sub(r'\s+',' ',text)[:240]})
    return ev

LL=rows('origin/chore/test-report-local','docs/runs/operator/local.md','ledger-local','local.md','owner')
WW=rows('origin/chore/test-report-web','docs/runs/operator/web.md','web','web.md','driver')
json.dump({'ledger_local_rows':LL,'web_rows':WW},open(f'{S}/out_rows.json','w'))
print('local rows',len(LL),'web rows',len(WW))

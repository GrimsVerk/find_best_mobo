import re,json,os,sys,subprocess
sys.path.insert(0,os.environ['S'])
from gen_common import *
from gen_commits import build

# ---------- PR -> head branch, from run.md 'waiting on PR #N (branch)' ----
prmap={}
for stamp in ['20260820T085531Z','20260820T102917Z','20260820T112543Z']:
    for m in re.finditer(r'waiting on PR #(\d+) \(([^)]*)\)',
                         open(f'{S}/src/run-{stamp}.md',encoding='utf-8').read()):
        prmap[int(m.group(1))]=m.group(2)
for m in re.finditer(r'PR #(\d+)[^|\n]{0,200}?head [`"]?(docs/[a-z0-9\-\/\.]+)',
                     open(f'{S}/src/web.md',encoding='utf-8').read()):
    prmap.setdefault(int(m.group(1)),m.group(2))

def branch_role(b):
    if not b: return 'unknown'
    if re.search(r'oracle-plan-od-\d+',b): return 'steward'
    if re.search(r'oracle-\d{14}',b): return 'oracle'
    if b.startswith('docs/oracle-plan'): return 'steward'
    if b.startswith('docs/plan-'): return 'planner'
    if b.startswith('template/'): return 'owner'
    if b.startswith('docs/bl-'): return 'owner'
    if b.startswith('docs/r26-'): return 'driver'
    return 'unknown'

LEDGER_ONLY=('docs/runs/operator/','driver-logs/')
def rolemap(subj,pr,files,merge,prmap):
    if files and all(f.startswith('docs/runs/operator/') for f in files):
        return 'owner'   # ledger branch chore/test-report-*: the operator's own hand-typed report
    if merge and pr: return 'bot'
    if re.match(r'^Update from template',subj): return 'owner'
    if re.match(r'^Run evidence for',subj): return 'driver'
    if re.match(r'^Merge branch',subj): return 'bot'
    if re.search(r'rulings and handoff|^Oracle|^oracle|^Rule ',subj): return 'oracle'
    if re.match(r'^Plan\b',subj): return 'steward'
    if re.match(r'^File BL-',subj):
        b=prmap.get(pr,'')
        if b.startswith('docs/bl-'): return 'owner'
        return branch_role(b) if branch_role(b)!='unknown' else 'unknown'
    if re.match(r'^Request the pull request',subj): return 'driver'
    r=branch_role(prmap.get(pr,''))
    return r

ALL={}
ALL['local_commits']=build('dump-runlocal.txt','run/local','local',prmap,rolemap)
ALL['web_commits']  =build('dump-runweb.txt','run/web','web',prmap,rolemap)
ALL['ledgerlocal_commits']=build('dump-ledgerlocal.txt','chore/test-report-local','ledger-local',prmap,rolemap)
ALL['ledgerweb_commits']  =build('dump-ledgerweb.txt','chore/test-report-web','ledger-web',prmap,rolemap)
ALL['main_commits']=build('dump-main.txt','main','runner',prmap,rolemap)
json.dump({'prmap':prmap,**ALL},open(f'{S}/out_commits.json','w'))
for k,v in ALL.items(): print(k,len(v))

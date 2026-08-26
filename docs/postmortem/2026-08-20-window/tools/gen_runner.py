import re,json,os,sys
sys.path.insert(0,os.environ['S'])
from gen_common import *
P='docs/runs/operator/runner-2026-08-20.md'
SHA='316ff10f9b9ba0b6ef75403037fcfd3868660fbd'
CD=sh('git','log','-1','--date=format-local:%Y-%m-%dT%H:%M:%SZ','--format=%cd',SHA).strip()
lines=open(f'{S}/src/runner.md',encoding='utf-8').read().split('\n')
ev=[]
for i,ln in enumerate(lines,1):
    m=re.match(r'^##\s+(RN-\d+)\s*(?:—|-)?\s*(.*)$',ln)
    if not m: continue
    rid,head=m.group(1),m.group(2)
    body=[]
    for ln2 in lines[i:]:
        if re.match(r'^##\s',ln2): break
        body.append(ln2)
    body='\n'.join(body)
    sev=re.search(r'\*\*Severity:\*\*\s*(.+)',body)
    prm=re.search(r'PR #(\d+)',head+' '+body)
    ev.append({'_ts':CD,'prec':'derived','tier':'reconstructed',
        'src':f'main:{P}:{i}','sha':SHA,'phase':None,'it':None,'role':'unknown',
        'cls':'finding_logged','pr':(int(prm.group(1)) if prm else None),'files':[P],
        'ids':merge_ids([{'family':'RN','id':rid,'source':'subject'}],
                        ids_from(head,'subject',lane='runner'),ids_from(body,'body',lane='runner')),
        'ob':None,'engine':'Claude Opus 5 <noreply@anthropic.com>',
        'notes':(f'{rid} — {head[:150]} | severity as written: '
                 f'{(sev.group(1).strip() if sev else "not stated")} | timestamp_utc is the '
                 f'committer date of {SHA[:8]} on main; the file carries no per-entry timestamp. '
                 f'This is 16:47:02Z, AFTER the last lane event of the window (15:46:33Z) — the task '
                 f'brief says the file was written during the window; the commit date says otherwise. '
                 f'Both stated, neither resolved. Merged to main 2026-08-24 in 7e73d254.')})
json.dump(ev,open(f'{S}/out_runner.json','w'))
print(len(ev),[e['ids'][0]['id'] for e in ev], CD)

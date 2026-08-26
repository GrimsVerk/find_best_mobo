import re,json,os,sys
sys.path.insert(0,os.environ['S'])
from gen_common import *

def first_commit_adding(branch,path):
    shas=sh('git','log','--reverse','--format=%H',f'{MB}..{branch}','--',path).split()
    res={}
    for sha in shas:
        d=sh('git','show','--pretty=format:','-U0',sha,'--',path)
        cd=sh('git','log','-1','--date=format-local:%Y-%m-%dT%H:%M:%SZ','--format=%cd',sha).strip()
        for ln in d.splitlines():
            if not ln.startswith('+') or ln.startswith('+++'): continue
            m=re.match(r'^#{2,4}\s+(F\d+)\b',ln[1:])
            if m and m.group(1) not in res:
                res[m.group(1)]=(sha,cd)
    return res

def ledger(branch,path,lane,srcfile):
    lines=open(f'{S}/src/{srcfile}',encoding='utf-8').read().split('\n')
    added=first_commit_adding(branch,path)
    ev=[]; seen={}
    for i,ln in enumerate(lines,1):
        m=re.match(r'^#{2,4}\s+(F\d+)\s*(?:—|-)?\s*(.*)$',ln)
        if not m: continue
        fid=m.group(1); head=m.group(2)
        body=[]
        for ln2 in lines[i:]:
            if re.match(r'^#{1,4}\s',ln2): break
            body.append(ln2)
        body='\n'.join(body)
        sha,cd = added.get(fid,(None,None))
        prm=re.search(r'PR #(\d+)',head+' '+body)
        dup = fid in seen
        seen[fid]=seen.get(fid,0)+1
        note=f'{fid} — {head[:160]}'
        if not sha: note+=' | COULD NOT LOCATE the commit that adds this heading; timestamp_utc null'
        if dup: note+=f' | DUPLICATE id: {fid} appears {seen[fid]} times in this ledger — CONFLICT, both emitted, not resolved'
        ev.append({'_ts':cd,'prec':'derived','tier':'reconstructed',
            'src':f'{branch}:{path}:{i}','sha':sha,'phase':None,'it':None,'role':'owner',
            'cls':'finding_logged','pr':(int(prm.group(1)) if prm else None),'files':[path],
            'ids':merge_ids([{'family':'F','id':f'{lane}/{fid}','source':'subject'}],
                            ids_from(head,'subject',lane=lane),
                            ids_from(body,'body',lane=lane)),
            'ob':None,'engine':None,'notes':note})
    return ev

L=ledger('origin/chore/test-report-local','docs/runs/operator/local.md','ledger-local','local.md')
W=ledger('origin/chore/test-report-web','docs/runs/operator/web.md','ledger-web','web.md')
json.dump({'ledger_local_findings':L,'ledger_web_findings':W},open(f'{S}/out_ledger.json','w'))
print('local findings',len(L),'web findings',len(W))
print('local:',[e['ids'][0]['id'] for e in L])
print('web:',[e['ids'][0]['id'] for e in W])
print('null ts local:',[e['ids'][0]['id'] for e in L if not e['_ts']])
print('null ts web:',[e['ids'][0]['id'] for e in W if not e['_ts']])

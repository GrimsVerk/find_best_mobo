import re,json,os,sys,datetime
sys.path.insert(0,os.environ['S'])
from gen_common import *

def T(s):
    return datetime.datetime.strptime(s,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)

runmd=json.load(open(f'{S}/out_local_runmd.json'))
# fill WORKER_RESULT / spawn-worker / Deleted-branch timestamps from the NEXT timestamped line
for i,e in enumerate(runmd):
    if e['_ts']: continue
    nxt=None
    for e2 in runmd[i+1:]:
        if e2['_ts']: nxt=e2; break
    prev=None
    for e2 in reversed(runmd[:i]):
        if e2['_ts']: prev=e2; break
    if nxt:
        e['_ts']=nxt['_ts']; e['prec']='range'
        e['notes']=(e['notes'] or '')+(f" | timestamp_utc bounded: after {prev['_ts'] if prev else 'run start'}"
                                       f", at or before {nxt['_ts']}; upper bound emitted")
    else:
        e['prec']='derived'
        e['notes']=(e['notes'] or '')+' | no following timestamped line; timestamp_utc null'

com=json.load(open(f'{S}/out_commits.json'))
led=json.load(open(f'{S}/out_ledger.json'))
rows=json.load(open(f'{S}/out_rows.json'))
recon=json.load(open(f'{S}/out_recon.json'))
runner=json.load(open(f'{S}/out_runner.json'))

BR={'local':'run/local','web':'run/web','ledger-local':'chore/test-report-local',
    'ledger-web':'chore/test-report-web','runner':'main'}

buckets={
 'local':   runmd + recon['events'] + com['local_commits'],
 'web':     rows['web_rows'] + com['web_commits'],
 'ledger-local': led['ledger_local_findings'] + rows['ledger_local_rows'] + com['ledgerlocal_commits'],
 'ledger-web':   led['ledger_web_findings'] + com['ledgerweb_commits'],
 'runner':  runner + com['main_commits'],
}

WEB_NOTE=('run/web landed NO run directory for this window: no docs/runs/<STAMP>/ exists on that '
          'branch, so there is no machine log. Every lane=web event is a RECONSTRUCTION from '
          'hand-typed web.md prose plus commit dates.')

out=[]
for lane,evs in buckets.items():
    # drop events with no timestamp to the end, stable
    evs=sorted(evs,key=lambda e:(e['_ts'] is None, e['_ts'] or '', e['src']))
    prev=None
    n=0
    for e in evs:
        n+=1
        gap=None
        if e['_ts'] and prev and prev['_ts'] and e['tier']=='recorded' and prev['tier']=='recorded':
            gap=int((T(e['_ts'])-T(prev['_ts'])).total_seconds())
        notes=e.get('notes')
        if not e['files']:
            notes=(notes+' | ' if notes else '')+('files_touched is empty and file_class is null: '
                   'this event is a log line or a ledger row, not a commit, so it touches no path')
        if lane=='web' and e['tier']=='reconstructed':
            notes=(notes+' | ' if notes else '')+WEB_NOTE
        if lane=='web' and e['tier']=='derived':
            notes=(notes+' | ' if notes else '')+('run/web has no run directory for this window; '
                   'this event is commit metadata only')
        src=e['src']
        if e['sha'] and src==e['sha']:
            src=f"{BR[lane]}@{e['sha']}"
        rec={
         'event_id': f'{lane}-{n:04d}',
         'lane': lane,
         'timestamp_utc': e['_ts'],
         'timestamp_precision': e['prec'],
         'evidence_tier': e['tier'],
         'source_ref': src,
         'commit_sha': e['sha'],
         'phase': e['phase'],
         'iteration': e['it'],
         'actor_role': e['role'],
         'engine_model': (e.get('engine') or None),
         'event_class': e['cls'],
         'pr_number': e['pr'],
         'files_touched': e['files'],
         'file_class': file_class(e['files']),
         'ids_referenced': e['ids'],
         'oracle_bytes_added': e.get('ob'),
         'gap_seconds': gap,
         'notes': notes,
        }
        out.append(rec)
        prev=e

with open(f'{S}/events.jsonl','w',encoding='utf-8') as f:
    for r in out: f.write(json.dumps(r,ensure_ascii=False)+'\n')
import collections
print('TOTAL',len(out))
print(collections.Counter(r['lane'] for r in out))

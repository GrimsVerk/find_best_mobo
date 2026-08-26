import re,json,os,sys,subprocess
sys.path.insert(0,os.environ['S'])
from gen_common import *

def build(dumpfile, branch, lane, prmap, rolemap):
    out=[]
    cs=list(parse_dump(f'{S}/src/{dumpfile}'))
    # non-merge commit -> the PR whose merge commit brought it in
    inpr={}
    for c in cs:
        ps=c.get('parents','').split()
        m=re.search(r'\(#(\d+)\)\s*$',c.get('subject',''))
        if len(ps)>1 and m:
            for s in sh('git','log','--format=%H',f'{ps[0]}..{ps[1]}').split():
                inpr.setdefault(s,int(m.group(1)))
    for c in cs:
        sha=c['sha']; subj=c.get('subject',''); parents=c.get('parents','').split()
        files=c['files']; merge=len(parents)>1
        pr=None
        m=re.search(r'\(#(\d+)\)\s*$',subj)
        if m: pr=int(m.group(1))
        elif sha in inpr: pr=inpr[sha]
        # class
        if merge and pr: cls='pr_merged'
        elif re.match(r'^Update from template',subj): cls='template_update'
        elif re.match(r'^Merge branch',subj): cls='other'
        elif re.search(r'^(Oracle|oracle)[:\s]|Rule |^Rule|rulings and handoff|Rule on ',subj): cls='ruling_issued'
        elif re.match(r'^Plan\b',subj) or re.search(r'^Plan ',subj): cls='plan_written'
        elif re.match(r'^File BL-',subj): cls='uncertainty_opened'
        elif re.match(r'^Run evidence for',subj): cls='operator_action'
        elif re.match(r'^Request the pull request',subj): cls='pr_opened'
        elif re.match(r'^Log |^F\d',subj): cls='finding_logged'
        else: cls='other'
        if cls=='ruling_issued' and re.match(r'^File BL-',subj): cls='uncertainty_opened'
        # mechanical override: a non-merge commit that edits the oracle design layer IS a ruling
        if not merge and 'docs/DESIGN.oracle.md' in files: cls='ruling_issued'
        # ledger branches: a commit editing the operator ledger records findings
        if files and all(f.startswith('docs/runs/operator/') for f in files) and not merge:
            cls='finding_logged'
        # role
        role=rolemap(subj,pr,files,merge,prmap)
        if role=='unknown' and cls=='ruling_issued': role='oracle'
        rng=' ; '.join(c.get('ranges',[]))
        ids=merge_ids(ids_from(subj,'subject',lane=lane),
                      ids_from(' '.join(c['ids_diff'])+' '+rng,'diff',lane=lane),
                      ids_from(' '.join(c['ids_body']),'body',lane=lane))
        ob=None
        if cls=='ruling_issued':
            ob=oracle_bytes(sha)
        out.append(dict(_ts=c['cdate'],prec='second',tier='derived',
            src=sha, sha=sha, phase=None, it=None, role=role, cls=cls, pr=pr,
            files=files, ids=ids, ob=ob,
            engine=(c.get('coauth') or None),
            notes=('merge commit; committer date is the merge time' if merge else
                   'commit metadata on '+branch+(('; landed by PR #%d'%pr) if pr else ''))))
    return out

import re, json, subprocess, os
S = os.environ['S']
PIN = '89351d71b44fcc5382f2708cbeba6c2c905c7ae0'
MB  = '88400b8036bb20b4a2eb6233d98731f4821a4723'

ID_RE = re.compile(r'(?<![A-Za-z0-9])((?:BL|OD|ESC|RN)-\d+|R\d+|V\d+|S\d+|F\d+)(?![A-Za-z0-9])')

def classify_file(p):
    if p.startswith(('src/','tests/','acceptance/','data/')): return 'product'
    if p.startswith(('.claude/','.github/','scripts/')) or p in (
        'pyproject.toml','uv.lock','AGENTS.md','README.md'): return 'machinery'
    return 'documents'

def file_class(paths):
    if not paths: return None
    cs = {classify_file(p) for p in paths}
    return cs.pop() if len(cs)==1 else 'mixed'

# Range notation. Dashed families (BL/OD/ESC/RN) only via '..' or 'through' —
# a hyphen or em dash between two dashed ids is prose ("OD-13 — OD-5"), not a range.
# Undashed families (R/V/S/F) also accept a plain hyphen: "R8-R16", "R1002-R1007".
RANGE_D = re.compile(r'(BL|OD|ESC|RN)-(\d+)\s*(?:\.\.|\s+through\s+)\s*(?:(?:BL|OD|ESC|RN)-)?(\d+)')
RANGE_U = re.compile(r'(?<![A-Za-z0-9])(R|V|S|F)(\d+)\s*(?:\.\.|-|\s+through\s+)\s*\1?(\d+)(?![A-Za-z0-9])')

def expand_ranges(text):
    """Return every id named by a range in `text`, as raw tokens."""
    got=[]
    for m in RANGE_D.finditer(text or ''):
        fam,a,b=m.group(1),int(m.group(2)),int(m.group(3))
        if b>=a and b-a<=200: got += [f'{fam}-{i}' for i in range(a,b+1)]
    for m in RANGE_U.finditer(text or ''):
        fam,a,b=m.group(1),int(m.group(2)),int(m.group(3))
        if b>=a and b-a<=200: got += [f'{fam}{i}' for i in range(a,b+1)]
    return got

# One F namespace per lane PAIR: the findings themselves live in the ledgers, so a
# reference to F5 from run/local and a reference to F5 in local.md are the same id.
F_NS = {'local':'ledger-local','ledger-local':'ledger-local',
        'web':'ledger-web','ledger-web':'ledger-web',
        'runner':'ledger-local'}   # the runner file's only F reference cites local.md by path

def ids_from(text, source, lane=None):
    out=[]
    toks=set(ID_RE.findall(text or '')) | set(expand_ranges(text or ''))
    for tok in sorted(toks):
        fam = tok.split('-')[0] if '-' in tok else tok[0]
        idv = tok
        if fam=='F' and lane: idv = F_NS.get(lane,lane)+'/'+tok
        out.append({'family':fam,'id':idv,'source':source})
    return out

def merge_ids(*lists):
    seen={}; out=[]
    for L in lists:
        for d in L:
            k=(d['family'],d['id'],d['source'])
            if k in seen: continue
            seen[k]=1; out.append(d)
    return out

def parse_dump(path):
    """Yield dict per commit from dump-*.txt."""
    cur=None; mode=None
    for raw in open(path, encoding='utf-8', errors='replace'):
        ln=raw.rstrip('\n')
        if ln.startswith('@@@COMMIT '):
            cur={'sha':ln.split()[1],'files':[],'ids_subject':[],'ids_diff':[],'ids_body':[],'ranges':[]}; mode=None; continue
        if cur is None: continue
        if ln=='--endcommit--':
            yield cur; cur=None; mode=None; continue
        if ln=='--files--': mode='files'; continue
        if ln=='--ids-subject--': mode='ids_subject'; continue
        if ln=='--ids-diff--': mode='ids_diff'; continue
        if ln=='--ids-body--': mode='ids_body'; continue
        if ln=='--ranges--': mode='ranges'; continue
        if mode is None:
            if '=' in ln:
                k,v=ln.split('=',1); cur[k]=v
            continue
        if mode=='files':
            if ln.strip(): cur['files'].append(ln.strip())
        elif mode=='ranges':
            if ln.strip(): cur['ranges'].append(ln.strip())
        else:
            cur[mode].extend([t for t in ln.split() if t])
    if cur: yield cur

def sh(*a):
    return subprocess.run(a,capture_output=True,text=True).stdout

def oracle_bytes(sha):
    """lines and bytes added to docs/DESIGN.oracle.md by this commit."""
    out = sh('git','show','--numstat','--pretty=format:','-m','--first-parent',sha)
    lines=None
    for r in out.splitlines():
        p=r.split('\t')
        if len(p)==3 and p[2]=='docs/DESIGN.oracle.md':
            try: lines=int(p[0])
            except ValueError: lines=None
            break
    if lines is None: return None
    d = sh('git','show','--pretty=format:','-m','--first-parent','-U0',sha,'--','docs/DESIGN.oracle.md')
    b=0
    for r in d.splitlines():
        if r.startswith('+') and not r.startswith('+++'):
            b += len(r[1:].encode('utf-8'))+1
    return {'lines_added':lines,'bytes_added':b}

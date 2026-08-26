import json,sys,re
def key(n): 
    m=re.match(r'([A-Z]+)-?(\d+)',n); return (m.group(1),int(m.group(2)))
for f in ['DESIGN.oracle','BACKLOG']:
    L=json.load(open(f'/tmp/claude-0/-home-user-find-best-mobo/c652d734-b697-5598-8543-9437ace59a45/scratchpad/cmp/local-{f}.json'));W=json.load(open(f'/tmp/claude-0/-home-user-find-best-mobo/c652d734-b697-5598-8543-9437ace59a45/scratchpad/cmp/web-{f}.json'))
    both=sorted(set(L['secs'])&set(W['secs']),key=key)
    print(f'##### {f}: {len(both)} shared ids')
    for i in both:
        same = L['secs'][i].strip()==W['secs'][i].strip()
        hsame = L['heads'][i]==W['heads'][i]
        print(f'{i}\ttext_same={same}\thead_same={hsame}')
    print('local-only:',sorted(set(L['secs'])-set(W['secs']),key=key))
    print('web-only:',sorted(set(W['secs'])-set(L['secs']),key=key))
    print()

import json,re
S="/tmp/claude-0/-home-user-find-best-mobo/c652d734-b697-5598-8543-9437ace59a45/scratchpad"
for f in ['DESIGN.oracle','BACKLOG']:
    L=json.load(open(f'{S}/cmp/local-{f}.json'));W=json.load(open(f'{S}/cmp/web-{f}.json'))
    diff=[i for i in L['secs'] if i in W['secs'] and L['secs'][i].strip()!=W['secs'][i].strip()]
    diff.sort(key=lambda n:int(re.search(r'\d+',n).group()))
    print(f'===== {f} =====')
    for i in diff:
        print(f'--- {i} ---')
        print('  L HEAD:',L['heads'][i])
        print('  W HEAD:',W['heads'][i])
        print(f'  L lines={len(L["secs"][i].splitlines())} chars={len(L["secs"][i])}')
        print(f'  W lines={len(W["secs"][i].splitlines())} chars={len(W["secs"][i])}')

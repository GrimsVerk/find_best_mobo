import re,sys,subprocess,json
ref,path,out=sys.argv[1],sys.argv[2],sys.argv[3]
txt=subprocess.run(['git','show',f'{ref}:{path}'],capture_output=True,text=True).stdout
lines=txt.split('\n')
# heading forms: '#### BL-1 ...'  or  '- **BL-1** — ...'
pat=re.compile(r'^(?:#{1,6}\s+|-\s+\*\*)((?:BL|OD|ESC|RN)-\d+|R\d+|V\d+|S\d+)\b')
secs={};heads={};cur=None;buf=[]
for ln in lines:
    m=pat.match(ln)
    if m:
        if cur: secs[cur]='\n'.join(buf).rstrip()
        cur=m.group(1);heads[cur]=ln.strip();buf=[ln]
    elif cur is not None: buf.append(ln)
if cur: secs[cur]='\n'.join(buf).rstrip()
json.dump({'heads':heads,'secs':secs},open(out,'w'))
print(f'{ref}:{path} -> {len(secs)}: {sorted(secs)}')

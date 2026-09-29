import json,re
raw=json.load(open('pool_raw.json'))
out=[];seen=set()
def clean(t):
    lines=[]
    for l in t.split('\n'):
        s=l.strip()
        if not s or s.startswith('#') or s.startswith('※') or s.startswith('|'): continue
        s=s.replace('**','')
        if re.fullmatch(r'\*[^*].*\*',s): continue   # flavor
        if s in('효과',): continue
        lines.append(s)
    return '\n'.join(lines)
for c in raw:
    if c['name'].startswith('정본 룰'): continue
    code=c['code']
    if c['theme']=='포커짐승들' and c['name'].endswith('메이드에 실패한 강아지'): code='PKBS-003-1'
    if c['theme']=='포커짐승들' and c['name']=='포커짐승들의 도박장': code='PKBS-014F'
    name=re.sub(r'\s*\((본편|흑월침식)[^)]*\)\s*$','',c['name']).strip()
    note=re.search(r'\(((?:본편|흑월침식)[^)]*)\)',c['name'])
    c2=dict(c); c2['code']=code; c2['name']=name; c2['text']=clean(c['text'])
    if note: c2['note']=note.group(1)
    # tags
    tags=[c['theme']]
    if code in('SB-002','SB-003','SB-004','SB-005'): tags=['봉인을 푸는 자']
    c2['tags']=tags
    if c2['type']=='스킬':
        c2['skill_tags']=[c['theme']]
        if code=='AMBR-018': c2['skill_tags']=['호박옥','봉인을 푸는 자']
        if code=='PKBS-015': c2['no_common']=True
    assert name not in seen,name; seen.add(name)
    out.append(c2)
json.dump(out,open('card_pool.json','w'),ensure_ascii=False,indent=1)
print(len(out)); print(sum(1 for c in out if c['type']=='스킬'),'skills')
for c in out:
    if c['type']=='스킬': print(c['name'],c['skill_tags'])
print(out[150]['text'])

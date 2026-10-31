import re,glob,json,os
THEME={'격투가':'격투가','공용카드':'공용','던전마스터':'던전마스터','데이터버그':'데이터버그','번성충':'번성충',
'세리':'세리','소원의분수':'소원의분수','솔루나':'솔루나','저주인형':'저주인형','포커짐승들':'포커짐승들','호박옥':'호박옥'}
def clean(s):
    s=re.sub(r'\*+','',s); s=re.sub(r'^#+\s*','',s); return s.strip()
cards=[]
for f in sorted(glob.glob(os.environ.get('SRC','/home/claude/src')+'/*.md')):
    base=os.path.basename(f)
    theme=next((v for k,v in THEME.items() if base.startswith(k)),None)
    if not theme: continue
    L=open(f,errors='replace').read().split('\n')
    for i,l in enumerate(L):
        if not l.startswith('| **색** |'): continue
        hdr=[clean(x) for x in l.strip('|').split('|')]
        row=[clean(x) for x in L[i+2].strip('|').split('|')]
        d=dict(zip(hdr,row))
        # heading
        j=i-1
        while j>=0 and (not L[j].strip() or L[j].startswith('|')): j-=1
        title=clean(L[j])
        m=re.match(r'([A-Z]{2,5}-\d{3}(?:-\d)?)\s+(.*)',title)
        code,name=(m.group(1),m.group(2).strip()) if m else (None,title)
        # effect text until next heading/table of next card
        k=i+3; eff=[]
        while k<len(L) and not L[k].startswith('| **색** |'):
            eff.append(L[k]); k+=1
        # trim effect back to before next title
        while eff and (not eff[-1].strip() or eff[-1].startswith('#') or re.match(r'^\*\*[A-Z]',eff[-1]) or eff[-1].startswith('**')):
            if eff[-1].startswith('**1') : break
            eff.pop()
        c={'theme':theme,'code':code,'name':name,'color':d.get('색'),
           'text':'\n'.join(x for x in eff if x.strip())[:3000]}
        if '레벨' in d:
            c['type']='몬스터'; c['level']=int(re.sub(r'\D','',d['레벨']) or 0)
            c['race']=d.get('종족'); c['attr']=d.get('속성')
            c['atk']=d.get('공격력'); c['def']=d.get('수비력')
            c['deck']='메인' if c['level']<=4 else '상급'
        else:
            k=d.get('종류','')
            if '스킬' in k: c['type']='스킬'; c['deck']='스킬'
            elif '필드' in k: c['type']='필드'; c['deck']='메인'
            else:
                c['type']='마법'; c['deck']='메인'
                m2=re.search(r'\((.*?)\)',k); c['subtype']=m2.group(1) if m2 else ''
        cards.append(c)
json.dump(cards,open('/home/claude/sim/pool_raw.json','w'),ensure_ascii=False,indent=1)
from collections import Counter
print(Counter((c['theme'],c['type']) for c in cards))
for c in cards: print(c['theme'],c['code'],c['name'][:30],c['type'],c.get('level',''),c['deck'],c.get('subtype',''))

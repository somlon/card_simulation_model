"""뉴네오유희왕 덱 파일 로더 · 검증기
덱 파일 형식 (.deck, UTF-8 텍스트):
    이름: 번성충 대발생 기본형
    스킬: 번성충-대발생
    [메인]
    3 번성충-시체송장벌레
    2 COM-008            # 카드명 또는 카드 번호, '#' 뒤는 주석
    [상급]
    ...
    [전략]
    ...
"""
import json,re,sys,os
from collections import Counter
HERE=os.path.dirname(os.path.abspath(__file__))
POOL=json.load(open(os.path.join(HERE,'card_pool.json'),encoding='utf-8'))
BY_NAME={c['name']:c for c in POOL}
BY_CODE={c['code']:c for c in POOL if c.get('code')}
LIMITS={'메인':(20,40),'상급':(0,20),'전략':(0,10)}
MAX_COPIES=3

def lookup(key):
    return BY_NAME.get(key) or BY_CODE.get(key)

def parse(text):
    deck={'이름':'','스킬':None,'메인':[],'상급':[],'전략':[]}; errs=[]; sec=None
    for n,raw in enumerate(text.splitlines(),1):
        line=raw.split('#',1)[0].strip()
        if not line: continue
        m=re.match(r'^(이름|스킬)\s*[:：]\s*(.+)$',line)
        if m:
            deck[m.group(1)]=m.group(2).strip(); continue
        m=re.match(r'^\[(메인|상급|전략)\]$',line)
        if m: sec=m.group(1); continue
        m=re.match(r'^(\d+)\s*[xX×]?\s+(.+)$',line)
        if not m or not sec:
            errs.append(f'{n}행: 해석할 수 없는 줄 「{raw.strip()}」'); continue
        c=lookup(m.group(2).strip())
        if not c: errs.append(f'{n}행: 카드 풀에 없는 카드 「{m.group(2).strip()}」'); continue
        deck[sec].append((int(m.group(1)),c['name']))
    return deck,errs

def validate(deck):
    errs=[];warns=[]
    sk=lookup(deck['스킬'] or '')
    if not sk or sk['type']!='스킬':
        errs.append(f'스킬 카드 「{deck["스킬"]}」을(를) 찾을 수 없음'); return errs,warns
    allowed=set(sk['skill_tags']) | (set() if sk.get('no_common') else {'공용'})
    for sec,(lo,hi) in LIMITS.items():
        total=sum(n for n,_ in deck[sec])
        if not lo<=total<=hi: errs.append(f'[{sec}] {total}장 — 허용 범위 {lo}~{hi}장')
        for n,name in deck[sec]:
            c=BY_NAME[name]
            if not set(c['tags'])&allowed:
                errs.append(f'[{sec}] 「{name}」 태그 {c["tags"]} — 스킬 「{sk["name"]}」로 사용 불가')
            if c['type']=='스킬': errs.append(f'[{sec}] 스킬 카드 「{name}」는 덱에 넣을 수 없음')
            elif sec=='메인' and c['deck']!='메인': errs.append(f'[메인] 「{name}」(레벨 {c.get("level")})는 상급 덱 카드')
            elif sec=='상급' and c['deck']!='상급': errs.append(f'[상급] 「{name}」는 메인 덱 카드')
    st=sum(n for n,_ in deck['전략'])
    if st!=LIMITS['전략'][1]: errs.append(f'[전략] {st}장 — 시뮬레이션 방침상 최대 {LIMITS["전략"][1]}장을 채워야 함')
    cnt=Counter(); 
    for sec in('메인','상급'):
        for n,name in deck[sec]: cnt[name]+=n
    for name,n in cnt.items():
        if n>MAX_COPIES: errs.append(f'「{name}」 {n}장 — 동명 카드는 {MAX_COPIES}장까지')
    for n,name in deck['전략']:
        if cnt[name]+n>MAX_COPIES:
            warns.append(f'[전략] 「{name}」 전량 교체 시 {cnt[name]+n}장이 될 수 있음 — 교체 시점에 3장 제한 검사')
    return errs,warns

def load(path):
    deck,perr=parse(open(path,encoding='utf-8').read())
    verr,warn=validate(deck) if not perr else ([],[])
    return deck,perr+verr,warn

if __name__=='__main__':
    for p in sys.argv[1:]:
        d,e,w=load(p)
        print(f'■ {p} — {d["이름"] or "(이름 없음)"} / 스킬 {d["스킬"]}')
        for s in('메인','상급','전략'): print(f'   {s} {sum(n for n,_ in d[s])}장')
        for x in e: print('   ✗',x)
        for x in w: print('   △',x)
        print('   → 등록 가능' if not e else '   → 등록 불가')

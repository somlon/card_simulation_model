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
LIMITS={'메인':(20,40),'상급':(0,20),'전략':(0,20)}   # 규칙 명세서 §3-2
STRATEGY_FILL=20   # 시뮬레이션 방침: 전략 덱은 항상 이 매수를 채운다 (규칙상 0~20장, 사용자 재정 2026-09-30)
MAX_COPIES=3
# 고정 카드: 스킬 → {카드: 매수}. 레시피 학습기 · 전략 덱 교체가 바꾸지 않는다.
# ASSUME(2026-10-11): 희생제 1번(라운드 시작 시 자신의 덱의 「퇴마의 부적」을 상대 마법 존에 놓는다)은 자신에게 불리한 설계상 부담이므로,
# 학습기가 부적을 빼서 1번을 피하지 못하도록 메인 덱에 1장 고정한다 (재정 대기)
LOCKED={'희생제':{'퇴마의 부적':1}}

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

def skill_allowed(sk):
    """스킬 카드로 덱에 넣을 수 있는 카드 태그: 스킬에 표기된 태그 + 「공용」(no_common 스킬은 제외) (§3-1)"""
    return set(sk['skill_tags']) | (set() if sk.get('no_common') else {'공용'})

def validate(deck,policy=True):
    """덱 구축 규칙 검사. policy=False면 시뮬레이션 방침(전략 덱 STRATEGY_FILL장 채우기)은 빼고 규칙만 본다"""
    errs=[];warns=[]
    sk=lookup(deck['스킬'] or '')
    if not sk or sk['type']!='스킬':
        errs.append(f'스킬 카드 「{deck["스킬"]}」을(를) 찾을 수 없음'); return errs,warns
    allowed=skill_allowed(sk)
    # 전략 덱 카드는 주 스킬 또는 전략 덱의 스킬 카드 중 하나의 태그에 맞으면 된다(사용자 지시 2026-10-29 — 그 스킬로 바꾼 뒤 넣을 카드).
    # 메인 · 상급 덱 카드는 지금 쓰는 주 스킬의 태그에 맞아야 한다
    st_skills=[BY_NAME[name] for _,name in deck['전략'] if name in BY_NAME and BY_NAME[name]['type']=='스킬']
    allowed_st=allowed.union(*(skill_allowed(x) for x in st_skills))
    for sec,(lo,hi) in LIMITS.items():
        total=sum(n for n,_ in deck[sec])
        if not lo<=total<=hi: errs.append(f'[{sec}] {total}장 — 허용 범위 {lo}~{hi}장')
        for n,name in deck[sec]:
            c=BY_NAME[name]
            if c['type']=='스킬':   # 스킬 카드는 전략 덱에만 넣을 수 있다 (§3-1)
                if sec!='전략': errs.append(f'[{sec}] 스킬 카드 「{name}」는 메인 · 상급 덱에 넣을 수 없음 (전략 덱만 가능)')
                continue
            if not set(c['tags'])&(allowed_st if sec=='전략' else allowed):
                who=f'스킬 「{sk["name"]}」' + (' 또는 전략 덱의 스킬 카드' if sec=='전략' and st_skills else '')
                errs.append(f'[{sec}] 「{name}」 태그 {c["tags"]} — {who}로 사용 불가')
            if c['type']=='몬스터' and not 1<=(c.get('level') or 0)<=10:
                errs.append(f'[{sec}] 「{name}」 레벨 {c.get("level")} — 레벨은 1~10 (레벨 0은 존재하지 않음, §3-2)')
            elif sec=='메인' and c['deck']!='메인': errs.append(f'[메인] 「{name}」(레벨 {c.get("level")})는 상급 덱 카드')
            elif sec=='상급' and c['deck']!='상급': errs.append(f'[상급] 「{name}」는 메인 덱 카드')
    st=sum(n for n,_ in deck['전략'])
    if policy and st!=STRATEGY_FILL: errs.append(f'[전략] {st}장 — 시뮬레이션 방침상 {STRATEGY_FILL}장을 채워야 함')
    cnt=Counter(); 
    for sec in('메인','상급'):
        for n,name in deck[sec]: cnt[name]+=n
    for name,n in cnt.items():
        if n>MAX_COPIES: errs.append(f'「{name}」 {n}장 — 동명 카드는 {MAX_COPIES}장까지')
    for n,name in deck['전략']:
        if cnt[name]+n>MAX_COPIES:
            warns.append(f'[전략] 「{name}」 전량 교체 시 {cnt[name]+n}장이 될 수 있음 — 교체 시점에 3장 제한 검사')
    return errs,warns

def load(path,policy=True):
    deck,perr=parse(open(path,encoding='utf-8').read())
    verr,warn=validate(deck,policy) if not perr else ([],[])
    return deck,perr+verr,warn

if __name__=='__main__':
    for p in sys.argv[1:]:
        d,e,w=load(p)
        print(f'■ {p} — {d["이름"] or "(이름 없음)"} / 스킬 {d["스킬"]}')
        for s in('메인','상급','전략'): print(f'   {s} {sum(n for n,_ in d[s])}장')
        for x in e: print('   ✗',x)
        for x in w: print('   △',x)
        print('   → 등록 가능' if not e else '   → 등록 불가')

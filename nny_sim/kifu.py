"""기보 정리기 — 로그를 사람이 읽기 좋은 마크다운으로.

구성: 매치 → 라운드(선공 · 시작 패 · 결과) → 턴(형세 요약 한 줄 + 단계별 진행).
- ▶ 발동 · 소환 · 공격 같은 행동, ↳ 체인 처리, ✦ 결과(파괴 · 대미지 · 서치), · 판단(선택 + 대안 2개)
- 판단 줄은 후보가 둘 이상인 경우만, 멀리건 · 서치 대상 같은 사소한 판단은 생략한다.
"""
import re

SKIP_DEC = ('멀리건', '서치', '대상', '버릴 카드', '드로우 덱', '인카운터 분기')

def short(name):
    return name.split(' (')[0]

def render(log, title='기보', max_matches=None, names=None):
    out = [f'# {title}', '', '> 기호: **▶** 행동 · **↳** 체인 처리 · **✦** 결과 · *판단*은 고른 수와 대안(학습 승률). 형세 줄은 턴 시작 시점.', '']
    names = list(names or []); match_no = 0; rnd_no = 0
    def S(m):
        for n in names: m = m.replace(n, short(n))
        return m
    phase = None; buf = []
    def flush():
        nonlocal buf
        out.extend(buf); buf = []
    for e in log:
        k = e['k']; m = e['m']; d = e.get('data')
        if k == 'match':
            match_no += 1
            if max_matches and match_no > max_matches: break
            flush(); out += ['', '---', '', f'## {m}', '']
            continue
        if k == 'round':
            if d and 'decks' in d:
                rnd_no = d['round']
            flush(); out += ['', f'### {S(m.strip("█ ").strip())}', '']; phase = None
            continue
        if k == 'side':
            flush(); out.append(f'- 🔁 {S(m)}'); continue
        if k == 'snap':
            flush()
            if not d: continue
            nm = [short(x) for x in names] if len(names) == 2 else ['선', '후']
            fld = f' · 필드 존: {d["field"][0]}({nm[d["field"][1]]})' if d.get('field') else ''
            out += ['', f'#### {e["t"]}턴 · {nm[e["tp"]]}', '',
                    f'`HP {nm[0]} {d["hp"][0]} / {nm[1]} {d["hp"][1]}` · 패 {d["hand"][0]}/{d["hand"][1]} · 덱(메인/상급) {d["deck"][0]} · {d["deck"][1]}{fld}', '']
            for i in (0, 1):
                items = d['mons'][i] + d['spells'][i]
                out.append(f'- {nm[i]} 필드: ' + (', '.join(items) if items else '(비어 있음)'))
            out.append(''); phase = None
            continue
        if k == 'turn':
            continue
        if k == 'end':
            flush(); out += ['', f'**{S(m.strip("■ "))}**', '']; continue
        if k == 'draw' and '시작 패' in m:
            out.append(f'- {S(m)}'); continue
        if e['t'] == 0 and k == 'draw': continue
        ph = e.get('ph')
        if ph and ph != phase and e['t'] > 0:
            phase = ph; buf.append(f'- **[{ph}]**')
        if k == 'decision':
            if not d or d['decision'].startswith(SKIP_DEC) or len(d['opts']) < 2: 
                if '멀리건' in m and '판단' not in m: out.append(f'- {S(m)}')
                continue
            alts = [f'{lab} {v}%' for lab, v, n in d['opts'] if lab != d['pick']][:2]
            buf.append(f'  - *판단 ({d["decision"]}): {d["pick"]}* — 대안 ' + (', '.join(alts) if alts else '없음'))
            continue
        if k in ('act', 'res', 'sys', 'draw'):
            t0 = S(m); t = t0.replace(' 0번 효과 발동', ' 발동(필드에 놓기)').replace(' 0번 처리', ' 발동 처리')
            if re.search(r'효과 발동|일반소환|특수소환|→ .*|직접공격|세트$', t0) and k == 'act' and '대미지' not in t and '패에 넣음' not in t:
                buf.append(f'  - ▶ {t}')
            elif k == 'res':
                buf.append(f'    - ↳ {t}')
            elif k == 'draw':
                buf.append(f'  - {t}')
            else:
                buf.append(f'    - ✦ {t}')
    flush()
    return '\n'.join(out)

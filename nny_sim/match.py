"""매치(3판 2선승) 진행 + 전략 덱 교체(사이드) 학습.

정본 4: 라운드가 끝날 때마다 각자 전략 덱과 카드를 교체할 수 있다(메인 · 상급 매수는 그대로 — 같은 종류끼리 1:1 교체).
교체 판단은 상대 덱별 카드 승률표(learned/side.json)로 한다:
  카드 가치 = 그 카드가 활성 덱(메인+상급)에 있었던 라운드의 승률 (상대 덱별, 없으면 50%)
  전략 덱 카드의 가치가 활성 덱의 가장 낮은 카드보다 높으면 1:1 교체 (동명 3장 제한 유지)
라운드가 끝날 때마다 활성 덱의 모든 카드에 그 라운드 승패를 기록한다.
"""
import random
from engine import Game
from cards import Impl, POOL
from policy import Table

SIDE = Table('side')

def counts_of(d, secs=('메인', '상급')):
    c = {}
    for s in secs:
        for n, name in d[s]: c[name] = c.get(name, 0) + n
    return c

def deck_from(base, active, strat):
    d = dict(base); d['메인'] = []; d['상급'] = []; d['전략'] = []
    for name, n in sorted(active.items()):
        if n > 0: d['메인' if POOL[name]['deck'] == '메인' else '상급'].append((n, name))
    d['전략'] = [(n, name) for name, n in sorted(strat.items()) if n > 0]
    return d

def card_value(me, opp, name, A=10.0):
    """카드 기여도 = 사용률 × 사용 시 승률 + (1 − 사용률) × 0.4 (안 쓰이고 남는 카드는 0.4로 수렴)
    전략 덱에서 한 번도 들어가 보지 않은 카드는 0.5 — 지는 덱은 자연스럽게 새 카드를 시험한다."""
    b = f'{me} vs {opp}|카드|{name}'
    w, n = SIDE.L1.get(b + '|사용', (0, 0)); _, pn = SIDE.L1.get(b + '|존재', (0, 0))
    if pn == 0: return 0.5
    u = (n + 1) / (pn + 2); pw = (w + 0.5 * A) / (n + A)
    return u * pw + (1 - u) * 0.4

def skill_tags(skill):
    sk = POOL[skill]; return set(sk['skill_tags']) | (set() if sk.get('no_common') else {'공용'})

def fits(name, skill):
    """덱 구축 기준은 태그 (§3-1): 스킬에 표기된 태그 또는 「공용」"""
    return bool(set(POOL[name]['tags']) & skill_tags(skill))

def is_skill(name): return POOL[name]['type'] == '스킬'

def side_swap(deck, opp_skill, rng, eps=0.0, log=None, pname=''):
    me = deck['스킬']; act = counts_of(deck); st = counts_of(deck, ('전략',))
    swaps = []
    # 전략 덱의 스킬 카드 (§3-1): 새 스킬의 태그로 메인 · 상급 덱을 모두 쓸 수 있을 때만 교체 후보
    skills = lambda: [n for n, k in st.items() if k > 0 and is_skill(n) and n != me and all(fits(x, n) for x, k2 in act.items() if k2 > 0)]
    new = me
    explore = eps and rng.random() < eps
    if explore:   # 탐색: 무작위 1~2장 교체
        for _ in range(rng.choice((1, 2))):
            ins = [n for n, k in st.items() if k > 0 and not is_skill(n) and act.get(n, 0) < 3 and fits(n, me)]
            if not ins: break
            i = rng.choice(ins); kind = POOL[i]['deck']
            outs = [n for n, k in act.items() if k > 0 and POOL[n]['deck'] == kind and n != i]
            if not outs: continue
            o = rng.choice(outs); swaps.append((o, i, '탐색'))
            act[o] -= 1; act[i] = act.get(i, 0) + 1; st[i] -= 1; st[o] = st.get(o, 0) + 1
    else:
        for _ in range(10):
            ins = sorted([n for n, k in st.items() if k > 0 and not is_skill(n) and act.get(n, 0) < 3 and fits(n, me)],
                         key=lambda n: -card_value(me, opp_skill, n))
            done = False
            for i in ins:
                kind = POOL[i]['deck']; vi = card_value(me, opp_skill, i)
                outs = sorted([n for n, k in act.items() if k > 0 and POOL[n]['deck'] == kind and n != i], key=lambda n: card_value(me, opp_skill, n))
                if outs and card_value(me, opp_skill, outs[0]) + 0.02 < vi:
                    o = outs[0]; swaps.append((o, i, f'{card_value(me, opp_skill, o)*100:.0f}%→{vi*100:.0f}%'))
                    act[o] -= 1; act[i] = act.get(i, 0) + 1; st[i] -= 1; st[o] = st.get(o, 0) + 1
                    done = True; break
            if not done: break
    # 스킬 교체: 스킬 가치 = 그 스킬을 쓴 라운드의 기여도 (써 본 적 없으면 0.5)
    sks = skills()
    if sks:
        if explore:
            if rng.random() < 0.5: new = rng.choice(sks)
        else:
            best = max(sks, key=lambda n: card_value(n, opp_skill, n))
            if card_value(me, opp_skill, me) + 0.02 < card_value(best, opp_skill, best): new = best
    if new != me:
        swaps.append((me, new, '스킬 교체')); st[new] -= 1; st[me] = st.get(me, 0) + 1
    if log is not None:
        if swaps:
            log.append({'t': 0, 'ph': '', 'tp': 0, 'k': 'side', 'm': f'{pname} 전략 덱 교체: ' + ', '.join(f'「{o}」 → 「{i}」 ({why})' for o, i, why in swaps),
                        'data': {'player': pname, 'swaps': swaps}})
        else:
            log.append({'t': 0, 'ph': '', 'tp': 0, 'k': 'side', 'm': f'{pname} 전략 덱 교체 없음', 'data': {'player': pname, 'swaps': []}})
    d = deck_from(deck, act, st); d['스킬'] = new
    return d

def record_round(deck, opp_skill, won, used):
    me = deck['스킬']
    for name in list(counts_of(deck)) + [me]:   # 스킬 카드도 기록 — 전략 덱 스킬 교체 판단용
        b = f'{me} vs {opp_skill}|카드|{name}'
        e = SIDE.L1.setdefault(b + '|존재', [0, 0]); e[0] += int(won); e[1] += 1
        if name in used:
            e = SIDE.L1.setdefault(b + '|사용', [0, 0]); e[0] += int(won); e[1] += 1

import re
_RE = re.compile(r'^(.+?) 「(.+?)」 (?:\d번 효과 발동|일반소환|특수소환)')
def used_cards(log_slice, pname):
    out = set()
    for e in log_slice:
        m = _RE.match(e['m'])
        if m and m.group(1) == pname: out.add(m.group(2))
    return out

def play_match(dA, dB, first, rng, log, make_ai, side=True, side_eps=0.0, learn_side=True, side_fn=None):
    """make_ai(deck) -> AI. 반환: (매치 승자, 라운드 목록)
    side_fn(i, decks, wins, rounds, rng, side_eps, log) -> 플레이어 i의 새 덱. 없으면 학습표 교체(side_swap) — DRL 정책 연결용"""
    decks = [dA, dB]; wins = [0, 0]; rounds = []; f = first; rnd = 0
    while max(wins) < 2:   # 승점 2점 선취 (§11-2). 라운드는 규칙의 종료 조건으로만 끝나므로 무승부는 없다
        rnd += 1
        log.append({'t': 0, 'ph': '', 'tp': 0, 'k': 'round', 'm': f'████ {rnd}라운드 — 선공 {decks[f]["이름"]} ████',
                    'data': {'round': rnd, 'first': f, 'decks': [counts_of(d) for d in decks]}})
        i0 = len(log)
        seed = rng.randrange(2 ** 31)
        g = Game(decks, [make_ai(decks[0]), make_ai(decks[1])], f, random.Random(seed), log, Impl)
        g.seed = seed; g.dlog = []          # 탐색 AI의 재현용
        w, why = g.run()
        rounds.append({'first': f, 'winner': w, 'reason': why, 'turns': g.turn, 'log': (i0, len(log))})
        wins[w] += 1
        if learn_side:
            for i in (0, 1): record_round(decks[i], decks[1 - i]['스킬'], w == i, used_cards(log[i0:], decks[i]['이름']))
        if max(wins) < 2 and side:
            if side_fn is None:
                decks = [side_swap(decks[i], decks[1 - i]['스킬'], rng, side_eps, log, decks[i]['이름']) for i in (0, 1)]
            else:
                decks = [side_fn(i, decks, wins, rounds, rng, side_eps, log) for i in (0, 1)]
        # 교체 후, 이전 라운드의 패자가 선후공을 결정한다 (정본 4, §11-2)
        loser = 1 - w
        f = loser if make_ai(decks[loser]).wants_first(decks[w]['스킬']) else w
    mw = 0 if wins[0] > wins[1] else 1 if wins[1] > wins[0] else None
    return mw, rounds

"""덱 레시피 학습 (한 장 단위 국소 탐색 + 단계별 걸러내기).

한 라운드:
  1) 현재 레시피에서 한 장 추가 · 한 장 제거 · 한 장 교체한 합법 후보를 전부 만든다 (덱 구축 규칙 검사 통과분만).
  2) 모든 후보를 짧게 평가 → 상위만 길게 평가 → 최종 후보를 현재 레시피와 같은 시드로 맞대결 비교.
  3) 차이가 통계적으로 유의(쌍대 비교 z > 1.96)하면 채택, 아니면 현재 레시피 유지.
평가 상대는 구현된 다른 덱 전부(균등 가중), 선공 5:5, 판단은 학습형 정책(학습 끔).
상태는 learned/deckopt_<스킬>.json에 저장되어 여러 번에 나눠 이어서 돌릴 수 있다.

전략 덱 채우기 (전략 덱이 방침 매수 STRATEGY_FILL보다 적을 때, 한 라운드에 1장):
  전략 덱 카드는 라운드 사이 교체 때만 쓰이므로, 전략 덱에 1장 더하는 것만으로는 평가 결과가 거의 달라지지 않는다.
  그래서 후보 카드마다 「같은 종류(메인/상급)에서 기여도가 가장 낮은 카드와 1장 바꾼 덱」을 시험 평가해
  그 승률이 가장 높은 카드를 전략 덱에 넣는다(활성 덱은 바꾸지 않는다). 방침상 채워야 하므로 유의성 검정은 하지 않는다.
  실행: python deck_opt.py <시작 덱> fill   (전략 덱이 찰 때까지 반복)
"""
import json, os, random, sys, time, glob, math
from engine import Game
from cards import Impl, IMPL, POOL
from policy import LearnedAI
import deck as D

def legal_names(skill):
    sk = POOL[skill]; tags = set(sk['skill_tags']) | (set() if sk.get('no_common') else {'공용'})
    return sorted(n for n, c in POOL.items() if c['type'] != '스킬' and set(c['tags']) & tags and n in IMPL)

def to_deck(name, skill, counts, strat=None):
    d = {'이름': name, '스킬': skill, '메인': [], '상급': [], '전략': []}
    for n, k in sorted(counts.items()):
        if k > 0: d['메인' if POOL[n]['deck'] == '메인' else '상급'].append((k, n))
    d['전략'] = [(k, n) for n, k in sorted((strat or {}).items()) if k > 0]
    return d

def valid(skill, counts, strat):
    """덱 구축 규칙을 지키고 전략 덱이 방침 매수(STRATEGY_FILL) 이하인가 — 채우는 중인 덱도 후보로 다룬다"""
    e, _ = D.validate(to_deck('x', skill, counts, strat), policy=False)
    return not e and sum(strat.values()) <= D.STRATEGY_FILL

def neighbors(skill, counts, strat, rng, n_swap=140, n_strat=60):
    """한 장 단위 이웃: 메인/상급 추가 · 제거 · 교체, 전략 덱 교체(매수 유지). 교체류는 무작위 표본."""
    names = legal_names(skill); out = []
    for a in names:
        if counts.get(a, 0) < 3:
            c = dict(counts); c[a] = c.get(a, 0) + 1
            if valid(skill, c, strat): out.append((f'+{a}', c, strat))
    swaps = []
    for r in [n for n, k in counts.items() if k > 0]:
        c = dict(counts); c[r] -= 1
        if valid(skill, c, strat): out.append((f'-{r}', c, strat))
        for a in names:
            if a == r or counts.get(a, 0) >= 3 or POOL[a]['deck'] != POOL[r]['deck']: continue
            swaps.append((r, a))
    for r, a in rng.sample(swaps, min(n_swap, len(swaps))):
        c = dict(counts); c[r] -= 1; c[a] = c.get(a, 0) + 1
        if valid(skill, c, strat): out.append((f'-{r} +{a}', c, strat))
    ss = [(r, a) for r in [n for n, k in strat.items() if k > 0] for a in names if a != r and strat.get(a, 0) < 3]
    for r, a in rng.sample(ss, min(n_strat, len(ss))):
        s2 = dict(strat); s2[r] -= 1; s2[a] = s2.get(a, 0) + 1
        if valid(skill, counts, s2): out.append((f'전략 -{r} +{a}', counts, s2))
    return out

def fill_candidates(skill, counts, strat, opps):
    """전략 덱 채우기 후보: [(label, 시험용 활성 덱, 1장 더한 전략 덱)].
    시험용 활성 덱 = 후보 카드를 같은 종류에서 기여도가 가장 낮은 카드와 1장 바꾼 덱.
    활성 덱과 전략 덱을 합쳐 3장을 넘는 후보는 교체에 쓸 수 없으므로 뺀다."""
    import season as S
    con = S.contribution(to_deck('x', skill, counts, strat), {o['스킬']: o for o in opps})
    out = []
    for a in legal_names(skill):
        if counts.get(a, 0) + strat.get(a, 0) >= 3: continue
        outs = sorted([n for n, k in counts.items() if k > 0 and n != a and POOL[n]['deck'] == POOL[a]['deck']], key=lambda n: (con[n], n))
        if not outs: continue
        c2 = dict(counts); c2[outs[0]] -= 1; c2[a] = c2.get(a, 0) + 1
        s2 = dict(strat); s2[a] = s2.get(a, 0) + 1
        if valid(skill, counts, s2) and valid(skill, c2, strat): out.append((f'전략 +{a} (시험: 「{outs[0]}」 → 「{a}」)', c2, s2))
    return out

def fill_round(state, opps):
    t0 = time.time(); STALLS[0] = 0; skill = state['skill']; cur = state['counts']; cst = state['strat']; rnd = len(state['history']) + 1
    seed = 1000003 * rnd
    cands = fill_candidates(skill, cur, cst, opps)
    if not cands:
        rec = {'round': rnd, 'mode': '전략 덱 채우기', 'candidates': 0, 'stopped': '더 넣을 수 있는 후보 없음', 'strat_total': sum(cst.values())}
        state['history'].append(rec); return rec
    s1 = [(rate(evaluate(skill, c, opps, 2, seed, s)), lab, c, s) for lab, c, s in cands]
    s1.sort(key=lambda x: -x[0]); top = s1[:8]
    s2 = [(rate(evaluate(skill, c, opps, 8, seed + 7, s)), lab, c, s) for _, lab, c, s in top]
    s2.sort(key=lambda x: -x[0]); best = s2[0]
    base = rate(evaluate(skill, cur, opps, 8, seed + 7, cst))
    state['strat'] = best[3]
    rec = {'round': rnd, 'mode': '전략 덱 채우기', 'candidates': len(cands), 'base': round(base * 100, 1), 'best': best[1],
           'best_rate': round(best[0] * 100, 1), 'top3': [(lab, round(r * 100, 1)) for r, lab, _, _ in s2[:3]],
           'strat_total': sum(best[3].values()), 'stalled': STALLS[0], 'sec': round(time.time() - t0)}
    state['history'].append(rec)
    return rec

STALLS = [0]   # 규칙상 끝나지 않아 안전장치(SAFETY_TURNS)로 중단된 매치 수

def play(me, opp, first_me, seed):
    """Bo3 매치 (전략 덱 교체 포함, 학습 끔) — 반환: 매치 승리 1 / 패배 0 / 판정 없음 None (안전장치 중단)"""
    import match as M
    from engine import StalledGame
    try:
        mw, _ = M.play_match(me, opp, 0 if first_me else 1, random.Random(seed), [],
                             lambda x: LearnedAI(x['스킬'], learn=False), learn_side=False)
    except StalledGame:
        STALLS[0] += 1; return None
    return None if mw is None else int(mw == 0)

def evaluate(skill, counts, opps, n_per, seed0, strat=None):
    me = to_deck('후보', skill, counts, strat); res = []
    for k in range(n_per):
        for j, o in enumerate(opps):
            for f in (True, False):
                res.append(play(me, o, f, seed0 + k * 100 + j * 10 + f))
    return res

def rate(r): v = [x for x in r if x is not None]; return sum(v) / max(1, len(v))

def paired_z(a, b):
    d = [x - y for x, y in zip(a, b) if x is not None and y is not None]
    m = sum(d) / len(d); sd = math.sqrt(sum((x - m) ** 2 for x in d) / max(1, len(d) - 1))
    return m, (m / (sd / math.sqrt(len(d))) if sd else 0.0)

def one_round(state, opps, budget=270):
    if sum(state['strat'].values()) < D.STRATEGY_FILL: return fill_round(state, opps)   # 방침 매수까지 전략 덱부터 채운다
    t0 = time.time(); STALLS[0] = 0; skill = state['skill']; cur = state['counts']; cst = state['strat']; rnd = len(state['history']) + 1
    seed = 1000003 * rnd; rng = random.Random(seed)
    cands = neighbors(skill, cur, cst, rng)
    s1 = [(rate(evaluate(skill, c, opps, 2, seed, s)), lab, c, s) for lab, c, s in cands]
    s1.sort(key=lambda x: -x[0]); top = s1[:24]
    s2 = [(rate(evaluate(skill, c, opps, 8, seed + 7, s)), lab, c, s) for _, lab, c, s in top]
    s2.sort(key=lambda x: -x[0]); top = s2[:3]
    base3 = evaluate(skill, cur, opps, 40, seed + 13, cst); s3 = []
    for _, lab, c, s in top:
        r = evaluate(skill, c, opps, 40, seed + 13, s); s3.append((rate(r), lab, c, s, r))
        if time.time() - t0 > budget: break
    s3.sort(key=lambda x: -x[0]); best = s3[0]
    m, z = paired_z(best[4], base3)
    rec = {'round': rnd, 'candidates': len(cands), 'base': round(rate(base3) * 100, 1), 'best': best[1],
           'best_rate': round(best[0] * 100, 1), 'diff': round(m * 100, 2), 'z': round(z, 2), 'accepted': z > 1.96,
           'top3': [(lab, round(r * 100, 1)) for r, lab, _, _, _ in s3], 'matches_final': len(base3), 'stalled': STALLS[0], 'sec': round(time.time() - t0)}
    if z > 1.96: state['counts'] = best[2]; state['strat'] = best[3]
    state['history'].append(rec)
    return rec

def load_state(skill, start_deck):
    path = os.path.join('learned', f'deckopt_{skill}.json')
    if os.path.exists(path):
        st = json.load(open(path, encoding='utf-8'))
        if 'strat' in st: return st, path
    d, e, _ = D.load(start_deck, policy=False); assert not e, e   # 전략 덱을 채우는 중인 덱도 시작점으로 쓸 수 있다
    counts = {}; strat = {}
    for sec in ('메인', '상급'):
        for k, n in d[sec]: counts[n] = counts.get(n, 0) + k
    for k, n in d['전략']: strat[n] = strat.get(n, 0) + k
    return {'skill': d['스킬'], 'start': start_deck, 'counts': counts, 'strat': strat, 'history': []}, path

if __name__ == '__main__':
    import season as S
    start = sys.argv[1]; arg = sys.argv[2] if len(sys.argv) > 2 else '1'
    sk = D.load(start)[0]['스킬']
    state, path = load_state(sk, start)
    rounds = max(0, D.STRATEGY_FILL - sum(state['strat'].values())) if arg == 'fill' else int(arg)   # fill: 전략 덱이 찰 때까지
    decks = S.load_decks(); opps = [d for k, d in decks.items() if k != sk]
    print('상대:', [o['이름'] for o in opps])
    for _ in range(rounds):
        rec = one_round(state, opps)
        if rec.get('stopped'): print(json.dumps(rec, ensure_ascii=False), flush=True); break
        json.dump(state, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        base_name = D.load(start)[0]['이름']
        name = (f'{base_name.split(" [전략 덱")[0]} [전략 덱 {rec["strat_total"]}장 채움]' if rec.get('mode') == '전략 덱 채우기'
                else f'{base_name.split(" (")[0]} (레시피 학습 {len(state["history"])}라운드 · 매치 기준)')
        nd = to_deck(name, sk, state['counts'], state['strat'])
        S.save_deck(nd)
        print(json.dumps(rec, ensure_ascii=False), flush=True)

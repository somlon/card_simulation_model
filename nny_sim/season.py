"""시즌 학습: 구현된 모든 덱의 모든 조합을 Bo3 매치로 돌리며
  ① 판단 정책(learned/policy.json) ② 전략 덱 교체 · 카드 기여도(learned/side.json)를 학습하고
  ③ 덱마다 매치 패배가 ADJUST_EVERY회 쌓이면 그 덱에 레시피 학습기(deck_opt.one_round) 한 라운드를 돌린다(자동 덱 조정).
     후보 = 한 장 추가 · 제거 · 교체(매수 증감 포함, 로그 기여도 하위 카드 교체를 우선), 짧게 → 길게 → 최종 짝 비교,
     유의(z > 1.96)할 때만 채택. 예전 방식(기여도 하위 3종의 감소 · 제거 · 교체만)은 매수를 줄이기만 해서 바꿈(사용자 지시 2026-10-06).
덱 레시피의 현재 버전은 learned/decks/<스킬>.json 에 저장되며, 조정 이력은 learned/adjust_log.json.
"""
import json, os, glob, random, time, itertools, sys, math
import deck as D
import policy as P
import match as M
from cards import POOL, IMPL

ADJUST_EVERY = 60
DECK_DIR = os.path.join('learned', 'decks'); os.makedirs(DECK_DIR, exist_ok=True)
STATE = os.path.join('learned', 'season.json')

def load_decks():
    decks = {}
    for f in sorted(glob.glob('decks/시제_*.deck')):
        d = D.load(f)[0]; sk = d['스킬']; p = os.path.join(DECK_DIR, f'{sk}.json')
        if os.path.exists(p): d = json.load(open(p, encoding='utf-8')); d = {k: [tuple(x) for x in v] if isinstance(v, list) else v for k, v in d.items()}
        decks[sk] = d
    return decks

def save_deck(d):
    json.dump(d, open(os.path.join(DECK_DIR, f'{d["스킬"]}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    lines = [f"이름: {d['이름']}", f"스킬: {d['스킬']}"]
    for sec in ('메인', '상급', '전략'):
        lines.append(f'[{sec}]'); lines += [f'{k} {n}' for k, n in d[sec]]
    open(os.path.join('decks', f'학습_{d["스킬"].replace(" ", "_")}.deck'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')

def contribution(d, decks):
    """덱 d의 카드별 기여도 — 상대 덱별 기여도를 그 상대와의 표본 수로 가중 평균"""
    me = d['스킬']; out = {}
    for name in M.counts_of(d):
        num = den = 0
        for op in decks:
            if op == me: continue
            _, pn = M.SIDE.L1.get(f'{me} vs {op}|카드|{name}|존재', (0, 0))
            if pn: num += M.card_value(me, op, name) * pn; den += pn
        out[name] = num / den if den else 0.5
    return out

def eval_deck(d, decks, n, seed):
    """덱 d의 평균 매치 승률 (모든 상대, 선공 교대, 학습 끔)"""
    w = m = 0; rng = random.Random(seed)
    for op, od in decks.items():
        if op == d['스킬']: continue
        for i in range(n):
            mw, _ = M.play_match(d, od, i % 2, rng, [], lambda x: P.LearnedAI(x['스킬'], learn=False), learn_side=False)
            if mw is not None: m += 1; w += (mw == 0)
    return w / max(1, m), m

def adjust(d, decks, log, ev=None, n=(2, 8, 40)):
    """레시피 학습기 한 라운드로 덱 d를 조정한다 (판단은 학습형 정책, 학습 끔). 반환 (새 덱, 기록)"""
    import deck_opt as DO
    me = d['스킬']; st = DO.state_from_deck(d)
    con, val = DO.log_guides(me, st['counts'], st['strat'], decks)
    opps = [od for k, od in decks.items() if k != me]
    rec = DO.one_round(st, opps, ev=ev, contrib=con, value_of=val, n=n)
    rec = dict(rec, deck=me, 결정=rec['best'] if rec.get('accepted') else '현재 유지')
    if rec.get('accepted'):
        nd = DO.to_deck(d['이름'].split(' [')[0] + f' [자동 조정 {time.strftime("%m-%d %H:%M")}]', me, st['counts'], st['strat'])
        d = nd
    log.append(rec)
    return d, rec

if __name__ == '__main__':
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 250; eps = float(sys.argv[2]) if len(sys.argv) > 2 else 0.1
    decks = load_decks()
    try: st = json.load(open(STATE, encoding='utf-8'))
    except Exception: st = {'matches': 0, 'loss_since': {}, 'record': {}}
    try: alog = json.load(open(os.path.join('learned', 'adjust_log.json'), encoding='utf-8'))
    except Exception: alog = []
    rng = random.Random(int(time.time())); t0 = time.time(); n = 0
    pairs = list(itertools.combinations(sorted(decks), 2))
    while time.time() - t0 < budget:
        a, b = rng.choice(pairs); first = rng.randrange(2)
        try:
            mw, rounds = M.play_match(decks[a], decks[b], first, rng, [], lambda x: P.LearnedAI(x['스킬'], eps=eps), side_eps=eps)
        except Exception as ex:
            import traceback; st.setdefault('errors', []).append(f'{a} vs {b}: {traceback.format_exc()[-400:]}'); continue
        n += 1; st['matches'] += 1
        for i, sk in enumerate((a, b)):
            r = st['record'].setdefault(sk, [0, 0]); r[1] += 1
            if mw == i: r[0] += 1
            elif mw is not None:
                st['loss_since'][sk] = st['loss_since'].get(sk, 0) + 1
                if st['loss_since'][sk] >= ADJUST_EVERY:
                    st['loss_since'][sk] = 0
                    decks[sk], rec = adjust(decks[sk], decks, alog); save_deck(decks[sk])
                    print('자동 조정:', json.dumps(rec, ensure_ascii=False), flush=True)
    P.POLICY.games += n; P.POLICY.save(); M.SIDE.save()
    json.dump(st, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(alog, open(os.path.join('learned', 'adjust_log.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{n}매치 ({time.time()-t0:.0f}s) · 누적 {st["matches"]}매치 ·', {k: f'{v[0]}/{v[1]}' for k, v in st['record'].items()})

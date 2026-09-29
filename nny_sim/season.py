"""시즌 학습: 구현된 모든 덱의 모든 조합을 Bo3 매치로 돌리며
  ① 판단 정책(learned/policy.json) ② 전략 덱 교체 · 카드 기여도(learned/side.json)를 학습하고
  ③ 덱마다 매치 패배가 ADJUST_EVERY회 쌓이면 기여도가 가장 낮은 카드 3종류의 매수를 조정 · 제거한다(자동 덱 조정).
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

def adjust(d, decks, log):
    me = d['스킬']; con = contribution(d, decks)
    act = M.counts_of(d); st = M.counts_of(d, ('전략',))
    worst = sorted(act, key=lambda n: con[n])[:3]
    sk = POOL[me]; tags = set(sk['skill_tags']) | (set() if sk.get('no_common') else {'공용'})
    pool = [n for n, c in POOL.items() if c['type'] != '스킬' and set(c['tags']) & tags and n in IMPL]
    opts = [('현재 유지', d)]
    for w in worst:
        kind = POOL[w]['deck']
        repl = sorted([n for n in pool if POOL[n]['deck'] == kind and n != w and act.get(n, 0) < 3],
                      key=lambda n: -(con.get(n) if n in con else max([M.card_value(me, op, n) for op in decks if op != me] or [0.5])))[:1]
        for lab, delta in ((f'「{w}」 1장 감소', {w: -1}), (f'「{w}」 제거', {w: -act[w]})) + tuple((f'「{w}」 1장 → 「{r}」', {w: -1, r: +1}) for r in repl):
            a2 = dict(act)
            for k2, v in delta.items(): a2[k2] = a2.get(k2, 0) + v
            nd = M.deck_from(d, a2, st); e, _ = D.validate(nd)
            if not e: opts.append((lab, nd))
    seed = random.randrange(10 ** 9)
    s1 = sorted(((eval_deck(od, decks, 3, seed)[0], lab, od) for lab, od in opts), key=lambda x: -x[0])
    base = next(x for x in s1 if x[1] == '현재 유지')
    best = next((x for x in s1 if x[1] != '현재 유지'), None)
    rec = {'deck': me, '기여도 하위 3종': {w: round(con[w] * 100, 1) for w in worst},
           '후보': [(lab, round(r * 100, 1)) for r, lab, _ in s1]}
    if best:
        rb, nb = eval_deck(best[2], decks, 30, seed + 1); rc, nc = eval_deck(d, decks, 30, seed + 1)
        se = math.sqrt(max(1e-9, rb * (1 - rb) / max(1, nb) + rc * (1 - rc) / max(1, nc)))
        rec['재측정'] = {'현재': round(rc * 100, 1), best[1]: round(rb * 100, 1), '판수': nb, 'z': round((rb - rc) / se, 2)}
        if (rb - rc) / se > 1.64:
            rec['결정'] = best[1]; d = best[2]; d['이름'] = d['이름'].split(' [')[0] + f' [자동 조정 {time.strftime("%m-%d %H:%M")}]'
        else: rec['결정'] = '현재 유지'
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

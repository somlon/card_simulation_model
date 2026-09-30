import sys, time, random, json
import match as M, policy as P, season as S
from search import SearchAI, rf_evaluator
ds = S.load_decks(); a = ds['번성충-대발생']; b = ds['솔루나 아츠']
mode = sys.argv[1]; n = int(sys.argv[2]); ev = rf_evaluator() if mode == 'rf' else None
w = m = 0; t0 = time.time()
for i in range(n):
    def mk(d):
        if d['스킬'] == a['스킬']:
            x = SearchAI(d['스킬'], 4, 3, key_only=True, depth=2); x.evaluator = ev; return x
        return P.LearnedAI(d['스킬'], learn=False)
    mw, _ = M.play_match(a, b, i % 2, random.Random(5000 + i), [], mk, learn_side=False)
    if mw is not None: m += 1; w += (mw == 0)
    if time.time() - t0 > 200: break
print(json.dumps({'형세 판정': 'RF' if ev else '수동 공식', '매치': m, '탐색 번성충 매치 승': w, '승률': round(w / m * 100, 1), '매치당 초': round((time.time() - t0) / m, 2)}, ensure_ascii=False))

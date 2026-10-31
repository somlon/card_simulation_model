"""선후공별 시작 패 배분 전수 측정 (각 배분 · 각 선후공 N판)"""
import random, sys, json
from engine import Game
from cards import Impl
from ai import HeuristicAI
import deck as D
me, _, _ = D.load(sys.argv[1]); op, _, _ = D.load(sys.argv[2]); N = int(sys.argv[3])
rng = random.Random(int(sys.argv[4]) if len(sys.argv) > 4 else 5)
res = {}
for pos in ('first', 'second'):
    for k in range(5, -1, -1):
        w = n = 0
        for i in range(N):
            g = Game([me, op], [HeuristicAI(me['스킬'], {pos: k}), HeuristicAI(op['스킬'])], 0 if pos == 'first' else 1, rng, [], Impl)
            x, _ = g.run()
            if x is None: continue
            n += 1; w += (x == 0)
        res[(pos, k)] = (w, n); print(pos, k, f'{w/n*100:.1f}%', n, flush=True)
json.dump({f'{p}|{k}': v for (p, k), v in res.items()}, open('split_pos_result.json', 'w'))

"""덱 하나의 시작 패 배분(메인 k / 상급 5-k)을 전부 N판씩 측정. 선공 5:5. 상대는 현재 정책."""
import random, sys
from engine import Game
from cards import Impl
from ai import HeuristicAI
import deck as D
me, _, _ = D.load(sys.argv[1]); op, _, _ = D.load(sys.argv[2]); N = int(sys.argv[3])
rng = random.Random(int(sys.argv[4]) if len(sys.argv) > 4 else 21)
print('배분 | 전체 | 선공 | 후공 | 판수')
for k in range(5, -1, -1):
    w = {True: [0, 0], False: [0, 0]}
    for i in range(N):
        first_me = (i % 2 == 0)
        g = Game([me, op], [HeuristicAI(me['스킬'], {'first': k, 'second': k}), HeuristicAI(op['스킬'])], 0 if first_me else 1, rng, [], Impl)
        win, _ = g.run()
        if win is None: continue
        w[first_me][0] += (win == 0); w[first_me][1] += 1
    tot = w[True][0] + w[False][0]; n = w[True][1] + w[False][1]
    f = lambda a: f'{a[0]/a[1]*100:.1f}% ({a[0]}-{a[1]-a[0]})'
    print(f'메인{k}/상급{5-k} | {tot/n*100:.1f}% | {f(w[True])} | {f(w[False])} | {n}', flush=True)

"""학습 실행: 탐색 비율 eps로 N판을 돌리며 학습표(learned/*.json)를 갱신·저장한다."""
import random, sys
from engine import Game
from cards import Impl
import ai as A
import deck as D
a, _, _ = D.load(sys.argv[1]); b, _, _ = D.load(sys.argv[2]); N = int(sys.argv[3]); eps = float(sys.argv[4]) if len(sys.argv) > 4 else 0.2
A.BREEDING.eps = eps; rng = random.Random(int(sys.argv[5]) if len(sys.argv) > 5 else 99)
for i in range(N):
    g = Game([a, b], [A.HeuristicAI(a['스킬']), A.HeuristicAI(b['스킬'])], i % 2, rng, [], Impl); g.run()
A.BREEDING.save()
for k in sorted(A.BREEDING.t):
    print(k, {o: f'{(w+1)/(n+2)*100:.1f}% n={n}' for o, (w, n) in A.BREEDING.t[k].items()})

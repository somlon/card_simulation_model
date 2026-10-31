"""전 판단 학습: 두 덱 모두 LearnedAI(탐색 eps)로 자기대전하며 승률표 갱신.
구간마다 탐색 없이(학습 끔) 휴리스틱 정책 상대 승률을 측정해 향상 여부를 기록한다."""
import random, sys, time, json
from engine import Game
from cards import Impl
from ai import HeuristicAI
import policy as P
import deck as D
a, _, _ = D.load(sys.argv[1]); b, _, _ = D.load(sys.argv[2])
chunks = int(sys.argv[3]); per = int(sys.argv[4]); ev = int(sys.argv[5]); eps = float(sys.argv[6]) if len(sys.argv) > 6 else 0.15
rng = random.Random(int(time.time()))
def evaluate(n):
    out = {}
    for who in (0, 1):   # who = 학습 정책을 쓰는 덱
        w = m = 0
        for i in range(n):
            ais = [P.LearnedAI(a['스킬'], learn=False) if who == 0 else HeuristicAI(a['스킬']),
                   P.LearnedAI(b['스킬'], learn=False) if who == 1 else HeuristicAI(b['스킬'])]
            x, _ = Game([a, b], ais, i % 2, rng, [], Impl).run()
            if x is None: continue
            m += 1; w += (x == who)
        out[[a, b][who]['스킬']] = round(w / m * 100, 1)
    return out
try: hist = json.load(open('learned/train_history.json'))
except Exception: hist = []
if P.POLICY.games == 0:
    base = evaluate(ev); print('학습 전 (학습 정책 vs 휴리스틱 상대):', base, flush=True); hist.append((0, base))
for c in range(chunks):
    t = time.time()
    for i in range(per):
        Game([a, b], [P.LearnedAI(a['스킬'], eps=eps), P.LearnedAI(b['스킬'], eps=eps)], i % 2, rng, [], Impl).run()
    P.POLICY.games += per; P.POLICY.save()
    r = evaluate(ev); hist.append((P.POLICY.games, r))
    print(f'누적 {P.POLICY.games}판 ({time.time()-t:.0f}s): {r}  L2 항목 {len(P.POLICY.L2)}', flush=True)
json.dump(hist, open('learned/train_history.json', 'w'), ensure_ascii=False)

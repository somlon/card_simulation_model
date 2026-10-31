"""시작 패 배분 학습 1단계: 배분(메인 0~5장)별 승률을 시뮬레이션으로 측정해 덱·선후공별 최적값을 고른다.
상대는 현재 정책으로 고정하고, 두 덱을 번갈아 갱신한다(반복 최적 대응)."""
import random, sys, json, math
from engine import Game
from cards import Impl
from ai import HeuristicAI
import deck as D

def game(dA, dB, first, splitA, splitB, rng):
    g = Game([dA, dB], [HeuristicAI(dA['스킬'], splitA), HeuristicAI(dB['스킬'], splitB)], first, rng, [], Impl)
    w, _ = g.run(); return w

def eval_split(me, opp, my_idx, pos, k, my_tab, opp_tab, n, rng):
    wins = 0; played = 0
    for i in range(n):
        tab = dict(my_tab); tab[pos] = k
        first = my_idx if pos == 'first' else 1 - my_idx
        if my_idx == 0: w = game(me, opp, first, tab, opp_tab, rng)
        else: w = game(opp, me, first, opp_tab, tab, rng)
        if w is None: continue
        played += 1; wins += (w == my_idx)
    return wins / max(1, played), played

if __name__ == '__main__':
    dA, _, _ = D.load(sys.argv[1]); dB, _, _ = D.load(sys.argv[2]); N = int(sys.argv[3]); iters = int(sys.argv[4])
    rng = random.Random(11)
    tabs = [{'first': 4, 'second': 4}, {'first': 5, 'second': 5}]
    decks = [dA, dB]; report = {}
    for it in range(iters):
        for me in (0, 1):
            for pos in ('first', 'second'):
                maxk = 5
                res = {k: eval_split(decks[me], decks[1 - me], me, pos, k, tabs[me], tabs[1 - me], N, rng) for k in range(0, maxk + 1)}
                bestk = max(res, key=lambda k: res[k][0])
                tabs[me][pos] = bestk
                report[(it, decks[me]['스킬'], pos)] = {k: round(v[0] * 100, 1) for k, v in res.items()}
                print(f'반복{it+1} {decks[me]["스킬"]} {"선공" if pos=="first" else "후공"}: ' +
                      ' '.join(f'메인{k}={v[0]*100:.1f}%' for k, v in res.items()) + f' → 메인 {bestk}', flush=True)
    print('최종 배분표:', json.dumps({decks[i]['스킬']: tabs[i] for i in (0, 1)}, ensure_ascii=False))

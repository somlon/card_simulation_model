"""선후공 원인 분석 + 말린 패 추출. 단판 N판 (선공 교대)."""
import random, sys, re, json, math, collections
from engine import Game
from cards import Impl
from ai import HeuristicAI
import deck as D
A_, _, _ = D.load(sys.argv[1]); B_, _, _ = D.load(sys.argv[2]); N = int(sys.argv[3])
rng = random.Random(4242)
OPPDEP = ('번성충-메뚜기여왕', '번성충-장수말벌여왕', '번성충-시체송장벌레', '번성충-넓적배사마귀', '번성충-맵시기생벌')
rows = []
for i in range(N):
    log = []; first = i % 2
    g = Game([A_, B_], [HeuristicAI(A_['스킬']), HeuristicAI(B_['스킬'])], first, rng, log, Impl)
    w, why = g.run()
    own = {0: [], 1: []}; seen = []
    for sn in g.snaps: own[sn['tp']].append(sn['turn'])
    def turn_of(e): return e['t']
    r = dict(first=first, winner=w, turns=g.turn, open=g.opening, snaps=g.snaps)
    # 행동 집계
    act = collections.Counter(); dmg = collections.Counter(); both_on = None; rm = collections.Counter()
    oppdep = collections.Counter(); sumn = collections.Counter()
    name0, name1 = g.p[0].name, g.p[1].name
    for e in log:
        m = e['m']; t = e['t']; tp = e['tp']
        mm = re.match(r'(.+?) 「(.+?)」 (\d)번 효과 발동', m)
        if mm:
            pi = 0 if mm.group(1) == name0 else 1
            act[(pi, t)] += 1
            if mm.group(2) in OPPDEP: oppdep[(pi, t)] += 1
        mm = re.match(r'(.+?) (\d+) 대미지', m)
        if mm: pi = 0 if mm.group(1) == name0 else 1; dmg[(1 - pi, t)] += int(mm.group(2))
        mm = re.match(r'(.+?) 「(.+?)」 (일반소환|특수소환)', m)
        if mm: pi = 0 if mm.group(1) == name0 else 1; sumn[(pi, t)] += 1; sumn[(pi, t, mm.group(2))] += 1
        if re.search(r'파괴$|덱으로$|제외$|릴리스$', m): rm[t] += 1
    r['own'] = own; r['act'] = {f'{k[0]}|{k[1]}': v for k, v in act.items()}
    r['oppdep'] = {f'{k[0]}|{k[1]}': v for k, v in oppdep.items()}
    r['dmg'] = {f'{k[0]}|{k[1]}': v for k, v in dmg.items()}
    r['sum'] = {'|'.join(map(str, k)): v for k, v in sumn.items()}
    rows.append(r)
json.dump(rows, open('analysis_rows.json', 'w'), ensure_ascii=False)
print(len(rows))

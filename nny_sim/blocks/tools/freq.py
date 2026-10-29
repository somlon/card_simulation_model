"""한 덱의 효과 발동 빈도: 그 덱이 낀 대전 n매치(휴리스틱)의 기록에서 「<카드> n번 효과 발동」 수. 사용: python3 freq.py <nny_sim> <덱 이름> <n> <seed>"""
import sys, os, re, collections, random
sim, deck, n, seed = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
sys.path.insert(0, sim); os.chdir(sim)
import match_sim as MS, match as M
MS._init({'ai': 'heuristic'})
names = sorted(MS._W['decks'])
cnt = collections.Counter(); wins = 0; games = 0; rx = re.compile(r'^(\S+) 「([^」]+)」 (\d+)번 효과 발동')
rng = random.Random(seed)
for i in range(n):
    opp = names[i % len(names)]
    decks = MS._W['decks']
    dA = dict(decks[deck], 이름='A'); dB = dict(decks[opp], 이름='B')
    log = []
    try:
        mw, rounds = M.play_match(dA, dB, i % 2, random.Random(seed * 1000 + i), log, MS._W['make_ai'], side=True, side_eps=0.0, learn_side=False)
    except Exception as ex:
        print('ERR', opp, ex); continue
    games += 1; wins += mw == 0
    for e in log:
        m = rx.match(e.get('m', ''))
        if m and m.group(1) == 'A': cnt[f'{m.group(2)}#{m.group(3)}'] += 1
print(f'{deck}: {wins}/{games} 승')
for k, v in cnt.most_common(): print(f'  {v:5} {k}')

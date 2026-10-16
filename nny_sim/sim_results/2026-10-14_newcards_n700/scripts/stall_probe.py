"""리그에서 안전장치(1000턴)로 중단된 솔루나 아츠 미러전 하나를 같은 시드로 다시 돌려 마지막 턴들의 양상을 본다"""
import collections, json, os, random, re, sys
sys.setrecursionlimit(10000); sys.path.insert(0, os.getcwd())
import match_sim as MS, match as M
from engine import StalledGame
MS._init({'ai': 'table', 'policy': None, 'side': None})
decks = MS._W['decks']; a = b = '솔루나 아츠'
dA = dict(decks[a], 이름=f"{decks[a]['이름']} [자리0]"); dB = dict(decks[b], 이름=f"{decks[b]['이름']} [자리1]")
seed, first = int(sys.argv[1]), int(sys.argv[2])
log = []
try:
    M.play_match(dA, dB, first, random.Random(seed), log, MS._W['make_ai'], side=True, side_eps=0.0, learn_side=False)
    print('끝남(중단 아님)')
except StalledGame as e:
    print('중단:', e)
NT = re.compile(r' \(시제품용[^)]*\)')
turns = [e for e in log if e.get('k') == 'turn']
print('턴 줄 수', len(turns)); print('\n'.join(NT.sub('', e['m']) for e in turns[:3])); print('...'); print('\n'.join(NT.sub('', e['m']) for e in turns[-3:]))
last_t = log[-1]['t']; tail = [e for e in log if e['t'] >= last_t - 4 and e.get('k') in ('act', 'res', 'sys', 'draw')]
print(f'--- 마지막 5턴 행동 {len(tail)}줄 중 앞 60줄')
for e in tail[:60]: print(e['t'], e.get('ph'), NT.sub('', e['m'])[:160])
c = collections.Counter(re.sub(r'\d+', '#', NT.sub('', e['m']))[:90] for e in log if e['t'] > 100 and e.get('k') in ('act', 'res', 'sys'))
print('--- 100턴 이후 자주 나온 줄'); [print(v, k) for k, v in c.most_common(15)]
snaps = [e for e in log if e.get('k') == 'snap' and e.get('data')]
for s in snaps[-2:]: print('형세', s['t'], s['data']['hp'], s['data']['hand'], s['data']['deck'], s['data']['mons'], s['data']['spells'])
print('--- 999~1000턴 모든 줄')
for e in log:
    if e['t'] >= 999: print(e['t'], e.get('ph'), e.get('k'), NT.sub('', e['m'])[:220])
# 마지막으로 공격 · 효과 발동이 있었던 턴
acts = [e for e in log if e.get('k') == 'act' and ('→' in e['m'] or '효과 발동' in e['m'] or '소환' in e['m'])]
print('마지막 행동 턴', acts[-1]['t'] if acts else None)
for e in acts[-12:]: print(' ', e['t'], NT.sub('', e['m'])[:200])

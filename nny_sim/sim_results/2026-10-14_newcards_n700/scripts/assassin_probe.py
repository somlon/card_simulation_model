"""던전마스터 다크엘프 어새신 1번 「같은 카드 한 체인 중복 발동」 영향 측정 (nny_sim 폴더에서 실행)
  python3 assassin_probe.py <리그 폴더> orig|fix <순서쌍당 매치 수> <출력.json>
리그 원자료의 앞쪽 매치를 같은 시드로 다시 돌린다. fix = 1번 발동 조건에 「이 카드의 1번이 체인에 없을 것」 추가.
"""
import collections, gzip, json, os, sys
sys.setrecursionlimit(10000); sys.path.insert(0, os.getcwd())
run, variant, n, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
import cards as C, cards9 as C9, match_sim as MS

DUN = '던전마스터 셔플!'
CNT = collections.Counter()
orig_fn = C.IMPL[C9.ASSASSIN]


def patched(c):
    orig_fn(c)
    e1 = next(e for e in c.effects if e.num == 1)
    cond0, res0 = e1.cond, e1.res

    def res1(g, c, p, l):
        CNT['res1'] += 1
        if c.zone != 'hand': CNT['res1_not_in_hand'] += 1
        return res0(g, c, p, l)
    e1.res = res1
    if variant == 'fix':
        e1.cond = lambda g, c, p, ev: cond0(g, c, p, ev) and not any(l.card is c and l.eff.num == 1 for l in g.chain)


C.IMPL[C9.ASSASSIN] = patched
MS._init(json.load(open(os.path.join(run, 'meta.json'), encoding='utf-8'))['ai'])

want = collections.defaultdict(list); league = {}
with gzip.open(os.path.join(run, 'rounds.jsonl.gz'), 'rt', encoding='utf-8') as f:
    for line in f:
        r = json.loads(line)
        if r.get('type', 'round') != 'round' or DUN not in r['decks'] or r['decks'][0] == r['decks'][1]: continue
        k = tuple(r['decks'])
        if r['round'] == 1 and len(want[k]) < n: want[k].append((r['match_id'], r['first_seat'], r['seed']))
        league.setdefault(r['match_id'], r['match_winner_seat'])
res = {'variant': variant, 'n': n, 'pairs': {}}
same = tot = 0
for (a, b), ms in sorted(want.items()):
    w = g = st = 0
    for mid, first, seed in ms:
        recs = MS.play_one(a, b, first, seed, mid)
        if not recs or recs[0].get('type', 'round') != 'round': st += 1; continue
        ds = 0 if a == DUN else 1
        mw = recs[0]['match_winner_seat']; w += (mw == ds); g += 1
        tot += 1; same += (mw == league.get(mid))
    res['pairs'][f'{a} vs {b}'] = {'dungeon_seat': 0 if a == DUN else 1, 'wins': w, 'games': g, 'stalled': st}
    print(variant, a, 'vs', b, w, '/', g, flush=True)
res['dungeon_win'] = sum(v['wins'] for v in res['pairs'].values()); res['games'] = sum(v['games'] for v in res['pairs'].values())
res['same_winner_as_league'] = [same, tot]; res['counts'] = dict(CNT)
json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(variant, '던전 매치 승률', round(100 * res['dungeon_win'] / res['games'], 2), res['games'], '리그와 같은 승자', same, '/', tot, dict(CNT))

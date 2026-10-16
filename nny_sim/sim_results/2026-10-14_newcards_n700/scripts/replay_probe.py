"""리그를 같은 시드로 다시 돌린다 — 다른 코드(수정 브랜치)의 nny_sim 폴더에서 실행해 수정 효과를 잰다
  python3 noswap_probe.py <리그 폴더> <순서쌍당 매치 수> <조각 번호> <조각 수> <출력.jsonl>
리그 원자료의 순서쌍마다 앞쪽 매치 N개(1라운드 선공 · 시드 그대로)를 play_match 그대로(교체 포함) 재생한다 — 코드만 바뀐 폴더에서 돌려 수정 효과를 잰다.
2 · 3라운드 선후공 선택 · 시작 패 배분 등 다른 판단은 리그와 같다 — 교체만 끈다.
"""
import collections, gzip, json, os, sys
sys.setrecursionlimit(10000); sys.path.insert(0, os.getcwd())
run, n, k, K, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
import match as M, match_sim as MS

_pm = M.play_match


def play_match_noswap(*a, **kw):
    kw['side'] = False
    return _pm(*a, **kw)


# (교체를 끄지 않는다)
MS._init(json.load(open(os.path.join(run, 'meta.json'), encoding='utf-8'))['ai'])
want = collections.defaultdict(list); league = {}
with gzip.open(os.path.join(run, 'rounds.jsonl.gz'), 'rt', encoding='utf-8') as f:
    for line in f:
        r = json.loads(line)
        if r.get('type', 'round') != 'round': continue
        key = tuple(r['decks'])
        if r['round'] == 1 and len(want[key]) < n: want[key].append((r['match_id'], r['first_seat'], r['seed']))
        league.setdefault(r['match_id'], (r['match_winner_seat'], r['match_rounds']))
pairs = sorted(want)[k::K]
with open(out, 'w', encoding='utf-8') as fo:
    for a, b in pairs:
        w = 0
        for mid, first, seed in want[(a, b)]:
            recs = MS.play_one(a, b, first, seed, mid)
            ok = bool(recs) and recs[0].get('type', 'round') == 'round'
            rec = dict(match_id=mid, decks=[a, b], first_seat=first, seed=seed, league_winner=league[mid][0], league_rounds=league[mid][1],
                       winner=recs[0]['match_winner_seat'] if ok else None, rounds=recs[0]['match_rounds'] if ok else None,
                       r1_winner=recs[0]['winner_seat'] if ok else None, stalled=not ok,
                       kind=(recs[0].get('type', 'round') if recs else 'none'), error=(recs[0].get('error', '')[-400:] if recs and not ok else ''))
            fo.write(json.dumps(rec, ensure_ascii=False) + '\n'); w += (rec['winner'] == 0)
        fo.flush(); print(a, 'vs', b, w, '/', len(want[(a, b)]), flush=True)
print('끝', out)

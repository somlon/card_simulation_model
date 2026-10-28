"""같은 시드 스모크: 모든 덱 쌍 × n매치(휴리스틱) — 오류 · 안전장치 중단 수와 매치 결과 요약. 사용: python3 smoke.py <nny_sim> <n> <seed> [out.json]"""
import sys, os, json, time, collections
sim, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
sys.path.insert(0, sim); os.chdir(sim)
import match_sim as MS
MS._init({'ai': 'heuristic'})
names = sorted(MS._W['decks'])
sched = MS.schedule(names, n, seed)
t0 = time.time(); res = []; errs = []; stalled = 0
for a, b, first, sd, mid in sched:
    recs = MS.play_one(a, b, first, sd, mid)
    for r in recs:
        if r.get('type') == 'error_match': errs.append((a, b, sd, r['error'][-1500:]))
        if r.get('type') == 'stalled_match': stalled += 1
    w = recs[0].get('match_winner_seat') if recs and 'match_winner_seat' in recs[0] else None
    res.append((a, b, sd, w, len(recs)))
dt = time.time() - t0
print(f'매치 {len(sched)} · {dt:.0f}s · 오류 {len(errs)} · 중단 {stalled}')
for e in errs[:5]: print('ERR', e[0], e[1], e[2]); print(e[3])
wins = collections.Counter()
for a, b, sd, w, k in res:
    if w is not None: wins[a if w == 0 else b] += 1
print({k: v for k, v in sorted(wins.items())})
if len(sys.argv) > 4: json.dump(dict(res=res, errs=[e[:3] for e in errs], stalled=stalled, sec=dt), open(sys.argv[4], 'w'), ensure_ascii=False)

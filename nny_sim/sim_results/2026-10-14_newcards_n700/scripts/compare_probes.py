"""같은 매치(순서쌍당 앞쪽 N개) 재생 결과 비교: 리그 원래 결과 vs 교체 끔(noswap) vs 수정 4건(fixed)
  python3 -I compare_probes.py <출력.md> <출력.json> noswap=<a.jsonl,b.jsonl> fixed=<c.jsonl,d.jsonl>
"""
import collections, json, sys

out_md, out_js = sys.argv[1], sys.argv[2]
sets = {}
for arg in sys.argv[3:]:
    k, v = arg.split('=', 1); recs = []
    for f in v.split(','):
        try: recs += [json.loads(l) for l in open(f, encoding='utf-8')]
        except FileNotFoundError: pass
    sets[k] = recs
SWING = [('던전마스터 셔플!', '호박옥 - 봉인의 계약'), ('투기장의 규칙', '데이터버그 패키지 프로그램'), ('희생제', '호박옥 - 몽식의 계약')]


def rates(recs, key):
    d = collections.defaultdict(lambda: [0, 0]); pair = collections.defaultdict(lambda: [0, 0]); st = 0
    for r in recs:
        w = r[key]
        if w is None: st += 1; continue
        a, b = r['decks']
        for s in (0, 1):
            dk, op = r['decks'][s], r['decks'][1 - s]
            d[dk][0] += (w == s); d[dk][1] += 1
            pair[(dk, op)][0] += (w == s); pair[(dk, op)][1] += 1
    return d, pair, st


def pc(x): return 100.0 * x[0] / x[1] if x[1] else float('nan')


L = []; J = {}
for name, label in (('noswap', '전략 덱 교체 끔'), ('fixed', '구현 오류 4건 수정')):
    recs = [r for r in sets.get(name, []) if not r['stalled'] or True]
    if not recs: continue
    base_d, base_p, _ = rates(recs, 'league_winner'); new_d, new_p, st = rates(recs, 'winner')
    n = len(recs)
    L += [f'### {label} — 같은 시드 재생 {n:,}매치 (순서쌍당 앞쪽 {n // max(1, len(base_p)) if base_p else 0}개 · 미러전 포함, 안전장치 중단 {st})', '',
          f'| 덱 | 리그(같은 매치) | {label} | 차이 |', '|---|---|---|---|']
    J[name] = {'matches': n, 'stalled': st, 'decks': {}, 'pairs': {}}
    for dk in sorted(base_d, key=lambda x: -pc(base_d[x])):
        a, b = pc(base_d[dk]), pc(new_d[dk])
        L.append(f'| {dk} | {a:.1f} | {b:.1f} | {b - a:+.1f} |'); J[name]['decks'][dk] = [a, b]
    ext = lambda P: sum(1 for k, v in P.items() if k[0] != k[1] and (pc(v) >= 90 or pc(v) <= 10))
    near = lambda P: sum(1 for k, v in P.items() if k[0] != k[1] and 40 <= pc(v) <= 60)
    big = sorted(((k, pc(base_p[k]), pc(new_p[k])) for k in base_p if k[0] != k[1] and k[0] < k[1]), key=lambda x: -abs(x[2] - x[1]))
    L += ['', f'- 한쪽이 90% 이상인 순서쌍(미러 제외 110개 중): 리그 {ext(base_p)} → {ext(new_p)}, 40~60% 접전: 리그 {near(base_p)} → {near(new_p)}',
          '- 가장 크게 바뀐 상성(행 덱 기준): ' + ' · '.join(f'{k[0]} vs {k[1]} {x:.0f} → {y:.0f}' for k, x, y in big[:6])]
    for a, b in SWING:
        if (a, b) in base_p:
            L.append(f'- 상성 역전 사례 {a} vs {b}: 리그 {pc(base_p[(a, b)]):.0f}% → {pc(new_p[(a, b)]):.0f}%')
    L.append('')
    J[name]['extreme'] = [ext(base_p), ext(new_p)]; J[name]['near'] = [near(base_p), near(new_p)]
    J[name]['top_changes'] = [[k[0], k[1], x, y] for k, x, y in big[:10]]
open(out_md, 'w', encoding='utf-8').write('\n'.join(L) + '\n'); json.dump(J, open(out_js, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n'.join(L))

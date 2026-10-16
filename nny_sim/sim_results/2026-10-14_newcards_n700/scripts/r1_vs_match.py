"""두 리그(학습표 AI · 빈 표 AI)의 1라운드 승률과 매치 승률 비교 — 전략 덱 교체(1라운드 뒤)의 몫을 가르기 위한 표
  python3 -I r1_vs_match.py <학습표 rounds.jsonl.gz> <빈 표 rounds.jsonl.gz> <출력.md> <출력.json>
1라운드는 두 AI 모두 같은 덱(교체 전) · 같은 시드의 1라운드 선공이라, 1라운드 승률 차이 = 라운드 안 플레이 차이,
매치 승률 차이 중 1라운드로 설명되지 않는 몫 = 2 · 3라운드(교체 · 선후공 선택 · 플레이) 몫이다.
"""
import collections, gzip, json, sys

PAIRS = [('던전마스터 셔플!', '호박옥 - 봉인의 계약'), ('투기장의 규칙', '데이터버그 패키지 프로그램'), ('희생제', '호박옥 - 몽식의 계약')]


def load(path):
    r1 = collections.defaultdict(lambda: [0, 0]); r23 = collections.defaultdict(lambda: [0, 0]); mt = collections.defaultdict(lambda: [0, 0])
    comeback = collections.defaultdict(lambda: [0, 0])   # 1라운드 진 덱이 매치를 이긴 비율
    pr1 = collections.defaultdict(lambda: [0, 0]); pm = collections.defaultdict(lambda: [0, 0])
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if r.get('type', 'round') != 'round': continue
            a, b = r['decks']
            for s in (0, 1):
                d, o = r['decks'][s], r['decks'][1 - s]
                won = r['winner_seat'] == s
                if r['round'] == 1:
                    r1[d][0] += won; r1[d][1] += 1; pr1[(d, o)][0] += won; pr1[(d, o)][1] += 1
                    mw = r['match_winner_seat'] == s
                    mt[d][0] += mw; mt[d][1] += 1; pm[(d, o)][0] += mw; pm[(d, o)][1] += 1
                    if not won and a != b: comeback[d][0] += mw; comeback[d][1] += 1
                else:
                    r23[d][0] += won; r23[d][1] += 1
    return r1, r23, mt, comeback, pr1, pm


def pct(x): return 100.0 * x[0] / x[1] if x[1] else float('nan')


T = load(sys.argv[1]); E = load(sys.argv[2])
decks = sorted(T[2], key=lambda d: -pct(T[2][d]))
L = ['| 덱 | 1R 승률 학습표 | 1R 승률 빈 표 | 1R 차 | 2·3R 승률 학습표 | 2·3R 승률 빈 표 | 매치 학습표 | 매치 빈 표 | 매치 차 | 1R 패 → 매치 역전 학습표 | 빈 표 |', '|---|---|---|---|---|---|---|---|---|---|---|']
out = {'decks': {}, 'pairs': {}}
for d in decks:
    a1, e1 = pct(T[0][d]), pct(E[0][d]); a2, e2 = pct(T[1][d]), pct(E[1][d]); am, em = pct(T[2][d]), pct(E[2][d]); ac, ec = pct(T[3][d]), pct(E[3][d])
    L.append(f'| {d} | {a1:.1f} | {e1:.1f} | {a1 - e1:+.1f} | {a2:.1f} | {e2:.1f} | {am:.1f} | {em:.1f} | {am - em:+.1f} | {ac:.1f} | {ec:.1f} |')
    out['decks'][d] = dict(r1_table=a1, r1_empty=e1, r23_table=a2, r23_empty=e2, match_table=am, match_empty=em, comeback_table=ac, comeback_empty=ec)
tc = [sum(v[0] for v in T[3].values()), sum(v[1] for v in T[3].values())]; ec_ = [sum(v[0] for v in E[3].values()), sum(v[1] for v in E[3].values())]
L += ['', f'1라운드를 진 쪽이 매치를 뒤집은 비율(미러전 제외, 전체): 학습표 {pct(tc):.1f}% ({tc[1]:,}매치) · 빈 표 {pct(ec_):.1f}% ({ec_[1]:,}매치)', '',
      '| 순서쌍(행 덱 기준) | 1R 학습표 | 1R 빈 표 | 매치 학습표 | 매치 빈 표 |', '|---|---|---|---|---|']
for a, b in PAIRS:
    x = (a, b)
    L.append(f'| {a} vs {b} | {pct(T[4][x]):.1f} | {pct(E[4][x]):.1f} | {pct(T[5][x]):.1f} | {pct(E[5][x]):.1f} |')
    out['pairs'][f'{a} vs {b}'] = dict(r1_table=pct(T[4][x]), r1_empty=pct(E[4][x]), match_table=pct(T[5][x]), match_empty=pct(E[5][x]))
# 20%p 이상 바뀐 순서쌍: 1라운드도 20%p 이상 바뀌었는가
big = [(k, pct(T[5][k]) - pct(E[5][k]), pct(T[4][k]) - pct(E[4][k])) for k in T[5] if k[0] != k[1] and abs(pct(T[5][k]) - pct(E[5][k])) >= 20]
same_dir = sum(1 for _, m, r in big if abs(r) >= 10 and (m > 0) == (r > 0))
L += ['', f'매치 승률이 20%p 이상 바뀐 순서쌍 {len(big)}개 중 1라운드 승률도 같은 방향으로 10%p 이상 바뀐 순서쌍 {same_dir}개 '
      f'(평균 |매치 차| {sum(abs(m) for _, m, _ in big) / len(big):.1f}%p · 평균 |1R 차| {sum(abs(r) for _, _, r in big) / len(big):.1f}%p)']
out['big'] = dict(n=len(big), r1_same_dir_10=same_dir, mean_abs_match=sum(abs(m) for _, m, _ in big) / len(big), mean_abs_r1=sum(abs(r) for _, _, r in big) / len(big),
                  comeback_table=pct(tc), comeback_empty=pct(ec_))
open(sys.argv[3], 'w', encoding='utf-8').write('\n'.join(L) + '\n'); json.dump(out, open(sys.argv[4], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n'.join(L))

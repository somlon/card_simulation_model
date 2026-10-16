"""두 판단표(학습표 + 교체표)의 맞대결 — train_table의 평가 (2)와 같은 짝 설계(같은 덱 · 시드, 자리 교대)를 따로 실행한다.

  python3 h2h_tables.py --a learned/policy.json.gz learned/side.json --b empty --n 50 --out sim_results/<폴더>/h2h_final_vs_empty.json

  --a / --b: 「학습표 교체표」 경로 두 개, 또는 empty(빈 표 = 휴리스틱 점수만 쓰는 사전값 AI). 결과의 rate는 A의 승률(%)과 95% 신뢰구간.
  재학습을 빈 표에서 시작했을 때, 최종 표가 학습 전(휴리스틱 사전값)보다 나은지 확인하는 데 쓴다 (2026-10-13)."""
import argparse, json, os, sys
import train_table as TT, policy as P, season as SE


def empty():
    t = P.Table.__new__(P.Table); t.path = None; t.source = 'empty'; t.L0 = {}; t.L1 = {}; t.L2 = {}; t.games = 0
    return t


def load(spec):
    if spec == ['empty'] or spec == 'empty': return (empty(), empty()), 'empty'
    pol, side = spec
    return (P.Table.load(pol), TT.side_table(side)), f'{pol} + {side}'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', nargs='+', required=True); ap.add_argument('--b', nargs='+', required=True)
    ap.add_argument('--n', type=int, default=50, help='순서쌍당 시드 수 (시드마다 자리를 바꿔 2매치)')
    ap.add_argument('--workers', type=int, default=4); ap.add_argument('--seed', type=int, default=20261013)
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    sys.setrecursionlimit(10000)
    decks = SE.load_decks(); names = sorted(decks)
    TT._G['decks'] = decks
    (A, la), (B, lb) = load(a.a), load(a.b)
    TT._G['cur'], TT._G['prev'] = A, B
    r = TT.h2h(names, a.n, a.workers, a.seed)
    r.update(a=la, b=lb, n_per_pair=a.n, seed=a.seed, decks=names)
    print(f'A({la}) 대 B({lb}): A 승률 {r["rate"]}% ± {r["ci95"]} (매치 {r["games"]}, 중단 {r["stalled"]})')
    for d, (w, m) in sorted(r['by_deck'].items()): print(f'  {d}: {100 * w / m:.1f}% ({w}/{m})')
    if a.out:
        os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
        json.dump(r, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

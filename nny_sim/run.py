"""매치 실행기: python run.py 덱A.deck 덱B.deck [--games N] [--seed S] [--log out.txt]"""
import sys, random, argparse, json
from engine import Game
from cards import Impl
from ai import HeuristicAI
import policy as P
import deck as D

def play_match(dA, dB, first, rng, log, side_eps=0.0):
    """Bo3 매치 + 전략 덱 교체 (match.py). 판단은 학습형 정책."""
    import match as M
    return M.play_match(dA, dB, first, rng, log, lambda d: P.LearnedAI(d['스킬']), side=True, side_eps=side_eps)

def fmt(log):
    out = []
    for e in log:
        k = e['k']
        if k in ('turn', 'round', 'end'): out.append(''); out.append(e['m'])
        elif k == 'decision': out.append(f'      · {e["m"]}')
        else: out.append(f'   [{e["ph"]}] {e["m"]}')
    return '\n'.join(out)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('a'); ap.add_argument('b')
    ap.add_argument('--games', type=int, default=1); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--log'); a = ap.parse_args()
    dA, eA, _ = D.load(a.a); dB, eB, _ = D.load(a.b)
    assert not eA and not eB, (eA, eB)
    rng = random.Random(a.seed); full = []
    res = []
    from report import Report
    rep = Report()
    for i in range(a.games):
        log = []
        first = i % 2    # 선공 5:5
        mw, rounds = play_match(dA, dB, first, rng, log)
        res.append((first, mw, rounds))
        for r in rounds: rep.add(log[r['log'][0]:r['log'][1]], [dA['이름'], dB['이름']], r['winner'], r['reason'])
        if a.log:
            res_s = ' · '.join(f'{r["reason"]}' for r in rounds)
            full.append({'t': 0, 'ph': '', 'tp': 0, 'k': 'match', 'm': f'매치 {i+1} — 1라운드 선공 {[dA,dB][first]["이름"]} · 승자 {[dA,dB][mw]["이름"] if mw is not None else "무승부"}'})
            full.extend(log)
    if a.log:
        import kifu
        open(a.log, 'w', encoding='utf-8').write(kifu.render(full, f'기보 — {dA["이름"]} vs {dB["이름"]}', names=[dA['이름'], dB['이름']]))
    P.POLICY.save()
    import match as M; M.SIDE.save()
    txt = rep.text()
    open('시뮬레이션_보고서.md', 'w', encoding='utf-8').write('# 시뮬레이션 종료 보고서\n\n' + txt)
    print(txt)
    print(json.dumps([(f, w, [(r['first'], r['winner'], r['turns'], r['reason']) for r in rs]) for f, w, rs in res], ensure_ascii=False))

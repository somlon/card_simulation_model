"""같은 시드 비교: 휴리스틱(규칙만 — 1.2.2) vs 학습하는 휴리스틱(전략 = 학습표, session.LearningHeuristicAI), 상대 학습표 AI. python3 heuristic_compare.py <sim> <split> <app> <매치 수> <작업자>"""
import sys, os, random, json, itertools
from multiprocessing import Pool
SIM, SPLIT, APP = sys.argv[1:4]; N = int(sys.argv[4]); W = int(sys.argv[5])


def run(job):
    sys.path[:0] = [SIM, os.path.join(os.path.dirname(APP), 'viewer'), APP]; os.chdir(SIM)
    import match as M, policy as P, season as SE, tables as T, session as SS
    from ai import HeuristicAI
    kind, a, b, seed, hseat = job
    decks = SE.load_decks(); da, db = decks[a], decks[b]
    table = T.matchup_table(SPLIT, {da['스킬'], db['스킬']})

    class Plain(HeuristicAI):
        def end_game(self, g, p, w): self.decisions = []

    def mk(d):
        if d['_seat'] == hseat: return Plain(d['스킬']) if kind == 'old' else SS.LearningHeuristicAI(d['스킬'], learn=False, table=table)
        return P.LearnedAI(d['스킬'], learn=False, table=table)
    try:
        mw, rounds = M.play_match(dict(da, 이름='A'), dict(db, 이름='B'), seed % 2, random.Random(seed), [], mk, side=True, side_eps=0.0, learn_side=False)
    except Exception as ex:
        return kind, a, b, seed, hseat, 'err', repr(ex)[:200]
    return kind, a, b, seed, hseat, mw, None


if __name__ == '__main__':
    sys.path[:0] = [SIM]; os.chdir(SIM)
    import season as SE
    names = sorted(SE.load_decks()); rng = random.Random(1)
    base = []
    for i in range(N):
        a, b = rng.sample(names, 2); base.append((a, b, 1000 + i, i % 2))
    jobs = [(k,) + j for j in base for k in ('old', 'new')]
    with Pool(W) as pool: res = pool.map(run, jobs, chunksize=1)
    out = {'old': [0, 0, 0], 'new': [0, 0, 0]}; same = 0; pairs = {}
    for kind, a, b, seed, hs, mw, err in res:
        if mw == 'err': out[kind][2] += 1; print('err', kind, a, b, seed, err); continue
        out[kind][0] += int(mw == hs); out[kind][1] += 1; pairs.setdefault(seed, {})[kind] = mw
    same = sum(1 for v in pairs.values() if v.get('old') == v.get('new'))
    print(json.dumps({'heuristic_match_wins_vs_table': {k: f'{w}/{n} ({w / max(n, 1) * 100:.1f}%) err {e}' for k, (w, n, e) in out.items()}, 'same_winner': same, 'n': len(pairs)}, ensure_ascii=False))

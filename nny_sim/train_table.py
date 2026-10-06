"""학습표 재학습: 모든 덱의 순서쌍(미러전 포함, 7덱이면 49개)으로 자기대전해 학습표(policy · side)를 수렴할 때까지 갱신한다.

  python train_table.py --out learned/train_49                 # 처음부터 (기존 learned/policy.json · side.json에서 이어받음)
  python train_table.py --out learned/train_49                 # 같은 --out이면 마지막 체크포인트부터 이어서
  python train_table.py --out learned/train_49 --export learned  # 결과 표를 learned/policy.json.gz · side.json으로 내보냄

알고리즘 — 몬테카를로 대조(contextual bandit) 표 학습의 병렬 · 비정상(non-stationary) 버전
  · 반복 1회 = 순서쌍마다 --per-pair 매치(3판 2선승, 라운드 사이 전략 덱 교체 포함). 작업자들이 반복 시작 시점 표의
    사본(fork)으로 두며 자기 사본에 바로 반영하고, 끝나면 증분(Δ승수 · Δ판수)을 돌려준다 → 주 프로세스가 합친다.
  · 망각: 반복마다 모든 칸의 (승수, 판수)에 γ(--gamma)를 곱한다. 정책이 바뀌면 예전 판의 승패는 낡은 정보가 되므로
    이동 평균으로 추정한다. 판수가 --prune 아래로 줄어든 L2 칸은 지운다(표 크기 억제).
  · 시작 표: 기존 표를 이어받되 판수를 상한(--cap1 · --cap2)으로 줄인다(평균은 유지). 규칙 · 코드 수정 이후의 판이
    빨리 반영되게 하려는 것. 상대를 묶은 L0 단계는 L1에서 다시 만든다.
  · 탐색: ε을 --eps0 → --eps1로 --anneal 반복에 걸쳐 줄인다. 판 시작 결정(시작 패 배분 · 멀리건 재배분 · 선후공)은 톰슨 표본.
    전략 덱 교체 탐색은 --side-eps0 → --side-eps1.
  · 평가(--eval-every 반복마다)
    (1) 리그: 탐색 · 학습 없이 match_sim과 같은 고정 일정(순서쌍당 --eval-matches, 시드 1) → 덱별 · 순서쌍별 매치 승률
    (2) 맞대결: 직전 평가 시점의 표와 지금 표를 같은 덱 · 자리 교대 짝 설계로 붙인다(순서쌍당 --h2h-matches 시드 × 2)
  · 수렴(유의미한 변화 없음) — 다음 두 조건이 --patience회 연속이면 멈춘다(최소 --min-iters 반복 뒤)
    (a) 직전 평가 대비 덱별 매치 승률 변화가 유의하지 않음: Σ(Δ/SE)²의 χ²(덱 수) 검정 p > 0.05
    (b) 직전 평가 시점 표 대비 맞대결 승률의 95% 신뢰구간 하한이 50% 미만(유의한 향상 없음)
  · 레시피 학습(시즌): 평가가 끝날 때마다(= 학습 단계 하나 = 시즌 하나) 표를 고정한 채 덱마다 레시피 학습기
    (deck_opt.one_round: 한 장 추가 · 제거 · 교체 후보, 로그 기여도 우선, 짧게 → 길게 → 최종 짝 비교, z > 1.96이면 채택)를
    한 라운드씩 돌리고, 바뀐 레시피로 다음 단계 학습을 이어 간다(사용자 지시 2026-10-06). --no-recipe면 끈다.
    시즌마다 각 덱의 레시피와 변경 내역을 state.json의 seasons에 남긴다 — 덱별 승률 보고서의 시즌별 레시피 표 자료.
    수렴 조건 (a) · (b)에 더해 (c) 그 시즌에 채택된 레시피 변경이 없어야 한다.
  · --time-limit 초가 지나면 반복 경계에서 체크포인트를 저장하고 멈춘다(같은 명령으로 이어서 실행).
"""
import argparse, copy, gc, itertools, json, math, multiprocessing as mp, os, random, sys, time, traceback

for _k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_k, '1')

_G = {}   # 작업자와 공유하는 상태(포크 시점에 복사됨)


# ─────────────── 표 연산 ───────────────
def cap_counts(D, m):
    """판수 상한: 평균(승수/판수)은 그대로 두고 판수만 m으로 줄인다"""
    for v in D.values():
        if v[1] > m:
            f = m / v[1]; v[0] *= f; v[1] = m


def decay(D, g, prune=None):
    dead = []
    for k, v in D.items():
        v[0] *= g; v[1] *= g
        if prune is not None and v[1] < prune: dead.append(k)
    for k in dead: del D[k]
    return len(dead)


def add_into(D, delta):
    for k, (w, n) in delta.items():
        a = D.setdefault(k, [0, 0]); a[0] += w; a[1] += n


def merge_policy(T, d1, d2):
    import policy as P
    add_into(T.L1, d1); add_into(T.L2, d2)
    d0 = {}
    for k, (w, n) in d1.items():
        k0 = P.k0_of(k)
        if k0 is not None:
            a = d0.setdefault(k0, [0, 0]); a[0] += w; a[1] += n
    add_into(T.L0, d0)


def clone(T):
    t = copy.copy(T)
    t.L0 = {k: list(v) for k, v in T.L0.items()}; t.L1 = {k: list(v) for k, v in T.L1.items()}
    t.L2 = {k: list(v) for k, v in T.L2.items()}
    return t


# ─────────────── 작업자 ───────────────
def _deck_pair(a, b):
    decks = _G['decks']
    return dict(decks[a], 이름=f"{decks[a]['이름']} [자리0]"), dict(decks[b], 이름=f"{decks[b]['이름']} [자리1]")


def _train_worker(batch):
    """학습 매치 묶음 → (L1 증분, L2 증분, side 증분, 통계)"""
    import match as M, policy as P
    from engine import StalledGame
    T = P.POLICY
    d1, d2 = {}, {}
    if not getattr(T, '_recording', False):
        orig = T.update

        def upd(k1, k2, won, _o=orig):
            _o(k1, k2, won)
            r1, r2 = _G['rec']
            a = r1.setdefault(k1, [0, 0]); a[0] += won; a[1] += 1
            b = r2.setdefault(k2, [0, 0]); b[0] += won; b[1] += 1
        T.update = upd; T._recording = True
    _G['rec'] = (d1, d2)
    side0 = {k: (v[0], v[1]) for k, v in M.SIDE.L1.items()}
    eps, side_eps = _G['eps'], _G['side_eps']
    st = {'matches': 0, 'rounds': 0, 'stalled': 0, 'errors': 0, 'err': None}
    for a, b, first, seed in batch:
        dA, dB = _deck_pair(a, b)
        try:
            mw, rounds = M.play_match(dA, dB, first, random.Random(seed), [], lambda d: P.LearnedAI(d['스킬'], learn=True, eps=eps),
                                      side=True, side_eps=side_eps, learn_side=True)
            st['matches'] += 1; st['rounds'] += len(rounds)
        except StalledGame:
            st['stalled'] += 1
        except Exception:
            st['errors'] += 1; st['err'] = st['err'] or traceback.format_exc()[-1500:]
    ds = {}
    for k, v in M.SIDE.L1.items():
        w0, n0 = side0.get(k, (0, 0))
        if v[1] != n0: ds[k] = [v[0] - w0, v[1] - n0]
    return d1, d2, ds, st


def _league_worker(batch):
    import match_sim as MS
    out = []
    for a, b, first, seed, mid in batch:
        out += MS.play_one(a, b, first, seed, mid)
    return out


def _h2h_worker(batch):
    """맞대결: 자리 new_seat는 지금 표, 다른 자리는 직전 평가 시점 표 → (내 덱, 상대 덱, 지금 표 승리 여부 또는 None)"""
    import match as M, policy as P
    from engine import StalledGame
    cur, prev = _G['cur'], _G['prev']
    out = []
    for a, b, first, seed, ns in batch:
        tabs = {ns: cur, 1 - ns: prev}

        def make_ai(deck):
            return P.LearnedAI(deck['스킬'], learn=False, table=tabs[deck['_seat']][0])

        def side_fn(i, decks, wins, rounds, rng, side_eps, log):
            old = M.SIDE; M.SIDE = tabs[i][1]
            try:
                return M.side_swap(decks[i], decks[1 - i]['스킬'], rng, side_eps, log, decks[i]['이름'])
            finally:
                M.SIDE = old
        dA, dB = _deck_pair(a, b)
        mine, theirs = (a, b) if ns == 0 else (b, a)
        try:
            mw, _ = M.play_match(dA, dB, first, random.Random(seed), [], make_ai, side=True, side_eps=0.0, learn_side=False, side_fn=side_fn)
            out.append((mine, theirs, int(mw == ns)))
        except StalledGame:
            out.append((mine, theirs, None))
    return out


def _recipe_worker(job):
    import deck_opt as DO
    return DO.serial_ev([job])[0]


def parallel_ev(jobs, workers):
    """deck_opt 평가기의 병렬판: 후보 하나(상대 전부 × 선후공 × n쌍)를 작업 하나로 나눠 돌린다. 순서 유지"""
    gc.collect(); gc.freeze()
    try:
        with mp.get_context('fork').Pool(workers) as pool:
            return pool.map(_recipe_worker, jobs, chunksize=1)
    finally:
        gc.unfreeze()


def deck_rows(d):
    """레시피 → 표용 행 {구역: [[매수, 카드], ...]}"""
    return {sec: [[k, n] for k, n in d[sec]] for sec in ('메인', '상급', '전략')}


def _chunks(lst, n):
    k = max(1, math.ceil(len(lst) / n))
    return [lst[i:i + k] for i in range(0, len(lst), k)]


def _pool_map(fn, items, workers, chunks_per_worker=6):
    gc.collect(); gc.freeze()          # 포크한 작업자가 큰 표를 쓰기 시 복사하지 않게
    try:
        with mp.get_context('fork').Pool(workers) as pool:
            return list(pool.imap_unordered(fn, _chunks(items, workers * chunks_per_worker)))
    finally:
        gc.unfreeze()


# ─────────────── 평가 ───────────────
def league(names, n, workers):
    import match_sim as MS
    recs = []
    for r in _pool_map(_league_worker, MS.schedule(names, n, 1), workers): recs += r
    s = MS.summarize(recs)
    return {'decks': {d: s['decks'][d]['match'] for d in names}, 'vs': {k: v for k, v in s['vs'].items()},
            'matches': s['matches'], 'stalled': s['stalled_matches'], 'errors': s['error_matches']}


def h2h(names, n, workers, seed):
    rng = random.Random(seed); sched = []
    for a, b in itertools.product(names, repeat=2):
        for k in range(n):
            s = rng.randrange(2 ** 31)
            for ns in (0, 1): sched.append((a, b, k % 2, s, ns))
    w = m = stalled = 0; by = {}
    for r in _pool_map(_h2h_worker, sched, workers):
        for mine, theirs, won in r:
            if won is None: stalled += 1; continue
            w += won; m += 1
            x = by.setdefault(mine, [0, 0]); x[0] += won; x[1] += 1
    p = w / m; ci = 1.96 * math.sqrt(p * (1 - p) / m)
    return {'win': w, 'games': m, 'rate': round(100 * p, 2), 'ci95': round(100 * ci, 2), 'stalled': stalled, 'by_deck': by}


def chi2_change(cur, prev):
    """덱별 매치 승률 변화의 χ² 검정 → (통계량, 자유도, p값, 최대 |Δ|pp)"""
    from scipy.stats import chi2
    x = 0.0; df = 0; mx = 0.0
    for d, c in cur.items():
        p0 = prev.get(d)
        if not p0: continue
        a, b = c['win'] / c['games'], p0['win'] / p0['games']
        pool = (c['win'] + p0['win']) / (c['games'] + p0['games'])
        se2 = pool * (1 - pool) * (1 / c['games'] + 1 / p0['games'])
        if se2 > 0: x += (a - b) ** 2 / se2; df += 1
        mx = max(mx, abs(a - b) * 100)
    return x, df, (float(chi2.sf(x, df)) if df else None), mx


def coverage(T, names, skills):
    """순서쌍별 L1 방문 수 (학습표 공백 확인용)"""
    cov = {}
    for k, (w, n) in T.L1.items():
        pair = k.split('|', 1)[0]
        cov[pair] = cov.get(pair, 0) + n
    return {f'{skills[a]} vs {skills[b]}': round(cov.get(f'{skills[a]} vs {skills[b]}', 0)) for a, b in itertools.product(names, repeat=2)}


# ─────────────── 저장 ───────────────
def save_ckpt(out, T, S, state, prev=None):
    import policy as P
    T.save(os.path.join(out, 'policy.json.gz'))
    P.Table.save(S, os.path.join(out, 'side.json.gz'))
    if prev is not None:
        prev[0].save(os.path.join(out, 'prev_policy.json.gz')); P.Table.save(prev[1], os.path.join(out, 'prev_side.json.gz'))
    tmp = os.path.join(out, 'state.json.tmp')
    json.dump(state, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(out, 'state.json'))


def side_table(path):
    import policy as P
    t = P.Table.load(path)
    return t


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--iters', type=int, default=200)
    ap.add_argument('--per-pair', type=int, default=60)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--gamma', type=float, default=0.97)
    ap.add_argument('--prune', type=float, default=0.2)
    ap.add_argument('--cap0', type=float, default=5000); ap.add_argument('--cap1', type=float, default=2000); ap.add_argument('--cap2', type=float, default=200)
    ap.add_argument('--eps0', type=float, default=0.15); ap.add_argument('--eps1', type=float, default=0.05)
    ap.add_argument('--side-eps0', type=float, default=0.10); ap.add_argument('--side-eps1', type=float, default=0.03)
    ap.add_argument('--anneal', type=int, default=30)
    ap.add_argument('--eval-every', type=int, default=5)
    ap.add_argument('--eval-matches', type=int, default=100)
    ap.add_argument('--h2h-matches', type=int, default=50)
    ap.add_argument('--patience', type=int, default=2)
    ap.add_argument('--min-iters', type=int, default=15)
    ap.add_argument('--time-limit', type=float, default=1e18)
    ap.add_argument('--seed', type=int, default=20261006)
    ap.add_argument('--no-recipe', action='store_true', help='시즌마다 레시피 학습을 하지 않는다')
    ap.add_argument('--recipe-n', default='2,8,40', help='레시피 학습 단계별 상대당 매치 쌍 수(짧게,길게,최종)')
    ap.add_argument('--export')
    a = ap.parse_args(argv)
    sys.setrecursionlimit(10000)
    import season as SE, policy as P, match as M, match_sim as MS
    os.makedirs(a.out, exist_ok=True)
    names = sorted(SE.load_decks()); decks = SE.load_decks(); skills = {n: decks[n]['스킬'] for n in names}
    _G['decks'] = decks
    st_path = os.path.join(a.out, 'state.json')

    if a.export:
        T = P.Table.load(os.path.join(a.out, 'policy.json.gz')); S = P.Table.load(os.path.join(a.out, 'side.json.gz'))
        T.save(os.path.join(a.export, 'policy.json.gz')); P.Table.save(S, os.path.join(a.export, 'side.json'))
        state = json.load(open(st_path, encoding='utf-8'))
        if state.get('decks'):   # 마지막 시즌 레시피 → learned/decks/<스킬>.json, 시즌별 레시피 기록 → recipe_seasons.json
            os.makedirs(os.path.join(a.export, 'decks'), exist_ok=True)
            for name, d in state['decks'].items():
                json.dump(d, open(os.path.join(a.export, 'decks', f'{d["스킬"]}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            json.dump(state.get('seasons', []), open(os.path.join(a.export, 'recipe_seasons.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('내보냄:', a.export); return

    t_start = time.time()
    if os.path.exists(st_path):
        state = json.load(open(st_path, encoding='utf-8'))
        T = P.Table.load(os.path.join(a.out, 'policy.json.gz')); S = P.Table.load(os.path.join(a.out, 'side.json.gz'))
        prev = None
        if os.path.exists(os.path.join(a.out, 'prev_policy.json.gz')):
            prev = (P.Table.load(os.path.join(a.out, 'prev_policy.json.gz')), P.Table.load(os.path.join(a.out, 'prev_side.json.gz')))
        if state.get('decks'):
            decks = {k: {f: [tuple(x) for x in v] if isinstance(v, list) else v for f, v in d.items()} for k, d in state['decks'].items()}
            _G['decks'] = decks
        print(f'이어서: 반복 {state["iter"]}부터', flush=True)
    else:
        T = P.POLICY; S = M.SIDE
        before = {'L1': len(T.L1), 'L2': len(T.L2), 'coverage': coverage(T, names, skills)}
        cap_counts(T.L1, a.cap1); cap_counts(T.L2, a.cap2); T.rebuild_L0(); cap_counts(T.L0, a.cap0)
        cap_counts(S.L1, a.cap1)
        state = {'iter': 0, 'args': vars(a), 'history': [], 'evals': [], 'calm': 0, 'converged': False, 'before': before}
        prev = None
    state.setdefault('seasons', []); state.setdefault('recipe_hist', {}); state.setdefault('recipe_done', -1)
    if not state['seasons']:   # 시즌 0 = 학습 시작(또는 시즌 방식으로 전환한) 시점 레시피
        state['seasons'].append({'season': 0, 'iter': state['iter'], 'changes': {}, 'accepted': 0, 'recipes': {n: deck_rows(decks[n]) for n in names}})
    P.POLICY = T; M.SIDE = S
    # 리그 평가용 match_sim 작업자 상태 (포크로 전달)
    a.recipe_n = tuple(int(x) for x in str(a.recipe_n).split(','))
    MS._W.update({'decks': decks, 'spec': {'ai': 'table', 'policy': None, 'side': None},
                  'make_ai': lambda d: P.LearnedAI(d['스킬'], learn=False), 'side_fn': None})

    def evaluate(it):
        nonlocal prev
        t0 = time.time()
        lg = league(names, a.eval_matches, a.workers)
        ev = {'iter': it, 'league': lg, 'L0': len(T.L0), 'L1': len(T.L1), 'L2': len(T.L2), 'coverage': coverage(T, names, skills)}
        if state['evals']:
            x, df, pv, mx = chi2_change(lg['decks'], state['evals'][-1]['league']['decks'])
            ev['chi2'] = {'stat': round(x, 2), 'df': df, 'p': pv, 'max_delta_pp': round(mx, 2)}
        if prev is not None:
            _G['cur'] = (T, S); _G['prev'] = prev
            ev['h2h'] = h2h(names, a.h2h_matches, a.workers, a.seed + it)
        prev = (clone(T), clone(S))
        calm_a = 'chi2' in ev and ev['chi2']['p'] is not None and ev['chi2']['p'] > 0.05
        calm_b = 'h2h' in ev and (ev['h2h']['rate'] - ev['h2h']['ci95']) < 50.0
        ev['calm'] = bool(calm_a and calm_b)
        state['calm'] = state['calm'] + 1 if ev['calm'] else 0
        ev['sec'] = round(time.time() - t0, 1)
        state['evals'].append(ev)
        rates = ' · '.join(f'{d[:6]} {lg["decks"][d]["rate"]:.1f}' for d in names)
        msg = f'[평가 {it}] {rates}'
        if 'chi2' in ev: msg += f' | Δ χ²={ev["chi2"]["stat"]} p={ev["chi2"]["p"]:.3f} 최대Δ {ev["chi2"]["max_delta_pp"]}pp'
        if 'h2h' in ev: msg += f' | 직전 표 대비 {ev["h2h"]["rate"]}% ± {ev["h2h"]["ci95"]}'
        msg += f' | 안정 {state["calm"]}/{a.patience} ({ev["sec"]}s)'
        print(msg, flush=True)
        if it >= a.min_iters and state['calm'] >= a.patience:
            state['converged'] = True

    def recipe_stage(it):
        """시즌 하나: 표를 고정하고 덱마다 레시피 학습기 한 라운드. 채택된 레시피는 다음 단계부터 쓴다"""
        import deck_opt as DO
        t0 = time.time(); changes = {}; accepted = 0
        for n in names:
            d = decks[n]; st = DO.state_from_deck(d); st['history'] = state['recipe_hist'].get(n, [])
            con, val = DO.log_guides(d['스킬'], st['counts'], st['strat'], {k: decks[k] for k in names})
            rec = DO.one_round(st, [decks[k] for k in names if k != n], ev=lambda jobs: parallel_ev(jobs, a.workers),
                               contrib=con, value_of=val, n=a.recipe_n)
            state['recipe_hist'][n] = st['history']
            if rec.get('accepted'):
                accepted += 1
                base = d['이름'].split(' [')[0]
                decks[n] = DO.to_deck(f'{base} [시즌 {len(state["seasons"])} 레시피]', d['스킬'], st['counts'], st['strat'])
            changes[n] = {k: rec.get(k) for k in ('best', 'base', 'best_rate', 'diff', 'z', 'accepted', 'candidates', 'sizes_before', 'sizes_after', 'top3')}
            print(f'  [레시피 {n}] {"채택" if rec.get("accepted") else "유지"}: {rec.get("best")} '
                  f'({rec.get("base")}% → {rec.get("best_rate")}%, z={rec.get("z")}) 매수 {rec.get("sizes_after")}', flush=True)
        season = {'season': len(state['seasons']), 'iter': it, 'changes': changes, 'accepted': accepted,
                  'recipes': {n: deck_rows(decks[n]) for n in names}, 'sec': round(time.time() - t0, 1)}
        state['seasons'].append(season); state['recipe_done'] = it
        state['decks'] = {k: decks[k] for k in names}
        if accepted: state['calm'] = 0; state['converged'] = False
        print(f'[시즌 {season["season"]}] 레시피 변경 {accepted}개 덱 ({season["sec"]}s) · 안정 {state["calm"]}/{a.patience}', flush=True)

    if not state['evals']:
        evaluate(0); save_ckpt(a.out, T, S, state, prev)
    last_eval = state['evals'][-1]['iter']
    if not a.no_recipe and last_eval > 0 and state['recipe_done'] < last_eval and not state['converged']:
        recipe_stage(last_eval); save_ckpt(a.out, T, S, state, prev)   # 평가까지 하고 멈춘 시즌의 레시피 학습을 마저 한다

    while state['iter'] < a.iters and not state['converged']:
        it = state['iter'] + 1; t0 = time.time()
        frac = min(1.0, (it - 1) / max(1, a.anneal))
        _G['eps'] = a.eps0 + (a.eps1 - a.eps0) * frac
        _G['side_eps'] = a.side_eps0 + (a.side_eps1 - a.side_eps0) * frac
        rng = random.Random(f'{a.seed}-{it}'); sched = []
        for x, y in itertools.product(names, repeat=2):
            for k in range(a.per_pair): sched.append((x, y, k % 2, rng.randrange(2 ** 31)))
        rng.shuffle(sched)
        res = _pool_map(_train_worker, sched, a.workers)
        # 망각 → 합치기
        pr = decay(T.L2, a.gamma, a.prune); decay(T.L1, a.gamma); decay(T.L0, a.gamma); decay(S.L1, a.gamma)
        tot = {'matches': 0, 'rounds': 0, 'stalled': 0, 'errors': 0}; err = None
        for d1, d2, ds, st in res:
            merge_policy(T, d1, d2); add_into(S.L1, ds)
            for k in tot: tot[k] += st[k]
            err = err or st['err']
        T.games += tot['rounds']
        h = dict(iter=it, eps=round(_G['eps'], 4), side_eps=round(_G['side_eps'], 4), pruned=pr, sec=round(time.time() - t0, 1), **tot)
        if err: h['err'] = err
        state['history'].append(h); state['iter'] = it
        print(f'[반복 {it}] 매치 {tot["matches"]} 라운드 {tot["rounds"]} 중단 {tot["stalled"]} 오류 {tot["errors"]} · ε {h["eps"]:.3f} · '
              f'L2 {len(T.L2)} (−{pr}) · {h["sec"]}s', flush=True)
        if err: print(err, flush=True)
        if it % a.eval_every == 0:
            evaluate(it); save_ckpt(a.out, T, S, state, prev)
            if not a.no_recipe and not state['converged']:
                recipe_stage(it); save_ckpt(a.out, T, S, state, prev)
        if time.time() - t_start > a.time_limit:
            save_ckpt(a.out, T, S, state, prev); print('시간 한도 — 저장하고 멈춤', flush=True); return
    save_ckpt(a.out, T, S, state, prev)
    print('수렴' if state['converged'] else '반복 한도 도달', flush=True)


if __name__ == '__main__':
    main()

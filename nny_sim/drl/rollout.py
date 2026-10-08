"""게임 생성 · 평가 작업자 (multiprocessing spawn 풀에서 실행).

작업자는 numpy만 쓴다(PyTorch 불필요). 스레드 과다 사용을 막기 위해 BLAS 스레드를 1로 고정한다
(실측: 고정하지 않으면 4개 병렬의 총처리량이 1개일 때보다 낮아짐).

역할(role)
  cur        지금 학습 중인 정책(표본 기록, 확률 표본 추출)
  past       과거 체크포인트(기록 없음, 탐욕)
  table      학습표 LearnedAI(교사 표, 기록 없음)
  heuristic  휴리스틱 AI
  teacher    모방 학습 자료 수집: 학습표로 두면서 DRL 입력 · 교사 분포를 기록
"""
import os
for _k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_k, '1')
import json, math, random, traceback, itertools
import numpy as np

_W = {}


def load_table(path):
    """학습표 JSON(policy.json 형식) → policy.Table.
    .json.gz 압축본도 읽는다 — 큰 학습표(예: C 표 101MB)는 GitHub 파일 한도(100MB) 때문에 압축해 보관한다"""
    import policy as P
    return P.Table.load(path)


def init_worker(cfg):
    import season as SE, policy as P, match as M
    _W['cfg'] = cfg
    _W['decks'] = SE.load_decks()
    _W['tables'] = {}
    if cfg.get('teacher'):
        P.POLICY = _table(cfg['teacher'])          # table 역할 · 교사 = 같은 표
    if cfg.get('teacher_side'):
        M.SIDE = _table(cfg['teacher_side'])       # 학습표 쪽 전략 덱 교체에 쓰는 표


def _table(path):
    t = _W.setdefault('tables', {})
    if path not in t:
        t[path] = load_table(path)
    return t[path]


def _actor(arrays, remap=None):
    from .model import NumpyActor
    return NumpyActor(arrays, remap)


def _make_ai(role, skill, seat, actor, rec, nrng, use_teacher_kl):
    import policy as P
    from ai import HeuristicAI
    from .agent import DRLAI
    cfg = _W.get('cfg', {}); ttemp = cfg.get('teacher_temp') or 0.03
    if role == 'cur':
        return DRLAI(skill, actor=actor, mode='sample', rng=nrng, recorder=rec, seat=seat,
                     teacher=P.POLICY if use_teacher_kl else None, teacher_temp=ttemp, log_decisions=False)
    if role == 'past':
        return DRLAI(skill, actor=actor, mode='greedy', log_decisions=False)
    if role == 'teacher':
        return DRLAI(skill, mode='teacher', teacher=P.POLICY, teacher_eps=cfg.get('teacher_eps') or 0.0, teacher_temp=ttemp,
                     recorder=rec, seat=seat, log_decisions=False)
    if role == 'table':
        return P.LearnedAI(skill, learn=False)
    if role == 'heuristic':
        return HeuristicAI(skill)
    raise ValueError(role)


def play_one_match(dA, dB, first, seed, roles, actors, rec, nrng, use_teacher_kl=False):
    """역할이 지정된 Bo3 매치 1회. 반환: (매치 승자, 라운드 목록)"""
    import match as M
    from . import side as SD
    mk = lambda d: _make_ai(roles[d['_seat']], d['스킬'], d['_seat'], actors[d['_seat']], rec, nrng, use_teacher_kl)

    def side_fn(i, decks, wins, rounds, rng, side_eps, log):
        ctx = dict(round=len(rounds), wins_me=wins[i], wins_op=wins[1 - i], lost_last=rounds[-1]['winner'] != i)
        role = roles[i]
        if role in ('cur', 'past'):
            return SD.drl_side_swap(decks[i], decks[1 - i], ctx, actors[i], mode='sample' if role == 'cur' else 'greedy',
                                    rng=nrng, recorder=rec if role == 'cur' else None, seat=i, log=log, pname=decks[i]['이름'])
        if role == 'teacher':
            return SD.teacher_side_swap(decks[i], decks[1 - i], ctx, rng, recorder=rec, seat=i, log=log, pname=decks[i]['이름'])
        return M.side_swap(decks[i], decks[1 - i]['스킬'], rng, side_eps, log, decks[i]['이름'])

    return M.play_match(dA, dB, first, random.Random(seed), [], mk, side=True, side_eps=0.0, learn_side=False, side_fn=side_fn)


def run_job(job):
    """학습 자료 생성. job: worker, seed, n_matches, cur(가중치), past(가중치 또는 None), mix({역할: 비중}), mode('ppo'|'bc')"""
    from engine import StalledGame
    from .agent import Recorder
    rng = random.Random(job['seed']); nrng = np.random.default_rng(job['seed'])
    decks = _W['decks']; pairs = list(itertools.combinations(sorted(decks), 2))
    cur = _actor(job['cur']) if job.get('cur') is not None else None
    past = _actor(job['past']) if job.get('past') is not None else None
    mix = {k: v for k, v in job.get('mix', {'self': 1.0}).items() if v > 0 and (k != 'past' or past is not None)}
    kinds = sorted(mix); weights = [mix[k] for k in kinds]
    from . import side as SD
    rec = Recorder(job['worker']); st = {'matches': 0, 'stalled': 0, 'errors': 0, 'err_msgs': [], 'vs': {}}
    unmapped0 = SD.STATS['teacher_unmapped']
    for _ in range(job['n_matches']):
        a, b = rng.choice(pairs); first = rng.randrange(2); seed = rng.randrange(2 ** 31)
        if job['mode'] == 'bc':
            roles = ['teacher', 'teacher']; opp = 'teacher'
        else:
            opp = rng.choices(kinds, weights)[0]
            if opp == 'self':
                roles = ['cur', 'cur']
            else:
                me = rng.randrange(2); roles = [None, None]; roles[me] = 'cur'; roles[1 - me] = opp
        actors = [cur if r == 'cur' else past if r == 'past' else None for r in roles]
        rec.begin_match()
        try:
            mw, _ = play_one_match(decks[a], decks[b], first, seed, roles, actors, rec, nrng, job.get('teacher_kl', False))
        except StalledGame:
            rec.abort_match(); st['stalled'] += 1; continue
        except Exception:
            rec.abort_match(); st['errors'] += 1
            if len(st['err_msgs']) < 3:
                st['err_msgs'].append(traceback.format_exc()[-1500:])
            continue
        rec.end_match(mw); st['matches'] += 1
        if opp not in ('self', 'teacher') and mw is not None:
            e = st['vs'].setdefault(opp, [0, 0]); e[0] += int(roles[mw] == 'cur'); e[1] += 1
    st['teacher_unmapped'] = SD.STATS['teacher_unmapped'] - unmapped0
    return {'worker': job['worker'], 'data': rec.packed(), 'stats': st}


# ── 평가 ── 고정 시드 단판(학습 끔). x · y: {'kind': 'drl', 'arrays': ...} | {'kind': 'table', 'path': ...} | {'kind': 'heuristic'}
def _eval_ai(spec, skill):
    import policy as P
    from ai import HeuristicAI
    from .agent import DRLAI
    if spec['kind'] == 'drl':
        return DRLAI(skill, actor=spec['_actor'], mode='greedy', log_decisions=False)
    if spec['kind'] == 'table':
        ai = P.LearnedAI(skill, learn=False)
        tab = _table(spec['path'])
        orig = ai.choose

        def choose(g, p, decision, opts, scale=40.0, log=True, _t=tab):
            old = P.POLICY; P.POLICY = _t
            try:
                return orig(g, p, decision, opts, scale, log)
            finally:
                P.POLICY = old
        ai.choose = choose
        return ai
    if spec['kind'] == 'heuristic':
        return HeuristicAI(skill)
    raise ValueError(spec['kind'])


def games_list(names, k, base):
    out = []; s = base
    for i, j in itertools.permutations(range(len(names)), 2):
        for first in (0, 1):
            for _ in range(k):
                out.append((names[i], names[j], first, s)); s += 1
    return out


def eval_job(job):
    """단판 평가. job: x, y(spec), games[(덱 x, 덱 y, 선공, 시드)]. x는 항상 자리 0"""
    from engine import Game, StalledGame
    from cards import Impl
    decks = _W['decks']; out = {'w': 0, 'n': 0, 'stalled': 0, 'turns': 0, 'errors': 0, 'err_msgs': [], 'by_deck': {}}
    x = dict(job['x']); y = dict(job['y'])
    for spec in (x, y):
        if spec['kind'] == 'drl':
            spec['_actor'] = _actor(spec['arrays'], spec.get('remap'))   # remap: 카드 풀이 바뀐 옛 모델의 번호 매핑
    for a, b, first, seed in job['games']:
        g = Game([decks[a], decks[b]], [_eval_ai(x, decks[a]['스킬']), _eval_ai(y, decks[b]['스킬'])], first, random.Random(seed), [], Impl)
        try:
            win, _ = g.run()
        except StalledGame:
            out['stalled'] += 1; continue
        except Exception:
            out['errors'] += 1
            if len(out['err_msgs']) < 3:
                out['err_msgs'].append(f'{a} vs {b} (선공 {first}, 시드 {seed}): ' + traceback.format_exc()[-1200:])
            continue
        if win is None:
            continue
        out['n'] += 1; out['w'] += int(win == 0); out['turns'] += g.turn
        e = out['by_deck'].setdefault(a, [0, 0]); e[0] += int(win == 0); e[1] += 1
    return out


def eval_match_job(job):
    """Bo3 매치 평가(전략 덱 교체 포함). x = DRL(자리 0), y = 학습표 {'kind': 'table', 'path', 'side'} 또는 휴리스틱.
    학습표 쪽 교체는 y['side'] 표(없으면 learned/side.json), 휴리스틱 쪽 교체도 기존과 같이 학습표 교체 규칙을 쓴다"""
    import policy as P, match as M
    from engine import StalledGame
    decks = _W['decks']; out = {'w': 0, 'n': 0, 'stalled': 0, 'turns': 0, 'errors': 0, 'err_msgs': [], 'by_deck': {}}
    x = job['x']; y = job['y']
    actor = _actor(x['arrays'], x.get('remap'))
    old = (P.POLICY, M.SIDE)
    try:
        if y['kind'] == 'table':
            P.POLICY = _table(y['path'])
            if y.get('side'):
                M.SIDE = _table(y['side'])
        role = 'table' if y['kind'] == 'table' else 'heuristic'
        nrng = np.random.default_rng(0)
        for a, b, first, seed in job['games']:
            try:
                mw, rounds = play_one_match(decks[a], decks[b], first, seed, ['past', role], [actor, None], None, nrng)
            except StalledGame:
                out['stalled'] += 1; continue
            except Exception:
                out['errors'] += 1
                if len(out['err_msgs']) < 3:
                    out['err_msgs'].append(f'{a} vs {b}: ' + traceback.format_exc()[-1200:])
                continue
            if mw is None:
                continue
            out['n'] += 1; out['w'] += int(mw == 0); out['turns'] += len(rounds)
            e = out['by_deck'].setdefault(a, [0, 0]); e[0] += int(mw == 0); e[1] += 1
    finally:
        P.POLICY, M.SIDE = old
    return out


def merge_eval(parts):
    w = sum(p['w'] for p in parts); n = sum(p['n'] for p in parts)
    by = {}
    for p in parts:
        for k, (a, b) in p['by_deck'].items():
            e = by.setdefault(k, [0, 0]); e[0] += a; e[1] += b
    pr = w / max(1, n); se = math.sqrt(pr * (1 - pr) / max(1, n))
    return {'win': round(pr * 100, 1), 'ci95': round(1.96 * se * 100, 1), 'games': n,
            'stalled': sum(p['stalled'] for p in parts), 'errors': sum(p['errors'] for p in parts),
            'err_msgs': [m for p in parts for m in p.get('err_msgs', [])][:3],
            'avg_turns': round(sum(p['turns'] for p in parts) / max(1, n), 2),
            'by_deck': {k: round(a / max(1, b) * 100, 1) for k, (a, b) in sorted(by.items())}}

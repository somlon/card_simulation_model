"""DRL 학습 실행기.

  모방 학습 초기화 (교사 = 학습표)
    python -m drl.train bc  --run learned/drl/run1 --teacher learned/policy.json [--teacher-side learned/side.json] [--matches 3000]
  자기 대국 PPO (bc 결과에서 이어서, 시간 예산 안에서 반복 · 체크포인트)
    python -m drl.train ppo --run learned/drl/run1 --minutes 100
  같은 명령을 다시 실행하면 마지막 체크포인트에서 이어 한다(세션 2시간 한도 · 유휴 회수 대비).

실행 폴더(--run)
  config.json   설정(처음 실행 때 저장, 이어 할 때 그대로 사용)
  ckpt.pt       학습기 전체 상태(망 · 최적화기) + 반복 수 · 최고 점수 · 상대군 목록 — 매 반복 원자적 저장
  model_bc.npz  모방 학습 직후 모델      model_last.npz  마지막 모델      model_best.npz  평가 게이트를 통과한 최고 모델
  snapshots/    상대군(과거 체크포인트)   log.jsonl  반복별 기록
대국에 쓰는 것은 model_*.npz 하나(numpy만 필요). 학습표보다 약하면 채택하지 않는다 — evaluate로 확인.
"""
import os
for _k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_k, '1')      # 작업자 프로세스용 (학습기는 torch.set_num_threads로 따로 정한다)
import argparse, concurrent.futures as cf, json, multiprocessing as mp, random, sys, time
import numpy as np
import torch
from . import buffer as B
from . import model as MD
from . import rollout as R
from .learner import Learner

DEFAULTS = dict(
    seed=1, workers=4, learner_threads=4,
    teacher=None, teacher_side=None, teacher_eps=0.05, teacher_temp=0.03,
    bc_matches=3000, bc_epochs=4, lr_bc=1e-3,
    matches_per_iter=160, epochs=3, minibatch=1024, side_minibatch=256, clip=0.2, lam=0.95,
    lr_actor=3e-4, lr_critic=1e-3, max_grad_norm=0.5, total_iters=400,
    ent_start=0.01, ent_end=0.003, kl_start=1.0, kl_iters=40,
    mix={'self': 0.6, 'past': 0.2, 'table': 0.15, 'heuristic': 0.05},
    snap_every=10, pool_size=5, eval_every=10, eval_k=4, max_matches_per_job=150,
)


def _atomic_torch_save(obj, path):
    tmp = path + '.tmp'
    torch.save(obj, tmp); os.replace(tmp, path)


def _log(run, rec):
    with open(os.path.join(run, 'log.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    print(json.dumps(rec, ensure_ascii=False), flush=True)


def load_config(run, args):
    p = os.path.join(run, 'config.json')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            cfg = json.load(f)
    else:
        cfg = dict(DEFAULTS)
    for k in ('teacher', 'teacher_side', 'workers', 'seed'):
        v = getattr(args, k, None)
        if v is not None:
            cfg[k] = v
    if getattr(args, 'matches', None):
        cfg['bc_matches'] = args.matches
    os.makedirs(run, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    return cfg


def make_pool(cfg):
    """작업자 풀. ProcessPoolExecutor는 작업자가 비정상 종료되면(예: 메모리 한도) BrokenProcessPool로 바로 알려 준다
    (multiprocessing.Pool은 잃어버린 작업을 영원히 기다린다). spawn: 작업자는 학습기의 torch 스레드 상태를 물려받지 않는다"""
    return cf.ProcessPoolExecutor(cfg['workers'], mp_context=mp.get_context('spawn'), initializer=R.init_worker,
                                  initargs=({k: cfg.get(k) for k in ('teacher', 'teacher_side', 'teacher_eps', 'teacher_temp')},))


def collect(pool, cfg, it, cur, past_list, mode, teacher_kl, n_total):
    """n_total 매치를 작업 여러 개로 나눠 생성한다(작업 하나 ≤ max_matches_per_job — 작업자 메모리 상한).
    반환: ({'game': 묶음, 'side': 묶음}, 통계). 묶음의 worker 칸 = 작업 번호(궤적 · 매치 구분용)"""
    rng = random.Random(cfg['seed'] * 100003 + it)
    per = max(1, min(cfg.get('max_matches_per_job', 150), -(-n_total // cfg['workers'])))
    sizes = [per] * (n_total // per) + ([n_total % per] if n_total % per else [])
    jobs = [dict(worker=j, seed=rng.randrange(2 ** 31), n_matches=n, cur=cur, past=(rng.choice(past_list) if past_list else None),
                 mix=cfg['mix'], mode=mode, teacher_kl=teacher_kl) for j, n in enumerate(sizes)]
    packs = {'game': [], 'side': []}; st = {'matches': 0, 'stalled': 0, 'errors': 0}; vs = {}; msgs = []
    for r in pool.map(R.run_job, jobs):
        for k in packs:
            packs[k].append(r['data'][k])
        for k in st:
            st[k] += r['stats'][k]
        for k, (w, n) in r['stats']['vs'].items():
            e = vs.setdefault(k, [0, 0]); e[0] += w; e[1] += n
        msgs += r['stats']['err_msgs']
    st['vs'] = {k: f'{w}/{n}' for k, (w, n) in vs.items()}
    if msgs:
        st['err_sample'] = msgs[0][-600:]
    return {k: B.concat(v) for k, v in packs.items()}, st


def evaluate(pool, cfg, arrays, opponents, k, base=10 ** 7):
    import season as SE
    names = sorted(SE.load_decks())
    gl = R.games_list(names, k, base); W = cfg['workers']
    out = {}
    for name, spec in opponents.items():
        parts = list(pool.map(R.eval_job, [dict(x={'kind': 'drl', 'arrays': arrays}, y=spec, games=gl[i::W]) for i in range(W)]))
        out[name] = R.merge_eval(parts)
    return out


def eval_opponents(cfg):
    ops = {'heuristic': {'kind': 'heuristic'}}
    if cfg.get('teacher'):
        ops['table'] = {'kind': 'table', 'path': cfg['teacher']}
    return ops


def cmd_bc(args):
    cfg = load_config(args.run, args)
    if not cfg.get('teacher'):
        sys.exit('bc에는 --teacher(학습표 policy.json 경로)가 필요함')
    torch.set_num_threads(cfg['learner_threads'])
    lr = Learner(cfg); t0 = time.time()
    with make_pool(cfg) as pool:
        data, st = collect(pool, cfg, 0, None, [], 'bc', False, cfg['bc_matches'])
        # 검증용으로 매치 5%를 떼어 둔다(매치 단위로 나눠 같은 판의 표본이 양쪽에 섞이지 않게)
        is_val = lambda P: (P['worker'].astype(np.int64) * 7919 + P['match']) % 20 == 0
        train = {k: B.select(P, np.nonzero(~is_val(P))[0]) for k, P in data.items() if P is not None}
        val = {k: B.select(P, np.nonzero(is_val(P))[0]) for k, P in data.items() if P is not None}
        del data
        _log(args.run, {'stage': 'bc_collect', 'samples': {k: B.size(P) for k, P in train.items()},
                        'val_samples': {k: B.size(P) for k, P in val.items()}, **st, 'sec': round(time.time() - t0)})
        _log(args.run, {'stage': 'bc_before', **lr.bc_metrics(val)})
        lr.set_lr(1.0, actor_lr=cfg['lr_bc'])   # 모방 학습은 지도 학습 — PPO보다 높은 학습률
        for ep in range(cfg['bc_epochs']):
            m = lr.update(train, 0.0, 0.0, bc=True, epochs=1)
            _log(args.run, {'stage': 'bc_epoch', 'epoch': ep + 1, **m, 'val': lr.bc_metrics(val), 'sec': round(time.time() - t0)})
        lr.set_lr(1.0)                    # PPO 시작 학습률로 되돌림
        arrays = lr.export()
        MD.save_model(os.path.join(args.run, 'model_bc.npz'), arrays, {'stage': 'bc', 'config': cfg})
        ev = evaluate(pool, cfg, arrays, eval_opponents(cfg), cfg['eval_k'])
        _log(args.run, {'stage': 'bc_eval', **{k: {kk: v[kk] for kk in ('win', 'ci95', 'games', 'stalled')} for k, v in ev.items()}})
    score = ev.get('table', ev['heuristic'])['win']
    MD.save_model(os.path.join(args.run, 'model_best.npz'), arrays, {'stage': 'bc', 'eval': ev, 'config': cfg})
    _atomic_torch_save({'learner': lr.state_dict(), 'it': 0, 'best': score, 'snapshots': [], 'bc_done': True}, os.path.join(args.run, 'ckpt.pt'))


def cmd_ppo(args):
    cfg = load_config(args.run, args)
    torch.set_num_threads(cfg['learner_threads'])
    ck_path = os.path.join(args.run, 'ckpt.pt')
    lr = Learner(cfg)
    if os.path.exists(ck_path):
        ck = torch.load(ck_path, weights_only=False); lr.load_state_dict(ck['learner'])
        it, best, snaps = ck['it'], ck['best'], ck['snapshots']
    else:
        it, best, snaps = 0, -1.0, []
    snap_dir = os.path.join(args.run, 'snapshots'); os.makedirs(snap_dir, exist_ok=True)
    past = [MD.load_arrays(p)[0] for p in snaps]
    deadline = time.time() + args.minutes * 60; t0 = time.time()
    with make_pool(cfg) as pool:
        while time.time() < deadline and it < cfg['total_iters']:
            ti = time.time()
            frac = 1.0 - it / cfg['total_iters']
            c_ent = cfg['ent_end'] + (cfg['ent_start'] - cfg['ent_end']) * frac
            c_kl = cfg['kl_start'] * max(0.0, 1.0 - it / max(1, cfg['kl_iters'])) if cfg.get('teacher') else 0.0
            lr.set_lr(frac)
            cur = lr.export()
            data, st = collect(pool, cfg, it + 1, cur, past, 'ppo', c_kl > 0, cfg['matches_per_iter'])
            tc = time.time()
            m = lr.update(data, c_ent, c_kl)
            it += 1
            rec = {'it': it, 'collect_s': round(tc - ti, 1), 'update_s': round(time.time() - tc, 1), 'c_ent': round(c_ent, 4),
                   'c_kl': round(c_kl, 3), **st, **m}
            if it % cfg['snap_every'] == 0:
                p = os.path.join(snap_dir, f'snap_{it:05d}.npz'); MD.save_model(p, cur, {'it': it})
                snaps = (snaps + [p])[-cfg['pool_size']:]; past = [MD.load_arrays(q)[0] for q in snaps]
            arrays = lr.export()
            if it % cfg['eval_every'] == 0:
                ev = evaluate(pool, cfg, arrays, eval_opponents(cfg), cfg['eval_k'])
                rec['eval'] = {k: {kk: v[kk] for kk in ('win', 'ci95', 'stalled')} for k, v in ev.items()}
                score = ev.get('table', ev['heuristic'])['win']
                if score > best:   # 평가 게이트: 교사 상대 승률이 지금까지 최고일 때만 최고 모델 교체
                    best = score; rec['new_best'] = True
                    MD.save_model(os.path.join(args.run, 'model_best.npz'), arrays, {'it': it, 'eval': ev, 'config': cfg})
            MD.save_model(os.path.join(args.run, 'model_last.npz'), arrays, {'it': it, 'config': cfg})
            _atomic_torch_save({'learner': lr.state_dict(), 'it': it, 'best': best, 'snapshots': snaps}, ck_path)
            rec['elapsed_min'] = round((time.time() - t0) / 60, 1)
            _log(args.run, rec)


def main(argv=None):
    ap = argparse.ArgumentParser(description='DRL 판단 정책 학습')
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('bc', 'ppo'):
        s = sub.add_parser(name)
        s.add_argument('--run', required=True); s.add_argument('--teacher'); s.add_argument('--teacher-side', dest='teacher_side')
        s.add_argument('--workers', type=int); s.add_argument('--seed', type=int)
        if name == 'bc':
            s.add_argument('--matches', type=int)
        else:
            s.add_argument('--minutes', type=float, default=100)
    args = ap.parse_args(argv)
    {'bc': cmd_bc, 'ppo': cmd_ppo}[args.cmd](args)


if __name__ == '__main__':
    main()

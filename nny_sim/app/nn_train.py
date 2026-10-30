"""신경망 AI 로컬 학습기 — PyTorch 없이 numpy만으로 배우망(drl/model.py 구조)을 미세 조정한다.

배포본(Windows)에는 PyTorch가 없다(수백 MB). 대국용 추론(drl.model.NumpyActor)과 같은 구조의 순전파를 다시 쓰고
역전파를 손으로 구현했다(tests/nn_grad_check.py 가 PyTorch 학습망 drl/nets.Actor 의 기울기와 대조).

학습 자료: 학습을 켠 대전에서 기록한 판단 표본(nn_samples.py — 학습표 판단이 있는 자리 모두, 그 라운드 승패, 로컬 학습표의 교사 분포).
표본 가중치 s_i(nn_samples 'sw' — 출처별: 사람 대전 learndata.HUMAN_WEIGHT · AI끼리 AI_WEIGHT): 손실 = Σ s_i·L_i / Σ s_i.
손실(표본 i, 후보 j, 고른 후보 a, π = softmax(로짓)):
  L_i = C_TEACHER · KL(t_i ‖ π_i)        로컬 학습표(사람 대전 기록이 반영된 표)를 따라가게
      + C_BASE    · KL(b_i ‖ π_i)        기본 모델(b = 학습 전 모델의 분포)에서 너무 멀어지지 않게(망각 방지)
      − C_RESULT  · r_i · log π_i[a]     이긴 라운드의 선택은 늘리고 진 라운드의 선택은 줄인다(r = ±1)
로짓 기울기 = s_i / Σ s · (C_TEACHER·(π − t) + C_BASE·(π − b) + C_RESULT·r·(π − 원핫(a))).
검증: 매치 단위로 일부를 떼어 두고, 에포크마다 검증 손실이 가장 낮았던 가중치를 남긴다.
전략 덱 교체 배우(side_*)는 바꾸지 않는다(사람 대전 표본에 없음).
"""
import json, os, time
import numpy as np

C_TEACHER = 1.0      # 로컬 학습표(교사) 분포를 따라가는 정도
C_BASE = 0.5         # 기본 모델 분포에 묶어 두는 정도
C_RESULT = 0.3       # 라운드 승패로 고른 후보를 늘리고 줄이는 정도
LR = 1e-4            # Adam 학습률(미세 조정 — 기본 모델 학습의 모방 단계 1e-3보다 작게)
ADAM_B1, ADAM_B2, ADAM_EPS = 0.9, 0.999, 1e-8
EPOCHS = 4
BATCH = 256
CLIP_NORM = 0.5      # 기울기 전체 노름 상한
VAL_EVERY_MATCH = 10  # 매치 10개 중 1개꼴을 검증용으로 떼어 둔다(매치가 이보다 적으면 검증 없이 학습)
FWD_CHUNK = 2048     # 기본 모델 분포 · 검증 손실 계산 묶음 크기

TRAINABLE = ('emb', 'mon_w', 'mon_b', 'spl_w', 'spl_b', 't1_w', 't1_b', 't2_w', 't2_b', 'a_w', 'a_b', 'h1_w', 'h1_b', 'h2_w', 'h2_b')


def _relu(x):
    return np.maximum(x, 0.0)


def _starts(lens):
    flat = lens.reshape(-1).astype(np.int64)
    return np.cumsum(flat) - flat


def seg_sum(vals, lens):
    """연속 조각(길이 lens, 합 = len(vals))별 합 → [len(lens), …]. 빈 조각은 0"""
    lens = lens.reshape(-1).astype(np.int64)
    out = np.zeros((len(lens),) + vals.shape[1:], vals.dtype)
    nz = np.nonzero(lens)[0]
    if len(nz):
        out[nz] = np.add.reduceat(vals, _starts(lens)[nz], axis=0)
    return out


def batch(P, ix=None):
    """표본 묶음(drl.buffer 형식) → 계산용 배열 dict (float32 · int64)"""
    from drl import buffer as B
    if ix is not None:
        P = B.select(P, ix)
    f = lambda k: np.ascontiguousarray(P[k], np.float32)
    i = lambda k: np.ascontiguousarray(P[k], np.int64)
    cl = i('cand_len')
    b = {'n': len(cl), 'g': f('g'), 'bag_ids': i('bag_ids'), 'bag_len': i('bag_len'),
         'mon_id': i('mon_id'), 'mon_f': f('mon_f'), 'spl_id': i('spl_id'), 'spl_f': f('spl_f'), 'dcard': i('dcard'),
         'cand_ids': i('cand_ids'), 'cand_num': f('cand_num'), 'cand_len': cl, 'cand_seg': np.repeat(np.arange(len(cl)), cl),
         'pick': _starts(cl) + i('idx'), 'tp': f('tp'), 'has_tp': np.asarray(P['has_tp'], bool), 'reward': f('reward'),
         'sw': f('sw') if 'sw' in P else np.ones(len(cl), np.float32)}   # 표본 가중치(출처별) — 없으면(예전 묶음) 모두 1
    return b


def forward(w, b, keep=False):
    """후보별 로짓 [Nc]. keep=True면 역전파용 중간값도 돌려준다 (drl.model.NumpyActor.logits 와 같은 계산)"""
    from drl import model as MD, schema as S
    E = w['emb']; n = b['n']
    zb = b['bag_len'].shape[1]
    pooled = seg_sum(E[b['bag_ids']], b['bag_len']).reshape(n, zb * MD.D) * MD.BAG_SCALE
    mi = np.concatenate([E[b['mon_id']], b['mon_f']], -1); mpre = mi @ w['mon_w'] + w['mon_b']
    mmask = (b['mon_id'] != S.PAD)[..., None].astype(np.float32); mx = (_relu(mpre) * mmask).sum(2).reshape(n, -1)
    si = np.concatenate([E[b['spl_id']], b['spl_f']], -1); spre = si @ w['spl_w'] + w['spl_b']
    smask = (b['spl_id'] != S.PAD)[..., None].astype(np.float32); sx = (_relu(spre) * smask).sum(2).reshape(n, -1)
    x = np.concatenate([b['g'], pooled, mx, sx, E[b['dcard']]], -1)
    h1pre = x @ w['t1_w'] + w['t1_b']; h1 = _relu(h1pre)
    h2pre = h1 @ w['t2_w'] + w['t2_b']; s = _relu(h2pre)
    ci = b['cand_ids']
    ai = np.concatenate([E[ci[:, 0]], E[ci[:, 1]], b['cand_num']], -1); apre = ai @ w['a_w'] + w['a_b']; a = _relu(apre)
    z = np.concatenate([s[b['cand_seg']], a], -1); zpre = z @ w['h1_w'] + w['h1_b']; zh = _relu(zpre)
    logit = (zh @ w['h2_w'] + w['h2_b'])[:, 0]
    if not keep:
        return logit
    return logit, dict(mi=mi, mpre=mpre, mmask=mmask, si=si, spre=spre, smask=smask, x=x, h1pre=h1pre, h1=h1, h2pre=h2pre,
                       ai=ai, apre=apre, z=z, zpre=zpre, zh=zh, zb=zb)


def backward(w, b, c, dlogit):
    """로짓 기울기 [Nc] → 가중치 기울기 dict"""
    from drl import model as MD
    D = MD.D; H = w['t2_w'].shape[1]; n = b['n']
    g = {}
    dl = dlogit[:, None].astype(np.float32)
    g['h2_w'] = c['zh'].T @ dl; g['h2_b'] = dl.sum(0)
    dzpre = (dl @ w['h2_w'].T) * (c['zpre'] > 0)
    g['h1_w'] = c['z'].T @ dzpre; g['h1_b'] = dzpre.sum(0)
    dz = dzpre @ w['h1_w'].T
    ds = seg_sum(dz[:, :H], b['cand_len'])
    dapre = dz[:, H:] * (c['apre'] > 0)
    g['a_w'] = c['ai'].T @ dapre; g['a_b'] = dapre.sum(0)
    dai = dapre @ w['a_w'].T
    dh2pre = ds * (c['h2pre'] > 0)
    g['t2_w'] = c['h1'].T @ dh2pre; g['t2_b'] = dh2pre.sum(0)
    dh1pre = (dh2pre @ w['t2_w'].T) * (c['h1pre'] > 0)
    g['t1_w'] = c['x'].T @ dh1pre; g['t1_b'] = dh1pre.sum(0)
    dx = dh1pre @ w['t1_w'].T
    G = b['g'].shape[1]; zb = c['zb']; HM2 = c['mpre'].shape[1] * c['mpre'].shape[-1]; HS2 = c['spre'].shape[1] * c['spre'].shape[-1]
    o = G; dpooled = dx[:, o:o + zb * D].reshape(n * zb, D) * MD.BAG_SCALE; o += zb * D
    dmx = dx[:, o:o + HM2].reshape(n, c['mpre'].shape[1], 1, -1); o += HM2
    dsx = dx[:, o:o + HS2].reshape(n, c['spre'].shape[1], 1, -1); o += HS2
    dEd = dx[:, o:o + D]
    dmpre = dmx * c['mmask'] * (c['mpre'] > 0)
    g['mon_w'] = c['mi'].reshape(-1, c['mi'].shape[-1]).T @ dmpre.reshape(-1, dmpre.shape[-1]); g['mon_b'] = dmpre.reshape(-1, dmpre.shape[-1]).sum(0)
    dmi = dmpre @ w['mon_w'].T
    dspre = dsx * c['smask'] * (c['spre'] > 0)
    g['spl_w'] = c['si'].reshape(-1, c['si'].shape[-1]).T @ dspre.reshape(-1, dspre.shape[-1]); g['spl_b'] = dspre.reshape(-1, dspre.shape[-1]).sum(0)
    dsi = dspre @ w['spl_w'].T
    # 임베딩: 모음 · 몬스터 칸 · 마법 칸 · 판단 카드 · 후보 카드 두 장의 기울기를 한 번에 모은다
    bag_rows = np.repeat(dpooled, b['bag_len'].reshape(-1), axis=0)
    ids = np.concatenate([b['bag_ids'], b['mon_id'].reshape(-1), b['spl_id'].reshape(-1), b['dcard'], b['cand_ids'][:, 0], b['cand_ids'][:, 1]])
    rows = np.concatenate([bag_rows, dmi[..., :D].reshape(-1, D), dsi[..., :D].reshape(-1, D), dEd, dai[:, :D], dai[:, D:2 * D]])
    gE = np.zeros_like(w['emb']); np.add.at(gE, ids, rows); g['emb'] = gE
    return g


def seg_softmax(logit, b):
    """표본별 softmax · log-softmax [Nc]"""
    cl = b['cand_len']; st = _starts(cl)
    mx = np.maximum.reduceat(logit, st)[b['cand_seg']]
    e = np.exp(logit - mx); den = np.add.reduceat(e, st)[b['cand_seg']]
    return e / den, (logit - mx) - np.log(den)


def loss_grad(logit, b, base_p):
    """(손실 평균, 로짓 기울기, 지표). base_p: 기본 모델 분포 [Nc]"""
    p, lp = seg_softmax(logit, b); n = b['n']; seg = b['cand_seg']
    t = b['tp']; has = b['has_tp'][seg].astype(np.float32)
    onehot = np.zeros_like(p); onehot[b['pick']] = 1.0
    r = b['reward'][seg]
    tiny = 1e-8
    kl_t = np.bincount(seg, has * t * (np.log(np.maximum(t, tiny)) - lp), minlength=n)
    kl_b = np.bincount(seg, base_p * (np.log(np.maximum(base_p, tiny)) - lp), minlength=n)
    pg = -b['reward'] * lp[b['pick']]
    sw = b['sw'].astype(np.float64); wn = sw / sw.sum()   # 표본 가중치(출처별)를 합 1로 — 가중치가 모두 같으면 평균과 같다
    loss = float(((C_TEACHER * kl_t + C_BASE * kl_b + C_RESULT * pg) * wn).sum())
    dlogit = (C_TEACHER * has * (p - t) + C_BASE * (p - base_p) + C_RESULT * r * (p - onehot)) * wn[seg]
    top = np.maximum.reduceat(lp, _starts(b['cand_len']))
    model_top = lp >= top[seg] - 1e-6
    t_top = t >= np.maximum.reduceat(t, _starts(b['cand_len']))[seg] - 1e-9
    agree = np.bincount(seg, (model_top & t_top).astype(np.float64), minlength=n) > 0
    hm = b['has_tp']
    m = {'loss': float(loss), 'kl_teacher': float(kl_t[hm].mean()) if hm.any() else None, 'kl_base': float(kl_b.mean()),
         'teacher_agree': float(agree[hm].mean()) if hm.any() else None,
         'win_logp': float(lp[b['pick']][b['reward'] > 0].mean()) if (b['reward'] > 0).any() else None}
    return loss, dlogit, m


def base_probs(w, P, n):
    """기본 모델(학습 전 가중치)의 후보 분포 [Nc] — 묶음 전체를 FWD_CHUNK씩"""
    out = []
    for i in range(0, n, FWD_CHUNK):
        b = batch(P, np.arange(i, min(i + FWD_CHUNK, n)))
        out.append(seg_softmax(forward(w, b), b)[0].astype(np.float32))
    return np.concatenate(out) if out else np.zeros(0, np.float32)


def _cand_slices(P):
    """표본별 후보 구간(시작, 길이) — 미니배치에 기본 모델 분포를 맞춰 붙일 때"""
    cl = P['cand_len'].astype(np.int64)
    return _starts(cl), cl


def _take(arr, starts, lens, ix):
    from drl import buffer as B
    return B.ragged_take(arr, starts[ix], lens[ix])[0]


def evaluate(w, P, base_p):
    """묶음 전체의 손실 · 지표(갱신 없음)"""
    n = len(P['idx']); st, cl = _cand_slices(P); tot = {}; cnt = 0
    for i in range(0, n, FWD_CHUNK):
        ix = np.arange(i, min(i + FWD_CHUNK, n)); b = batch(P, ix)
        _, _, m = loss_grad(forward(w, b), b, _take(base_p, st, cl, ix))
        k = len(ix); cnt += k
        for key, v in m.items():
            if v is not None: tot[key] = tot.get(key, 0.0) + v * k
    return {k: round(v / cnt, 4) for k, v in tot.items()}


def train(arrays, P, matches, epochs=EPOCHS, seed=0, progress=None, stop=None):
    """arrays: 기본 모델 가중치(배우 + 전략 덱 배우). P: 표본 묶음(game), matches[N]: 표본별 매치 번호.
    반환: (새 가중치, 기록). progress(비율 0~1, 기록), stop() → True면 멈추고 그때까지의 최선 가중치를 돌려준다"""
    rng = np.random.default_rng(seed)
    from drl import buffer as B
    w0 = {k: np.asarray(v, np.float32) for k, v in arrays.items()}
    w = {k: v.copy() for k, v in w0.items()}
    um = np.unique(matches)
    val_m = um[::VAL_EVERY_MATCH] if len(um) >= VAL_EVERY_MATCH else um[:0]
    is_val = np.isin(matches, val_m)
    Ptr, Pva = B.select(P, np.nonzero(~is_val)[0]), (B.select(P, np.nonzero(is_val)[0]) if is_val.any() else None)
    ntr = len(Ptr['idx'])
    if ntr == 0:
        raise ValueError('학습할 표본이 없습니다')
    t0 = time.time()
    bp_tr = base_probs(w0, Ptr, ntr); st_tr, cl_tr = _cand_slices(Ptr)
    bp_va = base_probs(w0, Pva, len(Pva['idx'])) if Pva is not None else None
    log = {'samples': ntr, 'val_samples': 0 if Pva is None else len(Pva['idx']), 'matches': int(len(um)), 'val_matches': int(len(val_m)),
           'before': {'train': evaluate(w, Ptr, bp_tr), 'val': evaluate(w, Pva, bp_va) if Pva is not None else None}, 'epochs': []}
    mom = {k: np.zeros_like(w[k]) for k in TRAINABLE}; vel = {k: np.zeros_like(w[k]) for k in TRAINABLE}; step = 0
    best = None; best_w = {k: v.copy() for k, v in w.items()}
    steps_total = epochs * (-(-ntr // BATCH)); stopped = False
    for ep in range(epochs):
        perm = rng.permutation(ntr); agg = {}
        for i in range(0, ntr, BATCH):
            ix = np.sort(perm[i:i + BATCH]); b = batch(Ptr, ix)
            logit, cache = forward(w, b, keep=True)
            _, dlogit, m = loss_grad(logit, b, _take(bp_tr, st_tr, cl_tr, ix))
            gr = backward(w, b, cache, dlogit)
            norm = float(np.sqrt(sum(float((gr[k] ** 2).sum()) for k in TRAINABLE)))
            scale = min(1.0, CLIP_NORM / (norm + 1e-12)); step += 1
            for k in TRAINABLE:
                gk = gr[k].reshape(w[k].shape) * scale
                mom[k] = ADAM_B1 * mom[k] + (1 - ADAM_B1) * gk; vel[k] = ADAM_B2 * vel[k] + (1 - ADAM_B2) * gk * gk
                mh = mom[k] / (1 - ADAM_B1 ** step); vh = vel[k] / (1 - ADAM_B2 ** step)
                w[k] -= LR * mh / (np.sqrt(vh) + ADAM_EPS)
            for key, v in m.items():
                if v is not None: agg.setdefault(key, []).append(v)
            if progress: progress(step / steps_total, {'epoch': ep + 1, 'loss': round(m['loss'], 4)})
            if stop and stop():
                stopped = True; break
        rec = {'epoch': ep + 1, 'train': {k: round(float(np.mean(v)), 4) for k, v in agg.items()}, 'sec': round(time.time() - t0, 1)}
        if Pva is not None:
            rec['val'] = evaluate(w, Pva, bp_va); score = rec['val']['loss']
        else:
            score = rec['train']['loss']
        if best is None or score < best:
            best = score; best_w = {k: v.copy() for k, v in w.items()}; rec['best'] = True
        log['epochs'].append(rec)
        if stopped:
            break
    log['stopped'] = stopped; log['sec'] = round(time.time() - t0, 1)
    log['after'] = {'train': evaluate(best_w, Ptr, bp_tr), 'val': evaluate(best_w, Pva, bp_va) if Pva is not None else None}
    return best_w, log


def main(argv=None):   # 명령행(개발용): python3 nn_train.py --sim <실행 폴더> --model <기본 모델.npz> --samples <표본 폴더> --out <새 모델.npz>
    import argparse, sys
    ap = argparse.ArgumentParser(); ap.add_argument('--sim', required=True); ap.add_argument('--model', required=True)
    ap.add_argument('--samples', required=True); ap.add_argument('--out', required=True); ap.add_argument('--epochs', type=int, default=EPOCHS)
    a = ap.parse_args(argv)
    sys.path.insert(0, os.path.abspath(a.sim)); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import nn_samples as NS
    from drl import model as MD
    arrays, meta = MD.load_arrays(a.model)
    P, matches, info = NS.load_all(a.samples)
    w, log = train(arrays, P, matches, epochs=a.epochs, progress=lambda f, m: print(f'\r{f * 100:5.1f}% {m}', end='', flush=True))
    print(); print(json.dumps(log, ensure_ascii=False, indent=1))
    MD.save_model(a.out, w, {'stage': 'local', 'base': os.path.basename(a.model), 'train': log})


if __name__ == '__main__':
    main()

"""numpy 학습기(nn_train.py)의 순전파 · 역전파 확인 — 개발 환경 전용(PyTorch 필요).
  python3 nn_grad_check.py <sim>
① 순전파 로짓 = 대국용 추론 drl.model.NumpyActor.logits (표본별)
② 손으로 쓴 역전파 = PyTorch 학습망 drl.nets.Actor 의 자동 미분 (같은 가중치 · 같은 표본, 무작위 로짓 기울기)
③ 손실 기울기(loss_grad) = 수치 미분(중앙 차분)"""
import os, random, sys
import numpy as np
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sim = os.path.abspath(sys.argv[1]); sys.path[:0] = [sim, APP]; os.chdir(sim)
import torch
from drl import model as MD, buffer as B
from drl.agent import DRLAI, Recorder
from drl.nets import Actor
import season as SE, match as M
import nn_train as NT

decks = SE.load_decks(); names = sorted(decks)
w = MD.init_arrays(seed=3); actor = MD.NumpyActor(w)
rec = Recorder(); rng = random.Random(5); obs_list = []
for k in range(2):   # 무작위 가중치 DRL끼리 2매치 — 표본만 모은다
    a, b = rng.sample(names, 2); rec.begin_match()
    mk = lambda d: DRLAI(d['스킬'], actor=actor, mode='sample', rng=np.random.default_rng(k), recorder=rec, seat=0 if d['이름'] == 'A' else 1, log_decisions=False)
    mw, _ = M.play_match(dict(decks[a], 이름='A'), dict(decks[b], 이름='B'), 0, random.Random(k), [], mk, side=True, side_eps=0.0, learn_side=False)
    rec.end_match(mw)
P = rec.packed()['game']; n = B.size(P); print('표본', n, '후보', int(P['cand_len'].sum()))
bt = NT.batch(P)

# ① 순전파 = NumpyActor
logit = NT.forward(w, bt); st = NT._starts(bt['cand_len'])
raw = [e for e in rec.samples]   # packed 이후엔 비어 있음 → 표본 하나씩 다시 계산: 묶음에서 꺼내 NumpyActor 형식으로
err1 = 0.0
for i in range(0, n, max(1, n // 50)):
    s1 = B.select(P, [i]); b1 = NT.batch(s1)
    zb = b1['bag_len'][0]; ids = b1['bag_ids']; bags = []; o = 0
    for L in zb: bags.append(ids[o:o + L]); o += L
    obs = (b1['g'][0], bags, b1['mon_id'][0], b1['mon_f'][0], b1['spl_id'][0], b1['spl_f'][0], b1['dcard'][0])
    ref = actor.logits(obs, (b1['cand_ids'], b1['cand_num']))
    err1 = max(err1, float(np.abs(ref - logit[st[i]:st[i] + len(ref)]).max()))
print('① 순전파 최대 차이', err1)

# ② 역전파 = PyTorch 자동 미분
rs = np.random.default_rng(0); dl = rs.standard_normal(len(logit)).astype(np.float32)
lg, cache = NT.forward(w, bt, keep=True); gnp = NT.backward(w, bt, cache, dl)
net = Actor(); net.load_arrays(w); tb = B.to_torch(P)
out = net(tb); (out * torch.as_tensor(dl)).sum().backward()
worst = 0.0
for k, v in net.named_parameters():
    if k not in gnp: continue
    ref = v.grad.numpy(); got = gnp[k].reshape(ref.shape)
    rel = float(np.abs(ref - got).max() / (np.abs(ref).max() + 1e-8)); worst = max(worst, rel)
    print(f'  {k:6s} 상대 오차 {rel:.2e}')
print('② 역전파 최대 상대 오차', worst)

# ③ 손실 기울기 = 수치 미분 (로짓 몇 칸)
bp = NT.seg_softmax(rs.standard_normal(len(logit)), bt)[0]
lg64 = lg.astype(np.float64); _, d, _ = NT.loss_grad(lg64, bt, bp); errs = []
for j in rs.choice(len(lg64), 20, replace=False):
    e = np.zeros_like(lg64); e[j] = 1e-5
    num = (NT.loss_grad(lg64 + e, bt, bp)[0] - NT.loss_grad(lg64 - e, bt, bp)[0]) / 2e-5
    errs.append(abs(num - d[j]) / (abs(num) + abs(d[j]) + 1e-12))
print('③ 손실 기울기 최대 상대 오차', max(errs))
ok = err1 < 1e-4 and worst < 1e-3 and max(errs) < 1e-4
print('결과:', '통과' if ok else '실패'); sys.exit(0 if ok else 1)

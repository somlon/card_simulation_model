"""학습기: 이익 계산(GAE) · 모방 학습(BC) · PPO 갱신. 표본은 buffer의 묶음 형식(열 단위 numpy)이다.

손실 가중치(가중치 분배)
  배우   L = L_PPO-clip − c_ent·H(π) + c_kl·KL(π_교사 ‖ π)
         c_ent: 0.01 → 0.003 선형 감소(초반 탐색 → 후반 수렴), c_kl: 1.0 → 0 선형 감소(kl_iters 동안, 초반 망각 방지)
  비평가 MSE(V(s_완전), 목표 λ-이익) — 배우와 망 · 최적화기를 분리하므로 가치 손실 계수가 배우 학습을 흔들지 않는다
  전략 덱 교체 배우 · 비평가도 같은 방식(별도 망), λ = 1(몬테카를로; 궤적이 짧다)
이익은 궤적(한 게임의 한 자리)별로 γ = 1, λ = 0.95로 계산하고 배치 전체에서 정규화한다.
보상은 궤적 끝에만 있다: 게임 판단 = 그 게임 승패(±1), 전략 덱 교체 = 매치 승패(±1).
미니배치는 epoch마다 새로 섞어 그때그때 묶는다(표준 PPO; 묶기는 색인 연산이라 빠르다).
"""
import numpy as np
import torch
from . import buffer as B
from .nets import Actor, Critic, SideActor, SideCritic, segment_log_softmax


def gae(values, reward, lam):
    """궤적 하나: values[T](V(s_t)), 끝 보상 reward, γ = 1 → (이익[T], 목표[T])"""
    T = len(values); adv = np.zeros(T, np.float32); last = 0.0
    for t in reversed(range(T)):
        nxt = reward if t == T - 1 else values[t + 1]
        last = (nxt - values[t]) + lam * last
        adv[t] = last
    return adv, adv + np.asarray(values, np.float32)


def _seg_max(x, seg, n):
    """표본별 최댓값 [n]"""
    return torch.full((n,), -1e30, dtype=x.dtype).scatter_reduce(0, seg, x, reduce='amax')


def _teacher_hits(lp, t, seg, n):
    """표본별: 모델의 최고 후보가 교사의 최고 후보인가"""
    mb = lp >= _seg_max(lp, seg, n)[seg] - 1e-6; tb = t >= _seg_max(t, seg, n)[seg] - 1e-9
    return torch.zeros(n).index_add(0, seg, (mb & tb).float()) > 0


class Learner:
    def __init__(self, cfg):
        self.cfg = cfg
        torch.manual_seed(cfg['seed'])
        self.actor = Actor(); self.critic = Critic(); self.sactor = SideActor(); self.scritic = SideCritic()
        self.opt_a = torch.optim.Adam(self.actor.parameters(), lr=cfg['lr_actor'], eps=1e-5)
        self.opt_c = torch.optim.Adam(self.critic.parameters(), lr=cfg['lr_critic'], eps=1e-5)
        self.opt_sa = torch.optim.Adam(self.sactor.parameters(), lr=cfg['lr_actor'], eps=1e-5)
        self.opt_sc = torch.optim.Adam(self.scritic.parameters(), lr=cfg['lr_critic'], eps=1e-5)

    def nets(self, kind):
        """(배우, 비평가, 배우 최적화기, 비평가 최적화기)"""
        return (self.actor, self.critic, self.opt_a, self.opt_c) if kind == 'game' else (self.sactor, self.scritic, self.opt_sa, self.opt_sc)

    # 대국용 가중치(배우 + 전략 덱 배우)
    def export(self):
        return {**self.actor.export(), **self.sactor.export()}

    def state_dict(self):
        return {k: getattr(self, k).state_dict() for k in ('actor', 'critic', 'sactor', 'scritic', 'opt_a', 'opt_c', 'opt_sa', 'opt_sc')}

    def load_state_dict(self, sd):
        for k, v in sd.items():
            getattr(self, k).load_state_dict(v)

    def set_lr(self, frac, actor_lr=None):
        """frac: 남은 비율(1 → 0). 학습률 선형 감소(최소 10%). actor_lr을 주면 배우 쪽은 그 값(모방 학습용)"""
        f = max(0.1, frac)
        for o, base in ((self.opt_a, self.cfg['lr_actor']), (self.opt_sa, self.cfg['lr_actor']),
                        (self.opt_c, self.cfg['lr_critic']), (self.opt_sc, self.cfg['lr_critic'])):
            lr = actor_lr if (actor_lr is not None and o in (self.opt_a, self.opt_sa)) else base * f
            for gp in o.param_groups:
                gp['lr'] = lr

    @torch.no_grad()
    def advantages(self, kind, P, lam, bs=8192):
        """묶음 P의 (이익, 목표, 궤적 수). 비평가는 완전 정보 관측을 본다"""
        crit = self.nets(kind)[1]; n = B.size(P)
        v = np.concatenate([crit(B.to_torch(P, np.arange(i, min(i + bs, n)))).numpy() for i in range(0, n, bs)])
        order, bounds = B.trajectories(P)
        adv = np.zeros(n, np.float32); ret = np.zeros(n, np.float32)
        for s, e in bounds:
            ix = order[s:e]
            a, r = gae(v[ix], float(P['reward'][ix[-1]]), lam)
            adv[ix] = a; ret[ix] = r
        return adv, ret, len(bounds)

    def _policy_step(self, net, opt, b, adv, c_ent, c_kl, clip, bc):
        logits = net(b); seg = b['cand_seg']; n = b['n']
        lp_all = segment_log_softmax(logits, seg, n)
        ent = -torch.zeros(n).index_add(0, seg, torch.exp(lp_all) * lp_all)
        m = b['has_teacher']; t = b['teacher']; st = {}
        if bc:   # 모방 학습: 교사 분포에 대한 교차 엔트로피
            ce = -torch.zeros(n).index_add(0, seg, t * lp_all)
            loss = ce[m].mean()
            st['bc_ce'] = float(loss.detach()); st['bc_acc'] = float(_teacher_hits(lp_all.detach(), t, seg, n)[m].float().mean())
        else:
            lp = lp_all[b['pick']]; ratio = torch.exp(lp - b['logp_old']); a = torch.as_tensor(adv)
            pg = -torch.min(ratio * a, torch.clamp(ratio, 1 - clip, 1 + clip) * a).mean()
            loss = pg - c_ent * ent.mean()
            st.update(pg=float(pg.detach()), ent=float(ent.detach().mean()),
                      clipfrac=float(((ratio.detach() - 1).abs() > clip).float().mean()), approx_kl=float((b['logp_old'] - lp.detach()).mean()))
            if c_kl > 0 and bool(m.any()):
                kl = torch.zeros(n).index_add(0, seg, t * (torch.log(t.clamp_min(1e-8)) - lp_all))
                loss = loss + c_kl * kl[m].mean(); st['kl_teacher'] = float(kl[m].detach().mean())
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), self.cfg['max_grad_norm']); opt.step()
        return st

    def _value_step(self, net, opt, b, ret):
        v = net(b); loss = ((v - torch.as_tensor(ret)) ** 2).mean()
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step()
        return float(loss.detach())

    def update(self, data, c_ent, c_kl, bc=False, epochs=None):
        """data: {'game': 묶음, 'side': 묶음}. bc=True: 모방 학습(교사 분포 교차 엔트로피 + 비평가 몬테카를로 목표)"""
        cfg = self.cfg; epochs = epochs or cfg['epochs']; out = {}
        rng = np.random.default_rng(cfg['seed'] + sum(B.size(P) for P in data.values()))
        for kind in ('game', 'side'):
            P = data.get(kind)
            if B.size(P) == 0:
                continue
            if bc:
                P = B.select(P, np.nonzero(P['has_tp'])[0])     # 교사 분포가 있는 표본만
                if B.size(P) == 0:
                    continue
            net, crit, opt, optc = self.nets(kind)
            if bc:   # λ = 1, γ = 1: 비평가 목표 = 궤적 끝 보상(표본마다 저장됨). 이익은 쓰지 않으므로 비평가 추론을 생략한다
                ret = P['reward'].astype(np.float32); adv = np.zeros_like(ret); ntraj = len(B.trajectories(P)[1])
            else:
                adv, ret, ntraj = self.advantages(kind, P, cfg['lam'] if kind == 'game' else 1.0)
                adv = (adv - adv.mean()) / (adv.std() + 1e-8)
            mb = cfg['minibatch'] if kind == 'game' else cfg.get('side_minibatch', 256)   # 전략 덱 표본은 적다 → 작은 묶음
            agg = {}; n = B.size(P)
            for _ in range(epochs):
                perm = rng.permutation(n)
                for i in range(0, n, mb):
                    ix = np.sort(perm[i:i + mb]); b = B.to_torch(P, ix)
                    s = self._policy_step(net, opt, b, adv[ix], c_ent, c_kl, cfg['clip'], bc)
                    s['v_loss'] = self._value_step(crit, optc, b, ret[ix])
                    for k, v in s.items():
                        agg.setdefault(k, []).append(v)
            out[kind] = {k: round(float(np.mean(v)), 4) for k, v in agg.items()}
            out[kind].update(samples=n, trajs=ntraj)
        return out

    @torch.no_grad()
    def bc_metrics(self, data, bs=8192):
        """모방 학습 검증 지표(갱신 없음): 교사 분포 교차 엔트로피 · 최고 후보 일치율"""
        out = {}
        for kind in ('game', 'side'):
            P = data.get(kind)
            if B.size(P) == 0:
                continue
            P = B.select(P, np.nonzero(P['has_tp'])[0]); n = B.size(P)
            if n == 0:
                continue
            net = self.nets(kind)[0]; ce = []; hit = []
            for i in range(0, n, bs):
                b = B.to_torch(P, np.arange(i, min(i + bs, n))); seg = b['cand_seg']
                lp = segment_log_softmax(net(b), seg, b['n'])
                ce.append(-torch.zeros(b['n']).index_add(0, seg, b['teacher'] * lp)); hit.append(_teacher_hits(lp, b['teacher'], seg, b['n']))
            out[kind] = {'val_ce': round(float(torch.cat(ce).mean()), 4), 'val_acc': round(float(torch.cat(hit).float().mean()), 4), 'val_samples': n}
        return out

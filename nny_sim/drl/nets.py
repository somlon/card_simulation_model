"""PyTorch 학습망 — model.py의 numpy 추론과 같은 구조 · 같은 매개변수 이름(가중치 [입력, 출력] 배치).
배우(Actor) · 비평가(Critic, 완전 정보) · 전략 덱 배우/비평가. 학습에만 필요하다.

가중치 초기화(PPO 실무 관행, Andrychowicz et al. 2021 「What Matters in On-Policy RL」):
  은닉층 직교 초기화 gain √2, 정책 출력층 gain 0.01(초기 정책을 거의 균등하게), 가치 출력층 gain 1, 임베딩 N(0, 0.1) · PAD 0.
"""
import math
import torch
import torch.nn as nn
import torch.nn.functional as Fn
from . import model as MD
from . import schema as S


def _param(shape, gain=None, emb=False):
    t = torch.empty(*shape)
    if emb:
        nn.init.normal_(t, 0.0, 0.1); t[S.PAD] = 0.0
    elif len(shape) == 1:
        nn.init.zeros_(t)
    else:
        nn.init.orthogonal_(t, gain=gain if gain is not None else math.sqrt(2.0))
    return nn.Parameter(t)


class _Base(nn.Module):
    def _make(self, shapes, gains=None, embs=()):
        gains = gains or {}
        for k, shp in shapes.items():
            self.register_parameter(k, _param(shp, gains.get(k), k in embs))

    def export(self):
        return {k: v.detach().cpu().numpy().copy() for k, v in self.named_parameters()}

    def load_arrays(self, arrays):
        with torch.no_grad():
            for k, v in self.named_parameters():
                v.copy_(torch.as_tensor(arrays[k]))


def trunk(P, pre, b, n_bags, bag_key):
    """배치 상태 표현 [B, H]. P: 매개변수 소유 모듈, pre: 이름 앞머리('' 또는 'c_')"""
    E = getattr(P, pre + 'emb')
    B = b['g'].shape[0]
    pooled = Fn.embedding_bag(b[bag_key + '_ids'], E, b[bag_key + '_off'], mode='sum').view(B, n_bags * MD.D) * MD.BAG_SCALE
    mid = b['mon_id']; sid = b['spl_id']
    mx = torch.relu(torch.cat([Fn.embedding(mid, E), b['mon_f']], -1) @ getattr(P, pre + 'mon_w') + getattr(P, pre + 'mon_b'))
    mx = (mx * (mid != S.PAD).unsqueeze(-1).float()).sum(2).reshape(B, -1)
    sx = torch.relu(torch.cat([Fn.embedding(sid, E), b['spl_f']], -1) @ getattr(P, pre + 'spl_w') + getattr(P, pre + 'spl_b'))
    sx = (sx * (sid != S.PAD).unsqueeze(-1).float()).sum(2).reshape(B, -1)
    x = torch.cat([b['g'], pooled, mx, sx, Fn.embedding(b['dcard'], E)], -1)
    h = torch.relu(x @ getattr(P, pre + 't1_w') + getattr(P, pre + 't1_b'))
    return torch.relu(h @ getattr(P, pre + 't2_w') + getattr(P, pre + 't2_b'))


class Actor(_Base):
    def __init__(self):
        super().__init__()
        self._make(MD.actor_shapes(), gains={'h2_w': 0.01}, embs=('emb',))

    def forward(self, b):
        """반환: 후보별 로짓 [Nc] (b['cand_seg']로 표본에 속함)"""
        s = trunk(self, '', b, len(S.BAGS_ACTOR), 'bag')
        E = self.emb; ci = b['cand_ids']
        a = torch.relu(torch.cat([Fn.embedding(ci[:, 0], E), Fn.embedding(ci[:, 1], E), b['cand_num']], -1) @ self.a_w + self.a_b)
        z = torch.cat([s[b['cand_seg']], a], -1)
        return (torch.relu(z @ self.h1_w + self.h1_b) @ self.h2_w + self.h2_b)[:, 0]


def critic_shapes():
    sh = {('c_' + k): v for k, v in MD.actor_shapes().items() if not k.startswith(('a_', 'h1_', 'h2_'))}
    sh['c_t1_w'] = (MD.trunk_in(len(S.BAGS_ORACLE)), MD.H)
    sh['c_v_w'] = (MD.H, 1); sh['c_v_b'] = (1,)
    return sh


class Critic(_Base):
    """완전 정보 비평가 V(s) ∈ (-1, 1) — 학습에만 쓰고 대국에는 쓰지 않는다"""
    def __init__(self):
        super().__init__()
        self._make(critic_shapes(), gains={'c_v_w': 1.0}, embs=('c_emb',))

    def forward(self, b):
        s = trunk(self, 'c_', {**b, 'mon_id': b['omon_id'], 'mon_f': b['omon_f'], 'spl_id': b['ospl_id'], 'spl_f': b['ospl_f']},
                  len(S.BAGS_ORACLE), 'obag')
        return torch.tanh(s @ self.c_v_w + self.c_v_b)[:, 0]


class SideActor(_Base):
    def __init__(self):
        super().__init__()
        self._make(MD.side_shapes(), gains={'s_h2_w': 0.01}, embs=('s_emb',))

    def forward(self, b):
        E = self.s_emb; B = b['g'].shape[0]
        pooled = Fn.embedding_bag(b['bag_ids'], E, b['bag_off'], mode='sum').view(B, -1) * MD.SIDE_BAG_SCALE
        s = torch.relu(torch.relu(torch.cat([b['g'], pooled], -1) @ self.s_t1_w + self.s_t1_b) @ self.s_t2_w + self.s_t2_b)
        ci = b['cand_ids']
        a = torch.relu(torch.cat([Fn.embedding(ci[:, 0], E), Fn.embedding(ci[:, 1], E), b['cand_num']], -1) @ self.s_a_w + self.s_a_b)
        z = torch.cat([s[b['cand_seg']], a], -1)
        return (torch.relu(z @ self.s_h1_w + self.s_h1_b) @ self.s_h2_w + self.s_h2_b)[:, 0]


class SideCritic(_Base):
    def __init__(self):
        super().__init__()
        self._make({'sc_emb': (S.N_CARDS, MD.SD), 'sc_t1_w': (MD.side_trunk_in(len(S.SIDE_BAGS_ORACLE)), MD.SH), 'sc_t1_b': (MD.SH,),
                    'sc_t2_w': (MD.SH, MD.SH), 'sc_t2_b': (MD.SH,), 'sc_v_w': (MD.SH, 1), 'sc_v_b': (1,)},
                   gains={'sc_v_w': 1.0}, embs=('sc_emb',))

    def forward(self, b):
        B = b['g'].shape[0]
        pooled = Fn.embedding_bag(b['obag_ids'], self.sc_emb, b['obag_off'], mode='sum').view(B, -1) * MD.SIDE_BAG_SCALE
        s = torch.relu(torch.relu(torch.cat([b['g'], pooled], -1) @ self.sc_t1_w + self.sc_t1_b) @ self.sc_t2_w + self.sc_t2_b)
        return torch.tanh(s @ self.sc_v_w + self.sc_v_b)[:, 0]


def segment_log_softmax(logits, seg, n_seg):
    """표본별(세그먼트별) log-softmax. logits [Nc], seg [Nc] → [Nc]"""
    mx = torch.full((n_seg,), -1e30, dtype=logits.dtype).scatter_reduce(0, seg, logits, reduce='amax')
    z = logits - mx[seg]
    den = torch.zeros(n_seg, dtype=logits.dtype).index_add(0, seg, torch.exp(z))
    return z - torch.log(den)[seg]

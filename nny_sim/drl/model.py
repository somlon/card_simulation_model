"""신경망 구조 정의 · numpy 추론 · 모델 파일 입출력. (PyTorch 없이 동작 — 학습망은 nets.py)

배우(게임 판단) — 후보마다 점수(로짓)를 매기는 행동 인코딩 구조
  카드 임베딩 E[N_CARDS, D]  (0번 PAD는 항상 0)
  영역 모음(bags): 영역별 Σ E[카드] × BAG_SCALE           → Z×D
  몬스터 칸: ReLU([E[id], 수치] W_mon) · 칸 마스크 합       → 2×HM
  마법 칸  : ReLU([E[id], 수치] W_spl) · 칸 마스크 합       → 2×HS
  상태 s = ReLU(ReLU([전역, 모음, 몬스터, 마법, E[판단 카드]] W_t1) W_t2)          [H]
  행동 a = ReLU([E[주 카드], E[보조 카드], 행동 수치] W_a)                          [HA]
  로짓   = ReLU([s, a] W_h1) W_h2                                                   [K]
비평가(학습 전용, nets.py)는 같은 몸통에 완전 정보 모음 · 칸을 받아 V(s) 하나를 낸다.
전략 덱 교체 배우는 작은 별도 망(side_*).
"""
import io, json, os
import numpy as np
from . import schema as S

D = 32; HM = 64; HS = 32; H = 256; HA = 128; H2 = 256
BAG_SCALE = 0.2
SD = 16; SH = 128; SA = 64
SIDE_BAG_SCALE = 0.2


def trunk_in(n_bags):
    return S.G_DIM + n_bags * D + 2 * HM + 2 * HS + D


def side_trunk_in(n_bags):
    return S.SIDE_G_DIM + n_bags * SD


# 배우 매개변수 이름과 모양 — nets.py가 같은 이름으로 만든다(내보내기 · 불러오기 호환)
def actor_shapes():
    return {'emb': (S.N_CARDS, D), 'mon_w': (D + S.F_MON, HM), 'mon_b': (HM,), 'spl_w': (D + S.F_SPL, HS), 'spl_b': (HS,),
            't1_w': (trunk_in(len(S.BAGS_ACTOR)), H), 't1_b': (H,), 't2_w': (H, H), 't2_b': (H,),
            'a_w': (2 * D + S.A_DIM, HA), 'a_b': (HA,), 'h1_w': (H + HA, H2), 'h1_b': (H2,), 'h2_w': (H2, 1), 'h2_b': (1,)}


def side_shapes():
    return {'s_emb': (S.N_CARDS, SD), 's_t1_w': (side_trunk_in(len(S.SIDE_BAGS_ACTOR)), SH), 's_t1_b': (SH,),
            's_t2_w': (SH, SH), 's_t2_b': (SH,), 's_a_w': (2 * SD + S.SIDE_A_DIM, SA), 's_a_b': (SA,),
            's_h1_w': (SH + SA, SH), 's_h1_b': (SH,), 's_h2_w': (SH, 1), 's_h2_b': (1,)}


def _relu(x):
    return np.maximum(x, 0.0)


class NumpyActor:
    """대국용 추론기. arrays: 배우 · 전략 덱 배우 가중치(dict). remap: 카드 번호 매핑(schema.check_meta)"""

    def __init__(self, arrays, remap=None):
        self.w = {k: np.asarray(v, dtype=np.float32) for k, v in arrays.items()}
        for k, shp in {**actor_shapes(), **side_shapes()}.items():
            if k not in self.w:
                raise KeyError(f'DRL 모델에 가중치 {k}가 없음')
            got = self.w[k].shape
            if k in ('emb', 's_emb') and remap is not None:   # 카드 풀이 바뀐 옛 모델: 행 수 = 그 모델의 어휘 크기
                ok = got[1:] == shp[1:] and int(remap.max()) < got[0]
            else:
                ok = got == shp
            if not ok:
                raise ValueError(f'DRL 모델 가중치 {k}의 모양 {got} ≠ {shp}')
        self.remap = remap

    def _ids(self, x):
        return x if self.remap is None else self.remap[x]

    def state(self, obs):
        w = self.w; E = w['emb']
        g, bags, mon_id, mon_f, spl_id, spl_f, dcard = obs
        pooled = [E[self._ids(np.asarray(b, dtype=np.int64))].sum(0) if len(b) else np.zeros(D, np.float32) for b in bags]
        mid = self._ids(mon_id)
        mx = _relu(np.concatenate([E[mid], mon_f], -1) @ w['mon_w'] + w['mon_b']) * (mon_id != S.PAD)[..., None]
        sid = self._ids(spl_id)
        sx = _relu(np.concatenate([E[sid], spl_f], -1) @ w['spl_w'] + w['spl_b']) * (spl_id != S.PAD)[..., None]
        x = np.concatenate([g, np.concatenate(pooled) * BAG_SCALE, mx.sum(1).reshape(-1), sx.sum(1).reshape(-1),
                            E[self._ids(np.int64(dcard))]])
        return _relu(_relu(x @ w['t1_w'] + w['t1_b']) @ w['t2_w'] + w['t2_b'])

    def logits(self, obs, cands):
        w = self.w; E = w['emb']
        s = self.state(obs)
        ids, num = cands
        ids = self._ids(ids)
        a = _relu(np.concatenate([E[ids[:, 0]], E[ids[:, 1]], num], -1) @ w['a_w'] + w['a_b'])
        z = np.concatenate([np.broadcast_to(s, (len(a), H)), a], -1)
        return (_relu(z @ w['h1_w'] + w['h1_b']) @ w['h2_w'] + w['h2_b'])[:, 0]

    def side_logits(self, sobs, scands):
        w = self.w; E = w['s_emb']
        g, bags = sobs
        pooled = [E[self._ids(np.asarray(b, dtype=np.int64))].sum(0) if len(b) else np.zeros(SD, np.float32) for b in bags]
        s = _relu(_relu(np.concatenate([g, np.concatenate(pooled) * SIDE_BAG_SCALE]) @ w['s_t1_w'] + w['s_t1_b']) @ w['s_t2_w'] + w['s_t2_b'])
        ids, num = scands
        ids = self._ids(ids)
        a = _relu(np.concatenate([E[ids[:, 0]], E[ids[:, 1]], num], -1) @ w['s_a_w'] + w['s_a_b'])
        z = np.concatenate([np.broadcast_to(s, (len(a), SH)), a], -1)
        return (_relu(z @ w['s_h1_w'] + w['s_h1_b']) @ w['s_h2_w'] + w['s_h2_b'])[:, 0]


def init_arrays(seed=0):
    """numpy 초기 가중치(테스트 · 도구용). 학습은 nets.py의 초기화를 쓴다"""
    rs = np.random.default_rng(seed); out = {}
    for k, shp in {**actor_shapes(), **side_shapes()}.items():
        if k.endswith('_b'):
            out[k] = np.zeros(shp, np.float32)
        elif k in ('emb', 's_emb'):
            out[k] = (rs.standard_normal(shp) * 0.1).astype(np.float32); out[k][S.PAD] = 0
        else:
            out[k] = (rs.standard_normal(shp) * np.sqrt(2.0 / shp[0])).astype(np.float32)
    return out


# ── 모델 파일 ── npz 하나에 가중치 + 메타(JSON 문자열)를 담는다. 임시 파일에 쓴 뒤 교체(원자적 저장)
def save_model(path, arrays, extra_meta=None):
    meta = {'schema': S.schema_meta(), **(extra_meta or {})}
    d = os.path.dirname(os.path.abspath(path)); os.makedirs(d, exist_ok=True)
    buf = io.BytesIO()
    np.savez_compressed(buf, __meta__=np.array(json.dumps(meta, ensure_ascii=False)), **{k: np.asarray(v) for k, v in arrays.items()})
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(buf.getvalue()); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def load_arrays(path):
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(str(z['__meta__']))
        arrays = {k: z[k] for k in z.files if k != '__meta__'}
    return arrays, meta


def load_actor(path):
    """모델 파일 → NumpyActor (스키마 검사 포함)"""
    arrays, meta = load_arrays(path)
    remap = S.check_meta(meta['schema'])
    keys = set(actor_shapes()) | set(side_shapes())
    return NumpyActor({k: v for k, v in arrays.items() if k in keys}, remap), meta

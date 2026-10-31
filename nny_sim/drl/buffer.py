"""표본 저장 형식 — 열 단위로 묶은 numpy 배열(packed).

표본을 파이썬 객체(작은 배열 20여 개)로 들고 있으면 표본당 약 6KB가 들고, 3,000매치 모방 학습 자료에서
작업자가 메모리 한도(14GB)를 넘겨 종료된 적이 있다. 열 단위로 묶으면 표본당 약 1.7KB이고,
미니배치 묶기도 색인 연산으로 끝난다(파이썬 반복 없음).

묶음 dict 한 개 = 한 종류('game' 또는 'side')의 표본 N개
  공통: idx[N] logp[N] has_tp[N] tp[Nc] seat[N] gid[N] match[N] worker[N] reward[N]
        cand_len[N] cand_ids[Nc,2] cand_num[Nc,A]
  game: g[N,G] mon_id/mon_f/spl_id/spl_f(배우) · omon_id/omon_f/ospl_id/ospl_f(비평가) · dcard[N] · dt[N]
        bag_len[N,ZA] bag_ids[…] · obag_len[N,ZO-ZA] obag_ids[…]
  side: g[N,SG] · bag_len[N,2] bag_ids · obag_len[N,1] obag_ids
수치 특징은 float16으로 저장하고(값 범위 0~수 단위) 학습 직전에 float32로 바꾼다.
"""
import numpy as np

F16 = np.float16


def _ragged(list_of_lists):
    """[[배열, ...], ...] (표본별 영역 배열 목록) → (len[N, Z] int16, 평탄화 번호 int16)"""
    lens = np.array([[len(b) for b in bags] for bags in list_of_lists], np.int16)
    flat = [b for bags in list_of_lists for b in bags]
    ids = np.concatenate(flat).astype(np.int16) if flat else np.zeros(0, np.int16)
    return lens, ids


def pack(kind, entries, worker=0):
    """Recorder 표본 목록 → 묶음 dict. entries: [종류, 자리, 게임 번호, 내용, 보상, 매치 번호]"""
    if not entries:
        return None
    C = [e[3] for e in entries]; N = len(C)
    obs = [c[0] for c in C]; orc = [c[1] for c in C]; cands = [c[2] for c in C]
    P = {'kind': kind}
    P['cand_len'] = np.array([len(c[0]) for c in cands], np.int16)
    P['cand_ids'] = np.concatenate([c[0] for c in cands]).astype(np.int16)
    P['cand_num'] = np.concatenate([c[1] for c in cands]).astype(F16)
    P['idx'] = np.array([c[3] for c in C], np.int16); P['logp'] = np.array([c[4] for c in C], np.float32)
    P['has_tp'] = np.array([c[5] is not None for c in C])
    P['tp'] = np.concatenate([c[5] if c[5] is not None else np.zeros(k, np.float32) for c, k in zip(C, P['cand_len'])]).astype(np.float32)
    P['seat'] = np.array([e[1] for e in entries], np.int8)
    P['gid'] = np.array([e[2] if kind == 'game' else e[5] for e in entries], np.int64)   # 전략 덱 궤적 = 매치
    P['match'] = np.array([e[5] for e in entries], np.int32); P['worker'] = np.full(N, worker, np.int16)
    P['reward'] = np.array([e[4] for e in entries], np.float32)
    if kind == 'game':
        P['g'] = np.stack([o[0] for o in obs]).astype(F16)
        P['mon_id'] = np.stack([o[2] for o in obs]).astype(np.int16); P['mon_f'] = np.stack([o[3] for o in obs]).astype(F16)
        P['spl_id'] = np.stack([o[4] for o in obs]).astype(np.int16); P['spl_f'] = np.stack([o[5] for o in obs]).astype(F16)
        P['dcard'] = np.array([o[6] for o in obs], np.int16); P['dt'] = np.array([c[6] for c in C], np.int8)
        P['bag_len'], P['bag_ids'] = _ragged([o[1] for o in obs])
        if orc[0] is not None:
            P['obag_len'], P['obag_ids'] = _ragged([r[0] for r in orc])
            P['omon_id'] = np.stack([r[1] for r in orc]).astype(np.int16); P['omon_f'] = np.stack([r[2] for r in orc]).astype(F16)
            P['ospl_id'] = np.stack([r[3] for r in orc]).astype(np.int16); P['ospl_f'] = np.stack([r[4] for r in orc]).astype(F16)
    else:
        P['g'] = np.stack([o[0] for o in obs]).astype(F16)
        P['bag_len'], P['bag_ids'] = _ragged([o[1] for o in obs])
        if orc[0] is not None:
            P['obag_len'], P['obag_ids'] = _ragged(orc)
    return P


_RAGGED = {'cand_len': ('cand_ids', 'cand_num', 'tp'), 'bag_len': ('bag_ids',), 'obag_len': ('obag_ids',)}


def concat(packs):
    packs = [p for p in packs if p is not None]
    if not packs:
        return None
    out = {'kind': packs[0]['kind']}
    for k in packs[0]:
        if k != 'kind':
            out[k] = np.concatenate([p[k] for p in packs])
    return out


def size(P):
    return 0 if P is None else len(P['idx'])


def _starts(lens):
    """len[N] 또는 len[N, Z] → 같은 모양의 평탄 배열 시작 위치"""
    flat = lens.reshape(-1).astype(np.int64)
    return (np.cumsum(flat) - flat).reshape(lens.shape)


def ragged_take(flat, starts, lens):
    """평탄 배열에서 (시작, 길이) 조각들을 이어 붙여 가져온다 → (값, 출력 시작 위치)"""
    starts = starts.reshape(-1).astype(np.int64); lens = lens.reshape(-1).astype(np.int64)
    tot = int(lens.sum()); out_off = np.cumsum(lens) - lens
    pos = np.arange(tot, dtype=np.int64) - np.repeat(out_off, lens) + np.repeat(starts, lens)
    return flat[pos], out_off


def select(P, ix):
    """묶음에서 표본 ix만 골라 새 묶음(원래 순서 유지)"""
    ix = np.asarray(ix, np.int64); out = {'kind': P['kind']}
    done = set()
    for lk, deps in _RAGGED.items():
        if lk not in P:
            continue
        st = _starts(P[lk])
        for d in deps:
            out[d], _ = ragged_take(P[d], st[ix], P[lk][ix]); done.add(d)
    for k, v in P.items():
        if k != 'kind' and k not in done:
            out[k] = v[ix]
    return out


def to_torch(P, ix=None):
    """묶음(또는 그 일부 ix) → 학습망 입력 텐서 dict (PyTorch는 여기서만 필요 — 묶기 자체는 numpy만 쓴다)"""
    import torch
    if ix is not None:
        P = select(P, ix)
    T = lambda a, dt=torch.float32: torch.as_tensor(np.ascontiguousarray(a)).to(dt)
    n = len(P['idx']); b = {'n': n, 'g': T(P['g'])}
    b['bag_ids'] = T(P['bag_ids'], torch.long); b['bag_off'] = T(_starts(P['bag_len']).reshape(-1), torch.long)
    if 'obag_len' in P:
        # 비평가 모음 = 배우 모음 + 완전 정보 모음 (표본별로 배우 영역 뒤에 이어 붙인다)
        za = P['bag_len'].shape[1]; zo = P['obag_len'].shape[1]
        lens = np.concatenate([P['bag_len'], P['obag_len']], 1)
        a_st = _starts(P['bag_len']); o_st = _starts(P['obag_len'])
        flat = np.concatenate([P['bag_ids'], P['obag_ids']])
        starts = np.concatenate([a_st, o_st + len(P['bag_ids'])], 1)
        ids, off = ragged_take(flat, starts, lens)
        b['obag_ids'] = T(ids, torch.long); b['obag_off'] = T(off, torch.long)
    if P['kind'] == 'game':
        for k in ('mon_id', 'spl_id', 'omon_id', 'ospl_id', 'dcard'):
            if k in P:
                b[k] = T(P[k], torch.long)
        for k in ('mon_f', 'spl_f', 'omon_f', 'ospl_f'):
            if k in P:
                b[k] = T(P[k])
    cl = P['cand_len'].astype(np.int64); cst = np.cumsum(cl) - cl
    b['cand_ids'] = T(P['cand_ids'], torch.long); b['cand_num'] = T(P['cand_num'])
    b['cand_seg'] = torch.as_tensor(np.repeat(np.arange(n), cl))
    b['pick'] = torch.as_tensor(cst + P['idx'].astype(np.int64))
    b['logp_old'] = T(P['logp']); b['has_teacher'] = torch.as_tensor(P['has_tp'])
    b['teacher'] = T(P['tp'])
    return b


def trajectories(P):
    """궤적(작업자, 게임 번호, 자리)별 표본 번호 목록 — 궤적 안은 시간 순서.
    반환: (order[N]: 궤적별로 정렬한 표본 번호, bounds: 궤적 경계 [(시작, 끝)])"""
    key = np.stack([P['worker'].astype(np.int64), P['gid'], P['seat'].astype(np.int64)], 1)
    order = np.lexsort((np.arange(len(key)), key[:, 2], key[:, 1], key[:, 0]))   # 안정 정렬: 같은 궤적 안의 원래 순서 유지
    k = key[order]
    cut = np.nonzero(np.any(k[1:] != k[:-1], axis=1))[0] + 1
    edges = np.concatenate([[0], cut, [len(order)]])
    return order, list(zip(edges[:-1], edges[1:]))

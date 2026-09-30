"""게임 상태 · 후보 행동 → 신경망 입력.

관측은 판단하는 쪽(p)의 시점이다. 배우(actor)는 규칙상 p가 볼 수 있는 정보만 받는다:
  상대 패 · 상대 덱 · 상대의 뒷면 카드는 보이지 않는다(뒷면 카드는 UNK, 공격력 등 0).
비평가(critic)는 학습할 때만 쓰이며 완전 정보를 받는다(PerfectDou의 PTIE): 상대 패 · 상대 남은 덱 · 상대 뒷면 카드의 정체.

관측 튜플 Obs = (g, bags, mon_id, mon_f, spl_id, spl_f, dcard)
  g       float32[G_DIM]              전역 수치
  bags    list[int16 배열] (BAGS_ACTOR) 영역별 카드 번호 모음(순서 없음)
  mon_id  int32[2, N_SLOT]            몬스터 칸 카드 번호 (0 = 나, 1 = 상대)
  mon_f   float32[2, N_SLOT, F_MON]
  spl_id  int32[2, N_SLOT]            마법 · 필드 칸
  spl_f   float32[2, N_SLOT, F_SPL]
  dcard   int                          판단 대상 카드(멀리건 · 트리거) 번호, 없으면 PAD
비평가 추가분 Oracle = (bags_extra, mon_id, mon_f, spl_id, spl_f)  — 칸은 뒷면도 정체를 드러낸 판
"""
import math
import numpy as np
from engine import START_HP, Card, Effect
from . import schema as S

HP = float(START_HP)
_PH = {ph: i for i, ph in enumerate(S.PHASES)}
_ZONE_GROUP = {'hand': 0, 'm': 1, 's': 1, 'shared': 1, 'fieldz': 1, 'grave': 2, 'banish': 3, 'main': 4, 'upper': 4}
_TYPE = {'몬스터': 0, '마법': 1, '필드': 2, '스킬': 3}


def _hidden(c, viewer):
    """viewer가 정체를 볼 수 없는 카드: 상대의 뒷면 카드, 상대의 패 · 덱 카드(패로 간 카드는 엔진에서 faceup=True라 영역으로 판정)"""
    return c.controller != viewer and (not c.faceup or c.zone in ('hand', 'main', 'upper'))


def _mon_slots(g, side_p, viewer, reveal):
    ids = np.zeros(S.N_SLOT, np.int32); f = np.zeros((S.N_SLOT, S.F_MON), np.float32)
    mons = [c for c in g.p[side_p].m if c]
    if g.shared is not None and g.shared.controller == side_p:
        mons.append(g.shared)
    for k, c in enumerate(mons[:S.N_SLOT]):
        hide = _hidden(c, viewer) and not reveal
        ids[k] = S.UNK if hide else S.cid(c.name)
        can_atk = c.faceup and c.pos == 'atk' and c.summon_turn <= g.turn and c.attacks_made < 1 + c.extra_attacks
        f[k] = (0.0 if hide else g.atk(c) / 3000.0, 0.0 if hide else g.df(c) / 3000.0, c.pos == 'atk', c.faceup,
                0.0 if hide else (c.level or 0) / 10.0, c.attacks_made > 0, can_atk and g.turn_player == side_p, c.summon_turn == g.turn,
                bool(c.negated), sum(c.counters.values()) / 5.0, len(c.equips) / 3.0, c.zone == 'shared')
    return ids, f


def _spl_slots(g, side_p, viewer, reveal):
    ids = np.zeros(S.N_SLOT, np.int32); f = np.zeros((S.N_SLOT, S.F_SPL), np.float32)
    sp = [c for c in g.p[side_p].s if c]
    if g.fieldz is not None and g.fieldz.controller == side_p:
        sp.append(g.fieldz)
    for k, c in enumerate(sp[:S.N_SLOT]):
        hide = _hidden(c, viewer) and not reveal
        ids[k] = S.UNK if hide else S.cid(c.name)
        f[k] = (c.faceup, c.set_turn == g.turn, sum(c.counters.values()) / 5.0, c.zone == 'fieldz')
    return ids, f


def _onehot(n, i):
    v = [0.0] * n
    if i is not None and 0 <= i < n:
        v[i] = 1.0
    return v


def global_feats(g, p, dt, dsub):
    me, op = g.p[p], g.p[1 - p]
    mm, om = g.monsters(p), g.monsters(1 - p)
    top = g.chain[-1].player == p if g.chain else False
    so = g.shared_owner
    f = _onehot(len(S.DECISION_TYPES), dt) + _onehot(S.N_DSUB, dsub) + _onehot(len(S.PHASES), _PH.get(g.phase))
    f += [min(g.turn, 30) / 10.0, g.turn == 1, g.turn_player == p, g.first == p, len(g.chain) / 4.0, top, bool(g.locked)]
    f += [me.hp / HP, op.hp / HP, (me.hp - op.hp) / HP]
    f += [len(me.hand) / 7.0, len(op.hand) / 7.0, len(me.main) / 30.0, len(me.upper) / 15.0, len(op.main) / 30.0,
          len(op.upper) / 15.0, len(me.grave) / 20.0, len(op.grave) / 20.0, len(me.banish) / 10.0, len(op.banish) / 10.0]
    f += [me.normal_summons, len(g.free_m(p)) / 5.0, len(g.free_s(p)) / 5.0, len(g.free_m(1 - p)) / 5.0, len(g.free_s(1 - p)) / 5.0]
    f += [g.shared is not None, g.shared is not None and g.shared.controller == p, so == p, so == 1 - p, so is None]
    f += [g.fieldz is not None, g.fieldz is not None and g.fieldz.controller == p]
    f += [g.no_attack.get(p) == g.turn, g.no_attack.get(1 - p) == g.turn, g.no_damage.get(p, -1) >= g.turn, g.no_damage.get(1 - p, -1) >= g.turn]
    f += _onehot(len(S.SKILLS), S.SKILL_IX.get(me.skill.name) if me.skill else None)
    f += _onehot(len(S.SKILLS), S.SKILL_IX.get(op.skill.name) if op.skill else None)
    ma = [g.atk(c) for c in mm if c.faceup]; oa = [g.atk(c) for c in om if c.faceup]
    f += [sum(ma) / 5000.0, sum(oa) / 5000.0, len(mm) / 5.0, len(om) / 5.0, max(ma or [0]) / 3000.0, max(oa or [0]) / 3000.0, me.oath >= g.turn]
    f += [me.hp <= 1000, op.hp <= 1000, not me.main, not me.upper, not op.main, not op.upper]
    return np.asarray(f, dtype=np.float32)


def encode_obs(g, p, decision, oracle=False):
    """(Obs, Oracle 또는 None)"""
    dt, dsub, dname = S.parse_decision(decision)
    me, op = g.p[p], g.p[1 - p]
    ids = lambda cs: np.fromiter((S.cid(c.name) for c in cs), np.int16, len(cs))
    chain_me = [l.card for l in g.chain if l.player == p]; chain_op = [l.card for l in g.chain if l.player != p]
    bags = [ids(me.hand), ids(me.grave), ids(op.grave), ids(me.banish), ids(op.banish), ids(me.main + me.upper),
            ids(chain_me), ids(chain_op)]
    m0, mf0 = _mon_slots(g, p, p, False); m1, mf1 = _mon_slots(g, 1 - p, p, False)
    s0, sf0 = _spl_slots(g, p, p, False); s1, sf1 = _spl_slots(g, 1 - p, p, False)
    obs = (global_feats(g, p, dt, dsub), bags, np.stack([m0, m1]), np.stack([mf0, mf1]), np.stack([s0, s1]), np.stack([sf0, sf1]),
           S.cid(dname) if dname else S.PAD)
    if not oracle:
        return obs, None
    hidden = [c for c in g.field_cards(1 - p) if _hidden(c, p)]
    om1, omf1 = _mon_slots(g, 1 - p, p, True); os1, osf1 = _spl_slots(g, 1 - p, p, True)
    orc = ([ids(op.hand), ids(op.main + op.upper), ids(hidden)],
           np.stack([m0, om1]), np.stack([mf0, omf1]), np.stack([s0, os1]), np.stack([sf0, osf1]))
    return obs, orc


def _payload_parts(pay):
    """후보 payload → (주 카드, 보조 카드, 효과, 제물 수)"""
    if isinstance(pay, Card):
        return pay, None, None, 0
    if isinstance(pay, tuple):
        cards = [x for x in pay if isinstance(x, Card)]
        eff = next((x for x in pay if isinstance(x, Effect)), None)
        nested = next((x for x in pay if isinstance(x, tuple)), None)   # ('extra', card, ('summon', c, 제물, 표시))
        ntrib = len(nested[2]) if nested and len(nested) > 2 and isinstance(nested[2], tuple) else 0
        return (cards[0] if cards else None), (cards[1] if len(cards) > 1 else None), eff, ntrib
    return None, None, None, 0


def encode_cands(g, p, decision, opts, scale):
    """후보 [(label, h, payload)] → (ids int32[K, 2], num float32[K, A_DIM])"""
    dt, _, dname = S.parse_decision(decision)
    K = len(opts)
    hs = [h for _, h, _ in opts]
    order = sorted(range(K), key=lambda i: -hs[i]); rank = [0] * K
    for r, i in enumerate(order):
        rank[i] = r
    hmax = max(hs)
    ids = np.zeros((K, 2), np.int32); num = np.zeros((K, S.A_DIM), np.float32)
    nk = len(S.ACTION_KINDS)
    dnum = decision.rsplit('#', 1)[1] if dt == S.DT_IX['트리거'] and '#' in decision else None
    hand_names = [c.name for c in g.p[p].hand]
    for i, (lab, h, pay) in enumerate(opts):
        ak = S.action_kind(lab, dt)
        c1, c2, eff, ntrib = _payload_parts(pay)
        hide1 = c1 is not None and _hidden(c1, p)   # 상대의 뒷면 카드(대상 후보 등) — 정체를 넣지 않는다
        if c1 is None and ak == S.AK_IX['예'] and dname:
            en = int(dnum) if dnum and dnum.isdigit() else 0
            c1n = dname
        else:
            en = eff.num if eff is not None and not hide1 else 0
            c1n = c1.name if c1 is not None and not hide1 else None
        ids[i, 0] = S.cid(c1n) if c1n else (S.UNK if hide1 else S.PAD)
        ids[i, 1] = S.cid(c2.name) if c2 is not None and not (_hidden(c2, p)) else (S.UNK if c2 is not None else S.PAD)
        v = num[i]
        v[ak] = 1.0
        o = nk
        v[o + 0] = math.tanh(h / scale); v[o + 1] = rank[i] / max(1, K - 1); v[o + 2] = h == hmax; v[o + 3] = h == 0
        if en:
            v[o + 4 + min(en, 4) - 1] = 1.0
        if c1 is not None:
            v[o + 8] = c1.controller == p; v[o + 9] = c1.controller != p
            if not hide1:
                v[o + 10] = (g.atk(c1) if c1.type == '몬스터' else 0) / 3000.0
                v[o + 11] = (g.df(c1) if c1.type == '몬스터' else 0) / 3000.0
                v[o + 12] = (c1.level or 0) / 10.0
                v[o + 13 + _TYPE.get(c1.type, 1)] = 1.0
            v[o + 17 + _ZONE_GROUP.get(c1.zone, 5)] = 1.0
        if c2 is not None:
            tv = (g.atk(c2) if c2.pos == 'atk' else g.df(c2)) if not _hidden(c2, p) else 0
            v[o + 23] = tv / 3000.0; v[o + 24] = c2.pos != 'atk'; v[o + 25] = c2.faceup
            if c1 is not None and not hide1:
                v[o + 26] = (g.atk(c1) - tv) / 3000.0
        v[o + 27] = K / 16.0
        v[o + 28] = ntrib / 2.0
        if c1n:
            v[o + 29] = hand_names.count(c1n) / 3.0
            v[o + 30] = c1n == dname
            sub = S.POOL[c1n].get('subtype') if c1n in S.POOL else None
            v[o + 31] = sub in ('신속', '트리거')
    return ids, num

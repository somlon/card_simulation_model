"""전략 덱 교체(라운드 사이) — DRL 정책.

기존 학습표 방식(match.side_swap)과 같은 규칙 · 같은 선택 범위:
  카드 교체: 전략 덱의 카드(스킬 제외, 활성 덱 동명 3장 미만, 현재 스킬 태그에 맞음) ↔ 활성 덱의 같은 종류(메인/상급) 카드 1:1
  스킬 교체: 전략 덱의 스킬 카드 중 활성 덱 카드가 모두 새 스킬 태그에 맞는 것 (한 번만)
행동 분해: 「넣을 카드 × 뺄 카드」 조합(최대 150여 개)을 한 번에 고르지 않고 두 단계로 고른다.
  ① 넣기 단계: [멈춤] + 넣을 카드(뺄 카드가 있는 것만) + 스킬 교체
  ② 빼기 단계: ①에서 고른 카드와 같은 종류의 활성 덱 카드
최대 MAX_CARD_SWAPS번 카드 교체 + 스킬 교체 1번. 보상은 매치 승패(이 교체가 남은 라운드에 영향을 주므로).
"""
import numpy as np
import match as M
from cards import POOL
from . import schema as S

MAX_CARD_SWAPS = 10
KIND_STOP, KIND_IN, KIND_SKILL, KIND_OUT = 0, 1, 2, 3


STATS = {'teacher_unmapped': 0}   # 학습표 교체를 DRL 후보로 옮기지 못한 횟수(규칙이 어긋나면 늘어난다 — 작업자 통계로 보고)


def candidates(act, st, me, skill_done, pick_in=None, allow_cards=True):
    """넣기 단계(pick_in=None) 또는 빼기 단계(pick_in=넣을 카드)의 후보 [(종류, 뺄 카드/옛 스킬, 넣을 카드/새 스킬)].
    규칙은 match.py의 공용 함수(swap_ins · swap_outs · skill_swaps)를 그대로 쓴다 — 학습표 교체와 같은 범위"""
    if pick_in is not None:
        return [(KIND_OUT, o, pick_in) for o in sorted(M.swap_outs(act, pick_in))]
    out = [(KIND_STOP, None, None)]
    if allow_cards:
        out += [(KIND_IN, None, i) for i in sorted(M.swap_ins(act, st, me)) if M.swap_outs(act, i)]
    if not skill_done:
        out += [(KIND_SKILL, me, n) for n in sorted(M.skill_swaps(act, st, me))]
    return out


def apply_swap(act, st, o, i):
    M.apply_card_swap(act, st, o, i)


def apply_skill(st, old, new):
    st[new] -= 1; st[old] = st.get(old, 0) + 1
    return new


def _bag(counts):
    out = []
    for n, k in sorted(counts.items()):
        out += [S.cid(n)] * max(0, k)
    return np.asarray(out, np.int16)


def encode(act, st, me, opp_skill, ctx, step, skill_done, picking_out, opp_act=None):
    """(관측, 비평가 추가 모음 목록 또는 None)"""
    g = np.zeros(S.SIDE_G_DIM, np.float32)
    if me in S.SKILL_IX: g[S.SKILL_IX[me]] = 1.0
    if opp_skill in S.SKILL_IX: g[len(S.SKILLS) + S.SKILL_IX[opp_skill]] = 1.0
    o = 2 * len(S.SKILLS)
    g[o:o + 7] = (ctx['round'] / 3.0, ctx['wins_me'] / 2.0, ctx['wins_op'] / 2.0, float(ctx['lost_last']), step / 10.0,
                  float(skill_done), float(picking_out))
    return (g, [_bag(act), _bag(st)]), ([_bag(opp_act)] if opp_act is not None else None)


def encode_cands(cands, act):
    ids = np.zeros((len(cands), 2), np.int32); num = np.zeros((len(cands), S.SIDE_A_DIM), np.float32)
    for k, (kind, o, i) in enumerate(cands):
        num[k, kind] = 1.0
        if kind == KIND_STOP:
            continue
        ids[k] = (S.cid(o) if o else S.PAD, S.cid(i))
        num[k, 4] = act.get(i, 0) / 3.0
        if o:
            num[k, 5] = act.get(o, 0) / 3.0
        num[k, 6] = POOL[i]['deck'] == '메인'; num[k, 7] = POOL[i]['deck'] == '상급'
        num[k, 8] = bool(o) and POOL[o]['deck'] == POOL[i]['deck']
    return ids, num


def _describe(swaps):
    return ', '.join(f'「{o}」 → 「{i}」 ({why})' for o, i, why in swaps)


class _Walker:
    """교체 단계를 한 걸음씩 진행하며 후보 · 관측을 만든다(정책 · 교사 공용)"""

    def __init__(self, deck, opp_deck, ctx, record):
        self.me = deck['스킬']; self.act = M.counts_of(deck); self.st = M.counts_of(deck, ('전략',))
        self.opp_skill = opp_deck['스킬']; self.ctx = ctx
        self.opp_act = M.counts_of(opp_deck) if record else None
        self.skill_done = False; self.n_card = 0; self.step = 0; self.pick_in = None; self.swaps = []

    def cands(self):
        return candidates(self.act, self.st, self.me, self.skill_done, self.pick_in, self.n_card < MAX_CARD_SWAPS)

    def obs(self):
        return encode(self.act, self.st, self.me, self.opp_skill, self.ctx, self.step, self.skill_done, self.pick_in is not None, self.opp_act)

    def take(self, cand, why='DRL'):
        """후보 적용. 반환: 멈췄는가"""
        kind, o, i = cand; self.step += 1
        if kind == KIND_STOP:
            return True
        if kind == KIND_IN:
            self.pick_in = i
        elif kind == KIND_OUT:
            apply_swap(self.act, self.st, o, i); self.pick_in = None; self.n_card += 1; self.swaps.append((o, i, why))
        else:
            self.me = apply_skill(self.st, o, i); self.skill_done = True; self.swaps.append((o, i, '스킬 교체'))
        return False

    def deck(self, base):
        d = M.deck_from(base, self.act, self.st); d['스킬'] = self.me
        return d


MAX_STEPS = 2 * MAX_CARD_SWAPS + 2


def drl_side_swap(deck, opp_deck, ctx, actor, mode='greedy', rng=None, recorder=None, seat=0, log=None, pname='', temperature=1.0):
    """DRL 정책으로 전략 덱 교체. 반환: 새 덱(dict). mode: greedy | sample"""
    w = _Walker(deck, opp_deck, ctx, recorder is not None)
    for _ in range(MAX_STEPS):
        cands = w.cands()
        if not cands:
            break
        if len(cands) == 1:
            if w.take(cands[0]):
                break
            continue
        obs, orc = w.obs(); sc = encode_cands(cands, w.act)
        lg = actor.side_logits(obs, sc) / temperature
        lp = lg - lg.max(); lp = lp - np.log(np.exp(lp).sum())
        if mode == 'sample':
            idx = int(min(np.searchsorted(np.cumsum(np.exp(lp)), rng.random()), len(cands) - 1))
        else:
            idx = int(np.argmax(lg))
        if recorder is not None:
            recorder.add('side', seat, None, (obs, orc, sc, idx, float(lp[idx]), None))
        if w.take(cands[idx]):
            break
    if log is not None:
        log.append({'t': 0, 'ph': '', 'tp': 0, 'k': 'side',
                    'm': f'{pname} 전략 덱 교체(DRL): ' + (_describe(w.swaps) if w.swaps else '없음'), 'data': {'player': pname, 'swaps': w.swaps}})
    return w.deck(deck)


def teacher_side_swap(deck, opp_deck, ctx, rng, recorder=None, seat=0, log=None, pname=''):
    """학습표 방식(match.side_swap)으로 교체하고, 그 결정을 DRL 단계(넣기 → 빼기)로 풀어 모방 학습 표본으로 기록한다"""
    cap = []
    new = M.side_swap(deck, opp_deck['스킬'], rng, 0.0, cap, pname)
    if log is not None:
        log.extend(cap)
    if recorder is None:
        return new
    plan = []
    for o, i, why in (cap[-1]['data']['swaps'] if cap else []):
        plan += [(KIND_SKILL, o, i)] if why == '스킬 교체' else [(KIND_IN, None, i), (KIND_OUT, o, i)]
    plan.append((KIND_STOP, None, None))
    w = _Walker(deck, opp_deck, ctx, True)
    for want in plan:
        cands = w.cands()
        if want not in cands:   # 학습표 결정을 후보로 옮길 수 없음 — 이 뒤는 기록하지 않는다(덱은 학습표 결과 그대로)
            STATS['teacher_unmapped'] += 1
            break
        if len(cands) > 1:
            obs, orc = w.obs()
            tp = np.zeros(len(cands), np.float32); tp[cands.index(want)] = 1.0
            recorder.add('side', seat, None, (obs, orc, encode_cands(cands, w.act), cands.index(want), 0.0, tp))
        if w.take(want, '학습표'):
            break
    return new

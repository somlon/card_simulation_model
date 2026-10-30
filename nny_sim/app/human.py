"""사람 플레이어 — AI 자리(make_ai)에 들어가 판단을 화면에서 받는다.

학습형 AI(policy.LearnedAI)의 판단은 거의 모두 choose(결정 이름, 후보 [(이름, 휴리스틱 점수, 실행값)])를 지난다.
HumanAI 는 choose 에서 후보를 화면(Bridge)으로 보내 사람이 고른 것을 돌려준다. 고른 후보의 학습표 키는 AI와 똑같이 trace 에 남기므로,
라운드가 끝나면 사람의 판단도 그 덱의 학습표 값으로 쌓인다(LearnedAI.end_game).
choose 를 거치지 않는 판단 중 선후공 선택 · 덱 위 제외할 덱 · 1턴 1번 [지속] 적용 여부도 사람에게 묻는다.
카드 블록 안에서 엔진이 블록 가치로 자동으로 고르는 하위 선택(J2 선택지 · 코스트로 버릴 카드 · 특수소환할 몬스터 · 카운터 등)도
고르는 쪽이 사람이면 화면에서 묻는다(install_block_hooks — 엔진은 고치지 않고 감싼다).
"""
import sys, threading

import policy as P
from ai import HeuristicAI, INTERFERE
from cards import act_score

# 수의 가치를 계산하는 함수 — 이 안에서 불린 고르기는 「가정」이므로 사람에게 묻지 않고 AI와 같은 기본 방식으로 고른다
# (블록 가치 v_search 가 「이 효과라면 무엇을 서치할까」를 pick_search 로 가정한다 — blocks/lib.py)
EVAL_FRAMES = {'act_score', 'legal', 'can_act'}
EVAL_PREFIX = ('v_', 'can_')   # 블록의 가치(val) · 발동 판정(can) 함수 이름 — blocks/lib.py


def evaluating(depth=60):
    f = sys._getframe(2)
    while f is not None and depth:
        n = f.f_code.co_name
        if n in EVAL_FRAMES or n.startswith(EVAL_PREFIX): return True
        f = f.f_back; depth -= 1
    return False


class Abort(BaseException):
    """대전을 그만둠 — 엔진의 except Exception 에 걸리지 않도록 BaseException"""


class Bridge:
    """엔진 스레드(ask) ↔ 화면(reply) 사이에서 판단 하나를 주고받는다"""

    def __init__(self):
        self.cv = threading.Condition(); self.pending = None; self.answer = None; self.aborted = False; self.seq = 0

    def ask(self, req):
        with self.cv:
            self.seq += 1; req = dict(req, id=self.seq); self.pending = req; self.answer = None; self.cv.notify_all()
            while self.answer is None and not self.aborted: self.cv.wait(0.5)
            if self.aborted: raise Abort()
            a = self.answer; self.pending = None; self.answer = None
            return a

    def reply(self, rid, idx):
        with self.cv:
            p = self.pending
            if not p or p['id'] != rid or not (0 <= idx < len(p['opts'])): return False
            self.answer = idx; self.cv.notify_all(); return True

    def abort(self):
        with self.cv: self.aborted = True; self.cv.notify_all()


class HumanAI(P.LearnedAI):
    def __init__(self, skill, bridge, table, learn=True, hints=False):
        super().__init__(skill, learn=learn, table=table)
        self.bridge = bridge; self.hints = hints

    def _ask(self, g, p, decision, labels, values=None, extra=None, subs=None, marks=None):
        """subs: 후보마다 덧붙일 설명(같은 이름 카드를 칸으로 구별 — 「상대 몬스터 존 3」 등), marks: 후보마다 보드에서 빛낼 카드(기록기 번호)"""
        opts = [{'label': lab, **({'v': values[i]} if values and self.hints else {}),
                 **({'sub': subs[i]} if subs and subs[i] else {}), **({'u': marks[i]} if marks and marks[i] else {})} for i, lab in enumerate(labels)]
        return self.bridge.ask({'kind': 'choose', 'p': p, 'decision': decision, 'opts': opts,
                                'turn': getattr(g, 'turn', 0), 'phase': getattr(g, 'phase', ''), **(extra or {})})

    # ── 놓을 존 · 소환 표시 형식 (사람이 직접) ──
    def choose_zone(self, g, p, c, kind, opts):
        """엔진(Game.place_monster · place_spell)이 묻는 놓을 존: 빈 몬스터 존 번호 · 'shared'(빈 공유 존) / 빈 마법 존 번호.
        화면은 그 존들을 보드에 표시해 눌러 고르게 한다(zones). 가치 계산(가정) 안이면 첫 빈칸(엔진 기본)"""
        if len(opts) == 1 or evaluating(): return opts[0]
        name = {'monster': '몬스터', 'spell': '마법'}[kind]
        labels = ['공유 존' if z == 'shared' else f'{name} 존 {z + 1}' for z in opts]
        zones = [{'seat': p, 'zone': 'shared' if z == 'shared' else ('m' if kind == 'monster' else 's'), 'i': None if z == 'shared' else z} for z in opts]
        return opts[self._ask(g, p, f'놓을 존:{c.name}', labels, extra={'zones': zones, 'card': c.name})]

    def choose_summon_pos(self, g, p, c, how):
        """소환 표시 형식(앞면 공격 · 앞면 수비) — 학습표 AI 와 같은 판단 키(「소환 표시 형식:일반|특수」)로 사람에게 묻는다
        (LearnedAI.choose_summon_pos 는 LearnedAI.choose 를 직접 불러 사람 자리의 choose 를 거치지 않았다)"""
        heur, _ = self.summon_pos_heuristic(g, p, c, how)
        if evaluating(): return heur
        opts = [(f'공격 표시:{c.name}', 5 if heur == 'atk' else 0, 'atk'), (f'수비 표시:{c.name}', 5 if heur == 'def' else 0, 'def')]
        return self.choose(g, p, f'소환 표시 형식:{"일반" if how == "normal" else "특수"}', opts)

    def use_shared(self, g, p, c, full=True):
        """공유 존은 규칙상 언제든 고를 수 있다(§10-2) — 몬스터 존이 가득 찼을 때도 사람은 공유 존에 놓을 수 있다(Game.can_place).
        빈 몬스터 존이 있을 때 공유 존을 고르는 것은 choose_zone 의 후보로 묻는다(엔진이 choose_zone 을 부르면 여기는 쓰지 않음)"""
        return bool(full)

    # ── 시작 패 · 멀리건 메인 · 상급 배분 (사람이 직접) ──
    def choose_split(self, g, p, n):
        """시작 패 n장 중 메인 덱에서 뽑을 매수 — 학습표 AI 와 같은 판단 키(「시작 패 배분(선공|후공)」 · 후보 「메인 k」)로 사람에게 묻는다
        (LearnedAI.choose_split 은 LearnedAI.choose 를 직접 불러 사람 자리의 choose 를 거치지 않았다)"""
        pl = g.p[p]
        lo, hi = max(0, n - len(pl.upper)), min(n, len(pl.main))
        k0 = max(lo, min(hi, self.split_default(g, p, n)[0]))
        if evaluating() or lo >= hi: return k0
        pos = '선공' if g.first == p else '후공'
        return self.choose(g, p, f'시작 패 배분({pos})', self.split_opts(k0, lo, hi), scale=10, shown=split_labels(n))

    def mulligan_split(self, g, p, back):
        """멀리건으로 되돌린 장수만큼 다시 뽑을 때 메인 덱 몫 — 처음 배분과 달라도 된다(§4 STEP 6).
        판단 키는 학습표 AI 와 같은 「시작 패 재배분(선공|후공·n장·남은 상급 k)」"""
        n0 = HeuristicAI.mulligan_split(self, g, p, back)
        pl = g.p[p]; n = len(back)
        lo, hi = max(0, n - len(pl.upper)), min(n, len(pl.main))
        if evaluating() or lo >= hi: return max(lo, min(hi, n0))
        ups = sum(1 for c in pl.hand if c.deck_kind() == '상급')
        pos = '선공' if g.first == p else '후공'
        return self.choose(g, p, f'시작 패 재배분({pos}·{n}장·남은 상급 {min(ups, 3)})',
                           self.split_opts(max(lo, min(hi, n0)), lo, hi), scale=10, shown=split_labels(n))

    def choose(self, g, p, decision, opts, scale=40.0, log=True, explore='eps', shown=None, forced=None, subs=None, marks=None):
        """shown: 화면에 보일 이름표(후보 라벨 → 표시 문자열). 학습 키는 후보 라벨 그대로.
        forced: 이미 사람이 다른 화면에서 고른 후보 번호 — 다시 묻지 않고 학습 기록 · 판단 줄만 남긴다(breeding_pick).
        subs · marks: 화면 설명 · 빛낼 카드(_ask) — 같은 이름 카드를 후보로 따로 낼 때. 학습 키는 후보 라벨(카드 이름) 그대로"""
        if not opts: return None
        me = g.p[p].skill.name; op = g.p[1 - p].skill.name
        base = f'{me} vs {op}|{decision}|'; b = self.bucket(g, p)
        keyed = []
        for lab, h, _ in opts:
            k1 = base + lab; k2 = k1 + '|' + b
            v, n1, n2 = self.T.value(k1, k2, P.prior_of(h, scale))
            keyed.append((k1, k2, round(v * 100, 1)))
        idx = forced if forced is not None else 0 if len(opts) == 1 else \
            self._ask(g, p, decision, [shown(o[0]) if shown else o[0] for o in opts], [k[2] for k in keyed], subs=subs, marks=marks)
        if self.learn: self.trace.append(keyed[idx][:2])
        if log and len(opts) > 1:
            g.L(f'판단[{g.pname(p)}] {decision}: → {opts[idx][0]} (사람)', 'decision')
            g.log[-1]['data'] = {'p': p, 'decision': decision, 'pick': opts[idx][0], 'why': '사람',
                                 'opts': [(o[0], keyed[i][2], 0) for i, o in enumerate(opts)][:6]}
        return self._rec(g, p, idx, opts)

    # ── 제물 · 번식지 (사람이 직접 — AI는 가치가 낮은 제물 · 견제/엔진 안의 우선순위로 골랐다) ──
    def do_extra(self, g, p, pay):
        """제물 소환 · 표시 형식 변경. 제물 소환의 후보(HeuristicAI.extra_summon_options)는 AI가 가치가 낮은 몬스터를 제물로 미리 정해 두므로,
        실행할 때 릴리스할 몬스터를 사람에게 다시 묻는다(사용자 지시 2026-10-29)"""
        kind, c, ts, pos = pay
        if kind == 'summon' and ts and not evaluating():
            ts = self.ask_tributes(g, p, c, len(ts))
        return super().do_extra(g, p, (kind, c, ts, pos))

    def ask_tributes(self, g, p, c, n):
        """자신 필드의 릴리스할 수 있는 몬스터(Game.release_cands)에서 n장. 몬스터 존이 가득 차 있으면 1장 이상은 몬스터 존의 몬스터여야
        소환할 자리가 생긴다(HeuristicAI.pick_tributes 와 같은 조건) — 마지막 1장에서 그 조건을 맞춘다"""
        pool = list(g.release_cands(p)); out = []
        while len(out) < n:
            cand = pool
            if len(out) == n - 1 and not g.free_m(p) and not any(t.zone == 'm' for t in out):
                cand = [x for x in pool if x.zone == 'm']
            x = ask_card(self, g, p, f'「{c.name}」 제물 소환 — 릴리스할 몬스터' + (f' {len(out) + 1}/{n}' if n > 1 else ''), cand)
            out.append(x); pool.remove(x)
        return tuple(out)

    def breeding_pick(self, g, p, cands):
        """번식지: 패에 넣을 카드를 사람이 직접 고르고, 학습표 기록(「번식지(…)」의 견제 · 엔진)은 고른 카드의 종류로 남긴다"""
        if evaluating(): return super().breeding_pick(g, p, cands)
        x = ask_card(self, g, p, '번식지 — 패에 넣을 카드', cands)
        k = sum(1 for y in g.p[p].hand if y.name in INTERFERE)
        when = '자신턴' if g.turn_player == p else '상대턴'
        opts = [('견제', 5, x), ('엔진', 0, x)]
        self.choose(g, p, f'번식지({when}·견제패{min(k, 3)})', opts, forced=0 if x.name in INTERFERE else 1)
        return x

    def choose_first(self, me_skill, opp_skill, rnd, rng, log=None, pname=''):
        """이전 라운드 패자가 정하는 rnd라운드 선후공"""
        base = f'{me_skill} vs {opp_skill}|선후공 선택({rnd}라운드)|'
        labs = (('선공', True), ('후공', False))
        vals = [round(self.T.value(base + lab, base + lab + '|-', 0.5)[0] * 100, 1) for lab, _ in labs]
        idx = self.bridge.ask({'kind': 'choose', 'p': None, 'decision': f'{rnd}라운드 선후공 선택', 'turn': 0, 'phase': '',
                               'opts': [{'label': lab, **({'v': vals[i]} if self.hints else {})} for i, (lab, _) in enumerate(labs)]})
        lab, go = labs[idx]
        self._first_key = (base + lab, base + lab + '|-') if self.learn else None
        if log is not None:
            log.append({'t': 0, 'ph': '', 'tp': 0, 'k': 'decision', 'm': f'판단[{pname}] {rnd}라운드 선후공: → {lab} (사람)',
                        'data': {'decision': f'선후공 선택({rnd}라운드)', 'pick': lab, 'why': '사람', 'opts': []}})
        return go

    def pick_search(self, g, p, cands, why):
        if evaluating(): return HeuristicAI.pick_search(self, g, p, cands, why)
        return super().pick_search(g, p, cands, why)

    def pick_target(self, g, p, cands, purpose='remove', any_side=False):
        if evaluating(): return HeuristicAI.pick_target(self, g, p, cands, purpose, any_side)
        return super().pick_target(g, p, cands, purpose, any_side)

    def choose_mill_deck(self, g, chooser, target, n):
        pl = g.p[target]
        idx = self._ask(g, chooser, f'덱 위에서 {n}장 제외할 덱({"자신" if target == chooser else "상대"})',
                        [f'메인 덱 ({len(pl.main)}장)', f'상급 덱 ({len(pl.upper)}장)'])
        return ('main', 'upper')[idx]

    def cont_apply(self, g, p, src, num, why=''):
        idx = self._ask(g, p, f'「{src.name}」 {num}번 [지속]을 지금 적용할까요? ({why})', ['적용', '적용 안 함'])
        return idx == 0

    # ── 행동 목록: LearnedAI 와 같은 후보 · 실행이되, AI 운용 지침으로 빼는 후보는 빼지 않는다 ──
    # (AI만의 거름망: 손해로 보는 후보(VETO) 제외, 번성충 일반소환은 결착 때만, 결착 가능하면 자동 공격 — policy.LearnedAI 참고)
    def choose_triggers(self, g, p, cands):
        out = []
        for c, e, ev in cands:
            if e.mandatory: out.append((c, e, ev)); continue
            if self.choose(g, p, f'트리거:{c.name}#{e.num}', [('발동', act_score(g, c, e, p, ev, 1), True), ('안 함', 0, False)]):
                out.append((c, e, ev))
        return out

    def respond(self, g, p, opts):
        cand = [('패스', 0, None)]; seen = set(); subs = [None]; marks = [None]
        for c, e in opts:
            lab = f'{c.name}#{e.num}'; key = (lab, c.uid if g.on_field(c) else None)   # 필드의 같은 이름 카드는 따로(어느 카드로 발동할지)
            if key in seen: continue
            seen.add(key); cand.append((lab, act_score(g, c, e, p, g.chain, 0), (c, e)))
            subs.append(slot_label(g, p, c) if g.on_field(c) else None); marks.append(rec_uids(g, c))
        if len(cand) == 1: return None
        return self.choose(g, p, '대응' if g.chain else '우선권', cand, subs=subs, marks=marks)

    def main_phase(self, g, p, ph):
        failed = set()
        for _ in range(MAX_ACTIONS):
            acts = [('종료', 0, None)]; seen = set(); subs = [None]; marks = [None]
            def add(lab, s, pay, card=None):
                """같은 라벨(카드 이름)이어도 필드의 카드는 카드마다 따로 낸다 — 어느 카드로 발동 · 표시 형식 변경할지 고르게"""
                f = card is not None and g.on_field(card)
                key = (lab, card.uid if f else None)
                if key in seen: return
                seen.add(key); acts.append((lab, s, pay)); subs.append(slot_label(g, p, card) if f else None); marks.append(rec_uids(g, card) if card is not None else None)
            if ph == '진행' and g.can_normal(p):
                for c in g.p[p].hand:
                    if c.type != '몬스터' or c.flags.get('effect_only') or c.flags.get('no_normal') or g.tributes_needed(c.level) > 0: continue
                    if g.rule('no_special', c, p) or not g.can_place(c, p) or not g.can_normal(p, c): continue
                    if c.has('솔루나') and any(x.has('솔루나') and x.is_monster() for x in g.monsters(p)): continue
                    add(f'소환:{c.name}', 20 + g.atk(c) / 100, ('summon', c, None))
                for c in g.p[p].hand:
                    alt = getattr(c, 'alt_normal', None)
                    if alt and alt[0](g, p) and g.can_place(c, p) and g.can_normal(p, c): add(f'특수 일반소환:{c.name}', 70, ('alt', c, None))
            for lab, s, pay in self.extra_summon_options(g, p) + self.position_options(g, p, ph): add(lab, s, ('extra', pay[1], pay), pay[1])
            for c, e in g.options(p, ('ignition', 'quick')):
                if (c.uid, e.num) not in failed: add(f'발동:{c.name}#{e.num}', act_score(g, c, e, p, None, 0), ('act', c, e), c)
            if g.free_s(p):
                for c in g.p[p].hand:
                    if c.type == '마법' and c.d.get('subtype') in ('트리거', '신속') and not getattr(c.effects[0], 'hand_ok', False) \
                       and any(e.kind in ('resp', 'trigger', 'quick') for e in c.effects):
                        add(f'세트:{c.name}', 8, ('set', c, None))
            if len(acts) == 1: return
            pick = self.choose(g, p, f'{ph} 행동', acts, subs=subs, marks=marks)
            if pick is None: return
            kind, c, e = pick
            if kind == 'summon': g.normal_summon(c, p); g.after_action(p)
            elif kind == 'alt':
                c.alt_normal[1](g, p); g.L(f'{g.pname(p)} {c} 조건 충족 — 제물 없이 일반소환'); g.normal_summon(c, p); g.after_action(p)
            elif kind == 'act':
                if not g.act(p, c, e): failed.add((c.uid, e.num))
            elif kind == 'extra': self.do_extra(g, p, e)
            else: g._remove(c); g.place_spell(c, p, False); g.L(f'{g.pname(p)} 마법 1장 세트')

    def battle_phase(self, g, p):
        for _ in range(MAX_ATTACKS):
            if g.no_attack.get(p) == g.turn: g.L('공격 봉인 상태', 'sys'); return
            attackers = [m for m in g.battle_cards(p) if m.faceup and m.pos == 'atk' and m.summon_turn <= g.turn
                         and m.attacks_made < self.max_attacks(g, m) and not g.attack_banned(m)]
            if not attackers: return
            # 공격하는 몬스터 · 공격 대상은 카드마다 따로 낸다 — 같은 이름 카드가 여러 장이어도 어느 카드로 · 어느 카드를 공격할지 고른다(사용자 지시 2026-10-30).
            # 학습 키(라벨)는 카드 이름 그대로, 화면 설명(subs)은 칸 · 빛낼 카드(marks)는 그 카드들
            opts = [('공격 종료', 0, None)]; subs = [None]; marks = [None]
            for a in attackers:
                av = g.atk(a)
                if g.can_direct(a) and not (g.cont_flag(a, 'attack_all') and g.battle_cards(1 - p)):
                    opts.append((f'{a.name}→직접', av + 500, (a, None))); subs.append(f'{slot_label(g, p, a)} → 직접공격'); marks.append(rec_uids(g, a))
                for t in g.attack_targets(a):
                    tv = g.atk(t) if t.pos == 'atk' else g.df(t)
                    opts.append((f'{a.name}→{t.name}', av - tv, (a, t))); subs.append(f'{slot_label(g, p, a)} → {slot_label(g, p, t)}')
                    marks.append(rec_uids(g, a, t))
            if len(opts) > 1 and any(g.must_attack(o[2][0]) for o in opts[1:]):
                opts, subs, marks = opts[1:], subs[1:], marks[1:]   # 격투가의 투기장: 반드시 공격해야 하는 몬스터가 공격할 수 있으면 공격 종료 불가 (규칙)
            pick = self.choose(g, p, '공격', opts, scale=400, subs=subs, marks=marks)
            if pick is None: return
            g.attack(*pick)


MAX_ACTIONS = 60   # 한 단계에서 행동을 고르는 최대 횟수(무한 반복 방지 — LearnedAI 는 40)
MAX_ATTACKS = 20
ZONE_LABEL = {'hand': '패', 'm': '몬스터 존', 's': '마법 존', 'grave': '묘지', 'banish': '제외 존', 'main': '메인 덱', 'upper': '상급 덱',
              'shared': '공유 존', 'fieldz': '필드 존', 'skill': '스킬 존'}


def split_labels(n):
    """후보 라벨 「메인 k」 → 화면 이름표 「메인 k / 상급 n-k」"""
    return lambda lab: f'{lab} / 상급 {n - int(lab.split()[-1])}'


def slot_label(g, who, x):
    """필드의 카드가 있는 칸 — 「자신 몬스터 존 2」 · 「상대 공유 존」 · 「상대 몬스터 존 3 (수비)」(같은 이름 카드를 구별)"""
    s = g.side_of(x); side = '자신' if s == who else '상대'; z = ZONE_LABEL.get(x.zone, x.zone)
    if x.zone in ('m', 's'):
        row = g.p[x.controller].m if x.zone == 'm' else g.p[x.controller].s
        if x in row: z += f' {row.index(x) + 1}'
    pos = ' (뒷면)' if not x.faceup else ' (수비)' if x.is_monster() and getattr(x, 'pos', 'atk') == 'def' else ''
    return f'{side} {z}{pos}'


def rec_uids(g, *cards):
    """카드들의 기록기 번호(화면이 보드에서 빛낼 카드) — 기록기가 없으면 None"""
    rec = getattr(g, 'log', None)
    if not hasattr(rec, 'reg'): return None
    return [rec.reg(c) for c in cards if c is not None] or None


def card_label(g, who, x):
    """후보 카드 이름표 — 필드의 카드는 칸 번호까지(같은 이름 몬스터 둘을 구별), 패 · 덱 · 묘지는 이름만(같은 이름은 같은 선택)"""
    s = g.side_of(x); side = '자신' if s == who else '상대'; z = ZONE_LABEL.get(x.zone, x.zone)
    if x.zone in ('m', 's'):
        row = g.p[x.controller].m if x.zone == 'm' else g.p[x.controller].s
        if x in row: z += f' {row.index(x) + 1}'
    return f'{side} {z}: {x.name}' + ('' if x.faceup or s == who else ' (뒷면)')


def uniq_cards(g, who, cards):
    """이름표가 같은 후보는 하나만(같은 선택)"""
    out = {}
    for x in cards: out.setdefault(card_label(g, who, x), x)
    return list(out.items())


def human_at(g, who):
    """who 자리가 사람이고 가치 계산(가정) 중이 아니면 그 HumanAI, 아니면 None"""
    ai = g.p[who].ai
    return ai if isinstance(ai, HumanAI) and not evaluating() else None


def called_from(*names):
    """감싼 함수를 부른 엔진 함수 이름이 names 중 하나인가 — 처리(블록 실행부)에서 부를 때만 묻고, 발동 판정 · 가치 계산에서 부를 때는 AI 방식"""
    return sys._getframe(2).f_code.co_name in names


def ask_card(ai, g, who, title, cards):
    """후보 카드 중 1장을 사람에게 묻는다(이름표가 같은 후보는 하나 — uniq_cards)"""
    opts = uniq_cards(g, who, cards)
    return opts[0][1] if len(opts) == 1 else opts[ai._ask(g, who, title, [lab for lab, _ in opts])][1]


def ask_cards(ai, g, who, title, pool, n, stop=False):
    """후보에서 n장(stop이면 0 ~ n장 — 「그만 고르기」)을 1장씩 묻는다"""
    pool = list(pool); out = []
    while pool and len(out) < n:
        opts = uniq_cards(g, who, pool); labs = [lab for lab, _ in opts]
        if stop: labs = [STOP_LABEL] + labs
        elif len(opts) == 1: out.append(opts[0][1]); pool.remove(opts[0][1]); continue
        i = ai._ask(g, who, f'{title} {len(out) + 1}/{n}' if n > 1 else title, labs)
        if stop:
            if i == 0: break
            i -= 1
        out.append(opts[i][1]); pool.remove(opts[i][1])
    return out


STOP_LABEL = '그만 고르기'
# J2 선택지 이름표 — 선택지의 처리 블록(blocks.lib BLOCKS · dsl 이름) → 화면에 보일 말. 없는 블록은 블록 이름 그대로
BLOCK_LABEL = {'search': '서치', 'special': '특수소환', 'draw': '드로우', 'destroy': '파괴', 'release': '릴리스', 'damage': '대미지',
               'heal': 'HP 회복', 'mill': '덱 위에서 제외', 'counter': '카운터', 'negate_link': '발동 무효', 'negate_card': '효과 무효',
               'place': '필드에 놓기', 'equip': '장착', 'status': '상태 부여', 'stat': '능력치 변경', 'control': '컨트롤 이동',
               'deck_pick_grave': '덱에서 묘지로', 'show_set': '보여 주고 세트', 'kinds': '종류별로 이동'}
MOVE_LABEL = {'grave': '묘지로 보내기', 'banish': '제외', 'deck': '덱으로 되돌리기', 'hand': '패에 넣기'}
MILL_LABEL = {'grave': '덱 위에서 묘지로'}


def option_label(L, l, i, steps):
    parts = []
    for b in steps:
        if b.name in ('branch',): continue
        if b.name == 'move': lab = MOVE_LABEL.get(b.k.get('dest'), b.k.get('dest', 'move'))
        elif b.name == 'mill': lab = MILL_LABEL.get(b.k.get('dest'), BLOCK_LABEL['mill'])
        else: lab = BLOCK_LABEL.get(b.name, b.name)
        n = b.k.get('n')
        if n is not None and b.name in ('search', 'special', 'draw', 'move', 'mill', 'destroy', 'release'):
            try: lab += f' {L.num(l, n)}장'
            except Exception: pass
        parts.append(lab)
    return f'선택지 {i + 1}: ' + (' → '.join(parts) or '처리')


class _HookGlobals(dict):
    """블록 실행부 사본의 전역 이름 — 여기 넣은 이름(max)만 바꾸고 나머지는 blocks.lib 모듈의 지금 값을 읽는다"""
    def __init__(self, mod, **over): super().__init__(over); self.mod = mod

    def __missing__(self, key): return self.mod.__dict__[key]


def run_with_max(L, fn, title):
    """블록 실행부 fn 안에서 「후보 카드 중 max(…, key=…)」로 자동으로 고르는 곳을, 고르는 쪽(실행부의 p)이 사람이면 묻도록 바꾼 사본.
    title(실행부의 지역 변수 → 질문 문구). 엔진 코드를 옮겨 적지 않고 같은 코드 객체를 다른 전역 이름으로 실행한다"""
    import builtins, types
    def pick_max(*a, **kw):
        if len(a) == 1 and 'key' in kw and not kw.get('default'):
            f = sys._getframe(1); loc = f.f_locals
            xs = list(a[0]); g = loc.get('g'); p = loc.get('p')
            if g is not None and p is not None and len(xs) > 1 and all(isinstance(x, L.Card) for x in xs):
                ai = human_at(g, p)
                if ai: return ask_card(ai, g, p, title(loc), xs)
        return builtins.max(*a, **kw)
    return types.FunctionType(fn.__code__, _HookGlobals(L, max=pick_max, __builtins__=builtins), fn.__name__, fn.__defaults__, fn.__closure__)


_HOOKED = False


def install_block_hooks():
    """카드 블록 안에서 자동으로 고르던 하위 선택을, 고르는 쪽이 사람이면 화면에서 묻도록 감싼다. AI의 고르기 · 가치 계산(가정)은 그대로.
    모듈 함수는 L.<함수>를 바꾸고(블록 실행부가 전역 이름으로 부름), 블록 실행부는 L.BLOCKS[이름]의 run을 바꾼다
    (카드 효과 코드 생성이 첫 게임 때 run을 붙잡아 캐시하므로 첫 게임 전에 설치)"""
    global _HOOKED
    if _HOOKED: return
    import blocks.lib as L

    def set_run(name, run): L.BLOCKS[name] = L.BLOCKS[name]._replace(run=run)

    # 「카드 n장 고르기」(코스트 · 대상 · 처리 때 고르는 카드 — 고르는 사람 chooser 'opp'면 상대)
    orig_pick = L.pick_cards

    def pick_cards(g, c, p, pool, n, k):
        who = p if k.get('chooser', 'self') == 'self' else 1 - p
        pool = list(pool); ai = human_at(g, who)
        if not ai or n <= 0 or len(pool) <= n: return orig_pick(g, c, p, pool, n, k)
        return ask_cards(ai, g, who, f'「{c.name}」 카드 고르기', pool, n)
    L.pick_cards = pick_cards

    # 처리 때 고르는 카드: AI만의 고르기 보조(feeds — 버린 카드를 뒤 처리에 쓰기 · spare — 뒤 처리에 쓸 카드 남기기)는 사람에게는 빼고 그대로 고르게
    orig_subjects = L.subjects

    def subjects(g, c, p, l, k):
        q = L.payer(g, p, k) if k.get('cost') and k.get('transfer') else p
        if (k.get('feeds') is not None or k.get('spare') is not None) and human_at(g, q):
            k = {x: v for x, v in k.items() if x not in ('feeds', 'spare')}
        return orig_subjects(g, c, p, l, k)
    L.subjects = subjects

    # 「원하는 수까지」
    orig_want = L.want_pick

    def want_pick(g, c, p, pool, k):
        ai = human_at(g, p)
        if not ai or not called_from('subjects'): return orig_want(g, c, p, pool, k)
        return ask_cards(ai, g, p, f'「{c.name}」 원하는 만큼 고르기', pool, len(pool), stop=True)
    L.want_pick = want_pick

    # 특수소환할 몬스터(처리 때 후보에서)
    orig_summon = L.summon_pick

    def summon_pick(g, c, p, pool, why, brief=False):
        ai = human_at(g, p)
        if not ai or not called_from('do_special'): return orig_summon(g, c, p, pool, why, brief)
        return ask_card(ai, g, p, f'「{c.name}」 특수소환할 몬스터', pool)
    L.summon_pick = summon_pick

    # 카운터: 뗄 카드 · 뗄 개수(「임의의 개수」)
    orig_rm = L._remove_pick

    def remove_pick(g, c, p, xs, k):
        ai = human_at(g, p)
        if not ai or not called_from('do_counter'): return orig_rm(g, c, p, xs, k)
        return ask_card(ai, g, p, f'「{c.name}」 {k["name"]} 카운터를 뗄 카드', xs)
    L._remove_pick = remove_pick
    orig_any = L._any_n

    def any_n(g, c, p, x, k):
        ai = human_at(g, p); cur = x.counters.get(k['name'], 0)
        if not ai or not called_from('do_counter') or cur <= 1: return orig_any(g, c, p, x, k)
        return 1 + ai._ask(g, p, f'「{c.name}」 {x.name}에서 뗄 {k["name"]} 카운터 수', [f'{i}개' for i in range(1, cur + 1)])
    L._any_n = any_n

    # 블록 실행부 안의 max(후보, key=…) 자동 고르기
    set_run('counter', run_with_max(L, L.BLOCKS['counter'].run,
                                    lambda loc: f'「{loc["c"].name}」 {loc["name"]} 카운터를 {"놓을" if loc["op"] == "add" else "뗄"} 카드'))
    set_run('deck_pick_grave', run_with_max(L, L.BLOCKS['deck_pick_grave'].run, lambda loc: f'「{loc["c"].name}」 메인 덱에서 묘지로 보낼 카드'))
    set_run('flip_pick', run_with_max(L, L.BLOCKS['flip_pick'].run, lambda loc: f'「{loc["c"].name}」 앞면 표시로 뒤집을 몬스터'))

    # 레벨 · 속성 부여의 대상(picker 'mark' — AI는 족보 계획으로): 사람은 후보에서 직접
    orig_pick_run = L.BLOCKS['pick'].run

    def pick_run(g, c, p, l, k):
        if k.get('picker') == 'mark' and human_at(g, p): k = {x: v for x, v in k.items() if x != 'picker'}
        return orig_pick_run(g, c, p, l, k)
    set_run('pick', pick_run)

    # J2 「A하거나 B한다」 — 고르는 사람(chooser 'opp'면 상대)
    orig_opt = L.best_option

    def best_option(g, c, p, l, k):
        who = 1 - p if k.get('chooser') == 'opp' else p
        ai = human_at(g, who)
        if not ai: return orig_opt(g, c, p, l, k)
        ev = l.ctx.get('ev')
        ok = [i for i, o in enumerate(k['options']) if L.opt_ok(g, c, p, ev, o)]
        if len(ok) <= 1: return orig_opt(g, c, p, l, k)
        i = ok[ai._ask(g, who, f'「{c.name}」 선택지', [option_label(L, l, i, k['options'][i]) for i in ok])]
        g.L(f'판단[{g.pname(who)}] {c.name}: 선택지 {i + 1} (사람)', 'decision')
        return i
    L.best_option = best_option

    # 「「A」 · 「B」 … 카드를 각각 n장씩 / 합계 n장(같은 종류 cap장까지)」 코스트
    orig_kinds = L.kinds_pick

    def kinds_pick(g, c, p, k):
        xs = orig_kinds(g, c, p, k)
        ai = human_at(g, p)
        if xs is None or not ai or not called_from('do_kinds'): return xs
        return kinds_ask(L, ai, g, c, p, k) or xs
    L.kinds_pick = kinds_pick

    # 「덱에서 X n장을 골라 상대에게 보여 준다」 — 보여 줄 카드
    orig_show = L.BLOCKS['show_set'].run

    def show_run(g, c, p, l, k):
        ai = human_at(g, p)
        if not ai: return orig_show(g, c, p, l, k)
        cs = L.pick_pool(g, c, p, k['scope'], l)
        if len(cs) < k['show'] or not g.free_s(p): return orig_show(g, c, p, l, k)
        shown = ask_cards(ai, g, p, f'「{c.name}」 상대에게 보여 줄 카드', cs, k['show'])
        return show_set_with(L, g, c, p, k, shown)
    set_run('show_set', show_run)

    # 「필드의 뒷면 표시 카드를 전부 원하는 대로 재배치한다」 — 맞바꿀 자신 · 상대 뒷면 카드 쌍
    orig_fd = L.fd_plan

    def fd_plan(g, c, p):
        ai = human_at(g, p)
        if not ai or not called_from('do_rearrange'): return orig_fd(g, c, p)
        o = 1 - p; out = []; used = set()
        while True:
            pairs = []
            for z in ('m', 's'):
                mine = [x for x in getattr(g.p[p], z) if x is not None and not x.faceup and not g.immune(x, p, c) and x.uid not in used]
                theirs = [y for y in getattr(g.p[o], z) if y is not None and not y.faceup and not g.immune(y, p, c) and y.uid not in used]
                pairs += [(x, y) for x in mine for y in theirs]
            if not pairs: return out
            labs = [STOP_LABEL] + [f'{card_label(g, p, x)} ↔ {card_label(g, p, y)}' for x, y in pairs]
            i = ai._ask(g, p, f'「{c.name}」 맞바꿀 뒷면 카드', labs)
            if i == 0: return out
            x, y = pairs[i - 1]; out.append((x, y, 0.0)); used.update((x.uid, y.uid))
    L.fd_plan = fd_plan

    # [지속] 효과 변경 「자신의 「X」 카드의 효과를 「…」로 변경할 수 있다」 — 바꿀지
    orig_swapped = L.swapped

    def swapped(g, c, p, l):
        ai = human_at(g, p)
        if not ai: return orig_swapped(g, c, p, l)
        for src in g.srcs_with('rule:effect_swap'):
            f = src.rules.get('effect_swap')
            if f is None or src.controller != p or not f(g, src, p, c): continue
            if ai._ask(g, p, f'「{src.name}」: {c.name}의 효과를 「{f.label}」로 변경할까요?', ['변경', '변경 안 함']) != 0: return False
            if not g.rule('effect_swap', p, c, use=True, choose=False, why=f'{c.name} 효과 변경'): return False
            g.L(f'판단[{g.pname(p)}] {src.name}: {c}의 효과를 「{f.label}」로 변경 (사람)', 'decision')
            from blocks import build
            build.steps_fn(f.steps)(g, c, p, l)
            return True
        return False
    L.swapped = swapped

    # 포커짐승들: 족보 재료(지금 낼 수 있는 재료 조합 중에서 — cards8.plan_options) · 「원하는 레벨과 원하는 속성」 부여 · 짐승조커 선언
    if hasattr(L, 'combo_pick'):
        import cards8
        orig_combo = L.combo_pick

        def combo_pick(g, c, p, k):
            ai = human_at(g, p)
            if not ai: return orig_combo(g, c, p, k)
            opts = cards8.plan_options(g, c, p, k['kind'])
            if not opts: return orig_combo(g, c, p, k)
            labs = [' + '.join(card_label(g, p, m.card) for m in sel) for _, sel in opts]
            i = 0 if len(opts) == 1 else ai._ask(g, p, f'「{c.name}」 {cards8.KIND_LABEL[k["kind"]]} 재료', labs)
            g.L(f'판단[{g.pname(p)}] {c.name} 족보 재료: {labs[i]} (사람)', 'decision')
            return opts[i][1]
        L.combo_pick = combo_pick
        orig_grant, orig_joker = L.grant_pick, L.joker_pick

        def grant_pick(g, p, t):
            ai = human_at(g, p)
            return ask_level_attr(cards8, ai, g, p, f'「{t.name}」에 부여할') if ai else orig_grant(g, p, t)
        L.grant_pick = grant_pick

        def joker_pick(g, p, c):
            ai = human_at(g, p)
            return ask_level_attr(cards8, ai, g, p, f'「{c.name}」 선언할') if ai else orig_joker(g, p, c)
        L.joker_pick = joker_pick

    # 일반 서치 — 서치할 카드(같은 이름 · 같은 곳은 같은 선택)
    orig_search = L.BLOCKS['search'].run

    def do_search(g, c, p, l, k):
        """search 블록과 같은 처리 — 일반 서치에서 사람이 고르는 것만 다르다(blocks.lib.do_search)"""
        ai = human_at(g, p)
        if not ai or k.get('picker') == 'breeding' or k.get('name_ref'): return orig_search(g, c, p, l, k)
        sc = k['scope']; n = L.num(l, k.get('n', 1)); got = []
        for j in range(n):
            cs = g.search_cands(p, lambda y: L.match_card(g, c, p, y, sc) and y not in got, which=L.deck_which(sc))
            if not cs: g.L(f'{k.get("why") or c.name}: 대상 없음', 'sys'); break
            uniq = {}
            for y in cs: uniq.setdefault((y.name, y.zone), y)
            opts = list(uniq.values())
            x = opts[0] if len(opts) == 1 else opts[ai._ask(g, p, f'「{c.name}」 서치할 카드' + (f' {j + 1}/{n}' if n > 1 else ''),
                                                             [card_label(g, p, y) for y in opts])]
            g.to_hand(x); g.shuffle(p)
            if x.zone != 'hand': break
            g.L(f'{g.pname(p)} {k.get("why") or c.name}: {x} 패에 넣음'); got.append(x)
        if k.get('as') and got: L.refs(l)[k['as']] = got[0] if len(got) == 1 else got
        return len(got) == n or (k.get('upto') and bool(got))
    set_run('search', do_search)
    _HOOKED = True


def ask_level_attr(cards8, ai, g, p, title):
    """「원하는 레벨과 원하는 속성」 — 레벨(cards8.LEVELS) · 속성(cards8.SUITS)을 차례로 묻는다 → (레벨, 속성)"""
    lv = list(cards8.LEVELS)[ai._ask(g, p, f'{title} 레벨', [f'레벨 {x}' for x in cards8.LEVELS])]
    at = cards8.SUITS[ai._ask(g, p, f'{title} 속성', list(cards8.SUITS))]
    g.L(f'판단[{g.pname(p)}] {title} 레벨 · 속성: 레벨 {lv} · {at} (사람)', 'decision')
    return lv, at


def kinds_ask(L, ai, g, c, p, k):
    """kinds_pick 의 사람 판 — 같은 후보 · 매수 규칙(두플리카토르 2배 · 필드 카드는 KINDS_FIELD_MAX 이하)에서 1장씩 묻는다.
    카드 1장은 한 종류에만 쓴다. 남은 종류를 채울 수 없게 되는 카드는 후보에서 뺀다. 못 고르면 None(AI 고르기)"""
    m = 2 if k.get('cost') and g.rule('cost_double', p) else 1
    pool = [x for x in L.cards_in(g, c, p, k['scope']) if not g.on_field(x) or L.value(g, x) <= L.KINDS_FIELD_MAX]
    groups = list(k['groups'])
    if 'per' in k:
        need = {a: k['per'] * m for a in groups}; total = sum(need.values())
    else:
        need = {a: k.get('cap', 1) * m for a in groups}; total = k['total'] * m
    used = {a: 0 for a in groups}; out = []

    def feasible(rest, used):   # 남은 칸을 채울 수 있는가(종류마다 차례로 욕심껏 — 겹치는 카드는 앞 종류에)
        left = [x for x in pool if x not in rest]; got = 0
        for a in groups:
            room = need[a] - used[a]
            xs = [x for x in left if L.grp(x, a)][:room]
            got += len(xs); left = [x for x in left if x not in xs]
        return got >= total - len(rest)

    while len(out) < total:
        cands = []
        for x in pool:
            if x in out: continue
            a = next((a for a in groups if L.grp(x, a) and used[a] < need[a]), None)
            if a is None: continue
            u = dict(used); u[a] += 1
            if feasible(out + [x], u): cands.append((x, a))
        if not cands: return None
        labs = uniq_cards(g, p, [x for x, _ in cands])
        x = labs[0][1] if len(labs) == 1 else labs[ai._ask(g, p, f'「{c.name}」 코스트로 쓸 카드 {len(out) + 1}/{total}', [lab for lab, _ in labs])][1]
        a = next(a for y, a in cands if y is x); used[a] += 1; out.append(x)
    return out


def show_set_with(L, g, c, p, k, shown):
    """show_set 블록의 처리를 사람이 고른 공개 카드로(blocks.lib.do_show_set — 공개 카드 고르기 뒤는 같다: 상대가 무작위로 m장 → 세트 · 나머지 덱으로)"""
    m = g.flag(c, 'pick_n') or k.get('pick', 1)
    picks = g.rng.sample(shown, min(m, len(shown)))
    g.L(f'{g.pname(p)} 덱에서 {", ".join(map(str, shown))} 공개 → {g.pname(1 - p)} 무작위로 {", ".join(map(str, picks))}', 'decision')
    done = 0
    for x in picks:
        if not g.free_s(p): break
        g._remove(x); g.place_spell(x, p, False); g.L(f'{x} 마법 존에 세트'); done += 1
    g.shuffle(p)
    return done > 0

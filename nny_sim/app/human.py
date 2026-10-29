"""사람 플레이어 — AI 자리(make_ai)에 들어가 판단을 화면에서 받는다.

학습형 AI(policy.LearnedAI)의 판단은 거의 모두 choose(결정 이름, 후보 [(이름, 휴리스틱 점수, 실행값)])를 지난다.
HumanAI 는 choose 에서 후보를 화면(Bridge)으로 보내 사람이 고른 것을 돌려준다. 고른 후보의 학습표 키는 AI와 똑같이 trace 에 남기므로,
라운드가 끝나면 사람의 판단도 그 덱의 학습표 값으로 쌓인다(LearnedAI.end_game).
choose 를 거치지 않는 판단 중 선후공 선택 · 덱 위 제외할 덱 · 1턴 1번 [지속] 적용 여부도 사람에게 묻는다.
카드 블록 안의 일부 하위 선택(J2 선택지, 코스트로 버릴 카드 등 블록 가치로 고르는 것)은 AI와 같은 방식으로 자동 처리된다.
"""
import sys, threading

import policy as P
from ai import HeuristicAI
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

    def _ask(self, g, p, decision, labels, values=None):
        opts = [{'label': lab, **({'v': values[i]} if values and self.hints else {})} for i, lab in enumerate(labels)]
        return self.bridge.ask({'kind': 'choose', 'p': p, 'decision': decision, 'opts': opts,
                                'turn': getattr(g, 'turn', 0), 'phase': getattr(g, 'phase', '')})

    def choose(self, g, p, decision, opts, scale=40.0, log=True, explore='eps'):
        if not opts: return None
        me = g.p[p].skill.name; op = g.p[1 - p].skill.name
        base = f'{me} vs {op}|{decision}|'; b = self.bucket(g, p)
        keyed = []
        for lab, h, _ in opts:
            k1 = base + lab; k2 = k1 + '|' + b
            v, n1, n2 = self.T.value(k1, k2, P.prior_of(h, scale))
            keyed.append((k1, k2, round(v * 100, 1)))
        idx = 0 if len(opts) == 1 else self._ask(g, p, decision, [o[0] for o in opts], [k[2] for k in keyed])
        if self.learn: self.trace.append(keyed[idx][:2])
        if log and len(opts) > 1:
            g.L(f'판단[{g.pname(p)}] {decision}: → {opts[idx][0]} (사람)', 'decision')
            g.log[-1]['data'] = {'p': p, 'decision': decision, 'pick': opts[idx][0], 'why': '사람',
                                 'opts': [(o[0], keyed[i][2], 0) for i, o in enumerate(opts)][:6]}
        return self._rec(g, p, idx, opts)

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
        cand = [('패스', 0, None)]; seen = set()
        for c, e in opts:
            lab = f'{c.name}#{e.num}'
            if lab in seen: continue
            seen.add(lab); cand.append((lab, act_score(g, c, e, p, g.chain, 0), (c, e)))
        if len(cand) == 1: return None
        return self.choose(g, p, '대응' if g.chain else '우선권', cand)

    def main_phase(self, g, p, ph):
        failed = set()
        for _ in range(MAX_ACTIONS):
            acts = [('종료', 0, None)]; seen = set()
            def add(lab, s, pay):
                if lab not in seen: seen.add(lab); acts.append((lab, s, pay))
            if ph == '진행' and g.can_normal(p):
                for c in g.p[p].hand:
                    if c.type != '몬스터' or c.flags.get('effect_only') or c.flags.get('no_normal') or g.tributes_needed(c.level) > 0: continue
                    if g.rule('no_special', c, p) or not g.can_place(c, p) or not g.can_normal(p, c): continue
                    if c.has('솔루나') and any(x.has('솔루나') and x.is_monster() for x in g.monsters(p)): continue
                    add(f'소환:{c.name}', 20 + g.atk(c) / 100, ('summon', c, None))
                for c in g.p[p].hand:
                    alt = getattr(c, 'alt_normal', None)
                    if alt and alt[0](g, p) and g.can_place(c, p) and g.can_normal(p, c): add(f'특수 일반소환:{c.name}', 70, ('alt', c, None))
            for lab, s, pay in self.extra_summon_options(g, p) + self.position_options(g, p, ph): add(lab, s, ('extra', pay[1], pay))
            for c, e in g.options(p, ('ignition', 'quick')):
                if (c.uid, e.num) not in failed: add(f'발동:{c.name}#{e.num}', act_score(g, c, e, p, None, 0), ('act', c, e))
            if g.free_s(p):
                for c in g.p[p].hand:
                    if c.type == '마법' and c.d.get('subtype') in ('트리거', '신속') and not getattr(c.effects[0], 'hand_ok', False) \
                       and any(e.kind in ('resp', 'trigger', 'quick') for e in c.effects):
                        add(f'세트:{c.name}', 8, ('set', c, None))
            if len(acts) == 1: return
            pick = self.choose(g, p, f'{ph} 행동', acts)
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
            opts = [('공격 종료', 0, None)]; seen = set()
            for a in attackers:
                av = g.atk(a)
                if g.can_direct(a) and not (g.cont_flag(a, 'attack_all') and g.battle_cards(1 - p)):
                    lab = f'{a.name}→직접'
                    if lab not in seen: seen.add(lab); opts.append((lab, av + 500, (a, None)))
                for t in g.attack_targets(a):
                    tv = g.atk(t) if t.pos == 'atk' else g.df(t)
                    lab = f'{a.name}→{t.name}'
                    if lab not in seen: seen.add(lab); opts.append((lab, av - tv, (a, t)))
            if len(opts) > 1 and any(g.must_attack(o[2][0]) for o in opts[1:]):
                opts = opts[1:]   # 격투가의 투기장: 반드시 공격해야 하는 몬스터가 공격할 수 있으면 공격 종료 불가 (규칙)
            pick = self.choose(g, p, '공격', opts, scale=400)
            if pick is None: return
            g.attack(*pick)


MAX_ACTIONS = 60   # 한 단계에서 행동을 고르는 최대 횟수(무한 반복 방지 — LearnedAI 는 40)
MAX_ATTACKS = 20
ZONE_LABEL = {'hand': '패', 'm': '몬스터 존', 's': '마법 존', 'grave': '묘지', 'banish': '제외 존', 'main': '메인 덱', 'upper': '상급 덱',
              'shared': '공유 존', 'fieldz': '필드 존', 'skill': '스킬 존'}


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


_HOOKED = False


def install_block_hooks():
    """카드 블록 안에서 자동으로 고르던 것 중 「카드 n장 고르기」(blocks.lib.pick_cards — 코스트 · 대상 · 소환할 카드 등)와
    「서치할 카드」(search 블록)를, 고르는 쪽이 사람이면 화면에서 묻도록 감싼다. AI의 고르기 · 가치 계산(가정)은 그대로"""
    global _HOOKED
    if _HOOKED: return
    import blocks.lib as L
    orig_pick = L.pick_cards

    def pick_cards(g, c, p, pool, n, k):
        who = p if k.get('chooser', 'self') == 'self' else 1 - p
        ai = g.p[who].ai; pool = list(pool)
        if not isinstance(ai, HumanAI) or evaluating() or n <= 0 or len(pool) <= n: return orig_pick(g, c, p, pool, n, k)
        out = []
        while pool and len(out) < n:
            opts = uniq_cards(g, who, pool)
            x = opts[0][1] if len(opts) == 1 else opts[ai._ask(g, who, f'「{c.name}」 카드 고르기 {len(out) + 1}/{n}', [lab for lab, _ in opts])][1]
            out.append(x); pool.remove(x)
        return out
    L.pick_cards = pick_cards

    orig_search = L.BLOCKS['search'].run

    def do_search(g, c, p, l, k):
        """search 블록과 같은 처리 — 일반 서치에서 사람이 고르는 것만 다르다(blocks.lib.do_search)"""
        ai = g.p[p].ai
        if not isinstance(ai, HumanAI) or k.get('picker') == 'breeding' or k.get('name_ref'): return orig_search(g, c, p, l, k)
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
    L.BLOCKS['search'] = L.BLOCKS['search']._replace(run=do_search)
    _HOOKED = True

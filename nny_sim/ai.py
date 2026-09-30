"""휴리스틱 판단 정책 v0.1 — 사용자 검토용 초안.
모든 판단은 로그에 '판단' 항목으로 남는다(후보와 점수, 선택).
덱별 지침은 DECK_POLICY에 모은다: 시작 패 배분 / 드로우 덱 선택 / 멀리건 / 서치 우선순위.
"""
from cards import value, VETO
import json, os, random as _r

LEARN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'learned')

class Learner:
    """판단별 승률표(문맥 밴딧). 시뮬레이션이 끝날 때마다 그 판에서 내린 판단에 승패를 반영하고 파일에 누적한다."""
    def __init__(self, name):
        self.path = os.path.join(LEARN_DIR, name + '.json')
        try: self.t = json.load(open(self.path, encoding='utf-8'))
        except Exception: self.t = {}
        self.eps = 0.0          # 탐색 비율 (학습 실행 시 train.py가 올림)
    def stat(self, key, opt):
        w, n = self.t.get(key, {}).get(opt, [0, 0]); return (w + 1) / (n + 2), n
    def choose(self, key, opts, rng):
        if self.eps and rng.random() < self.eps: return rng.choice(opts), '탐색'
        best = max(opts, key=lambda o: self.stat(key, o)[0]); return best, '학습값'
    def update(self, key, opt, won):
        d = self.t.setdefault(key, {}).setdefault(opt, [0, 0]); d[0] += int(won); d[1] += 1
    def save(self):
        os.makedirs(LEARN_DIR, exist_ok=True)
        json.dump(self.t, open(self.path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)

BREEDING = Learner('breeding_ground')

# 상대 턴 견제 카드 (상대 턴에 패에서 쓸 수 있는 번성충 카드)
INTERFERE = ['번성충-노린재', '번성충-하루살이대군', '번성충-먹이바구미', '번성충-장수말벌여왕', '번성충-메뚜기여왕', '번성충-사충보복']

def p_skill(g, p): return g.p[p].skill.name if g.p[p].skill else None

DECK_POLICY = {
    '번성충-대발생': dict(
        split=5,
        split_table={},                                    # 상대 스킬별 고정 배분표 (SPLIT_BY_MATCHUP)
        upper_in_hand=(1, 2),         # 패에 상급 카드를 1~2장 유지하려 함
        search=['번성충-메뚜기여왕', '번성충-넓적배사마귀', '번성충-노린재', '번성충-하루살이대군', '번성충-장수말벌여왕',
                '번성충-시체송장벌레', '번성충-번식지', '번성충-군체이동', '번성충-사충보복', '번성충-맵시기생벌',
                '번성충-대장정', '번성충-병정흰개미', '번성충-먹이바구미'],
        mull_dead=[]),
    '솔루나 아츠': dict(
        split=5,
        split_table={'first': 5, 'second': 5},   # 학습 1단계 결과 (2026-09-22, 대 번성충-대발생, 각 400판)
        upper_in_hand=(0, 0),
        search=['솔루나 시엘', '솔루나 시아', '솔루나 인카운터', '솔루나 아츠 - 태양과 달의 가호', '솔루나 아츠 - 이클립스 하모니',
                '시아 아츠 - 일광정화', '시엘 아츠 - 월광허상', '솔루나 아츠 - 이클립스 오버드라이브', '시아 아츠 - 성광난무',
                '시엘 아츠 - 잔월의 유산', '시엘 아츠 - 월영침식', '시아 아츠 - 일광', '시엘 아츠 - 월영', '솔루나 아츠 - 듀얼 컴뱃',
                '솔루나 아츠 - 여명과 황혼의 궤적', '시아 아츠 - 여명신광', '시아 아츠 - 성광소각', '시아 아츠 - 일광지로',
                '솔루나 아츠 - 천체정렬'],
        mull_dead=['솔루나 시아 - 코로나 이그니스', '솔루나 시엘 - 블러드문 리퍼']),
}


# 매치업별 고정 시작 패 배분: (내 스킬, 상대 스킬) -> {'first': 메인 장수, 'second': 메인 장수}
SPLIT_BY_MATCHUP = {
    # 2026-09-22 선후공별 전수 측정(각 1000판) 후 상위 2개를 4000판 재측정: 선공 5=29.0% / 4=26.9%, 후공 5=45.3% / 4=41.5%
    ('번성충-대발생', '솔루나 아츠'): {'first': 5, 'second': 5},
}

class HeuristicAI:
    def __init__(self, skill, split_override=None):
        self.pol = dict(DECK_POLICY.get(skill, dict(split=5, upper_in_hand=(0, 1), search=[], mull_dead=[])))
        self.split_override = split_override
        self._seen = set()
        self.decisions = []      # {'first': k, 'second': k} — 학습된 배분표

    # ── 기록 ──
    def note(self, g, p, what, cands, pick):
        cs = ', '.join(f'{n}={s:.0f}' for n, s in cands[:8])
        g.L(f'판단[{g.pname(p)}] {what}: 후보 {{{cs}}} → {pick}', 'decision')

    # ── 우선순위 ──
    def card_pri(self, g, p, c):
        lst = self.pol['search']
        base = (len(lst) - lst.index(c.name)) if c.name in lst else 0
        dup = sum(1 for x in g.p[p].hand if x.name == c.name)
        return base - 4 * dup

    # ── 시작 패 · 드로우 ──
    def choose_split(self, g, p, n):
        pos = 'first' if g.first == p else 'second'
        opp_skill = g.p[1 - p].skill.name if g.p[1 - p].skill else None
        table = self.split_override or SPLIT_BY_MATCHUP.get((g.p[p].skill.name, opp_skill)) or self.pol.get('split_table')
        if table and pos in table:
            k = min(table[pos], n); src = f'학습 배분표({"선공" if pos=="first" else "후공"})'
        else:
            k = min(self.pol['split'], n); src = '임시 고정값'
        g.L(f'판단[{g.pname(p)}] 시작 패 배분: 메인 {k} / 상급 {n-k} ({src})', 'decision'); return k

    def mulligan(self, g, p, hand):
        back = [c for c in hand if c.name in self.pol['mull_dead']]
        lo, hi = self.pol['upper_in_hand']
        ups = [c for c in hand if c.deck_kind() == '상급' and c not in back]
        if len(ups) > hi: back += sorted(ups, key=lambda c: self.card_pri(g, p, c))[:len(ups) - hi]
        return back

    def mulligan_split(self, g, p, back):
        """멀리건으로 다시 뽑을 때 메인 덱에서 뽑을 매수. 규칙상 배분을 바꿀 수 있으나(§4 STEP 6) 기본값은 되돌린 카드와 같은 배분"""
        return sum(1 for c in back if c.deck_kind() == '메인')

    def wants_first(self, opp_skill):
        """이전 라운드 패자로서 선후공을 결정 (정본 4, §11-2). 덱별 지침 go_first가 없으면 선공"""
        return self.pol.get('go_first', True)

    def choose_mill_deck(self, g, chooser, target, n):
        """「덱의 위에서부터」(덱 미지정) 제외: 메인 · 상급 중 한쪽을 고른다 (§6-7). 메인 덱에 n장 이상 있으면 메인, 아니면 많은 쪽"""
        pl = g.p[target]
        return 'main' if len(pl.main) >= n or len(pl.main) >= len(pl.upper) else 'upper'

    def choose_draw_deck(self, g, p):
        lo, hi = self.pol['upper_in_hand']
        ups = sum(1 for c in g.p[p].hand if c.deck_kind() == '상급')
        pick = 'upper' if ups < lo and g.p[p].upper else 'main'
        g.L(f'판단[{g.pname(p)}] 드로우 덱: {"상급" if pick=="upper" else "메인"} (패의 상급 {ups}장, 목표 {lo}~{hi})', 'decision')
        return pick

    # ── 선택 ──
    def pick_search(self, g, p, cands, why):
        return max(cands, key=lambda c: self.card_pri(g, p, c))

    def prefers_place(self, g, p, conts): return len(g.spells(p)) < 2

    def pick_target(self, g, p, cands, purpose='remove', any_side=False):
        if not cands: return None
        if purpose == 'banish_grave':
            return max(cands, key=lambda c: (c.type == '몬스터', c.level))
        if any_side:
            opp = [c for c in cands if c.controller != p]
            cands = opp or cands
        if purpose == 'equip_leave':
            return min(cands, key=lambda c: value(g, c))
        return max(cands, key=lambda c: value(g, c) + (0.5 if c.flags.get('effect_only') else 0))

    def pick_discard(self, g, p, hand):
        return min(hand, key=lambda c: (self.card_pri(g, p, c), value(g, c)))

    def choose_triggers(self, g, p, cands):
        out = []; sc = []
        for c, e, ev in cands:
            s = 100 if e.mandatory else (e.score(g, c, p, ev) if e.score else 1)
            sc.append((f'{c.name}#{e.num}', s))
            if s > 0: out.append((s, c, e, ev))
        out.sort(key=lambda x: -x[0])
        if sc: self.note(g, p, '트리거 발동', sc, ', '.join(f'{c.name}#{e.num}' for _, c, e, _ in out) or '없음')
        return [(c, e, ev) for _, c, e, ev in out]

    def respond(self, g, p, opts):
        best = None; sc = []
        for c, e in opts:
            s = e.score(g, c, p, g.chain) if e.score else 0
            if s > 0: sc.append((f'{c.name}#{e.num}', s))
            if s > 0 and (best is None or s > best[0]): best = (s, c, e)
        if sc:
            self.note(g, p, '대응' if g.chain else '우선권', sc, f'{best[1].name}#{best[2].num}')
        return (best[1], best[2]) if best else None

    # ── 진행/정비 단계 ──
    def main_phase(self, g, p, ph):
        for _ in range(40):
            acts = []
            if ph == '진행' and g.p[p].normal_summons > 0:
                for c in g.p[p].hand:
                    if c.type != '몬스터' or c.flags.get('effect_only') or c.flags.get('no_normal') or g.tributes_needed(c.level) > 0: continue
                    if g.rule('no_special', c, p) or not g.can_place(c, p): continue
                    s = 20 + g.atk(c) / 100 + (40 if c.has('솔루나') else 0) + (10 if 'direct_attack' in getattr(c, 'rules', {}) else 0)
                    if c.has('번성충'):
                        # 지침: 번성충 몬스터는 이번 턴 결착(상대 HP 0)이 되는 경우에만 효과 대신 일반소환
                        dmg = self.lethal_damage(g, p, c)
                        s = 95 if dmg >= g.p[1 - p].hp else 0
                        key = (g.turn, ph, c.uid, s)
                        if key not in self._seen:
                            self._seen.add(key)
                            g.L(f'판단[{g.pname(p)}] {c.name} 일반소환 검토: 소환 후 직접공격 합계 {dmg} / 상대 HP {g.p[1-p].hp} → {"결착 가능, 허용" if s else "결착 불가, 보류"}', 'decision')
                    if c.has('솔루나') and any(x.has('솔루나') and x.is_monster() for x in g.monsters(p)): s = 0
                    acts.append((s, 'summon', c, None))
            for lab, s, pay in self.extra_summon_options(g, p) + self.position_options(g, p, ph):   # 제물 · 수비 소환, 표시 형식 변경
                acts.append((s, lab.split(':')[0], pay[1], pay))
            for c, e in g.options(p, ('ignition', 'quick')):
                s = e.score(g, c, p, None) if e.score else 0
                acts.append((s, 'act', c, e))
            if g.free_s(p):
                for c in g.p[p].hand:
                    if c.type == '마법' and c.d.get('subtype') in ('트리거', '신속') and not getattr(c.effects[0], 'hand_ok', False) \
                       and any(e.kind in ('resp', 'trigger', 'quick') for e in c.effects):
                        acts.append((8, 'set', c, None))
            acts = [a for a in acts if a[0] > 0]
            if not acts: return
            acts.sort(key=lambda a: -a[0])
            self.note(g, p, f'{ph} 행동', [(f'{a[1]}:{a[2].name}' + (f'#{a[3].num}' if a[1] == 'act' else ''), a[0]) for a in acts],
                      f'{acts[0][1]}:{acts[0][2].name}')
            s, kind, c, e = acts[0]
            if kind == 'summon':
                g.normal_summon(c, p); g.after_action(p)
            elif kind == 'act':
                g.act(p, c, e)
            elif kind == 'set':
                g._remove(c); g.place_spell(c, p, False); g.L(f'{g.pname(p)} 마법 1장 세트')
            else:
                self.do_extra(g, p, e)

    # ── 번식지 서치 (학습) ──
    def breeding_pick(self, g, p, cands):
        opp_skill = g.p[1 - p].skill.name if g.p[1 - p].skill else '?'
        k = sum(1 for x in g.p[p].hand if x.name in INTERFERE)
        when = '자신 턴 종료' if g.turn_player == p else '상대 턴 종료'
        key = f'{g.p[p].skill.name} vs {opp_skill}|{when}|견제패 {min(k, 3)}장'
        inter = [x for x in cands if x.name in INTERFERE]
        opts = ['견제'] + (['엔진'] if any(x.name not in INTERFERE for x in cands) else []) if inter else ['엔진']
        choice, why = BREEDING.choose(key, opts, g.rng) if len(opts) > 1 else (opts[0], '선택지 1개')
        pool = inter if choice == '견제' else [x for x in cands if x.name not in INTERFERE] or cands
        pick = max(pool, key=lambda c: self.card_pri(g, p, c))
        self.decisions.append(('breeding', key, choice))
        sts = ', '.join(f'{o} {BREEDING.stat(key, o)[0]*100:.0f}%(n={BREEDING.stat(key, o)[1]})' for o in opts)
        g.L(f'판단[{g.pname(p)}] 번식지: {key} — {sts} → {choice} ({why}) → {pick.name}', 'decision')
        return pick

    def end_game(self, g, p, winner):
        if winner is None: return
        for kind, key, choice in self.decisions:
            if kind == 'breeding': BREEDING.update(key, choice, winner == p)
        self.decisions = []

    # ── 공유 존 ──
    def use_shared(self, g, p, c, full=True):
        """빈 공유 존에 놓을지. 규칙상 언제든 고를 수 있으나(§10-2) 지침상 몬스터 존이 가득 찼을 때만 검토하고, 필요할 때만 사용:
        ① 비어 있는 공유 존의 마커가 상대 것 → 놓는 순간 마커가 뒤집혀 상대에게 페널티 (마커는 비어도 남는다, 사용자 재정 2026-09-30)
        ② 이 몬스터를 더해야 이번 턴 결착이 된다"""
        if not full: return False
        if g.shared_owner is not None and g.shared_owner != p: why = '마커가 상대 소유(상대 페널티)'
        elif self.lethal_damage(g, p, c) >= g.p[1 - p].hp: why = '이번 턴 결착에 필요'
        else: return False
        g.L(f'판단[{g.pname(p)}] 공유 존 사용 허용 — {why}', 'decision'); return True

    # ── 일반소환 확장 · 표시 형식 변경 (§5-2, §8-1) ──
    def pick_tributes(self, g, p, c):
        """일반소환에 필요한 제물을 고른다: 자신 필드의 몬스터 중 가치가 낮은 순. 제물이 모자라거나 소환할 자리가 없으면 None"""
        n = g.tributes_needed(c.level)
        if n == 0: return ()
        cands = sorted(g.release_cands(p), key=lambda x: (value(g, x), x.uid))
        if len(cands) < n: return None
        ts = tuple(cands[:n])
        if not g.free_m(p) and not any(t.zone == 'm' for t in ts): return None
        return ts

    def extra_summon_options(self, g, p):
        """무제물 공격 표시 소환 외의 일반소환 후보: 제물 소환(공격 · 수비)과 무제물 수비 표시 소환.
        반환 [(label, score, ('summon', card, tributes, pos))]. 기존 지침(번성충은 결착 시에만 · 솔루나 몬스터 1장) 유지.
        새 선택지는 학습표에 데이터가 없으므로, 휴리스틱상 타당한 경우만 후보로 내고 나머지는 VETO"""
        out = []
        if g.phase != '진행' or g.p[p].normal_summons <= 0: return out
        opp_atk = max([g.atk(m) for m in g.monsters(1 - p) if m.faceup] or [0])
        for c in g.p[p].hand:
            if c.type != '몬스터' or c.flags.get('effect_only') or c.flags.get('no_normal') or g.rule('no_special', c, p): continue
            if c.has('솔루나') and any(x.has('솔루나') and x.is_monster() for x in g.monsters(p)): continue
            ts = self.pick_tributes(g, p, c)
            if ts is None or (not ts and not g.can_place(c, p)): continue
            cost = sum(value(g, t) for t in ts)
            if ts:
                if c.has('번성충') and self.lethal_damage(g, p, c) < g.p[1 - p].hp: continue   # 지침: 번성충은 결착 시에만 일반소환
                gain = g.atk(c) - sum(g.atk(t) for t in ts if t.is_monster())
                out.append((f'소환:{c.name}', 20 + g.atk(c) / 100 - 12 * cost if gain > 0 else VETO, ('summon', c, ts, 'atk')))
            if g.def_allowed(p) and not c.has('번성충'):
                sd = (g.df(c) - g.atk(c)) / 100 - 10 - 12 * cost if g.df(c) > g.atk(c) and opp_atk > g.atk(c) else VETO
                out.append((f'수비 소환:{c.name}', sd, ('summon', c, ts, 'def')))
        return out

    def position_options(self, g, p, ph):
        """표시 형식 변경 후보 (§8-1): 정비 단계에 약한 몬스터를 수비로, 진행 단계에 공격할 수 있으면 공격으로"""
        out = []
        opp = [m for m in g.monsters(1 - p) if m.faceup]
        opp_atk = max([g.atk(m) for m in opp] or [0])
        wall = max([g.df(m) if m.pos == 'def' else g.atk(m) for m in opp] or [0])
        for m in g.monsters(p):
            if not g.can_change_pos(m, p): continue
            if m.pos == 'atk':
                s = 15 if ph == '정비' and opp_atk > g.atk(m) and g.df(m) > g.atk(m) else VETO
                out.append((f'수비 표시로:{m.name}', s, ('pos', m, None, None)))
            else:
                s = 15 if ph == '진행' and g.can_declare_attack(p) and g.atk(m) > wall else VETO
                out.append((f'공격 표시로:{m.name}', s, ('pos', m, None, None)))
        return out

    def do_extra(self, g, p, pay):
        kind, c, ts, pos = pay
        if kind == 'summon': g.normal_summon(c, p, ts, pos); g.after_action(p)
        else: g.change_position(c, p); g.triggers()   # 표시 형식 변경은 발동 · 소환이 아니므로 우선권이 넘어가지 않는다 (§6-1)

    def lethal_damage(self, g, p, extra=None):
        """이번 턴 남은 전투로 줄 수 있는 직접공격 대미지 추정 (extra: 추가로 필드에 낼 몬스터)"""
        if g.turn_player != p or g.turn == 1 or g.phase not in ('준비', '진행') or g.no_attack.get(p) == g.turn: return 0
        bonus = 100 if (extra is not None and extra.has('번성충') and p_skill(g, p) == '번성충-대발생') else 0
        tot = 0
        for m in g.monsters(p):
            if m.faceup and m.pos == 'atk' and m.attacks_made < self.max_attacks(g, m) and g.can_direct(m):
                tot += (g.atk(m) + (bonus if m.has('번성충') else 0)) * (self.max_attacks(g, m) - m.attacks_made)
        if extra is not None:
            direct_ok = 'direct_attack' in getattr(extra, 'rules', {}) or not g.monsters(1 - p)
            if direct_ok: tot += g.atk(extra) + bonus + (g.atk_bonus_if_on_field(extra, p) if hasattr(g, 'atk_bonus_if_on_field') else 0)
        return tot

    # ── 전투 ──
    def battle_phase(self, g, p):
        for _ in range(20):
            if p in g.no_attack and g.no_attack[p] == g.turn: g.L('공격 봉인 상태', 'sys'); return
            attackers = [m for m in g.monsters(p) if m.faceup and m.pos == 'atk' and not m.flags.get('no_attack')
                         and m.summon_turn <= g.turn and m.attacks_made < self.max_attacks(g, m)]
            if not attackers: return
            plan = []
            for a in attackers:
                av = g.atk(a)
                if g.can_direct(a) and not (a.flags.get('attack_all') and g.monsters(1 - p)):
                    plan.append((av + 500, a, None))
                for t in g.attack_targets(a):
                    tv = g.atk(t) if t.pos == 'atk' else g.df(t)
                    if av > tv: plan.append((200 + value(g, t) * 400 + (av - tv if t.pos == 'atk' else 0), a, t))
                    elif av == tv and t.pos == 'atk' and value(g, t) > value(g, a): plan.append((50, a, t))
            if not plan and g.rule('must_attack', p):
                plan = [(-1, a, t) for a in attackers for t in g.attack_targets(a)][:1]
            if not plan: return
            plan.sort(key=lambda x: -x[0])
            self.note(g, p, '공격', [(f'{a.name}→{t.name if t else "직접"}', s) for s, a, t in plan], f'{plan[0][1].name}→{plan[0][2].name if plan[0][2] else "직접"}')
            _, a, t = plan[0]
            g.attack(a, t)

    def max_attacks(self, g, m):
        n = 1 + m.extra_attacks
        if m.flags.get('attack_all'): n = max(n, len(g.monsters(1 - m.controller)))
        return n

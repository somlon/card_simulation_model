"""카드 구현 5차: 소원의 분수 27종 (카드 자료 2026-10-08)
자신의 메인 덱을 묘지로 보내는 것이 자원이 되는 테마 — 덱에서 묘지로 간 카드의 [유언]이 발동한다(Game.dump).

[유언] 단서 해석:
- 「(이 카드가 덱에서 묘지로 보내졌을 경우 이 효과는 발동하지 않는다.)」 — 사건의 이전 영역이 메인 · 상급 덱이면 발동하지 않는다.
- 「(이 효과는 필드에서 묘지로 보내졌을 경우, 발동하지 않는다.)」 — 이전 영역이 필드면 발동하지 않는다(발동 후 묘지로 간 마법 포함).
- 「(자신의 효과를 발동하기 위해 묘지로 보내졌을 경우, 이 효과는 발동하지 않는다.)」 — 「자신」 = 이 카드(사용자 답변 2026-10-20).
  이 카드의 효과를 발동하기 위한 코스트로 묘지로 보내졌을 때만 발동하지 않는다. 다른 카드의 코스트로 보내졌거나, 발동 후 규칙에 따라 묘지로 간 경우는 발동한다.
- 「묘지에서 이 카드와 「X」 카드 1장을 덱으로 되돌린다」 — ASSUME: 함께 되돌릴 카드가 없으면 발동하지 않는다.
재정: 「상대가 카드를 발동했을 때」(지혜의 원천 - 마도서)는 카드의 발동만 — 효과의 발동은 들지 않는다 (사용자 답변 2026-10-20, cards.opp_card_activation).
재정: 행운의 도적 2번(코인 효과 변경)은 코인의 1번(패에서 버리기)도 [유언](덱 위 2장)도 「메인 덱에서 카드 1장을 묘지로」로 바꿀 수 있다 (사용자 답변 2026-10-20).
  1번을 바꾸면 코인은 패에 남는다. AI는 메인 덱이 얇을 때(coin_replace_pick) 바꾼다.
재정: 덱 · 묘지 · 제외 존 · 패에서 소환하는 효과와 덱 · 묘지 · 제외 존에서 패에 넣는 효과는 효과 주체와 같은 이름의 자신 카드를 고를 수 없다
  (사용자 답변 · 지시 2026-10-20 — engine.Game.pickable). 희생의 의사 [유언]은 묘지의 자기 자신을 소생하지 않는다.
ASSUME: 기적의 영웅 3 · 4번은 공격력/수비력을 함께 깎으므로 둘을 합쳐 3번까지 (재정: 0에 도달하면 더는 발동할 수 없다).
"""
from engine import Effect
from cards import card, grp, best, value, own_turn, main_ok, opp_cards, last_opp_link, threat, cause_card, ev_is, VETO, field_pick, opp_card_activation
from cards2 import targets

WISH4 = ('행운', '용기', '지혜', '희생')
FIELD_Z = ('m', 's', 'shared', 'fieldz')


def deck_left(g, p): return len(g.p[p].main) + len(g.p[p].upper)


def lastwill(num, res, score=70, not_from_deck=False, not_cost=False, not_from_field=False, cond=None, cost=None, label='[유언]', threat=300):
    def cnd(g, c, p, ev):
        if not (ev_is(ev, 'to_grave') and ev['card'] is c and c.zone == 'grave'): return False
        if not_from_deck and ev['prev'] in ('main', 'upper'): return False
        ca = ev.get('cause') or ('', None)
        if not_cost and ca[0] == 'cost' and ca[1] is c: return False   # 「자신(이 카드)의 효과를 발동하기 위해」 — 이 카드의 효과의 코스트
        if not_from_field and ev['prev'] in FIELD_Z: return False
        return cond is None or cond(g, c, p, ev)
    sc = score if callable(score) else (lambda *a, s=score: s)
    return Effect(num, 'lastwill', ('grave',), cond=cnd, cost=cost, res=res, score=sc, threat=threat, label=label)


def recycle(num, group=None, not_cost=False, not_from_field=False):
    """[유언] 「묘지에서 이 카드와 「group」 카드 1장을(group=None: 다른 카드 1장을) 덱으로 되돌린다」.
    덱이 얇을 때(덱아웃 위험)만 쓸 가치가 크다. 함께 되돌릴 카드는 다시 쓰고 싶은 카드(우선순위 높은 카드)"""
    def others(g, c, p): return [x for x in g.p[p].grave if x is not c and (group is None or grp(x, group))]
    def res(g, c, p, l):
        os_ = others(g, c, p)
        if c.zone != 'grave' or not os_: return
        o = max(os_, key=lambda x: (g.p[p].ai.card_pri(g, p, x), value(g, x)))
        g.to_deck(c); g.to_deck(o); g.shuffle(p)
        g.L(f'{c} · {o} 묘지에서 덱으로')
    def sc(g, c, p, ev):
        n = deck_left(g, p)
        return 45 if n <= 8 else 20 if n <= 14 else -5
    return lastwill(num, res, sc, not_cost=not_cost, not_from_field=not_from_field,
                    cond=lambda g, c, p, ev: bool(others(g, c, p)), label='[유언] 묘지 → 덱', threat=100)


def coin_replace_pick(g, c, p):
    """행운의 도적 2번 [지속]: 자신의 「코인」 카드의 효과를 「메인 덱에서 카드 1장을 묘지로 보낸다」로 바꿀 수 있다 — 바꿀 때 보낼 카드, 안 바꾸면 None.
    AI: 메인 덱이 얇으면(12장 이하) 바꾼다 — [유언]이 있는 카드를 먼저"""
    if not (grp(c, '코인') and g.rule('coin_replace', p) and g.p[p].main and len(g.p[p].main) <= 12): return None
    return max(g.p[p].main, key=lambda x: (any(e.kind == 'lastwill' for e in x.effects), g.p[p].ai.card_pri(g, p, x)))


def coin_replaced(g, c, p):
    """코인 효과를 바꿨으면 True (메인 덱에서 고른 1장을 묘지로)"""
    x = coin_replace_pick(g, c, p)
    if x is None: return False
    g.L(f'판단[{g.pname(p)}] 행운의 도적: {c}의 효과를 「메인 덱에서 1장 묘지로」로 변경 (남은 메인 덱 {len(g.p[p].main)}장)', 'decision')
    g.deck_to_grave(p, x, f'{c.name} (변경)')
    return True


def coin_dump(g, c, p, l):
    """코인 몬스터 [유언]: 메인 덱 위에서 2장 묘지로. 행운의 도적 2번이 있으면 「메인 덱에서 카드 1장을 묘지로」로 바꿀 수 있다"""
    if not coin_replaced(g, c, p): g.dump(p, 2, c.name)


def coin_lastwill():
    return lastwill(2, coin_dump, lambda g, c, p, ev: 70 if len(g.p[p].main) >= 6 else 10, not_from_deck=True, label='[유언] 덱 위 2장 묘지로')


def discard_self(label):
    """「이 카드를 패에서 버린다」 (코인 1번). 행운의 도적 2번으로 바꾸면 코인은 패에 남고 메인 덱의 1장이 묘지로 간다 (사용자 답변 2026-10-20)"""
    def res(g, c, p, l):
        if c.zone != 'hand' or coin_replaced(g, c, p): return
        g.L(f'{c} 패에서 버림'); g.send_grave(c)
    return res


def coin_score(g, c, p, ev):
    return 60 if len(g.p[p].main) >= 6 else VETO


def own_field_to_grave(g, p, ev, exclude=None):
    """「자신 필드의 카드가 묘지로 보내졌을 때」"""
    return ev_is(ev, 'to_grave') and ev['prev'] in FIELD_Z and ev['ctrl'] == p and ev['card'] is not exclude


def low_mon_grave(g, p, lv=4):
    return [x for x in g.p[p].grave if x.is_monster() and x.level <= lv and g.can_special(x, p)]


def revive_best(g, p, cands):
    if not cands: g.L('특수소환할 몬스터 없음', 'sys'); return None
    x = max(cands, key=lambda x: (g.p[p].ai.card_pri(g, p, x), x.base_atk()))
    g.special_summon(x, p); return x


# ═══════════════════════ 몬스터 ═══════════════════════
@card('꿈이 가득한 아이')
def _(c):
    COIN = lambda x: grp(x, '코인')
    def cond2(g, c, p, ev):
        return (ev_is(ev, 'to_grave') and ev['prev'] in ('main', 'upper') and ev['card'].owner == p and COIN(ev['card'])
                and any(COIN(x) and x.is_monster() for x in g.p[p].grave))
    c.effects = [
        Effect(1, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and g.can_search(p, COIN, which=('main',)),
               res=lambda g, c, p, l: g.search(p, COIN, which=('main',), why='꿈이 가득한 아이'), score=lambda *a: 80, threat=300, label='[소환] 코인 서치'),
        Effect(2, 'trigger', ('field',), cond=cond2,
               res=lambda g, c, p, l: g.salvage(p, [x for x in g.p[p].grave if COIN(x) and x.is_monster()], '꿈이 가득한 아이'),
               score=lambda *a: 60, threat=200, label='코인 회수')]

@card('코인 - 희생의 펜던트')
def _(c):
    c.effects = [Effect(1, 'trigger', ('hand',), cond=lambda g, c, p, ev: c.zone == 'hand' and own_field_to_grave(g, p, ev),
                        res=discard_self(c.name), score=coin_score, threat=100, label='패에서 버림'), coin_lastwill()]

@card('희생의 의사')
def _(c):
    c.effects = [lastwill(2, lambda g, c, p, l: revive_best(g, p, low_mon_grave(g, p)), 75,
                          cond=lambda g, c, p, ev: bool(low_mon_grave(g, p)), label='[유언] 레벨 4 이하 소생')]

@card('코인 - 용기의 검')
def _(c):
    c.effects = [Effect(1, 'trigger', ('hand',), cond=lambda g, c, p, ev: c.zone == 'hand' and ev_is(ev, 'summon') and ev['player'] == 1 - p,
                        res=discard_self(c.name), score=coin_score, threat=100, label='패에서 버림'), coin_lastwill()]

@card('용기의 모험가')
def _(c):
    def cost(g, c, p, l):
        l.ctx['t'] = field_pick(g, p, pool=targets(g, p, g.all_field())); g.L(f'대상: {l.ctx["t"]}')
    def res(g, c, p, l):
        t = l.ctx.get('t')
        if t and g.on_field(t): g.destroy(t)
    c.effects = [lastwill(2, res, lambda g, c, p, ev: 75 if targets(g, p, opp_cards(g, p)) else VETO,
                          cond=lambda g, c, p, ev: bool(targets(g, p, g.all_field())), cost=cost, label='[유언] 파괴', threat=900)]

@card('코인 - 지혜의 서')
def _(c):
    def cond(g, c, p, ev):
        return (c.zone == 'hand' and ev_is(ev, 'activate') and ev['player'] == 1 - p
                and ev['link'].card.type == '마법' and ev['link'].eff.spell_act)
    c.effects = [Effect(1, 'trigger', ('hand',), cond=cond, res=discard_self(c.name), score=coin_score, threat=100, label='패에서 버림'), coin_lastwill()]

@card('지혜의 사서')
def _(c):
    def cost(g, c, p, l):
        l.ctx['t'] = field_pick(g, p, 'negate', targets(g, p, [x for x in g.all_field() if x.faceup])); g.L(f'대상: {l.ctx["t"]}')
    def res(g, c, p, l):
        t = l.ctx.get('t')
        if t and g.on_field(t) and g.negate_card(t, c): g.L(f'{t} 턴 종료 시까지 무효')
    c.effects = [lastwill(2, res, lambda g, c, p, ev: 40 if targets(g, p, [x for x in opp_cards(g, p) if x.faceup]) else VETO,
                          cond=lambda g, c, p, ev: bool(targets(g, p, [x for x in g.all_field() if x.faceup])), cost=cost, label='[유언] 무효', threat=600)]

@card('코인 - 행운의 네잎클로버')
def _(c):
    c.effects = [Effect(1, 'quick', ('hand',), cost=lambda g, c, p, l: g.L(f'코스트: 패에서 {c} 공개'), res=discard_self(c.name),
                        score=lambda g, c, p, ev: 45 if main_ok(g, p) and len(g.p[p].main) >= 6 else 0, threat=100, label='공개 · 버림'), coin_lastwill()]

@card('행운의 도박사')
def _(c):
    LUCK = lambda x: grp(x, '행운')
    c.effects = [lastwill(2, lambda g, c, p, l: g.search(p, LUCK, why='행운의 도박사'), 75,
                          cond=lambda g, c, p, ev: g.can_search(p, LUCK, source=c), label='[유언] 행운 서치')]

@card('행운의 도적')
def _(c):
    def cost1(g, c, p, l):
        cs = [x for x in g.field_cards(p) if x is not c]
        pick = None
        if cs:   # 묘지로 보내 [유언] · 「자신 필드의 카드가 묘지로」 트리거를 얻을 수 있는 카드, 없으면 가치가 가장 낮은 카드(1.3 이하)
            lw = [x for x in cs if any(e.kind == 'lastwill' for e in x.effects) and not x.flags.get('immune_others')]
            low = [x for x in cs if value(g, x) <= 1.3 and not x.flags.get('immune_others')]
            pool = lw or low
            if pool: pick = min(pool, key=lambda x: value(g, x))
        l.ctx['sent'] = pick is not None
        if pick is not None: g.L(f'코스트: {pick} 묘지로'); g.send_grave(pick, ('cost', c))
    c.rules = {'coin_replace': lambda g, src, p: p == src.controller}
    c.effects = [Effect(1, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c, cost=cost1,
                        res=lambda g, c, p, l: g.draw(p, 2 if l.ctx.get('sent') else 1), score=lambda *a: 80, threat=300, label='[소환] 드로우'),
                 recycle(3, '행운')]

@card('지혜의 마법사')
def _(c):
    import re
    def destroys(link):
        """그 효과 번호의 문장(「N.」 줄과 그 아래 「-」 줄들)에 카드를 파괴하는 처리가 있는가"""
        lines, on = [], False
        for x in link.card.d.get('text', '').split('\n'):
            if re.match(r'^\d+\.', x): on = x.startswith(f'{link.eff.num}.')
            if on: lines.append(x)
        return bool(re.search(r'파괴한다|파괴하고', ' '.join(lines)))
    def cond2(g, c, p, ev):
        l = last_opp_link(g, p)
        return l is not None and destroys(l) and getattr(g, 'wiz_cd', {}).get(p, -1) < g.turn
    def res2(g, c, p, l):
        g.negate(l.ctx['t'])
        if not hasattr(g, 'wiz_cd'): g.wiz_cd = {}
        g.wiz_cd[p] = g.turn + 1   # 「사용 후, 다음 턴까지 자신은 이 효과를 사용할 수 없다」 — 플레이어 단위(같은 이름 다른 장도)
    c.effects = [
        Effect(1, 'resp', ('field',), cond=lambda g, c, p, ev: last_opp_link(g, p) is not None, cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]),
               res=lambda g, c, p, l: g.negate(l.ctx['t']), score=lambda g, c, p, ev: 60 if threat(g, p) >= 600 else 0, threat=800, label='무효'),
        Effect(2, 'resp', ('field',), cond=cond2, cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]), res=res2,
               score=lambda g, c, p, ev: 65, threat=800, label='파괴 효과 무효'),
        recycle(3, '지혜')]

@card('용기의 전사')
def _(c):
    def cost1(g, c, p, l):
        l.ctx['t'] = best(g, targets(g, p, opp_cards(g, p)), p); g.L(f'대상: {l.ctx["t"]}')
    def res1(g, c, p, l):
        t = l.ctx.get('t')
        if t and g.on_field(t): g.destroy(t)
        if g.on_field(c): c.mods.append(('atk', 1000, 'turn')); g.L(f'{c} 공격력 +1000 (턴 종료 시까지)')
    c.rules = {'double_attack': lambda g, src, m: m.controller == src.controller and grp(m, '용기') and (m is src or not g.immune(m, src.controller, src))}
    c.effects = [Effect(1, 'quick', ('field',), cond=lambda g, c, p, ev: bool(targets(g, p, opp_cards(g, p))), cost=cost1, res=res1,
                        score=lambda g, c, p, ev: 65 if main_ok(g, p) or threat(g, p) >= 800 else 0, threat=1000, label='파괴 · 공격력 +1000'),
                 recycle(3, '용기')]

@card('희생의 성녀')
def _(c):
    def res1(g, c, p, l):
        revive_best(g, p, [x for x in g.p[p].grave if x.is_monster() and g.can_special(x, p)])
    def returnable(g, p, x):
        if x.zone != 'grave': return False
        if x.is_monster(): return g.can_special(x, p)
        return x.type == '필드' or bool(g.free_s(p))
    def cond2(g, c, p, ev):   # 처리할 수 없는 발동은 막는다 (특수소환 불가 몬스터 · 빈 마법 존 없음)
        return own_field_to_grave(g, p, ev, exclude=c) and g.on_field(c) and returnable(g, p, ev['card'])
    def cost2(g, c, p, l):
        l.ctx['x'] = l.ctx['ev']['card']; g.L(f'코스트: {c} 묘지로'); g.send_grave(c, ('cost', c))
    def res2(g, c, p, l):
        x = l.ctx['x']
        if x.zone != 'grave': g.L(f'{x} 묘지에 없음 — 처리 없음', 'sys'); return
        if x.is_monster():
            if g.can_special(x, p): g.special_summon(x, p)
        elif x.type == '필드' or x.d.get('subtype') == '지속':
            if x.type == '필드': g._remove(x); g.place_field(x, p); g.L(f'{x} 앞면으로 놓음')
            elif g.free_s(p): g._remove(x); g.place_spell(x, p, True); g.L(f'{x} 앞면으로 놓음')
        elif g.free_s(p):
            g._remove(x); g.place_spell(x, p, False); g.L(f'{x} 세트')
    def sc2(g, c, p, ev):
        x = ev['card'] if isinstance(ev, dict) else None
        return 30 + 20 * value(g, x) if x is not None and value(g, x) > value(g, c) * 0.8 else -5
    c.effects = [Effect(1, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c
                        and any(x.is_monster() and g.can_special(x, p) for x in g.p[p].grave), res=res1, score=lambda *a: 85, threat=500, label='[소환] 소생'),
                 Effect(2, 'trigger', ('field',), cond=cond2, cost=cost2, res=res2, score=sc2, threat=400, label='묘지로 간 카드 되살림'),
                 recycle(3, '희생')]

@card('기적의 영웅')
def _(c):
    c.flags.update(ss_by_skill_only=True, effect_only=True, no_release=True, immune_others=True, also_groups=WISH4)
    def alive(g, c): return g.atk(c) > 0 and g.df(c) > 0   # 재정: 0에 도달하면 3 · 4번을 더는 발동할 수 없다
    def shrink(g, c):
        if g.on_field(c): c.mods += [('atk', -1000, None), ('def', -1000, None)]; g.L(f'{c} 공격력/수비력 -1000 → {g.atk(c)}/{g.df(c)}')
    def res3(g, c, p, l):
        t = best(g, targets(g, p, opp_cards(g, p)), p)
        if t: g.destroy(t)
        shrink(g, c)
    def res4(g, c, p, l):
        g.negate(l.ctx['t']); shrink(g, c)
    c.effects = [
        Effect(3, 'quick', ('field',), opt=None, cond=lambda g, c, p, ev: alive(g, c) and bool(targets(g, p, opp_cards(g, p))), res=res3,
               score=lambda g, c, p, ev: (30 + 20 * max(value(g, x) for x in opp_cards(g, p))) if main_ok(g, p) else (50 if threat(g, p) >= 900 else 0),
               threat=1000, label='파괴 (공/수 -1000)'),
        Effect(4, 'resp', ('field',), opt=None, cond=lambda g, c, p, ev: alive(g, c) and last_opp_link(g, p) is not None,
               cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]), res=res4,
               score=lambda g, c, p, ev: 70 if threat(g, p) >= 700 else 0, threat=900, label='무효 (공/수 -1000)')]


# ═══════════════════════ 마법 · 필드 ═══════════════════════
@card('행운의 카드 - 조커')
def _(c):
    def res(g, c, p, l):
        out = g.dump(p, 2, c.name)
        if any(grp(x, '행운') for x in out): g.draw(p, 1)
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: bool(g.p[p].main), res=res,
                        score=lambda g, c, p, ev: 50 if len(g.p[p].main) >= 8 else 5, threat=300),
                 recycle(2, '행운', not_cost=True)]

@card('용기의 무기 - 검')
def _(c):
    def res(g, c, p, l):
        t = best(g, targets(g, p, opp_cards(g, p)), p)
        if t: g.destroy(t)
    c.effects = [Effect(1, 'quick', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: bool(targets(g, p, opp_cards(g, p))), res=res,
                        score=lambda g, c, p, ev: (25 + 15 * max(value(g, x) for x in opp_cards(g, p))) if main_ok(g, p) else (45 if threat(g, p) >= 900 else 0),
                        threat=1000),
                 recycle(2, '용기', not_cost=True)]

@card('지혜의 원천 - 마도서')
def _(c):
    def cost1(g, c, p, l):
        l.ctx['t'] = g.chain[-1]
        cs = [x for x in g.field_cards(p) if x is not c and not x.flags.get('immune_others')] or [c]
        x = min(cs, key=lambda x: (not any(e.kind == 'lastwill' for e in x.effects), value(g, x)))
        g.L(f'코스트: {x} 묘지로'); g.send_grave(x, ('cost', c))
    c.effects = [
        Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda g, c, p, ev: 40, threat=500),
        Effect(1, 'resp', ('field',), cond=lambda g, c, p, ev: opp_card_activation(g, p, c, 1) is not None, cost=cost1,
               res=lambda g, c, p, l: g.negate(l.ctx['t']), score=lambda g, c, p, ev: 60 if threat(g, p) >= 700 else 0, threat=800, label='무효'),
        recycle(2, '지혜', not_cost=True)]

@card('희생의 상징 - 펜던트')
def _(c):
    c.effects = [Effect(1, 'trigger', ('hand', 'field'), spell_act=True,
                        cond=lambda g, c, p, ev: own_field_to_grave(g, p, ev, exclude=c) and bool(low_mon_grave(g, p)),
                        res=lambda g, c, p, l: revive_best(g, p, low_mon_grave(g, p)), score=lambda *a: 65, threat=400),
                 recycle(2, '희생', not_cost=True)]

def hero_condition(c, group):
    G = lambda x: grp(x, group)
    def res1(g, c, p, l):
        if g.on_field(c): g.to_deck(c); g.L(f'{c} 덱으로'); g.shuffle(p)
        g.draw(p, 1)
    def res2(g, c, p, l):
        cands = g.search_cands(p, G)
        if not cands: return
        sumo = [x for x in cands if x.is_monster() and g.can_special(x, p)]
        x = g.p[p].ai.pick_search(g, p, cands, c.name)
        if x in sumo and (x.deck_kind() == '상급' or g.p[p].ai.card_pri(g, p, x) >= 0):
            g.special_summon(x, p)          # 상급 덱 몬스터는 특수소환이 이득(일반소환에 제물이 든다)
        else:
            g.to_hand(x); g.L(f'{x} 패에 넣음')
        g.shuffle(p)
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, res=res1, cond=lambda g, c, p, ev: deck_left(g, p) > 0,
                        score=lambda g, c, p, ev: 15 if deck_left(g, p) >= 10 else VETO, threat=200, label='덱으로 · 1드로우'),
                 lastwill(2, res2, 75, not_from_field=True, cond=lambda g, c, p, ev: g.can_search(p, G, source=c), label=f'[유언] {group} 서치/특수소환')]

for _g in WISH4:
    card(f'영웅의 조건 - {_g}')(lambda c, _g=_g: hero_condition(c, _g))

@card('소망')
def _(c):
    COIN = lambda x: grp(x, '코인')
    c.effects = [Effect(1, 'resp', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: last_opp_link(g, p) is not None and g.can_search(p, COIN),
                        res=lambda g, c, p, l: g.search(p, COIN, why='소망'), score=lambda *a: 45, threat=200),
                 recycle(2)]

@card('염원')
def _(c):
    def cond(g, c, p, ev):
        return ev_is(ev, 'added_to_hand') and ev['player'] == 1 - p and ev['card'].zone == 'hand'
    def res(g, c, p, l):
        x = l.ctx['ev']['card']; q = 1 - p
        # 상대가 고른다: 넣은 카드를 지키는 쪽(우선순위가 0보다 큰 카드)이면 「내 덱 위 2장 묘지로」, 아니면 「넣은 카드 제외」
        keep = x.zone == 'hand' and x.controller == q and g.p[q].ai.card_pri(g, q, x) > 0
        if not g.p[p].main: keep = False
        g.L(f'판단[{g.pname(q)}] 염원: {"덱 위 2장 묘지로" if keep or x.zone != "hand" else x.name + " 제외"}', 'decision')
        if keep or x.zone != 'hand': g.dump(p, 2, '염원')
        else: g.banish(x); g.L(f'{x} 제외')
    c.effects = [Effect(1, 'trigger', ('hand', 'field'), spell_act=True, cond=cond, res=res, score=lambda *a: 55, threat=500),
                 recycle(2)]

@card('기적의 전조')
def _(c):
    def res2(g, c, p, l):
        if c.zone == 'grave' and g.free_s(p): g._remove(c); g.place_spell(c, p, True); g.L(f'{c} 마법 존에 앞면으로 놓음')
    c.effects = [
        Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda g, c, p, ev: 35 if not any(x.name == c.name for x in g.spells(p)) else 0, threat=300),
        Effect(1, 'trigger', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and bool(g.p[p].main),
               res=lambda g, c, p, l: g.dump(p, 1, c.name), score=lambda g, c, p, ev: 50 if len(g.p[p].main) >= 8 else -5, threat=200, label='덱 위 1장 묘지로'),
        lastwill(2, res2, 70, not_from_field=True, cond=lambda g, c, p, ev: bool(g.free_s(p)), label='[유언] 앞면으로 놓음')]

@card('간절한 마음')
def _(c):
    c.rules = {'dump_extra': lambda g, src, p: p == src.controller}
    c.effects = [Effect(0, 'ignition', ('hand',), spell_act=True,
                        score=lambda g, c, p, ev: 0 if (g.fieldz and g.fieldz.name == c.name and g.fieldz.controller == p) else 45, threat=400),
                 recycle(2)]


# ═══════════════════════ 스킬 ═══════════════════════
@card('소원의 분수')
def _(c):
    HERO = '기적의 영웅'
    def need1(g, p):
        """1번 코스트: 묘지의 행운 · 용기 · 지혜 · 희생 카드를 각 2장 (카드 1장은 한 종류에만 쓴다 — 4종 중 2종 이상인 카드는 없다)"""
        out = []; m = 2 if g.rule('cost_double', p) else 1   # 두플리카토르: 카드 매수 2배 → 종류마다 4장 (재정 정리 2026-10-17)
        for k in WISH4:
            xs = sorted([x for x in g.p[p].grave if grp(x, k) and x not in out], key=lambda x: g.p[p].ai.card_pri(g, p, x))
            if len(xs) < 2 * m: return None
            out += xs[:2 * m]
        return out
    def hero_cands(g, p): return [x for x in g.p[p].upper if x.name == HERO and g.can_special(x, p)]
    def cost1(g, c, p, l):
        xs = need1(g, p)
        for x in xs: g.banish(x, ('cost', c))
        g.L(f'코스트: 묘지 {len(xs)}장 제외 ({", ".join(x.name for x in xs)})')
    def res1(g, c, p, l):
        cs = [x for x in g.p[p].upper if x.name == HERO and g.can_special(x, p)]
        if cs: g.special_summon(cs[0], p)
    def need2(g, p):
        """2번 코스트: 자신 필드/묘지의 행운 · 용기 · 지혜 · 희생 카드 합계 3장, 같은 종류는 1장까지.
        1번에 쓸 묘지 2장씩을 남기도록, 남는 장수가 많은 종류부터 · 묘지 카드부터 고른다. 기적의 영웅은 고르지 않는다"""
        pool = [x for x in g.p[p].grave] + [x for x in g.field_cards(p) if x.name != HERO]
        by = {k: [x for x in pool if grp(x, k)] for k in WISH4}
        ks = sorted([k for k in WISH4 if by[k]], key=lambda k: -sum(1 for x in by[k] if x.zone == 'grave'))
        m = 2 if g.rule('cost_double', p) else 1   # 두플리카토르: 합계 6장, 같은 종류는 2장까지로 본다 (재정 정리 2026-10-17 — 종류 상한 2배는 ASSUME)
        out = []
        for k in ks:
            xs = sorted([x for x in by[k] if x not in out], key=lambda x: (x.zone != 'grave', g.p[p].ai.card_pri(g, p, x), value(g, x)))
            out += xs[:min(m, 3 * m - len(out))]
            if len(out) >= 3 * m: break
        return out if len(out) >= 3 * m and len({k for k in WISH4 for x in out if grp(x, k)}) >= 3 else None
    def cost2(g, c, p, l):
        xs = need2(g, p)
        for x in xs: g.banish(x, ('cost', c))
        g.L(f'코스트: {len(xs)}장 제외 ({", ".join(x.name for x in xs)})')
    def res2(g, c, p, l):   # 「상대 필드의 카드 1장을 묘지로 보낸다」 — 대상 지정이 없으므로 처리 시 고른다
        t = best(g, targets(g, p, opp_cards(g, p)), p)
        if t: g.L(f'{t} 묘지로'); g.send_grave(t)
    def sc2(g, c, p, ev):
        ts = targets(g, p, opp_cards(g, p))
        if not ts: return VETO
        hero_ready = need1(g, p) is not None and hero_cands(g, p)
        base = 25 + 15 * max(value(g, x) for x in ts) - (25 if hero_ready else 0)
        return base if main_ok(g, p) else (base if threat(g, p) >= 900 else 0)
    c.effects = [
        Effect(1, 'quick', ('skill',), cond=lambda g, c, p, ev: need1(g, p) is not None and bool(hero_cands(g, p)), cost=cost1, res=res1,
               score=lambda g, c, p, ev: 95 if main_ok(g, p) else (70 if threat(g, p) >= 900 or not own_turn(g, p) else 0), threat=1200, label='기적의 영웅 특수소환'),
        Effect(2, 'quick', ('skill',), cond=lambda g, c, p, ev: need2(g, p) is not None and bool(targets(g, p, opp_cards(g, p))), cost=cost2, res=res2,
               score=sc2, threat=1000, label='상대 카드 묘지로')]

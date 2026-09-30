"""카드 구현 3차: 솔루나 월영잠행 · 월영암수 + 흑월침식 12종 (흑월침식 텍스트는 솔루나_통합본_v1 기준)"""
from engine import Effect
from cards import card, best, value, own_turn, main_ok, opp_cards, last_opp_link, threat, cause_card, ev_is, mon, SIA, CIEL, arts, own_mon, search_sc
from cards2 import targets


def free(g, p, c):
    """달그림자에 잠식된 태양 2번: 「시엘」 카드의 효과 코스트 면제"""
    return g.rule('ciel_cost_free', p, c)

def pay(g, p, c, fn):
    if free(g, p, c): g.L(f'코스트 면제 ({c.name} — 스킬 2번)', 'sys'); return None
    return fn()

def bounce_opp(g, p, n=1):
    for _ in range(n):
        t = best(g, targets(g, p, opp_cards(g, p)), p, 'bounce')
        if t: g.L(f'{t} 덱으로'); g.to_deck(t)


@card('시엘 아츠 - 월영잠행')
def _(c):
    def res1(g, c, p, l):
        ms = own_mon(g, p, CIEL)
        if ms and g.change_control(ms[0], 1 - p):
            m = ms[0]; m.flags['return_at_end'] = g.turn
            m.end_return = lambda g2, x: x.controller != x.owner and g2.change_control(x, x.owner) and g2.L(f'{x} 컨트롤 복귀', 'sys')
            g.L(f'{m} 턴 종료 시까지 상대 필드로')
        bounce_opp(g, p)
    def res2(g, c, p, l):
        cs = [m for m in g.monsters(1 - p) if CIEL(m) and m.owner == p]
        if cs: g.change_control(cs[0], p); g.L(f'{cs[0]} 되찾음')
        t = best(g, targets(g, p, opp_cards(g, p)), p)
        if t: g.destroy(t)
    arts(c, lambda g, c, p, ev: bool(own_mon(g, p, CIEL)) and bool(opp_cards(g, p)), None, res1,
         lambda g, c, p: mon(g, SIA, p) and bool(opp_cards(g, p)), res2, sc1=35, sc2=40)

@card('시엘 아츠 - 월영암수')
def _(c):
    def cost1(g, c, p, l):
        def f():
            m = own_mon(g, p, CIEL)[0]; g.L(f'코스트: {m} 상대 패로'); g.to_hand(m, ('cost', c), p=1 - p); m.owner_tmp = True
        return pay(g, p, c, f)
    def res1(g, c, p, l):
        hand = g.p[1 - p].hand
        for _ in range(min(2, len(hand))):
            x = g.p[1 - p].ai.pick_discard(g, 1 - p, hand); g.to_deck(x); g.L(f'상대 패 {x.name} 덱으로')
    def res2(g, c, p, l):
        if g.p[1 - p].grave: t = best(g, g.p[1 - p].grave, p, 'banish_grave'); g.banish(t); g.L(f'상대 묘지 {t} 제외')
    arts(c, lambda g, c, p, ev: (bool(own_mon(g, p, CIEL)) or free(g, p, c)) and len(g.p[1 - p].hand) >= 2, cost1, res1,
         lambda g, c, p: mon(g, SIA) and bool(g.p[1 - p].grave), res2, sc1=30, sc2=10)


# ─────────── 흑월침식 (텍스트: 솔루나_통합본_v1 — v3 문서 미수록, 2026-09-23 복원) ───────────
@card('솔루나 시아 - 박혼')
def _(c):
    c.effects = [Effect(2, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and bool(targets(g, p, opp_cards(g, p))),
                        res=lambda g, c, p, l: bounce_opp(g, p), score=lambda *a: 90, threat=900, label='[소환] 덱 바운스')]

@card('솔루나 시엘 - 쉐도우 오버플로')
def _(c):
    def mod(g, src, x):
        p = src.controller
        if x.controller == p or not x.is_monster() or g.immune(x, p): return 0
        return -800 if mon(g, SIA, p) else 0
    c.atk_mod = mod
    c.effects = [
        Effect(2, 'quick', ('field',), cond=lambda g, c, p, ev: bool(targets(g, p, opp_cards(g, p))), res=lambda g, c, p, l: bounce_opp(g, p),
               score=lambda g, c, p, ev: 70 if main_ok(g, p) or threat(g, p) >= 800 else 0, threat=900, label='덱 바운스'),
        Effect(3, 'lastwill', ('grave',), cond=lambda g, c, p, ev: ev_is(ev, 'to_grave') and ev['card'] is c and g.can_special(c, p),
               res=lambda g, c, p, l: c.zone == 'grave' and g.special_summon(c, p), score=lambda *a: 90, threat=500, label='[유언] 자기 소생')]

@card('솔루나 시아 - 쉐도우 임프리스')
def _(c):
    c.atk_mod = lambda g, src, x: 3000 if x is src and mon(g, CIEL) else 0
    c.rules = {'immune': lambda g, src, x, by: x is src and mon(g, CIEL)}
    def res2(g, c, p, l):
        g.negate(l.ctx['t']); bounce_opp(g, p)
    c.effects = [
        Effect(2, 'resp', ('field',), cond=lambda g, c, p, ev: last_opp_link(g, p) is not None,
               cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]), res=res2, score=lambda g, c, p, ev: 75 if threat(g, p) >= 500 else 0, threat=1000, label='무효 + 바운스'),
        Effect(3, 'trigger', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'activate') and ev['player'] == p and ev['link'].card.has('시엘') and bool(targets(g, p, opp_cards(g, p))),
               res=lambda g, c, p, l: bounce_opp(g, p), score=lambda *a: 80, threat=800, label='시엘 발동 시 바운스')]

@card('시엘 아츠 - 잠식된 달그림자의 힘')
def _(c):
    def res1(g, c, p, l):
        for _ in range(2):
            cs = [x for x in g.p[p].main if CIEL(x) and g.can_special(x, p)]
            if cs: g.special_summon(cs[0], p)
        g.shuffle(p)
    def res2(g, c, p, l):
        cs = [x for x in g.p[p].upper if CIEL(x) and g.can_special(x, p)]
        if cs: g.special_summon(max(cs, key=lambda x: x.level), p)
    c.effects = [
        Effect(1, 'quick', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: any(CIEL(x) for x in g.p[p].main) and g.can_special(c, p), res=res1,
               score=lambda g, c, p, ev: 70 if main_ok(g, p) else 0, threat=500),
        Effect(2, 'trigger', ('grave',), cond=lambda g, c, p, ev: ev_is(ev, 'leave_field') and ev['ctrl'] == p and SIA(ev['card'])
               and any(CIEL(x) for x in g.p[p].upper), cost=lambda g, c, p, l: pay(g, p, c, lambda: g.banish(c, ('cost', c))),
               res=res2, score=lambda *a: 80, threat=600)]

@card('시엘 아츠 - 홀로 선 달')
def _(c):
    def res1(g, c, p, l):
        g.damage(p, 1000, '자해 (홀로 선 달)')   # ASSUME D-2: 효과이므로 코스트 면제 대상 아님
        cs = [x for x in g.deck_cards(p) if CIEL(x) and g.can_special(x, p) and not x.flags.get('effect_only')]
        if cs: g.special_summon(max(cs, key=lambda x: x.level), p)
    c.effects = [
        Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda *a: 45, threat=400),
        Effect(1, 'quick', ('field',), cond=lambda g, c, p, ev: g.p[p].hp > 1000 and any(CIEL(x) for x in g.deck_cards(p)) and bool(g.free_m(p)),
               res=res1, score=lambda g, c, p, ev: 40 if main_ok(g, p) and g.p[p].hp > 2500 else 0, threat=300),
        Effect(2, 'trigger', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'leave_field') and ev['dest'] == 'deck' and cause_card(ev) is not None
               and cause_card(ev).controller == p and cause_card(ev).has('시아'), res=lambda g, c, p, l: g.heal(p, 2000), score=lambda *a: 80, threat=200),
        Effect(3, 'trigger', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'leave_field') and ev['ctrl'] == p and CIEL(ev['card']),
               res=lambda g, c, p, l: search_sc(g, p, lambda x: x.has('시엘'), '홀로 선 달'), score=lambda *a: 75, threat=200)]

@card('시엘 아츠 - 진월광무')
def _(c):
    def snap(g, c, p, l): l.ctx['hi'] = mon(g, lambda x: CIEL(x) and x.level >= 8)
    def res1(g, c, p, l):
        bounce_opp(g, p, 2)
        if l.ctx['hi']: search_sc(g, p, lambda x: x.has('시엘'), '진월광무')
    def cost2(g, c, p, l):
        if free(g, p, c): g.L('코스트 면제 (진월광무 2번)', 'sys'); return
        x = [x for x in g.p[p].hand if CIEL(x)][0]; g.to_deck(x, ('cost', c)); g.banish(c, ('cost', c))
    c.effects = [
        Effect(1, 'quick', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: any(x.has('시엘') and x is not c for x in g.all_field()) and bool(targets(g, p, opp_cards(g, p))),
               cost=snap, res=res1, score=lambda g, c, p, ev: 30 + 20 * min(2, len(opp_cards(g, p))) if main_ok(g, p) else (40 if threat(g, p) >= 900 else 0), threat=1000),
        Effect(2, 'quick', ('grave',), cond=lambda g, c, p, ev: free(g, p, c) or any(CIEL(x) for x in g.p[p].hand), cost=cost2,
               res=lambda g, c, p, l: search_sc(g, p, lambda x: x.has('시엘'), '진월광무 2번'), score=lambda g, c, p, ev: 30 if main_ok(g, p) else 0, threat=200)]

@card('시엘 아츠 - 메모리 오브 솔루나')
def _(c):
    def res(g, c, p, l):
        bounce_opp(g, p)
        g.salvage(p, [x for x in g.p[p].grave if x is not c], '메모리 오브 솔루나')
    e = Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: mon(g, SIA) and mon(g, CIEL), res=res,
               score=lambda *a: 45, threat=700)
    e.no_resp = True
    c.effects = [e]

@card('흑월침식 - 약일태동')
def _(c):
    def snap(g, c, p, l): l.ctx['ciel'] = mon(g, CIEL)
    def res1(g, c, p, l):
        for _ in range(2):
            if g.p[p].hand: d = g.p[p].ai.pick_discard(g, p, g.p[p].hand); g.send_grave(d); g.L(f'{d} 버림')
        for _ in range(2): search_sc(g, p, lambda x: x.has('시엘'), '약일태동')
        if l.ctx['ciel']: g.draw(p, 1)
    def cost2(g, c, p, l):
        g.banish(c, ('cost', c)); x = [x for x in g.p[p].hand if CIEL(x)][0]; g.to_deck(x, ('cost', c))
    c.effects = [
        Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: len(g.p[p].hand) >= 3, cost=snap, res=res1,
               score=lambda *a: 40, threat=300),
        Effect(2, 'ignition', ('grave',), cond=lambda g, c, p, ev: main_ok(g, p) and any(CIEL(x) for x in g.p[p].hand) and any(CIEL(x) for x in g.p[p].upper),
               cost=cost2, res=lambda g, c, p, l: g.search(p, CIEL, which=('upper',), why='약일태동 2번'), score=lambda *a: 25, threat=200)]

@card('흑월침식 - 저문 달의 세계')
def _(c):
    def snap(g, c, p, l):
        l.ctx['ciel'] = mon(g, CIEL)
        fields = [x for x in g.deck_cards(p) if x.type == '필드']
        l.ctx['mode'] = 'field' if fields and not (g.fieldz and g.fieldz.controller == p) else 'search'
    def res(g, c, p, l):
        if l.ctx['mode'] == 'field':
            f = [x for x in g.deck_cards(p) if x.type == '필드']
            if f: x = g.p[p].ai.pick_search(g, p, f, '저문 달의 세계'); g._remove(x); g.place_field(x, p); g.L(f'덱에서 {x} 발동')
        else: search_sc(g, p, lambda x: x.has('시엘'), '저문 달의 세계')
        if l.ctx['ciel']: g.draw(p, 1)
    c.effects = [Effect(1, 'quick', ('hand', 'field'), spell_act=True, cost=snap, res=res, score=lambda g, c, p, ev: 45 if main_ok(g, p) else 0, threat=300)]

def field_swap():
    def res3(g, c, p, l):
        f = [x for x in g.deck_cards(p) if x.type == '필드' and x.has('시엘') and x.name != c.name]
        if f: x = g.p[p].ai.pick_search(g, p, f, '필드 교체'); g._remove(x); g.place_field(x, p); g.L(f'덱에서 {x} 발동')
    return Effect(3, 'quick', ('field',), cond=lambda g, c, p, ev: any(x.type == '필드' and x.has('시엘') and x.name != c.name for x in g.deck_cards(p)),
                  cost=lambda g, c, p, l: pay(g, p, c, lambda: g.to_deck(c, ('cost', c))), res=res3,
                  score=lambda g, c, p, ev: 10 if main_ok(g, p) else 0, threat=200, label='필드 교체')

@card('시엘 아츠 - 흑색 태양')
def _(c):
    def cost2(g, c, p, l):
        l.ctx['t'] = g.chain[-1]
        pay(g, p, c, lambda: g.to_deck([m for m in g.monsters(p) if CIEL(m) and m.faceup][0], ('cost', c)))
    def res2(g, c, p, l):
        t = l.ctx['t']; g.negate(t)
        if g.on_field(t.card): g.to_deck(t.card); g.L(f'{t.card} 덱으로')
    c.effects = [
        Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda g, c, p, ev: 0 if (g.fieldz and g.fieldz.controller == p) else 55, threat=600),
        Effect(1, 'quick', ('field',), cond=lambda g, c, p, ev: any(CIEL(x) and g.can_special(x, p) for x in g.p[p].main),
               res=lambda g, c, p, l: (lambda cs: cs and g.special_summon(cs[0], p))([x for x in g.p[p].main if CIEL(x) and g.can_special(x, p)]),
               score=lambda g, c, p, ev: 65 if main_ok(g, p) else 0, threat=500),
        Effect(2, 'resp', ('field',), cond=lambda g, c, p, ev: last_opp_link(g, p) is not None and (free(g, p, c) or mon(g, CIEL, p)),
               cost=cost2, res=res2, score=lambda g, c, p, ev: 65 if threat(g, p) >= 600 else 0, threat=900, label='무효 + 덱'),
        field_swap()]

@card('시엘 아츠 - 만월')
def _(c):
    c.rules = {'immune': lambda g, src, x, by: SIA(x) and x.controller == src.controller and mon(g, CIEL, src.controller),
               'no_battle_target': lambda g, src, x: SIA(x) and x.controller == src.controller and mon(g, CIEL, src.controller)}
    c.effects = [
        Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda g, c, p, ev: 0 if (g.fieldz and g.fieldz.controller == p) else 50, threat=600),
        Effect(2, 'quick', ('field',), cond=lambda g, c, p, ev: free(g, p, c) or bool(own_mon(g, p, CIEL)),
               cost=lambda g, c, p, l: pay(g, p, c, lambda: g.to_deck(own_mon(g, p, CIEL)[0], ('cost', c))),
               res=lambda g, c, p, l: search_sc(g, p, lambda x: x.has('시엘'), '만월'), score=lambda g, c, p, ev: 30 if main_ok(g, p) else 0, threat=200),
        field_swap()]

@card('달그림자에 잠식된 태양')
def _(c):
    c.flags['unnegatable'] = True
    def lim(g, src, x, p):
        return p == src.controller and x.is_monster() and SIA(x) and any(SIA(m) for m in g.monsters(p))
    c.rules = {'no_special': lim, 'ciel_cost_free': lambda g, src, p, card: p == src.controller and card.has('시엘')}
    def res1(g, c, p, l):
        cs = [x for x in g.p[p].main + g.p[p].hand if x.name == '솔루나 시아 - 박혼']
        if cs:
            x = cs[0]; g._remove(x); g.place_monster(x, p, 'atk'); x.flags['no_pos_change'] = True
            g.L(f'필드에 {x}을(를) 공격 표시로 놓음 (ASSUME D-3: 메인 덱에서, 소환 아님)'); g.shuffle(p)
    def res3(g, c, p, l):
        g.damage(p, 1000, '자해 (달그림자에 잠식된 태양)')
        cs = [x for x in g.p[p].hand + g.p[p].main + g.p[p].grave + g.p[p].banish if SIA(x) and g.can_special(x, p)]
        if cs:
            x = sorted(cs, key=lambda x: (x.name != '솔루나 시아 - 박혼', -x.level))[0]
            g.special_summon(x, p, 'atk')   # ASSUME D-3: 「소환한다」 = 특수소환
    c.effects = [
        Effect(1, 'trigger', ('skill',), mandatory=True, cond=lambda g, c, p, ev: ev_is(ev, 'game_start'), res=res1, threat=0),
        Effect(3, 'trigger', ('skill',), mandatory=True, opt=None,
               cond=lambda g, c, p, ev: ev_is(ev, 'leave_field') and ev['ctrl'] == p and SIA(ev['card']), res=res3, threat=0, label='시아 재배치')]

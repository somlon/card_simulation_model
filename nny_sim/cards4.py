"""카드 구현 4차: 세리 (기본 v8 + 확장 데쿠마 v2, 18종)
세금 = 덱 위에서 카드 제외. 승리 플랜은 상대 덱아웃.
덱 위에서 제외 (규칙 명세서 §6-7):
- 「메인 덱의 위에서부터」 · 「상급 덱의 위에서부터」는 그 덱만. 「제외할 카드가 부족할 경우 … 대신 제외한다」 문구가 있을 때만 다른 덱에서 채운다.
- 「덱의 위에서부터」(메인/상급 미지정)는 메인 · 상급 중 한쪽을 골라 그 덱에서 제외한다.
  고르는 쪽은 문장의 주어: 「상대의 덱의 위에서부터 … 제외한다」는 효과를 쓴 플레이어, 「그 플레이어는 자신의 덱」 · 「서로 자신의 덱」은 덱 주인.
재정 (사용자 답변 2026-10-20):
- 델레가토르 1번: 상대가 대신 낼 수 있는 모든 코스트를 상대가 낸다. 상대가 대신 낼 수 없으면 그 효과는 발동할 수 없다.
  덱 코스트는 상대 덱이 모자라도 발동할 수 있고, 대신 지불하다 모자라면 상대의 덱이 음수가 되어 패배한다.
  → 엔진 공통 규칙(engine.Game.cost_payer · transfer_ok · pay_deck_cost, 코스트 종류는 카드 텍스트 — cards.parse_cost).
  이 파일의 코스트 함수는 지불자를 엔진에서 받는다: 덱 위 제외(tax_cost) · 제외 존→덱(return_cost — 세리 [유언] · 프로쿠라토르 2번).
- 세제 2 · 3번(「서로가 … 제외하고 발동」)은 상대도 발동할 수 있다(발동한 플레이어가 자신의 덱으로 코스트를 내고 드로우) — 엔진 Effect.either_player.
- 이탈세 2번 「필드에서 벗어나게 하는 효과」 = 필드에 있는 카드를 필드가 아닌 위치로 이동시키는 효과(말 그대로) — cards.moves_off_field.
- 두플리카토르(코스트 2배)는 카드 매수로 지불하는 모든 코스트(재정 정리 2026-10-17 — dupcost.py). 프로쿠라토르 2번 「제외 존의 카드를 전부」는 매수가 없어 그대로.
"""
import math
from engine import Effect
from cards import card, best, value, own_turn, main_ok, opp_cards, last_opp_link, threat, cause_card, ev_is, VETO, moves_off_field
from cards2 import targets

SERI = lambda x: x.has('세리') and x.type == '몬스터'
SERI3 = lambda x: SERI(x) and x.level == 3
DECUMA = lambda x: x.has('데쿠마')

def tax_n(g, p, n):
    """세리식 덱 코스트의 매수: 두플리카토르면 2배"""
    return n * 2 if g.rule('cost_double', p) else n

def tax_cost(g, p, n, why, kind='mill', deck='main'):
    """세리식 코스트: 덱 위 n장 제외(deck: 'main' 메인 덱 · 부족분 상급 덱 / 'upper' 그 반대). 두플리카토르면 2배,
    델레가토르면 상대가 대신 지불(모자라면 상대 패배 — engine.Game.pay_deck_cost)"""
    k = tax_n(g, p, n)
    if k != n: g.L(f'두플리카토르: 코스트 {k}장으로', 'sys')
    return g.pay_deck_cost(p, k, deck, why) or True   # 「메인 덱의 위에서부터 … 부족하면 상급 덱에서 대신」

def return_cost(g, p, k):
    """세리식 「자신의 제외 존에서 카드를 k장 골라 자신의 덱으로 되돌리고 발동」 코스트의 (지불자, 매수).
    두플리카토르면 2배, 델레가토르면 상대가 자신의 제외 존에서 대신 지불 (engine.Game.cost_payer)"""
    if g.rule('cost_double', p): k *= 2
    return g.cost_payer(p), k

def seri_lastwill():
    def need(g, p): return return_cost(g, p, 1 if g.rule('seri_lw_one', p) else 3)   # 세 - 아이라리움 2번: 1장
    def cond(g, c, p, ev):
        if not (ev_is(ev, 'to_grave') and ev['card'] is c): return False
        q, k = need(g, p)
        return len(g.p[q].banish) >= k and any(SERI(x) and g.can_special(x, p) for x in g.p[p].main)
    def cost(g, c, p, l):
        q, k = need(g, p)
        if q != p: g.L(f'델레가토르: 코스트를 {g.pname(q)}가 대신 지불', 'sys')
        back = sorted(g.p[q].banish, key=lambda x: (not SERI(x), -g.p[q].ai.card_pri(g, q, x)))[:k]
        for x in back: g.p[q].banish.remove(x); x.zone = None; g._to_deck_raw(x)
        g.L(f'코스트: {g.pname(q)} 제외 존 {len(back)}장 덱으로'); g.shuffle(q)
    def res(g, c, p, l):
        cs = [x for x in g.p[p].main if SERI(x) and g.can_special(x, p)]
        if cs: g.special_summon(g.p[p].ai.pick_search(g, p, cs, '세리 유언'), p)
    e = Effect(2, 'lastwill', ('grave',), cond=cond, cost=cost, res=res,
               score=lambda *a: 80, threat=400, label='[유언] 제외 존 → 덱 (코스트) + 세리 특수소환')
    e.cost_payable = lambda g, c, p, q: len(g.p[q].banish) >= need(g, p)[1]   # 델레가토르: 상대 제외 존에서 대신 (engine.Game.transfer_ok)
    return e

def spell_lastwill(num=2):
    """마법 공통 [유언]: 상대에 의해 묘지로 → 자신 덱 위 3장 제외(코스트)하고 이 카드를 패로"""
    return Effect(num, 'lastwill', ('grave',),
        cond=lambda g, c, p, ev: ev_is(ev, 'to_grave') and ev['card'] is c and cause_card(ev) is not None and cause_card(ev).controller == 1 - p,
        cost=lambda g, c, p, l: tax_cost(g, p, 3, '유언 코스트') and None, res=lambda g, c, p, l: c.zone == 'grave' and (g.to_hand(c), g.L(f'{c} 패로')),
        score=lambda *a: 60, threat=200, label='[유언] 패로 복귀')

@card('세리 - 델레가토르')
def _(c):
    c.rules = {'cost_transfer': lambda g, src, p: p == src.controller}
    c.effects = [seri_lastwill()]

@card('세리 - 두플리카토르')
def _(c):
    c.rules = {'cost_double': lambda g, src, p: True}
    c.effects = [seri_lastwill()]

@card('세리 - 엑삭토르')
def _(c):
    c.effects = [Effect(1, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c,
                        res=lambda g, c, p, l: (g.mill(p, 5, None, '엑삭토르'), g.mill(1 - p, 5, None, '엑삭토르')),   # 「서로 자신의 덱」: 각자 메인 · 상급 중 선택 (§6-7)
                        score=lambda g, c, p, ev: 70 if len(g.p[1 - p].main) <= len(g.p[p].main) + 10 else 30, threat=600, label='서로 5장 제외'), seri_lastwill()]

@card('세리 - 릭토르')
def _(c):
    c.rules = {'immune': lambda g, src, x, by: x is not src and x.controller == src.controller and by != src.controller and g.on_field(x)}
    c.effects = [seri_lastwill()]

@card('세리 - 데쿠마누스')
def _(c):
    def on_ev(g, src, ev):
        if ev['kind'] == 'draw' and ev['player'] == 1 - src.controller: g.mill(1 - src.controller, 2, 'main', '데쿠마누스')   # 「메인 덱의 위에서부터」: 메인 덱만
    c.on_event = on_ev
    c.effects = [seri_lastwill()]

@card('세리 - 멘소르')
def _(c):
    def res(g, c, p, l):
        a, b = len(g.p[p].main), len(g.p[1 - p].main)
        if a != b: big = p if a > b else 1 - p; g.mill(big, abs(a - b), 'main', '멘소르')
    c.effects = [Effect(1, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c,
                        # 메인 덱이 많은 쪽을 같은 매수까지 깎는다. 내 덱이 더 많으면 내 덱을 깎게 되므로(제외에 반응하는 카드 없음 — 손해뿐) 쓰지 않는다
                        res=res, score=lambda g, c, p, ev: 80 if len(g.p[1 - p].main) > len(g.p[p].main) else VETO, threat=500), seri_lastwill()]

def alt_normal(c, can, pay):
    c.alt_normal = (can, pay)

@card('치프 세리 - 프로쿠라토르')
def _(c):
    alt_normal(c, lambda g, p: sum(1 for x in g.p[p].grave if SERI3(x)) >= 3,
               lambda g, p: [g.banish(x, ('cost', c)) for x in [x for x in g.p[p].grave if SERI3(x)][:3]])
    def cost2(g, c, p, l):
        q = g.cost_payer(p)   # 델레가토르면 상대가 자신의 제외 존 전부를 자신의 덱으로 (engine.Game.cost_payer)
        if q != p: g.L(f'델레가토르: 코스트를 {g.pname(q)}가 대신 지불', 'sys')
        xs = list(g.p[q].banish); l.ctx['n'] = len(xs)
        for x in xs: g.p[q].banish.remove(x); x.zone = None; g._to_deck_raw(x)
        g.shuffle(q); g.L(f'코스트: {g.pname(q)} 제외 존 {len(xs)}장 덱으로')
    e2 = Effect(2, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and bool(g.p[g.cost_payer(p)].banish),
                cost=cost2, res=lambda g, c, p, l: g.mill(1 - p, l.ctx['n'], None, '프로쿠라토르', chooser=p), score=lambda *a: 90, threat=900)
    e2.cost_payable = lambda g, c, p, q: bool(g.p[q].banish)
    c.effects = [
        e2,
        Effect(3, 'lastwill', ('grave',), cond=lambda g, c, p, ev: ev_is(ev, 'to_grave') and ev['card'] is c and any(SERI3(x) for x in g.p[p].grave),
               res=lambda g, c, p, l: [g.special_summon(x, p) for x in [x for x in g.p[p].grave if SERI3(x)][:2]], score=lambda *a: 85, threat=500)]

@card('치프 세리 - 호레아리우스')
def _(c):
    def pay(g, p):
        xs = [x for x in g.p[p].banish if SERI3(x)][:2]
        for x in xs: g.p[p].banish.remove(x); x.zone = None; g._to_deck_raw(x)
        g.shuffle(p)
    alt_normal(c, lambda g, p: sum(1 for x in g.p[p].banish if SERI3(x)) >= 2, pay)
    c.rules = {'banish_immune': lambda g, src, p: p == src.controller}
    c.effects = [Effect(2, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and len(g.p[p].banish) >= 5,
                        res=lambda g, c, p, l: g.mill(1 - p, len(g.p[p].banish) // 5, None, '호레아리우스', chooser=p), score=lambda *a: 90, threat=800)]

@card('소환세')
def _(c):
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: any(SERI(x) for x in g.p[p].main),
                        res=lambda g, c, p, l: g.search(p, SERI, which=('main',), why='소환세'), score=lambda *a: 55, threat=300), spell_lastwill()]

@card('인지세')
def _(c):
    def res(g, c, p, l):
        """2026-10-08 텍스트: 상대가 「메인 덱 위 5장 제외(부족분은 상급 덱에서)」와 「그 카드 무효」 중 고른다.
        상대 판단(휴리스틱): 덱이 넉넉하고(제외 후 10장 이상 남음) 무효화될 효과의 위협도가 600 이상이면 제외, 아니면 무효"""
        t = l.ctx['t']; q = 1 - p
        left = len(g.p[q].main) + len(g.p[q].upper)
        if t in g.chain and not t.negated and left - 5 >= 10 and t.eff.threat >= 600:
            g.L(f'판단[{g.pname(q)}] 인지세: 덱 {left}장, 위협도 {t.eff.threat} → 5장 제외 선택', 'decision')
            g.mill(q, 5, 'main', '인지세', fallback=True)
        else:
            g.L(f'판단[{g.pname(q)}] 인지세: 덱 {left}장 → 무효 선택', 'decision'); g.negate(t)
    e = Effect(1, 'resp', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: last_opp_link(g, p) is not None,
               cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]), res=res,
               score=lambda g, c, p, ev: 55 if threat(g, p) >= 500 or len(g.p[1 - p].main) + len(g.p[1 - p].upper) <= 12 else 25, threat=700)
    c.effects = [e, spell_lastwill()]

@card('이탈세')
def _(c):
    def cond2(g, c, p, ev):
        l = last_opp_link(g, p)   # 상대가 자신 필드의 카드를 필드가 아닌 위치로 이동시키는 효과의 발동을 선언했을 때 (사용자 답변 2026-10-20)
        return l is not None and moves_off_field(g, l, p)
    def res2(g, c, p, l):
        t = l.ctx['t']; q = t.player
        t.replaced = lambda g2, tl: g2.mill(q, 5, 'upper', '이탈세로 변경된 효과', fallback=True)
        g.L(f'{t.card}의 효과를 「덱 위 5장 제외」로 변경'); c.flags['lw_mode'] = None
    e4 = Effect(4, 'lastwill', ('grave',), cond=lambda g, c, p, ev: ev_is(ev, 'to_grave') and ev['card'] is c,
                res=lambda g, c, p, l: g.mill(1 - p, 10, None, '이탈세 유언', chooser=p), score=lambda *a: 75, threat=600, label='[유언] 상대 10장 제외')
    e4.no_resp = True
    e3 = spell_lastwill(3)
    e3.score = lambda g, c, p, ev: 0 if len(g.p[1 - p].main) + len(g.p[1 - p].upper) <= 14 else 60   # 3 · 4번 택1: 상대 덱이 적으면 4번
    c.effects = [Effect(2, 'resp', ('hand', 'field'), spell_act=True, cond=cond2, cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]), res=res2,
                        score=lambda *a: 70, threat=800), e3, e4]
    c.flags['exclusive_nums'] = (3, 4)

@card('취득세')
def _(c):
    def on_ev(g, src, ev):
        if ev['kind'] == 'summon' and ev['how'] == 'special': g.mill(ev['player'], 2, None, '취득세')
    c.on_event = on_ev
    c.effects = [Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda *a: 45, threat=500), spell_lastwill()]

@card('스키푸스')
def _(c):
    def cost(g, c, p, l):
        n = 2 * (2 if g.rule('cost_double', p) else 1)
        xs = [x for x in g.p[p].banish if x.has('세리')][:n]
        for x in xs: g.p[p].banish.remove(x); x.zone = None; g._to_deck_raw(x)
        g.shuffle(p); g.L(f'코스트: 제외 존 세리 {len(xs)}장 덱으로')
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True,
        cond=lambda g, c, p, ev: sum(1 for x in g.p[p].banish if x.has('세리')) >= 2 * (2 if g.rule('cost_double', p) else 1),
        cost=cost, res=lambda g, c, p, l: g.search(p, lambda x: SERI(x) or DECUMA(x), which=('main',), why='스키푸스'),
        score=lambda *a: 50, threat=300), spell_lastwill()]

@card('아나보케')
def _(c):
    def res(g, c, p, l):
        g.decuma_skip = g.turn; g.decuma_double = p
        g.L('이 턴 데쿠마 1번의 제외 무효, 다음 자신 턴 종료 시 2배')
    c.effects = [Effect(1, 'quick', ('hand', 'field'), spell_act=True,
        cond=lambda g, c, p, ev: any(l.card.name == '데쿠마' and l.eff.num == 1 for l in g.chain),   # 「데쿠마」 1번 발동에 대응해서만
        res=res, score=lambda g, c, p, ev: 30 if own_turn(g, p) and len(g.p[p].main) <= 12 else 0, threat=100), spell_lastwill()]

@card('세 - 아이라리움')
def _(c):
    def on_ev(g, src, ev):   # 2026-10-08: 드로우 · 덱에서 패에 넣기 모두 — 그 플레이어가 자신의 덱 위 2장 (덱 미지정 → 덱 주인이 고름)
        if (ev['kind'] == 'added_to_hand' and ev['prev'] in ('main', 'upper')) or ev['kind'] == 'draw':
            g.mill(ev['player'], 2, None, '아이라리움')
    c.on_event = on_ev
    c.rules = {'seri_lw_one': lambda g, src, p: p == src.controller}
    c.effects = [Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda g, c, p, ev: 0 if (g.fieldz and g.fieldz.controller == p) else 55, threat=600)]

@card('호레움')
def _(c):
    c.rules = {'decuma_plus': lambda g, src, p: p == src.controller,
               'indestructible': lambda g, src, x, battle: (not battle) and SERI(x) and x.controller == src.controller and len(g.p[src.controller].banish) >= 15}
    c.effects = [Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda g, c, p, ev: 0 if (g.fieldz and g.fieldz.controller == p) else 50, threat=600)]

@card('세제')
def _(c):
    def on_ev(g, src, ev):
        if ev['kind'] == 'activate': g.mill(ev['player'], 1, None, '세제')
    c.on_event = on_ev
    def res2(g, c, p, l): g.draw(p, 2, 'main')
    def res3(g, c, p, l): g.draw(p, 1, 'upper')
    def can_tax_draw(g, p, n, deck, draws):
        """코스트 n장(자신의 deck에서, 부족분은 다른 덱)을 내고 나서 deck에서 draws장 드로우할 수 있는가 (정본 3-6 e).
        델레가토르면 코스트는 상대 덱에서 나가므로(모자라도 발동 — engine.Game.pay_deck_cost) 드로우할 매수만 본다"""
        own = len(g.p[p].main if deck == 'main' else g.p[p].upper)
        if g.cost_payer(p) != p: return own >= draws
        return own >= tax_n(g, p, n) + draws
    # 「서로가 … 발동」: 상대도 이 스킬의 2 · 3번을 발동할 수 있다 (사용자 답변 2026-10-20 — 엔진 Effect.either_player, cards.Impl.attach가 텍스트로 표시)
    c.effects = [
        Effect(2, 'ignition', ('skill',), cond=lambda g, c, p, ev: main_ok(g, p) and can_tax_draw(g, p, 9, 'main', 2),
               cost=lambda g, c, p, l: tax_cost(g, p, 9, '세제 2번 코스트') and None, res=res2,   # 두플리카토르 · 델레가토르 적용
               score=lambda g, c, p, ev: 30 if len(g.p[p].main) > len(g.p[1 - p].main) + 9 else 0, threat=200, label='9장 제외 → 2장 드로우'),
        Effect(3, 'ignition', ('skill',), cond=lambda g, c, p, ev: main_ok(g, p) and can_tax_draw(g, p, 4, 'upper', 1),
               cost=lambda g, c, p, l: tax_cost(g, p, 4, '세제 3번 코스트', deck='upper') and None, res=res3,
               score=lambda g, c, p, ev: 25 if len(g.p[p].upper) >= 8 else 0, threat=200, label='상급 4장 제외 → 1장 드로우')]

@card('데쿠마')
def _(c):
    def res1(g, c, p, l):
        """1번: 서로의 턴 종료 시 강제 발동 — 그 턴 플레이어가 메인 덱 매수/10(올림)만큼 메인 덱 위에서 제외.
        발동하는 효과(체인 1)이므로 「아나보케」(데쿠마 1번 발동 시)로 대응할 수 있다. 2번: 이 효과로 자신이 제외했고 제외 존에 세리가 있으면 1드로우"""
        q = g.turn_player
        if getattr(g, 'decuma_skip', -1) == g.turn: g.L('아나보케: 이 턴 데쿠마 제외 무효', 'sys'); return
        n = math.ceil(len(g.p[q].main) / 10)
        if q != p and g.rule('decuma_plus', p): n += 1
        if getattr(g, 'decuma_double', None) == q and q == p: n *= 2; g.decuma_double = None
        k = g.mill(q, n, 'main', '데쿠마')
        if q == p and k and any(x.has('세리') for x in g.p[p].banish) and g.p[p].main and g.p[p].opt.get(('데쿠마', 2), 0) == 0:
            g.p[p].opt[('데쿠마', 2)] = 1; g.draw(p, 1, 'main')
    c.effects = [Effect(1, 'trigger', ('skill',), cond=lambda g, c, p, ev: ev_is(ev, 'end_phase') and bool(g.p[g.turn_player].main),
                        res=res1, mandatory=True, threat=300, label='턴 종료 시 메인 덱 1/10 제외'),
                 Effect(3, 'ignition', ('skill',), cond=lambda g, c, p, ev: main_ok(g, p) and len(g.p[p].banish) >= 20
                        and any(x.has('치프 세리') and g.can_special(x, p) for x in g.p[p].upper),
                        res=lambda g, c, p, l: (lambda cs: cs and g.special_summon(cs[0], p))([x for x in g.p[p].upper if x.has('치프 세리')]),
                        score=lambda *a: 80, threat=700, label='치프 세리 특수소환')]

"""카드 구현 4차: 세리 (기본 v8 + 확장 데쿠마 v2, 18종)
세금 = 덱 위에서 카드 제외. 승리 플랜은 상대 덱아웃.
덱 위에서 제외 (규칙 명세서 §6-7):
- 「메인 덱의 위에서부터」 · 「상급 덱의 위에서부터」는 그 덱만. 「제외할 카드가 부족할 경우 … 대신 제외한다」 문구가 있을 때만 다른 덱에서 채운다.
- 「덱의 위에서부터」(메인/상급 미지정)는 메인 · 상급 중 한쪽을 골라 그 덱에서 제외한다.
  고르는 쪽은 문장의 주어: 「상대의 덱의 위에서부터 … 제외한다」는 효과를 쓴 플레이어, 「그 플레이어는 자신의 덱」 · 「서로 자신의 덱」은 덱 주인.
ASSUME (재정 목록 G):
- 델레가토르(코스트 대납) · 두플리카토르(코스트 2배)는 「덱 위에서 제외」 · 「제외 존에서 덱으로」 형태의 코스트에만 적용.
- 세제 2 · 3번은 스킬 주인만 사용(「서로가」 문구의 상대 사용 여부 미확정).
- 이탈세 2번의 「필드에서 벗어나게 하는 효과」는 상대가 자신 필드 카드를 대상으로 한 제거 · 바운스 · 제외 계열(위협도 900 이상)로 근사.
"""
import math
from engine import Effect
from cards import card, best, value, own_turn, main_ok, opp_cards, last_opp_link, threat, cause_card, ev_is
from cards2 import targets

SERI = lambda x: x.has('세리') and x.type == '몬스터'
SERI3 = lambda x: SERI(x) and x.level == 3
DECUMA = lambda x: x.has('데쿠마')

def tax_cost(g, p, n, why, kind='mill'):
    """세리식 코스트: 덱 위 n장 제외. 두플리카토르면 2배, 델레가토르면 상대가 대신 지불"""
    if g.rule('cost_double', p): n *= 2; g.L(f'두플리카토르: 코스트 {n}장으로', 'sys')
    payer = 1 - p if g.rule('cost_transfer', p) else p
    if payer != p: g.L(f'델레가토르: 코스트를 {g.pname(payer)}가 대신 지불', 'sys')
    return g.mill(payer, n, 'main', why, fallback=True)   # 「메인 덱의 위에서부터 … 부족하면 상급 덱에서 대신」

def seri_lastwill():
    def res(g, c, p, l):
        k = 1 if g.rule('seri_lw_one', p) else 3
        back = sorted(g.p[p].banish, key=lambda x: (not SERI(x), -g.p[p].ai.card_pri(g, p, x)))[:k]
        for x in back: g.p[p].banish.remove(x); x.zone = None; g._to_deck_raw(x)
        g.L(f'제외 존 {len(back)}장 덱으로'); g.shuffle(p)
        cs = [x for x in g.p[p].main if SERI(x) and g.can_special(x, p)]
        if cs: g.special_summon(g.p[p].ai.pick_search(g, p, cs, '세리 유언'), p)
    return Effect(2, 'lastwill', ('grave',), cond=lambda g, c, p, ev: ev_is(ev, 'to_grave') and ev['card'] is c, res=res,
                  score=lambda *a: 80, threat=400, label='[유언] 제외 존 회수 + 세리 특수소환')

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
                        res=res, score=lambda g, c, p, ev: 80 if len(g.p[1 - p].main) > len(g.p[p].main) else 5, threat=500), seri_lastwill()]

def alt_normal(c, can, pay):
    c.alt_normal = (can, pay)

@card('치프 세리 - 프로쿠라토르')
def _(c):
    alt_normal(c, lambda g, p: sum(1 for x in g.p[p].grave if SERI3(x)) >= 3,
               lambda g, p: [g.banish(x, ('cost', c)) for x in [x for x in g.p[p].grave if SERI3(x)][:3]])
    def cost2(g, c, p, l):
        xs = list(g.p[p].banish); l.ctx['n'] = len(xs)
        for x in xs: g.p[p].banish.remove(x); x.zone = None; g._to_deck_raw(x)
        g.shuffle(p); g.L(f'코스트: 제외 존 {len(xs)}장 덱으로')
    c.effects = [
        Effect(2, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and bool(g.p[p].banish),
               cost=cost2, res=lambda g, c, p, l: g.mill(1 - p, l.ctx['n'], None, '프로쿠라토르', chooser=p), score=lambda *a: 90, threat=900),
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
        t = l.ctx['t']; k = g.mill(1 - p, 5, 'main', '인지세', fallback=True)
        if k < 5: g.L('제외할 카드 부족 — 발동 무효'); g.negate(t)
    e = Effect(1, 'resp', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: last_opp_link(g, p) is not None,
               cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]), res=res,
               score=lambda g, c, p, ev: 55 if threat(g, p) >= 500 or len(g.p[1 - p].main) + len(g.p[1 - p].upper) <= 12 else 25, threat=700)
    c.effects = [e, spell_lastwill()]

@card('이탈세')
def _(c):
    def cond2(g, c, p, ev):
        l = last_opp_link(g, p)
        return l is not None and l.eff.threat >= 900 and bool(g.field_cards(p))
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

@card('아이라리움')
def _(c):
    def on_ev(g, src, ev):
        if ev['kind'] == 'added_to_hand' and ev['prev'] in ('main', 'upper'): g.mill(ev['player'], 2, None, '아이라리움')
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
    c.effects = [
        Effect(2, 'ignition', ('skill',), cond=lambda g, c, p, ev: main_ok(g, p) and len(g.p[p].main) >= 11,
               cost=lambda g, c, p, l: g.mill(p, 9, 'main', '세제 2번 코스트', fallback=True) and None, res=res2,
               score=lambda g, c, p, ev: 30 if len(g.p[p].main) > len(g.p[1 - p].main) + 9 else 0, threat=200, label='9장 제외 → 2장 드로우'),
        Effect(3, 'ignition', ('skill',), cond=lambda g, c, p, ev: main_ok(g, p) and len(g.p[p].upper) >= 5,
               cost=lambda g, c, p, l: g.mill(p, 4, 'upper', '세제 3번 코스트', fallback=True) and None, res=res3,
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

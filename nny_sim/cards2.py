"""카드 구현 2차: 공용 8종 · 번성충 기생 축 6종 · 격투가 11종"""
from engine import Effect
from cards import card, best, value, own_turn, main_ok, opp_cards, oath, last_opp_link, threat, cause_card, ev_is, bsc_common


def targets(g, p, cands):
    """p의 효과로 고를 수 있는 카드 (내성 제외)"""
    return [x for x in cands if not g.immune(x, p)]


# ═══════════════════════ 공용 ═══════════════════════
@card('매수당한 킬러')
def _(c):
    def res2(g, c, p, l):
        t = best(g, targets(g, p, opp_cards(g, p)), p)
        if t: g.destroy(t)
    c.effects = [
        Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: g.can_special(c, p),
               res=lambda g, c, p, l: c.zone == 'hand' and g.special_summon(c, p),
               score=lambda g, c, p, ev: 45 if main_ok(g, p) else (35 if threat(g, p) >= 900 else 0), label='특수소환'),
        Effect(2, 'quick', ('field',), cond=lambda g, c, p, ev: bool(targets(g, p, opp_cards(g, p))), res=res2,
               score=lambda g, c, p, ev: 60 if main_ok(g, p) or threat(g, p) >= 800 else 0, threat=1000, label='파괴'),
        Effect(3, 'trigger', ('field',), mandatory=True, cond=lambda g, c, p, ev: ev_is(ev, 'end_phase') and ev['player'] == 1 - p,
               res=lambda g, c, p, l: g.on_field(c) and g.destroy(c), threat=0, label='자폭')]

@card('선택받은 용사')
def _(c):
    def res1(g, c, p, l):
        if c.zone in ('hand', 'grave', 'main', 'upper') and g.special_summon(c, p):
            c.flags['immune_opp_perm'] = True; g.L(f'{c}은(는) 상대의 효과를 받지 않음')
    c.rules = {'no_trigger_spell': lambda g, src, pl: pl == 1 - src.controller}
    c.effects = [
        Effect(1, 'resp', ('hand',), cond=lambda g, c, p, ev: last_opp_link(g, p) is not None and last_opp_link(g, p).card.type == '마법'
               and last_opp_link(g, p).card.d.get('subtype') == '트리거' and g.can_special(c, p),
               res=res1, score=lambda *a: 70, threat=700, label='특수소환 (ASSUME: 패에서)'),
        Effect(3, 'trigger', ('field',), mandatory=True, cond=lambda g, c, p, ev: ev_is(ev, 'end_phase') and ev['player'] == p,
               res=lambda g, c, p, l: g.on_field(c) and g.send_grave(c), threat=0)]

@card('해주')
def _(c):
    def res(g, c, p, l):
        for x in g.spells(1 - p):
            if x.d.get('subtype') == '지속' and not g.immune(x, p): x.negated = True
        g.no_damage[p] = g.turn; g.L(f'상대 지속 마법 전부 무효, 이 턴 {g.pname(p)}는 대미지를 줄 수 없음')
    c.effects = [Effect(1, 'quick', ('hand', 'field'), spell_act=True, res=res,
        cond=lambda g, c, p, ev: any(x.d.get('subtype') == '지속' for x in g.spells(1 - p)),
        score=lambda g, c, p, ev: 30 if not own_turn(g, p) and threat(g, p) >= 700 and last_opp_link(g, p).card.d.get('subtype') == '지속' else 0, threat=700)]

@card('럭키 다이스')
def _(c):
    def res(g, c, p, l):
        d = g.rng.randint(1, 6); n = 1 if d == 1 else 2 if d <= 3 else 3
        g.L(f'주사위: {d} → {n}장 파괴' + (' + 1장 드로우' if d == 6 else ''))
        for _ in range(n):
            t = best(g, targets(g, p, opp_cards(g, p)), p)
            if t: g.destroy(t)
        if d == 6: g.draw(p, 1)
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, res=res, cond=lambda g, c, p, ev: bool(opp_cards(g, p)),
        score=lambda g, c, p, ev: 20 + 15 * min(3, len(opp_cards(g, p))), threat=1200)]

@card('명계의 징벌')
def _(c):
    def cond1(g, c, p, ev):
        if not isinstance(ev, dict): return False
        if ev.get('kind') == 'added_to_hand' and ev['prev'] == 'grave' and ev['player'] == 1 - p: return True
        return ev.get('kind') == 'summon' and ev.get('prev') == 'grave' and ev['player'] == 1 - p
    def res1(g, c, p, l):
        t = l.ctx['ev']['card']
        if t.zone in ('hand', 'm', 'shared') : g.banish(t); g.L(f'{t} 제외')
    e1 = Effect(1, 'trigger', ('hand', 'field'), spell_act=True, cond=cond1, res=res1, score=lambda *a: 70, threat=900)
    e1.no_resp = True
    def res2(g, c, p, l):
        t = best(g, targets(g, p, opp_cards(g, p)), p)
        if t: g.destroy(t)
    c.effects = [e1, Effect(2, 'trigger', ('grave',), cond=lambda g, c, p, ev: cond1(g, c, p, ev) and bool(opp_cards(g, p)),
                            cost=lambda g, c, p, l: g.banish(c, ('cost', c)), res=res2, score=lambda *a: 60, threat=900)]

@card('명계의 규율')
def _(c):
    def cond(g, c, p, ev):
        l = last_opp_link(g, p)
        return l is not None and l.ctx.get('from_zone') == 'grave'
    def res(g, c, p, l):
        idx = g.chain.index(l) if l in g.chain else len(g.chain)
        for x in g.chain[:idx]:
            if x.player == 1 - p and x.ctx.get('from_zone') == 'grave' and not x.negated: g.negate(x)
    c.effects = [Effect(1, 'resp', ('hand', 'field'), spell_act=True, cond=cond, res=res, score=lambda *a: 60, threat=800)]

@card('사기 감지')
def _(c):
    c.effects = [Effect(1, 'trigger', ('hand', 'field'), spell_act=True,
        cond=lambda g, c, p, ev: ev_is(ev, 'added_to_hand') and ev['prev'] in ('main', 'upper') and ev['player'] == 1 - p and ev['card'].zone == 'hand',
        res=lambda g, c, p, l: l.ctx['ev']['card'].zone == 'hand' and (g.L(f'{l.ctx["ev"]["card"]} 묘지로'), g.send_grave(l.ctx['ev']['card'])),
        score=lambda g, c, p, ev: 40 + 10 * value(g, ev['card']) if isinstance(ev, dict) and 'card' in ev else 40, threat=700)]

@card('고대의 봉인')
def _(c):
    def res(g, c, p, l):
        t = l.ctx.get('t')
        if t and g.on_field(t):
            t.mods.append(('atk', -1000, 'turn')); t.flags['no_release_until'] = g.turn; t.flags['immune_all_until'] = g.turn
            g.L(f'{t} 공격력 -1000, 턴 종료 시까지 릴리스 불가 · 다른 카드의 효과를 받지 않음')
    def cost(g, c, p, l):
        l.ctx['t'] = max([x for x in g.field_cards(p) if x is not c], key=lambda x: value(g, x))
    c.effects = [Effect(1, 'quick', ('hand', 'field'), spell_act=True, cost=cost, res=res,
        cond=lambda g, c, p, ev: any(x is not c for x in g.field_cards(p)),
        score=lambda g, c, p, ev: 45 if last_opp_link(g, p) and threat(g, p) >= 900 else 0, threat=500)]


# ═══════════════════════ 번성충 — 기생 축 ═══════════════════════
PARA = '기생'

@card('번성충-기생유생')
def _(c):
    c.flags['no_normal'] = True
    c.effects = [
        Effect(1, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and ev['how'] == 'special',
               res=lambda g, c, p, l: g.add_counter(c, PARA, 1), score=lambda *a: 80, threat=200, label='카운터 1'),
        Effect(2, 'ignition', ('hand',),
               cond=lambda g, c, p, ev: main_ok(g, p) and g.can_special(c, p) and not any(m.counters.get(PARA) for m in g.monsters(p)),
               res=lambda g, c, p, l: c.zone == 'hand' and g.special_summon(c, p),
               score=lambda *a: 60, threat=200, label='패에서 특수소환 (ASSUME: [지속] 허가 = 기동 처리)')]

@card('번성충-기생포자')
def _(c):
    def res(g, c, p, l):
        ts = [m for m in g.monsters(p) if m.faceup and m.has('번성충')]
        if ts: g.add_counter(max(ts, key=lambda m: m.counters.get(PARA, 0)), PARA, 1)
    c.effects = [Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: any(m.faceup and m.has('번성충') for m in g.monsters(p)),
        cost=lambda g, c, p, l: (g.send_grave(c, ('cost', c)), oath(g, p)) and None, res=res,
        score=lambda g, c, p, ev: 40 if main_ok(g, p) else 0, threat=200)]

@card('번성충-기생촉수')
def _(c):
    def cost(g, c, p, l):
        m = min([m for m in g.monsters(p) if m.counters.get(PARA)], key=lambda m: value(g, m)); g.tribute(m, ('cost', c)); oath(g, p)
    def res(g, c, p, l):
        if c.zone == 'hand': g.special_summon(c, p)
        ts = targets(g, p, [m for m in g.monsters(1 - p) if m.faceup])
        if ts: g.add_counter(best(g, ts, p, 'steal'), PARA, 1)
    c.effects = [Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: any(m.counters.get(PARA) for m in g.monsters(p)) and any(m.faceup for m in g.monsters(1 - p)),
        cost=cost, res=res, score=lambda g, c, p, ev: 55 if main_ok(g, p) else 0, threat=900, label='감염')]

@card('번성충-기생완전체')
def _(c):
    c.flags['no_normal'] = True
    GY = lambda g, p: [x for x in g.p[p].grave if x.name.startswith('번성충-기생') and x.is_monster()]
    def cost2(g, c, p, l):
        for x in GY(g, p)[:2]: g.banish(x, ('cost', c))
    def res1(g, c, p, l):
        ts = targets(g, p, [m for m in g.monsters(1 - p) if m.faceup])
        if ts: g.add_counter(best(g, ts, p, 'steal'), PARA, 2)
    c.atk_mod = lambda g, src, x: 1500 if x is src and not any(m.faceup for m in g.monsters(1 - src.controller)) else 0
    c.effects = [
        Effect(1, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and ev['how'] == 'special'
               and any(m.faceup for m in g.monsters(1 - p)), res=res1, score=lambda *a: 90, threat=1000),
        Effect(3, 'ignition', ('hand',), cond=lambda g, c, p, ev: main_ok(g, p) and len(GY(g, p)) >= 2 and g.can_special(c, p),
               cost=cost2, res=lambda g, c, p, l: c.zone == 'hand' and g.special_summon(c, p), score=lambda *a: 65, threat=600, label='특수소환')]
    c.flags['atk_1500_if_empty'] = True

@card('번성충-사충회귀')
def _(c):
    GY = lambda g, p: [x for x in g.p[p].grave if x.name.startswith('번성충-기생') and x.is_monster()]
    def res(g, c, p, l):
        cs = [x for x in GY(g, p) if g.can_special(x, p)]
        if cs:
            x = max(cs, key=lambda x: x.level)
            if g.special_summon(x, p): g.add_counter(x, PARA, 1)
        c.flags['banish_after'] = True
    c.grave_redirect = None
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: bool(GY(g, p)) and g.free_m(p) != [],
        res=res, score=lambda *a: 50, threat=300)]
    c.flags['banish_on_resolve'] = True

@card('번성충-기생')
def _(c):
    """스킬: 기생 카운터 = 컨트롤 (상태 점검), 직접공격 1턴 1장, 종료 단계 감소, 진행 단계 이동"""
    def state(g, src):
        p = src.controller
        for m in list(g.monsters(0) + g.monsters(1)):
            if m.counters.get(PARA) and m.controller != p:
                if g.change_control(m, p): m.flags['para'] = True; g.L(f'{m} 기생 — 컨트롤 획득', 'sys')
            elif not m.counters.get(PARA) and m.flags.get('para') and m.controller == p and m.owner != p:
                m.flags.pop('para'); g.change_control(m, m.owner); g.L(f'{m} 기생 해제 — 컨트롤 반환', 'sys')
    c.state_check = state
    c.rules = {'direct_attack': lambda g, src, x: x.flags.get('para') and x.controller == src.controller and getattr(g, 'para_turn', -1) != g.turn}
    def on_ev(g, src, ev):
        if ev['kind'] == 'direct_hit' and ev['card'].flags.get('para') and ev['card'].controller == src.controller:
            g.para_turn = g.turn; x = ev['card']
            g.remove_counter(x, PARA, x.counters.get(PARA, 0))
    c.on_event = on_ev
    def end(g, src):
        p = src.controller
        if g.turn_player != p: return
        for m in list(g.monsters(p)):
            if m.owner != p and m.counters.get(PARA): g.remove_counter(m, PARA, 1)
    c.end_process = end
    def res3(g, c, p, l):
        srcs = [m for m in g.monsters(p) if m.faceup and m.has('번성충') and m.counters.get(PARA)]
        if not srcs: g.L('이동할 기생 카운터 없음 — 불발', 'sys'); return
        src = max(srcs, key=lambda m: m.counters[PARA])
        ts = targets(g, p, [m for m in g.monsters(1 - p) if m.faceup])
        if ts: g.remove_counter(src, PARA, 1); g.add_counter(best(g, ts, p, 'steal'), PARA, 1)
    c.effects = [Effect(3, 'ignition', ('skill',), cond=lambda g, c, p, ev: main_ok(g, p) and g.phase == '진행'
                        and any(m.faceup and m.has('번성충') and m.counters.get(PARA) for m in g.monsters(p)) and any(m.faceup for m in g.monsters(1 - p)),
                        res=res3, score=lambda *a: 70, threat=0, label='카운터 이동')]


# ═══════════════════════ 격투가 ═══════════════════════
def no_own_mon(g, p): return not g.monsters(p)
FGTR = lambda x: x.has('격투가')
FGTR_MON = lambda x: x.has('격투가') and x.type == '몬스터'

def search(g, p, pred, why, which=('main', 'upper')): return g.search(p, pred, which=which, why=why)

def lastwill(res, score=70):
    return Effect(9, 'lastwill', ('grave',), cond=lambda g, c, p, ev: ev_is(ev, 'to_grave') and ev['card'] is c, res=res, score=lambda *a: score, threat=300, label='[유언]')

@card('격투가 스네이크 스케일')
def _(c):
    def res(g, c, p, l):
        t = best(g, targets(g, p, g.all_field()), p)
        if t: g.destroy(t)
        if g.p[p].hand:
            d = g.p[p].ai.pick_discard(g, p, g.p[p].hand); g.L(f'{d} 버림'); g.send_grave(d)
    e = lastwill(lambda g, c, p, l: search(g, p, FGTR, '스네이크 스케일'))
    e.num = 2
    c.effects = [Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: bool(targets(g, p, opp_cards(g, p))),
                        cost=lambda g, c, p, l: g.L(f'코스트: 패에서 {c} 공개'), res=res,
                        score=lambda g, c, p, ev: 55 if main_ok(g, p) or threat(g, p) >= 900 else 0, threat=1000, label='공개 · 파괴'), e]

@card('격투가 래빗 풋')
def _(c):
    def res(g, c, p, l):
        search(g, p, FGTR, '래빗 풋')
        if g.p[p].hand:
            d = g.p[p].ai.pick_discard(g, p, g.p[p].hand); g.L(f'{d} 버림'); g.send_grave(d)
    e = lastwill(lambda g, c, p, l: search(g, p, FGTR_MON, '래빗 풋 유언')); e.num = 2
    c.effects = [Effect(1, 'quick', ('hand',), cost=lambda g, c, p, l: g.L(f'코스트: 패에서 {c} 공개'), res=res,
                        score=lambda g, c, p, ev: 45 if main_ok(g, p) else 0, threat=300, label='공개 · 서치'), e]

def fighter_ss(extra_destroy=False):
    def res(g, c, p, l):
        if c.zone == 'hand' and g.special_summon(c, p) and extra_destroy:
            t = best(g, targets(g, p, opp_cards(g, p)), p)
            if t: g.destroy(t)
    return Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: no_own_mon(g, p) and g.can_special(c, p), res=res,
                  score=lambda g, c, p, ev: 70 if main_ok(g, p) and g.phase == '진행' else (30 if not own_turn(g, p) and g.phase == '종료' else 0),
                  threat=800 if extra_destroy else 300, label='무상 특수소환')

def battle(res, score=90):
    return Effect(2, 'battle', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'battle_win') and ev['card'] is c, res=res,
                  score=lambda *a: score, threat=700, label='[전투]')

def destroy_n(g, p, n):
    for _ in range(n):
        t = best(g, targets(g, p, opp_cards(g, p)), p)
        if t: g.destroy(t)

def self_revive(): 
    e = lastwill(lambda g, c, p, l: c.zone == 'grave' and g.special_summon(c, p)); e.num = 3; return e

@card('격투가 타이거팽')
def _(c):
    def r(g, c, p, l):
        destroy_n(g, p, 1)
        if g.on_field(c): c.extra_attacks += 1; g.L(f'{c} 1회 더 공격 가능')
    c.effects = [fighter_ss(), battle(r), self_revive()]

@card('격투가 라이온하트')
def _(c):
    def r(g, c, p, l):
        search(g, p, FGTR, '라이온하트'); g.heal(p, 1000)
        if g.on_field(c): c.extra_attacks += 1; g.L(f'{c} 1회 더 공격 가능')
    c.effects = [fighter_ss(), battle(r), self_revive()]

@card('격투가 엘리펀트 노즈')
def _(c): c.effects = [fighter_ss(True), battle(lambda g, c, p, l: destroy_n(g, p, 2))]

@card('격투가 라이노 혼')
def _(c): c.effects = [fighter_ss(True), battle(lambda g, c, p, l: (destroy_n(g, p, 1), g.damage(1 - p, 1000, c.name)))]

@card('격투가 세레모니')
def _(c):
    def res(g, c, p, l):
        m = l.ctx['ev']['card']
        if not g.on_field(m): return
        m.extra_attacks += 1
        def extra(g2, ev):
            if ev['kind'] == 'battle_win' and ev['card'] is m:
                g2.L(f'세레모니 부여 효과: {m} [전투]', 'sys'); g2.damage(1 - p, 1000, '세레모니'); destroy_n(g2, p, 1)
        extra.until = g.turn; g.floating.append(extra)   # ASSUME: 부여 효과는 이 턴 동안
        g.L(f'{m} 1회 더 공격 + [전투] 부여 (이 턴)')
    c.effects = [Effect(1, 'trigger', ('hand', 'field'), spell_act=True,
        cond=lambda g, c, p, ev: ev_is(ev, 'battle_win') and ev['player'] == p and FGTR_MON(ev['card']) and g.on_field(ev['card']),
        res=res, score=lambda *a: 85, threat=800)]

@card('격투가 입장')
def _(c):
    def res1(g, c, p, l):
        cands = [x for x in g.deck_cards(p) if FGTR_MON(x)]
        if not cands: return
        x = g.p[p].ai.pick_search(g, p, cands, '입장')
        if no_own_mon(g, p) and g.can_special(x, p) and main_ok(g, p) or (not own_turn(g, p) and no_own_mon(g, p) and g.can_special(x, p)):
            if g.special_summon(x, p): x.flags['immune_opp_until'] = g.turn; g.L(f'{x} 이 턴 상대의 효과를 받지 않음')
        else: g.to_hand(x); g.L(f'{x} 패에 넣음')
        g.shuffle(p)
    c.effects = [
        Effect(1, 'quick', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: any(FGTR_MON(x) for x in g.deck_cards(p)), res=res1,
               score=lambda g, c, p, ev: 55 if main_ok(g, p) else 0, threat=400),
        Effect(2, 'trigger', ('grave',), cond=lambda g, c, p, ev: ev_is(ev, 'destroyed') and FGTR(ev['card']) and ev['card'].owner == p,
               cost=lambda g, c, p, l: g.banish(c, ('cost', c)), res=lambda g, c, p, l: search(g, p, FGTR, '입장 2번'), score=lambda *a: 60, threat=300)]

@card('격투가 반격')
def _(c):
    c.effects = [Effect(1, 'resp', ('hand', 'field'), spell_act=True,
        cond=lambda g, c, p, ev: last_opp_link(g, p) is not None and any(FGTR(x) and x.faceup for x in g.all_field() if x is not c),
        cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]), res=lambda g, c, p, l: g.negate(l.ctx['t']),
        score=lambda g, c, p, ev: 60 if threat(g, p) >= 600 else 0, threat=800)]

@card('격투가의 투기장')
def _(c):
    c.rules = {'must_attack': lambda g, src, pl: pl == 1 - src.controller}   # 상대는 몬스터가 있으면 반드시 공격 (수비 표시 금지는 AI가 수비를 쓰지 않아 자동 충족)
    def res2(g, c, p, l):
        cands = [x for x in g.deck_cards(p) if FGTR_MON(x)]
        if not cands: return
        x = g.p[p].ai.pick_search(g, p, cands, '투기장')
        if g.can_special(x, p) and no_own_mon(g, p): g.special_summon(x, p)
        else: g.to_hand(x)
        g.shuffle(p)
    c.effects = [
        Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda g, c, p, ev: 0 if (g.fieldz and g.fieldz.name == c.name and g.fieldz.controller == p) else 60, threat=700),
        Effect(2, 'quick', ('field',), cond=lambda g, c, p, ev: no_own_mon(g, p) and any(FGTR_MON(x) for x in g.deck_cards(p)), res=res2,
               score=lambda g, c, p, ev: 75 if main_ok(g, p) and g.phase == '진행' else (40 if not own_turn(g, p) and g.phase == '종료' else 0), threat=500),
        Effect(3, 'trigger', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'destroyed') and ev['card'].type == '몬스터'
               and ev['card'].owner == 1 - p, res=lambda g, c, p, l: search(g, p, FGTR, '투기장 3번'), score=lambda *a: 70, threat=300)]

@card('투기장의 규칙')
def _(c):
    def cost1(g, c, p, l):
        x = min([x for x in g.p[p].hand if FGTR(x)], key=lambda x: g.p[p].ai.card_pri(g, p, x)); g.L(f'코스트: {x} 덱으로'); g.to_deck(x, ('cost', c))
    def res2(g, c, p, l):
        xs = [x for x in g.p[p].hand if FGTR(x) and g.p[p].ai.card_pri(g, p, x) <= 0]
        for x in xs: g.to_deck(x)
        g.shuffle(p)
        if xs: g.L(f'{len(xs)}장 덱으로 → 같은 수 드로우'); g.draw(p, len(xs))
    c.effects = [
        Effect(1, 'quick', ('skill',), cond=lambda g, c, p, ev: any(FGTR(x) for x in g.p[p].hand) and any(FGTR(x) for x in g.p[p].main),
               cost=cost1, res=lambda g, c, p, l: search(g, p, FGTR, '투기장의 규칙', which=('main',)),
               score=lambda g, c, p, ev: 30 if main_ok(g, p) else 0, threat=200),
        Effect(2, 'ignition', ('skill',), cond=lambda g, c, p, ev: main_ok(g, p) and any(FGTR(x) and g.p[p].ai.card_pri(g, p, x) <= 0 for x in g.p[p].hand),
               res=res2, score=lambda *a: 20, threat=100, label='패 순환 (ASSUME: 1턴 1회)')]

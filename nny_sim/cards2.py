"""카드 구현 2차: 공용 8종 · 격투가 11종 (격투가는 2026-10-08 카드 자료로 갱신 — 아래 격투가 절 머리말).
번성충 기생 축 6종은 사용자 지시(2026-10-13)로 카드 풀에서 삭제되어 구현도 지움 (git 기록에 남아 있음)."""
from engine import Effect, link_targets
from cards import card, best, value, own_turn, main_ok, opp_cards, oath, last_opp_link, threat, cause_card, ev_is, bsc_common, field_pick, VETO, text_attrs, effect_line, hand_add


def targets(g, p, cands, src=None):
    """p의 효과로 고를 수 있는 카드 (내성 제외). src = 효과의 주체 카드 — 주면 「「X」 카드 이외의 효과를 받지 않는다」를 그 카드로 판정한다
    (호박옥 효과가 상대의 봉인된 에이스를 고를 수 있게, 2026-10-15). 주지 않으면 전과 같다(주체를 모름 = 받지 않음)"""
    return [x for x in cands if not g.immune(x, p, src)]


# ═══════════════════════ 공용 ═══════════════════════
@card('매수당한 킬러')
def _(c):
    def cost2(g, c, p, l):   # 「상대 필드의 카드 1장을 대상으로 하고 발동」
        l.ctx['t'] = best(g, targets(g, p, opp_cards(g, p)), p); g.L(f'대상: {l.ctx["t"]}')
    def res2(g, c, p, l):
        t = l.ctx.get('t')
        if t and g.on_field(t) and t.controller == 1 - p: g.destroy(t)
    c.effects = [
        Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: g.can_special(c, p),
               res=lambda g, c, p, l: c.zone == 'hand' and g.special_summon(c, p),
               score=lambda g, c, p, ev: 45 if main_ok(g, p) else (35 if threat(g, p) >= 900 else 0), label='특수소환'),
        Effect(2, 'quick', ('field',), cond=lambda g, c, p, ev: bool(targets(g, p, opp_cards(g, p))), cost=cost2, res=res2,
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
        # 3번은 「(이 효과는 강제로 발동한다.)」가 없으므로 임의 (§6-3). 자신을 묘지로 보내 얻는 것이 없어 AI는 쓰지 않는다
        Effect(3, 'trigger', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'end_phase') and ev['player'] == p,
               res=lambda g, c, p, l: g.on_field(c) and g.send_grave(c), score=lambda *a: VETO, threat=0)]

@card('해주')
def _(c):
    def res(g, c, p, l):
        for x in g.spells(1 - p):
            if x.d.get('subtype') == '지속': g.negate_card(x, c)
        g.no_damage[p] = max(g.no_damage.get(p, -1), g.turn); g.L(f'상대 지속 마법 전부 무효, 이 턴 {g.pname(p)}는 대미지를 줄 수 없음')
    def sc(g, c, p, ev):   # 일반 마법(2026-10-08): 자신 턴에만. 이 턴 대미지를 줄 수 없게 되므로 공격할 수 있는 턴에는 손해를 뺀다
        n = sum(1 for x in g.spells(1 - p) if x.d.get('subtype') == '지속' and x.faceup and not g.immune(x, p))
        return 25 * n - (25 if g.can_declare_attack(p) and any(m.faceup and m.pos == 'atk' for m in g.monsters(p)) else 0) if n else 0
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, res=res,
        cond=lambda g, c, p, ev: any(x.d.get('subtype') == '지속' for x in g.spells(1 - p)), score=sc, threat=700)]

@card('럭키 다이스')
def _(c):
    def res(g, c, p, l):
        d = g.rng.randint(1, 6); n = 1 if d == 1 else 2 if d <= 5 else 3   # 2026-10-08: 1 → 1장, 2~5 → 2장, 6 → 3장 (드로우 없음)
        g.L(f'주사위: {d} → {n}장 파괴')
        for _ in range(n):
            t = best(g, targets(g, p, opp_cards(g, p)), p)
            if t: g.destroy(t)
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
        # 설계도 확정(2026-10-10) 문장: 「상대가 묘지의 카드의 효과를 발동했을 때 발동. 그 효과와, 그보다 먼저 발동되어 아직 처리되지 않은 효과를
        # 전부 무효로 한다.」 — 묘지에서 발동한 것만이 아니라 앞선 처리 대기 효과 전부(자신 것 포함)
        for x in g.chain[:idx]:
            if not x.negated: g.negate(x)
    c.effects = [Effect(1, 'resp', ('hand', 'field'), spell_act=True, cond=cond, res=res, score=lambda *a: 60, threat=800)]

@card('사기 감지')
def _(c):
    c.effects = [Effect(1, 'trigger', ('hand', 'field'), spell_act=True,
        cond=lambda g, c, p, ev: (h := hand_add(ev)) is not None and h[2] in ('main', 'upper') and h[1] == 1 - p and h[0].zone == 'hand',   # 드로우 포함 (사용자 답변 2026-10-28)
        res=lambda g, c, p, l: l.ctx['ev']['card'].zone == 'hand' and (g.L(f'{l.ctx["ev"]["card"]} 묘지로'), g.send_grave(l.ctx['ev']['card'])),
        score=lambda g, c, p, ev: 40 + 10 * value(g, ev['card']) if isinstance(ev, dict) and 'card' in ev else 40, threat=700)]

@card('고대의 봉인')
def _(c):
    def res(g, c, p, l):
        t = l.ctx.get('t')
        if t and g.on_field(t) and not g.blocked(t, ('effect', c)):
            t.mods.append(('atk', -1000, 'turn')); t.flags['no_release_until'] = g.turn; t.flags['immune_all_until'] = g.turn
            g.L(f'{t} 공격력 -1000, 턴 종료 시까지 릴리스 불가 · 다른 카드의 효과를 받지 않음')
    def cost(g, c, p, l):
        l.ctx['t'] = max(targets(g, p, [x for x in g.field_cards(p) if x is not c]), key=lambda x: value(g, x))
    c.effects = [Effect(1, 'quick', ('hand', 'field'), spell_act=True, cost=cost, res=res,
        cond=lambda g, c, p, ev: bool(targets(g, p, [x for x in g.field_cards(p) if x is not c])),
        score=lambda g, c, p, ev: 45 if last_opp_link(g, p) and threat(g, p) >= 900 else 0, threat=500)]


# ═══════════════════════ 격투가 ═══════════════════════
# 2026-10-08 카드 자료(사용자 업로드 2026-10-13) 반영. 예전 텍스트에서 바뀐 것:
#  스네이크 스케일 1 · 엘리펀트 노즈 1 · 라이노 혼 1 · 2 · 세레모니가 「대상으로 하고 발동」(발동 시 고름), 엘리펀트 · 라이노 1번은 「대상으로 하고 발동.
#  이 카드를 특수소환하고, 그 카드를 파괴한다」, 세레모니 부여는 영구 · 중첩(재정), 투기장의 규칙에 [전투] 1장 드로우(1번)가 생기고
#  서치(2번)는 코스트가 아닌 처리 · 「덱」(메인 · 상급), 카드군 「격투가」가 생김.
# ASSUME:
#  - [전투] = 전투로 카드를 파괴하는 데 성공했을 때(엔진 battle_win, §7). 몬스터가 아닌 카드(세레모니 · 스킬 1번)의 [전투] = 자신 몬스터의 battle_win.
#  - 처리 순서(사용자 답변 2026-10-17): 텍스트 앞 효과를 처리해야 뒤 효과도 처리한다 — 스네이크 스케일 1번은 대상을 파괴하지 못하면 패를 버리지 않는다.
#    라이노 혼 2번도 대상을 파괴하지 못하면 1000 대미지를 주지 않는다.
#  - 엘리펀트 노즈 · 라이노 혼 1번: 「자신 필드에 몬스터가 존재하지 않을 경우」는 발동 조건, 특수소환하지 못하면 파괴도 하지 않는다.
#  - 세레모니: 대상 = 자신 필드의 앞면 「격투가」 몬스터(전투한 몬스터가 아니어도 됨). 부여(재정) — 그 몬스터가 필드에 있는 동안 영구:
#    매 턴 공격 횟수 +1(부여한 턴 포함) · 부여 [전투](효과 번호 30+k, k번째 부여분마다 · 몬스터 한 장마다 1턴 1번). 필드를 벗어나면 사라진다.
#    부여 [전투] 「필드의 카드 1장을 대상으로」: 상대 카드 우선, 상대 카드가 없으면 1000 대미지로 결착할 때만 자신 카드를 대상으로 쓴다.
#  - 격투가의 투기장 3번 「상대 필드의 몬스터가 파괴되었을 경우」: 파괴 직전 상대가 컨트롤하던 몬스터(to_grave 사건의 ctrl).
#  - 투기장의 규칙 2번: 되돌리기 · 서치 모두 처리(코스트 아님). AI는 되돌린 카드와 다른 이름을 서치(없으면 같은 이름도 가능).
#    3번(종류 표기 없음)은 기동 효과(1턴 1번, 기존 ASSUME) — AI는 같은 이름이 2장 이상인 카드의 여분(1장은 남김) 중 버릴 만한 것만 되돌린다.
#  - 격투가 반격 「필드에 「격투가」 카드가 존재할 때」 = 서로의 필드의 앞면 「격투가」 카드(세트된 카드는 세지 않음, 이 카드 자신 제외).
#  - 격투가 입장 1번 「패에 넣거나 특수소환한다」: AI는 자신 필드가 비었거나 이 턴 공격할 수 있을 때(자신 턴) · 상대 턴이면 특수소환.
#  - 한 번의 전투로 대상 지정 효과가 여럿 발동하면(라이노 혼 2번 · 세레모니 부여분) 체인 위 자신의 다른 발동이 고른 카드는 되도록 피한다.
#  - 투기장 1번(수비 표시 금지)은 투기장 컨트롤러의 효과를 받지 않는 몬스터에는 적용하지 않는다.
def no_own_mon(g, p): return not g.monsters(p)
FGTR = lambda x: x.has('격투가')
FGTR_MON = lambda x: x.has('격투가') and x.type == '몬스터'

def search(g, p, pred, why, which=('main', 'upper')): return g.search(p, pred, which=which, why=why)

def need(e, f):
    """발동 조건 덧붙이기: 처리할 대상이 없으면(규칙상 처리 불가) 발동하지 않는다"""
    old = e.cond
    e.cond = lambda g, c, p, ev: (old is None or old(g, c, p, ev)) and f(g, c, p, ev)
    return e

def lastwill(res, score=70):
    return Effect(9, 'lastwill', ('grave',), cond=lambda g, c, p, ev: ev_is(ev, 'to_grave') and ev['card'] is c, res=res, score=lambda *a: score, threat=300, label='[유언]')

def opp_t(g, p): return targets(g, p, opp_cards(g, p))

def taken_on_chain(g, p):
    """체인 위 p의 발동이 이미 대상으로 고른 카드 — 한 번의 전투로 대상 지정 효과가 여럿 발동할 때 같은 카드를 고르지 않게"""
    return {id(x) for lk in g.chain if lk.player == p for x in link_targets(lk)}

def pick_opp_target(g, c, p, l, why=''):
    """「상대 필드의 카드 1장을 대상으로 하고 발동」: 발동 시(코스트 단계) 고른다. 고를 카드가 없으면 발동 취소"""
    ts = opp_t(g, p)
    if not ts: return False
    tk = taken_on_chain(g, p)
    l.ctx['t'] = best(g, [x for x in ts if id(x) not in tk] or ts, p); g.L(f'{why}대상: {l.ctx["t"]}')

def destroy_target(g, p, l):
    """발동 시 고른 대상을 파괴한다. 파괴했으면 True — 뒤 효과는 앞 효과를 처리했을 때만 처리한다 (사용자 답변 2026-10-17)"""
    t = l.ctx.get('t')
    return bool(t is not None and g.on_field(t) and t.controller == 1 - p and g.destroy(t))

def discard1(g, p):
    if g.p[p].hand:
        d = g.p[p].ai.pick_discard(g, p, g.p[p].hand); g.L(f'{d} 버림'); g.send_grave(d)

@card('격투가 스네이크 스케일')
def _(c):
    def res(g, c, p, l):
        if destroy_target(g, p, l): discard1(g, p)
    e = need(lastwill(lambda g, c, p, l: search(g, p, FGTR, '스네이크 스케일')), lambda g, c, p, ev: g.can_search(p, FGTR))
    e.num = 2
    c.effects = [Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: bool(opp_t(g, p)),
                        cost=lambda g, c, p, l: pick_opp_target(g, c, p, l, f'코스트: 패에서 {c} 공개 · '), res=res,
                        score=lambda g, c, p, ev: (40 + 10 * max(value(g, x) for x in opp_t(g, p))) if (main_ok(g, p) or threat(g, p) >= 900) and opp_t(g, p) else 0,
                        threat=1000, label='공개 · 상대 카드 대상 파괴 · 1장 버림'), e]

@card('격투가 래빗 풋')
def _(c):
    def res(g, c, p, l):
        search(g, p, FGTR, '래빗 풋'); discard1(g, p)
    e = need(lastwill(lambda g, c, p, l: search(g, p, FGTR_MON, '래빗 풋 유언')), lambda g, c, p, ev: g.can_search(p, FGTR_MON)); e.num = 2
    c.effects = [Effect(1, 'quick', ('hand',), cost=lambda g, c, p, l: g.L(f'코스트: 패에서 {c} 공개'), res=res,
                        cond=lambda g, c, p, ev: g.can_search(p, FGTR),
                        score=lambda g, c, p, ev: 45 if main_ok(g, p) else 0, threat=300, label='공개 · 서치'), e]

def ss_score(g, p, extra=0.0):
    return (70 + extra) if main_ok(g, p) and g.phase == '진행' else ((30 + extra) if not own_turn(g, p) and g.phase == '종료' else 0)

def fighter_ss():
    """타이거팽 · 라이온하트 1번: 자신 필드에 몬스터가 없을 때 패에서 특수소환"""
    return Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: no_own_mon(g, p) and g.can_special(c, p),
                  res=lambda g, c, p, l: c.zone == 'hand' and g.special_summon(c, p),
                  score=lambda g, c, p, ev: ss_score(g, p), threat=300, label='무상 특수소환')

def fighter_ss_target():
    """엘리펀트 노즈 · 라이노 혼 1번: 자신 필드에 몬스터가 없을 때 상대 카드 1장을 대상으로 발동 → 이 카드를 특수소환하고 그 카드를 파괴"""
    def res(g, c, p, l):
        if c.zone == 'hand' and g.special_summon(c, p): destroy_target(g, p, l)
    return Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: no_own_mon(g, p) and g.can_special(c, p) and bool(opp_t(g, p)),
                  cost=lambda g, c, p, l: pick_opp_target(g, c, p, l), res=res,
                  score=lambda g, c, p, ev: ss_score(g, p, 10 * max([value(g, x) for x in opp_t(g, p)] or [0])), threat=800,
                  label='특수소환 + 상대 카드 대상 파괴')

def battle(res, score=90, num=2, cond=None, cost=None, label='[전투]'):
    return Effect(num, 'battle', ('field',),
                  cond=lambda g, c, p, ev: ev_is(ev, 'battle_win') and ev['card'] is c and (cond is None or cond(g, c, p, ev)),
                  cost=cost, res=res, score=score if callable(score) else (lambda *a, s=score: s), threat=700, label=label)

def destroy_n(g, p, n):
    for _ in range(n):
        t = best(g, opp_t(g, p), p)
        if t: g.destroy(t)

def extra_attack(g, c):
    if g.on_field(c): c.extra_attacks += 1; g.L(f'{c} 1회 더 공격 가능')

def self_revive():
    e = need(lastwill(lambda g, c, p, l: c.zone == 'grave' and g.special_summon(c, p)), lambda g, c, p, ev: g.can_special(c, p)); e.num = 3; return e

@card('격투가 타이거팽')
def _(c):
    def r(g, c, p, l):
        destroy_n(g, p, 1); extra_attack(g, c)
    c.effects = [fighter_ss(), battle(r), self_revive()]

@card('격투가 라이온하트')
def _(c):
    def r(g, c, p, l):
        search(g, p, FGTR, '라이온하트'); g.heal(p, 1000); extra_attack(g, c)
    c.effects = [fighter_ss(), battle(r), self_revive()]

@card('격투가 엘리펀트 노즈')
def _(c): c.effects = [fighter_ss_target(), battle(lambda g, c, p, l: destroy_n(g, p, 2))]

@card('격투가 라이노 혼')
def _(c):
    def r(g, c, p, l):
        if destroy_target(g, p, l): g.damage(1 - p, 1000, c.name)
    c.effects = [fighter_ss_target(),
                 battle(r, cond=lambda g, c, p, ev: bool(opp_t(g, p)), cost=lambda g, c, p, l: pick_opp_target(g, c, p, l), label='[전투] 상대 카드 대상 파괴 + 1000')]

CER_BASE = 30   # 세레모니 부여 [전투]의 효과 번호: 31, 32, … (k번째 부여분 — 각각 1턴 1번, 재정)

def cer_effect(k, name=''):
    """세레모니 k번째 부여 [전투]: 필드의 카드 1장을 대상으로 하고 발동 → 상대에게 1000 대미지, 그 카드를 파괴.
    name = 부여하는 카드(세레모니) — 그 카드의 「-」 항목에 연결해(Effect.grant_of) 대상 지정 · 제거 효과 등의 성질을 그 문장에서 단다(cards.text_attrs).
    제거 효과라 뒷면 마법도 대상으로 할 수 있다 (사용자 답변 2026-10-23 PDF Q6 — 부여 효과는 카드에 붙을 때가 아니라 게임 중에 생기므로 Impl.attach를 거치지 않는다)"""
    def pool(g, p): return targets(g, p, g.all_field())
    def opp_pool(g, p):
        """대상으로 고를 수 있는 상대 카드 — 「상대 효과의 대상이 되지 않는다」를 반영(발동 판정과 같은 엄격한 관점, Game.probing)"""
        prev = getattr(g, 'probing', None); g.probing = p
        try: return [x for x in pool(g, p) if x.controller != p]
        finally: g.probing = prev
    def cond(g, c, p, ev): return c.flags.get('ceremony', 0) >= k and bool(pool(g, p))
    def cost(g, c, p, l):
        ts = pool(g, p)
        if not ts: return False
        tk = taken_on_chain(g, p)
        opp = [x for x in ts if x.controller != p]
        if not opp and g.p[1 - p].hp > 1000: return False   # 자신 카드를 파괴하게 되는데 결착도 아니면 쓰지 않는다 (점수가 이미 막음 — 안전장치)
        l.ctx['t'] = best(g, [x for x in opp if id(x) not in tk] or opp, p) if opp else field_pick(g, p, pool=ts); g.L(f'대상: {l.ctx["t"]}')
    def res(g, c, p, l):
        g.damage(1 - p, 1000, f'{c.name} (세레모니 부여 [전투])')
        t = l.ctx.get('t')
        if t is not None and g.on_field(t): g.destroy(t)
    def sc(g, c, p, ev):
        if opp_pool(g, p): return 90
        return 1000 if g.p[1 - p].hp <= 1000 else VETO   # 자신 카드를 파괴하게 되면 결착일 때만
    e = battle(res, sc, num=CER_BASE + k, cond=cond, cost=cost, label=f'[전투] (세레모니 부여 {k}) 1000 대미지 + 대상 파괴')
    e.opt_per_card = True   # 부여받은 효과 — 부여마다 별개의 1턴 1번(같은 이름 몬스터 2장이 각각 받아도 각각 1번, 사용자 답변 2026-10-17)
    e.grant_of = (name, 0)   # 세레모니 텍스트의 첫 「-」 항목
    text_attrs(e, *effect_line(None, e))
    return e

@card('격투가 세레모니')
def _(c):
    def mons(g, c, p): return [m for m in g.monsters(p) if m.faceup and FGTR_MON(m) and not g.immune(m, p, c)]
    def cost(g, c, p, l):
        ms = mons(g, c, p)
        if not ms: return False
        bat = l.ctx['ev']['card'] if isinstance(l.ctx.get('ev'), dict) else None   # 전투한 몬스터를 먼저
        l.ctx['t'] = bat if bat in ms else max(ms, key=lambda m: (g.atk(m), value(g, m))); g.L(f'대상: {l.ctx["t"]}')
    def res(g, c, p, l):
        m = l.ctx.get('t')
        if m is None or not g.on_field(m) or g.blocked(m, ('effect', c)): return
        k = m.flags.get('ceremony', 0) + 1
        col = m.flags.get('clear_on_leave') or {}
        col.setdefault('ceremony', None); col.setdefault('perm_extra_attacks', None)   # 필드를 벗어나면 부여가 사라진다
        m.flags['clear_on_leave'] = col
        m.flags['ceremony'] = k; m.flags['perm_extra_attacks'] = m.flags.get('perm_extra_attacks', 0) + 1
        m.extra_attacks += 1
        if not any(e.num == CER_BASE + k for e in m.effects): m.effects.append(cer_effect(k, c.name))
        g.L(f'{m}: 1회 더 공격 + [전투] 부여 (영구, {k}중첩)')
    c.effects = [Effect(1, 'trigger', ('hand', 'field'), spell_act=True,
        cond=lambda g, c, p, ev: ev_is(ev, 'battle_win') and ev['player'] == p and bool(mons(g, c, p)),
        cost=cost, res=res, score=lambda *a: 85, threat=800, label='[전투] 「격투가」 몬스터 대상 — 추가 공격 · [전투] 부여')]

@card('격투가 입장')
def _(c):
    def res1(g, c, p, l):
        cands = [x for x in g.deck_cards(p) if FGTR_MON(x)]
        if not cands: return
        x = g.p[p].ai.pick_search(g, p, cands, '입장')
        useful = no_own_mon(g, p) or (own_turn(g, p) and g.can_declare_attack(p)) or not own_turn(g, p)   # 빈 필드 · 이 턴 공격 · 상대 턴 벽
        if useful and g.can_special(x, p):
            if g.special_summon(x, p): x.flags['immune_opp_until'] = g.turn; g.L(f'{x} 이 턴 상대의 효과를 받지 않음')
        else: g.to_hand(x); g.L(f'{x} 패에 넣음')
        g.shuffle(p)
    c.effects = [
        Effect(1, 'quick', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: any(FGTR_MON(x) for x in g.deck_cards(p)), res=res1,
               score=lambda g, c, p, ev: 55 if main_ok(g, p) else 0, threat=400),
        Effect(2, 'trigger', ('grave',), cond=lambda g, c, p, ev: ev_is(ev, 'destroyed') and FGTR(ev['card']) and ev['card'].owner == p and g.can_search(p, FGTR),
               cost=lambda g, c, p, l: g.banish(c, ('cost', c)), res=lambda g, c, p, l: search(g, p, FGTR, '입장 2번'), score=lambda *a: 60, threat=300)]

@card('격투가 반격')
def _(c):
    c.effects = [Effect(1, 'resp', ('hand', 'field'), spell_act=True,
        cond=lambda g, c, p, ev: last_opp_link(g, p) is not None and any(FGTR(x) and x.faceup for x in g.all_field() if x is not c),
        cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]), res=lambda g, c, p, l: g.negate(l.ctx['t']),
        score=lambda g, c, p, ev: 60 if threat(g, p) >= 600 else 0, threat=800)]

@card('격투가의 투기장')
def _(c):
    # 1번 [지속]: 상대는 몬스터가 있으면 반드시 공격 · 상대 필드의 몬스터는 수비 표시로 존재할 수 없다
    c.rules = {'must_attack': lambda g, src, pl: pl == 1 - src.controller,
               'no_defense': lambda g, src, pl: pl == 1 - src.controller}
    def state(g, src):   # 이미 수비 표시인 상대 몬스터는 공격 표시가 된다 — 앞면 수비 → 공격, 뒷면 수비 → 뒷면 공격 (사용자 답변 2026-10-23 PDF Q14)
        for m in g.monsters(1 - src.controller):
            if m.pos == 'def' and not g.immune(m, src.controller, src):
                m.pos = 'atk'; g.L(f'{m} 수비 표시로 존재할 수 없음 → {"공격" if m.faceup else "뒷면 공격"} 표시 (격투가의 투기장)', 'sys')
    c.state_check = state
    def res2(g, c, p, l):
        cands = [x for x in g.deck_cards(p) if FGTR_MON(x)]
        if not cands: return
        x = g.p[p].ai.pick_search(g, p, cands, '투기장')
        if g.can_special(x, p) and no_own_mon(g, p): g.special_summon(x, p)
        else: g.to_hand(x)
        g.shuffle(p)
    def cond3(g, c, p, ev):   # 「상대 필드의 몬스터가 파괴되었을 경우」: 파괴 직전 상대가 컨트롤하던 몬스터 존(공유 존 포함)의 몬스터 (묘지 대신 덱으로 가도)
        return ev_is(ev, 'destroyed') and ev.get('ctrl') == 1 - p and ev.get('prev') in ('m', 'shared') and g.can_search(p, FGTR)
    c.effects = [
        Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda g, c, p, ev: 0 if (g.fieldz and g.fieldz.name == c.name and g.fieldz.controller == p) else 60, threat=700),
        Effect(2, 'quick', ('field',), cond=lambda g, c, p, ev: no_own_mon(g, p) and any(FGTR_MON(x) for x in g.deck_cards(p)), res=res2,
               score=lambda g, c, p, ev: 75 if main_ok(g, p) and g.phase == '진행' else (40 if not own_turn(g, p) and g.phase == '종료' else 0), threat=500),
        Effect(3, 'trigger', ('field',), cond=cond3, res=lambda g, c, p, l: search(g, p, FGTR, '투기장 3번'), score=lambda *a: 70, threat=300)]

@card('투기장의 규칙')
def _(c):
    def deck_n(g, p): return len(g.p[p].main) + len(g.p[p].upper)
    def pri(g, p, x): return g.p[p].ai.card_pri(g, p, x)
    def ret2(g, p):
        hs = [x for x in g.p[p].hand if FGTR(x)]
        return min(hs, key=lambda x: pri(g, p, x)) if hs else None
    def res2(g, c, p, l):
        x = ret2(g, p)
        if x is not None: g.L(f'{x} 덱으로'); g.to_deck(x); g.shuffle(p)
        other = lambda y: FGTR(y) and (x is None or y.name != x.name)   # 되돌린 카드와 다른 이름 우선 (없으면 같은 이름도)
        search(g, p, other if g.can_search(p, other) else FGTR, '투기장의 규칙 2번')
    def sc2(g, c, p, ev):
        if not main_ok(g, p): return 0
        x = ret2(g, p)
        if x is None: return 0
        better = [y for y in g.deck_cards(p) if FGTR(y) and y.name != x.name and pri(g, p, y) > pri(g, p, x)]
        return 30 if better else 0
    def extras(g, p):
        """3번: 같은 이름이 2장 이상인 「격투가」 카드의 여분(1장은 남김) 중 버릴 만한(AI 우선도 ≤ 0) 카드"""
        by = {}
        for x in g.p[p].hand:
            if FGTR(x): by.setdefault(x.name, []).append(x)
        return [x for xs in by.values() if len(xs) >= 2 for x in xs[1:] if pri(g, p, x) <= 0]
    def res3(g, c, p, l):
        xs = extras(g, p)
        for x in xs: g.to_deck(x)
        g.shuffle(p)
        if xs: g.L(f'{len(xs)}장 덱으로 → 같은 수 드로우'); g.draw(p, len(xs))
    c.effects = [
        Effect(1, 'battle', ('skill',), cond=lambda g, c, p, ev: ev_is(ev, 'battle_win') and ev['player'] == p,
               res=lambda g, c, p, l: g.draw(p, 1), score=lambda g, c, p, ev: 60 if deck_n(g, p) >= 4 else VETO, threat=200, label='[전투] 1장 드로우'),
        Effect(2, 'quick', ('skill',), cond=lambda g, c, p, ev: any(FGTR(x) for x in g.p[p].hand) and g.can_search(p, FGTR),
               res=res2, score=sc2, threat=200, label='패의 「격투가」 1장 덱으로 → 「격투가」 서치'),
        Effect(3, 'ignition', ('skill',), cond=lambda g, c, p, ev: main_ok(g, p) and bool(extras(g, p)) and deck_n(g, p) >= len(extras(g, p)),
               res=res3, score=lambda *a: 20, threat=100, label='패 순환 (ASSUME: 기동 · 1턴 1번)')]

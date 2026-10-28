"""[지속] 적용 블록 · 카드 단위 설정 (블록 A17 상태 · 보정의 적용 모드, A1 파괴의 적용 모드 …) — 엔진의 [지속] 훅으로 설치한다.

엔진 훅(engine.Game이 읽는 것): c.rules[키](g, src, *인자) · c.flags[키] · c.atk_mod · c.def_mod · c.on_event · c.state_check · c.end_process ·
c.extra_normal · c.cont_nums(훅 → 효과 번호: [지속] 1턴 횟수, Game.cont_num) · c.cont_forced(주인에게 불리한 [지속]).
설치기는 조립 명세의 cont=[…] · card=[…] 블록마다 하나 — installer(블록, 효과 번호, 단서, 명세, 카드 자료) → f(c).
"""
from engine import Effect
from blocks import lib as L
from cards import VETO

KINDS = {}


def kind(name):
    def deco(fn):
        KINDS[name] = fn
        return fn
    return deco


def installer(b, num, notes, kw, d):
    f = KINDS[b.name]
    def inst(c, f=f, k=b.k):
        f(c, num, k, notes, kw)
        if kw.get('forced'): c.cont_forced = tuple(getattr(c, 'cont_forced', ()) or ()) + (num,)
    return inst


def note_num(c, hook, num):
    """[지속] 훅의 효과 번호 — 엔진이 그 번호 문장의 1턴 횟수를 본다(Game.cont_num)"""
    n = dict(getattr(c, 'cont_nums', None) or {}); n[hook] = num; c.cont_nums = n


def while_fn(k):
    """[지속]의 적용 조건: while_counter — 「이 카드에 X 카운터가 놓여 있는 한」(앞면 · 1개 이상), while_zone — 「이 카드가 Z 존에 존재할 경우」"""
    wc, wz = k.get('while_counter'), k.get('while_zone')
    if wc is None and wz is None and not k.get('live'): return lambda g, x: True
    return lambda g, x: x.faceup and (wc is None or x.counters.get(wc, 0) > 0) and (wz is None or x.zone == wz)


def add_rule(c, key, fn, num):
    r = dict(c.rules or {}); r[key] = fn; c.rules = r
    note_num(c, 'rule:' + key, num)


def chain_hook(c, name, fn):
    """같은 카드에 같은 이름의 훅이 여럿이면 차례로 부른다"""
    old = getattr(c, name, None)
    if old is None: setattr(c, name, fn); return
    def both(*a, _o=old, _f=fn):
        _o(*a); _f(*a)
    setattr(c, name, both)


# ═══════════════════════ 플레이어 규칙 (금지 · 강제) ═══════════════════════
@kind('forbid')
def k_forbid(c, num, k, notes, kw):
    """「(상대 · 자신)는 …할 수 없다」 — 엔진 규칙 키 k['key'] (예: 'no_trigger_spell' — 트리거 마법을 발동할 수 없다,
    'no_defense' — 필드의 몬스터는 수비 표시로 존재할 수 없다, 'must_attack' — 반드시 공격해야 한다, 'no_deck_to_hand' …).
    규칙 함수의 첫 인자 = 그 규칙을 받는 플레이어(또는 카드 — 카드면 그 컨트롤러로 판정)"""
    who = k.get('who', 'opp')
    def fn(g, src, x, *a):
        q = x if isinstance(x, int) else x.controller
        if q not in L.sides(src.controller, who): return False
        w = k.get('while')
        return w is None or L.TESTS[w.name](g, src, src.controller, None, w.k)
    add_rule(c, k['key'], fn, num)
    if k['key'] == 'no_defense':
        def state(g, src):   # 이미 수비 표시인 몬스터는 공격 표시로 — 앞면 수비 → 공격, 뒷면 수비 → 뒷면 공격 (사용자 답변 2026-10-23 PDF Q14)
            for q in L.sides(src.controller, who):
                for m in g.monsters(q):
                    if m.pos == 'def' and not g.immune(m, src.controller, src):
                        m.pos = 'atk'; g.L(f'{m} 수비 표시로 존재할 수 없음 → {"공격" if m.faceup else "뒷면 공격"} 표시 ({src.name})', 'sys')
        chain_hook(c, 'state_check', state)


# ═══════════════════════ 지속 · 필드 마법의 카드 발동(놓기) ═══════════════════════
def place_effect(c):
    """효과 번호 0 — 지속 · 필드 마법 카드를 앞면으로 놓기만 하는 발동. 점수(B안): 그 카드의 [지속] · 효과를 쓸 수 있게 되는 가치,
    자신 필드 존에 이미 같은 카드가 있으면 0, 다른 자신 필드 마법을 덮어쓰면 줄임"""
    def sc(g, c, p, ev): return L.place_gain(g, c, p)
    import cards
    e = Effect(0, 'ignition', ('hand', 'field'), spell_act=True, score=sc, threat=400, label='카드 발동(놓기)')
    cards.text_attrs(e, '', c.name)   # 0번 = 놓기만 하는 발동 — 처리 문장 없음(행동 세금의 확정 행동도 없음)
    return e


# ═══════════════════════ 카드 자신의 규칙 · 공격력 증감 · 종료 처리 · 장착 해제 ═══════════════════════
@kind('self_rule')
def k_self_rule(c, num, k, notes, kw):
    """이 카드 자신에게만 걸리는 엔진 규칙 — 'direct_attack'(「이 카드는 상대 몬스터가 존재해도 직접공격할 수 있다」) · 'double_attack' ·
    battle=True: 'indestructible'의 전투 파괴만(「이 카드는 전투로는 파괴되지 않는다」 — 규칙 인자 battle)"""
    w = while_fn(k)
    b = k.get('battle')   # True · 'battle': 전투로만 / 'effect': 효과로만(「효과로 파괴되지 않는다」)
    if b: add_rule(c, k['key'], lambda g, src, x, battle=False, *a: (battle if b in (True, 'battle') else not battle) and x is src and w(g, src), num)
    else: add_rule(c, k['key'], lambda g, src, x, *a: x is src and w(g, src), num)


@kind('stat_mod')
def k_stat_mod(c, num, k, notes, kw):
    """[지속] 공격력 · 수비력 증감 — 받는 카드(to: 집합 조건, 이 카드 컨트롤러 기준) × 양(amt, 또는 per: 집합 조건들의 카드 수 × amt)"""
    to, amt, per = k['to'], k['amt'], k.get('per')
    def mod(g, src, x):
        p = src.controller
        if not (g.on_field(x) and x.faceup and L.match_card(g, src, p, x, to) and x.controller in L.sides(p, to.get('side', 'own'))): return 0
        if per is None: return amt
        return amt * sum(len(L.cards_in(g, src, p, sc)) for sc in per)
    setattr(c, 'def_mod' if k.get('stat') == 'def' else 'atk_mod', mod)
    note_num(c, 'def_mod' if k.get('stat') == 'def' else 'atk_mod', num)


@kind('end_process')
def k_end_process(c, num, k, notes, kw):
    """[지속] 「(각 턴 · 자신 턴)의 종료 시에, …한다」 — 발동이 아닌 종료 단계 처리(Game.play_turn의 end_process, 체인 · 1턴 1회 발동 없음)"""
    steps, whose = tuple(k['steps']), k.get('whose', 'both')
    c.end_steps = (steps, whose)   # AI 가치(lib.counter_effects)가 읽는다
    def end_process(g, c):
        p = c.controller
        if whose != 'both' and (g.turn_player == p) != (whose == 'own'): return
        L.steps_run(g, c, p, steps)
    chain_hook(c, 'end_process', end_process)
    note_num(c, 'end_process', num)
    c.end_order = end_order


def end_order(g, c):
    """종료 시 처리와 「턴 종료 시」 트리거의 순서는 그 카드의 플레이어가 정한다(사용자 답변 2026-10-21) — AI: 지금 발동할 수 있는 자신의 「턴 종료 시」 트리거가
    있으면 그 뒤에(종료 시 처리가 그 트리거의 조건 — 카운터 등 — 을 바꾸기 전에)"""
    p = c.controller; ev = {'kind': 'end_phase', 'player': g.turn_player}
    for x in g.field_cards(p):
        for e in x.effects:
            sp = getattr(e, 'spec', None)
            if sp is None or e.kind != 'trigger': continue
            if any(w.name == 'when_phase' and w.k.get('phase') == 'end' for w in sp.kw.get('when', ())) and e.cond(g, x, p, ev): return 'after'
    return 'before'


@kind('host_leave')
def k_host_leave(c, num, k, notes, kw):
    """「이 카드가 장착된 몬스터가 필드에서 벗어났을 경우, …」 — 장착 대상이 떠날 때 처리(engine._remove의 on_host_leave)"""
    steps = tuple(k['steps'])
    def host_leave(g, e, host):
        g.L(f'{e} 장착 몬스터 {host} 이탈 → 처리', 'sys'); L.steps_run(g, e, e.controller, steps)
    c.on_host_leave = host_leave



@kind('player_rule')
def k_player_rule(c, num, k, notes, kw):
    """플레이어가 받는 [지속] 규칙 — 규칙 함수의 첫 인자가 플레이어: 'cost_transfer'(델레가토르) · 'cost_double'(두플리카토르) · 'seri_lw_one'(아이라리움 2번) …"""
    who, w = k.get('who', 'own'), k.get('while')
    add_rule(c, k['key'], lambda g, src, q, *a: q in L.sides(src.controller, who) and (w is None or L.TESTS[w.name](g, src, src.controller, None, w.k)), num)


@kind('rule_immune')
def k_rule_immune(c, num, k, notes, kw):
    """[지속] 「(자신 필드의 다른 카드들)은 상대의 효과를 받지 않는다」 — 엔진 규칙 'immune'(x, by): 받는 카드 x · 효과를 쓴 플레이어 by"""
    to, frm = k['to'], k.get('from', 'opp')
    def fn(g, src, x, by):
        if not (g.on_field(x) and L.match_card(g, src, src.controller, x, to) and x.controller in L.sides(src.controller, to.get('side', 'own'))): return False
        return frm == 'any' or (by is not None and (by != src.controller) == (frm == 'opp'))
    add_rule(c, 'immune', fn, num)


@kind('alt_normal')
def k_alt_normal(c, num, k, notes, kw):
    """[제약] 「이 카드는 (집합의 카드 n장을) 제외하는 것으로 일반소환할 수 있다」 — 그 몬스터만의 일반소환 방법(c.alt_normal = (할 수 있는가, 지불))"""
    sc, n = k['scope'], k['n']
    def can(g, p): return len(L.cards_in(g, c, p, sc)) >= n
    def pay(g, p):
        for x in L.cards_in(g, c, p, sc)[:n]: g.banish(x, ('cost', c))
    c.alt_normal = (can, pay)


@kind('exclusive')
def k_exclusive(c, num, k, notes, kw):
    """「이 카드의 a · b번 효과는 동시에 발동할 수 없다」 — 엔진 Game.triggers가 같은 선언 차례에 하나만"""
    c.flags['exclusive_nums'] = tuple(k['nums'])



# ═══════════════════════ 솔루나에서 더한 것 ═══════════════════════
@kind('effect_only')
def k_effect_only(c, num, k, notes, kw):
    """[제약] 「이 카드는 카드의 효과로만 소환할 수 있다」 — 소환 조건이라 패 · 덱 · 묘지에서도 판정(flags['effect_only'] — 일반소환 불가).
    by='skill': 「스킬 카드의 효과로만 특수소환할 수 있다」(flags['ss_by_skill_only'] — Game.can_special)"""
    c.flags['effect_only'] = True
    if k.get('by') == 'skill': c.flags['ss_by_skill_only'] = True


@kind('grave_redirect')
def k_grave_redirect(c, num, k, notes, kw):
    """「이 카드는 묘지로 보내질 경우 덱으로 되돌아간다」 — 키워드가 없으면 어디서 묘지로 가도, [지속]이면 필드에 있을 때만(Game.cont_active)"""
    c.grave_redirect = (lambda g, x: g.cont_active(x)) if k.get('cont') else (lambda g, x: True)


@kind('card_flag')
def k_card_flag(c, num, k, notes, kw):
    """[지속] 카드 자신의 상태 플래그(엔진이 읽는 것) — 'attack_all'(상대 몬스터 전부에 공격 선언) 등. lasting: 한 번 적용하면 그 턴 동안 계속(c.cont_lasting)"""
    v = k.get('value', True)
    if k.get('while_counter') or k.get('while_zone') or k.get('live'):   # 조건부 [지속] · live: 무효면 꺼짐 — 그때그때 계산(Game.flag), 무효면 꺼짐
        w = while_fn(k)
        c.flags[k['key']] = (lambda g, x, v=v, w=w: (v if w(g, x) and not g.is_neg(x) else None))
        if k.get('while_counter'): c.counter_guard = set(getattr(c, 'counter_guard', None) or ()) | {k['while_counter']}
    else:
        c.flags[k['key']] = v
    note_num(c, 'flag:' + k['key'], num)
    if k.get('lasting'): c.cont_lasting = set(getattr(c, 'cont_lasting', None) or ()) | {num}


@kind('field_limit')
def k_field_limit(c, num, k, notes, kw):
    """[지속] 「자신 필드에 「A」 · 「B」 몬스터는 각각 1장밖에 존재할 수 없다」 — 소환(no_special) · 제외 존 복귀 · 컨트롤 획득(field_limit) 모두 (재정 10-20 Q8)"""
    groups = tuple(k['groups']); cap = k.get('n', 1)
    def lim(g, src, x, p):
        if p != src.controller or not x.is_monster(): return False
        from cards import grp
        return any(grp(x, a) and sum(1 for m in g.monsters(p) if m is not x and grp(m, a) and m.is_monster()) >= cap for a in groups)
    add_rule(c, 'no_special', lim, num); add_rule(c, 'field_limit', lim, num)


# ═══════════════════════ 소원의 분수에서 더한 것 ═══════════════════════
@kind('swap')
def k_swap(c, num, k, notes, kw):
    """[지속] A15 효과 변경 「자신의 「X」 카드의 효과를 「…」로 변경할 수 있다」 — 규칙 'effect_swap'(받는 카드 x). 처리 때 바꿀지는 lib.swapped(AI),
    바뀐 처리 = k['steps']"""
    to = k['to']
    def fn(g, src, q, x):
        return q == src.controller and x.controller == q and L.match_card(g, src, q, x, to)
    fn.steps, fn.label = tuple(k['steps']), k.get('label', '…')
    add_rule(c, 'effect_swap', fn, num)


@kind('rule_to')
def k_rule_to(c, num, k, notes, kw):
    """[지속] 카드에 걸리는 엔진 규칙(CARD_RULES — 'double_attack' 등)을 집합 조건(to, 이 카드 컨트롤러 기준)에 맞는 필드의 카드에
    (「자신 필드의 「용기」 몬스터는 2회 공격할 수 있다」). 받는 카드의 내성은 엔진 공통(Game.rule_reaches)"""
    to, w, b = k['to'], k.get('while'), k.get('battle')
    def fn(g, src, x, *a):
        if b and not (a and a[0]): return False   # battle: 전투로 파괴되지 않는다(규칙 인자 battle)
        if w is not None and not L.TESTS[w.name](g, src, src.controller, None, w.k): return False
        return g.on_field(x) and x.controller in L.sides(src.controller, to.get('side', 'own')) and L.match_card(g, src, src.controller, x, to)
    add_rule(c, k['key'], fn, num)


# ═══════════════════════ 저주인형에서 더한 것 ═══════════════════════
@kind('turn_start')
def k_turn_start(c, num, k, notes, kw):
    """[지속] 「(서로의 · 상대의 · 자신의) 턴 시작 시에 …한다 · 이하의 효과 중 하나를 선택하여 적용한다」 — 발동이 아닌 처리(1턴 횟수는 이 번호, 주인이 고른다).
    actor: 처리하는 플레이어('own' 이 카드의 컨트롤러 · 'opp' 상대 — 「상대는 …」)"""
    steps, whose, actor = tuple(k['steps']), k.get('whose', 'both'), k.get('actor', 'own')
    def on_ev(g, src, ev):
        if ev['kind'] != 'phase' or ev['phase'] != '준비': return
        p = src.controller
        if whose != 'both' and (g.turn_player == p) != (whose == 'own'): return
        if not g.cont_use(src, num, '턴 시작 시 처리'): return
        L.steps_run(g, src, p if actor == 'own' else 1 - p, steps)
    chain_hook(c, 'on_event', on_ev)


@kind('round_start')
def k_round_start(c, num, k, notes, kw):
    """「라운드 시작 시에 …한다」 — 라운드(게임) 시작 사건에 처리(발동 아님)"""
    steps = tuple(k['steps'])
    def on_ev(g, src, ev):
        if ev['kind'] == 'game_start': L.steps_run(g, src, src.controller, steps)
    chain_hook(c, 'on_event', on_ev)


@kind('next_act_replace')
def k_next_act_replace(c, num, k, notes, kw):
    """[지속] 「이 카드의 X 카운터가 n개 이상일 때, 이 카드의 주인이 다음에 발동하는 효과는 무효가 되고 「…」로 변경된다」 — 주인 = 이 카드의 컨트롤러(재정).
    바뀐 처리 = k['steps'](이 카드의 효과 — 이 카드가 주체, 그 플레이어가 처리). 발동한 카드가 이 카드의 효과를 받지 않으면 바뀌지 않는다(Game.replace —
    재정 Q59 · Q60). 바꿔 둔 발동은 flags['replace_pending'] — 처리 전에 무효화되면 카운터는 그대로, 다음 발동이 다시 변경 대상(이 카드 자신의 발동 포함).
    턴 제약이 없는 [지속]이라 같은 턴의 다음 발동에 바로 다시 적용된다(사용자 답변 2026-10-23 PDF Q3)"""
    name, th, steps = k['counter'], k['n'], tuple(k['steps'])
    def on_ev(g, src, ev):
        if ev['kind'] == 'negated' and src.flags.get('replace_pending') is ev.get('link'):
            src.flags.pop('replace_pending', None); return
        if ev['kind'] != 'activate' or ev['player'] != src.controller or src.counters.get(name, 0) < th: return
        pend = src.flags.get('replace_pending')
        if pend is not None:
            if not pend.negated and pend in g.chain: return
            src.flags.pop('replace_pending', None)
        link = ev['link']
        def rep(g2, tl, src=src):
            src.flags.pop('replace_pending', None)
            L.steps_run(g2, src, src.controller, steps)
        if not g.replace(link, rep, src): return
        src.flags['replace_pending'] = link
        g.L(f'{src.name}: {link.card}의 효과는 무효 — 「{k.get("label", "…")}」로 변경됨', 'sys')
    chain_hook(c, 'on_event', on_ev)


# ═══════════════════════ 포커짐승들에서 더한 것 ═══════════════════════
@kind('stat_per')
def k_stat_per(c, num, k, notes, kw):
    """[지속] 공격력 · 수비력 증감 「… 1장당 n 올린다」 — 받는 카드(to: 이 카드 컨트롤러 기준 집합, self_only: 이 카드), 세는 카드: 필드(서로)의 앞면 카드 중
    count=('attr', 속성) 그 속성을 가진 카드 / ('same', 'attr') 받는 카드와 같은 속성 / ('same', 'level') 받는 카드와 같은 레벨의 몬스터.
    받는 카드 자신도 센다(사용자 답변 2026-10-22 — 빼는 경우는 텍스트에 「이외」 · 「다른」). 속성은 부여 · 「모두로 취급」 포함(cards8.attrs)"""
    to, amt, cnt_, st = k.get('to'), k['amt'], k['count'], k.get('stat', 'atk')
    def mod(g, src, x):
        import cards8
        if k.get('self_only'):
            if x is not src: return 0
        elif not (g.on_field(x) and x.faceup and L.match_card(g, src, src.controller, x, to) and x.controller in L.sides(src.controller, to.get('side', 'own'))): return 0
        fu = [y for y in g.all_field() if y.faceup]
        if cnt_[0] == 'attr': return amt * sum(1 for y in fu if cnt_[1] in cards8.attrs(g, y))
        if cnt_[1] == 'attr':
            a = cards8.attrs(g, x)
            return amt * sum(1 for y in fu if cards8.attrs(g, y) & a) if a else 0
        if not x.level: return 0
        return amt * sum(1 for y in fu if y.is_monster() and y.level == x.level)
    setattr(c, 'def_mod' if st == 'def' else 'atk_mod', mod)
    note_num(c, 'def_mod' if st == 'def' else 'atk_mod', num)


@kind('extra_normal')
def k_extra_normal(c, num, k, notes, kw):
    """[지속] 「자신은 (1턴에 n번까지) 「X」 몬스터를 추가로 일반소환할 수 있다」 — 권리(Game.extra_normal_left)"""
    n, to = k.get('n', 1), k.get('to')
    c.extra_normal = lambda g, src, p, x: n if p == src.controller and (x is None or to is None or L.match_card(g, src, p, x, to)) else 0


@kind('whenever')
def k_whenever(c, num, k, notes, kw):
    """[지속] 「…할 때마다 …한다」 — 사건이 시점 블록(k['when'])에 맞을 때마다 처리(발동 아님)"""
    w, steps = k['when'], tuple(k['steps'])
    def on_ev(g, src, ev):
        if L.TESTS[w.name](g, src, src.controller, ev, w.k):
            g.L(f'{src.name} {num}번: 처리', 'sys'); L.steps_run(g, src, src.controller, steps, ev)
    chain_hook(c, 'on_event', on_ev)


@kind('hand_quick')
def k_hand_quick(c, num, k, notes, kw):
    """[지속] 「자신 「X」 몬스터의 [신속] 효과를 패에서도 발동할 수 있다」 — 규칙 pk_hand_quick, 1턴 횟수는 단서(「1턴에 n번까지」)"""
    add_rule(c, 'pk_hand_quick', lambda g, src, p, *a: p == src.controller, num)
    c.hand_quick_n = notes.get('opt') or 1; c.hand_quick_num = num


# ═══════════════════════ 던전마스터에서 더한 것 ═══════════════════════
@kind('auto_destroy')
def k_auto_destroy(c, num, k, notes, kw):
    """[지속] 「이 카드가 필드에 존재하는 한, (공격력 · 수비력) N 이상의 상대 필드의 몬스터는 파괴된다」 — 상태 확인(state_check)마다.
    이 규칙을 가진 모든 카드의 파괴 대상을 먼저 모은 뒤 한꺼번에 파괴(양쪽에 있으면 동시에). 효과를 받지 않는 · 효과로 파괴되지 않는 몬스터는 건너뛴다"""
    c.auto_destroy = list(getattr(c, 'auto_destroy', None) or []) + [(k['stat'], k['n'], k['to'])]
    if getattr(c, '_ad_hooked', False): return
    c._ad_hooked = True
    def sc(g, src):
        if g.__dict__.get('_auto_destroy_busy') or not g.on_field(src): return
        hits = []
        for s in [x for x in g.all_field() if getattr(x, 'auto_destroy', None) and g.cont_active(x)]:
            p = s.controller
            for st, n, to in s.auto_destroy:
                for m in L.cards_in(g, s, p, to):
                    if not m.faceup or not m.is_monster(): continue
                    v = g.atk(m) if st == 'atk' else g.df(m)
                    if v >= n and not g.immune(m, p, s) and not g.rule('indestructible', m, False) and all(m is not h for _, h in hits):
                        hits.append((s, m))
        if not hits: return
        g._auto_destroy_busy = True
        try:
            for s, m in hits:
                if g.on_field(m) and m.controller != s.controller and m.faceup:
                    g.L(f'{s.name} [지속]: {m}(공 {g.atk(m)} / 수 {g.df(m)}) 파괴'); g.destroy(m, ('effect', s))
        finally:
            g._auto_destroy_busy = False
    chain_hook(c, 'state_check', sc)


@kind('guard_while')
def k_guard_while(c, num, k, notes, kw):
    """처리로 붙은 상태(flags[flag])가 있고 조건(while)이 맞는 동안: 「전투로는 파괴되지 않으며 효과를 받지 않는다」(헬 1번 뒷문장 — 처리 때 부여, 필드를 벗어나면 사라짐)"""
    flag, w = k['flag'], k['while']
    def on(g, x): return x.faceup and g.on_field(x) and bool(x.flags.get(flag)) and L.TESTS[w.name](g, x, x.controller, None, w.k)
    c.flags['immune_except_group'] = lambda g, x: '__아무 카드군도 아님__' if on(g, x) else None   # 다른 모든 카드의 효과를 받지 않는다
    r = dict(c.rules or {}); r['indestructible'] = lambda g, src, x, battle=False, *a: battle and x is src and on(g, src); c.rules = r


@kind('no_battle_damage_self')
def k_no_battle_damage_self(c, num, k, notes, kw):
    """[지속] 「이 카드가 몬스터와 전투할 때, 상대 플레이어에게 가하는 대미지는 0이 된다」 — 엔진 규칙 no_battle_damage(p, 공격 몬스터, 공격 대상)"""
    add_rule(c, 'no_battle_damage', lambda g, src, p, a, t: p == 1 - src.controller and (a is src or t is src), num)


@kind('lw_replace')
def k_lw_replace(c, num, k, notes, kw):
    """[지속] 「자신의 [유언] 효과가 발동할 때, 그 효과를 「…」로 변경할 수 있다」 — 바뀐 처리는 그 카드의 효과(「이 카드」 = [유언] 카드), 그 플레이어가 처리.
    AI(B안): 바뀐 처리의 블록 가치가 원래 효과 점수보다 클 때(강제 [유언] 「상대는 1장 드로우」 등은 대개 바꾼다)"""
    steps = tuple(k['steps'])
    c.lw_replace_steps = steps   # [유언] 점수가 바뀐 처리의 가치도 본다(lib.lw_alt)
    def on_ev(g, src, ev):
        if ev['kind'] != 'activate' or ev.get('player') != src.controller: return
        link = ev['link']
        if link.eff.kind != 'lastwill' or link.replaced is not None or link.negated: return
        p = src.controller; x = link.card; e0 = link.ctx.get('ev')
        new = L.v_steps(g, x, p, e0, steps)
        L.LW_ALT_OFF[0] = True
        try: old = link.eff.score(g, x, p, e0)
        finally: L.LW_ALT_OFF[0] = False
        if new <= old: return
        def rep(g2, tl, p=p): L.steps_run(g2, tl.card, p, steps, src=tl.card)
        if g.replace(link, rep, src):
            g.L(f'판단[{g.pname(p)}] {src.name}: {x}의 [유언]을 「{k.get("label", "…")}」로 변경', 'decision')
    chain_hook(c, 'on_event', on_ev)

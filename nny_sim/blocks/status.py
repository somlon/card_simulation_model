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
    def sc(g, c, p, ev):
        if c.type == '필드' and g.fieldz is not None and g.fieldz.controller == p:
            return 0.0 if g.fieldz.name == c.name else L.UNIT
        if any(x.name == c.name and x.faceup for x in g.spells(p)): return 0.0
        return 3.0 * L.UNIT
    return Effect(0, 'ignition', ('hand', 'field'), spell_act=True, score=sc, threat=400, label='카드 발동(놓기)')


# ═══════════════════════ 카드 자신의 규칙 · 공격력 증감 · 종료 처리 · 장착 해제 ═══════════════════════
@kind('self_rule')
def k_self_rule(c, num, k, notes, kw):
    """이 카드 자신에게만 걸리는 엔진 규칙 — 'direct_attack'(「이 카드는 상대 몬스터가 존재해도 직접공격할 수 있다」) · 'double_attack' …"""
    add_rule(c, k['key'], lambda g, src, x, *a: x is src, num)


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
    def end_process(g, c):
        p = c.controller
        if whose != 'both' and (g.turn_player == p) != (whose == 'own'): return
        L.steps_run(g, c, p, steps)
    chain_hook(c, 'end_process', end_process)
    note_num(c, 'end_process', num)


@kind('host_leave')
def k_host_leave(c, num, k, notes, kw):
    """「이 카드가 장착된 몬스터가 필드에서 벗어났을 경우, …」 — 장착 대상이 떠날 때 처리(engine._remove의 on_host_leave)"""
    steps = tuple(k['steps'])
    def host_leave(g, e, host):
        g.L(f'{e} 장착 몬스터 {host} 이탈 → 처리', 'sys'); L.steps_run(g, e, e.controller, steps)
    c.on_host_leave = host_leave

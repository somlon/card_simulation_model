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

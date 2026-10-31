"""블록 실행부 (blocks/README.md) — 블록마다 실행 · 발동 판정 · 가치(AI 점수, B안) · 위협도.

조립기(build.py)가 만든 효과 함수가 이 함수들을 상수 인자 k(조립 명세의 값, dict)로 부른다.
  실행(코스트 · 처리):  run(g, c, p, l, k) → bool   (처리했는가 — 재정 G2: 앞 처리를 해야 뒤 처리도 한다)
  발동 판정:           can(g, c, p, ev, k) → bool (재정 G2: 처리할 수 있어야 발동 선언)
  가치:                val(g, c, p, ev, k) → float (점수 단위 — 카드 가치 1 = UNIT점)
  위협도:              threat(k) → int (상대 AI가 무효를 고려할 크기 · 보유 가치, engine.Effect.threat)
시점 · 조건 블록:       f(g, c, p, ev, k) → bool
c = 효과의 주체 카드, p = 발동한 플레이어, l = engine.Link (l.ctx에 고른 카드 · 사건), ev = 사건(dict) 또는 체인(list).

카드 집합(scope — dsl.S): side · zone · kind · group · name · faceup · not_self · level · atk · def · counter · attr · pred.
"""
from collections import namedtuple
from engine import Card, link_targets
from cards import grp, value

FIELD_Z = ('m', 's', 'shared', 'fieldz')

BlockDef = namedtuple('BlockDef', 'name run can val threat')
BLOCKS = {}


def block(name, can=None, val=None, threat=0):
    """처리 · 코스트 블록 등록 — threat은 정수 또는 k → 정수"""
    def deco(fn):
        BLOCKS[name] = BlockDef(name, fn, can or _always, val or _zero, threat if callable(threat) else (lambda k, t=threat: t))
        return fn
    return deco


TESTS = {}       # 시점 · 조건 블록 이름 → f(g, c, p, ev, k)


def test(name):
    def deco(fn):
        TESTS[name] = fn
        return fn
    return deco


def _always(g, c, p, ev, k): return True
def _zero(g, c, p, ev, k): return 0.0


# ═══════════════════════ 카드 집합 ═══════════════════════
_OPS = {'>=': lambda a, b: a >= b, '<=': lambda a, b: a <= b, '==': lambda a, b: a == b, '>': lambda a, b: a > b, '<': lambda a, b: a < b}
SPELL_SUB = {'normal': '일반', 'cont': '지속', 'quick': '신속', 'trigger': '트리거'}


def sides(p, side):
    return (p,) if side == 'own' else (1 - p,) if side == 'opp' else (p, 1 - p)


def zone_cards(g, q, zone):
    pl = g.p[q]
    if zone == 'field': return g.field_cards(q)
    if zone == 'mzone': return g.battle_cards(q)
    if zone == 'szone': return g.spells(q)
    if zone == 'deck': return pl.main + pl.upper
    if zone == 'skill': return [pl.skill] if pl.skill else []
    return list(getattr(pl, zone))


def kind_ok(x, kind):
    if kind in (None, 'card'): return True
    if kind == 'monster': return x.is_monster()
    if kind == 'spell': return x.type == '마법' and not x.is_monster()
    if kind == 'field_spell': return x.type == '필드'
    if kind == 'not_monster': return not x.is_monster()
    if isinstance(kind, tuple): return x.type == '마법' and x.d.get('subtype') in tuple(SPELL_SUB.get(s, s) for s in kind)
    return x.type == kind


def match_card(g, c, p, x, sc):
    """x가 집합 조건 sc의 필터(영역 · 쪽 제외)에 맞는가"""
    if sc.get('not_self') and x is c: return False
    if not kind_ok(x, sc.get('kind')): return False
    gr = sc.get('group')
    if gr is not None and not (any(grp(x, a) for a in gr) if isinstance(gr, tuple) else grp(x, gr)): return False
    ng = sc.get('not_group')
    if ng is not None and grp(x, ng): return False
    nm = sc.get('name')
    if nm is not None and not (x.name in nm if isinstance(nm, tuple) else x.name == nm): return False
    fu = sc.get('faceup')
    if fu is not None and x.faceup != fu: return False
    for key in ('level', 'atk', 'def'):
        cmp_ = sc.get(key)
        if cmp_ is not None:
            if not x.is_monster(): return False
            v = x.level if key == 'level' else g.atk(x) if key == 'atk' else g.df(x)
            if not _OPS[cmp_[0]](v, cmp_[1]): return False
    cn = sc.get('counter')   # 카운터 이름 또는 (이름, 최소 개수)
    if cn is not None and (x.counters.get(cn[0], 0) < cn[1] if isinstance(cn, tuple) else x.counters.get(cn, 0) <= 0): return False
    hs = sc.get('name_has')   # 「「X」를 소환한다」 — 카드명 줄임 표기(이름에 X가 든 카드)
    if hs is not None and hs not in x.name: return False
    nh = sc.get('name_not_has')   # 「「X」 이외의 몬스터」 — 이름에 X가 든 카드 제외(카드명 줄임 표기)
    if nh is not None and nh in x.name: return False
    at = sc.get('attr')
    if at is not None and not x.has_attr(at): return False
    pr = sc.get('pred')
    if pr is not None and not PRED[pr](g, c, p, x): return False
    return True


def cards_in(g, c, p, sc):
    """집합 조건 sc에 맞는 카드 목록 (내성은 보지 않는다)"""
    out = []
    zones = sc.get('zone', 'field')
    for q in sides(p, sc.get('side', 'both')):
        for z in (zones if isinstance(zones, tuple) else (zones,)):
            out += [x for x in zone_cards(g, q, z) if match_card(g, c, p, x, sc)]
    return out


PRED = {     # 이름 붙은 판정 — 필터 문법으로 쓰기 어려운 것
    'releasable': lambda g, c, p, x: g.releasable(x),
    'same_name': lambda g, c, p, x: x.name == c.name and x is not c,     # 「동명의 카드」(이 카드 자신 제외)
    'not_negated': lambda g, c, p, x: not g.is_neg(x),
    'own_owned': lambda g, c, p, x: x.owner == p,                         # 원래 주인이 자신(상대 필드로 옮긴 자신의 카드)
    'is_self': lambda g, c, p, x: x is c,                                 # 이 카드(「이 카드에 카운터가 n개 이상」)
}


# ═══════════════════════ 고른 카드 · 값 (Link.ctx) ═══════════════════════
def refs(l):
    return l.ctx.setdefault('refs', {})


def ref_cards(g, c, p, l, name):
    """참조 이름 → 카드 목록. 'SELF' = 이 카드, 'EV' = 사건의 카드, 'EVLINK' = 응답한 발동의 카드,
    그 밖은 발동 시 고른 대상(l.ctx[이름]) 또는 처리 · 코스트에서 고른 카드(l.ctx['refs'][이름])"""
    if name == 'SELF': return [c]
    if l is None: return []
    if name == 'EV':
        ev = l.ctx.get('ev')
        x = ev.get('card') if isinstance(ev, dict) else None
        return [x] if x is not None else []
    if name == 'EVLINK':
        lk = l.ctx.get('evlink')
        return [lk.card] if lk is not None else []
    if name == 'EVCAUSE':   # 사건을 일으킨 카드(「상대의 몬스터 카드에 의해」 — 사건의 cause)
        ev = l.ctx.get('ev'); ca = ev.get('cause') if isinstance(ev, dict) else None
        return [ca[1]] if ca and isinstance(ca[1], Card) else []
    v = l.ctx.get(name)
    if v is None: v = refs(l).get(name)
    if v is None: return []
    return [v] if isinstance(v, Card) else [x for x in v if isinstance(x, Card)]


def num(l, v, default=1):
    """값: 정수 또는 ('ref', 이름) — 앞에서 남긴 수(「제거한 개수」 등)"""
    if v is None: return default
    if isinstance(v, tuple) and v and v[0] == 'ref': return refs(l).get(v[1], 0) if l is not None else 0
    return v


def n_of(k, default=1):
    """미리 보기용 정수 매수 (남긴 수를 참조하면 1로 본다)"""
    v = k.get('n', default)
    return v if isinstance(v, int) else 1


# ═══════════════════════ AI 고르기 ═══════════════════════
def taken_on_chain(g, p):
    """체인 위 p의 다른 발동이 이미 대상으로 고른 카드 — 같은 카드를 두 번 대상으로 고르지 않게(가능하면)"""
    return {id(x) for lk in g.chain if lk.player == p for x in link_targets(lk)}


def pick_cards(g, c, p, pool, n, k):
    """후보에서 n장 고른다. 고르는 사람 = k['chooser']('self' 기본 · 'opp').
    손해를 주는 고르기(harm — 파괴 · 제거 · 코스트 기본)는 상대 카드는 가치 높은 것부터, 자신 카드는 가치 낮은 것부터.
    이로운 고르기(harm=False — 특수소환 · 보호 · 강화)는 자신 카드 가치 높은 것부터. 필드 밖(덱 · 묘지 · 패)은 덱 지침 우선순위(card_pri)"""
    who = p if k.get('chooser', 'self') == 'self' else 1 - p
    ai = g.p[who].ai
    harm = k.get('harm', True)
    pool = list(pool); out = []
    tk = taken_on_chain(g, p) if k.get('targeted') else set()
    while pool and len(out) < n:
        cand = [x for x in pool if id(x) not in tk] or pool
        on_f = [x for x in cand if g.on_field(x)]
        if on_f:
            theirs = [x for x in on_f if g.side_of(x) != who]
            if harm and theirs:
                x = ai.pick_target(g, who, theirs, k.get('purpose', 'remove'))
            elif harm and who != p:   # 상대가 자신 필드의 카드를 골라 잃는다(「상대는 자신 필드의 … 1장 골라 파괴한다」) — 덱 지침에서 덜 아끼는 카드
                x = min(on_f, key=lambda y: (ai.card_pri(g, who, y), value(g, y)))
            elif harm:   # 자신 필드의 카드를 잃는다: 카드 가치 + 이 턴 아직 쓸 수 있는 필드 효과의 가치가 작은 것부터
                x = min(on_f, key=lambda y: keep_val(g, who, y))
            else:
                mine = [y for y in on_f if g.side_of(y) == who] or on_f
                x = max(mine, key=lambda y: value(g, y))
        else:
            mine = [y for y in cand if g.side_of(y) == who]
            if harm and mine and k.get('dest') == 'grave' and all(y.zone in ('main', 'upper') for y in mine):
                # 덱에서 묘지로 보내는 자신 카드: 묘지로 가서 쓰이는 카드([유언] 기대 가치)부터, 같으면 덱 지침에서 덜 아끼는 카드
                x = max(mine, key=lambda y: (round(lw_bonus(g, who, y, y.zone), 1), -ai.card_pri(g, who, y)))
            elif harm and mine:
                x = min(mine, key=lambda y: (ai.card_pri(g, who, y), value(g, y)))
            elif harm:
                x = max(cand, key=lambda y: value(g, y))
            else:
                x = ai.pick_search(g, who, cand, k.get('why') or f'{c.name}')
        out.append(x); pool.remove(x)
    return out


# ═══════════════════════ S1 고르기 ═══════════════════════
def pick_pool(g, c, p, sc, l=None, cost=False):
    """고를 수 있는 후보: 집합 조건에 맞고 p의 효과를 받지 않는 필드의 카드는 뺀다
    (대상 지정 여부는 엔진의 발동 판정 · 코스트 단계 판정이 본다 — Game.immune · Effect.targets_text).
    cost=True: 대상을 지정하지 않는 코스트(「…를 묘지로 보내고 발동」 등)는 효과가 아니므로 효과 내성을 보지 않는다(사용자 지시 2026-10-30 —
    기적의 영웅도 행운의 도적 1번의 코스트로 묘지로 보낼 수 있다, 재정 Q2 · Q58 「코스트로 하는 것은 효과가 아니다」와 같음).
    「릴리스할 수 없다」 같은 금지는 그 블록의 조건(pred 'releasable' 등)이 따로 본다.
    sc['among'] = 앞에서 남긴 카드 목록(「덱 위 5장을 확인하고 그 중 …」)의 참조 이름 — 그 안에서만 고른다"""
    if sc.get('among'):
        base = [x for x in ref_cards(g, c, p, l, sc['among']) if match_card(g, c, p, x, sc)] if l is not None else []
    else:
        base = cards_in(g, c, p, sc)
    if sc.get('counter_add'):   # 카운터를 놓는 효과: 「카운터를 쌓는 효과는 적용」 카드는 내성이 있어도 놓을 수 있다(Game.counter_blocked)
        out = [x for x in base if not g.counter_blocked(x, c)]
    else:
        out = base if cost else [x for x in base if not (g.on_field(x) and g.immune(x, p, c))]
    if sc.get('pickable'): out = [x for x in out if g.pickable(x, c)]   # 같은 이름 규칙(덱 · 묘지 · 제외 존에서 패에 넣기 — Game.pickable)
    return out


def need(k):
    return 1 if k.get('upto') else num(None, k.get('n', 1))


def cost_n(g, c, p, k, n):
    """코스트로 내는 카드 매수 — 두플리카토르 1번(「서로가 카드의 발동을 위해 코스트로 지불해야 하는 카드의 매수는 2배」, Game.rule 'cost_double')면 2배.
    「이 카드」만의 코스트는 2배가 되지 않는다(룰지 f 개정 2026-10-25), 「이 카드를 포함한 n장」은 이 카드를 뺀 나머지만(k['incl_self'])"""
    if k.get('cost') and k.get('n_rule') and g.rule(k['n_rule'][0], p): n = k['n_rule'][1]   # 코스트 매수를 바꾸는 [지속](세 - 아이라리움 2번)
    if not k.get('cost') or k.get('ref') == 'SELF' or not isinstance(n, int) or not g.rule('cost_double', p): return n
    return 2 * n - 1 if k.get('incl_self') else 2 * n


def pick_n(g, c, p, l, k):
    """고를 매수: n, 또는 n_count = (집합, 상한) — 「자신 묘지의 「번성충」 몬스터 수(최대 6장)만큼」"""
    if 'n_count' in k:
        sc, cap = k['n_count']
        return min(cap, len(cards_in(g, c, p, sc)))
    return cost_n(g, c, p, k, num(l, k.get('n', 1)))


def can_pick(g, c, p, ev, k):
    n = pick_n(g, c, p, None, k)
    if 'n_count' in k: return len(pick_pool(g, c, p, k['scope'])) >= 1   # 고를 수(「…수만큼」)는 코스트 뒤에 정해질 수 있다
    return len(pick_pool(g, c, p, k['scope'])) >= (1 if k.get('upto') else n)


@block('pick', can=can_pick)
def pick(g, c, p, l, k):
    """S1 고르기 — 대상(발동 시)은 l.ctx[ref], 그 밖은 l.ctx['refs'][ref]. 후보가 모자라면 False(발동 취소 · 뒤 처리 없음)"""
    pool = pick_pool(g, c, p, k['scope'], l)
    n = pick_n(g, c, p, l, k)
    upto = k.get('upto') or 'n_count' in k
    if n <= 0 or len(pool) < (1 if upto else n): return False
    if k.get('picker') == 'mark':   # 레벨 · 속성 부여의 대상: 족보 계획(cards8.plan_mark)이 고른 카드, 쓸 곳이 없으면 이 카드(뒤에 릴리스해 드로우)
        t = _mark_plan(g, p)[1]
        xs = [t if t in pool else c if c in pool else pool[0]]
    else:
        xs = pick_cards(g, c, p, pool, min(n, len(pool)), k)
    dst = l.ctx if k.get('targeted') else refs(l)
    dst[k['ref']] = xs[0] if n == 1 and not upto else xs
    g.L(('대상: ' if k.get('targeted') else '고름: ') + ', '.join(map(str, xs)))
    return True


# ═══════════════════════ 처리 대상 해석 ═══════════════════════
def payer(g, p, k):
    """코스트를 실제로 내는 플레이어 — 델레가토르 1번(상대가 대신 지불, Game.cost_payer)은 대신 낼 수 있는 코스트(k['transfer'])에만"""
    return g.cost_payer(p) if k.get('cost') and k.get('transfer') else p


def subjects(g, c, p, l, k):
    """처리 블록이 다룰 카드: ref(앞에서 고른 카드 — ref_scope가 있으면 처리 때 조건 재확인) 또는 scope + n(처리 때 고름, 대상 지정 아님)"""
    if k.get('cost') and k.get('transfer'): p = payer(g, p, k)
    if k.get('cap_by'):   # 처리할 수 있는 만큼만(「…버린다. 버린 수까지 …놓는다」 — 뒤 처리의 후보 · 빈 자리 수가 상한)
        k = dict(k, n=min(num(l, k.get('n', 1)), *[len(g.free_s(p)) if b == 'free_s' else len(cards_in(g, c, p, b)) for b in k['cap_by']]))
    if 'ref' in k:
        xs = ref_cards(g, c, p, l, k['ref'])
        rs = k.get('ref_scope')
        if rs is not None: xs = [x for x in xs if x in cards_in(g, c, p, rs)]
        return xs
    sc = k.get('scope')
    if sc is None: return []
    pool = pick_pool(g, c, p, sc, l, cost=bool(k.get('cost')))
    if k.get('all'): return pool
    if k.get('want'): return want_pick(g, c, p, pool, k)
    n = cost_n(g, c, p, k, num(l, k.get('n', 1)))
    if k.get('feeds') is not None and n == 1 and pool:   # 「패를 버린다. 묘지에서 …를 특수소환한다」 — 버린 카드도 뒤 처리 후보: 되살릴 가치 − 패에 둘 가치가 큰 카드
        fd = k['feeds']; ai = g.p[p].ai
        def gain(x):
            ok = x.is_monster() and match_card(g, c, p, x, dict(fd, side=None, zone=None)) and not x.flags.get('ss_self_only') and not g.rule('no_special', x, p)
            return (value(g, x) * UNIT + mon_extra(g, x, p) if ok else 0.0) - ai.card_pri(g, p, x)
        xs = [max(pool, key=gain)]
        if k.get('as'): refs(l)[k['as']] = xs[0]
        return xs
    if k.get('spare') is not None:   # 「…를 되돌리고 발동. …를 특수소환한다」 — 뒤 처리에 쓸 가장 좋은 카드는 되도록 남긴다(AI)
        sp = [x for x in cards_in(g, c, p, k['spare']) if x in pool]
        if sp and len(pool) - 1 >= n: pool.remove(max(sp, key=lambda x: value(g, x) * UNIT + mon_extra(g, x, p)))
    if n <= 0 or not pool: return []
    xs = pick_cards(g, c, p, pool, min(n, len(pool)), k)   # 발동 때는 정한 수가 있어야 하지만(can_subjects), 처리 때 줄었으면 있는 만큼
    if k.get('as'): refs(l)[k['as']] = xs[0] if len(xs) == 1 else xs
    return xs


def can_subjects(g, c, p, ev, k):
    """발동 판정: 처리 때 고를 후보가 정한 수만큼 있는가 (앞에서 고른 카드를 쓰는 블록은 True)"""
    if k.get('cost') and k.get('transfer'): p = payer(g, p, k)
    if 'ref' in k or k.get('scope') is None or k['scope'].get('among'): return True
    cost = bool(k.get('cost'))
    if k.get('all') or k.get('want'): return bool(pick_pool(g, c, p, k['scope'], cost=cost)) or k.get('zero_ok', False)   # 「전부」 · 「원하는 수까지」: 1장 이상
    n = k.get('n', 1)
    if not isinstance(n, int): n = 1
    n = cost_n(g, c, p, k, n)
    if k.get('upto') and k.get('zero_ok'): return True   # 「…까지」가 0장이어도 되는 문장(카운터만 떼고 아무것도 파괴하지 않음 등)
    return len(pick_pool(g, c, p, k['scope'], cost=cost)) >= (1 if k.get('upto') else n)


def preview(g, c, p, ev, k):
    """가치 계산용 미리 보기 — 고르지 않고 가장 그럴듯한 후보(상대 카드 가치 높은 것 · 자신 카드 가치 낮은 것)"""
    if 'ref' in k:
        if k['ref'] == 'SELF': return [c]
        if k['ref'] == 'EV': return [ev['card']] if isinstance(ev, dict) and ev.get('card') is not None else []
        rs = k.get('ref_scope')
        if rs is None: return []
        pool = pick_pool(g, c, p, rs)
        return sorted(pool, key=lambda x: (g.side_of(x) == p, -value(g, x)))[:1]
    sc = k.get('scope')
    if sc is None: return []
    pool = pick_pool(g, c, p, sc)
    if k.get('all'): return pool
    n = n_of(k)
    return sorted(pool, key=lambda x: (g.side_of(x) == p, -value(g, x) if g.side_of(x) != p else value(g, x)))[:n]


def _each(g, c, p, l, k, fn):
    xs = subjects(g, c, p, l, k)
    done = sum(1 for x in xs if fn(x))
    if k.get('count_as'): refs(l)[k['count_as']] = done
    if not xs: return False
    return done > 0 if k.get('any_ok', True) else done == len(xs)


# ═══════════════════════ 가치 (B안) ═══════════════════════
UNIT = 15.0          # 카드 가치(cards.value) 1 = 15점 — 예전 손 점수(20 ~ 100)와 같은 크기
HAND_CARD = 2.0      # 패 1장(서치)의 가치 (cards.value 단위)
DRAW_CARD = 1.6      # 드로우 1장의 가치
LETHAL = 1000.0      # 결착(상대 HP 0)
SELF_DISCARD = 0.5   # 처리로 이 카드 자신을 패에서 버릴 때 잃는 가치(그 카드 가치의 비율)
HP_UNIT = 50.0       # 대미지 50 = 1점


def v_loss(g, p, xs):
    """xs를 잃을 때의 가치 변화: 상대 카드 +, 자신 카드 −"""
    return sum((-1.0 if g.side_of(x) == p else 1.0) * value(g, x) for x in xs) * UNIT


def v_remove(g, c, p, ev, k):
    """파괴 · 릴리스(묘지로): 잃는 카드 가치 + 자신 카드는 묘지로 가서 발동할 [유언]의 기대 가치"""
    xs = preview(g, c, p, ev, k)
    return v_loss(g, p, xs) + sum(lw_bonus(g, p, x, x.zone) for x in xs if g.side_of(x) == p)


# ═══════════════════════ 처리 블록 ═══════════════════════
def th_target(k, hit=1000):
    """제거 계열 블록의 위협도: 상대 카드(또는 발동 시 고른 대상)면 hit, 이 카드 자신이면 0, 자신 카드면 작게"""
    r = k.get('ref')
    if r == 'SELF': return 0
    side = (k.get('ref_scope') or k.get('scope') or {}).get('side')
    if side == 'own': return 100
    return hit


def _cause(c, k):
    return ('cost', c) if k.get('cost') else ('effect', c)


@block('destroy', can=can_subjects, val=v_remove, threat=th_target)
def do_destroy(g, c, p, l, k):
    """A1 파괴"""
    return _each(g, c, p, l, k, lambda x: g.on_field(x) and bool(g.destroy(x, _cause(c, k))))


def _move_one(g, c, p, x, dest, cause, k=None):
    if dest == 'grave':
        prev = x.zone
        if x.zone in ('main', 'upper'):
            g.deck_to_grave(g.side_of(x), x, c.name)
        else:
            g.send_grave(x, cause)
        return x.zone != prev   # 묘지 대신 덱으로 가는 카드(코로나 이그니스 등)도 보낸 것이다
    if dest == 'banish':
        g.banish(x, cause)
        if x.zone == 'banish' and k and k.get('until') == 'turn': x.flags['return_from_banish'] = g.turn   # 「턴 종료 시까지 제외」 — 턴 종료 시 돌아온다
        return x.zone == 'banish'
    if dest == 'deck':
        g.to_deck(x, cause); return x.zone in ('main', 'upper')
    if dest == 'hand':
        g.to_hand(x, cause); return x.zone == 'hand'
    if dest == 'opp_hand':
        g.to_hand(x, cause, p=1 - x.owner); return x.zone == 'hand'
    raise ValueError(dest)


def v_among(g, c, p, k):
    """「덱 위 n장을 확인하고 그 중 …」 — 확인할 덱에 맞는 카드가 있으면 그 비율만큼 기대(고르기 전이라 숨은 정보)"""
    sc = k['scope']; zone = sc.get('look_zone', 'upper')
    deck = getattr(g.p[p], zone); n = sc.get('look_n', 5)
    if not deck: return 0.0
    f = sum(1 for x in deck if match_card(g, c, p, x, sc)) / len(deck)
    return min(1.0, f * n)


LW_FLAT = 0.7 * HAND_CARD    # [유언] 가치를 블록으로 셀 수 없을 때(옛 함수 · 중첩 미리 보기)의 기대 가치 (카드 가치 단위)
_LW_DEPTH = [0]


def lw_bonus(g, p, x, prev):
    """묘지로 가면 발동할 [유언]이 있는 자신 카드의 기대 가치 — 조립된 [유언]은 그 블록 가치(B안, 한 단계까지 — 그 안의 [유언]은 고정값),
    옛 함수는 고정값. [유언]의 단서(덱 · 필드에서 보내졌을 때 발동하지 않음)는 보내지기 전 영역 prev로 본다"""
    best = 0.0
    for e in x.effects:
        if e.kind != 'lastwill': continue
        sp = getattr(e, 'spec', None)
        if sp is None:
            best = max(best, LW_FLAT * UNIT); continue
        from blocks import text as T
        nt = T.notes(T.sentences(x.d).get(sp.key, ''))
        if nt.get('not_from_deck') and prev in ('main', 'upper'): continue
        if nt.get('not_from_field') and prev in FIELD_Z: continue
        if _LW_DEPTH[0]:
            best = max(best, LW_FLAT * UNIT); continue
        _LW_DEPTH[0] += 1
        try: v = e.score(g, x, p, {'kind': 'to_grave', 'card': x, 'prev': prev})
        finally: _LW_DEPTH[0] -= 1
        best = max(best, v)
    return min(best, LETHAL / 10)


def deck_need(g, q):
    """덱이 얇을 때 묘지 · 제외 존의 카드를 덱으로 되돌리는 1장의 가치(덱아웃 방지) — 15장 미만부터 커진다"""
    left = len(g.p[q].main) + len(g.p[q].upper)
    return (15 - left) * 2.0 if left < 15 else -1.5


def v_move(g, c, p, ev, k):
    if k.get('scope', {}).get('among'):
        hit = v_among(g, c, p, k)
        return hit * (HAND_CARD * UNIT if k['dest'] == 'hand' else 0.1 * UNIT)
    if k.get('want'):   # 「원하는 수까지」 — 쓸모가 적은 카드를 돌리는 만큼 조금
        return 5.0 * len(want_pick(g, c, p, pick_pool(g, c, p, k['scope']), k))
    xs = preview(g, c, p, ev, k)
    dest = k['dest']
    out = 0.0
    for x in xs:
        mine = g.side_of(x) == p
        if x is c and spent_spell(c) and dest != 'hand':   # 발동한 일반 · 신속 · 트리거 마법 자신 — 처리 뒤 어차피 묘지로 가는 카드
            out += deck_need(g, p) if dest == 'deck' else 0.0
            continue
        if g.on_field(x):
            out += v_loss(g, p, [x]) * (0.8 if dest == 'hand' else 1.0)
        elif x is c and x.zone == 'hand' and dest == 'grave' and not k.get('cost'):
            out -= SELF_DISCARD * value(g, x) * UNIT   # 「이 카드를 패에서 버린다」가 효과의 처리 — 버리는 것이 이 카드의 쓰임(잃는 것은 필드에 낼 가치의 일부)
        elif x.zone == 'hand':
            out += (-1.0 if mine else 1.0) * HAND_CARD * UNIT * 0.8
        elif dest == 'hand':
            out += (1.0 if mine else -1.0) * HAND_CARD * UNIT
        elif dest == 'deck' and x.zone in ('grave', 'banish'):
            out += deck_need(g, g.side_of(x)) * (1.0 if mine else -1.0)
        else:
            out += (-0.1 if mine else 0.1) * UNIT
        if mine and dest == 'grave': out += lw_bonus(g, p, x, x.zone)
    return out


def spent_spell(c):
    return c.type == '마법' and c.d.get('subtype') in ('일반', '신속', '트리거') and not c.flags.get('as_spell')


def th_move(k):
    return th_target(k, 900)


@block('move', can=can_subjects, val=v_move, threat=th_move)
def do_move(g, c, p, l, k):
    """A2 이동 — dest 'grave' · 'banish' · 'deck' · 'hand' · 'opp_hand'. 패의 카드를 묘지로 = 버리기, 덱의 카드를 묘지로 = deck_to_grave"""
    cause = _cause(c, k)
    lab = {'grave': '묘지로', 'banish': '제외', 'deck': '덱으로', 'hand': '패로', 'opp_hand': '상대 패로'}[k['dest']]
    def mv(x):
        ok = _move_one(g, c, p, x, k['dest'], cause, k)
        if ok: g.L(f'{x} {lab}' + (' (코스트)' if k.get('cost') else ''))
        return ok
    ok = _each(g, c, p, l, k, mv)
    if ok and k.get('shuffle') == 'both': g.shuffle(0); g.shuffle(1)
    elif ok and k.get('shuffle') == 'opp': g.shuffle(1 - p)
    elif ok and k.get('shuffle'): g.shuffle(p)
    return ok


def deck_which(sc):
    z = sc.get('zone', 'deck')
    return {'main': ('main',), 'upper': ('upper',)}.get(z, ('main', 'upper'))


def can_search(g, c, p, ev, k):
    """발동 판정: 서치할 카드가 정한 매수만큼 있는가(재정 G2) — 같은 이름 규칙 · 덱→패 금지는 엔진(Game.search_cands)"""
    sc = k['scope']; n = n_of(k)
    if k.get('name_ref'): return True   # 「동일한 이름의 카드」 — 앞에서 정한 카드에 달림(처리 때)
    cs = g.search_cands(p, lambda y: match_card(g, c, p, y, sc), which=deck_which(sc))
    return len(cs) >= (1 if k.get('upto') else n)


def v_search(g, c, p, ev, k):
    """서치: 패 1장의 가치, 가져올 카드(덱 지침이 고를 카드)가 몬스터면 그 몬스터를 낼 때 가치의 절반이 더 크면 그것"""
    v = HAND_CARD * UNIT
    if not _LW_DEPTH[0]:
        sc = k['scope']; prev = g.src; g.src = c
        try: cs = g.search_cands(p, lambda y: match_card(g, c, p, y, sc), which=deck_which(sc))
        finally: g.src = prev
        if cs:
            x = g.p[p].ai.pick_search(g, p, cs, c.name)
            if x.is_monster(): v = max(v, 0.5 * (value(g, x) * UNIT + mon_extra(g, x, p)))
    return v * n_of(k)


@block('search', can=can_search, val=v_search, threat=300)
def do_search(g, c, p, l, k):
    """A2 이동 「덱에서 … 패에 넣는다」(서치) — 같은 이름 규칙 · 덱→패 금지는 엔진(Game.search_cands · to_hand)"""
    sc = k['scope']; n = num(l, k.get('n', 1)); got = []
    for _ in range(n):
        if k.get('picker') == 'breeding' and hasattr(g.p[p].ai, 'breeding_pick'):   # 번식지 — 학습하는 고르기(ai.breeding_pick)
            cs = g.search_cands(p, lambda y: match_card(g, c, p, y, sc), which=deck_which(sc))
            if not cs: g.L(f'{c.name}: 대상 없음', 'sys'); break
            x = g.p[p].ai.breeding_pick(g, p, cs); g.to_hand(x); g.shuffle(p)
            if x.zone != 'hand': break
            g.L(f'{g.pname(p)} {c.name}: {x} 패에 넣음')
        elif k.get('name_ref'):   # 「덱에서 동일한 이름의 카드를 패에 넣는다」 — 앞에서 정한 카드(ref)와 같은 이름
            nm = {y.name for y in ref_cards(g, c, p, l, k['name_ref'])}
            x = g.search(p, lambda y: y.name in nm and y not in got, which=deck_which(sc), why=k.get('why') or c.name)
        else:
            cs = g.search_cands(p, lambda y: match_card(g, c, p, y, sc) and y not in got, which=deck_which(sc))
            if not cs: g.L(f'{k.get("why") or c.name}: 대상 없음', 'sys'); x = None
            else:
                ai = g.p[p].ai
                x = max(cs, key=lambda y: (round(hand_pick_val(g, p, y), 1), ai.card_pri(g, p, y)))
                g.to_hand(x); g.shuffle(p)
                if x.zone != 'hand': x = None
                else: g.L(f'{g.pname(p)} {k.get("why") or c.name}: {x} 패에 넣음')
        if x is None: break
        got.append(x)
    if k.get('as') and got: refs(l)[k['as']] = got[0] if len(got) == 1 else got
    return len(got) == n or (k.get('upto') and bool(got))


def v_draw(g, c, p, ev, k):
    who = p if k.get('who', 'self') == 'self' else 1 - p
    if not isinstance(k.get('n', 1), int): return 0.0   # 앞에서 남긴 수만큼(「그 수만큼 드로우」) — 그 가치는 앞 블록이 센다
    left = len(g.p[who].main) + len(g.p[who].upper)
    if left <= n_of(k) + 2: v = -LETHAL if left <= n_of(k) else -2 * UNIT   # 덱아웃이 가까우면 드로우는 손해
    else: v = DRAW_CARD * UNIT * n_of(k)
    return v if who == p else -v


@block('draw', val=v_draw, threat=300)
def do_draw(g, c, p, l, k):
    """A2 이동 「드로우」 — 덱→패 금지 · 덱아웃은 엔진(Game.draw)"""
    who = p if k.get('who', 'self') == 'self' else 1 - p
    before = len(g.p[who].hand)
    g.draw(who, num(l, k.get('n', 1)), k.get('deck'))
    return len(g.p[who].hand) > before


def v_mill(g, c, p, ev, k):
    """덱 위 n장 제외: 상대 덱은 덱아웃에 가까울수록 크게(남은 매수 이하면 결착), 자신 덱은 상대보다 먼저 바닥나게 되면 크게 손해.
    자신 메인 덱 위에서 묘지로(dest='grave')는 [유언]이 있는 카드가 섞여 있는 만큼 기대 가치를 더한다"""
    n = n_of(k); who = k.get('who', 'self'); out = 0.0
    if k.get('dest') == 'grave' and who == 'self':
        main = g.p[p].main
        if main:
            out += n * sum(lw_bonus(g, p, x, 'main') for x in main) / len(main)
    for q, sign in (((1 - p, 1.0),) if who == 'opp' else ((p, -1.0),) if who == 'self' else ((1 - p, 1.0), (p, -1.0))):
        left = len(g.p[q].main) + len(g.p[q].upper)
        if sign > 0:
            out += LETHAL if left <= n and not k.get('cost') else n * (2.0 + 30.0 / max(1, left))
        else:
            other = len(g.p[1 - q].main) + len(g.p[1 - q].upper)
            out -= n * (2.0 + (4.0 if left - n < other else 0.0))
    return out


def can_mill(g, c, p, ev, k):
    """「메인 덱 위에서부터 n장을 묘지로 보낸다」: 메인 덱에 n장 있어야 발동(재정 G2). 덱 위 제외(세리)는 부족분 규칙 · 덱아웃이 있어 늘 발동"""
    if k.get('dest') != 'grave' or k.get('cost'): return True
    return len(g.p[p if k.get('who', 'self') == 'self' else 1 - p].main) >= n_of(k)


@block('mill', can=can_mill, val=v_mill, threat=lambda k: 600 if k.get('who') in ('opp', 'both') else 100)
def do_mill(g, c, p, l, k):
    """A2 이동 「덱 위 보내기」 — dest 'banish'(제외, Game.mill) · 'grave'(메인 덱 위에서 묘지로, Game.dump).
    who 'self' · 'opp' · 'both'(「서로 자신의 덱의 …」 — 각자 고름), deck 'main' · 'upper' · None(덱 미지정 — 고르는 쪽: 주어, §6-7),
    fallback: 「제외할 카드가 부족할 경우 … 대신 제외한다」, chooser 'self': 「상대의 덱의 위에서부터 … 제외한다」는 효과를 쓴 플레이어가 고른다.
    코스트(「…제외하고 발동」)는 Game.pay_deck_cost — 두플리카토르 2배 · 델레가토르면 상대 덱에서(모자라면 상대 패배)"""
    n = cost_n(g, c, p, k, num(l, k.get('n', 1)))
    if k.get('cost'): return g.pay_deck_cost(p, n, k.get('deck'), f'{c.name} 코스트') >= 0
    if k.get('dest', 'banish') == 'grave':
        out = g.dump(p if k.get('who', 'self') == 'self' else 1 - p, n, c.name)
        if k.get('as') and l is not None: refs(l)[k['as']] = list(out)
        return bool(out)
    whos = {'self': (p,), 'opp': (1 - p,), 'both': (p, 1 - p)}[k.get('who', 'self')]
    got = 0
    for q in whos:
        got += g.mill(q, n, k.get('deck'), c.name, fallback=k.get('fallback', False), chooser=p if k.get('chooser') == 'self' else None)
    return got > 0


@block('release', can=can_subjects, val=v_remove, threat=lambda k: th_target(k, 900))
def do_release(g, c, p, l, k):
    """A3 릴리스 (릴리스 불가 성질 · 「릴리스되었을 때」 원인 표시는 엔진 Game.tribute)"""
    cause = _cause(c, k)
    def rel(x):
        if not g.on_field(x): return False
        g.tribute(x, cause); return x.zone != 'm' and x.zone != 'shared' and not g.on_field(x)
    return _each(g, c, p, l, k, rel)


def summon_cands(g, c, p, k):
    """특수소환 후보 — 「다른 카드의 효과로 소환할 수 없다」([제약] flags['ss_self_only'])는 다른 카드의 효과로는 고르지 않는다"""
    return [x for x in cards_in(g, c, p, k['scope']) if (x.is_monster() or k.get('any_card')) and not (x.flags.get('ss_self_only') and x is not c)
            and g.can_special(x, p)]


def can_special(g, c, p, ev, k):
    if k.get('who') == 'opp': p = 1 - p
    if 'ref' in k:
        if k['ref'] == 'SELF': return c.zone in k.get('src_zone', ('hand', 'grave', 'main', 'upper', 'banish')) and g.can_special(c, p)
        return True
    return len(summon_cands(g, c, p, k)) >= (1 if k.get('upto') or k.get('all') else n_of(k))


def v_special(g, c, p, ev, k):
    if not g.free_m(p) and not g.free_shared(): return 0.0
    if 'ref' in k:
        xs = [c] if k['ref'] == 'SELF' else [ev['card']] if k['ref'] == 'EV' and isinstance(ev, dict) and ev.get('card') is not None else []
    else:
        prev = g.src; g.src = c   # 미리 보기도 이 효과가 소환하는 것으로 판정(「스킬 카드의 효과로만」 · 같은 이름 규칙 — Game.can_special)
        try: xs = sorted(summon_cands(g, c, p, k), key=lambda x: -value(g, x) - mon_extra(g, x, p) / UNIT)[:n_of(k)]
        finally: g.src = prev
    return sum(value(g, x) * UNIT + mon_extra(g, x, p) for x in xs)


FIELD_FX = 0.3   # 소환한 몬스터가 필드에서 쓸 수 있는 효과 1개의 기대 가치(카드 가치 단위)


def mon_extra(g, x, p):
    """소환하는 몬스터가 가져오는 효과의 가치(B안): [소환] 효과는 그 블록 가치(한 단계), 필드에서 쓰는 다른 효과는 1개당 FIELD_FX"""
    if _LW_DEPTH[0]: return 0.0
    out = 0.0
    for e in x.effects:
        if e.kind == 'summon' and getattr(e, 'spec', None) is not None:
            _LW_DEPTH[0] += 1
            try: out += max(0.0, e.score(g, x, p, {'kind': 'summon', 'card': x, 'player': p, 'how': 'special'}))
            finally: _LW_DEPTH[0] -= 1
        elif e.kind == 'ignition' and 'field' in e.zones and getattr(e, 'spec', None) is not None:
            _LW_DEPTH[0] += 1   # 필드에서 쓸 기동 효과: 자신 진행 단계면 바로 쓸 수 있어 그 블록 가치, 아니면 절반 — 적어도 FIELD_FX
            f = 1.0 if g.turn_player == p and g.phase == '진행' else 0.5
            try: out += max(FIELD_FX * UNIT, f * e.score(g, x, p, None))
            finally: _LW_DEPTH[0] -= 1
        elif 'field' in e.zones and e.kind not in ('cont', 'restrict', 'lastwill', 'summon'):
            out += FIELD_FX * UNIT
    return out


def summon_pick(g, c, p, pool, why, brief=False):
    """특수소환할 몬스터 고르기(B안): 카드 가치 + 가져오는 효과의 가치(mon_extra)가 큰 것, 같으면 덱 지침 우선순위.
    brief: 소환한 뒤 곧바로 묘지로 보낸다(「그 후, 그 카드를 묘지로 보낸다」) — [소환] 효과와 묘지에서의 가치([유언] · 되살릴 가치)로"""
    ai = g.p[p].ai
    if brief:
        def bv(x):
            v = lw_bonus(g, p, x, 'm') + value(g, x) * 0.3 * UNIT
            for e in x.effects:
                if e.kind == 'summon' and getattr(e, 'spec', None) is not None and not _LW_DEPTH[0]:
                    _LW_DEPTH[0] += 1
                    try: v += max(0.0, e.score(g, x, p, {'kind': 'summon', 'card': x, 'player': p, 'how': 'special'}))
                    finally: _LW_DEPTH[0] -= 1
            return v
        return max(pool, key=lambda x: (round(bv(x), 1), ai.card_pri(g, p, x)))
    return max(pool, key=lambda x: (round(value(g, x) * UNIT + mon_extra(g, x, p), 1), ai.card_pri(g, p, x)))


@block('special', can=can_special, val=v_special, threat=500)
def do_special(g, c, p, l, k):
    """A6 특수소환 — ref(이 카드 · 고른 카드) 또는 scope에서 n장(처리 때 고름). pos 'atk' · 'def' · None(소환하는 쪽이 고름).
    who='opp': 「상대는 (자신의 덱에서) …를 특수소환한다」 — 상대가 상대 쪽 집합에서 소환(집합의 side는 상대 기준)"""
    if k.get('who') == 'opp': p = 1 - p
    pos = k.get('pos')
    if 'ref' in k:
        xs = ref_cards(g, c, p, l, k['ref'])
        if k['ref'] == 'SELF':
            xs = [x for x in xs if x.zone in k.get('src_zone', ('hand', 'grave', 'main', 'upper', 'banish'))]
        rs = k.get('ref_scope')
        if rs is not None: xs = [x for x in xs if x in cards_in(g, c, p, rs)]
        done = [x for x in xs if (k['ref'] == 'SELF' or g.can_special(x, p)) and g.special_summon(x, p, pos)]
    else:
        n = 99 if k.get('all') else num(l, k.get('n', 1)); done = []
        while len(done) < n:
            pool = [x for x in summon_cands(g, c, p, k) if x not in done]
            if not pool: break
            x = summon_pick(g, c, p, pool, k.get('why') or f'{c.name} 특수소환', k.get('brief'))
            if not g.special_summon(x, p, pos): break
            done.append(x)
        if any(z in ('main', 'upper', 'deck') for z in _zones(k['scope'])) and done: g.shuffle(p)
        if not k.get('all') and not k.get('upto') and len(done) < n: return bool(done) and False
    if k.get('as') and done: refs(l)[k['as']] = done[0] if len(done) == 1 else done
    return bool(done)


def _zones(sc):
    z = sc.get('zone', 'field')
    return z if isinstance(z, tuple) else (z,)


def v_damage(g, c, p, ev, k):
    amt = k['amt'] if isinstance(k['amt'], int) else 500
    if k.get('who', 'opp') == 'opp':
        return LETHAL if amt >= g.p[1 - p].hp else amt / HP_UNIT
    return -LETHAL if amt >= g.p[p].hp else -amt / HP_UNIT


@block('damage', val=v_damage, threat=lambda k: min(1000, (k['amt'] if isinstance(k['amt'], int) else 500) // 2))
def do_damage(g, c, p, l, k):
    """A16 HP 증감 — 대미지"""
    who = 1 - p if k.get('who', 'opp') == 'opp' else p
    amt = num(l, k['amt']) * (num(l, k['times']) if 'times' in k else 1)
    if amt <= 0: return False
    g.damage(who, amt, c.name); return True


def v_heal(g, c, p, ev, k):
    amt = k['amt'] if isinstance(k['amt'], int) else 500
    return (amt if k.get('who', 'self') == 'self' else -amt) / (HP_UNIT * 2)


@block('heal', val=v_heal, threat=100)
def do_heal(g, c, p, l, k):
    who = p if k.get('who', 'self') == 'self' else 1 - p
    g.heal(who, num(l, k['amt'])); return True


def _counter_k(k):
    """카운터 블록의 카드 고르기용 명세 — n은 카운터 수이므로 카드 수는 k['cards'](기본 1), 놓을 때는 내성 대신 Game.counter_blocked"""
    kk = dict(k, n=k.get('cards', 1))
    if k.get('op', 'add') == 'add' and k.get('scope') is not None: kk['scope'] = dict(k['scope'], counter_add=True)
    return kk


COUNTER_UNIT = 5.0   # 카운터 1개의 기본 가치 — 그 카드를 가진 쪽의 자원(자신 카드 +, 상대 카드 −)
GUARD_ON = 0.5       # 「이 카드에 X 카운터가 놓여 있는 한」 보호가 켜지고 꺼지는 가치(그 카드 가치의 비율)


def counter_keep(x, name):
    """x에 남겨 두고 싶은 name 카운터 수 — 「놓여 있는 한」 [지속]이 있으면 1, 「n개 이상일 때」 조건이 있으면 n"""
    k = 1 if name in (getattr(x, 'counter_guard', None) or ()) else 0
    for e in x.effects:
        ck = getattr(e, 'counter_keep', None)
        if ck and ck[0] == name: k = max(k, ck[1])
    return k


def counter_gain(g, c, p, x, name, n):
    """x에 name 카운터 n개를 놓는 가치(B안)"""
    mine = g.side_of(x) == p
    if not mine: return -COUNTER_UNIT * n
    cur = x.counters.get(name, 0); keep = counter_keep(x, name)
    v = COUNTER_UNIT * n + counter_effects(g, x, p, name, n)
    if keep and cur == 0: v += GUARD_ON * value(g, x) * UNIT
    if keep > 1 and cur < keep: v += COUNTER_UNIT * min(n, keep - cur)
    return v


def counter_loss(g, p, x, name, n):
    """x의 name 카운터 n개를 떼는 손해(B안, 음수)"""
    if g.side_of(x) != p: return COUNTER_UNIT * n
    cur = x.counters.get(name, 0); keep = counter_keep(x, name)
    v = -COUNTER_UNIT * n
    if keep and cur - n < keep <= cur: v -= GUARD_ON * value(g, x) * UNIT
    return v


def can_counter(g, c, p, ev, k):
    op = k.get('op', 'add'); name = k['name']
    if op == 'add': return can_subjects(g, c, p, ev, _counter_k(k))
    xs = _counter_all(g, c, p, None, k)
    if k.get('partial'): return True
    if k.get('total'): return sum(x.counters.get(name, 0) for x in xs) >= num(None, k.get('n', 1))
    need = 1 if op in ('remove_all', 'remove_any') else num(None, k.get('n', 1))
    # 「제거한 개수까지 …」의 쓸 곳(fit)이 비어도 되는 문장(zero_ok — 카운터만 떼고 아무것도 하지 않을 수 있음)이 아니면 쓸 곳이 있어야 발동
    if op == 'remove_any' and k.get('fit') is not None and not k.get('zero_ok') and not pick_pool(g, c, p, k['fit']): return False
    return any(x.counters.get(name, 0) >= need for x in xs)


def _counter_all(g, c, p, l, k):
    """떼는 카운터를 셀 카드(내성과 상관없이 — 받지 않는 카드의 카운터는 떼지 못할 뿐 있는 것은 있다, 재정 PDF Q2)"""
    if 'ref' in k: return ref_cards(g, c, p, l, k['ref']) if l is not None or k['ref'] == 'SELF' else ([c] if k['ref'] == 'SELF' else [])
    return [x for x in cards_in(g, c, p, k['scope']) if x.counters.get(k['name'], 0) > 0]


def counter_effects(g, x, p, name, n):
    """자신 카드 x에 name 카운터 n개를 더 놓을 때 그 카드의 효과 · [지속] 처리로 생기는 가치(B안):
    「이 카드에 카운터가 m개 놓였을 때」 트리거(정확히 m개가 될 때 그 효과 점수) ·
    종료 시 처리가 이 카운터를 전부 떼고 그 수만큼 HP를 증감하면(이 턴에 처리될 때) 그 증감"""
    out = 0.0; cur = x.counters.get(name, 0)
    for e in x.effects:
        need = getattr(e, 'counter_need', None)
        if need is not None and need[0] == name and cur + n == need[1]:
            out += max(0.0, e.score(g, x, p, {'kind': 'counter', 'card': x, 'name': name, 'delta': n, 'total': cur + n}))
    es = getattr(x, 'end_steps', None)
    if es is not None:
        steps, whose = es
        if whose == 'both' or (g.turn_player == x.controller) == (whose == 'own'):
            ref = next((b.k.get('count_as') for b in steps if b.name == 'counter' and b.k.get('name') == name and b.k.get('op') == 'remove_all'), None)
            if ref is not None:
                for b in _flat_steps(g, x, p, steps):
                    if b.name == 'damage' and b.k.get('times') == ('ref', ref):
                        out += (-1.0 if b.k.get('who') == 'self' else 1.0) * n * b.k['amt'] / HP_UNIT
    return out


def _flat_steps(g, c, p, steps):
    """처리 블록 목록을 지금 상태로 펼친다 — 분기(J2)는 조건을 지금 판정"""
    for b in steps:
        if b.name == 'branch':
            cb = b.k['cond']
            yield from _flat_steps(g, c, p, b.k['then'] if TESTS[cb.name](g, c, p, None, cb.k) else b.k['other'])
        else:
            yield b


def _any_n(g, c, p, x, k):
    """「임의의 개수만큼 제거하고 … 제거한 개수까지」 — AI: 쓸 곳(fit 집합의 카드 수)만큼, 남겨 둘 개수는 남기고(모자라면 있는 만큼)"""
    cur = x.counters.get(k['name'], 0)
    fit = len(pick_pool(g, c, p, k['fit'])) if k.get('fit') is not None else cur
    keep = counter_keep(x, k['name'])
    avail = cur - keep if cur - keep >= 1 else cur
    return max(1 if cur else 0, min(fit, avail))   # 발동했으면 1개 이상 뗀다(쓸 곳이 없어도 되는 zero_ok 문장 — 쓸 곳이 있으면 예전과 같음)


def _remove_pick(g, c, p, xs, k):
    """한 카드에서 떼기: 남겨 둘 개수를 지키고도 뗄 수 있는 카드 · 많이 가진 카드 · 가치 낮은 카드(remove_all은 fit 집합 수에 맞는 카드)"""
    name = k['name']; op = k.get('op')
    if op == 'remove_all':
        f = len(pick_pool(g, c, p, k['fit'])) if k.get('fit') is not None else 99
        return max(xs, key=lambda x: (min(x.counters.get(name, 0), f) - max(0, x.counters.get(name, 0) - f) - 0.5 * (counter_keep(x, name) > 0), -value(g, x)))
    n = num(None, k.get('n', 1))
    return max(xs, key=lambda x: (x.counters.get(name, 0) - n - counter_keep(x, name) >= 0, x.counters.get(name, 0), -value(g, x)))


def v_counter(g, c, p, ev, k):
    op = k.get('op', 'add'); name = k['name']
    if op == 'add':
        xs = [c] if k.get('ref') == 'SELF' else pick_pool(g, c, p, _counter_k(k)['scope']) if k.get('scope') is not None else []
        if not xs: return 0.0
        n = n_of(k)
        if k.get('all'): return sum(counter_gain(g, c, p, x, name, n) for x in xs)
        return max(counter_gain(g, c, p, x, name, n) for x in xs)
    xs = [x for x in _counter_all(g, c, p, None, k) if x.counters.get(name, 0) > 0]
    if not xs: return 0.0
    if k.get('total'):
        return -COUNTER_UNIT * n_of(k)
    x = _remove_pick(g, c, p, xs, k)
    n = x.counters.get(name, 0) if op == 'remove_all' else _any_n(g, c, p, x, k) if op == 'remove_any' else n_of(k)
    return counter_loss(g, p, x, name, n)


@block('counter', can=can_counter, val=v_counter, threat=200)
def do_counter(g, c, p, l, k):
    """A19 카운터 — op 'add' · 'remove' · 'remove_all' · 'remove_any'(임의의 개수 — AI가 정함). 뗀 · 놓은 개수는 k['count_as']로 남긴다.
    total: 「(자신 필드의 …에서) 카운터를 합계 n개 제거한다」 — 여러 카드에서. 재정 G6: 정한 개수가 없으면 처리하지 못한 것(아무것도 하지 않음).
    효과를 받지 않는 카드의 카운터는 떼지 못하지만 있는 것으로 센다(처리는 이어 감 — 재정 PDF Q2).
    partial: 「제거하지 못하면 대신 …」 — 있는 만큼 떼고 모자란 수를 k['short_as']로 남긴다"""
    op = k.get('op', 'add'); name = k['name']; total = 0
    if op == 'add':
        xs = [c] if k.get('ref') == 'SELF' else ref_cards(g, c, p, l, k['ref']) if 'ref' in k else None
        if xs is None:
            pool = pick_pool(g, c, p, _counter_k(k)['scope'], l)
            if not pool: return False
            xs = pool if k.get('all') else [max(pool, key=lambda x: counter_gain(g, c, p, x, name, num(l, k.get('n', 1))))]
        n = num(l, k.get('n', 1))
        for x in xs:
            if g.add_counter(x, name, n, src=c): total += n
        if k.get('count_as'): refs(l)[k['count_as']] = total
        return total > 0
    allx = [x for x in _counter_all(g, c, p, l, k) if x.counters.get(name, 0) > 0]
    if k.get('total'):
        need = num(l, k.get('n', 1)); have = sum(x.counters.get(name, 0) for x in allx)
        if have < need and not k.get('partial'): return False
        left = {x.uid: x.counters.get(name, 0) for x in allx}; plan = {}
        for _ in range(need):   # 하나씩: 남겨 둘 개수를 넘는 여유가 큰 카드부터
            cs = [x for x in allx if left[x.uid] > 0]
            if not cs: break
            x = max(cs, key=lambda x: (left[x.uid] - counter_keep(x, name), -value(g, x)))
            left[x.uid] -= 1; plan[x.uid] = plan.get(x.uid, 0) + 1
        for x in allx:
            if plan.get(x.uid): total += g.remove_counter(x, name, plan[x.uid], src=c)
        if k.get('count_as'): refs(l)[k['count_as']] = total
        if k.get('short_as'): refs(l)[k['short_as']] = need - total
        return True if k.get('partial') else total >= need or have >= need
    if not allx: return False
    xs = allx if 'ref' in k else [_remove_pick(g, c, p, [x for x in allx if op != 'remove' or x.counters.get(name, 0) >= num(l, k.get('n', 1))] or allx, k)]
    for x in xs:
        n = x.counters.get(name, 0) if op == 'remove_all' else _any_n(g, c, p, x, k) if op == 'remove_any' else num(l, k.get('n', 1))
        if n <= 0 or (op == 'remove' and x.counters.get(name, 0) < n): continue
        total += g.remove_counter(x, name, n, src=c)
    if k.get('count_as'): refs(l)[k['count_as']] = total
    return total > 0


def v_negate_link(g, c, p, ev, k):
    lk = g.chain[-1] if g.chain else None
    return (lk.eff.threat / 10.0) if lk is not None and lk.player != p else 0.0


@block('negate_link', val=v_negate_link, threat=1000)
def do_negate_link(g, c, p, l, k):
    """A12 발동 무효 — 응답한 발동(l.ctx['evlink'])"""
    lk = l.ctx.get('evlink')
    if lk is None or lk.negated: return False
    g.negate(lk, destroy=k.get('destroy', False), by=c)
    x = lk.card
    if k.get('act_grave') and lk.negated and lk.eff.spell_act and g.on_field(x) and x.is_spell_like() and x.d.get('subtype') not in ('일반', '신속', '트리거'):
        g.L(f'{x}의 발동 무효 → 묘지로', 'sys'); g.send_grave(x, ('rule', None))   # 「그 발동을 무효로 한다」 — 지속 · 필드 마법 카드의 발동이면 그 카드도 묘지로
    return lk.negated


@block('negate_card', can=can_subjects, val=lambda g, c, p, ev, k: 0.6 * v_remove(g, c, p, ev, k), threat=700)
def do_negate_card(g, c, p, l, k):
    """A14 카드 무효 — 턴 종료 시까지"""
    return _each(g, c, p, l, k, lambda x: g.negate_card(x, c))


@block('extra_attack', val=lambda g, c, p, ev, k: 0.6 * UNIT * n_of(k) if g.battle_cards(1 - p) or g.p[1 - p].hp > 0 else 0.0, threat=300)
def do_extra_attack(g, c, p, l, k):
    """A17 상태 · 보정 「1회 더 공격할 수 있다」 — ref의 몬스터(기본 이 카드)"""
    xs = ref_cards(g, c, p, l, k.get('ref', 'SELF'))
    n = num(l, k.get('n', 1)); done = False
    for x in xs:
        if g.on_field(x) and x.is_monster():
            x.extra_attacks += n; done = True
            if k.get('perm'):   # 영구 부여(세레모니 재정) — 매 턴 다시 붙고(Game.play_turn), 필드를 벗어나면 사라진다
                col = dict(x.flags.get('clear_on_leave') or {}); col.setdefault('perm_extra_attacks', None); x.flags['clear_on_leave'] = col
                x.flags['perm_extra_attacks'] = x.flags.get('perm_extra_attacks', 0) + n
            g.L(f'{x} {n}회 더 공격 가능' + (' (영구)' if k.get('perm') else ''))
    return done


def v_stat(g, c, p, ev, k):
    amt = k['amt'] if isinstance(k['amt'], int) else 0
    xs = preview(g, c, p, ev, k)
    return sum((1 if g.side_of(x) == p else -1) * amt for x in xs) / 100.0


@block('stat', can=can_subjects, val=v_stat, threat=300)
def do_stat(g, c, p, l, k):
    """A17 상태 · 보정 — 공격력 · 수비력 증감(until 'turn' = 턴 종료 시까지, None = 필드에 있는 동안)"""
    stats = ('atk', 'def') if k.get('stat') == 'both' else (k.get('stat', 'atk'),); amt = num(l, k['amt']); until = k.get('until', 'turn')
    def f(x):
        if not g.on_field(x) or g.blocked(x, ('effect', c)): return False
        for st in stats: x.mods.append((st, amt, until))
        g.L(f'{x} {"공격력/수비력" if len(stats) == 2 else "공격력" if stats[0] == "atk" else "수비력"} {amt:+d}'); return True
    return _each(g, c, p, l, k, f)


# ═══════════════════════ 조건 (C1) ═══════════════════════
@test('cnt')
def t_cnt(g, c, p, ev, k):
    """C1 조건 — 집합의 카드 수 비교"""
    return _OPS[k.get('op', '>=')](len(cards_in(g, c, p, k['scope'])) + k.get('plus', 0), k.get('n', 1))


@test('cond_own_turn')
def t_own_turn(g, c, p, ev, k): return g.turn_player == p


@test('cond_opp_turn')
def t_opp_turn(g, c, p, ev, k): return g.turn_player != p


# ═══════════════════════ 시점 (E) ═══════════════════════
def ev_kind(ev, kind):
    return isinstance(ev, dict) and ev.get('kind') == kind


def _who_ok(k, actor, p):
    w = k.get('who', 'both')
    return w == 'both' or (w == 'own') == (actor == p)


@test('when_summoned')
def w_summoned(g, c, p, ev, k):
    """E1 소환되었을 때 — who: 소환한 플레이어, self: 이 카드가, how: 'special' · 'normal', prev: 출발 영역, filter: 소환된 카드, side: 소환된 필드"""
    if not ev_kind(ev, 'summon') or ev.get('negated'): return False
    x = ev['card']
    if k.get('self') and x is not c: return False
    if not _who_ok(k, ev['player'], p): return False
    if k.get('how') and ev.get('how') != k['how']: return False
    if k.get('prev') and ev.get('prev') not in k['prev']: return False
    f = k.get('filter')
    return f is None or match_card(g, c, p, x, f)


@test('when_to_grave')
def w_to_grave(g, c, p, ev, k):
    """E3 이 카드가 묘지로 보내졌을 때([유언]) — 단서 not_from_field · not_from_deck · not_cost(text.notes).
    [유언] 우선 선언(Game.triggers의 lw_grace): 같은 선언 차례의 앞 발동 코스트로 묘지를 떠나도 발동한다(재정 로그 2)"""
    if not (ev_kind(ev, 'to_grave') and ev['card'] is c and (c.zone == 'grave' or c.uid in getattr(g, 'lw_grace', ()))): return False
    if k.get('not_from_field') and ev['prev'] in FIELD_Z: return False
    if k.get('not_from_deck') and ev['prev'] in ('main', 'upper'): return False
    ca = ev.get('cause') or ('', None)
    if k.get('not_cost') and ca[0] == 'cost' and ca[1] is c: return False
    if k.get('released') and not ev.get('released'): return False
    if k.get('by_opp'):   # 「이 카드가 상대에 의해 자신의 묘지로 보내진 경우」 — 원인 카드(효과 · 코스트 · 전투)의 컨트롤러가 상대
        src = ca[1] if len(ca) > 1 else None
        if not (isinstance(src, Card) and src.controller != p): return False
    return True


@test('when_phase')
def w_phase(g, c, p, ev, k):
    """E4 시점 — phase 'start'(턴 시작 시) · 'end'(종료 단계가 되었을 때 · 턴 종료 시), whose 'own' · 'opp' · 'both'"""
    if k['phase'] == 'end':
        if not ev_kind(ev, 'end_phase'): return False
        tp = ev['player']
    elif k['phase'] == 'end_step':   # 「종료 단계(페이즈)가 되었을 때」 — 종료 단계에 들어설 때([지속] 종료 처리 · 「턴 종료 시」보다 먼저)
        if not (ev_kind(ev, 'phase') and ev['phase'] == '종료'): return False
        tp = g.turn_player
    else:
        if not (ev_kind(ev, 'phase') and ev['phase'] == '준비'): return False
        tp = g.turn_player
    w = k.get('whose', 'both')
    return w == 'both' or (w == 'own') == (tp == p)


@test('when_battle_win')
def w_battle_win(g, c, p, ev, k):
    """[전투] 이 카드(몬스터가 아닌 카드는 자신의 몬스터 — 재정 격투가 1)가 전투로 카드를 파괴했을 때 (엔진 battle_win, §7)"""
    if not ev_kind(ev, 'battle_win'): return False
    return ev['player'] == p if k.get('any_own') else ev['card'] is c


@test('when_destroyed')
def w_destroyed(g, c, p, ev, k):
    """E3 파괴되었을 때 — who: 파괴된 카드의 쪽(파괴 직전 컨트롤러), filter, zone(파괴 직전 위치)"""
    if not ev_kind(ev, 'destroyed'): return False
    ctrl = ev.get('ctrl', ev['card'].controller)
    if not _who_ok(k, ctrl, p): return False
    if k.get('zone') and ev.get('prev') not in k['zone']: return False
    f = k.get('filter')
    return f is None or match_card(g, c, p, ev['card'], f)


def last_link(g, p, k):
    """E2 응답할 발동 — 체인의 마지막 발동이 조건(who · card_only · sub · from_zone)에 맞으면"""
    if not g.chain: return None
    lk = g.chain[-1]
    if lk.negated or not _who_ok(k, lk.player, p): return None
    if k.get('card_only') and not getattr(lk.eff, 'spell_act', False): return None
    if k.get('sub') and not (getattr(lk.eff, 'spell_act', False) and lk.card.type == '마법'
                             and lk.card.d.get('subtype') in tuple(SPELL_SUB.get(s, s) for s in k['sub'])): return None
    if k.get('from_zone') and lk.ctx.get('from_zone') not in k['from_zone']: return None
    return lk


@test('when_activated')
def w_activated(g, c, p, ev, k):
    """E2 발동했을 때(체인 응답, Effect.kind 'resp'). moves_off: 「자신 필드의 카드를 필드에서 벗어나게 하는 효과」(cards.moves_off_field — 재정 10-20 Q4)"""
    lk = last_link(g, p, k)
    if lk is None: return False
    if k.get('moves_off'):
        from cards import moves_off_field
        return moves_off_field(g, lk, p)
    return True


@block('keep_link')
def keep_link(g, c, p, l, k):
    """코스트 단계: 응답한 발동을 기록 — 처리 블록이 「그 효과 · 그 발동」(l.ctx['evlink'])으로 쓴다"""
    lk = last_link(g, p, k)
    if lk is None: return False
    l.ctx['evlink'] = lk
    return True


# ═══════════════════════ 점수 시점 보정 (B안) ═══════════════════════
def timing(g, c, p, ev, info, v):
    """효과 점수 = 시점 보정 × 블록 가치 합. 시점이 정해진 효과(트리거 · [소환] · [유언] · [전투] · 응답)는 그대로.
    [신속]은 언제 쓰는가가 판단이다: 자신 턴 진행 · 정비 단계(체인 없음)에는 그대로, 상대 발동에 응답할 때는 상대 카드를 없애거나 무효로 하는
    효과(disrupt)만, 자신 전투 단계에는 방해 효과만(상대 몬스터를 치우고 공격), 상대 턴에는 방해 효과를 줄여서 · 상대 종료 단계에는 자원 효과를 줄여서"""
    if info['kind'] == 'lastwill': v = lw_alt(g, c, p, ev, v)
    if info['kind'] == 'trigger' and c.zone == 'hand':
        v = yields(g, c, p, ev, info.get('num'), v)
        if v > 0 and info.get('self_ss'): v = zone_share(g, c, p, v)
    if info.get('places') and c.zone == 'hand': v += place_gain(g, c, p)   # 지속 · 필드 마법의 카드의 발동 — 처리하고 앞면으로 남는다
    if v <= 0 or info['kind'] != 'quick' or info.get('aware') or info.get('phase_only'): return v   # 쓸 수 있는 단계가 정해진 효과는 그때 쓴다
    if any(lk.card is c and lk.eff.num == info.get('num') for lk in g.chain): return 0.0   # 같은 효과를 체인에 거듭 쌓지 않는다(앞 발동이 처리되면 형세가 바뀐다)
    own = g.turn_player == p
    if g.chain and g.chain[-1].player != p: return v if info['disrupt'] else 0.0
    if own:
        if g.phase in ('진행', '정비') and not g.chain: return v
        return 0.8 * v if g.phase == '전투' and info['disrupt'] else 0.0
    if g.phase == '종료': return 0.6 * v
    return 0.7 * v if info['disrupt'] else 0.0


def wants_cost(g, c, p, l, k):
    """「…하고 발동할 수도 있다」 코스트를 낼지 — 코스트 가치 + 그 코스트로 더 얻는 처리(k['gain'])의 가치가 양수일 때"""
    ev = l.ctx.get('ev')
    return BLOCKS[k['blk']].val(g, c, p, ev, k) + v_steps(g, c, p, ev, k.get('gain', ())) > 0


def wants(g, c, p, l, b):
    """「…할 수 있다」 처리를 할지 — 그 블록의 가치가 양수일 때"""
    return BLOCKS[b.name].val(g, c, p, l.ctx.get('ev'), b.k) > 0


# ═══════════════════════ 사건 · 조건 (추가) ═══════════════════════
@test('when_hand_added')
def w_hand_added(g, c, p, ev, k):
    """E3 「패에 넣었을 때」 — 효과로 덱 · 묘지에서 패에 넣기 + 드로우(턴 시작 드로우 포함 — 사용자 답변 2026-10-28, cards.hand_add).
    who: 넣은 플레이어, src: 출발 영역 ('deck' = 메인 · 상급), self: 이 카드가, filter"""
    from cards import hand_add
    h = hand_add(ev)
    if h is None: return False
    x, q, prev = h
    if k.get('self') and x is not c: return False
    if not _who_ok(k, q, p): return False
    src = k.get('src')
    if src is not None:
        z = ('main', 'upper') if src == 'deck' else (src,) if isinstance(src, str) else src
        if prev not in z: return False
    if k.get('still', True) and x.zone != 'hand': return False
    f = k.get('filter')
    return f is None or match_card(g, c, p, x, f)


@test('when_any')
def w_any(g, c, p, ev, k):
    """여러 사건 중 하나 (「…넣거나 특수소환했을 때」)"""
    return any(TESTS[b.name](g, c, p, ev, b.k) for b in k['of'])


@test('cond_ref_in')
def t_ref_in(g, c, p, l, k):
    """J2 분기: 앞에서 남긴 값(주사위 눈 등)이 vals 중 하나인가 — 처리 때 l(Link)을 받는다"""
    return refs(l).get(k['ref']) in k['vals']


@block('roll')
def do_roll(g, c, p, l, k):
    """주사위 — 눈을 k['as']로 남긴다"""
    d = g.rng.randint(1, k.get('sides', 6)); refs(l)[k['as']] = d; g.L(f'주사위: {d}')
    return True


def can_negate_chain(g, c, p, ev, k):
    """「「X」의 효과를 무효로 한다」: 처리를 기다리는 X의 효과가 있어야(그 카드가 이 효과를 받을 때) — from_zone만이면 늘"""
    if not k.get('name'): return True
    return any(not lk.negated and _link_ok(lk, k, g, c, p) and not g.link_unaffected(lk, c) for lk in g.chain)


def v_negate_chain(g, c, p, ev, k):
    """무효로 할 발동의 위협도 합 — 상대 것은 +, 자신 것은 −(앞선 처리 대기 효과 전부를 무효로 하면 자신 것도 사라진다)"""
    return sum(lk.eff.threat * (1 if lk.player != p else -1) for lk in g.chain if not lk.negated and _link_ok(lk, k, g)) / 10.0


@block('negate_chain', can=can_negate_chain, val=v_negate_chain, threat=900)
def do_negate_chain(g, c, p, l, k):
    """A12 발동 무효 — 이 발동보다 먼저 체인에 오른 발동 중 조건(from_zone 등)에 맞는 것 전부"""
    idx = g.chain.index(l) if l in g.chain else len(g.chain)
    done = 0
    for lk in g.chain[:idx]:
        if not lk.negated and _link_ok(lk, k, g, c, p):
            g.negate(lk, by=c); done += lk.negated
    return done > 0


def _link_ok(lk, k, g=None, c=None, p=None):
    """체인의 발동 lk가 조건에 맞는가 — from_zone(그 효과를 발동한 위치) · name(「「X」의 효과」: X 카드의 발동, 또는 X의 효과 변경으로 바뀐 발동 — flags['replace_pending'])"""
    if k.get('from_zone') and lk.ctx.get('from_zone') not in k['from_zone']: return False
    if k.get('name'):
        if lk.card.name == k['name']: return True
        return g is not None and any(x.name == k['name'] and x.flags.get('replace_pending') is lk and not (c is not None and g.immune(x, p, c))
                                     for x in g.all_field())
    return True


def want_pick(g, c, p, pool, k):
    """「원하는 수까지」 — AI: 같은 이름이 2장 이상인 카드의 여분(1장은 남김) 중 덱 지침 우선순위가 0 이하인 것"""
    ai = g.p[p].ai; by = {}
    for x in pool: by.setdefault(x.name, []).append(x)
    return [x for xs in by.values() if len(xs) >= 2 for x in xs[1:] if ai.card_pri(g, p, x) <= 0]


# ═══════════════════════ A17 상태 · 보정 (처리 모드) ═══════════════════════
# 카드에 거는 상태: 종류 → (기간별 플래그). 기간 'turn' = 턴 종료 시까지, 'next' = 다음 턴 종료 시까지, 'perm' = 필드에 있는 동안
CARD_STATUS = {
    'immune_opp': {'turn': 'immune_opp_until', 'next': 'immune_opp_until', 'perm': 'immune_opp_perm'},   # 상대의 효과를 받지 않는다
    'immune_all': {'turn': 'immune_all_until', 'next': 'immune_all_until'},                              # 다른 카드의 효과를 받지 않는다
    'no_release': {'turn': 'no_release_until', 'next': 'no_release_until'},                              # 릴리스할 수 없다
    'battle_indestr': {'turn': 'battle_indestr_until', 'next': 'battle_indestr_until'},                  # 전투로는 파괴되지 않는다
    'no_pos_change': {'turn': 'no_pos_change_until', 'next': 'no_pos_change_until'},                    # 표시 형식을 변경할 수 없다
    'no_attack': {'turn': 'no_attack_until', 'next': 'no_attack_until'},                                 # 공격할 수 없다
    'no_act': {'turn': 'no_act_until'},                                                                   # 이 턴에 효과를 발동할 수 없다(build — 모든 조립 효과의 발동 조건)
}
PROTECT = ('immune_opp', 'immune_all', 'no_release', 'battle_indestr')


def v_status(g, c, p, ev, k):
    """보호 상태는 상대가 위협적인 효과를 발동했을 때 크고, 그 밖에는 작다. 상대 카드를 묶는 상태(공격 불가 등)는 그 카드 가치의 일부"""
    xs = preview(g, c, p, ev, k)
    if not xs: return 0.0
    if k['kind'] in PROTECT:
        lk = g.chain[-1] if g.chain else None
        danger = 1.0 if lk is not None and lk.player != p and lk.eff.threat >= 800 else 0.1
        return danger * sum(value(g, x) for x in xs if g.side_of(x) == p) * UNIT
    return 0.3 * v_loss(g, p, xs)


@block('status', can=can_subjects, val=v_status, threat=500)
def do_status(g, c, p, l, k):
    """A17 상태 · 보정 — 카드에 상태를 건다(CARD_STATUS). 그 효과를 받지 않는 카드에는 걸 수 없다(Game.blocked)"""
    key = CARD_STATUS[k['kind']][k.get('until', 'turn')]
    until = k.get('until', 'turn')
    def f(x):
        if not g.on_field(x) or g.blocked(x, ('effect', c)): return False
        x.flags[key] = True if until == 'perm' else g.turn + (1 if until == 'next' else 0)
        col = dict(x.flags.get('clear_on_leave') or {}); col.setdefault(key, None); x.flags['clear_on_leave'] = col   # 필드를 벗어나면 풀린다
        g.L(f'{x}: {k.get("label", k["kind"])} ({"필드에 있는 동안" if until == "perm" else "다음 턴 종료 시까지" if until == "next" else "턴 종료 시까지"})')
        return True
    return _each(g, c, p, l, k, f)


def v_no_damage(g, c, p, ev, k):
    can_hit = g.can_declare_attack(p) and any(m.faceup and m.pos == 'atk' for m in g.monsters(p))
    return -UNIT if can_hit else 0.0


@block('no_damage', val=v_no_damage, threat=0)
def do_no_damage(g, c, p, l, k):
    """플레이어 규칙 「이 턴에, 자신은 상대에게 대미지를 입힐 수 없다」 · until='next_own': 「다음 자신 턴 종료 시까지」"""
    end = g.turn + ((2 if g.turn_player == p else 1) if k.get('until') == 'next_own' else 0)
    g.no_damage[p] = max(g.no_damage.get(p, -1), end); g.L(f'{"다음 자신 턴 종료 시" if end > g.turn else "이 턴 종료 시"}까지 {g.pname(p)}은(는) 상대에게 대미지를 줄 수 없음'); return True


# ═══════════════════════ A8 장착 ═══════════════════════
def v_equip(g, c, p, ev, k):
    xs = preview(g, c, p, ev, k)
    v = 0.8 * v_loss(g, p, [x for x in xs if g.side_of(x) != p]) if k.get('negate') else 0.0
    if k.get('on_leave'): v += 0.5 * v_steps(g, c, p, ev, k['on_leave'])   # 장착 대상이 떠날 때 얻는 것(맵시기생벌)
    return v


def can_equip(g, c, p, ev, k):
    return (not k.get('from_hand') or bool(g.free_s(p))) and can_subjects(g, c, p, ev, k)


@block('equip', can=can_equip, val=v_equip, threat=700)
def do_equip(g, c, p, l, k):
    """A8 장착 — 이 카드를 장착 마법 카드 취급으로 ref의 몬스터에 장착한다. negate: 장착되어 있는 한 그 몬스터의 효과를 무효(flags['negates_host'])"""
    xs = subjects(g, c, p, l, k)
    if not xs: return False
    t = xs[0]
    if k.get('from_hand'):   # 「이 카드를 패에서 … 장착 마법 카드 취급으로 장착」(맵시기생벌) — 마법 존에 놓는다
        if c.zone != 'hand' or not g.free_s(p) or not g.on_field(t): return False
        g._remove(c); g.place_spell(c, p, True); c.flags['as_spell'] = True
    if not (g.on_field(t) and g.on_field(c)) or g.blocked(t, ('effect', c)): return False
    c.flags['stay'] = True; c.equip_to = t; t.equips.append(c)
    if k.get('on_leave'):   # 「이 카드가 장착된 몬스터가 필드에서 벗어났을 경우, …」 (engine._remove의 on_host_leave)
        steps = k['on_leave']
        def host_leave(g, e, host, steps=steps):
            g.L(f'{e} 장착 몬스터 {host} 이탈 → 처리', 'sys'); steps_run(g, e, e.controller, steps)
        c.on_host_leave = host_leave
    if k.get('negate'):
        c.flags['negates_host'] = True
        g.L(f'{c}를 {t}에 장착 — 효과 무효'); g.emit('negated', link=None, card=t, player=t.controller, by=c)
    else:
        g.L(f'{c}를 {t}에 장착')
    return True


# ═══════════════════════ J2 고르기(선택지) ═══════════════════════
def opt_ok(g, c, p, ev, steps):
    for b in steps:
        if b.name == 'branch' or b.k.get('may'): continue
        bd = BLOCKS[b.name]
        if not bd.can(g, c, p, ev, b.k): return False
        break   # 선택지의 첫 처리만 미리 본다 (뒤 처리는 앞 처리 결과에 달림)
    return True


def opt_val(g, c, p, ev, steps):
    return sum(BLOCKS[b.name].val(g, c, p, ev, b.k) for b in steps if b.name in BLOCKS)


@test('cond_any_option')
def t_any_option(g, c, p, ev, k):
    return any(opt_ok(g, c, p, ev, o) for o in k['options'])


def best_option(g, c, p, l, k):
    """「A하거나 B한다」 — 할 수 있는 선택지 중 가치가 가장 큰 것(효과를 쓰는 플레이어가 고름). 없으면 -1"""
    ev = l.ctx.get('ev'); best, bv = -1, None
    sign = -1.0 if k.get('chooser') == 'opp' else 1.0   # 「상대는 …하거나 …한다」 — 상대가 자신에게 나은(효과를 쓴 쪽에 나쁜) 쪽을 고른다
    for i, o in enumerate(k['options']):
        if not opt_ok(g, c, p, ev, o): continue
        v = sign * opt_val(g, c, p, ev, o)
        if bv is None or v > bv: best, bv = i, v
    if best >= 0 and len(k['options']) > 1:
        g.L(f'판단[{g.pname(p if sign > 0 else 1 - p)}] {c.name}: 선택지 {best + 1}', 'decision')
    return best



# ═══════════════════════ 번성충에서 더한 블록 ═══════════════════════
@block('oath')
def do_oath(g, c, p, l, k):
    """플레이어 규칙 「이 효과를 발동한 턴, 자신은 「X」 카드만 사용할 수 있으며, 이 제약은 다음 상대 턴 종료 시까지 적용된다」 — 발동할 때(코스트 칸)"""
    import cards
    cards.oath(g, p, k['group']); return True


def steps_run(g, c, p, steps, ev=None, src=None):
    """처리 블록 목록을 체인 밖에서 처리한다([지속] 종료 처리 · 지연 효과 · 장착 해제 등) — 처리 중인 효과의 주체는 src(기본 c)"""
    from engine import Link
    from blocks import build
    fn = build.steps_fn(steps)
    l = Link(c, None, p, {'ev': ev})
    prev = (g.src, getattr(g, 'src_eff', None)); g.src, g.src_eff = (src or c), None
    try: g.deferring_hp(fn, g, c, p, l)
    finally: g.src, g.src_eff = prev


def v_steps(g, c, p, ev, steps):
    return sum(BLOCKS[b.name].val(g, c, p, ev, b.k) for b in steps if b.name in BLOCKS)


FLOAT_TIMES = 1.5    # 「이 턴, …할 때마다」 — 상대 턴에 아직 그 사건이 일어날 기대 횟수


def v_floating(g, c, p, ev, k):
    inner = v_steps(g, c, p, ev, k['steps'])
    likely = g.turn_player != p and g.phase in ('준비', '진행')   # 상대가 소환할 턴이 아직 남았다
    return (FLOAT_TIMES if likely else 0.1) * inner


@block('floating', val=v_floating, threat=200)
def do_floating(g, c, p, l, k):
    """「이 턴, …할 때마다 …한다」 — 이 턴 동안 사건마다 처리하는 지연 효과(Game.floating)"""
    w = k['when']; steps = k['steps']
    def fl(g, ev, c=c, p=p):
        if TESTS[w.name](g, c, p, ev, w.k):
            g.L(f'{c.name}: {ev.get("kind")} 사건 → 처리', 'sys'); steps_run(g, c, p, steps, ev)
    fl.until = g.turn; g.floating.append(fl)
    g.L(f'{c.name}: 이 턴 동안 적용'); return True


def v_replace(g, c, p, ev, k):
    lk = g.chain[-1] if g.chain else None
    if lk is None or lk.player == p: return 0.0
    return lk.eff.threat / 10.0 + v_steps(g, lk.card, lk.player, ev, k['steps']) * -1.0


@block('replace', val=v_replace, threat=700)
def do_replace(g, c, p, l, k):
    """A15 효과 변경 — 응답한 발동(evlink)의 처리를 「…」로 바꾼다. 바뀐 효과는 그 카드 자신의 효과(재정 Q59), 그 발동을 한 플레이어가 처리.
    그 카드가 이 효과를 받지 않으면 바뀌지 않는다(Game.replace — Q59 · Q60)"""
    lk = l.ctx.get('evlink')
    if lk is None: return False
    steps = k['steps']
    if g.replace(lk, lambda g, tl: steps_run(g, tl.card, tl.player, steps, src=tl.card), c):
        g.L(f'{lk.card}의 효과를 「{k.get("label", "…")}」로 변경'); return True
    return False


@block('equip_card', can=lambda g, c, p, ev, k: bool(g.free_s(p)), val=lambda g, c, p, ev, k: v_remove(g, c, p, ev, k), threat=1000)
def do_equip_card(g, c, p, l, k):
    """A8 장착 — ref의 카드를 장착 카드로 취급하여 이 카드에 장착한다(자신 마법 존, flags['as_spell']). 이 카드가 필드를 벗어나면 규칙에 따라 묘지(원래 주인)로"""
    xs = subjects(g, c, p, l, k)
    if not xs or not g.on_field(c) or not g.free_s(p): return False
    t = xs[0]
    if not g.on_field(t) or g.blocked(t, ('effect', c)): return False
    g._remove(t); g.place_spell(t, p, True); t.flags['as_spell'] = True
    t.equip_to = c; c.equips.append(t); g.L(f'{t}을(를) {c}에 장착 카드로 장착'); return True


def can_place(g, c, p, ev, k):
    return bool(pick_pool(g, c, p, k['scope']))


def can_place(g, c, p, ev, k):
    if 'ref' in k:
        xs = [c] if k['ref'] == 'SELF' else [ev['card']] if k['ref'] == 'EV' and isinstance(ev, dict) else []
        return any(x.type == '필드' or g.free_s(p) for x in xs) if xs else True
    pool = pick_pool(g, c, p, k['scope'])
    if not pool: return False
    return any(x.type == '필드' for x in pool) or bool(g.free_s(1 - p if k.get('to') == 'opp' else p))


PLACE_UP = 3.0      # 앞면으로 놓는 지속 · 필드 마법 1장의 가치(카드 가치 단위 — 놓인 동안 [지속] · 효과)


@block('place', can=can_place, val=lambda g, c, p, ev, k: ((HAND_CARD if k.get('set') else PLACE_UP) * UNIT * n_of(k)) if can_place(g, c, p, ev, k) else 0.0, threat=900)
def do_place(g, c, p, l, k):
    """A7 마법 놓기 — 덱 등에서 필드 카드를 골라 발동(필드 존에 앞면) · 마법 카드를 앞면으로 놓기 · 세트(set=True). n장(upto: 있는 만큼)"""
    n = num(l, k.get('n', 1)); done = 0
    for _ in range(n):
        if 'ref' in k:   # 앞에서 정한 그 카드(희생의 성녀 · 기적의 전조)
            pool = [x for x in ref_cards(g, c, p, l, k['ref']) if x.zone not in FIELD_Z and (x.type == '필드' or g.free_s(p))]
            if k.get('ref_scope') is not None: pool = [x for x in pool if x in cards_in(g, c, p, k['ref_scope'])]
        else:
            pool = [x for x in pick_pool(g, c, p, k['scope'], l) if x.type == '필드' or g.free_s(1 - p if k.get('to') == 'opp' else p)]
        if not pool: break
        fresh = [x for x in pool if not any(y.name == x.name for y in g.spells(p))] or pool   # 같은 카드가 이미 있으면 다른 카드를 먼저
        x = g.p[p].ai.pick_search(g, p, fresh, k.get('why') or c.name)
        src = '덱에서 ' if x.zone in ('main', 'upper') else ''
        g._remove(x)
        if x.type == '필드': g.place_field(x, p); g.L(f'{src}{x} 발동')
        else:
            if not g.place_spell(x, 1 - p if k.get('to') == 'opp' else p, not k.get('set')): break
            if k.get('set') and k.get('act_this_turn'): x.flags['act_this_turn'] = g.turn
            g.L(f'{src}{x} {"세트" if k.get("set") else "앞면으로 놓음"}')
        done += 1
    if done and k.get('scope') is not None and any(z in ('main', 'upper', 'deck') for z in _zones(k['scope'])): g.shuffle(p)
    return done == n or (k.get('upto') and done > 0)


def v_no_attack(g, c, p, ev, k):
    o = 1 - p
    if g.turn_player != o or not g.can_declare_attack(o) or g.phase not in ('준비', '진행', '전투'): return -0.5 * UNIT
    pot = sum(g.atk(m) for m in g.battle_cards(o) if m.faceup and m.pos == 'atk')
    if pot >= g.p[p].hp: return LETHAL
    return pot / HP_UNIT - 0.5 * UNIT


@block('no_attack', val=v_no_attack, threat=600)
def do_no_attack(g, c, p, l, k):
    """플레이어 규칙 「이 턴, 상대 플레이어는 몬스터로 공격할 수 없다」"""
    g.no_attack[1 - p] = g.turn; g.L(f'이 턴 {g.pname(1 - p)}는 몬스터로 공격할 수 없음'); return True


@test('when_sent_grave')
def w_sent_grave(g, c, p, ev, k):
    """E3 묘지로 보내졌을 때 — filter(카드) · prev(출발 영역) · ctrl(보내지기 전 컨트롤러 'own' · 'opp') · by('opp_monster' — 상대 필드의 몬스터 카드에 의해)"""
    if not ev_kind(ev, 'to_grave'): return False
    x = ev['card']
    if k.get('prev') and ev.get('prev') not in k['prev']: return False
    if k.get('ctrl') and (ev.get('ctrl') == p) != (k['ctrl'] == 'own'): return False
    f = k.get('filter')
    if f is not None and not match_card(g, c, p, x, f): return False
    if k.get('by') == 'opp_monster':
        ca = ev.get('cause'); src = ca[1] if ca else None
        if not (isinstance(src, Card) and src.type == '몬스터' and src.controller != p and g.on_field(src)): return False
    return True


@block('look')
def do_look(g, c, p, l, k):
    """「덱 위에서 카드 n장을 확인하고」 — 위 n장을 k['as']로 남긴다(옮기지 않음)"""
    lst = getattr(g.p[p], k.get('zone', 'upper'))
    top = lst[-num(l, k.get('n', 1)):] if lst else []
    refs(l)[k['as']] = list(top); g.L(f'{"상급" if k.get("zone", "upper") == "upper" else "메인"} 덱 위 {len(top)}장 확인: {", ".join(map(str, top))}')
    return bool(top)


@block('to_bottom')
def do_to_bottom(g, c, p, l, k):
    """「나머지 카드는 임의의 순서로 덱 아래로 되돌린다」 — 확인한 카드 중 아직 덱에 있는 것"""
    lst = getattr(g.p[p], k.get('zone', 'upper'))
    for x in ref_cards(g, c, p, l, k['ref']):
        if x in lst: lst.remove(x); lst.insert(0, x)
    return True



# ═══════════════════════ 세리에서 더한 것 ═══════════════════════
@test('cond_tax_draw')
def t_tax_draw(g, c, p, ev, k):
    """「자신의 X 덱에서 카드를 n장 제외하고 발동. 자신의 X 덱에서 m장 드로우한다」 — 코스트를 낸 뒤 드로우할 수 있는가(정본 3-6 e, G2).
    델레가토르면 코스트는 상대 덱에서 나가므로(모자라도 발동 — Game.pay_deck_cost) 드로우할 매수만 본다"""
    deck = getattr(g.p[p], k['deck'])
    if g.cost_payer(p) != p: return len(deck) >= k['draws']
    n = 2 * k['n'] if g.rule('cost_double', p) else k['n']
    return len(deck) >= n + k['draws']


# ═══════════════════════ 솔루나에서 더한 것 ═══════════════════════
@block('control', can=can_subjects, val=lambda g, c, p, ev, k: 0.0 if k.get('to', 'opp') == 'opp' else v_remove(g, c, p, ev, k), threat=500)
def do_control(g, c, p, l, k):
    """A9 필드 안 이동 — 컨트롤을 옮긴다(to 'opp' · 'self'). back='turn': 턴 종료 시 원래 컨트롤러에게 돌아온다(「이 효과로 컨트롤이 변경된 카드는 턴 종료 시에 …」).
    새 컨트롤러의 빈 몬스터 존 · 필드 매수 제한은 엔진(Game.change_control)"""
    to = 1 - p if k.get('to', 'opp') == 'opp' else p
    def f(x):
        if not g.on_field(x): return False
        orig = x.controller
        if not g.change_control(x, to) or x.controller != to: return False
        g.L(f'{x} 컨트롤 → {g.pname(to)}')
        if k.get('back') == 'turn':
            x.flags['return_at_end'] = g.turn
            x.end_return = lambda g2, y, o=orig: y.controller != o and g2.change_control(y, o) and g2.L(f'{y} 컨트롤 복귀', 'sys')
        return True
    return _each(g, c, p, l, k, f)


def can_control(g, c, p, ev, k):
    to = 1 - p if k.get('to', 'opp') == 'opp' else p
    return bool(g.free_m(to)) and can_subjects(g, c, p, ev, k)


BLOCKS['control'] = BLOCKS['control']._replace(can=can_control)


@test('when_left_field')
def w_left_field(g, c, p, ev, k):
    """E3 필드를 벗어났을 때 — ctrl(벗어나기 직전 컨트롤러 'own' · 'opp'), filter, cause 'effect'(효과 · 코스트로), by 'opp'(원인 카드의 컨트롤러가 상대)"""
    if not ev_kind(ev, 'leave_field'): return False
    if k.get('ctrl') and (ev.get('ctrl') == p) != (k['ctrl'] == 'own'): return False
    f = k.get('filter')
    if f is not None and not match_card(g, c, p, ev['card'], f): return False
    ca = ev.get('cause') or ('', None)
    if k.get('cause') == 'effect' and ca[0] not in ('effect', 'cost'): return False
    if k.get('by') == 'opp':
        src = ca[1] if len(ca) > 1 else None
        if not (isinstance(src, Card) and src.controller != p): return False
    if k.get('self') and ev['card'] is not c: return False
    return True


@test('when_both_destroyed')
def w_both_destroyed(g, c, p, ev, k):
    """「자신 필드의 A · B 몬스터가 동시에 파괴되었을 때」 — 같은 원인(같은 카드의 효과 · 같은 전투)으로 파괴된 자신 필드의 몬스터에 두 카드군이 모두.
    파괴 사건(destroyed)으로 본다 — 묘지 대신 덱으로 가는 몬스터도 든다(지금 처리하는 사건 묶음 g.cur_evs)"""
    if not ev_kind(ev, 'destroyed'): return False
    evs = getattr(g, 'cur_evs', [])
    dest = {id(e['card']) for e in evs if e['kind'] == 'destroyed'}
    groups = {}
    for e in evs:
        if e['kind'] == 'leave_field' and e['ctrl'] == p and e['prev'] in ('m', 'shared') and id(e['card']) in dest:
            ca = e.get('cause') or ('', None)
            groups.setdefault((ca[0], id(ca[1])), []).append(e['card'])
    a, b = k['groups']
    return any(any(grp(x, a) and x.is_monster() for x in v) and any(grp(x, b) and x.is_monster() for x in v) for v in groups.values())


@test('cond_ev_card')
def t_ev_card(g, c, p, x, k):
    """J2 분기: 사건의 카드가 필터에 맞는가 (처리 때는 l(Link), 발동 판정 때는 사건 dict를 받는다)"""
    ev = x.ctx.get('ev') if hasattr(x, 'ctx') else x
    card = ev.get('card') if isinstance(ev, dict) else None
    return card is not None and match_card(g, c, p, card, k['filter'])


def _act_after(g, p, k):
    """「자신의 「X」 효과의 발동에 이어 상대가 효과를 발동했을 때」 — 체인의 마지막이 상대 발동이고 그 앞이 자신의 「X」 카드 발동"""
    return len(g.chain) >= 2 and g.chain[-1].player != p and g.chain[-2].player == p and grp(g.chain[-2].card, k['after_own_group'])


_w_act = TESTS['when_activated']


@test('when_activated')
def w_activated2(g, c, p, ev, k):
    if k.get('after_own_group') and not _act_after(g, p, k): return False
    return _w_act(g, c, p, ev, k)



def follow_ok(g, c, p, n, opt):
    """딸린 효과(n번)를 이 턴 아직 쓸 수 있는가 — 「n번 효과」도 1턴 1번 제약을 받는다(아츠 2단 구조 재정, 카드명 × 번호)"""
    return opt is None or g.p[p].opt.get((c.name, n), 0) < opt


def follow_use(g, c, p, n):
    g.p[p].opt[(c.name, n)] = g.p[p].opt.get((c.name, n), 0) + 1



@test('cond_all')
def t_all(g, c, p, ev, k):
    """여러 조건이 모두 (「「시아」 · 「시엘」 몬스터가 각각 1장씩 존재할 경우」)"""
    return all(TESTS[b.name](g, c, p, ev, b.k) for b in k['of'])



# ═══════════════════════ 소원의 분수에서 더한 것 ═══════════════════════
@test('cond_ref_true')
def t_ref_true(g, c, p, l, k):
    """J2 분기: 앞에서 남긴 값이 참(「카드를 묘지로 보내고 발동했을 경우」 — 고를 수 있는 코스트를 냈는가)"""
    return bool(refs(l).get(k['ref'])) if hasattr(l, 'ctx') else False


@test('cond_ref_has')
def t_ref_has(g, c, p, l, k):
    """J2 분기: 앞에서 남긴 카드 중 필터에 맞는 것이 있는가(「「행운」 카드가 묘지로 보내졌을 경우」)"""
    if not hasattr(l, 'ctx'): return False
    return any(match_card(g, c, p, x, k['filter']) for x in ref_cards(g, c, p, l, k['ref']))


@test('cond_self_stat_pos')
def t_self_stat_pos(g, c, p, ev, k):
    """「이 카드의 공격력/수비력을 1000 내린다」를 할 수 있는가 — 0에 도달하면 더는 발동할 수 없다(재정)"""
    return g.atk(c) > 0 and g.df(c) > 0


@test('when_activated_ev')
def w_activated_ev(g, c, p, ev, k):
    """E2 발동 사건(체인 응답이 아닌 트리거 — 「…가 마법 카드를 발동했을 때, …」): who · card_only · type"""
    if not ev_kind(ev, 'activate'): return False
    lk = ev['link']
    if not _who_ok(k, ev['player'], p): return False
    if k.get('card_only') and not getattr(lk.eff, 'spell_act', False): return False
    if k.get('type') and lk.card.type != k['type']: return False
    return True


def _destroys(lk):
    """그 발동이 카드를 파괴하는 효과인가 — 조립된 효과는 블록(파괴), 옛 함수는 효과 문장(「파괴한다 · 파괴하고」)"""
    sp = getattr(lk.eff, 'spec', None)
    if sp is not None:
        from blocks import build
        return any(b.name == 'destroy' and b.k.get('ref') != 'SELF' for b in build._flat(list(sp.kw.get('do', ()))))
    import re
    lines, on = [], False
    for x in (lk.card.d.get('text') or '').split('\n'):
        if re.match(r'^\d+\.', x): on = x.startswith(f'{lk.eff.num}.')
        if on: lines.append(x)
    return bool(re.search(r'파괴한다|파괴하고', ' '.join(lines)))


_w_act2 = TESTS['when_activated']


@test('when_activated')
def w_activated3(g, c, p, ev, k):
    if k.get('destroys'):
        lk = last_link(g, p, k)
        if lk is None or not _destroys(lk): return False
    return _w_act2(g, c, p, ev, k)


def kinds_pick(g, c, p, k):
    """「「A」 · 「B」 … 카드를 각각 n장씩」(per) · 「합계 n장 (같은 종류는 1장까지)」(total) — 고를 카드 목록, 못 고르면 None.
    두플리카토르(코스트 매수 2배)면 각각 2n장 · 합계 2n장(같은 종류 2장까지 — ASSUME). 카드 1장은 한 종류에만 쓴다"""
    m = 2 if k.get('cost') and g.rule('cost_double', p) else 1
    pool = [x for x in cards_in(g, c, p, k['scope']) if not g.on_field(x) or value(g, x) <= KINDS_FIELD_MAX]
    ai = g.p[p].ai; out = []
    if 'per' in k:
        for a in k['groups']:
            xs = sorted([x for x in pool if grp(x, a) and x not in out], key=lambda x: (ai.card_pri(g, p, x), value(g, x)))
            if len(xs) < k['per'] * m: return None
            out += xs[:k['per'] * m]
        return out
    total, cap = k['total'] * m, k.get('cap', 1) * m
    left = {a: sum(1 for x in pool if grp(x, a) and x.zone == 'grave') for a in k['groups']}
    for a in sorted(k['groups'], key=lambda a: -left[a]):   # 묘지에 많이 남는 종류부터 · 묘지 카드부터(다른 효과에 쓸 것을 남김)
        xs = sorted([x for x in pool if grp(x, a) and x not in out], key=lambda x: (x.zone != 'grave', ai.card_pri(g, p, x), value(g, x)))
        out += xs[:min(cap, total - len(out))]
        if len(out) >= total: break
    return out if len(out) >= total else None


KINDS_FIELD_MAX = 2.0   # AI: 「자신 필드/묘지에서 … 제외」 코스트에 쓰는 필드의 카드는 카드 가치가 이 이하인 것만(기적의 영웅 같은 큰 카드는 남김)


def kinds_progress(g, c, p, k, without=()):
    """「각각 n장씩」 코스트를 얼마나 모았는가(0 ~ 1) — 종류마다 min(장수, n) / n 의 평균"""
    pool = [x for x in cards_in(g, c, p, k['scope']) if x not in without]
    need = k['per'] * (2 if g.rule('cost_double', p) else 1)
    return sum(min(need, sum(1 for x in pool if grp(x, a))) / need for a in k['groups']) / len(k['groups'])


def v_kinds(g, c, p, ev, k):
    """코스트로 제외하는 카드의 가치 + 다른 효과가 「각각 n장씩」 모으는 카드를 쓰면 그 효과까지 모은 만큼 손해(모은 비율 감소 × 그 효과 점수)"""
    xs = kinds_pick(g, c, p, k) or []
    v = sum(-value(g, x) * UNIT if g.on_field(x) else -0.1 * UNIT for x in xs)
    if not xs or 'per' in k: return v
    for e in list(c.effects) + (list(g.p[p].skill.effects) if g.p[p].skill is not None and g.p[p].skill is not c else []):
        for k2 in getattr(e, 'kinds_costs', ()):
            if 'per' not in k2: continue
            drop = kinds_progress(g, c, p, k2) - kinds_progress(g, c, p, k2, xs)
            if drop > 0: v -= drop * max(0.0, e.score(g, c, p, ev))
    return v


@block('kinds', can=lambda g, c, p, ev, k: kinds_pick(g, c, p, k) is not None, val=v_kinds, threat=0)
def do_kinds(g, c, p, l, k):
    """S1 고르기(종류별 매수) + 이동 — 코스트 「… 카드를 각각 2장씩 제외하고」 · 「합계 3장 제외하고 (같은 종류는 1장까지)」"""
    xs = kinds_pick(g, c, p, k)
    if xs is None: return False
    for x in xs: _move_one(g, c, p, x, k['dest'], _cause(c, k), k)
    g.L(f'{"코스트: " if k.get("cost") else ""}{len(xs)}장 {"제외" if k["dest"] == "banish" else k["dest"]} ({", ".join(x.name for x in xs)})')
    return True


# 사용 후 쉼(효과 틀 F05 — 「이 효과의 사용 후, 다음 턴까지 자신은 이 효과를 사용할 수 없다」): 플레이어 × 카드명 × 번호
def cool_ok(g, c, p, num):
    return getattr(g, '_cool', {}).get((p, c.name, num), -1) < g.turn


def cool_set(g, c, p, num):
    if '_cool' not in g.__dict__: g._cool = {}
    g._cool[(p, c.name, num)] = g.turn + 1
    return True


# A15 효과 변경 [지속](「자신의 「X」 카드의 효과를 「…」로 변경할 수 있다」 — status.k_swap): 처리 때 바꿀지
SWAP_DECK_THIN = 12    # AI: 메인 덱이 이만큼 이하로 얇으면 바꾼다(덱아웃 방지 — 예전 coin_replace_pick과 같은 기준)
SWAP_KEEP = 2 * UNIT   # AI: 원래 효과의 점수가 이 이상이면 바꾸지 않는다


def swapped(g, c, p, l):
    """처리 시작 때: 이 효과를 바꿀 수 있는 [지속](규칙 'effect_swap' — 받는 카드 c)이 있고 AI가 바꾸기로 하면 바뀐 처리만 하고 True.
    바뀐 효과는 그 카드 자신의 효과(재정 Q59)이고 원래 처리는 하지 않는다(코인 1번을 바꾸면 코인은 패에 남는다 — 사용자 답변 2026-10-20)"""
    for src in g.srcs_with('rule:effect_swap'):
        f = src.rules.get('effect_swap')
        if f is None or src.controller != p or not f(g, src, p, c): continue
        if not g.p[p].main or len(g.p[p].main) > SWAP_DECK_THIN: return False
        if l.eff is not None and l.eff.score(g, c, p, l.ctx.get('ev')) >= SWAP_KEEP: return False   # 원래 효과가 큰 것(기적의 영웅 특수소환 등)은 그대로
        if not g.rule('effect_swap', p, c, use=True, choose=False, why=f'{c.name} 효과 변경'): return False
        g.L(f'판단[{g.pname(p)}] {src.name}: {c}의 효과를 「{f.label}」로 변경 (남은 메인 덱 {len(g.p[p].main)}장)', 'decision')
        from blocks import build
        build.steps_fn(f.steps)(g, c, p, l)
        return True
    return False


def deck_pick_grave(g, c, p, l, k):
    """「메인 덱에서 카드 n장을 묘지로 보낸다」(위에서부터가 아님) — AI: [유언] 기대 가치가 큰 카드 · 우선순위 높은 카드"""
    done = 0
    for _ in range(num(l, k.get('n', 1))):
        if not g.p[p].main: break
        x = max(g.p[p].main, key=lambda x: (lw_bonus(g, p, x, 'main'), g.p[p].ai.card_pri(g, p, x)))
        g.deck_to_grave(p, x, c.name); done += 1
    return done > 0


BLOCKS['deck_pick_grave'] = BlockDef('deck_pick_grave', deck_pick_grave, _always, lambda g, c, p, ev, k: 5.0, lambda k: 100)


@test('cond_ev_back')
def t_ev_back(g, c, p, ev, k):
    """「묘지로 보내진 카드에 따라 … 자신 필드에 특수소환 · 놓는다 · 세트한다」를 할 수 있는가 — 몬스터는 특수소환할 수 있어야, 마법은 놓을 자리(필드 마법은 필드 존)"""
    x = ev.get('card') if isinstance(ev, dict) else None
    if x is None: return False
    if x.is_monster(): return g.can_special(x, p)
    return x.type == '필드' or bool(g.free_s(p))


# ═══════════════════════ 저주인형에서 더한 것 ═══════════════════════
@test('cond_counters')
def t_counters(g, c, p, ev, k):
    """C1 조건 — 집합의 카드에 놓인 name 카운터 수의 합 비교(「자신 필드에 저주 카운터가 3개 이상일 경우」)"""
    return _OPS[k.get('op', '>=')](sum(x.counters.get(k['name'], 0) for x in cards_in(g, c, p, k['scope'])) + k.get('plus', 0), k.get('n', 1))


@test('cond_can')
def t_can(g, c, p, ev, k):
    """블록을 지금 처리할 수 있는가(발동 판정 — 분기 안의 처리를 미리 볼 때)"""
    b = k['blk']; return BLOCKS[b.name].can(g, c, p, ev, b.k)


@test('cond_any')
def t_any(g, c, p, ev, k):
    return any(TESTS[b.name](g, c, p, ev, b.k) for b in k['of'])


@test('when_counter')
def w_counter(g, c, p, ev, k):
    """E5 값 변화 「이 카드에 X 카운터가 n개 놓였을 때」 — 놓아서 정확히 n개가 된 순간만(넘어서 n개를 지나치면 발동하지 않음 — 사용자 답변 2026-10-20)"""
    if not (ev_kind(ev, 'counter') and ev['card'] is c and ev['name'] == k['name'] and ev['delta'] > 0): return False
    return ev.get('total', c.counters.get(k['name'], 0)) == k['n']


@test('when_negated')
def w_negated(g, c, p, ev, k):
    """E6 무효화되었을 때 — who: 그 효과(카드)의 플레이어"""
    return ev_kind(ev, 'negated') and _who_ok(k, ev['player'], p)


@block('act_limit', val=lambda g, c, p, ev, k: ACT_LIMIT_VAL if g.turn_player == p else 0.2 * ACT_LIMIT_VAL, threat=700)
def do_act_limit(g, c, p, l, k):
    """플레이어 규칙 「다음 턴, 상대가 발동할 수 있는 효과는 n회로 제한된다」(Game.act_limit)"""
    g.act_limit[1 - p] = (g.turn + 1, num(l, k['n'])); g.L(f'다음 턴 {g.pname(1 - p)}가 발동할 수 있는 효과 {num(l, k["n"])}회로 제한'); return True


ACT_LIMIT_VAL = 3.0 * UNIT   # 다음 턴(상대 턴) 상대의 발동 횟수 제한의 가치 — 자신 턴 종료 단계에 쓸 때(다음 턴이 상대 턴)


WIN_PROGRESS = 15.0 * UNIT   # 「…이 n장 모였을 경우 승리」 — 모은 비율만큼의 가치(결착 전)


@block('win', val=lambda g, c, p, ev, k: LETHAL, threat=1500)
def do_win(g, c, p, l, k):
    """A23 승리 「자신은 게임에서 승리한다」"""
    from engine import GameOver
    raise GameOver(p, f'{g.pname(p)} 특수 승리 ({c.name})')


# ═══════════════════════ 호박옥에서 더한 것 ═══════════════════════
def _alt_use(g, c, p, ev, k):
    """「A하고 발동. A할 수 없는 경우 대신 B하고 …할 수 있다」 — A를 할 수 있으면 A, 아니면 B"""
    a = k['first']; return a if BLOCKS[a.name].can(g, c, p, ev, dict(a.k, cost=k.get('cost', False))) else k['alt']


@block('alt', can=lambda g, c, p, ev, k: any(BLOCKS[b.name].can(g, c, p, ev, dict(b.k, cost=k.get('cost', False))) for b in (k['first'], k['alt'])),
       val=lambda g, c, p, ev, k: BLOCKS[_alt_use(g, c, p, ev, k).name].val(g, c, p, ev, _alt_use(g, c, p, ev, k).k))
def do_alt(g, c, p, l, k):
    b = _alt_use(g, c, p, l.ctx.get('ev'), k)
    return BLOCKS[b.name].run(g, c, p, l, dict(b.k, cost=k.get('cost', False)))


def face_down_one(g, c, t, pos):
    """A18 표시 형식 「뒷면(수비) 표시로 한다」 — 앞면이면 뒷면으로(엔진 set_face_down), 이미 뒷면이면 표시 형식만"""
    if not g.on_field(t) or not t.is_monster(): return False
    if t.faceup:
        if not g.set_face_down(t): return False
        if pos: t.pos = pos
        g.L(f'{t} 뒷면{" 수비" if pos == "def" else ""} 표시'); return True
    if pos and t.pos != pos and not g.blocked(t, ('effect', c)):
        t.pos = pos; g.L(f'{t} 뒷면 수비 표시로'); return True
    return False


@block('face_down', can=can_subjects, val=lambda g, c, p, ev, k: 0.6 * v_remove(g, c, p, ev, k), threat=700)
def do_face_down(g, c, p, l, k):
    return _each(g, c, p, l, k, lambda x: face_down_one(g, c, x, k.get('pos')))


def can_show_set(g, c, p, ev, k):
    return len(pick_pool(g, c, p, k['scope'])) >= k['show'] and bool(g.free_s(p))


@block('show_set', can=can_show_set, val=lambda g, c, p, ev, k: 3.0 * UNIT, threat=400)
def do_show_set(g, c, p, l, k):
    """「덱에서 X n장을 골라 상대에게 보여주고, 상대는 그중 m장을 무작위로 고른다. 그 카드를 자신의 마법 존에 세트한다. 나머지는 덱으로」 —
    고를 매수는 이 카드의 [지속](flags['pick_n'] — 「공유 존에 존재할 경우 상대는 2장을 고른다」)이 바꿀 수 있다. 서로 다른 이름을 먼저 보여 준다(ASSUME)"""
    cs = pick_pool(g, c, p, k['scope'], l)
    if len(cs) < k['show'] or not g.free_s(p): g.L('보여 줄 카드 · 빈 마법 존 없음', 'sys'); return False
    ai = g.p[p].ai; shown = []
    for x in sorted(cs, key=lambda x: -ai.card_pri(g, p, x)):
        if len(shown) < k['show'] and x.name not in [y.name for y in shown]: shown.append(x)
    for x in cs:
        if len(shown) < k['show'] and x not in shown: shown.append(x)
    m = g.flag(c, 'pick_n') or k.get('pick', 1)
    picks = g.rng.sample(shown, min(m, len(shown)))
    g.L(f'{g.pname(p)} 덱에서 {", ".join(map(str, shown))} 공개 → {g.pname(1 - p)} 무작위로 {", ".join(map(str, picks))}', 'decision')
    done = 0
    for x in picks:
        if not g.free_s(p): break
        g._remove(x); g.place_spell(x, p, False); g.L(f'{x} 마법 존에 세트'); done += 1
    g.shuffle(p)
    return done > 0


@test('when_counter_sum')
def w_counter_sum(g, c, p, ev, k):
    """E5 「자신 필드의 X에 놓인 Y 카운터의 합계가 n개 이상이 되었을 때」 — 사건 당시 상태(엔진 counter_snap)로 그 사건 전 · 뒤 합계"""
    if not (ev_kind(ev, 'counter') and ev['name'] == k['name'] and 'snap' in ev): return False
    sc = k['scope']; ok = lambda x, fu, q: q in sides(p, sc.get('side', 'own')) and (fu or sc.get('faceup') is None) and match_card(g, c, p, x, dict(sc, faceup=None))
    after = sum(n for x, n, fu, q in ev['snap'] if ok(x, fu, q))
    hit = any(x is ev['card'] and ok(x, fu, q) for x, n, fu, q in ev['snap'])
    before = after - ev['delta'] if hit else after
    return before < k['n'] <= after


@test('when_hp_below')
def w_hp_below(g, c, p, ev, k):
    """E5 「자신의 HP가 n 이하가 되었을 때」 — 대미지 사건 당시 HP(엔진 hp_after)가 n 초과에서 n 이하로"""
    if not (ev_kind(ev, 'damage') and ev['player'] == p): return False
    after = ev.get('hp_after', g.p[p].hp)
    return after <= k['n'] < after + ev['amount']


@test('when_game_start')
def w_game_start(g, c, p, ev, k):
    return ev_kind(ev, 'game_start')


_w_act3 = TESTS['when_activated']


@test('when_activated')
def w_activated4(g, c, p, ev, k):
    """hit_own: 「자신 필드의 몬스터가 상대의 효과의 대상이 되었을 때 또는 상대가 자신 필드의 카드를 필드에서 벗어나게 하는 효과를 발동했을 때」"""
    if k.get('hit_own'):
        lk = last_link(g, p, k)
        if lk is None: return False
        from cards import moves_off_field
        return any(x.controller == p and g.on_field(x) and x.is_monster() for x in link_targets(lk)) or moves_off_field(g, lk, p)
    return _w_act3(g, c, p, ev, k)


_w_sg = TESTS['when_sent_grave']


@test('when_sent_grave')
def w_sent_grave2(g, c, p, ev, k):
    """battle: 「전투로 파괴했을 때」(묘지로 간 사건이 전투 파괴) · by_opp_battle: 파괴한 몬스터가 상대 필드의 앞면 몬스터"""
    if k.get('battle'):
        if not (ev_kind(ev, 'to_grave') and ev.get('battle') and ev.get('destroyed')): return False
        ca = ev.get('cause') or ('', None)
        a = ca[1] if ca[0] == 'battle' else None
        if not (isinstance(a, Card) and a.controller != p and g.on_field(a) and a.faceup): return False
    return _w_sg(g, c, p, ev, k)


# ═══════════════════════ 포커짐승들에서 더한 것 ═══════════════════════
# 족보 재료 고르기 · 레벨/속성 부여 계획은 조합 탐색 공용 함수(cards8 — 재료 풀 · 족보 찾기 · 부여 계획)를 쓴다.
# 재료 매수 · 상대 카드 사용 여부는 그 효과 문장에서 읽는다(cards8.combo_sizes · combo_opp_ok).
def hand_quick_src(g, p):
    """[지속] 「자신 「X」 몬스터의 [신속] 효과를 패에서도 발동할 수 있다 (1턴에 n번까지)」 — 이 턴 아직 쓸 수 있는 그 카드(규칙 pk_hand_quick)"""
    for s in g.srcs_with('rule:pk_hand_quick'):
        f = s.rules.get('pk_hand_quick')
        if f is None or not f(g, s, p): continue
        lim = getattr(s, 'hand_quick_n', 1)
        if g.p[p].opt.get((s.name, s.hand_quick_num), 0) < lim: return s
    return None


def can_combo(g, c, p, ev, k):
    import cards8
    if c.zone == 'hand' and not k.get('hand_ok') and hand_quick_src(g, p) is None: return False
    return cards8.plan(g, c, p, k['kind']) is not None


def v_combo(g, c, p, ev, k):
    """족보 코스트의 가치(B안): 재료를 잃는 손익(cards8.mat_cost — 상대 카드를 쓰면 이득) — 얻는 것은 처리 블록이 센다"""
    import cards8
    r = cards8.plan(g, c, p, k['kind'])
    return -sum(m.cost for m in r[1]) * UNIT if r else 0.0


def combo_pick(g, c, p, k):
    """족보 코스트의 재료 → [재료] 또는 None. AI는 조합 탐색의 최선(cards8.plan) — 사람 자리는 화면에서 고른다(app/human.py 가 바꿔 씀)"""
    import cards8
    r = cards8.plan(g, c, p, k['kind'], fresh=True)
    return None if r is None else r[1]


def grant_pick(g, p, t):
    """「원하는 레벨과 원하는 속성」을 부여할 때 고르는 (레벨, 속성) — AI는 족보 가치가 가장 큰 것(cards8.plan_grant). 사람 자리는 화면에서"""
    import cards8
    _, lv, at = cards8.plan_grant(g, p, t)
    return lv, at


def joker_pick(g, p, c):
    """짐승조커 「레벨과 속성을 선언한다」 — AI는 족보 가치가 가장 큰 것(cards8.plan_joker). 사람 자리는 화면에서"""
    import cards8
    _, lv, at = cards8.plan_joker(g, p, c)
    return lv, at


@block('combo', can=can_combo, val=v_combo, threat=0)
def do_combo(g, c, p, l, k):
    """족보 코스트 「…를 포함하는 … n장을 릴리스(덱으로 되돌리)고 발동」 — 재료는 AI가 조합 탐색으로 고른다(cards8.plan). 패에서 발동한 것이
    원래 패에서 쓸 수 없는 [신속]이면 패 허가 [지속]의 1턴 횟수를 쓴다(무효화되면 돌려받음 — opt_keys)"""
    import cards8
    sel = combo_pick(g, c, p, k)
    if sel is None: return False
    if l.ctx.get('from_zone') == 'hand' and not k.get('hand_ok'):
        s = hand_quick_src(g, p)
        if s is None: return False
        key = (s.name, s.hand_quick_num)
        l.ctx.setdefault('opt_keys', []).append(key)   # 엔진이 발동 횟수로 센다(무효화되면 돌려받음)
        g.L(f'{s.name}: 패에서 [신속] 발동', 'sys')
    g.L(f'{cards8.KIND_LABEL[k["kind"]]} 완성')
    cards8.pay(g, c, p, sel, cards8.MODE[k['kind']])
    return True


def _mark_plan(g, p):
    import cards8
    return cards8._memo(g, ('mark', p), lambda: cards8.plan_mark(g, p, cards8.mark_cands(g, p)))


def v_grant_la(g, c, p, ev, k):
    import cards8
    v, t, _, _ = _mark_plan(g, p)
    d = v - cards8.best_play(g, p)
    return d * UNIT if t is not None and d > 0.3 else 0.0


@block('grant_la', val=v_grant_la, threat=300)
def do_grant_la(g, c, p, l, k):
    """「그 카드에 원하는 레벨과 원하는 속성을 부여한다」 — 처리 때 족보 가치가 가장 큰 레벨 · 속성(cards8.plan_grant). 필드에 있는 동안만"""
    import cards8
    xs = [x for x in subjects(g, c, p, l, k) if g.on_field(x) and not g.blocked(x, ('effect', c))]
    if not xs: return False
    lv, at = grant_pick(g, p, xs[0])
    return cards8.grant(g, xs[0], lv, at, c) is not False


def v_joker(g, c, p, ev, k):
    import cards8
    v = cards8._memo(g, ('joker', p), lambda: cards8.plan_joker(g, p, c)[0])
    d = v - cards8.best_play(g, p)
    return d * UNIT if d > 0.3 else 0.0


@block('joker', can=lambda g, c, p, ev, k: (bool(g.free_m(p)) or bool(g.free_shared())) and not g.rule('no_special', c, p), val=v_joker, threat=400)
def do_joker(g, c, p, l, k):
    """「레벨과 속성을 선언한다. 이 카드는 해당 레벨과 속성을 가진 몬스터로 취급되어 원하는 자신 필드에 특수소환한다」 — 선언은 족보 가치(cards8.plan_joker)"""
    import cards8
    if not g.on_field(c): g.L(f'{c}이(가) 필드에 없음 — 처리 없음', 'sys'); return False
    lv, at = joker_pick(g, p, c)
    c.flags.pop('clear_on_leave', None)
    c.flags.update(as_monster=True, level_set=lv, attr_set=at)
    g.L(f'{c}: 레벨 {lv} · {at} 속성 선언 — 몬스터로 취급 (공격력 0 / 수비력 0)')
    if g.special_summon(c, p):
        c.flags['stay'] = True
        c.flags['clear_on_leave'] = {'as_monster': None, 'level_set': None, 'attr_set': None}
        return True
    for x in ('as_monster', 'level_set', 'attr_set'): c.flags.pop(x, None)
    return False


def v_take_grant(g, c, p, ev, k):
    import cards8
    ts = cards8.steal_cands(g, p)
    return 1.6 * max(value(g, t) for t in ts) * UNIT if ts else 0.0


@block('take_grant', can=lambda g, c, p, ev, k: True, val=v_take_grant, threat=900)
def do_take_grant(g, c, p, l, k):
    """「상대 필드의 카드 1장을 골라 속성과 레벨을 부여하여 컨트롤을 옮긴다」 — 처리 때 고름(비대상), 부여는 족보 가치(cards8.plan_grant)"""
    import cards8
    ts = cards8.steal_cands(g, p)
    if not ts: g.L('컨트롤을 옮길 상대 카드 없음', 'sys'); return False
    t = g.p[p].ai.pick_target(g, p, ts, 'steal')
    if g.blocked(t, ('effect', c)) or not cards8.take_control(g, t, p): return False
    g.L(f'{t} 컨트롤 획득')
    lv, at = grant_pick(g, p, t)
    cards8.grant(g, t, lv, at, c)
    return True


_w_aev = TESTS['when_activated_ev']


@test('when_activated_ev')
def w_activated_ev2(g, c, p, ev, k):
    """group: 발동한 카드가 「X」 카드(「자신이 「X」 효과를 발동할 때마다」)"""
    if k.get('group') and not (ev_kind(ev, 'activate') and grp(ev['link'].card, k['group'])): return False
    return _w_aev(g, c, p, ev, k)


# ═══════════════════════ 던전마스터에서 더한 것 ═══════════════════════
PRED['turnable'] = lambda g, c, p, x: __import__('cards9').turnable(g, x)   # 「뒷면 표시로 한다」를 받을 수 있는 앞면 카드
PRED['facedown_mon'] = lambda g, c, p, x: g.on_field(x) and not x.faceup and x.is_monster()


@test('cond_self_facedown')
def t_self_facedown(g, c, p, ev, k):
    """「(이 효과는 뒷면 표시일 때만 발동할 수 있다.)」 — 몬스터 존의 뒷면 이 카드"""
    return g.on_field(c) and not c.faceup and c.zone in ('m', 'shared')


@test('cond_ev_was_facedown')
def t_ev_was_facedown(g, c, p, x, k):
    """「뒷면 표시의 이 카드가 묘지로 보내졌을 경우」 — 사건의 was_faceup(보내지기 직전)"""
    ev = x.ctx.get('ev') if hasattr(x, 'ctx') else x
    return isinstance(ev, dict) and not ev.get('was_faceup', True)


@test('cond_not_on_chain')
def t_not_on_chain(g, c, p, ev, k):
    """이 카드의 이 효과가 체인에 아직 있지 않다(이 카드가 처리 전에 다시 같은 효과를 발동할 수 없음 — 어새신 1번 재정)"""
    return not any(lk.card is c and lk.eff.num == k['num'] for lk in g.chain)


@block('flip_up', val=lambda g, c, p, ev, k: 0.0)
def do_flip_up(g, c, p, l, k):
    """뒷면 몬스터를 앞면으로(소환 아님 — 사건 flip). pos: 「앞면 수비 표시로」"""
    import cards9
    xs = [c] if k.get('ref') == 'SELF' else subjects(g, c, p, l, k)
    return any(cards9.flip_up(g, x, c, k.get('pos')) for x in xs)


def v_turn_down(g, c, p, ev, k):
    xs = preview(g, c, p, ev, k)
    return sum((-0.3 if g.side_of(x) == p else 0.7) * value(g, x) * UNIT for x in xs)


@block('turn_down', can=can_subjects, val=v_turn_down, threat=700)
def do_turn_down(g, c, p, l, k):
    """A18 「뒷면 표시로 한다」 — 몬스터는 표시 형식 유지, 마법 존의 마법은 세트 상태로(이 턴에 세트한 것으로), 필드 존은 묘지로(cards9.turn_face_down).
    keep_set: 처리 중인 일반 · 신속 · 트리거 마법을 세트한 채 필드에 남긴다"""
    import cards9
    def f(x):
        was = x.zone == 's'
        ok = cards9.turn_face_down(g, x, c)
        if ok and was and k.get('keep_set'): cards9.keep_set(g, x)
        return ok
    return _each(g, c, p, l, k, f)


def owner_only_card(x):
    return any(getattr(e, 'owner_only', False) and getattr(e, 'facedown_ok', False) for e in x.effects)


def fd_take(g, p, y):
    """상대 필드의 뒷면 카드 y를 자신 필드로 받는 가치 — 원래 주인만 뒷면에서 쓸 수 있는 효과가 있는 상대 소유 카드는 받지 않는다"""
    if y.zone == 'm':
        if owner_only_card(y) and y.owner != p: return None
        return value(g, y) + 0.5
    return max((e.threat for e in y.effects), default=0) / 500


def fd_give(g, p, x):
    """자신 필드의 뒷면 카드 x를 상대 필드로 주는 손해 — 원래 주인만 쓰는 카드는 상대 필드에서도 자신이 쓴다"""
    if x.zone == 'm':
        if owner_only_card(x) and x.owner == p: return -0.5
        return 0.6 * value(g, x) + (0.6 if x.pos == 'def' else 0)
    return max((e.threat for e in x.effects), default=0) / 500


def fd_plan(g, c, p):
    """「필드의 뒷면 표시 카드를 전부 원하는 대로 재배치한다」 AI: 같은 종류 존끼리 자신 ↔ 상대 뒷면 카드 맞바꾸기 중 얻는 가치가 큰 것(재배치 모델은 cards9.swap_cards)"""
    o = 1 - p; out = []
    for z in ('m', 's'):
        mine = [x for x in getattr(g.p[p], z) if x is not None and not x.faceup and not g.immune(x, p, c)]
        theirs = [y for y in getattr(g.p[o], z) if y is not None and not y.faceup and not g.immune(y, p, c)]
        theirs = sorted([(fd_take(g, p, y), y.uid, y) for y in theirs if fd_take(g, p, y) is not None], key=lambda t: (-t[0], t[1]))
        mine = sorted([(fd_give(g, p, x), x.uid, x) for x in mine], key=lambda t: (t[0], t[1]))
        for (gain, _, y), (cost, _, x) in zip(theirs, mine):
            if gain - cost <= 0.3: break
            out.append((x, y, gain - cost))
    return out


@block('rearrange', can=lambda g, c, p, ev, k: any(x for i in (0, 1) for x in g.p[i].m + g.p[i].s if x and not x.faceup),
       val=lambda g, c, p, ev, k: (sum(d for _, _, d in fd_plan(g, c, p)) * UNIT) or -1.0, threat=700)   # 바꿀 것이 없으면 쓰지 않는다
def do_rearrange(g, c, p, l, k):
    import cards9
    plan = fd_plan(g, c, p)
    if not plan: g.L(f'{c.name}: 뒷면 카드 그대로 (바꿀 자리 없음)', 'sys'); return True
    for x, y, _ in plan:
        if cards9.swap_cards(g, x, y):
            g.L(f'{c.name}: 뒷면 카드 맞바꿈 — {g.pname(p)} 필드 ← {y.name} / {g.pname(1 - p)} 필드 ← {x.name} (컨트롤 이동)')
    return True


def flip_val(g, c, p, x):
    """뒷면 몬스터를 앞면으로 뒤집는 가치(AI): 자신 필드는 공격력 만큼(원래 주인만 뒷면에서 쓰는 카드는 뒤집지 않음), 상대 필드는 이번 턴 전투로 이길 수 있고 [지속]이 없을 때만"""
    if x.controller == p:
        if owner_only_card(x) and x.owner == p: return -1.0
        return 2.0 + g.atk(x) / 1000 + (1.3 if x.owner != p else 0)
    if not (g.can_declare_attack(p) and g.phase == '진행'): return -1.0
    if getattr(x, 'state_check', None) or getattr(x, 'on_event', None) or x.rules or getattr(x, 'atk_mod', None): return -1.0
    wall = g.df(x) if x.pos == 'def' else g.atk(x)
    if not any(m.faceup and m.pos == 'atk' and not g.attack_banned(m) and g.atk(m) > wall for m in g.monsters(p)): return -1.0
    return 1.0


def _flip_pool(g, c, p):
    return [x for x in g.monsters(0) + g.monsters(1) if not x.faceup and x.is_monster() and not g.immune(x, p, c)]


@block('flip_pick', can=lambda g, c, p, ev, k: bool(_flip_pool(g, c, p)),
       val=lambda g, c, p, ev, k: max([flip_val(g, c, p, x) for x in _flip_pool(g, c, p)] or [0.0]) * UNIT, threat=300)
def do_flip_pick(g, c, p, l, k):
    """「필드의 뒷면 표시 몬스터 1장을 앞면 표시로 뒤집는다」 — 처리 때 고름(비대상)"""
    import cards9
    cs = _flip_pool(g, c, p)
    if not cs: return False
    return cards9.flip_up(g, max(cs, key=lambda x: (flip_val(g, c, p, x), x.uid)), c)


@block('set_flag', val=lambda g, c, p, ev, k: k.get('val', 1.0) * UNIT)
def do_set_flag(g, c, p, l, k):
    """처리로 이 카드에 붙는 상태(필드를 벗어나면 사라짐) — 카드 단위 설정(status)이 그 상태를 읽는다(헬 1번 뒷문장)"""
    if not g.on_field(c): return False
    c.flags[k['key']] = True
    col = dict(c.flags.get('clear_on_leave') or {}); col.setdefault(k['key'], None); c.flags['clear_on_leave'] = col
    g.L(f'{c}: {k.get("label", k["key"])}'); return True


SHIELD_VAL = 1.5 * UNIT   # 상대 턴(공격 전) 「상대는 전투로 몬스터를 파괴할 수 없다」의 가치


@block('battle_shield', val=lambda g, c, p, ev, k: SHIELD_VAL if g.turn_player != p and g.phase in ('준비', '진행') else 0.3 * SHIELD_VAL, threat=300)
def do_battle_shield(g, c, p, l, k):
    """플레이어 규칙 「(턴 종료 시까지) 상대는 전투로 몬스터를 파괴할 수 없다」 — 이 턴 동안 자신 필드의 몬스터(나중에 나온 것 포함)에 전투 파괴 내성"""
    t0 = g.turn
    def guard(g2):
        for m in g2.monsters(p):
            if m.flags.get('battle_indestr_until', -1) < t0: m.flags['battle_indestr_until'] = t0
    def fl(g2, ev):
        if g2.turn == t0: guard(g2)
    fl.until = t0; g.floating.append(fl); guard(g)
    g.L(f'턴 종료 시까지 {g.pname(1 - p)}: 전투로 몬스터를 파괴할 수 없음'); return True


_w_lf = TESTS['when_left_field']


@test('when_left_field')
def w_left_field2(g, c, p, ev, k):
    """by_effect_of: 'opp' — 상대 카드의 효과(코스트 제외)로 필드의 카드가 필드를 벗어남(「상대가 카드를 효과로 제거할 때마다」)"""
    if k.get('by_effect_of'):
        if not ev_kind(ev, 'leave_field'): return False
        ca = ev.get('cause') or ('', None)
        src = ca[1] if ca[0] == 'effect' else None
        if not (isinstance(src, Card) and (src.controller != p) == (k['by_effect_of'] == 'opp')): return False
        if ev.get('prev') not in FIELD_Z: return False
    return _w_lf(g, c, p, ev, k)


LW_ALT_OFF = [False]   # 바꿀지 판단할 때는 원래 [유언]의 점수만 본다(status.k_lw_replace)


def lw_alt(g, c, p, ev, v):
    """[유언]의 점수: 자신의 [지속]이 그 [유언]을 다른 처리로 바꿀 수 있으면(lw_replace — 암흑의 율법) 둘 중 큰 쪽"""
    if LW_ALT_OFF[0]: return v
    for s in g.field_cards(p) + ([g.p[p].skill] if g.p[p].skill else []):
        steps = getattr(s, 'lw_replace_steps', None)
        if steps and g.cont_active(s): v = max(v, v_steps(g, c, p, ev, steps))
    return v


def place_gain(g, c, p):
    """지속 · 필드 마법 c를 앞면으로 놓는 가치(B안): 그 카드의 [지속] · 효과를 쓸 수 있게 되는 가치. 자신 필드에 이미 같은 카드가 있으면 0,
    다른 자신 필드 마법을 덮어쓰면 줄임, 주인에게 불리한 [지속]이 있는 카드(퇴마의 부적)는 0"""
    if getattr(c, 'cont_forced', None): return 0.0
    if c.type == '필드' and g.fieldz is not None and g.fieldz.controller == p:
        return 0.0 if g.fieldz.name == c.name else UNIT
    if any(x.name == c.name and x.faceup for x in g.spells(p)): return 0.0
    return PLACE_UP * UNIT


# ═══════════════════════ 데이터버그에서 더한 것 ═══════════════════════
def can_act_card(g, c):
    """「이 턴에 효과를 발동할 수 없다」(상태 no_act — 콜로니로 특수소환한 몬스터)가 아니면 True"""
    return c.flags.get('no_act_until', -1) < g.turn


_w_lf2 = TESTS['when_left_field']


@test('when_left_field')
def w_left_field3(g, c, p, ev, k):
    """dest: 벗어난 곳(「필드에서 패로」 — 'hand')"""
    if k.get('dest') and not (ev_kind(ev, 'leave_field') and ev.get('dest') == k['dest']): return False
    return _w_lf2(g, c, p, ev, k)


def v_negate_summon(g, c, p, ev, k):
    x = ev.get('card') if isinstance(ev, dict) else None
    if x is None: return 0.0
    live = any(e.kind == 'summon' for e in x.effects)
    return (value(g, x) + (HAND_CARD if live else 0)) * UNIT


@block('negate_summon', val=v_negate_summon, threat=1000)
def do_negate_summon(g, c, p, l, k):
    """A13 소환 무효 「그 소환을 무효로 하고 파괴한다」(설계도 확정 2026-10-10): 그 소환 사건에 negated — 그 소환의 [소환] 효과는 묻지 않고(엔진 Effect.summon_negate),
    이미 체인에 오른 그 몬스터의 [소환]은 처리하지 않는다(사용 횟수 반환). 몬스터는 파괴(k['destroy'])"""
    ev = l.ctx.get('ev'); x = ev.get('card') if isinstance(ev, dict) else None
    if x is None: return False
    ev['negated'] = True; g.L(f'{x}의 소환 무효')
    for lk in g.chain:
        e2 = lk.ctx.get('ev')
        if lk.card is x and lk.eff.kind == 'summon' and not lk.negated and isinstance(e2, dict) and e2.get('kind') == 'summon' and e2.get('card') is x:
            lk.negated = True
            for kk in lk.ctx.get('opt_keys', []):
                if g.p[lk.player].opt.get(kk): g.p[lk.player].opt[kk] -= 1
            g.L(f'  소환이 무효 — {x}의 {lk.eff.num}번 [소환] 효과는 처리되지 않음', 'sys')
    if k.get('destroy') and g.on_field(x) and x.controller != p: g.destroy(x, ('effect', c))
    return True


def v_mark_turn(g, c, p, ev, k):
    """이 턴 표시의 가치 — extra_ns(「이 턴에, 자신은 한 번 더 일반소환할 수 있다」): 패에서 일반소환할 수 있는 가장 좋은 몬스터를 낼 가치"""
    if k.get('what') == 'extra_ns':
        ms = [x for x in g.p[p].hand if x.type == '몬스터' and not x.flags.get('no_normal') and not x.flags.get('effect_only')]
        return max([value(g, x) * UNIT + mon_extra(g, x, p) for x in ms] or [0.1 * UNIT])
    return k.get('val', 1.0) * UNIT


@block('mark_turn', val=v_mark_turn)
def do_mark_turn(g, c, p, l, k):
    """「이 턴에, …」 — 이 카드에 이 턴 표시(flags[key] = 턴). 카드 단위 설정(status)이 읽는다(패키지 프로그램 — 추가 일반소환)"""
    c.flags[k['key']] = g.turn; g.L(f'{c.name}: {k.get("label", k["key"])}'); return True


def keep_val(g, p, x):
    """자신 필드의 카드 x를 남겨 둘 가치(B안): 카드 가치 + 이 턴 아직 쓸 수 있는 기동 · [신속] 필드 효과의 가치(한 단계)"""
    v = value(g, x) * UNIT
    if _LW_DEPTH[0] or g.side_of(x) != p: return v
    for e in x.effects:
        if e.kind in ('ignition', 'quick') and 'field' in e.zones and getattr(e, 'spec', None) is not None and g.opt_ok(p, x, e) and e.cond(g, x, p, None):
            _LW_DEPTH[0] += 1
            try: v += max(FIELD_FX * UNIT, v_steps(g, x, p, None, getattr(e, 'do_steps', ())))   # 쓸 수 있는 효과가 낼 것(코스트 빼기 전)
            finally: _LW_DEPTH[0] -= 1
    return v


@block('once', val=lambda g, c, p, ev, k: v_steps(g, c, p, ev, k['steps']) if g.p[p].opt.get((c.name, k['num']), 0) < 1 else 0.0)
def do_once(g, c, p, l, k):
    """「이 카드를 발동했을 때, …한다 (발동 선언을 필요로 하지 않는다)」 — 카드의 발동에 딸린 처리, 그 번호로 1턴 1번(이미 했으면 처리 없음, 발동은 됨)"""
    key = (c.name, k['num'])
    if g.p[p].opt.get(key, 0) >= 1: g.L(f'{c.name} {k["num"]}번: 이 턴에 이미 처리함', 'sys'); return True
    g.p[p].opt[key] = g.p[p].opt.get(key, 0) + 1
    from blocks import build
    build.steps_fn(k['steps'])(g, c, p, l)
    return True


TRIG_GUARD = [False]


def yields(g, c, p, ev, num, v):
    """같은 사건 묶음(g.cur_evs)에서 같은 카드의 다른 트리거가 더 큰 가치로 발동할 수 있으면 이 트리거는 양보한다(-1) — 같은 처리를 둘이 다투지 않게"""
    if TRIG_GUARD[0] or not getattr(g, 'cur_evs', None): return v
    TRIG_GUARD[0] = True
    try:
        for e in c.effects:
            if e.num == num or e.kind != 'trigger' or c.zone not in e.zones or getattr(e, 'spec', None) is None or not g.opt_ok(p, c, e): continue
            for ev2 in g.cur_evs:
                if e.cond(g, c, p, ev2) and e.score(g, c, p, ev2) > v: return -1.0
    finally: TRIG_GUARD[0] = False
    return v


def zone_share(g, c, p, v):
    """「패에서 이 카드를 특수소환한다」 트리거들이 빈 몬스터 존을 다툴 때: 지금 같은 사건 묶음으로 발동할 수 있는, 이 카드보다 가치가 큰 다른 패의 카드(이름별)가
    빈 자리 수 이상이면 양보(-1) — 자리를 약한 몬스터가 먼저 차지하지 않게(B안 — 카드 가치 + 가져오는 효과)"""
    free = len(g.free_m(p))
    if free <= 0 or TRIG_GUARD[0] or not getattr(g, 'cur_evs', None): return v
    mine = value(g, c) * UNIT + mon_extra(g, c, p)
    better = set()
    TRIG_GUARD[0] = True
    try:
        for x in g.p[p].hand:
            if x is c or x.name == c.name or x.name in better: continue
            for e in x.effects:
                if e.kind != 'trigger' or 'hand' not in e.zones or not getattr(e, 'self_ss', False) or not g.opt_ok(p, x, e): continue
                if any(e.cond(g, x, p, ev2) for ev2 in g.cur_evs) and value(g, x) * UNIT + mon_extra(g, x, p) > mine:
                    better.add(x.name); break
    finally: TRIG_GUARD[0] = False
    return -1.0 if len(better) >= free else v


def hand_pick_val(g, p, x):
    """서치로 패에 넣을 카드의 가치(B안): 패 1장, 몬스터는 낼 때 가치(카드 가치 + 가져오는 효과)의 절반이 더 크면 그것,
    패에 들어오면 스스로 나오는 카드(「패에 넣어졌을 때 … 특수소환」)는 더, 같은 이름이 이미 패에 있으면 절반"""
    v = HAND_CARD * UNIT
    if x.is_monster(): v = max(v, 0.5 * (value(g, x) * UNIT + mon_extra(g, x, p)))
    for e in x.effects:
        sp = getattr(e, 'spec', None)
        if sp is None or e.kind != 'trigger' or 'hand' not in e.zones or not getattr(e, 'self_ss', False): continue
        ws = list(sp.kw.get('when', ()))
        ws += [b for w in ws if w.name == 'when_any' for b in w.k['of']]
        if any(w.name == 'when_hand_added' and w.k.get('self') for w in ws) and g.opt_ok(p, x, e): v += HAND_CARD * UNIT
    if any(y.name == x.name for y in g.p[p].hand): v *= 0.5
    return v

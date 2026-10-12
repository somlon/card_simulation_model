"""카드 효과 구현. 카드 텍스트 → Effect 객체.
ASSUME 주석 = 규칙명세/재정 목록의 【가정】.
"""
import json, os
from engine import Effect, Game

HERE = os.path.dirname(os.path.abspath(__file__))
POOL = {c['name']: c for c in json.load(open(os.path.join(HERE, 'card_pool.json'), encoding='utf-8'))}
IMPL = {}          # name -> function(card)
RETIRED = set()    # 구현은 남아 있지만 지금 카드 풀에 없는 카드 (카드 DB 교체 2026-10-08 — 다시 올라오면 그대로 쓰인다)

def card(name):
    def deco(fn):
        if name in POOL: IMPL[name] = fn
        else: RETIRED.add(name)
        return fn
    return deco

def grp(x, name):
    """카드군 판정 (카드 자료의 「카드군」 필드). 필드가 없는 옛 형식 카드는 이름에 포함되는지로 본다.
    「기적의 영웅」처럼 효과로 다른 카드군으로도 취급되는 카드는 flags['also_groups']"""
    gs = x.d.get('groups')
    if gs is None: return name in x.name
    return name in gs or (name in x.flags.get('also_groups', ()) and x.zone in ('m', 'shared'))   # 「필드의 이 카드는 … 로도 취급」

class Impl:
    pool = POOL
    @staticmethod
    def attach(c):
        f = IMPL.get(c.name)
        if f: f(c)
        else: c.flags['unimplemented'] = True
        # 같은 이름 예외 자동 표시: 해당 번호 효과 문장에 「동명」 허용 문구나 자기 카드명이 가져오기 · 특수소환 대상으로 적힌 경우
        import re as _re
        for e in c.effects:
            line = next((l for l in c.d['text'].split('\n') if l.startswith(f'{e.num}.')), c.d['text'] if len(c.effects) == 1 else '')
            if _re.search(r'동명의 카드를 (패에 넣을|특수소환할) 수 있다', line) or \
               (f'「{c.name}」' in line and _re.search(r'특수소환|패에 넣', line)):
                e.same_name_ok = True

# ───────────── 공통 헬퍼 ─────────────
def own_turn(g, p): return g.turn_player == p
def main_ok(g, p): return own_turn(g, p) and g.phase in ('진행', '정비') and not g.chain
def opp_cards(g, p): return g.field_cards(1 - p)
def value(g, c):
    if c.is_monster(): return 1 + g.atk(c) / 1000 + (1.5 if c.level >= 8 else 0)
    if c.type == '필드': return 2.2
    if c.d.get('subtype') == '지속' or c.equip_to: return 1.8
    return 1.2 if c.faceup else 1.5
def best(g, cands, p, purpose='remove'):
    return g.p[p].ai.pick_target(g, p, cands, purpose) if cands else None
VETO = -10 ** 6   # AI 점수: 규칙상 발동할 수 있어도 AI는 고르지 않는다 (HeuristicAI는 0 이하, LearnedAI는 이 값 이하를 후보에서 뺀다)
def field_pick(g, p, purpose='remove', pool=None):
    """「필드의 카드」 = 자신 · 상대 양쪽 필드 (§14, §15-1).
    상대 카드가 있으면 그중에서 AI가 고르고, 없으면 손해가 가장 적은 자신의 카드를 고른다"""
    cands = [x for x in (g.all_field() if pool is None else pool) if not g.immune(x, p)]   # 효과를 받지 않는 카드는 고르지 않는다
    opp = [x for x in cands if x.controller != p]
    if opp: return best(g, opp, p, purpose)
    return min(cands, key=lambda x: value(g, x)) if cands else None
def oath(g, p, group='번성충'):
    """「이 효과를 발동한 턴, 자신은 「group」 카드만 사용할 수 있으며, 이 제약은 다음 상대 턴 종료 시까지 적용된다」"""
    g.p[p].oath = g.turn + (1 if own_turn(g, p) else 2); g.p[p].oath_group = group
def last_opp_link(g, p):
    return g.chain[-1] if g.chain and g.chain[-1].player != p else None
def threat(g, p):
    l = last_opp_link(g, p)
    return l.eff.threat if l else 0
def cause_card(ev):
    ca = ev.get('cause')
    return ca[1] if ca else None
def ev_is(ev, kind): return isinstance(ev, dict) and ev.get('kind') == kind


# ═══════════════════════ 번성충 ═══════════════════════
def bsc_common(c):
    c.rules = {'direct_attack': lambda g, src, x: x is src}

@card('번성충-시체송장벌레')
def _(c):
    bsc_common(c)
    def cost(g, c, p, l):
        t = best(g, g.p[1 - p].grave, p, 'banish_grave')
        g.L(f'코스트: 상대 묘지 {t} 제외'); g.banish(t); oath(g, p)
    c.effects = [Effect(1, 'quick', ('hand',),
        cond=lambda g, c, p, ev: bool(g.p[1 - p].grave) and g.can_special(c, p),
        cost=cost, res=lambda g, c, p, l: c.zone == 'hand' and g.special_summon(c, p),
        score=lambda g, c, p, ev: 55 if main_ok(g, p) and g.phase == '진행' else 0, threat=300, label='자체 특수소환')]

@card('번성충-맵시기생벌')
def _(c):
    bsc_common(c)
    def cost(g, c, p, l):
        t = best(g, [m for m in g.monsters(1 - p) if m.faceup], p, 'equip_leave')
        g._remove(c); g.place_spell(c, p, True); c.flags['as_spell'] = True
        c.equip_to = t; t.equips.append(c); l.ctx['t'] = t
        g.L(f'코스트: {c}를 {t}에 장착'); oath(g, p)
    def host_leave(g, e, host):
        g.L(f'{e} 장착 몬스터 {host} 이탈 → 서치 (ASSUME: 즉시 처리)', 'sys')
        g.search(e.owner, lambda x: x.is_monster() and x.has('번성충'), why='맵시기생벌', source=e)
    c.on_host_leave = host_leave
    c.effects = [Effect(1, 'quick', ('hand',),
        cond=lambda g, c, p, ev: any(m.faceup for m in g.monsters(1 - p)) and bool(g.free_s(p)),
        cost=cost, score=lambda g, c, p, ev: 35 if main_ok(g, p) else 0, threat=200, label='상대 몬스터에 장착')]

@card('번성충-먹이바구미')
def _(c):
    bsc_common(c)
    def res(g, c, p, l):
        def fl(g, ev):
            if ev['kind'] == 'summon' and ev['player'] == 1 - p:
                g.L('먹이바구미: 상대 소환 → 번성충 마법 서치', 'sys')
                g.search(p, lambda x: x.type == '마법' and x.has('번성충'), why='먹이바구미')
        fl.until = g.turn; g.floating.append(fl)
    def cost(g, c, p, l): g.send_grave(c, ('cost', c)); oath(g, p)
    c.effects = [Effect(1, 'quick', ('hand',), cost=cost, res=res,
        cond=lambda g, c, p, ev: g.can_search(p, lambda x: x.type == '마법' and x.has('번성충')),   # 서치할 마법이 없으면 발동 불가
        score=lambda g, c, p, ev: 30 if (not own_turn(g, p) and g.phase == '진행' and not g.chain) else 0,
        threat=200, label='상대 소환마다 마법 서치')]

@card('번성충-메뚜기여왕')
def _(c):
    bsc_common(c)
    rel = lambda g, p: [x for x in opp_cards(g, p) if g.releasable(x)]   # 「릴리스되지 않는다」 카드는 코스트로 쓸 수 없다
    def cost(g, c, p, l):
        t = best(g, rel(g, p), p); g.L(f'코스트: 상대 {t}를 제물로'); g.tribute(t, ('cost', c)); oath(g, p)
    c.effects = [Effect(1, 'quick', ('hand',),
        cond=lambda g, c, p, ev: bool(rel(g, p)) and g.can_special(c, p),
        cost=cost, res=lambda g, c, p, l: c.zone == 'hand' and g.special_summon(c, p),
        score=lambda g, c, p, ev: (60 + 10 * max(value(g, x) for x in rel(g, p))) if main_ok(g, p)
              else (15 * threat(g, p) / 500 if last_opp_link(g, p) and last_opp_link(g, p).card in rel(g, p) and threat(g, p) >= 900 else 0),
        threat=1000, label='상대 카드 제물 + 자체 특수소환')]

@card('번성충-노린재')
def _(c):
    bsc_common(c)
    def cost(g, c, p, l):
        l.ctx['t'] = g.chain[-1]; g.send_grave(c, ('cost', c)); oath(g, p)
    def res(g, c, p, l):
        t = l.ctx['t']
        t.replaced = lambda g, tl: g.draw(tl.player, 1)
        g.L(f'{t.card}의 효과를 「상대는 1장 드로우」로 변경')
    c.effects = [Effect(1, 'resp', ('hand',), cond=lambda g, c, p, ev: last_opp_link(g, p) is not None,
        cost=cost, res=res, score=lambda g, c, p, ev: 50 if threat(g, p) >= 800 else 0, threat=700, label='효과 치환')]

@card('번성충-넓적배사마귀')
def _(c):
    """2026-10-08 텍스트: 1. [신속] 상대 필드의 몬스터 1장을 대상으로 하고 발동. 이 카드를 패에서 특수소환한다.
    그 카드를 장착카드로 취급하여 이 카드에 장착한다. (맹세 제약 문구 없음)
    ASSUME: 장착된 상대 몬스터는 자신 마법 존의 장착 카드(장착 마법 취급)가 되고, 이 카드가 필드를 벗어나면 규칙에 따라 묘지(원래 주인)로 간다"""
    bsc_common(c)
    def cands(g, p): return [m for m in g.monsters(1 - p) if not g.immune(m, p)]
    def cost(g, c, p, l):
        l.ctx['t'] = best(g, cands(g, p), p, 'steal'); g.L(f'대상: {l.ctx["t"]}')
    def res(g, c, p, l):
        t = l.ctx['t']
        if c.zone != 'hand' or not g.special_summon(c, p): return
        if not (g.on_field(t) and t.controller == 1 - p and g.free_s(p)) or g.blocked(t, ('effect', c)): return
        g._remove(t); g.place_spell(t, p, True); t.flags['as_spell'] = True
        t.equip_to = c; c.equips.append(t); g.L(f'{t}을(를) {c}에 장착 카드로 장착')
    c.effects = [Effect(1, 'quick', ('hand',),
        cond=lambda g, c, p, ev: bool(cands(g, p)) and g.can_special(c, p) and bool(g.free_s(p)),
        cost=cost, res=res,
        score=lambda g, c, p, ev: (40 + max(g.atk(m) for m in cands(g, p)) / 50) if main_ok(g, p) else
              (35 if threat(g, p) >= 900 and last_opp_link(g, p).card in cands(g, p) else 0),
        threat=1000, label='상대 몬스터를 장착 카드로')]

@card('번성충-주기매미')
def _(c):
    bsc_common(c)
    def res(g, c, p, l):
        for i in (0, 1):
            for x in list(g.p[i].grave): g.to_deck(x)
        g.shuffle(0); g.shuffle(1); g.L('서로의 묘지 전부 덱으로')
    c.effects = [Effect(1, 'quick', ('hand',), cost=lambda g, c, p, l: (g.send_grave(c, ('cost', c)), oath(g, p)) and None,
        res=res, score=lambda g, c, p, ev: 25 if len(g.p[1 - p].grave) >= 6 and len(g.p[p].grave) <= 2 else 0, threat=600)]

@card('번성충-장수말벌여왕')
def _(c):
    bsc_common(c)
    tg = lambda g, p: [x for x in g.spells(1 - p) if g.releasable(x)]
    def cost(g, c, p, l):
        t = best(g, tg(g, p), p); g.L(f'코스트: 상대 마법 {t} 릴리스'); g.tribute(t, ('cost', c)); oath(g, p)
    c.effects = [Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: bool(tg(g, p)) and g.can_special(c, p),
        cost=cost, res=lambda g, c, p, l: c.zone == 'hand' and g.special_summon(c, p),
        score=lambda g, c, p, ev: 55 if main_ok(g, p) else (40 if last_opp_link(g, p) and last_opp_link(g, p).card in tg(g, p) else 0),
        threat=900, label='상대 마법 릴리스 + 자체 특수소환')]

@card('번성충-병정흰개미')
def _(c):
    bsc_common(c)
    def res(g, c, p, l):
        f = [x for x in g.deck_cards(p) if x.type == '필드' and x.has('번성충')]
        if not f: return
        g.L(f'덱에서 {f[0]} 발동'); g._remove(f[0]); g.place_field(f[0], p); g.shuffle(p)
    c.effects = [Effect(1, 'quick', ('hand',),
        cond=lambda g, c, p, ev: g.fieldz is not None and g.fieldz.controller == 1 - p and
             any(x.type == '필드' and x.has('번성충') for x in g.deck_cards(p)),
        cost=lambda g, c, p, l: (g.send_grave(c, ('cost', c)), oath(g, p)) and None, res=res,
        score=lambda g, c, p, ev: 60, threat=900, label='필드 교체')]

@card('번성충-하루살이대군')
def _(c):
    bsc_common(c)
    def res(g, c, p, l): g.no_attack[1 - p] = g.turn; g.L(f'이 턴 {g.pname(1-p)}는 몬스터로 공격할 수 없음')
    def sc(g, c, p, ev):
        if not g.can_declare_attack(1 - p): return VETO   # 상대가 이미 공격할 수 없는 턴(선공 1턴째 등)에는 쓰지 않는다
        if own_turn(g, p) or g.phase != '전투' or g.chain: return 0
        pot = sum(g.atk(m) for m in g.monsters(1 - p) if m.faceup and m.pos == 'atk')
        return 70 if pot >= g.p[p].hp * 0.5 or pot >= 2000 else 0
    c.effects = [Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: not own_turn(g, p),
        cost=lambda g, c, p, l: (g.send_grave(c, ('cost', c)), oath(g, p)) and None, res=res, score=sc, threat=600, label='공격 봉인')]

@card('번성충-군체이동')
def _(c):
    def n_max(g, p): return min(6, sum(1 for x in g.p[p].grave if x.is_monster() and x.has('번성충')))
    def pool(g, p): return [x for x in g.monsters(1 - p) if g.releasable(x) and not g.immune(x, p)]
    def cost(g, c, p, l):
        k = min(n_max(g, p), len(pool(g, p)))
        ts = sorted(pool(g, p), key=lambda x: -value(g, x))[:k]; l.ctx['ts'] = ts
        g.L(f'지정: {", ".join(map(str, ts))}')
    def res(g, c, p, l):
        ts = [t for t in l.ctx['ts'] if g.on_field(t) and t.controller == 1 - p]
        for t in ts: g.tribute(t)
        mons = sorted([x for x in g.p[p].grave if x.is_monster() and x.has('번성충')], key=lambda x: -x.base_atk())
        for x in mons[:len(ts)]:
            if not g.special_summon(x, p): break
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True,
        cond=lambda g, c, p, ev: n_max(g, p) > 0 and bool(pool(g, p)), cost=cost, res=res,
        score=lambda g, c, p, ev: 30 + 20 * min(n_max(g, p), len(pool(g, p))), threat=1200)]

@card('번성충-사충보복')
def _(c):
    def cond(g, c, p, ev):
        if not ev_is(ev, 'to_grave'): return False
        x = ev['card']; src = cause_card(ev)
        return (ev['prev'] in ('m', 'shared') and ev['ctrl'] == p and x.has('번성충') and x.type == '몬스터'
                and src is not None and src.type == '몬스터' and src.controller == 1 - p and g.on_field(src))
    def res(g, c, p, l):
        src = cause_card(l.ctx['ev'])
        if src and g.on_field(src): g.destroy(src)
        for _ in range(2): g.search(p, lambda x: x.is_monster() and x.has('번성충'), why='사충보복')
    c.effects = [Effect(1, 'trigger', ('hand', 'field'), spell_act=True, cond=cond, res=res, score=lambda *a: 80, threat=1000)]

@card('번성충-대장정')
def _(c):
    def res(g, c, p, l):
        top = g.p[p].upper[-5:]
        g.L(f'상급 덱 위 5장: {", ".join(map(str, top))}')
        cand = [x for x in top if x.has('번성충')]
        if cand:
            pick = g.p[p].ai.pick_search(g, p, cand, '대장정'); g.to_hand(pick); top.remove(pick); g.L(f'{pick} 패에 넣음')
            rest = [x for x in top if x.is_monster() and x.has('번성충')]
            if rest:
                gy = min(rest, key=lambda x: g.p[p].ai.card_pri(g, p, x)); g.send_grave(gy); top.remove(gy); g.L(f'{gy} 묘지로')
        for x in top:
            if x in g.p[p].upper: g.p[p].upper.remove(x); g.p[p].upper.insert(0, x)
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: bool(g.p[p].upper),
        res=res, score=lambda *a: 45, threat=300)]

@card('번성충-번식지')
def _(c):
    def end_process(g, c):
        """[지속] 각 턴의 종료 시 처리 — 발동이 아니므로 체인 · 우선권 · 1턴 1회 없음 (사용자 재정)"""
        p = c.controller
        cands = [x for x in g.deck_cards(p) if x.has('번성충') and x.name != c.name]   # 자기 자신(번식지)은 서치 불가
        if not cands: g.L('번식지: 대상 없음 — 불발', 'sys'); return
        pick = g.p[p].ai.breeding_pick(g, p, cands)
        g.L(f'번식지 처리: {pick} 패에 넣음'); g.to_hand(pick); g.shuffle(p)
    c.end_process = end_process
    c.effects = [Effect(0, 'ignition', ('hand',), spell_act=True,
                        score=lambda g, c, p, ev: 0 if (g.fieldz and g.fieldz.name == c.name and g.fieldz.controller == p) else 50, threat=600)]

@card('번성충-대발생')
def _(c):
    def mod(g, src, x):
        p = src.controller
        if x.controller != p or not x.is_monster() or not x.has('번성충') or not x.faceup: return 0
        n = sum(1 for y in g.field_cards(p) if y.has('번성충')) + sum(1 for y in g.p[p].grave if y.has('번성충'))
        return 100 * n
    c.atk_mod = mod


# ═══════════════════════ 공용 ═══════════════════════
@card('태양과 달의 마력')
def _(c):
    def tg(g, p): return [x for x in opp_cards(g, p) if not g.immune(x, p)]
    def res(g, c, p, l):
        t = l.ctx['t']
        if g.on_field(t):
            g.banish(t)
            if t.zone == 'banish': g.L(f'{t} 제외')
    e = Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: bool(tg(g, p)),
        cost=lambda g, c, p, l: l.ctx.update(t=best(g, tg(g, p), p)) or g.L(f'고름: {l.ctx["t"]}'), res=res,
        score=lambda g, c, p, ev: 20 + 15 * max(value(g, x) for x in tg(g, p)), threat=900)
    e.unnegatable = True; e.no_resp = True
    c.effects = [e]

@card('바이러스 모스키토')
def _(c):
    def cands(g, p): return [m for m in g.monsters(1 - p) if m.faceup and not g.immune(m, p)]   # 「대상으로 하고」: 효과를 받지 않는 몬스터는 대상이 될 수 없다
    def cost(g, c, p, l):
        t = best(g, cands(g, p), p, 'negate_monster'); l.ctx['t'] = t
    def res(g, c, p, l):
        t = l.ctx['t']
        if g.on_field(t) and g.on_field(c) and not g.blocked(t, ('effect', c)):
            c.flags['stay'] = True; c.equip_to = t; t.equips.append(c); c.flags['negates_host'] = True
            g.L(f'{c}를 {t}에 장착 — 효과 무효'); g.emit('negated', link=None, card=t, player=t.controller, by=c)
    e = Effect(1, 'quick', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: bool(cands(g, p)),
        cost=cost, res=res, score=lambda g, c, p, ev: (35 if main_ok(g, p) else 0) if not last_opp_link(g, p) else
        (45 if last_opp_link(g, p).card.is_monster() and last_opp_link(g, p).card.zone in ('m', 'shared') and threat(g, p) >= 800 else 0), threat=700)
    e.hand_ok = True
    c.effects = [e]


# ═══════════════════════ 솔루나 (본편) ═══════════════════════
def mon(g, pred, p=None): return g.exists_monster(pred, p)
SIA = lambda x: x.has('시아') and x.is_monster()
CIEL = lambda x: x.has('시엘') and x.is_monster()

def ciel_on_field(g): return any(x.faceup and grp(x, '시엘') for x in g.all_field())

def skill_limit(g, p, x):
    """솔루나 아츠 1번: 자신 필드에 시아 · 시엘 몬스터 각 1장"""
    return False

@card('솔루나 시아')
def _(c):
    def res2(g, c, p, l):
        t = field_pick(g, p)   # 「필드의 카드」: 자신 카드 포함
        if t: g.destroy(t)
    def res3(g, c, p, l):
        if ciel_on_field(g): g.negate(l.ctx['t'])   # 3번 「필드에 「시엘」이 있으면」: 처리 시 판정 (양쪽 필드, 「시엘」 카드 — 몬스터에 한하지 않음)
        else: g.L('필드에 「시엘」 없음 — 처리 없음 (재정)', 'sys')
    c.effects = [
        Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: mon(g, CIEL, p) and g.can_special(c, p),
               res=lambda g, c, p, l: c.zone == 'hand' and g.special_summon(c, p),
               score=lambda g, c, p, ev: 65 if main_ok(g, p) else (30 if not own_turn(g, p) and not g.chain and g.phase == '종료' else 0), label='패에서 특수소환'),
        Effect(2, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and mon(g, CIEL, p),
               res=res2, score=lambda g, c, p, ev: 90 if opp_cards(g, p) else VETO, threat=1000, label='파괴'),   # v3: 1턴 1회
        Effect(3, 'resp', ('field',), cond=lambda g, c, p, ev: last_opp_link(g, p) is not None,   # 재정: 시엘이 없어도 발동 선언 가능, 처리 시 없으면 아무 일도 없음
               cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]), res=res3,
               score=lambda g, c, p, ev: 60 if threat(g, p) >= 600 and ciel_on_field(g) else 0, threat=800, label='무효')]

@card('솔루나 시엘')
def _(c):
    def res2(g, c, p, l):
        t = field_pick(g, p, 'bounce')   # 「필드의 카드」: 자신 카드 포함
        if t: g.L(f'{t} 덱으로'); g.to_deck(t)
    def res3(g, c, p, l):
        if g.on_field(c): c.mods.append(('atk', 1000, 'turn')); c.extra_attacks += 1; g.L(f'{c} 공격력 +1000, 추가 공격')
    c.effects = [
        Effect(1, 'quick', ('hand',), cond=lambda g, c, p, ev: mon(g, SIA, p) and g.can_special(c, p),
               res=lambda g, c, p, l: c.zone == 'hand' and g.special_summon(c, p),
               score=lambda g, c, p, ev: 65 if main_ok(g, p) else 0, label='패에서 특수소환'),
        Effect(2, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and mon(g, SIA, p),
               res=res2, score=lambda g, c, p, ev: 90 if opp_cards(g, p) else VETO, threat=1000, label='덱 바운스'),   # v3: 1턴 1회
        Effect(3, 'battle', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'battle_win') and ev['card'] is c,
               res=res3, score=lambda *a: 80, threat=400, label='[전투] +1000·추가 공격')]

def effect_only(c):
    c.flags['effect_only'] = True
    c.grave_redirect = lambda g, x: True

@card('솔루나 시아 - 코로나 이그니스')
def _(c):
    effect_only(c)
    c.effects = [
        Effect(2, 'trigger', ('field',), score=lambda *a: 80,
               cond=lambda g, c, p, ev: ev_is(ev, 'leave_field') and ev['ctrl'] == 1 - p and (ev['cause'] or ('',))[0] in ('effect', 'cost'),
               res=lambda g, c, p, l: g.damage(1 - p, 1000, c.name), threat=500),   # 2026-10-08 텍스트: 예외 · 강제 문구 없음 → 1턴 1번, 임의
        Effect(3, 'resp', ('field',), cond=lambda g, c, p, ev: last_opp_link(g, p) is not None,
               cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]), res=lambda g, c, p, l: g.negate(l.ctx['t'], destroy=True, by=c),
               score=lambda g, c, p, ev: 70 if threat(g, p) >= 500 else 0, threat=900, label='무효 + 파괴')]

@card('솔루나 시엘 - 블러드문 리퍼')
def _(c):
    effect_only(c)
    c.flags['attack_all'] = True
    def res3(g, c, p, l):
        t = best(g, targets_of(g, p, opp_cards(g, p)), p)
        if t: g.banish(t); g.L(f'{t} 제외')
        g.heal(p, 800)
    c.effects = [Effect(3, 'battle', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'battle_win') and ev['card'] is c,
                        res=res3, opt=3, score=lambda *a: 90, threat=900, label='[전투] 제외 + 회복')]

def search_sc(g, p, pred, why):
    return g.search(p, pred, why=why)

@card('솔루나 인카운터')
def _(c):
    def res(g, c, p, l):
        l.ctx['had'] = mon(g, lambda x: grp(x, '솔루나'), p) and second_ok(g, c, p)   # 처리 시 「이미」 존재 = 1번 특수소환 전
        cands = [x for x in g.p[p].main if x.is_monster() and x.has('솔루나') and g.can_special(x, p)]
        if cands:
            x = g.p[p].ai.pick_search(g, p, cands, '인카운터 특수소환'); g.special_summon(x, p)
        if l.ctx['had']:
            use_second(g, c, p)
            conts = [x for x in g.deck_cards(p) if x.has('솔루나') and x.d.get('subtype') == '지속' and not any(y.name == x.name for y in g.spells(p))]
            if conts and g.free_s(p) and g.p[p].ai.prefers_place(g, p, conts):
                x = g.p[p].ai.pick_search(g, p, conts, '인카운터 지속 마법'); g._remove(x); g.place_spell(x, p, True)
                g.L(f'덱에서 {x} 앞면으로 놓음')   # ASSUME 「놓기」는 발동 아님
            else:
                search_sc(g, p, lambda x: x.has('시아') or x.has('시엘'), '인카운터')
        g.shuffle(p)
    e = Effect(1, 'quick', ('hand', 'field'), spell_act=True, res=res,
        cond=lambda g, c, p, ev: any(x.is_monster() and x.has('솔루나') and g.can_special(x, p) for x in g.p[p].main),
        score=lambda g, c, p, ev: 70 if main_ok(g, p) and g.phase == '진행' else 0, threat=600)
    e.hand_ok = True
    c.effects = [e]

@card('솔루나 아츠 - 여명과 황혼의 궤적')
def _(c):
    SOL = lambda m: m.has('솔루나')
    def cost1(g, c, p, l):   # 「자신 필드의 솔루나 몬스터」 (2026-10-08 텍스트)
        t = own_mon(g, p, SOL)[0]
        l.ctx['t'] = t; g.L(f'코스트: {t} 패로'); g.to_hand(t, ('cost', c))
    def res2(g, c, p, l):
        x = l.ctx['ev']['card']
        want = SIA if x.has('시엘') else CIEL
        cands = [y for y in g.p[p].hand + g.p[p].grave if want(y) and g.can_special(y, p)]
        if cands: g.special_summon(cands[0], p)
    c.effects = [
        Effect(0, 'ignition', ('hand', 'field'), spell_act=True, score=lambda g, c, p, ev: 40, threat=300),   # 세트된 카드도 자신 턴에 발동 (솔루나 아츠 2번이 세트)
        Effect(1, 'quick', ('field',), cond=lambda g, c, p, ev: mon(g, SOL, p) and g.can_search(p, lambda x: x.has('시아') or x.has('시엘')),   # [신속]: 자신 · 상대 턴 모두 발동 가능 (§7)
               cost=cost1, res=lambda g, c, p, l: search_sc(g, p, lambda x: x.has('시아') or x.has('시엘'), '여명과 황혼'),
               score=lambda g, c, p, ev: 25 if main_ok(g, p) and g.phase == '정비' else VETO, threat=300),
        Effect(2, 'trigger', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'to_grave') and ev['ctrl'] == p and ev['prev'] in ('m', 'shared')
               and ev['card'].has('솔루나') and ev['card'].type == '몬스터' and (ev['card'].has('시아') or ev['card'].has('시엘')), res=res2,
               score=lambda *a: 70, threat=600)]

@card('솔루나 아츠 - 듀얼 컴뱃')
def _(c):
    def snap(g, c, p, l):
        l.ctx['both'] = mon(g, SIA, p) and mon(g, CIEL, p)   # 발동 시점 판정
    def res(g, c, p, l):
        g.search(p, lambda x: x.has('시아') or x.has('시엘'), which=('main',), why='듀얼 컴뱃')
        if l.ctx['both']: search_sc(g, p, lambda x: x.has('솔루나'), '듀얼 컴뱃 추가')
    c.effects = [Effect(1, 'quick', ('hand', 'field'), spell_act=True, res=res, cost=snap,
        cond=lambda g, c, p, ev: g.can_search(p, lambda x: x.has('시아') or x.has('시엘'), which=('main',)),
        score=lambda g, c, p, ev: 50 if main_ok(g, p) else 0, threat=300)]

@card('솔루나 아츠 - 태양과 달의 가호')
def _(c):
    def res1(g, c, p, l):
        if g.p[p].hand:   # 「패를 1장 버린다」: 처리 문장 — 무효화되면 버리지 않는다
            d = g.p[p].ai.pick_discard(g, p, g.p[p].hand); g.L(f'{d} 버림'); g.send_grave(d)
        cands = [x for x in g.deck_cards(p) if (x.has('시아') or x.has('시엘')) and x.type == '마법']
        if cands and g.free_s(p):
            x = g.p[p].ai.pick_search(g, p, cands, '가호 세트'); g._remove(x); g.place_spell(x, p, False); x.flags['act_this_turn'] = g.turn
            g.L(f'덱에서 {x} 세트 (이 턴 발동 가능)'); g.shuffle(p)
    def res2(g, c, p, l):
        s, e = l.ctx['s'], l.ctx['e']   # 발동 시점 판정
        if s: g.negate(l.ctx['t'])
        if s and e: search_sc(g, p, lambda x: x.has('솔루나'), '가호')
        elif e: search_sc(g, p, lambda x: x.has('솔루나') and (x.d.get('subtype') == '지속' or x.type == '필드'), '가호')
    c.effects = [
        Effect(0, 'ignition', ('hand', 'field'), spell_act=True, score=lambda g, c, p, ev: 45, threat=500),
        Effect(1, 'quick', ('field',), cond=lambda g, c, p, ev: len(g.p[p].hand) >= 1 and bool(g.free_s(p)), res=res1,
               score=lambda g, c, p, ev: 20 if main_ok(g, p) and len(g.p[p].hand) >= 3 else 0, threat=300),
        Effect(2, 'quick', ('field',), cond=lambda g, c, p, ev: any(x.is_monster() and x.has('솔루나') and g.can_special(x, p) for x in g.p[p].main),
               res=lambda g, c, p, l: (lambda cs: cs and g.special_summon(g.p[p].ai.pick_search(g, p, cs, '가호 특수소환'), p))(
                   [x for x in g.p[p].main if x.is_monster() and x.has('솔루나') and g.can_special(x, p)]),
               score=lambda g, c, p, ev: 60 if main_ok(g, p) else (25 if not own_turn(g, p) and g.phase == '종료' else 0), threat=500, label='v3: 메인 덱 솔루나 특수소환')]

@card('솔루나 아츠 - 천체정렬')
def _(c):
    def res1(g, c, p, l):
        conts = [x for x in g.deck_cards(p) if x.has('솔루나') and x.d.get('subtype') == '지속']
        n = min(2, len(conts), len(g.free_s(p)), len(g.p[p].hand))
        for _ in range(n):
            d = g.p[p].ai.pick_discard(g, p, g.p[p].hand); g.send_grave(d, ('cost', c)); g.L(f'{d} 버림')
        for _ in range(n):
            conts = [x for x in g.deck_cards(p) if x.has('솔루나') and x.d.get('subtype') == '지속' and not any(y.name == x.name for y in g.spells(p))] or \
                    [x for x in g.deck_cards(p) if x.has('솔루나') and x.d.get('subtype') == '지속']
            if not conts or not g.free_s(p): break
            x = conts[0]; g._remove(x); g.place_spell(x, p, True); g.L(f'덱에서 {x} 앞면으로 놓음')
        g.shuffle(p)
    e = Effect(1, 'quick', ('hand', 'field'), spell_act=True, res=res1,
        cond=lambda g, c, p, ev: any(x.has('솔루나') and x.d.get('subtype') == '지속' for x in g.deck_cards(p)) and len(g.p[p].hand) >= 2,
        score=lambda g, c, p, ev: 30 if main_ok(g, p) and len(g.p[p].hand) >= 4 else 0, threat=300)
    e.hand_ok = True
    def cost2(g, c, p, l):
        d = next(x for x in g.p[p].hand if x.name == c.name); g.send_grave(d, ('cost', c)); g.banish(c, ('cost', c))
    c.effects = [e, Effect(2, 'quick', ('grave',), cond=lambda g, c, p, ev: any(x.name == c.name for x in g.p[p].hand) and
                          any(x.has('아츠') and x is not c for x in g.p[p].grave),
                          cost=cost2, res=lambda g, c, p, l: g.salvage(p, [x for x in g.p[p].grave if x.has('아츠')], '천체정렬', source=c),
                          score=lambda g, c, p, ev: 25 if main_ok(g, p) else 0, threat=200)]


# ── 아츠 2단 구조 (2026-10-08 텍스트 · 재정): 2번은 「1번 효과 처리 시에 … 존재할 경우」 1번 처리에 자동으로 딸려 처리된다
#    (별도 발동 없음). 2번도 1턴 1회 제약을 받는다 — 이번 턴 2번을 이미 처리했으면 1번만 처리한다.
#    1번이 무효화되면 2번도 처리되지 않는다. 2번 조건은 1번 처리 시점에 판정한다 ──
def second_ok(g, c, p, n=2):
    """「n번 효과 처리 시에 자동 처리」 효과를 이번 턴 아직 쓰지 않았는가 (1턴 1회)"""
    return g.p[p].opt.get((c.name, n), 0) < 1

def use_second(g, c, p, n=2):
    g.p[p].opt[(c.name, n)] = g.p[p].opt.get((c.name, n), 0) + 1

def arts(c, e1cond, e1cost, e1res, e2cond, e2res, sc1=50, sc2=40, kind='quick', trig1=None, hand_ok=False, threat=800):
    def score(g, c, p, ev):
        parts = [sc1(g, c, p, ev) if callable(sc1) else sc1]
        if second_ok(g, c, p) and e2cond(g, c, p): parts.append(sc2(g, c, p) if callable(sc2) else sc2)
        if any(x <= VETO for x in parts): return VETO   # 함께 처리될 효과 중 하나라도 AI가 피하는 경우
        return sum(parts) if (main_ok(g, p) or kind == 'trigger' or (g.chain and threat_ok(g, p))) else 0
    def res(g, c, p, l):
        e1res(g, c, p, l)
        if second_ok(g, c, p) and e2cond(g, c, p):
            use_second(g, c, p); g.L('  2번 처리 (1번 처리 시 조건 충족 — 별도 발동 없음)'); e2res(g, c, p, l)
    cond = (lambda g, c, p, ev: trig1(g, c, p, ev)) if (kind == 'trigger' and trig1 is not None) else e1cond
    E1 = Effect(1, kind, ('hand', 'field'), spell_act=True, cond=cond, cost=e1cost, res=res, score=score, threat=threat)
    E1.hand_ok = hand_ok
    c.effects = [E1]

def threat_ok(g, p): return threat(g, p) >= 900

def opp_magic(g, p):
    """상대 필드의 「마법 카드」 (필드 카드 · 장착 마법 취급 몬스터 제외)"""
    return [x for x in g.p[1 - p].s if x and x.type == '마법']

def targets_of(g, p, cands):
    return [x for x in cands if not g.immune(x, p)]

def own_mon(g, p, pred):
    """코스트용: 가치가 낮은 순 (효과로만 소환되는 상급은 뒤로)"""
    ms = [m for m in g.monsters(p) if m.faceup and pred(m)]
    return sorted(ms, key=lambda m: (m.flags.get('effect_only', False), value(g, m)))
def opp_target(g, c, p, l, purpose='remove'):
    t = best(g, targets_of(g, p, opp_cards(g, p)), p, purpose); return t   # 효과를 받지 않는 카드 제외

@card('시엘 아츠 - 월영침식')
def _(c):
    def cost1(g, c, p, l):
        if g.rule('ciel_cost_free', p, c): g.L('코스트 면제 (스킬)', 'sys'); return
        m = own_mon(g, p, CIEL)[0]; g.L(f'코스트: {m} 턴 종료 시까지 제외'); g.banish(m, ('cost', c)); m.flags['return_from_banish'] = g.turn
        l.ctx['t'] = best(g, targets_of(g, p, opp_cards(g, p)), p, 'bounce'); g.L(f'대상: {l.ctx["t"]}')
    def res1(g, c, p, l):
        t = l.ctx.get('t')
        if t and g.on_field(t) and t.controller == 1 - p: g.L(f'{t} 덱으로'); g.to_deck(t)
    def res2(g, c, p, l):
        t = best(g, targets_of(g, p, [x for x in opp_cards(g, p) if x.faceup and not g.is_neg(x)]), p, 'negate')
        if t and g.negate_card(t, c): g.L(f'{t} 턴 종료 시까지 무효')
    arts(c, lambda g, c, p, ev: (bool(own_mon(g, p, CIEL)) or g.rule('ciel_cost_free', p, c)) and bool(targets_of(g, p, opp_cards(g, p))), cost1, res1,
         lambda g, c, p: mon(g, SIA, p) and bool(opp_cards(g, p)), res2, sc1=45, sc2=25)

@card('시엘 아츠 - 잔월의 유산')
def _(c):
    def cost1(g, c, p, l):
        if g.rule('ciel_cost_free', p, c): g.L('코스트 면제 (스킬)', 'sys'); return
        m = own_mon(g, p, CIEL)[0]; g.L(f'코스트: {m} 묘지로'); g.send_grave(m, ('cost', c))
    def res1(g, c, p, l):
        g.salvage(p, [x for x in g.p[p].grave if not x.has('솔루나')], '잔월의 유산')   # v3: 「솔루나」 이외
    def res2(g, c, p, l):
        t = best(g, targets_of(g, p, opp_magic(g, p)), p)
        if t: g.destroy(t)
    arts(c, lambda g, c, p, ev: (bool(own_mon(g, p, CIEL)) or g.rule('ciel_cost_free', p, c)) and any(not x.has('솔루나') and x.name != c.name for x in g.p[p].grave), cost1, res1,
         lambda g, c, p: mon(g, SIA, p) and bool(opp_magic(g, p)), res2, sc1=10, sc2=45)

@card('시아 아츠 - 여명신광')
def _(c):
    def cost1(g, c, p, l):
        cs = [x for x in g.field_cards(p) if x.has('시아') and x.faceup and x is not c]
        m = sorted(cs, key=lambda x: (not x.is_monster(), x.type == '필드', x.flags.get('effect_only', False)))[0]
        g.L(f'코스트: {m} 덱으로'); g.to_deck(m, ('cost', c))
        l.ctx['t'] = field_pick(g, p, 'negate', targets_of(g, p, [x for x in g.all_field() if x is not c]))   # 「필드의 카드를 1장 대상으로」: 자신 카드 포함
    def res1(g, c, p, l):
        t = l.ctx.get('t')
        if t and g.on_field(t) and g.negate_card(t, c): g.L(f'{t} 턴 종료 시까지 무효')
        g.heal(p, 1000)
    def res2(g, c, p, l):
        g.salvage(p, [x for x in g.p[p].grave if x is not c], '여명신광')
    def ok1(g, c, p, ev):
        costs = [x for x in g.field_cards(p) if x.has('시아') and x.faceup and x is not c]
        tg = targets_of(g, p, [x for x in g.all_field() if x is not c])
        return bool(costs) and (any(t not in costs for t in tg) or (len(costs) >= 2 and len(tg) >= 2))
    arts(c, ok1, cost1, res1,
         lambda g, c, p: mon(g, CIEL, p) and any(x.name != c.name for x in g.p[p].grave), res2,
         sc1=lambda g, c, p, ev: 10 if opp_cards(g, p) else VETO, sc2=30)

@card('시아 아츠 - 성광난무')
def _(c):
    def cost1(g, c, p, l):
        m = own_mon(g, p, SIA)[0]; g.L(f'코스트: {m} 패로'); g.to_hand(m, ('cost', c))
        n = sum(1 for x in g.p[p].hand if x.has('시아'))
        l.ctx['ts'] = sorted(targets_of(g, p, opp_cards(g, p)), key=lambda x: -value(g, x))[:n]
    def res1(g, c, p, l):
        for t in l.ctx['ts']:
            if g.on_field(t): g.destroy(t)
    def res2(g, c, p, l):
        ms = targets_of(g, p, g.monsters(1 - p))
        if ms: t = best(g, ms, p, 'bounce'); g.L(f'{t} 덱으로'); g.to_deck(t)
    arts(c, lambda g, c, p, ev: bool(own_mon(g, p, SIA)) and bool(targets_of(g, p, opp_cards(g, p))), cost1, res1,
         lambda g, c, p: mon(g, CIEL, p) and bool(g.monsters(1 - p)), res2,
         sc1=lambda g, c, p, ev: 25 + 15 * min(len(opp_cards(g, p)), 1 + sum(1 for x in g.p[p].hand if x.has('시아'))), sc2=35)

@card('시아 아츠 - 일광지로')
def _(c):
    def cost1(g, c, p, l):
        m = own_mon(g, p, SIA)[0]; g.L(f'코스트: {m} 덱으로'); g.to_deck(m, ('cost', c))
    def res2(g, c, p, l):
        t = opp_target(g, c, p, l, 'bounce')
        if t: g.L(f'{t} 덱으로'); g.to_deck(t)
    arts(c, lambda g, c, p, ev: bool(own_mon(g, p, SIA)), cost1,
         lambda g, c, p, l: search_sc(g, p, lambda x: x.has('시아') or x.has('시엘'), '일광지로'),
         lambda g, c, p: mon(g, CIEL, p) and bool(opp_cards(g, p)), res2, sc1=5, sc2=40, kind='ignition')

@card('시아 아츠 - 성광소각')
def _(c):
    def cost1(g, c, p, l):
        m = (own_mon(g, p, SIA) or [x for x in g.monsters(1 - p) if SIA(x) and x.faceup])[0]; g.L(f'코스트: {m} 묘지로'); g.send_grave(m, ('cost', c))
    def res1(g, c, p, l):
        if g.p[1 - p].grave: t = best(g, g.p[1 - p].grave, p, 'banish_grave'); g.banish(t); g.L(f'상대 묘지 {t} 제외')
    def res2(g, c, p, l):
        t = best(g, targets_of(g, p, opp_magic(g, p)), p, 'bounce')
        if t: g.L(f'{t} 덱으로'); g.to_deck(t)
    arts(c, lambda g, c, p, ev: mon(g, SIA) and bool(g.p[1 - p].grave), cost1, res1,
         lambda g, c, p: mon(g, CIEL, p) and bool(opp_magic(g, p)), res2, sc1=0, sc2=40)

@card('솔루나 아츠 - 이클립스 오버드라이브')
def _(c):
    """v3: [트리거] 자신 필드의 시아 · 시엘 몬스터가 동시에 파괴되었을 때 — 필드 전부 파괴, 다음 자신 턴 종료 시까지 대미지 불가"""
    def both(g, p):
        """「동시에 파괴되었을 때」: 같은 원인(같은 카드의 효과 · 같은 전투)으로 파괴된 자신 필드의 시아 · 시엘 몬스터.
        파괴 사건(destroyed)으로 본다 — 코로나 이그니스 · 블러드문 리퍼는 묘지 대신 덱으로 가므로 to_grave가 없다"""
        evs = getattr(g, 'cur_evs', [])
        dest = {id(e['card']) for e in evs if e['kind'] == 'destroyed'}
        groups = {}
        for e in evs:
            if e['kind'] == 'leave_field' and e['ctrl'] == p and e['prev'] in ('m', 'shared') and id(e['card']) in dest:
                ca = e.get('cause') or ('', None)
                groups.setdefault((ca[0], id(ca[1])), []).append(e['card'])
        return any(any(SIA(x) for x in v) and any(CIEL(x) for x in v) for v in groups.values())
    def res(g, c, p, l):
        for t in [x for x in g.all_field() if x is not c]:
            if g.on_field(t): g.destroy(t)   # 앞선 파괴로 규칙에 따라 묘지로 간 장착 카드 등은 건너뛴다
        g.no_damage[p] = max(g.no_damage.get(p, -1), g.turn + (2 if own_turn(g, p) else 1))
        g.L(f'다음 자신 턴 종료 시까지 {g.pname(p)}는 대미지를 줄 수 없음')
    c.effects = [Effect(1, 'trigger', ('hand', 'field'), spell_act=True,
        cond=lambda g, c, p, ev: ev_is(ev, 'destroyed') and both(g, p),
        res=res, score=lambda g, c, p, ev: 20 + 25 * len(opp_cards(g, p)) - 20 * len([x for x in g.field_cards(p) if x is not c]), threat=1500)]

@card('솔루나 아츠 - 이클립스 하모니')
def _(c):
    e = Effect(1, 'resp', ('hand', 'field'), spell_act=True,
        cond=lambda g, c, p, ev: last_opp_link(g, p) is not None and mon(g, SIA, p) and mon(g, CIEL, p),
        cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]), res=lambda g, c, p, l: g.negate(l.ctx['t'], destroy=True, by=c),
        score=lambda g, c, p, ev: 65 if threat(g, p) >= 600 else 0, threat=900)
    e.no_resp = True
    c.effects = [e]

@card('시아 아츠 - 일광정화')
def _(c):
    def trig1(g, c, p, ev):
        return ev_is(ev, 'leave_field') and ev['ctrl'] == p and SIA(ev['card']) and cause_card(ev) is not None and cause_card(ev).controller == 1 - p and bool(opp_cards(g, p))
    def res1(g, c, p, l):
        t = opp_target(g, c, p, l)
        if t: g.destroy(t)
    def res2(g, c, p, l):
        cands = [x for x in g.p[p].upper if SIA(x) and g.can_special(x, p)]
        if cands: g.special_summon(max(cands, key=lambda x: x.level), p)
    arts(c, lambda *a: False, None, res1,
         lambda g, c, p: mon(g, CIEL, p) and any(SIA(x) and g.can_special(x, p) for x in g.p[p].upper), res2,
         sc1=80, sc2=75, kind='trigger', trig1=trig1)

@card('시엘 아츠 - 월광허상')
def _(c):
    def trig1(g, c, p, ev): return ev_is(ev, 'battle_win') and ev['player'] == p and bool(g.all_field())   # ASSUME [전투]=자신 몬스터가 전투로 파괴
    def res1(g, c, p, l):
        t = field_pick(g, p, 'bounce')   # 「필드의 카드」: 자신 카드 포함
        if t: g.L(f'{t} 덱으로'); g.to_deck(t)
    def res2(g, c, p, l):
        cands = [x for x in g.p[p].upper if CIEL(x) and g.can_special(x, p)]
        if cands: g.special_summon(max(cands, key=lambda x: x.level), p)
    arts(c, lambda *a: False, None, res1,
         lambda g, c, p: mon(g, SIA, p) and any(CIEL(x) and g.can_special(x, p) for x in g.p[p].upper), res2,
         sc1=lambda g, c, p, ev: 60 if opp_cards(g, p) else VETO, sc2=75, kind='trigger', trig1=trig1)

@card('시아 아츠 - 일광')
def _(c):
    """v3: 1번 [트리거] 시아 카드 발동에 이어 상대 발동 → 무효 · 파괴 / 2번 [신속] 자신을 덱으로 → 시엘 필드 발동"""
    def res2(g, c, p, l):
        g.to_deck(c)
        f = [x for x in g.deck_cards(p) if x.type == '필드' and x.has('시엘')]
        if f: g._remove(f[0]); g.place_field(f[0], p); g.L(f'덱에서 {f[0]} 발동')
    def cond1(g, c, p, ev):
        return len(g.chain) >= 2 and g.chain[-1].player == 1 - p and g.chain[-2].player == p and g.chain[-2].card.has('시아')
    c.effects = [
        Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda g, c, p, ev: 0 if (g.fieldz and g.fieldz.controller == p) else 50, threat=600),
        Effect(1, 'resp', ('field',), cond=cond1, cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]),
               res=lambda g, c, p, l: g.negate(l.ctx['t'], destroy=True, by=c), score=lambda *a: 70, threat=900),
        Effect(2, 'quick', ('field',), cond=lambda g, c, p, ev: any(x.type == '필드' and x.has('시엘') for x in g.deck_cards(p)), res=res2,
               score=lambda g, c, p, ev: 10 if main_ok(g, p) else 0, threat=300)]

@card('시엘 아츠 - 월영')
def _(c):
    """v3: 1번 [트리거] 시엘 카드 발동에 이어 상대 발동 → 묘지 아츠 회수 / 2번 [신속] 자신을 덱으로 → 시아 필드 발동"""
    def res2(g, c, p, l):
        g.to_deck(c)
        f = [x for x in g.deck_cards(p) if x.type == '필드' and x.has('시아')]
        if f: g._remove(f[0]); g.place_field(f[0], p); g.L(f'덱에서 {f[0]} 발동')
    def cond1(g, c, p, ev):
        return len(g.chain) >= 2 and g.chain[-1].player == 1 - p and g.chain[-2].player == p and g.chain[-2].card.has('시엘') \
               and any(x.has('아츠') and x.name != c.name for x in g.p[p].grave)
    c.effects = [
        Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda g, c, p, ev: 0 if (g.fieldz and g.fieldz.controller == p) else 48, threat=600),
        Effect(1, 'resp', ('field',), cond=cond1, res=lambda g, c, p, l: g.salvage(p, [x for x in g.p[p].grave if x.has('아츠')], '월영'),
               score=lambda *a: 40, threat=300),
        Effect(2, 'quick', ('field',), cond=lambda g, c, p, ev: any(x.type == '필드' and x.has('시아') for x in g.deck_cards(p)), res=res2,
               score=lambda g, c, p, ev: 10 if main_ok(g, p) else 0, threat=300)]

@card('솔루나 아츠')
def _(c):
    def lim(g, src, x, p):
        if p != src.controller or not x.is_monster(): return False
        for pred in (SIA, CIEL):
            if pred(x) and any(pred(m) for m in g.monsters(p)): return True
        return False
    c.rules = {'no_special': lim}
    def res2(g, c, p, l):
        cands = [x for x in g.deck_cards(p) if x.has('아츠') and x.type == '마법']
        if cands and g.free_s(p):
            x = g.p[p].ai.pick_search(g, p, cands, '솔루나 아츠 세트'); g._remove(x); g.place_spell(x, p, False); g.L(f'덱에서 {x} 세트'); g.shuffle(p)
    def cost3(g, c, p, l):   # 「묘지의 「아츠」 카드를 3장을 대상으로 하고 발동」 — 대상만 정한다
        l.ctx['ts'] = sorted([x for x in g.p[p].grave if x.has('아츠')], key=lambda x: g.p[p].ai.card_pri(g, p, x))[:3]
        g.L(f'대상: 묘지 아츠 {", ".join(map(str, l.ctx["ts"]))}')
    def res3(g, c, p, l):
        for x in l.ctx['ts']:
            if x.zone == 'grave': g.to_deck(x)
        g.shuffle(p); g.L('묘지 아츠 덱으로'); g.draw(p, 1)
    c.effects = [
        Effect(2, 'trigger', ('skill',), score=lambda *a: 60, cond=lambda g, c, p, ev: ev_is(ev, 'end_phase') and mon(g, SIA, p) and mon(g, CIEL, p) and bool(g.free_s(p))
                    and any(x.has('아츠') and x.type == '마법' for x in g.deck_cards(p)),   # 대상 없으면 불발 (재정 A-8)
               res=res2, threat=300),
        Effect(3, 'ignition', ('skill',), cond=lambda g, c, p, ev: main_ok(g, p) and sum(1 for x in g.p[p].grave if x.has('아츠')) >= 3,
               cost=cost3, res=res3, score=lambda *a: 35, threat=200)]


import cards2  # noqa: E402,F401  (2차 구현 등록)
import cards3  # noqa: E402,F401  (3차 구현 등록)
import cards4  # noqa: E402,F401  (세리)
import cards5  # noqa: E402,F401  (소원의 분수)
import cards6  # noqa: E402,F401  (저주인형)
import cards7  # noqa: E402,F401  (호박옥)
import cards8  # noqa: E402,F401  (포커짐승들)
import cards9  # noqa: E402,F401  (던전마스터)
import cards10  # noqa: E402,F401  (데이터버그)

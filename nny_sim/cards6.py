"""카드 구현 6차: 저주인형 18종 (카드 자료 2026-10-08)
스킬 「희생제」가 라운드 시작 시 상대 마법 존에 「퇴마의 부적」을 놓고, 저주 카운터(희생제 위)로 싸우는 테마.
저주 카운터는 스킬 카드 「희생제」에 놓인다 — 「자신 필드의 저주 카운터」는 희생제의 카운터로 센다(ASSUME: 스킬 존은 필드가 아니지만
저주 카운터를 놓을 곳이 희생제뿐이므로).

ASSUME:
- 효과 종류 표기가 없는 효과(마들렌 1번 · 저주인형 - 저주인형 2번 · 희생제 2번)는 기동 효과(자신 턴 · 체인 없음)로 처리한다.
- 「종료 단계(페이즈)가 되었을 때」 트리거는 양쪽 플레이어의 종료 단계마다(엔진의 phase 사건 '종료').
- 「(이 효과는 종료 단계에서만 사용할 수 있다.)」 [신속]은 종료 단계의 발동 기회(트리거 체인 · 종료 단계 발동 창)에서만.
- 퇴마의 부적 2번의 「이 카드의 주인」은 재정대로 부적이 놓인 마법 존의 플레이어(컨트롤러). 변경된 효과는 부적의 효과로 본다
  (저주인형 - 저주인형의 「퇴마의 부적 이외의 카드의 효과를 받지 않는다」를 통과).
- 저주 - 의심: 신속 마법이지만 「이 카드가 묘지로 보내졌을 때 다시 활성화」가 뜻을 가지려면 필드에 남아야 하므로, 처리 후 필드에 남고
  필드를 벗어나면 부적의 효과가 다시 적용된다.
- 저주 - 위저보드: 서로의 턴 시작 시마다 컨트롤러가 둘 중 하나를 고른다(특수소환이 가능하면 특수소환, 아니면 퇴마 카운터).
- 저주 - 탐욕: 상대는 부적이 있으면 퇴마 카운터(자신에게 유리), 없으면 패 1장 버리기를 고른다.
- 희생제 3번 「저주 카운터가 4개 놓였을 때」 = 카운터가 4개 미만에서 4개 이상이 되었을 때.
- 저주 - 원한의 굴레: 묘지의 「저주」 · 「저주인형」 카드가 5장 이상일 때만 발동한다.
"""
from engine import Effect, GameOver
from cards import card, grp, best, value, own_turn, main_ok, opp_cards, last_opp_link, threat, ev_is, VETO
from cards2 import targets

SAC = '희생제'
TALISMAN = '퇴마의 부적'
ACE = '저주인형 - 저주인형'
CURSE = '저주'; EXO = '퇴마'
DOLL = lambda x: grp(x, '저주인형')
DOLL_MON = lambda x: grp(x, '저주인형') and x.is_monster()


def sac(g, p):
    sk = g.p[p].skill
    return sk if sk is not None and sk.name == SAC else None

def curses(g, p):
    sk = sac(g, p)
    return (sk.counters.get(CURSE, 0) if sk else 0) + sum(x.counters.get(CURSE, 0) for x in g.field_cards(p))

def add_curse(g, p, n=1):
    sk = sac(g, p)
    if sk is None: g.L(f'「희생제」 없음 — 저주 카운터를 놓을 수 없음', 'sys'); return
    g.add_counter(sk, CURSE, n)

def remove_curse(g, p, n):
    left = n
    for x in [sac(g, p)] + g.field_cards(p):
        if x is None or left <= 0: continue
        left -= g.remove_counter(x, CURSE, left)
    return n - left

def talismans(g, side=None):
    xs = [x for x in g.all_field() if x.name == TALISMAN and x.faceup]
    return xs if side is None else [x for x in xs if x.controller == side]

def add_exo(g, p, n=1):
    """「필드의 「퇴마의 부적」에 퇴마 카운터를 n개 놓는다」 — 상대 필드의 부적을 먼저"""
    ts = sorted(talismans(g), key=lambda x: x.controller == p)
    if not ts: g.L('필드에 「퇴마의 부적」 없음 — 퇴마 카운터 없음', 'sys'); return
    g.add_counter(ts[0], EXO, n)

def has_chucky(g, p): return any(x.name == '저주인형 - 처키' and x.faceup for x in g.monsters(p))

def curse_gain_score(g, p):
    """저주 카운터를 늘릴 가치. 상대 턴 종료 시 희생제 4번이 전부 제거하고 300 × 개수 대미지를 받으므로,
    상대 턴의 종료 단계에 늘리는 것은 처키로 바로 쓰거나 희생제 3번(4개)을 일으킬 때만 이득"""
    n = curses(g, p)
    if own_turn(g, p): return 45 if n < 6 else 10
    if n < 4 <= n + 1 and any(x.is_monster() and g.can_special(x, p) for x in g.p[p].upper): return 50
    if has_chucky(g, p) and targets(g, p, opp_cards(g, p)): return 15
    return -10

def end_counter(num=2):
    return Effect(num, 'trigger', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'phase') and ev['phase'] == '종료' and sac(g, p) is not None,
                  res=lambda g, c, p, l: add_curse(g, p, 1), score=lambda g, c, p, ev: curse_gain_score(g, p), threat=100, label='종료 단계 저주 카운터')

def end_only(g): return g.phase == '종료'

def summon_from(g, p, cands, why):
    cands = [x for x in cands if g.can_special(x, p)]
    if not cands: g.L(f'{why}: 특수소환할 카드 없음', 'sys'); return None
    x = g.p[p].ai.pick_search(g, p, cands, why)
    g.special_summon(x, p); g.shuffle(p); return x


# ═══════════════════════ 몬스터 ═══════════════════════
@card('저주인형 마들렌')
def _(c):
    def cands(g, p, upper_ok):
        return [x for x in g.p[p].main + (g.p[p].upper if upper_ok else []) if x.is_monster() and g.can_special(x, p)]
    def res(g, c, p, l):
        add_curse(g, p, 1)
        summon_from(g, p, cands(g, p, curses(g, p) >= 3), '마들렌')   # 「자신 필드에 저주 카운터가 3개 이상일 경우, 상급 덱에서도」: 처리 중 판정
    c.effects = [Effect(1, 'ignition', ('field',), cond=lambda g, c, p, ev: main_ok(g, p) and bool(cands(g, p, curses(g, p) + 1 >= 3)), res=res,
                        score=lambda g, c, p, ev: 70, threat=500, label='저주 카운터 + 특수소환'), end_counter(2)]

@card('저주인형 - 비비안')
def _(c):
    def cost(g, c, p, l): remove_curse(g, p, 4); g.L('저주 카운터 4개 제거')
    def res(g, c, p, l):
        g.act_limit[1 - p] = (g.turn + 1, 4); g.L(f'다음 턴 {g.pname(1-p)}가 발동할 수 있는 효과 4회로 제한')
    def sc(g, c, p, ev):
        if any(l.card.name == SAC and l.eff.num == 4 for l in g.chain): return 50   # 어차피 희생제 4번에 사라질 카운터
        return 55 if own_turn(g, p) else 25
    c.effects = [Effect(1, 'quick', ('field',), cond=lambda g, c, p, ev: end_only(g) and curses(g, p) >= 4, cost=cost, res=res, score=sc, threat=700,
                        label='상대 발동 4회 제한'), end_counter(2)]

@card('저주인형 - 쿠로하')
def _(c):
    def res(g, c, p, l):
        add_curse(g, p, 1); g.negate(l.ctx['t'])
    c.effects = [Effect(1, 'resp', ('field',), cond=lambda g, c, p, ev: last_opp_link(g, p) is not None, cost=lambda g, c, p, l: l.ctx.update(t=g.chain[-1]),
                        res=res, score=lambda g, c, p, ev: 60 if threat(g, p) >= 500 else 0, threat=800, label='저주 카운터 + 무효'), end_counter(2)]

@card('저주인형 - 애나벨')
def _(c):
    CM = lambda x: grp(x, '저주') and x.type == '마법'
    def res(g, c, p, l):
        g.search(p, CM, why='애나벨'); add_curse(g, p, 1)
    c.effects = [Effect(1, 'summon', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'summon') and ev['card'] is c and (g.can_search(p, CM) or sac(g, p) is not None),
                        res=res, score=lambda *a: 80, threat=300, label='[소환] 저주 마법 서치 + 저주 카운터'), end_counter(2)]

@card('저주인형 - 처키')
def _(c):
    def cost(g, c, p, l):
        remove_curse(g, p, 2); l.ctx['t'] = best(g, targets(g, p, opp_cards(g, p)), p); g.L(f'코스트: 저주 카운터 2개 제거, 대상 {l.ctx["t"]}')
    def res(g, c, p, l):
        t = l.ctx.get('t')
        if t and g.on_field(t): g.destroy(t)
        g.damage(1 - p, 300, c.name)
    def sc(g, c, p, ev):
        ts = targets(g, p, opp_cards(g, p))
        if not ts: return VETO
        return 50 + 15 * max(value(g, x) for x in ts) + (20 if any(l.card.name == SAC and l.eff.num == 4 for l in g.chain) else 0)
    c.effects = [Effect(1, 'quick', ('field',), opt=None, cond=lambda g, c, p, ev: end_only(g) and curses(g, p) >= 2 and bool(targets(g, p, opp_cards(g, p))),
                        cost=cost, res=res, score=sc, threat=1000, label='저주 카운터 2 → 파괴 + 300'), end_counter(2)]

@card('저주인형 - 조리아드')
def _(c):
    def res(g, c, p, l):
        add_curse(g, p, 1)
        t = best(g, targets(g, p, opp_cards(g, p)), p)
        if t: g.destroy(t)
    c.effects = [
        Effect(1, 'resp', ('field',), opt=3, cond=lambda g, c, p, ev: last_opp_link(g, p) is not None, res=res,
               score=lambda g, c, p, ev: 65 if targets(g, p, opp_cards(g, p)) else 20, threat=1000, label='저주 카운터 + 파괴'),
        # 2번: 퇴마 카운터는 상대의 저주인형 파괴 자원 — 임의 효과(§6-3)이므로 쓰지 않는다
        Effect(2, 'trigger', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'phase') and ev['phase'] == '종료' and bool(talismans(g)),
               res=lambda g, c, p, l: add_exo(g, p, 1), score=lambda *a: VETO, threat=0, label='퇴마 카운터')]

@card(ACE)
def _(c):
    c.flags.update(immune_except=TALISMAN, no_release=True)
    c.rules = {'indestructible': lambda g, src, x, battle: battle and x is src}
    def res2(g, c, p, l):
        if not g.on_field(c): return
        g.banish(c); g.L(f'{c} 제외')
        n = sum(1 for x in g.p[p].banish if x.name == ACE)
        if n >= 3: raise GameOver(p, f'{g.pname(p)} 특수 승리 (제외 존의 「{ACE}」 3장)')
    def res3(g, c, p, l):
        if c.zone == 'grave': g.to_deck(c); g.L(f'{c} 덱으로')
        summon_from(g, p, [x for x in g.deck_cards(p) if DOLL_MON(x)], '저주인형 유언')
    c.effects = [
        Effect(2, 'ignition', ('field',), cond=lambda g, c, p, ev: main_ok(g, p), res=res2,
               score=lambda g, c, p, ev: 1000 if sum(1 for x in g.p[p].banish if x.name == ACE) >= 2 else 85, threat=1500, label='자신 제외 (3장 → 승리)'),
        Effect(3, 'lastwill', ('grave',), cond=lambda g, c, p, ev: ev_is(ev, 'to_grave') and ev['card'] is c, res=res3, score=lambda *a: 80, threat=500, label='[유언]')]


# ═══════════════════════ 마법 · 필드 ═══════════════════════
@card(TALISMAN)
def _(c):
    c.flags.update(immune_except='저주 - 의심', no_release=True)
    def on_ev(g, src, ev):
        """2번 [지속]: 퇴마 카운터 4개 이상이면 컨트롤러가 다음에 발동하는 효과를 「부적 카운터 4개 제거 · 상대 필드의 저주인형 카드 1장 파괴」로 바꾼다"""
        if ev['kind'] == 'negated' and src.flags.get('replace_pending') is ev['link']:
            src.flags.pop('replace_pending', None); return   # 변경된 효과가 무효화됨 — 카운터는 그대로, 다음 발동이 다시 변경 대상
        if ev['kind'] != 'activate' or ev['player'] != src.controller or src.counters.get(EXO, 0) < 4: return
        if src.flags.get('replace_pending'): return
        link = ev['link']
        if link.card is src: return
        q = src.controller
        def rep(g2, tl, src=src, q=q):
            src.flags.pop('replace_pending', None)
            if g2.on_field(src): g2.remove_counter(src, EXO, 4)
            ts = [x for x in g2.field_cards(1 - q) if DOLL(x)]
            t = g2.p[q].ai.pick_target(g2, q, ts, 'remove') if ts else None
            if t: g2.destroy(t, ('effect', src))
            else: g2.L('상대 필드에 「저주인형」 카드 없음', 'sys')
        link.replaced = rep; src.flags['replace_pending'] = link
        g.L(f'{TALISMAN}: {link.card}의 효과가 「퇴마 카운터 4개 제거 · 저주인형 카드 1장 파괴」로 변경됨', 'sys')
    c.on_event = on_ev
    c.effects = [
        Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda *a: VETO, threat=0),   # 자신 필드에 놓으면 자신이 손해 — AI는 쓰지 않는다
        Effect(3, 'trigger', ('field',), cond=lambda g, c, p, ev: ev_is(ev, 'phase') and ev['phase'] == '종료' and any(DOLL(x) for x in g.field_cards(1 - p) + g.deck_cards(1 - p) + g.p[1 - p].hand),
               res=lambda g, c, p, l: g.add_counter(c, EXO, 1), score=lambda *a: 40, threat=0, label='퇴마 카운터')]

@card('저주 - 재앙')
def _(c):
    def cands(g, p): return [x for x in g.p[p].main if DOLL(x) and x.is_monster() and g.can_special(x, p)]
    def res(g, c, p, l):
        summon_from(g, p, cands(g, p), '재앙'); add_exo(g, p, 2)
    c.effects = [Effect(1, 'quick', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: bool(cands(g, p)), res=res,
                        score=lambda g, c, p, ev: 50 if main_ok(g, p) else (30 if not own_turn(g, p) and end_only(g) else 0), threat=400)]

@card('저주 - 의심')
def _(c):
    def res(g, c, p, l):
        ts = [x for x in talismans(g) if not x.flags.get('perma_neg')]
        if not ts or not g.on_field(c): return
        c.flags['stay'] = True
        for t in ts: t.flags['perma_neg'] = c.uid; g.L(f'{t}의 효과 무효 (「{c.name}」이 필드에 있는 동안)')
        def fl(g2, ev, me=c):
            if ev['kind'] == 'leave_field' and ev['card'] is me:
                for x in talismans(g2) + [y for y in g2.all_field() if y.flags.get('perma_neg') == me.uid]:
                    if x.flags.get('perma_neg') == me.uid: x.flags.pop('perma_neg'); g2.L(f'{x}의 효과 다시 활성화', 'sys')
                me.flags.pop('stay', None)
                if fl in g2.floating: g2.floating.remove(fl)
        fl.until = None; g.floating.append(fl)
    def sc(g, c, p, ev):
        ts = [x for x in talismans(g) if not x.flags.get('perma_neg')]
        if not ts: return VETO
        hi = max(x.counters.get(EXO, 0) for x in ts)
        return (45 if hi >= 3 else 20) if main_ok(g, p) else (40 if hi >= 4 else 0)
    c.effects = [Effect(1, 'quick', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: any(not x.flags.get('perma_neg') for x in talismans(g)),
                        res=res, score=sc, threat=500)]

@card('저주 - 불문율')
def _(c):
    CUR = lambda x: grp(x, '저주')
    def res(g, c, p, l):
        for _ in range(2): g.search(p, CUR, which=('main',), why='불문율')
        add_exo(g, p, 1)
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: g.can_search(p, CUR, which=('main',)), res=res,
                        score=lambda g, c, p, ev: 50, threat=300)]

@card('저주 - 타락')
def _(c):
    def cost(g, c, p, l):
        l.ctx['t'] = best(g, targets(g, p, opp_cards(g, p)), p); g.L(f'대상: {l.ctx["t"]}')
    def res(g, c, p, l):
        t = l.ctx.get('t')
        if t and g.on_field(t): g.L(f'{t} 묘지로'); g.send_grave(t)
        add_exo(g, p, 1)
    c.effects = [Effect(1, 'resp', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: last_opp_link(g, p) is not None and bool(targets(g, p, opp_cards(g, p))),
                        cost=cost, res=res, score=lambda g, c, p, ev: 30 + 15 * max(value(g, x) for x in targets(g, p, opp_cards(g, p))), threat=900)]

@card('저주 - 탐욕')
def _(c):
    def on_ev(g, src, ev):
        p = src.controller; q = 1 - p
        if ev['kind'] != 'phase' or ev['phase'] != '준비' or g.turn_player != q: return
        ts = talismans(g, q)
        if ts or not g.p[q].hand:   # 상대가 고른다 — 자기 필드의 부적이 있으면 퇴마 카운터(저주인형 파괴 자원), 없으면 패 1장
            g.L(f'판단[{g.pname(q)}] 저주 - 탐욕: 퇴마 카운터 선택', 'decision')
            if ts: g.add_counter(ts[0], EXO, 1)
            elif talismans(g): add_exo(g, p, 1)
        else:
            x = g.p[q].ai.pick_discard(g, q, g.p[q].hand)
            g.L(f'판단[{g.pname(q)}] 저주 - 탐욕: 패 {x} 묘지로', 'decision'); g.send_grave(x, ('effect', src))
    c.on_event = on_ev
    c.effects = [Effect(0, 'ignition', ('hand',), spell_act=True, score=lambda g, c, p, ev: 0 if any(x.name == c.name for x in g.spells(p)) else 40, threat=400)]

@card('저주 - 강령')
def _(c):
    def cands(g, p): return [x for x in g.p[p].main if DOLL(x) and x.is_monster() and g.can_special(x, p)]
    def res(g, c, p, l):
        for _ in range(2): summon_from(g, p, cands(g, p), '강령')
        add_exo(g, p, 1)
    c.effects = [Effect(1, 'trigger', ('hand', 'field'), spell_act=True,
                        cond=lambda g, c, p, ev: ev_is(ev, 'negated') and ev['player'] == p and bool(cands(g, p)), res=res, score=lambda *a: 75, threat=600)]

@card('저주 - 빙의')
def _(c):
    def rel(g, p): return [x for x in targets(g, p, opp_cards(g, p)) if g.releasable(x)]
    def gy(g, p): return [x for x in g.p[p].grave if DOLL_MON(x) and g.can_special(x, p)]
    def res(g, c, p, l):
        t = best(g, rel(g, p), p)
        if t: g.tribute(t)
        summon_from(g, p, gy(g, p), '빙의'); add_exo(g, p, 1)
    c.effects = [Effect(1, 'quick', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: bool(rel(g, p)), res=res,
                        score=lambda g, c, p, ev: (30 + 15 * max(value(g, x) for x in rel(g, p)) + (10 if gy(g, p) else 0)) if main_ok(g, p)
                        else (40 if threat(g, p) >= 900 else 0), threat=900)]

@card('저주 - 원한의 굴레')
def _(c):
    G = lambda x: grp(x, '저주') or grp(x, '저주인형')
    def res(g, c, p, l):
        xs = sorted([x for x in g.p[p].grave if G(x) and x is not c], key=lambda x: -g.p[p].ai.card_pri(g, p, x))[:5]
        for x in xs: g.to_deck(x)
        g.shuffle(p); g.L(f'묘지 {len(xs)}장 덱으로'); g.draw(p, 1)
    c.effects = [Effect(1, 'ignition', ('hand', 'field'), spell_act=True, cond=lambda g, c, p, ev: sum(1 for x in g.p[p].grave if G(x)) >= 5, res=res,
                        score=lambda g, c, p, ev: 40 if len(g.p[p].main) + len(g.p[p].upper) <= 15 else 25, threat=200)]

@card('저주 - 위저보드')
def _(c):
    def on_ev(g, src, ev):
        if ev['kind'] != 'phase' or ev['phase'] != '준비': return
        p = src.controller
        cands = [x for x in g.deck_cards(p) if DOLL_MON(x) and g.can_special(x, p)]
        if cands:
            g.L(f'판단[{g.pname(p)}] 저주 - 위저보드: 덱에서 저주인형 특수소환 선택', 'decision')
            aces = [x for x in cands if x.name == ACE]
            x = aces[0] if aces else g.p[p].ai.pick_search(g, p, cands, '위저보드')
            g.special_summon(x, p); g.shuffle(p)
        elif talismans(g, 1 - p):
            g.L(f'판단[{g.pname(p)}] 저주 - 위저보드: 특수소환 불가 — 퇴마 카운터', 'decision'); g.add_counter(talismans(g, 1 - p)[0], EXO, 1)
    c.on_event = on_ev
    c.effects = [Effect(0, 'ignition', ('hand',), spell_act=True,
                        score=lambda g, c, p, ev: 0 if (g.fieldz and g.fieldz.name == c.name and g.fieldz.controller == p) else 55, threat=600)]


# ═══════════════════════ 스킬 ═══════════════════════
@card(SAC)
def _(c):
    def on_ev(g, src, ev):
        if ev['kind'] != 'game_start': return
        p = src.controller
        ts = [x for x in g.p[p].main + g.p[p].upper if x.name == TALISMAN]
        if not ts: g.L(f'{SAC} 1번: 덱에 「{TALISMAN}」 없음', 'sys'); return
        if not g.free_s(1 - p): return
        t = ts[0]; g._remove(t); g.place_spell(t, 1 - p, True)
        g.L(f'{SAC} 1번: 덱의 {t}을(를) {g.pname(1-p)}의 마법 존에 놓음'); g.shuffle(p)
    c.on_event = on_ev
    def mains(g, p): return [x for x in g.p[p].main if x.is_monster() and g.can_special(x, p)]
    def uppers(g, p): return [x for x in g.p[p].upper if x.is_monster() and g.can_special(x, p)]
    def cond3(g, c, p, ev):
        if not (ev_is(ev, 'counter') and ev['card'] is c and ev['name'] == CURSE and ev['delta'] > 0): return False
        n = c.counters.get(CURSE, 0)
        return n >= 4 > n - ev['delta'] and bool(uppers(g, p))
    def res4(g, c, p, l):
        n = c.counters.get(CURSE, 0)
        if n <= 0: return
        g.remove_counter(c, CURSE, n)
        g.damage(p, 300 * n, f'자해 ({SAC} 4번)')
        if any(x.name == ACE and x.faceup for x in g.monsters(p)): g.damage(1 - p, 100 * n, f'{SAC} 4번')
    c.effects = [
        Effect(2, 'ignition', ('skill',), cond=lambda g, c, p, ev: main_ok(g, p) and bool(mains(g, p)),
               res=lambda g, c, p, l: summon_from(g, p, mains(g, p), f'{SAC} 2번'), score=lambda *a: 65, threat=500, label='메인 덱 몬스터 특수소환'),
        Effect(3, 'trigger', ('skill',), cond=cond3, res=lambda g, c, p, l: summon_from(g, p, uppers(g, p), f'{SAC} 3번'),
               score=lambda *a: 85, threat=700, label='저주 카운터 4개 → 상급 덱 특수소환'),
        Effect(4, 'trigger', ('skill',), mandatory=True, opt=None,
               cond=lambda g, c, p, ev: ev_is(ev, 'end_phase') and ev['player'] == 1 - p and c.counters.get(CURSE, 0) > 0, res=res4, threat=0,
               label='상대 턴 종료 시 카운터 정산')]

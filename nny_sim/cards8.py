"""카드 구현 8차: 포커짐승들 20종 (카드 자료 2026-10-08)
※ 블록 체계(2026-10-28): 카드 효과는 조립표 blocks/t_pkbs.py로 옮겼다. 이 모듈에는 블록 · 테스트가 쓰는 공용 함수 · 상수만 남았고, 아래 설명은 옛 구현 기준의 재정 · 가정 기록이다.
몬스터의 레벨을 포커 숫자로, 속성(스페이드 · 다이아 · 하트 · 클로버)을 문양으로 써서 족보를 완성하는 테마.
족보 효과(스트레이트 · 플러쉬 · 풀 하우스 · 포카드, 스킬 「올인」의 원페어 · 트리플)는 재료를 릴리스하거나 덱으로 되돌리는 코스트로
상급 덱의 본체를 소환한다. 「메이드에 실패한」 몬스터는 재료로 묘지에 가면 [유언]이, 표시목 · 짐승조커는 릴리스되면 드로우가 붙는다.

ASSUME:
- 「상급 덱에서 「X」를 소환한다」 · 올인 「덱에서 … 1장을 소환한다」 = 특수소환 (표시 형식은 AI가 고른다, §5-2). 같은 이름 규칙(§3-6 f)을 따른다.
- 족보 재료의 범위는 코스트 문장에서 읽는다(combo_opp_ok): 「서로의」 · 「상대」가 있으면 상대 카드도, 없으면 자신 카드만 —
  스트레이트(토끼 2번 「패와 필드」) · 원페어(올인 「패, 필드」)는 자신 패 + 자신 필드(사용자 답변 2026-10-21), 플러쉬(늑대 2번)는 자신 패 + 서로의 필드,
  풀 하우스 · 포카드는 서로의 필드 + 서로의 묘지, 트리플은 자신 패 · 필드 + 상대 필드.
- 필드의 재료는 앞면 카드만 (뒷면 카드의 레벨 · 속성은 알 수 없다). 상대 카드는 내 효과를 받는 카드만(내성), 릴리스 재료는 릴리스할 수 있는 카드만.
- 패에서 발동한 풀 하우스(강아지 2번) · 포카드(고양이 2번)는 패의 이 카드도 재료로 덱으로 되돌린다 (「이 카드를 포함하는」).
- 올인 2번의 트리플 「자신의 몬스터를 포함하는」 = 세 장 중 1장 이상이 자신의 카드(패 · 자신 필드)면 된다 — 발동한 몬스터 자신일 필요는 없다.
- 올인 2번이 준 효과는 그 몬스터의 효과다: 1턴 1번은 부여받은 몬스터 한 장마다 따로 센다(사용자 답변 2026-10-17 — 부여 효과 번호 21 · 22, Game.opt_key),
  「자신이 포커짐승들 효과를 발동할 때마다」(메이드에 실패한 강아지 2번)에 포함된다. 효과가 무효인 몬스터는 쓸 수 없다(엔진 zone_ok).
- 레벨 · 속성 부여(표시목 1번 · 올인 원페어 · 짐승조커)는 그 카드가 필드에 있는 동안만 유지된다 (필드를 벗어나면 원래대로 —
  flags['clear_on_leave']). 표시목이 필드를 떠나도 이미 부여된 레벨 · 속성은 남는다. 부여된 속성은 원래 속성을 대신한다(쥐의 「모두」도 덮어씀).
- 표시목 · 올인이 마법 · 필드 카드에 부여하면 그 카드는 몬스터로 취급된다(flags['as_monster'], 공격력 0 / 수비력 0 · 종족 없음 — 재정).
  마법 · 필드 존에 그대로 있지만 공격할 수 있고 공격 대상이 된다(사용자 답변 2026-10-21 — engine.Game.battle_cards, 공격 표시로 본다).
  족보 재료 · 「몬스터」를 세는 효과에도 쓰인다. 표시목은 자신도 대상으로 할 수 있다.
- 짐승조커 1번: 처리 시 레벨(1~10)과 속성(4문양)을 선언하고 몬스터 존(또는 공유 존)에 특수소환한다. 필드를 떠나면 다시 마법 카드.
- 「이 카드가 릴리스되었을 때」 = Game.tribute로 묘지에 간 경우(코스트 · 일반소환의 제물 포함) — 엔진 사건 to_grave의 released.
- 스트플을 원하는 쥐 1번(속성 「모두로 취급」)은 [지속]이므로 필드에 있을 때만 적용된다(사용자 답변 2026-10-22 — [지속] 키워드의 적용 범위는 필드).
  패 · 묘지 · 덱에서는 원래 속성이고, 필드에서 뒷면이거나 무효가 되어도 원래 속성(engine.Game.cont_active).
- 쥐 3번 「자신 필드의 포커짐승들 몬스터가 파괴되었을 경우」 = 자신이 컨트롤하던 몬스터 존(공유 존 포함)의 포커짐승들 카드가 파괴되어 묘지로 간 사건.
- 「같은 속성의 카드 1장당」(플러쉬를 노리는 늑대 1번) · 「같은 레벨의 몬스터 1장당」(포카드를 보는 고양이 1번)은 필드(서로)의 앞면 카드를 세고,
  증감을 받는 그 몬스터 자신도 센다(사용자 답변 2026-10-22 — 빼는 경우는 효과 텍스트에 「이외」 · 「다른」으로 적혀 있다: cards.per_card_self).
  「다이아 속성의 카드 1장당」(플러쉬 늑대 1번)도 자신을 센다.
- 풀 하우스를 찾는 강아지 1번(종류 표기 없음, 「발동」 문구 없음)은 [지속] 권리로 본다: 앞면으로 필드에 있는 동안 1턴에 1번
  「포커짐승들」 몬스터를 추가로 일반소환할 수 있다 (풀 하우스 강아지 1번은 2번까지). 기본 일반소환을 먼저 쓰고 그 뒤에 추가 권리를 쓴다.
- 「이 카드를 패에서 상대에게 보여주고 발동」(상급 3종)은 표기가 없어 기동 효과(자신 턴 · 체인 없음): 공개가 코스트, 덱으로 되돌리기 · 서치가 처리.
- 메이드에 실패한 토끼 1번은 묘지에 2장 이상 있을 때만 발동 (2장을 되돌리지 못하면 「그 후」 드로우도 없다).
  「N장까지」는 1 ~ N장 — 최소 1장은 골라야 한다(사용자 답변 2026-10-22, 시골쥐 2번). 자신 묘지에 카드가 없으면 시골쥐 2번은 발동하지 않는다.
  체인 처리 중 묘지가 비어 1장도 되돌리지 못해도 「되돌리고 1장 드로우」의 드로우는 한다(예전 처리 그대로).
- 메이드에 실패한 강아지 1번 「「포커짐승들」 마법 카드」에 필드 카드(도박장)는 포함하지 않는다 (cards.opp_magic과 같은 구분).
- 쇠망치: 「덱 또는 묘지에서 카드를 패에 넣었을 경우」는 효과로 넣은 경우와 드로우(사용자 답변 2026-10-28 — cards.hand_add), 처리 시 그 카드가 아직
  상대의 패 · 필드에 있어야 제외한다.
- 도박장: 패에서의 [신속] 허가는 원래 패에서 쓸 수 없는 [신속](부르는 토끼 2번 · 노리는 늑대 2번)에만 쓰이고, 그 발동이 1턴 2번을 소모한다
  (무효화되면 돌려받음, §6-5). 올인이 준 효과는 필드의 몬스터에만 있으므로 해당 없다.

재정 질문:
- 「상급 덱에서 「X」를 소환한다」는 특수소환인가? (지금: 특수소환 — 쇠망치 · 명계의 징벌 등 「특수소환했을 경우」에 걸린다)
- 스트레이트 · 원페어의 「패와 필드」에 상대 필드의 몬스터도 포함되는가? (지금: 포함 — 「필드」 = 서로의 필드 관례)
- 트리플의 「자신의 몬스터를 포함하는」은 발동한 그 몬스터를 포함해야 하는가, 자신의 몬스터 아무거나 1장이면 되는가? (지금: 아무거나)
- 올인 2번이 준 [신속]의 1턴 1번은 몬스터 카드명마다인가, 플레이어당(스킬 효과 단위)인가? (지금: 몬스터 카드명마다)
- 풀 하우스를 찾는 강아지 1번은 [지속] 권리(추가 일반소환 1회)인가, 발동하는 효과(즉시 추가 일반소환)인가? (지금: [지속] 권리)
- 표시목이 부여한 레벨 · 속성은 표시목이 필드를 떠나도 남는가? 마법 카드에 부여해 몬스터로 취급되면 공격 · 공격 대상이 될 수 있는가? (지금: 남는다 / 안 된다)
- (해결 2026-10-22) 「1장당」은 자신도 센다 · 「3장까지」는 최소 1장 · [지속]은 필드에서만.
- 짐승조커 · 표시목 2번 「릴리스되었을 때」에 일반소환의 제물로 릴리스된 경우도 포함되는가? (지금: 포함)

엔진 변경 (모두 추가 · 플래그/속성이 없는 카드는 예전과 같음):
- engine.Card.is_monster: flags['as_monster']면 몬스터로 취급 (짐승조커 · 부여받은 마법/필드 카드)
- engine.Game._remove: flags['clear_on_leave'] = {플래그: 이전 값} — 필드를 벗어날 때 부여된 레벨 · 속성 · 몬스터 취급을 되돌린다
- engine.Game.send_grave(released=) · tribute: 릴리스로 묘지에 간 to_grave · leave_field 사건에 released=True
- engine.Game.df: [지속] def_mod 훅 (atk_mod와 같은 형태) — 포카드를 보는 고양이 1번 · 메이드에 실패한 고양이 2번
- engine.Game.extra_ns_used / extra_normal_left / can_normal, normal_summon: [지속] extra_normal(g, src, p, c) 추가 일반소환 권리
- ai.HeuristicAI.main_phase · extra_summon_options, policy.LearnedAI.main_phase: 일반소환 후보 조건을 g.can_normal(p[, c])로
  (권리가 없으면 normal_summons > 0과 같음). extra_summon_options: 카드의 ns_value(g, p, 제물, 제물 가치) 훅 — [소환]이 본체인 상급 몬스터의 제물 소환 가치
- ai.DECK_POLICY['올인']
"""
import re
from collections import namedtuple
from cards import grp, value, opp_cards, eff_text
from cards2 import targets

PK = '포커짐승들'
SKILL = '올인'
GAMBLE = '포커짐승들의 도박장'
SUITS = ('스페이드', '다이아', '하트', '클로버')
LEVELS = range(1, 11)   # 부여 · 선언할 수 있는 레벨(「원하는 레벨」)
ALL4 = frozenset(SUITS)
FIELD_M = ('m', 'shared')
RABBIT_UP, WOLF_UP, DOG_UP, CAT_UP = '♠ 스트레이트 토끼', '◆ 플러쉬 늑대', '♥ 풀 하우스 강아지', '♣ 포카드 고양이'
UP_TARGET = {'straight': RABBIT_UP, 'flush': WOLF_UP, 'full': DOG_UP, 'four': CAT_UP}
KIND_LABEL = {'straight': '스트레이트', 'flush': '플러쉬', 'full': '풀 하우스', 'four': '포카드', 'pair': '원페어', 'triple': '트리플'}


def PK_MON(x): return grp(x, PK) and x.is_monster()
def deck_left(g, p): return len(g.p[p].main) + len(g.p[p].upper)


def allin(g, p):
    """p의 스킬이 무효가 아닌 「올인」인가"""
    sk = g.p[p].skill
    return sk is not None and sk.name == SKILL and not sk.negated


def attrs(g, x):
    """x의 속성 집합: 부여된 속성(flags['attr_set']) > 쥐 1번 「4문양 모두로 취급」([지속] — 필드에 앞면으로 있고 무효가 아닐 때만) > 원래 속성"""
    v = x.flags.get('attr_set')
    if v is not None: return frozenset(v) if isinstance(v, (tuple, list, set, frozenset)) else frozenset((v,))
    if x.flags.get('all_suits') and g.cont_active(x): return ALL4
    a = x.d.get('attr')
    return frozenset((a,)) if a else frozenset()


def leaves_ok(g, x):
    """코스트로 필드를 벗어나게 할 수 있는가 (「파괴 이외의 방법으로 필드를 벗어나지 않는다」 — Game.stays와 같은 판정, 로그 없음)"""
    return not (g.on_field(x) and not g.is_neg(x) and g.flag(x, 'leave_only_destroy'))


def gambling_ok(g, p):
    """도박장 1번: 자신 「포커짐승들」 몬스터의 [신속]을 패에서 발동할 수 있다 (1턴에 2번까지)"""
    return g.rule('pk_hand_quick', p) and g.p[p].opt.get((GAMBLE, 1), 0) < 2


def grant(g, t, lv, at, src=None):
    """레벨 · 속성 부여 (필드에 있는 동안). 마법 · 필드 카드는 몬스터로 취급 (공격력 0 / 수비력 0, 표시목 재정).
    뒷면 카드에는 부여할 수 없다 — 대상을 지정하지 않는 효과(원페어 「고르고」)라도 (특수 케이스, 사용자 답변 2026-10-23 Q53)"""
    if not t.faceup: g.L(f'{t}: 뒷면 카드에는 레벨 · 속성을 부여할 수 없음', 'sys'); return False
    col = t.flags.get('clear_on_leave') or {}
    for k in ('level_set', 'attr_set', 'as_monster'):
        if k not in col: col[k] = t.flags.get(k)
    t.flags['clear_on_leave'] = col
    as_mon = not t.is_monster()
    t.flags['level_set'] = lv; t.flags['attr_set'] = at
    if as_mon: t.flags['as_monster'] = True
    g.L(f'{t}에 레벨 {lv} · {at} 속성 부여' + (' (몬스터로 취급)' if as_mon else ''))


# ═══════════════════════ 족보 재료 ═══════════════════════
Mat = namedtuple('Mat', 'card lv at where cost')   # where: hand / own_f / opp_f / own_g / opp_g, cost: AI 손익(낮을수록 좋음)


def rel_bonus(x):
    """릴리스(묘지로) 되면 이득이 붙는 카드: [유언] · 표시목 · 짐승조커 2번"""
    return any(e.kind == 'lastwill' for e in x.effects) or x.name in ('표시목', '짐승조커')


def mat_cost(g, p, x, where, mode):
    """재료로 쓰는 손익 (AI 사전값): 상대 필드 카드를 쓰면 이득, 자신 필드 · 패의 카드는 그 가치만큼 손해"""
    if where == 'opp_f': return -1.2 * value(g, x)
    if where == 'opp_g': return -0.1
    if where == 'own_g': return 0.15
    c = 0.9 if where == 'hand' else value(g, x)
    if mode == 'release' and rel_bonus(x): c -= 0.8
    return c


def _mat_ok(g, p, x, where, release):
    if where in ('own_f', 'opp_f'):
        if not x.faceup or not leaves_ok(g, x): return False
        if where == 'opp_f':
            # 재료 고르기는 대상 지정이 아니다 — 코스트 단계(Game.costing)에서도 발동 판정 때와 같은 내성으로 본다
            prev = getattr(g, 'costing', None); g.costing = None
            try: imm = g.immune(x, p)
            finally: g.costing = prev
            if imm: return False
    if release and not g.releasable(x): return False
    return True


def build_pool(g, p, zones, release):
    mode = 'release' if release else 'deck'
    out = []
    srcs = []
    if 'hand' in zones: srcs += [(x, 'hand') for x in g.p[p].hand]
    if 'own_f' in zones: srcs += [(x, 'own_f') for x in g.field_cards(p)]
    if 'opp_f' in zones: srcs += [(x, 'opp_f') for x in g.field_cards(1 - p)]
    if 'own_g' in zones: srcs += [(x, 'own_g') for x in g.p[p].grave]
    if 'opp_g' in zones: srcs += [(x, 'opp_g') for x in g.p[1 - p].grave]
    for x, where in srcs:
        if not x.is_monster(): continue
        lv = x.level
        if not lv or lv < 1 or not _mat_ok(g, p, x, where, release): continue
        out.append(Mat(x, lv, attrs(g, x), where, mat_cost(g, p, x, where, mode)))
    return out


REL_Z = ('hand', 'own_f', 'opp_f')
DECK_Z = ('own_f', 'opp_f', 'own_g', 'opp_g')


def _sig(g):
    return (g.turn, g.phase, len(g.log), len(g.chain), len(g.events),
            tuple(len(g.p[i].hand) for i in (0, 1)), tuple(len(g.p[i].grave) for i in (0, 1)),
            tuple(len(g.field_cards(i)) for i in (0, 1)), tuple(len(g.p[i].upper) + len(g.p[i].main) for i in (0, 1)))


def pools(g, p, fresh=False):
    """(릴리스 재료 R, 덱 되돌림 재료 D). 발동 판정 · AI 점수용으로 같은 상태에서는 다시 계산하지 않는다 (코스트 지불은 fresh)"""
    cache = g.__dict__.setdefault('_pk_pools', {})
    s = _sig(g)
    if not fresh:
        hit = cache.get(p)
        if hit and hit[0] == s: return hit[1]
    v = (build_pool(g, p, REL_Z, True), build_pool(g, p, DECK_Z, False))
    cache[p] = (s, v)
    return v


def with_over(g, p, ms, mode, over=None, virt=()):
    """AI 계획용 가상 재료: over = {필드의 카드: (레벨, 속성 집합)} 부여, virt = [(카드, 레벨, 속성 집합)] 자신 필드에 놓인 것으로"""
    if not over and not virt: return ms
    out = []; seen = set()
    for m in ms:
        if over and m.card in over:
            lv, at = over[m.card]; out.append(m._replace(lv=lv, at=frozenset(at))); seen.add(m.card)
        else: out.append(m)
    for x, (lv, at) in (over or {}).items():
        if x in seen or not g.on_field(x): continue
        where = 'own_f' if x.controller == p else 'opp_f'
        if (mode == 'release' or where in ('own_f', 'opp_f')) and not _mat_ok(g, p, x, where, mode == 'release'): continue
        out.append(Mat(x, lv, frozenset(at), where, mat_cost(g, p, x, where, mode)))
    for x, lv, at in virt:
        out.append(Mat(x, lv, frozenset(at), 'own_f', 0.2 if mode == 'release' else 1.0))
    return out


# ── 족보 찾기: (비용 합, [재료]) 또는 None. me = 발동하는 카드의 재료 항목, n = 이 카드를 포함한 재료 매수 (combo_sizes) ──
def f_straight(ms, me, n=3):
    """연속되는 레벨 n장 (레벨마다 1장, 이 카드 포함)"""
    bestr = None
    for lo in range(me.lv - n + 1, me.lv + 1):
        if lo < 1: continue
        pick = [me]
        for l in range(lo, lo + n):
            if l == me.lv: continue
            cs = [m for m in ms if m.lv == l and m.card is not me.card]
            if not cs: pick = None; break
            pick.append(min(cs, key=lambda m: m.cost))
        if pick:
            tot = sum(m.cost for m in pick)
            if bestr is None or tot < bestr[0]: bestr = (tot, pick)
    return bestr


def f_flush(ms, me, n=3):
    bestr = None
    for s in me.at:
        cs = sorted((m for m in ms if s in m.at and m.card is not me.card), key=lambda m: m.cost)
        if len(cs) >= n - 1:
            pick = [me] + cs[:n - 1]; tot = sum(m.cost for m in pick)
            if bestr is None or tot < bestr[0]: bestr = (tot, pick)
    return bestr


def _by_level(ms, me):
    by = {}
    for m in ms:
        if m.card is not me.card: by.setdefault(m.lv, []).append(m)
    for v in by.values(): v.sort(key=lambda m: m.cost)
    return by


def f_full(ms, me, splits=((3, 2), (2, 3))):
    """풀 하우스: 같은 레벨 묶음 두 개(두 레벨은 달라야 한다 — 「5장이 전부 같은 레벨일 수는 없으며」).
    splits = [(이 카드가 든 묶음의 매수(이 카드 포함), 다른 묶음의 매수), …] — 이 카드는 어느 묶음에든 들 수 있다"""
    by = _by_level(ms, me); same = by.get(me.lv, [])
    bestr = None
    for lv, lst in by.items():
        if lv == me.lv: continue
        for a, b in splits:
            if len(same) >= a - 1 and len(lst) >= b:
                pick = [me] + same[:a - 1] + lst[:b]
                tot = sum(m.cost for m in pick)
                if bestr is None or tot < bestr[0]: bestr = (tot, pick)
    return bestr


def f_four(ms, me, n=4):
    same = _by_level(ms, me).get(me.lv, [])
    if len(same) < n - 1: return None
    pick = [me] + same[:n - 1]
    return sum(m.cost for m in pick), pick


def f_pair(ms, me, n=2):
    same = _by_level(ms, me).get(me.lv, [])
    if len(same) < n - 1: return None
    pick = [me] + same[:n - 1]
    return sum(m.cost for m in pick), pick


def f_triple(ms, n=3):
    """트리플: 같은 레벨 n장, 그중 1장 이상은 자신의 카드(패 · 자신 필드)"""
    by = {}
    for m in ms: by.setdefault(m.lv, []).append(m)
    bestr = None
    for lv, lst in by.items():
        if len(lst) < n: continue
        lst = sorted(lst, key=lambda m: m.cost)
        pick = lst[:n]
        if not any(m.where in ('hand', 'own_f') for m in pick):
            own = [m for m in lst[n:] if m.where in ('hand', 'own_f')]
            if not own: continue
            pick = lst[:n - 1] + own[:1]
        tot = sum(m.cost for m in pick)
        if bestr is None or tot < bestr[0]: bestr = (tot, pick)
    return bestr


# ── 족보 재료 매수: 카드 텍스트의 코스트 문장(「…고 발동」)에서 읽는다 ──
_SIZES = {}


def combo_text(g, c, p, kind):
    """족보 효과의 원문: 올인이 준 효과(원페어 · 트리플)는 스킬 텍스트의 「-」 항목(부여 효과 번호 21 · 22 순서), 나머지는 그 카드의 효과 문장"""
    e = next((x for x in c.effects if getattr(x, 'pk_kind', None) == kind), None)
    if e is not None and getattr(e, 'pk_granted', None) is not None:
        sk = g.p[p].skill
        items = [l.strip() for l in (sk.d.get('text') or '').split('\n') if l.strip().startswith('-')] if sk else []
        return items[e.pk_granted] if e.pk_granted < len(items) else ''
    return eff_text(c, e.num if e is not None else 2)


def combo_base(g, c, p, kind):
    """(묶음별 매수, 이 카드를 포함하는가) — 「이 카드를 포함하는 … 3장」 → ([3], True), 「자신의 몬스터를 포함하는 … 3장」 → ([3], False)"""
    key = (c.name, kind, g.p[p].skill.name if kind in ('pair', 'triple') and g.p[p].skill else None)
    if key not in _SIZES:
        t = combo_text(g, c, p, kind)
        m = re.search(r'([^.]*?)고 발동', t)
        ph = m.group(1) if m else t
        _SIZES[key] = ([int(x) for x in re.findall(r'(\d+)장', ph)], bool(re.search(r'(이 카드를|자신을) 포함하는', ph)))
    return _SIZES[key]


_OPP = {}


def combo_opp_ok(g, c, p, kind):
    """족보 재료에 상대 카드(상대 필드 · 상대 묘지)를 쓸 수 있는가 — 코스트 문장에 「서로의」 · 「상대」가 있을 때만 (사용자 답변 2026-10-21)"""
    key = (c.name, kind, g.p[p].skill.name if kind in ('pair', 'triple') and g.p[p].skill else None)
    if key not in _OPP:
        t = combo_text(g, c, p, kind)
        m = re.search(r'([^.]*?)고 발동', t)
        _OPP[key] = bool(re.search(r'서로|상대', m.group(1) if m else t))
    return _OPP[key]


def combo_sizes(g, c, p, kind):
    """족보 재료 매수(이 카드 포함). 두플리카토르 1번(코스트 카드 매수 2배, Game.rule cost_double)이면 2배 —
    「이 카드를 포함하는 n장」은 이 카드를 뺀 나머지만 2배(이 카드 + 2(n-1)장, 사용자 답변 2026-10-20 · 재정 정리 2026-10-17),
    「이 카드」가 없는 매수(트리플 「자신의 몬스터를 포함하는」)는 전체 2배. 늘어난 재료도 그 족보의 레벨 · 속성 조건을 지킨다 (ASSUME)"""
    nums, self_inc = combo_base(g, c, p, kind)
    dup = bool(g.rule('cost_double', p))
    def tot(n, has_me): return (2 * n - 1 if has_me and self_inc else 2 * n) if dup else n
    if kind == 'full':
        a, b = (nums + [3, 2])[:2]
        return [(tot(a, True), tot(b, False)), (tot(b, True), tot(a, False))]
    return tot(nums[0] if nums else 0, True)


FINDERS = {'straight': f_straight, 'flush': f_flush, 'full': f_full, 'four': f_four, 'pair': f_pair}
MODE = {'straight': 'release', 'flush': 'release', 'pair': 'release', 'triple': 'release', 'full': 'deck', 'four': 'deck'}


def can_ss_after(g, p, x, sel, src):
    """코스트를 낸 뒤 x를 특수소환할 수 있는가: 소환 금지 · 같은 이름(§3-6 f) · 놓을 자리(코스트로 자신 몬스터 존이 비는 경우 포함)"""
    if g.rule('no_special', x, p) or x.flags.get('ss_by_skill_only'): return False
    if src is not None and x.name == src.name and x.zone in ('main', 'upper'): return False
    if g.free_m(p) or any(m.where == 'own_f' and m.card.zone == 'm' for m in sel): return True
    return g.can_place(x, p)


def steal_cands(g, p, sel=()):
    """원페어로 컨트롤을 옮길 수 있는 상대 필드의 카드 (코스트로 자리가 비는 것까지 계산)"""
    used = set(m.card for m in sel)
    fm = bool(g.free_m(p)) or any(m.where == 'own_f' and m.card.zone == 'm' for m in sel)
    fs = bool(g.free_s(p)) or any(m.where == 'own_f' and m.card.zone == 's' for m in sel)
    out = []
    for x in targets(g, p, opp_cards(g, p)):
        if not x.faceup: continue   # 「골라 속성과 레벨을 부여하여」: 뒷면 카드에는 부여할 수 없으므로 고르지 않는다 (사용자 답변 2026-10-23 Q53)
        if x in used or (x.zone in FIELD_M and not fm) or (x.zone == 's' and not fs): continue   # 공유 존의 몬스터도 새 컨트롤러의 빈 몬스터 존이 필요(설계도 확정)
        out.append(x)
    return out


def deck_summons(g, p, sel, src):
    """트리플로 덱에서 소환할 수 있는 6레벨 이하의 「포커짐승들」 몬스터"""
    return [x for x in g.deck_cards(p) if PK_MON(x) and 1 <= x.level <= 6 and can_ss_after(g, p, x, sel, src)]


def gain_of(g, p, kind, sel, src):
    """족보 결과의 가치 (AI 사전값, mat_cost와 같은 척도)"""
    if kind == 'straight':   # 스트레이트 토끼: [소환] 3장 드로우 + 1턴 1번 무효
        n = deck_left(g, p)
        return (2.4 if n >= 8 else 1.0 if n >= 4 else -4.0) + 0.6
    if kind == 'flush':      # 플러쉬 늑대: [소환] 묘지의 포커짐승들 몬스터 3장까지 소생 + 큰 공격력
        rev = sum(1 for x in g.p[p].grave if PK_MON(x)) + sum(1 for m in sel if m.where in ('hand', 'own_f') and m.card.type == '몬스터' and grp(m.card, PK))
        return 1.4 + 0.6 * min(3, rev)
    if kind == 'full':       # 풀 하우스 강아지: [소환] 2500 대미지 (결착이면 최우선)
        return 60.0 if g.p[1 - p].hp <= 2500 and g.no_damage.get(p, -1) < g.turn else 3.0
    if kind == 'four':       # 포카드 고양이: [소환] 묘지 4장까지 되돌려 그 수만큼 상대 카드 파괴
        gy = len(g.p[p].grave) - sum(1 for m in sel if m.where == 'own_g')
        of = len(targets(g, p, opp_cards(g, p))) - sum(1 for m in sel if m.where == 'opp_f')
        return 1.2 + 1.3 * max(0, min(4, gy, of))
    if kind == 'pair':
        ts = steal_cands(g, p, sel)
        return 1.6 * max(value(g, t) for t in ts) if ts else -9.0
    if kind == 'triple':
        cs = deck_summons(g, p, sel, src)
        if not cs: return -9.0
        rats = any(x.name.startswith('스트플을 원하는') for x in cs)
        return 1.3 + (0.6 if rats else 0)
    return 0.0


def plan(g, c, p, kind, R=None, D=None, over=None, virt=(), fresh=False):
    """c를 주체로 한 족보 kind의 최선 → (순이익, [재료]) 또는 None (규칙상 지금 낼 수 있는 재료 조합이 없음)"""
    if R is None: R, D = pools(g, p, fresh)
    mode = MODE[kind]
    ms = with_over(g, p, R if mode == 'release' else D, mode, over, virt)
    if not combo_opp_ok(g, c, p, kind): ms = [m for m in ms if m.where not in ('opp_f', 'opp_g')]   # 「패와 필드」 = 자신 카드만
    if kind in UP_TARGET and not any(x.name == UP_TARGET[kind] for x in g.p[p].upper): return None
    if kind == 'triple':
        r = f_triple(ms, combo_sizes(g, c, p, kind))
    else:
        me = next((m for m in ms if m.card is c), None)
        if me is None and mode == 'deck' and c.zone == 'hand' and c.is_monster() and c.level:
            me = Mat(c, c.level, attrs(g, c), 'hand', 0.9)   # 패에서 발동: 이 카드도 패에서 덱으로
        if me is None: return None
        r = FINDERS[kind](ms, me, combo_sizes(g, c, p, kind))
    if r is None: return None
    tot, sel = r
    if kind in UP_TARGET:
        up = next(x for x in g.p[p].upper if x.name == UP_TARGET[kind])
        if not can_ss_after(g, p, up, sel, c): return None
    elif kind == 'pair' and not steal_cands(g, p, sel): return None
    elif kind == 'triple' and not deck_summons(g, p, sel, c): return None
    return gain_of(g, p, kind, sel, c) - tot, sel


PLAN_ENUM_MAX = 20000   # 재료 조합을 나열할 때 살펴볼 조합 수 상한(넘으면 그 매수는 나열하지 않음)


def plan_options(g, c, p, kind):
    """사람이 고를 족보 재료: 규칙상 지금 낼 수 있는 재료 조합 전부 → [(순이익, [재료])] — 순이익(AI 가치) 높은 순, 같은 이름 · 같은 곳의 카드로 된
    조합은 하나만. 각 조합이 맞는지는 AI와 같은 족보 찾기(FINDERS · f_triple)가 그 재료만으로 그 조합 전부를 쓰는지로 본다 (plan 과 같은 뒤 검사)"""
    from itertools import combinations
    from math import comb
    R, D = pools(g, p, True)
    mode = MODE[kind]
    ms = list(R if mode == 'release' else D)
    if not combo_opp_ok(g, c, p, kind): ms = [m for m in ms if m.where not in ('opp_f', 'opp_g')]
    if kind in UP_TARGET and not any(x.name == UP_TARGET[kind] for x in g.p[p].upper): return []
    sizes = combo_sizes(g, c, p, kind)
    me = None
    if kind != 'triple':
        me = next((m for m in ms if m.card is c), None)
        if me is None and mode == 'deck' and c.zone == 'hand' and c.is_monster() and c.level:
            me = Mat(c, c.level, attrs(g, c), 'hand', 0.9)
        if me is None: return []
        ms = [m for m in ms if m.card is not c]
    ks = sorted({a + b for a, b in sizes}) if kind == 'full' else [sizes]
    out = {}
    for n in ks:
        k = n if kind == 'triple' else n - 1
        if k < 0 or k > len(ms) or comb(len(ms), k) > PLAN_ENUM_MAX: continue
        for sub in combinations(ms, k):
            sub = list(sub)
            r = f_triple(sub, n) if kind == 'triple' else FINDERS[kind](sub, me, sizes)
            if r is None: continue
            sel = r[1]
            if len(sel) != k + (0 if kind == 'triple' else 1): continue
            if kind in UP_TARGET:
                up = next(x for x in g.p[p].upper if x.name == UP_TARGET[kind])
                if not can_ss_after(g, p, up, sel, c): continue
            elif kind == 'pair' and not steal_cands(g, p, sel): continue
            elif kind == 'triple' and not deck_summons(g, p, sel, c): continue
            key = tuple(sorted((m.card.name, m.where) for m in sel))
            net = gain_of(g, p, kind, sel, c) - sum(m.cost for m in sel)
            if key not in out or net > out[key][0]: out[key] = (net, sel)
    return sorted(out.values(), key=lambda x: -x[0])


def pay(g, c, p, sel, mode):
    names = ', '.join(f'{m.card}' + ('(상대)' if m.where in ('opp_f', 'opp_g') else '') for m in sel)
    if mode == 'release':
        g.L(f'코스트: {names} 릴리스')
        for m in sel: g.tribute(m.card, ('cost', c))
    else:
        g.L(f'코스트: {names} 덱으로')
        for m in sel: g.to_deck(m.card, ('cost', c))
        g.shuffle(0); g.shuffle(1)


def take_control(g, t, p):
    """컨트롤을 옮긴다: 몬스터는 몬스터 존(Game.change_control), 마법 · 필드 카드는 자신의 마법 존 · 필드 존 그대로"""
    if t.zone in FIELD_M: return g.change_control(t, p)
    if t.zone == 's':
        fr = g.free_s(p)
        if not fr: return False
        o = g.p[t.controller]; o.s[o.s.index(t)] = None; g.p[p].s[g.pick_zone(p, t, 'spell', fr)] = t; t.controller = p
        return True
    if t.zone == 'fieldz': t.controller = p; return True
    return False


# ═══════════════════════ AI 계획: 레벨 · 속성을 정하는 효과 ═══════════════════════
def best_play(g, p, over=None, virt=()):
    """지금 p가 쓸 수 있는 족보 효과 중 가장 큰 순이익 (없으면 0). over · virt는 가상 부여 · 가상 짐승조커"""
    R, D = pools(g, p)
    gam = gambling_ok(g, p); al = allin(g, p)
    vset = {x for x, _, _ in virt}
    own = list(g.p[p].hand) + [x for x in g.field_cards(p) if x.faceup and not g.is_neg(x) and x not in vset] + list(vset)
    top = 0.0; triple_done = False
    for c in own:
        on_f = c in vset or g.on_field(c)
        for e in c.effects:
            k = getattr(e, 'pk_kind', None)
            if not k or not g.opt_ok(p, c, e): continue
            if k in ('pair', 'triple'):
                if not (al and on_f and grp(c, PK) and (c in vset or c.is_monster() or (over and c in over))): continue
                if k == 'triple' and triple_done: continue
            elif not on_f and not (e.pk_hand or gam): continue
            r = plan(g, c, p, k, R, D, over, virt)
            if k == 'triple': triple_done = True
            if r and r[0] > top: top = r[0]
    return top


def plan_grant(g, p, t):
    """t에 부여할 (레벨, 속성) 중 족보 가치가 가장 큰 것 → (가치, 레벨, 속성). 레벨을 먼저(속성 고정), 그 레벨로 속성을 고른다"""
    at0 = attrs(g, t) & ALL4
    lv0 = t.level if (t.is_monster() and t.level) else 1
    s0 = min(at0) if at0 else SUITS[0]
    blv, bv = lv0, best_play(g, p, over={t: (lv0, frozenset((s0,)))})
    for lv in LEVELS:
        if lv == lv0: continue
        v = best_play(g, p, over={t: (lv, frozenset((s0,)))})
        if v > bv + 1e-9: blv, bv = lv, v
    bs, bv2 = s0, bv
    for s in SUITS:
        if s == s0: continue
        v = best_play(g, p, over={t: (blv, frozenset((s,)))})
        if v > bv2 + 1e-9: bs, bv2 = s, v
    return bv2, blv, bs


def _memo(g, key, fn):
    cache = g.__dict__.setdefault('_pk_memo', {})
    s = _sig(g)
    hit = cache.get(key)
    if hit and hit[0] == s: return hit[1]
    v = fn(); cache[key] = (s, v)
    return v


def mark_cands(g, p, me=None):
    """표시목 1번 대상 후보 (AI는 앞면 카드만 계획): 자신 필드 → 상대 필드(가치 높은 순), 최대 8장"""
    own = [x for x in g.field_cards(p) if x.faceup]
    opp = sorted([x for x in g.field_cards(1 - p) if x.faceup], key=lambda x: -value(g, x))
    return targets(g, p, own + opp)[:8]


def plan_mark(g, p, cands):
    """→ (가치, 대상, 레벨, 속성)"""
    out = (best_play(g, p), None, None, None)
    for t in cands:
        v, lv, s = plan_grant(g, p, t)
        if v > out[0] + 1e-9: out = (v, t, lv, s)
    return out


def plan_joker(g, p, c):
    """짐승조커 1번 선언: 가상으로 자신 필드에 놓아 보고 족보 가치가 가장 큰 (레벨, 속성) → (가치, 레벨, 속성)"""
    hand_lv = [x.level for x in g.p[p].hand + g.monsters(p) if x.is_monster() and x.level and x is not c]
    lv0 = max(set(hand_lv), key=hand_lv.count) if hand_lv else 1   # 기본값: 자신 패 · 필드에 가장 많은 레벨 (다음 원페어용)
    s0 = SUITS[0]
    blv, bv = lv0, best_play(g, p, virt=[(c, lv0, frozenset((s0,)))])
    for lv in LEVELS:
        if lv == lv0: continue
        v = best_play(g, p, virt=[(c, lv, frozenset((s0,)))])
        if v > bv + 1e-9: blv, bv = lv, v
    bs, bv2 = s0, bv
    for s in SUITS[1:]:
        v = best_play(g, p, virt=[(c, blv, frozenset((s,)))])
        if v > bv2 + 1e-9: bs, bv2 = s, v
    return bv2, blv, bs

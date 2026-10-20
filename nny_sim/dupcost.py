"""두플리카토르 코스트 표 — 세리 - 두플리카토르 1번 [지속] 「서로가 카드의 발동을 위해 코스트로 지불해야 하는 카드의 매수는 2배가 된다」
(정본 3-6 f 재정 · 재정 정리 2026-10-17: 세리식 코스트만이 아니라 카드 매수로 지불하는 모든 코스트).

카드 이름 → {효과 번호: [코스트 명세, …]}. 명세 = (동작, 후보 함수 또는 None, 원래 매수 중 후보에서 내는 매수, 늘어나는 매수[, 적용 조건]).
  - 후보 None: 코스트가 「이 카드」뿐 → 「이 카드 1장」으로 보아 2배 = 이 카드 + 이 카드가 있던 곳의 다른 카드 1장 (Game.cost_extra_pool)
  - 후보 함수 (g, c, p) → 그 코스트로 낼 수 있는 카드 목록: 원래 n장 → 2n장 (n장 더)
  - 적용 조건 (g, c, p) → False면 이번 발동에는 카드 코스트가 없다(면제 · 카운터로 대신 내는 경우)
동작: grave(묘지로) · release(릴리스) · banish(제외) · deck(덱으로) · hand(패로) · hand_opp(상대 패로) · deck_grave(덱에서 묘지로).

넣지 않은 코스트 (코드에서 따로 2배로 하거나 해석이 남은 것):
  - 세리의 덱 위 제외 · 제외 존→덱 코스트, 스키푸스: cards4가 직접 2배
  - 소원의 분수 1 · 2번: cards5가 직접 2배 (종류별 매수)
  - 포커짐승들 족보(「이 카드를 포함하는 … n장」 · 올인 원페어 · 트리플): cards8.combo_sizes가 텍스트의 매수로 직접 2배 —
    이 카드를 뺀 나머지만 2배(사용자 답변 2026-10-20), 늘어난 재료도 족보 조건을 지킨다(ASSUME)
  - 더 바이러스 · 더 딜리트 1번: 소환 절차이므로 「카드의 발동」이 아니다
  - 「보여주고 발동」(공개)은 지불이 아니다. 봉인 · 저주 카운터는 카드가 아니다(정본 6)
  - 행운의 도적 1번(「보내고 발동할 수도 있다」 — 임의 코스트): 넣지 않음
"""


def _own_grave(pred):
    return lambda g, c, p: [x for x in g.p[p].grave if pred(x)]


def _own_mons(pred, release=False):
    return lambda g, c, p: [m for m in g.monsters(p) if m.faceup and pred(m) and (not release or g.releasable(m))]


def table():
    from cards import grp
    from cards10 import rel_pool, DBM, leaves_ok
    import cards7 as C7
    SOL = lambda x: x.has('솔루나') and x.is_monster()
    CIEL = lambda x: grp(x, '시엘') and x.is_monster()
    SIA = lambda x: grp(x, '시아') and x.is_monster()
    SELF_HAND = [('grave', None, 0, 1)]
    SELF_REL = [('release', None, 0, 1)]
    SELF_BANISH = [('banish', None, 0, 1)]
    SELF_GRAVE = [('grave', None, 0, 1)]
    ciel_paid = lambda g, c, p: not g.rule('ciel_cost_free', p, c)
    t = {
        # ── 공용 ──
        '명계의 징벌': {2: SELF_BANISH},
        # ── 번성충 ──
        '번성충-시체송장벌레': {1: [('banish', lambda g, c, p: list(g.p[1 - p].grave), 1, 1)]},
        '번성충-먹이바구미': {1: SELF_HAND}, '번성충-노린재': {1: SELF_HAND}, '번성충-주기매미': {1: SELF_HAND},
        '번성충-병정흰개미': {1: SELF_HAND}, '번성충-하루살이대군': {1: SELF_HAND},
        '번성충-메뚜기여왕': {1: [('release', lambda g, c, p: [x for x in g.field_cards(1 - p) if g.releasable(x)], 1, 1)]},
        '번성충-장수말벌여왕': {1: [('release', lambda g, c, p: [x for x in g.spells(1 - p) if g.releasable(x)], 1, 1)]},
        # ── 솔루나 ──
        '솔루나 아츠 - 여명과 황혼의 궤적': {1: [('hand', _own_mons(SOL), 1, 1)]},
        '솔루나 아츠 - 천체정렬': {2: [('grave', lambda g, c, p: [x for x in g.p[p].hand if x.name == c.name], 1, 1), ('banish', _own_grave(lambda x: True), 0, 1)]},
        '시엘 아츠 - 월영침식': {1: [('banish', _own_mons(CIEL), 1, 1, ciel_paid)]},
        '시엘 아츠 - 잔월의 유산': {1: [('grave', _own_mons(CIEL), 1, 1, ciel_paid)]},
        '시엘 아츠 - 월영암수': {1: [('hand_opp', _own_mons(CIEL), 1, 1, ciel_paid)]},
        '시아 아츠 - 여명신광': {1: [('deck', lambda g, c, p: [x for x in g.field_cards(p) if x.has('시아') and x.faceup and x is not c], 1, 1)]},
        '시아 아츠 - 성광난무': {1: [('hand', _own_mons(SIA), 1, 1)]},
        '시아 아츠 - 일광지로': {1: [('deck', _own_mons(SIA), 1, 1)]},
        '시아 아츠 - 성광소각': {1: [('grave', lambda g, c, p: [m for m in g.monsters(0) + g.monsters(1) if SIA(m) and m.faceup], 1, 1)]},
        # ── 격투가 ──
        '격투가 입장': {2: SELF_BANISH},
        # ── 소원의 분수 ──
        '지혜의 원천 - 마도서': {1: [('grave', lambda g, c, p: [x for x in g.field_cards(p) if x is not c], 1, 1)]},
        '희생의 성녀': {2: SELF_GRAVE},
        # ── 호박옥 ──
        '호박옥 - 결정충': {2: SELF_GRAVE},
        '호박옥 - 반혼체': {1: [('deck', _own_grave(C7.AMB), 2, 2)]},
        '호박옥 - 태고의 수해': {3: SELF_BANISH},
        # ── 던전마스터 ──
        '던전마스터 새크리파이스': {1: SELF_HAND, 2: SELF_HAND, 3: SELF_HAND},
        '던전마스터 망령': {1: SELF_REL}, '던전마스터 다크나이트': {1: SELF_REL}, '던전마스터 다크엘프 어새신': {2: SELF_REL},
        # ── 데이터버그 ──
        '데이터버그 캐터필러': {1: SELF_REL}, '데이터버그 코쿤': {1: SELF_REL},
        '데이터버그 앤트': {1: SELF_HAND}, '데이터버그 웜': {1: SELF_HAND},
        '데이터버그 에볼루션 마스터': {1: [('release', lambda g, c, p: rel_pool(g, p), 2, 2)]},
        '데이터버그 퀸 비': {2: [('release', lambda g, c, p: rel_pool(g, p), 2, 2)]},
        '데이터버그 유니온 마스터': {1: [('release', lambda g, c, p: rel_pool(g, p), 2, 2)]},
        '데이터버그 로딩': {2: [('release', lambda g, c, p: rel_pool(g, p, both=True), 2, 2)]},
        '데이터버그 습격': {1: [('grave', lambda g, c, p: [m for m in g.monsters(0) + g.monsters(1) if DBM(m) and m.faceup and leaves_ok(g, m)], 2, 2)]},
    }
    # 호박옥의 수호자: 1번(마르모르 · 카르분쿨루스 — 릴리스할 때만, 봉인 카운터로 대신 내면 카드 코스트 없음) · 3번 상급 덱 1장 묘지로 · 4번 [유언] 묘지 1장 제외
    rel_own = lambda g, c, p: [m for m in g.monsters(p) if m is not c and m.is_monster() and g.releasable(m)]
    for name in C7.GUARDS:
        t[name] = {3: [('deck_grave', lambda g, c, p: [x for x in g.p[p].upper if C7.AMB_MON(x)], 1, 1)],
                   4: [('banish', lambda g, c, p: [x for x in g.p[p].grave if x is not c and C7.AMB(x)], 1, 1)]}
    for name in ('호박옥의 수호자 - 마르모르', '호박옥의 수호자 - 카르분쿨루스'):
        t[name][1] = [('release', rel_own, 1, 1, lambda g, c, p: bool(rel_own(g, c, p)))]
    return t


_T = None


def apply(c):
    """Impl.attach에서 부른다: 표에 있는 효과에 Effect.cost_spec을 단다 (번호 0 — 카드를 놓기만 하는 발동 — 은 제외)"""
    global _T
    if _T is None: _T = table()
    spec = _T.get(c.name)
    if not spec: return
    for e in c.effects:
        if e.num and e.num in spec: e.cost_spec = spec[e.num]

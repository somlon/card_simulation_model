"""카드 효과 구현. 카드 텍스트 → Effect 객체.
ASSUME 주석 = 규칙명세/재정 목록의 【가정】.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
POOL = {c['name']: c for c in json.load(open(os.path.join(HERE, 'card_pool.json'), encoding='utf-8'))}


class _Implemented:
    """구현된 카드 이름 = 조립표(blocks/t_*.py)가 있는 카드 (deck_opt · season의 「구현된 카드」 판정)"""
    def __contains__(self, name):
        from blocks import dsl
        d = POOL.get(name)
        return d is not None and d.get('code') in dsl.TABLE


IMPL = _Implemented()

def grp(x, name):
    """카드군 판정 (카드 자료의 「카드군」 필드). 필드가 없는 옛 형식 카드는 이름에 포함되는지로 본다.
    「기적의 영웅」처럼 효과로 다른 카드군으로도 취급되는 카드는 flags['also_groups']"""
    gs = x.d.get('groups')
    if gs is None: return name in x.name
    return name in gs or (name in x.flags.get('also_groups', ()) and also_ok(x))   # 「필드의 이 카드는 … 로도 취급」

def also_ok(x):
    """[지속] 「필드의 이 카드는 … 카드로도 취급한다」가 지금 적용되는가: 앞면으로 필드에 있고 무효가 아니며(사용자 답변 2026-10-22),
    그 [지속]을 이 턴에 이미 적용하지 않았을 때(Game.cont_use가 남기는 flags['cont_spent'] — 1턴 1번)"""
    n = (getattr(x, 'cont_nums', None) or {}).get('flag:also_groups')
    neg = x.negated or bool(x.flags.get('perma_neg')) or any(e.flags.get('negates_host') for e in x.equips)
    return x.zone in ('m', 'shared') and x.faceup and not neg and n not in x.flags.get('cont_spent', ())

class Impl:
    pool = POOL
    @staticmethod
    def attach(c):
        import blocks
        if blocks.attach(c): return   # 조립표가 있는 카드는 블록으로 조립 (blocks/README.md) — 없으면 아래 옛 카드 함수
        c.flags['unimplemented'] = True   # 조립표가 없는 카드(카드 풀에 새로 들어온 카드) — 효과 없음

SELF_REF = r'이 카드(를|와|도|는|만)'          # 이 카드를 가리키는 말
SELF_TAKE = r'소환|패에 넣|패로 (되돌|가져)'   # 소환 · 패에 넣기(같은 이름 규칙 Game.pickable 이 보는 처리)


def sentences(line):
    """효과 문장 → 문장들(마침표 뒤 공백에서 나눔 — 「…고 발동.」 · 「…한다.」 · 「…)」)"""
    import re as _re
    return [x for x in _re.split(r'\.\s+', line) if x.strip()]


def text_attrs(e, line, name):
    """효과 문장 line(카드 name의 그 번호 줄, 부여 효과는 부여하는 카드의 「-」 항목)에서 Effect의 성질을 단다 — Impl.attach · 부여 효과(cards2.cer_effect) 공통"""
    import re as _re
    # 같은 이름 예외 자동 표시: 해당 번호 효과 문장에 「동명」 허용 문구나 자기 카드명이 가져오기 · 특수소환 대상으로 적힌 경우
    if _re.search(r'동명의 카드를 (패에 넣을|특수소환할) 수 있다', line) or \
       (f'「{name}」' in line and _re.search(r'특수소환|패에 넣', line)):
        e.same_name_ok = True
    # 같은 이름 규칙(engine.Game.pickable)의 자기 자신 예외: 이 카드를 직접 소환하거나 패에 넣는 문장이 있다 (「묘지의 이 카드를 특수소환한다」 ·
    # 「이 카드는 … 패에서 특수소환할 수 있다」 등) — 같은 문장 안이어야 한다. 「이 카드를 덱으로 되돌린다. 덱에서 「X」 몬스터를 특수소환한다」처럼
    # 다른 문장이면 덱으로 돌아간 이 카드를 고를 수 없다(저주인형 - 저주인형 3번 — 사용자 지시 2026-10-29)
    if _re.search(r'(이 카드|자신)를? ?포함하는|자신을 포함하는', line) or any(_re.search(SELF_REF, x) and _re.search(SELF_TAKE, x) for x in sentences(line)):
        e.self_ok = True
    # 대상 지정 효과인가 (발동 판정 중 내성 판정 — engine.Game.immune): 문장에 「대상으로 하고」가 있으면 대상 지정, 없으면 비대상
    if line: e.targets_text = bool(_re.search(r'대상으로 하', line))
    # 「서로가 … 하고 발동」: 어느 플레이어든 발동할 수 있다 (세제 2 · 3번 — 사용자 답변 2026-10-20, engine.Game.zone_ok · options)
    if _re.match(r'^\d+\.\s*서로가 [^.]*고 발동\.', line): e.either_player = True
    e.cost_items = parse_cost(line)   # 코스트 문장 (델레가토르 — engine.Game.transfer_ok)
    # 코스트의 「필드」에 상대 필드가 드는가 (cost_opp — 「서로」 · 「상대」가 적혀 있을 때만, 사용자 답변 2026-10-22 Q41)
    e.cost_opp_field = cost_opp_field(line)
    # 제거 효과인가 — 대상(「그 카드 …」)을 파괴 · 묘지로 · 제외 · 패 · 덱으로 옮긴다. 뒷면 마법은 이런 효과의 대상만 될 수 있다
    # (engine.Game.immune, 사용자 답변 2026-10-23 PDF Q6)
    if line: e.removal_text = e.targets_text and removal_text(line)
    # 처리의 첫 단계가 드로우인가('self' / 'opp' — 드로우하는 쪽) — 「효과로 덱에서 패에 넣을 수 없다」면 발동할 수 없다 (engine.Game.legal)
    e.draw_first = draw_first_text(line)
    # 처리에서 발동한 플레이어가 반드시 하는 행동 — 행동 세금을 발동할 때 코스트로 낸다 (engine.Game.pay_tax, 사용자 답변 2026-10-28)
    e.sure_acts = sure_acts(line) if e.num else frozenset()   # 0번 = 카드를 놓기만 하는 발동 (텍스트는 [지속] 문장)

def granted_lines(d):
    """카드 자료 d의 텍스트에서 부여하는 효과의 「-」 항목들 (앞의 「-」는 뗀다)"""
    return [l.strip()[1:].strip() for l in (d.get('text') or '').split('\n') if l.strip().startswith('-')]

# ───────────── 공통 헬퍼 ─────────────
def own_turn(g, p): return g.turn_player == p
def main_ok(g, p): return own_turn(g, p) and g.phase in ('진행', '정비') and not g.chain
def opp_cards(g, p): return g.field_cards(1 - p)
def value(g, c):
    if c.is_monster(): return 1 + g.atk(c) / 1000 + (1.5 if c.level >= 8 else 0)
    if c.type == '필드': return 2.2
    if c.d.get('subtype') == '지속' or c.equip_to: return 1.8
    if c.type == '스킬': return 2.5   # 무효 효과의 대상 (사용자 답변 2026-10-22 — 그 턴 종료 시까지)
    return 1.2 if c.faceup else 1.5
def best(g, cands, p, purpose='remove'):
    return g.p[p].ai.pick_target(g, p, cands, purpose) if cands else None
VETO = -10 ** 6   # AI 점수: 규칙상 발동할 수 있어도 AI는 고르지 않는다 (HeuristicAI는 0 이하, LearnedAI는 이 값 이하를 후보에서 뺀다)
def field_pick(g, p, purpose='remove', pool=None, src=None):
    """「필드의 카드」 = 자신 · 상대 양쪽 필드 (§14, §15-1).
    상대 카드가 있으면 그중에서 AI가 고르고, 없으면 손해가 가장 적은 자신의 카드를 고른다.
    src = 효과의 주체 카드(주면 「「X」 카드 이외의 효과를 받지 않는다」를 그 카드로 판정 — cards2.targets와 같은 규칙, 2026-10-15)"""
    cands = [x for x in (g.all_field() if pool is None else pool) if not g.immune(x, p, src)]   # 효과를 받지 않는 카드는 고르지 않는다
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
def hand_add(ev):
    """「패에 넣었을 때」 사건이면 (카드, 넣은 플레이어, 출발 영역), 아니면 None — 효과로 덱 · 묘지에서 패에 넣기(added_to_hand)와
    드로우(draw — 턴 시작 드로우 포함, 라운드 시작 패 · 멀리건 제외) 모두 (사용자 답변 2026-10-28: 「패에 넣었을 때」에 드로우 포함 —
    데이터버그 플라이 · 사기 감지 · 염원 · 트랩: 거짓 샘물 · 포커짐승들의 쇠망치)"""
    if ev_is(ev, 'added_to_hand'): return ev['card'], ev['player'], ev['prev']
    if ev_is(ev, 'draw') and ev.get('turn', 0) >= 1: return ev['card'], ev['player'], ev.get('prev', 'main')
    return None


# ── 카드 텍스트 판정 (여러 카드가 같은 문구를 쓰는 규칙은 텍스트에서 한 번에 판정한다 — CLAUDE.md R6) ──
import re as _re_t

def eff_text(c, num):
    """카드 c의 num번 효과 문장 (「num.」으로 시작하는 줄부터 다음 번호 전까지)"""
    lines, on = [], False
    for x in (c.d.get('text') or '').split('\n'):
        if _re_t.match(r'^\d+\.', x): on = x.startswith(f'{num}.')
        if on: lines.append(x)
    return ' '.join(lines)

# 필드의 카드를 필드가 아닌 곳(묘지 · 제외 존 · 덱 · 패)으로 옮기는 처리 동사(능동형만 — 「파괴되지 않는다」 · 「파괴되었을 때」 같은 보호 · 조건 문구는 빼고).
# 「파괴」는 언제나 필드의 카드를 묘지로 보낸다
_LEAVE = _re_t.compile(r'(파괴|제외|릴리스)(한다|하고|하며)|되돌린다|되돌리고|패에 넣는다|패에 넣고|묘지로 보낸다|묘지로 보내고|덱으로 보낸다')
_DESTROY = _re_t.compile(r'파괴(한다|하고|하며)')
_SELF_CLAUSE = _re_t.compile(r'(자신 필드|자신의 필드|이 카드)[^.,]*')
_REF_CLAUSE = _re_t.compile(r'그 (카드|몬스터|효과)[^.,]*')

def effect_body(c, num):
    """효과 문장에서 처리 부분(「…발동(한다).」 뒤, 발동 문구가 없으면 번호 뒤 전체). 괄호 안의 단서는 뺀다"""
    t = _re_t.sub(r'^\d+\.\s*', '', eff_text(c, num))
    parts = _re_t.split(r'발동(?:한다)?\.', t, maxsplit=1)
    return _re_t.sub(r'\([^)]*\)', '', parts[1] if len(parts) > 1 else t)

_COND_END = _re_t.compile(r'(경우|때|상태에서|1턴에 \d+번)$')
_NOT_PAY = _re_t.compile(r'(대상으로 하|보여주|지정하|고르)$')

def parse_cost(line):
    """효과 문장의 코스트(「…하고 발동」 · 「…고 발동한다」)를 항목으로: [{'text', 'self', 'deck'}]. 대상 지정(「대상으로 하고 발동」)과
    공개(「보여주고 발동」)는 지불이 아니므로 뺀다(「지정하고」 · 「고르고」도 대상 지정). 조건 구절(「…경우, 」 · 「…때, 」 · 「1턴에 1번, 」)은 뺀다.
    self: 「이 카드를 …」 · 「이 카드의 …」 · 「자신을 포함하는 …」 — 이 카드 자신으로 내는 코스트
    deck: 「덱의 위에서부터 카드를 n장 제외」 · 「덱에서 카드를 n장 제외」 — 덱으로 내는 코스트"""
    t = _re_t.sub(r'^\d+\.\s*', '', line or '')
    out = []
    for m in _re_t.finditer(r'([^.]*?)고 발동', t):
        for ph in _re_t.split(r'고,\s*', m.group(1)):
            parts = ph.split(',')
            start = max([i + 1 for i, x in enumerate(parts) if _COND_END.search(x.strip())] or [0])
            last = ','.join(parts[start:]).strip()
            if not last or _NOT_PAY.search(last): continue
            out.append({'text': last,
                        'self': bool(_re_t.search(r'이 카드(를|의)|자신을 포함하는|이 카드를 포함하는', last)),
                        'deck': bool(_re_t.search(r'덱의 위에서부터 카드를 \d+장 제외|덱에서 카드를 \d+장 제외', last))})
    return out

def cost_opp_field(line):
    """코스트 문장(「…고 발동」 앞)의 「필드」에 상대 필드가 드는가: 「서로」 · 「상대」가 적혀 있을 때만.
    적혀 있지 않은 「필드의(필드에서) …를 릴리스하고 · 묘지로 보내고 발동」은 자신 필드다 (사용자 답변 2026-10-22 Q41 — 데이터버그 로딩 2번 · 습격,
    Q21 마르모르 · 카르분쿨루스 「필드의 릴리스 가능한 몬스터」, Q26 족보 재료 cards8.combo_opp_ok와 같은 규칙)"""
    # 조건 구절(쉼표 뒤) · 대상 지정은 parse_cost가 빼고, 쉼표 없는 조건 구절(「상대가 …했을 때 자신 필드의 …」)은 여기서 뺀다
    return any(_re_t.search(r'서로|상대', _re_t.split(r'(?:때|경우),?\s+', it['text'])[-1]) for it in parse_cost(line))


_DRAW_FIRST = _re_t.compile(r'^(자신은|상대는|상대 플레이어는)?\s*(자신의\s*)?(메인 |상급 )?(덱에서\s*)?(카드를\s*)?\d+장을?\s*드로우')

def draw_first_text(line):
    """효과 처리의 첫 단계가 드로우인가 — 드로우만 하는 효과 · 「드로우하고 …」. 드로우하는 쪽을 돌려준다('self' / 'opp', 아니면 None).
    처리 부분 = 「…발동(한다 · 할 수도 있다).」 뒤(없으면 번호 · [종류] 표기 뒤 전체), 첫 문장이 드로우로 시작하는지 본다.
    「덱으로 되돌리고 1장 드로우」처럼 다른 처리가 먼저면 None — 발동은 되고 드로우만 하지 않는다 (사용자 답변 2026-10-23 PDF Q7 · 후속 답변)"""
    t = _re_t.sub(r'\([^)]*\)', '', _re_t.sub(r'^\d+\.\s*', '', line or ''))   # 단서 괄호(「(이 효과는 강제로 발동한다.)」)를 먼저 뺀다
    parts = _re_t.split(r'발동(?:한다|할 수도 있다)?\.', t, maxsplit=1)
    body = _re_t.sub(r'^\s*(\[[^\]]*\]\s*)+', '', parts[1] if len(parts) > 1 else t).strip()
    m = _DRAW_FIRST.match(body)
    if not m: return None
    return 'opp' if m.group(1) and m.group(1).startswith('상대') else 'self'

# ── 행동 세금: 「서로가 …할 때마다, 그 플레이어는 자신의 덱의 위에서부터 카드를 n장 제외한다」 [지속] (세 - 아이라리움 1번 · 세제 1번 · 취득세 1번) ──
# 행동하는 플레이어가 내는 코스트다 (사용자 답변 2026-10-27 · 10-28 — engine.Game.pay_tax). 「…할 때마다」 구절의 말로 행동 종류를 정한다
_TAX = _re_t.compile(r'서로가 ([^,]*?) 때마다, 그 플레이어는 자신의 덱의 위에서부터 카드를 (\d+)장 제외한다')
_TAX_ACTS = (('드로우', 'draw'), ('패에 카드를 넣', 'draw'), ('효과를 발동', 'activate'), ('특수소환', 'special'))

def action_taxes(d):
    """카드 자료 d의 [지속] 행동 세금 [(효과 번호, 행동, 매수)] — 행동: 'draw'(드로우 · 덱에서 패에 넣기) · 'activate'(효과의 발동) · 'special'(특수소환)"""
    out = []
    for l in (d.get('text') or '').split('\n'):
        m = _re_t.match(r'^(\d+)\.\s*\[지속\]', l); t = m and _TAX.search(l)
        if not t: continue
        for a in dict.fromkeys(a for k, a in _TAX_ACTS if k in t.group(1)):
            out.append((int(m.group(1)), a, int(t.group(2))))
    return out

# 처리에서 반드시 하는 행동: 드로우 · 덱에서 패에 넣기 / 특수소환
_SURE = {'draw': _re_t.compile(r'드로우(한다|하고)|덱(?: 맨)?(?: 위)?에서[^.]*?패에 넣(는다|고)'),
         'special': _re_t.compile(r'특수소환(한다|하고)')}
# 처리 때 그 행동을 하지 않을 수 있는 표시: 조건(문장 앞머리 — 문장 전체에 걸린다) / 선택 · 수량(그 행동의 구절에만 걸린다)
_IF = _re_t.compile(r'경우|때마다')
_CHOICE = _re_t.compile(r'까지|거나|만큼|그 중|수 있다|수도 있다|/')
_NO_DECL = _re_t.compile(r'발동 선언을 필요로 하지 않는다|별도의 발동 처리를 필요로 하지 않는다')

def sure_acts(line):
    """효과 문장 line의 처리에서 발동한 플레이어가 반드시 하는 행동('draw' · 'special')의 집합 — 그 행동 세금은 발동할 때 코스트로 낸다
    (사용자 답변 2026-10-28 「확정된 것만 발동 때」, engine.Game.activate). 조건이 붙은 문장(「…경우」 · 「…때마다」), 선택 · 수량이 붙은 구절
    (「…까지」 · 「…거나」 · 「그 수만큼」 · 「그 중」 · 「…할 수 있다」 · 「덱/묘지」 — 「…고」로 나눈 구절 단위: 「3장까지 덱으로 되돌리고 1장 드로우한다」의 드로우는 반드시),
    상대가 하는 행동(「상대는 …」), 바꾼 뒤의 효과 문장(「「…」로 변경한다」), 발동 선언이 없는 효과는 빼고 — 그 행동은 실제로 할 때 직전에 낸다(engine.Game.tax_before)"""
    if not line or _NO_DECL.search(line) or _re_t.match(r'^\d+\.\s*\[지속\]', line): return frozenset()   # [지속]은 발동하지 않는다
    t = _re_t.sub(r'\([^)]*\)', '', _re_t.sub(r'^\d+\.\s*', '', line))
    # 바꾼 뒤의 효과 문장(노린재 · 이탈세 2번 · 깜짝상자 1번) — 안에 겹친 카드 이름 「」는 먼저 다른 괄호로 바꿔 둔다
    t = _re_t.sub(r'「([^「」]*)」', lambda m: m.group(0) if _re_t.search(r'다\.?$', m.group(1)) else f'⟨{m.group(1)}⟩', t)
    t = _re_t.sub(r'「[^「」]*다\.?」', '', t)
    parts = _re_t.split(r'발동(?:한다|할 수도 있다)?\.', t, maxsplit=1)
    body = _re_t.sub(r'^\s*(\[[^\]]*\]\s*)+', '', parts[1] if len(parts) > 1 else t)
    out = set()
    for s in _re_t.split(r'\.', body):
        if not s.strip() or _IF.search(s) or _re_t.match(r'\s*상대(는| 플레이어는)', s): continue
        for cl in _re_t.split(r'(?<=고),?\s+', s):
            if not _CHOICE.search(cl): out.update(a for a, rx in _SURE.items() if rx.search(cl))
    return frozenset(out)

def act_score(g, c, e, p, ev, default):
    """AI가 보는 효과 점수 (e.score, 없으면 default). 발동할 때 내는 행동 세금으로 p가 바로 덱아웃 패배하면(engine.Game.tax_ruin) 고르지 않는다(VETO) —
    규칙상 발동할 수 있지만(사용자 답변 2026-10-27) 스스로 지는 발동이다. 강제 효과는 그대로 발동한다"""
    if not e.mandatory and g.tax_ruin(p, c, e): return VETO
    return e.score(g, c, p, ev) if e.score else default

def removal_text(line):
    """효과 문장(그 번호 줄만 — 부여하는 「- …」 하위 효과는 보지 않음)의 처리 부분에서, 발동한 쪽 자신의 카드(「자신 필드 …」 · 「이 카드 …」)를
    옮기는 구절을 뺀 나머지에 이동 동사(파괴 · 제외 · 묘지로 · 패 · 덱으로)가 있는가 — 대상을 필드에서 제거하는 효과"""
    t = _re_t.sub(r'^\d+\.\s*', '', line or '')
    parts = _re_t.split(r'발동(?:한다)?\.', t, maxsplit=1)
    body = _re_t.sub(r'\([^)]*\)', '', parts[1] if len(parts) > 1 else t)
    return bool(_LEAVE.search(_SELF_CLAUSE.sub('', body)))


def moves_off_field(g, link, p):
    """그 발동이 「p의 필드의 카드를 필드에서 벗어나게 하는 효과」인가 — 필드에 있는 카드를 필드가 아닌 위치로 이동시키는 효과
    (사용자 답변 2026-10-20 · 이탈세 2번 · 각성의 태동 1번). 발동 선언 때 판정한다:
    ① 발동 시 고른 대상(engine.link_targets)에 p의 필드 카드가 있고 처리 문장이 「그 카드 · 그 몬스터」를 옮기거나
    ② 처리 문장에서 발동한 쪽 자신의 카드(「자신 필드 …」 · 「이 카드 …」)와 대상을 가리키는 구절을 뺀 나머지의 한 구절이 필드의 카드를 옮기면
    (「파괴한다」 또는 「필드」 + 이동 동사). [지속] 효과는 발동하지 않으므로 해당 없음"""
    from engine import link_targets
    if not g.field_cards(p): return False
    body = effect_body(link.card, link.eff.num)
    if not _LEAVE.search(body): return False
    if any(g.on_field(x) and x.controller == p for x in link_targets(link)) and \
       any(_LEAVE.search(m.group(0)) for m in _REF_CLAUSE.finditer(body)): return True
    rest = _REF_CLAUSE.sub('', _SELF_CLAUSE.sub('', body))
    # 같은 구절(마침표 · 쉼표로 나뉜 부분) 안에서 「필드」와 이동 동사가 함께 나와야 한다 (조건 구절의 「필드」는 세지 않음)
    return any(_DESTROY.search(cl) or ('필드' in cl and _LEAVE.search(cl)) for cl in _re_t.split(r'[.,]', rest))


# ═══════════════════════ 솔루나 (본편) ═══════════════════════


# ── 아츠 2단 구조 (2026-10-08 텍스트 · 재정): 2번은 「1번 효과 처리 시에 … 존재할 경우」 1번 처리에 자동으로 딸려 처리된다
#    (별도 발동 없음). 2번도 1턴 1회 제약을 받는다 — 이번 턴 2번을 이미 처리했으면 1번만 처리한다.
#    1번이 무효화되면 2번도 처리되지 않는다. 2번 조건은 1번 처리 시점에 판정한다 ──

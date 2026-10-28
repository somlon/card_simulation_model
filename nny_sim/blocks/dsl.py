"""조립표 작성 문법 (blocks/README.md).

조립표 한 줄 = fx(카드 코드, 효과 키, 문장 틀, 조립 명세…):

    fx('FGTR-001', '1', '[신속] 패에서 이 카드를 보여주고 상대 필드의 카드 {n}장을 대상으로 하고 발동. 그 카드를 파괴하고 자신의 패를 {m}장 버린다.',
       zones=HAND,
       cost=[target('T', S('opp', 'field'), n='$n')],
       do=[destroy(ref='T'), discard('$m')])

- 문장 틀의 {이름}은 텍스트에서 읽는 수치. 명세의 '$이름'이 그 값으로 바뀐다.
- cost: 「…하고 발동」 앞부분 — 코스트 블록과 발동 시 고르는 대상(target)을 텍스트 순서대로.
- do: 처리 블록을 텍스트 순서대로. 재정 G2(2026-10-17): 앞 처리를 해야 뒤 처리도 하고(J1), 발동은 모든 처리를 할 수 있을 때만.
  branch(조건, [처리…], [다른 처리…])는 J2 분기. 처리 블록에 may=True면 「…할 수 있다」(하지 않아도 다음 처리로 간다).
- when: 발동 시점(E 블록), cond: 발동 조건(C1), cont: [지속] 적용 블록.
- 효과 틀(F): 키워드 · 단서 괄호에서 자동으로 읽고(text.notes), 여기 적은 값이 우선한다.
"""
from collections import namedtuple

Blk = namedtuple('Blk', 'name k')
Spec = namedtuple('Spec', 'code key tmpl kw')

TABLE = {}      # 카드 코드 → {효과 키: Spec}
THEMES = {}     # 카드 코드 → 조립표 모듈 이름 (CHANGES · 진행 확인용)


def fx(code, key, tmpl, **kw):
    """조립표 한 줄 등록"""
    TABLE.setdefault(code, {})[str(key)] = Spec(code, str(key), tmpl, kw)


def card_done(code, **kw):
    """효과 줄 없이 카드 단위 설정만 있는 카드(예: [제약]만 있는 문장)도 조립된 카드로 표시"""
    TABLE.setdefault(code, {})


# ── 카드 집합 ──
def S(side='both', zone='field', kind=None, **f):
    """카드 집합: side 'own' · 'opp' · 'both', zone 'field' · 'mzone' · 'szone' · 'hand' · 'grave' · 'banish' · 'deck' · 'main' · 'upper' · 'skill' (튜플 가능),
    kind 'monster' · 'spell' · 'card' · ('trigger',) …, 그 밖 필터: group · name · faceup · not_self · level · atk · def · counter · attr · pred"""
    d = dict(side=side, zone=zone, kind=kind)
    d.update(f)
    return d


def B(name, **k):
    return Blk(name, k)


# ── 고르기 (S1) ──
def target(ref, scope, n=1, **k):
    """발동 시 고르는 대상(「…를 대상으로 하고 발동」) — l.ctx[ref]"""
    return B('pick', ref=ref, scope=scope, n=n, targeted=True, at='act', **k)


def choose_at_act(ref, scope, n=1, **k):
    """발동 시 고르지만 대상 지정이 아닌 것(「…를 고르고 발동」)"""
    return B('pick', ref=ref, scope=scope, n=n, targeted=False, at='act', **k)


def choose(ref, scope, n=1, **k):
    """처리 때 고르기(「…를 고르고」 · 「1장을 골라」) — 대상 지정 아님"""
    return B('pick', ref=ref, scope=scope, n=n, targeted=False, at='res', **k)


# ── 처리 · 코스트 블록 (A) ──
def destroy(**k): return B('destroy', **k)
def send_grave(**k): return B('move', dest='grave', **k)
def banish(**k): return B('move', dest='banish', **k)
def to_deck(**k): return B('move', dest='deck', **k)
def to_hand(**k): return B('move', dest='hand', **k)
def release(**k): return B('release', **k)
def special(**k): return B('special', **k)
def search(scope, n=1, **k): return B('search', scope=scope, n=n, **k)
def draw(n=1, who='self', **k): return B('draw', n=n, who=who, **k)
def damage(amt, who='opp', **k): return B('damage', amt=amt, who=who, **k)
def heal(amt, who='self', **k): return B('heal', amt=amt, who=who, **k)
def counter(name, n=1, op='add', **k): return B('counter', name=name, n=n, op=op, **k)
def negate_link(**k): return B('negate_link', **k)
def negate_card(**k): return B('negate_card', **k)
def extra_attack(n=1, **k): return B('extra_attack', n=n, **k)
def stat(amt, stat='atk', **k): return B('stat', amt=amt, stat=stat, **k)


def discard(n=1, **k):
    """자신의 패를 n장 버린다(패 → 묘지)"""
    return B('move', dest='grave', scope=S('own', 'hand'), n=n, harm=True, **k)


def branch(cond, then, other=(), prob=None):
    """J2 분기 — cond(조건 블록)가 참이면 then, 아니면 other. prob: 우연(주사위 등)이면 then의 확률 — AI 점수의 기댓값"""
    return B('branch', cond=cond, then=tuple(then), other=tuple(other), prob=prob)


# ── 시점 (E) · 조건 (C1) ──
def when(name, **k): return B('when_' + name, **k)
def cnt(scope, op='>=', n=1): return B('cnt', scope=scope, op=op, n=n)
def cond(name, **k): return B('cond_' + name, **k)


# 자주 쓰는 발동 위치
HAND = ('hand',)
FIELD = ('field',)
GRAVE = ('grave',)
SKILL = ('skill',)
HAND_FIELD = ('hand', 'field')


def choice(*options, chooser='self'):
    """J2 선택지 「A하거나 B한다」 — 할 수 있는 선택지 중 고르는 사람이 자신에게 나은 것(가치 기준). chooser='opp': 「상대는 …하거나 …한다」"""
    return B('choice', options=tuple(tuple(o) for o in options), chooser=chooser)


def roll(as_='D', sides=6): return B('roll', sides=sides, **{'as': as_})
def ref_in(ref, *vals): return B('cond_ref_in', ref=ref, vals=tuple(vals))
def status(kind, until='turn', **k): return B('status', kind=kind, until=until, **k)
def no_damage(**k): return B('no_damage', **k)
def equip(**k): return B('equip', **k)
def grant(key, **k): return B('grant', key=key, **k)
def negate_chain(**k): return B('negate_chain', **k)
def when_any(*ws): return B('when_any', of=tuple(ws))


# ── [지속] 적용 (status.py) ──
def forbid(key, who='opp', **k):
    """플레이어 규칙 「…할 수 없다 · 반드시 …해야 한다」 — 엔진 규칙 키(no_trigger_spell · no_defense · must_attack · no_deck_to_hand …)"""
    return B('forbid', key=key, who=who, **k)
def oath(group): return B('oath', group=group)
def floating(w, steps): return B('floating', when=w, steps=tuple(steps))
def replace(steps, label=''): return B('replace', steps=tuple(steps), label=label)
def equip_card(**k): return B('equip_card', **k)
def place(scope, **k): return B('place', scope=scope, **k)
def no_attack(): return B('no_attack')
def look(as_, n, zone='upper'): return B('look', n=n, zone=zone, **{'as': as_})
def to_bottom(ref, zone='upper'): return B('to_bottom', ref=ref, zone=zone)
def self_rule(key): return B('self_rule', key=key)
def stat_mod(to, amt, per=None, stat='atk'): return B('stat_mod', to=to, amt=amt, per=per, stat=stat)
def end_process(steps, whose='both'): return B('end_process', steps=tuple(steps), whose=whose)
def host_leave(steps): return B('host_leave', steps=tuple(steps))
def player_rule(key, who='own'): return B('player_rule', key=key, who=who)
def rule_immune(to, frm='opp'): return B('rule_immune', to=to, **{'from': frm})
def alt_normal(scope, n): return B('alt_normal', scope=scope, n=n)
def exclusive(*nums): return B('exclusive', nums=nums)
def mill(n, who='self', **k): return B('mill', n=n, who=who, **k)
def control(**k): return B('control', **k)
def effect_only(): return B('effect_only')
def grave_redirect(cont=False): return B('grave_redirect', cont=cont)
def card_flag(key, lasting=False, value=True): return B('card_flag', key=key, lasting=lasting, value=value)
def field_limit(*groups, n=1): return B('field_limit', groups=groups, n=n)
def ev_card(**f): return B('cond_ev_card', filter=S(**f))

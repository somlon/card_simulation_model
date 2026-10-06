"""뉴네오유희왕 룰 엔진 코어 (v0.1 시제품)
규칙 근거: 「뉴 네오 유희왕 — 규칙 명세서 (LLM 적용본)」 2026-09-29 (정본 + 사용자 재정). 주석의 §번호는 이 문서의 절.
「사용자 재정 2026-09-30」은 명세서 이후 사용자가 확정한 항목. 【가정】 처리는 ASSUME 주석으로 표시.
"""
import random, itertools
from dataclasses import dataclass, field

MZ = 5; SZ = 5
START_HP = 5000
# 라운드는 규칙의 종료 조건(HP 0 · 덱아웃 · 특수승리, §11-1)으로만 끝난다. 턴 상한 · HP 판정은 없다 (사용자 재정 2026-09-30).
# 아래 값은 무한 진행을 막는 안전장치일 뿐 승패를 판정하지 않는다 — 넘으면 오류(StalledGame)로 중단한다.
SAFETY_TURNS = 1000


class StalledGame(RuntimeError):
    """규칙상 종료 조건이 SAFETY_TURNS 턴 안에 충족되지 않은 라운드 (판정 없음)"""


class GameOver(Exception):
    def __init__(self, winner, reason):
        self.winner, self.reason = winner, reason


# ─────────────────────────── 카드 인스턴스 ───────────────────────────
_uid = itertools.count(1)

class Card:
    def __init__(self, d, owner):
        self.uid = next(_uid); self.d = d; self.name = d['name']; self.owner = owner
        self.controller = owner; self.zone = None
        self.faceup = True; self.pos = 'atk'
        self.counters = {}; self.equip_to = None; self.equips = []
        self.summon_turn = -1; self.set_turn = -1; self.pos_turn = -1
        self.attacks_made = 0; self.extra_attacks = 0
        self.mods = []            # (stat, value, expires: 'turn'|None)
        self.negated = False      # 턴 종료 시까지 무효
        self.effects = []         # 카드 정의 모듈이 채움
        self.rules = {}
        self.flags = {}

    # 기본 속성
    @property
    def type(self): return self.d['type']
    @property
    def level(self): return self.d.get('level', 0)
    def is_monster(self): return self.type == '몬스터' and not self.flags.get('as_spell')
    def is_spell_like(self): return self.type in ('마법', '필드') or self.flags.get('as_spell')
    def deck_kind(self): return self.d['deck'] if self.d['deck'] in ('메인', '상급') else '메인'
    def has(self, s): return s in self.name
    def base_atk(self): return int(self.d.get('atk') or 0)
    def base_def(self): return int(self.d.get('def') or 0)
    def __repr__(self): return f'「{self.name}」'


# ─────────────────────────── 효과 정의 ───────────────────────────
@dataclass
class Effect:
    num: int
    kind: str                 # ignition | quick | trigger | resp | summon | lastwill | battle | cont
    zones: tuple = ('field',) # 발동 가능 영역: hand / field / grave / skill
    cond: object = None       # (g, c, p, ev) -> bool   ev: 이벤트 또는 chain(resp)
    cost: object = None       # (g, c, p, link) -> bool  코스트 지불 + 대상 선택
    res: object = None        # (g, c, p, link)
    score: object = None      # (g, c, p, ev) -> float  AI 평가 (≤0 이면 안 씀)
    opt: int = 1              # 효과 번호당 1턴 사용 횟수 (None = 무제한)
    mandatory: bool = False
    threat: int = 500         # 상대 AI가 무효화를 고려할 위협도
    label: str = ''
    spell_act: bool = False   # 마법 카드 자체의 발동(패→필드)


@dataclass
class Link:
    card: Card
    eff: Effect
    player: int
    ctx: dict = field(default_factory=dict)
    negated: bool = False
    replaced: object = None   # 노린재 등 처리 치환


# ─────────────────────────── 플레이어 ───────────────────────────
class Player:
    def __init__(self, idx, name, skill_def, ai):
        self.idx = idx; self.name = name; self.hp = START_HP
        self.main = []; self.upper = []; self.hand = []; self.grave = []; self.banish = []
        self.m = [None] * MZ; self.s = [None] * SZ; self.skill = None
        self.skill_def = skill_def; self.ai = ai
        self.normal_summons = 1; self.oath = -1       # 맹세 제약 만료 턴
        self.opt = {}                                  # (name, num) -> 사용 횟수 (이번 턴)


# ─────────────────────────── 게임 ───────────────────────────
class Game:
    def __init__(self, decks, ais, first, rng, log, card_impl):
        self.rng = rng; self.log = log; self.impl = card_impl
        self.p = [Player(i, decks[i]['이름'], decks[i]['스킬'], ais[i]) for i in range(2)]
        self.shared = None; self.shared_owner = None
        self.fieldz = None
        self.turn = 0; self.turn_player = first; self.first = first; self.phase = '준비'
        self.chain = []; self.events = []; self.floating = []; self.src = None; self.no_attack = {}; self.no_damage = {}
        self.resolving = False
        self.locked = False       # 종료 단계 a 이후: 양쪽 모두 효과를 발동할 수 없다 (§5-5)
        self.decks = decks

    # ── 로그 ──
    def L(self, msg, kind='act'):
        self.log.append({'t': self.turn, 'ph': self.phase, 'tp': self.turn_player, 'k': kind, 'm': msg})

    def pname(self, p): return self.p[p].name

    # ── 조회 ──
    def opp(self, p): return 1 - p
    def monsters(self, p, faceup_only=False):
        out = [c for c in self.p[p].m if c]
        if self.shared and self.shared.controller == p: out.append(self.shared)
        return [c for c in out if c.faceup or not faceup_only]
    def spells(self, p):
        out = [c for c in self.p[p].s if c]
        if self.fieldz and self.fieldz.controller == p: out.append(self.fieldz)
        return out
    def field_cards(self, p): return self.monsters(p) + self.spells(p)
    def all_field(self): return self.field_cards(0) + self.field_cards(1)
    def on_field(self, c): return c.zone in ('m', 's', 'shared', 'fieldz')
    def exists(self, p_or_none, pred):
        pool = self.all_field() if p_or_none is None else self.field_cards(p_or_none)
        return any(pred(c) for c in pool)
    def exists_monster(self, pred, p=None):
        pool = (self.monsters(0) + self.monsters(1)) if p is None else self.monsters(p)
        return any(c.faceup and pred(c) for c in pool)

    def atk(self, c):
        v = c.base_atk() + sum(x for s, x, _ in c.mods if s == 'atk')
        for src in self.continuous_sources():
            f = getattr(src, 'atk_mod', None)
            if f: v += f(self, src, c)
        if c.flags.get('atk_set') is not None: v = c.flags['atk_set']
        return max(0, v)
    def df(self, c):
        return max(0, c.base_def() + sum(x for s, x, _ in c.mods if s == 'def'))
    def immune(self, c, by):
        """c가 플레이어 by의 효과를 받지 않는가"""
        if by is None or by == c.controller: return False
        if c.flags.get('immune_opp_until', -1) >= self.turn: return True
        if c.flags.get('immune_opp_perm') and self.on_field(c): return True
        if c.flags.get('immune_all_until', -1) >= self.turn: return True
        return self.rule('immune', c, by)

    def blocked(self, c, cause):
        if not cause or cause[0] != 'effect' or cause[1] is None or not self.on_field(c): return False
        if self.immune(c, cause[1].controller):
            self.L(f'{c}은(는) 상대의 효과를 받지 않음', 'sys'); return True
        return False

    def is_neg(self, c): return c.negated or any(e.flags.get('negates_host') for e in c.equips)
    def continuous_sources(self):
        srcs = [c for c in self.all_field() if c.faceup and not self.is_neg(c) and not c.flags.get('as_spell')]
        srcs += [c for c in self.all_field() if c.flags.get('as_spell') and c.faceup]
        srcs += [self.p[i].skill for i in (0, 1) if self.p[i].skill and not self.p[i].skill.negated]
        return srcs
    def rule(self, key, *a):
        """[지속] 규칙 질의: 등록된 hook 중 하나라도 True면 True"""
        for src in self.continuous_sources():
            f = getattr(src, 'rules', {}).get(key)
            if f and f(self, src, *a): return True
        return False

    # ── 존 이동 ──
    def _remove(self, c):
        pl = self.p[c.controller] if c.zone in ('m', 's') else self.p[c.owner]
        z = c.zone
        if z == 'm': pl.m[pl.m.index(c)] = None
        elif z == 's': pl.s[pl.s.index(c)] = None
        elif z == 'shared': self.shared = None   # 마커는 공유 존이 비어도 남는다 (사용자 재정 2026-09-30)
        elif z == 'fieldz': self.fieldz = None
        elif z in ('hand', 'grave', 'banish', 'main', 'upper'):
            for pl_ in (self.p[c.owner], self.p[1 - c.owner]):   # 상대 패에 들어간 카드(월영암수 등)도 찾는다
                lst = getattr(pl_, z)
                if c in lst: lst.remove(c); break
        elif z == 'skill': pass
        was_field = z in ('m', 's', 'shared', 'fieldz')
        if was_field:
            c.counters = {}; c.mods = []; c.negated = False; c.flags.pop('atk_set', None)
            c.attacks_made = 0; c.extra_attacks = 0
            if c.equip_to:
                if c in c.equip_to.equips: c.equip_to.equips.remove(c)
                self.on_equip_leave(c)
                c.equip_to = None
            for e in list(c.equips):
                e.equip_to = None
                h = getattr(e, 'on_host_leave', None)
                if h: h(self, e, c)
                if self.on_field(e):
                    self.L(f'장착 대상 {c} 이탈 → {e} 묘지로', 'sys')
                    self.send_grave(e, cause=('rule', None))
            c.equips = []
            c.flags.pop('as_spell', None)
        c.zone = None
        return was_field

    def on_equip_leave(self, eq):
        f = getattr(eq, 'on_unequip', None)
        if f: f(self, eq)

    def free_m(self, p): return [i for i in range(MZ) if self.p[p].m[i] is None]
    def free_s(self, p): return [i for i in range(SZ) if self.p[p].s[i] is None]

    def place_monster(self, c, p, pos='atk', faceup=True, allow_shared=True):
        """자신의 몬스터 존 또는 공유 존에 놓는다. 공유 존이 비어 있으면 몬스터 존이 차 있지 않아도 고를 수 있다 (§10-2)"""
        fr = self.free_m(p)
        to_shared = allow_shared and self.shared is None and (not fr or self.p[p].ai.use_shared(self, p, c, full=False))
        if not fr and not to_shared: return False
        c.controller = p; c.pos = pos; c.faceup = faceup
        if not to_shared:
            self.p[p].m[fr[0]] = c; c.zone = 'm'; return True
        # 공유 존 마커 (사용자 재정 2026-09-30): 라운드에서 처음 놓으면 놓은 플레이어의 마커를 올린다(뒤집힘 아님).
        # 그 뒤에는 공유 존이 비어도 마커가 남고, 치워진 공유 존에 상대가 자신의 카드를 놓으면 뒤집힌다 (§10-3 a)
        self.shared = c; c.zone = 'shared'
        old = self.shared_owner; self.shared_owner = p
        if old is not None and old != p: self.flip_marker(old)
        return True

    def flip_marker(self, old):
        """공유 존 마커 뒤집힘: 기존 주인에게 정본 0-5의 1~3을 모두 적용 (§10-4). 규칙 처리이므로 효과 내성에 막히지 않는다"""
        self.L(f'공유 존 마커 뒤집힘 — {self.pname(old)}에게 페널티', 'sys')
        pl = self.p[old]
        if pl.hand:
            x = self.rng.choice(pl.hand); self.to_deck(x, ('rule', None)); self.L(f'  패 {x} 무작위로 덱으로', 'sys')
        tgt = self.p[1 - old].ai.pick_target(self, 1 - old, self.field_cards(old), 'bounce')   # 기존 주인의 필드 카드 중에서
        if tgt: self.L(f'  {self.pname(1-old)}가 {tgt} 선택 → 덱으로', 'sys'); self.to_deck(tgt, ('rule', None))
        self.damage(old, 1500, '공유 존 마커')

    def place_spell(self, c, p, faceup=True):
        fr = self.free_s(p)
        if not fr: return False
        self.p[p].s[fr[0]] = c; c.zone = 's'; c.controller = p; c.faceup = faceup
        if not faceup: c.set_turn = self.turn
        return True

    def place_field(self, c, p):
        if self.fieldz:
            old = self.fieldz; self.L(f'필드 존의 {old} 묘지로', 'sys'); self.send_grave(old, ('rule', None))
        self.fieldz = c; c.zone = 'fieldz'; c.controller = p; c.faceup = True

    # 이동 동작 (이벤트 발생)
    def send_grave(self, c, cause=None, destroyed=False, from_battle=False):
        cause = cause or ('effect', self.src)
        if self.blocked(c, cause): return
        prev = c.zone; ctrl = c.controller
        redirect = getattr(c, 'grave_redirect', None)
        was_field = self._remove(c)
        if redirect and redirect(self, c):
            self.L(f'{c} 묘지 대신 덱으로 (카드 효과)', 'sys'); self._to_deck_raw(c)
            if was_field: self.emit('leave_field', card=c, prev=prev, ctrl=ctrl, cause=cause, dest='deck')
            return
        c.controller = c.owner; c.zone = 'grave'; c.faceup = True; self.p[c.owner].grave.append(c)
        self.emit('to_grave', card=c, prev=prev, ctrl=ctrl, cause=cause, destroyed=destroyed, battle=from_battle)
        if was_field: self.emit('leave_field', card=c, prev=prev, ctrl=ctrl, cause=cause, dest='grave')

    def destroy(self, c, cause=None, battle=False):
        cause = cause or ('effect', self.src)
        if not battle and self.blocked(c, cause): return False
        if self.rule('indestructible', c, battle): 
            self.L(f'{c} 파괴되지 않음', 'sys'); return False
        self.L(f'{c} 파괴' + (' (전투)' if battle else ''))
        self.send_grave(c, cause, destroyed=True, from_battle=battle)
        self.emit('destroyed', card=c, cause=cause, battle=battle)
        return True

    def _to_deck_raw(self, c):
        c.controller = c.owner; c.faceup = True
        lst = self.p[c.owner].upper if c.deck_kind() == '상급' else self.p[c.owner].main
        lst.insert(self.rng.randrange(len(lst) + 1), c); c.zone = 'upper' if lst is self.p[c.owner].upper else 'main'

    def to_deck(self, c, cause=None):
        cause = cause or ('effect', self.src)
        if self.blocked(c, cause): return
        prev = c.zone; ctrl = c.controller
        was_field = self._remove(c); self._to_deck_raw(c)
        if was_field: self.emit('leave_field', card=c, prev=prev, ctrl=ctrl, cause=cause, dest='deck')

    def to_hand(self, c, cause=None, p=None):
        cause = cause or ('effect', self.src)
        if self.blocked(c, cause): return
        prev = c.zone; ctrl = c.controller
        was_field = self._remove(c)
        owner = c.owner if p is None else p
        c.controller = owner; c.zone = 'hand'; c.faceup = True; self.p[owner].hand.append(c)
        if prev in ('main', 'upper', 'grave'):
            self.emit('added_to_hand', card=c, prev=prev, player=owner)
        if was_field: self.emit('leave_field', card=c, prev=prev, ctrl=ctrl, cause=cause, dest='hand')

    def banish(self, c, cause=None):
        cause = cause or ('effect', self.src)
        if self.blocked(c, cause): return
        prev = c.zone; ctrl = c.controller
        was_field = self._remove(c)
        c.controller = c.owner; c.zone = 'banish'; c.faceup = True; self.p[c.owner].banish.append(c)   # 제외 존은 앞면 공개 (§10-7)
        if was_field: self.emit('leave_field', card=c, prev=prev, ctrl=ctrl, cause=cause, dest='banish')

    def tribute(self, c, cause=None):
        if c.flags.get('no_release_until', -1) >= self.turn: self.L(f'{c}은(는) 릴리스할 수 없음', 'sys'); return
        cause = cause or ('effect', self.src)
        if self.blocked(c, cause): return
        self.L(f'{c} 릴리스'); self.send_grave(c, cause)

    def change_control(self, c, p):
        if c.controller == p: return True
        if c.zone == 'shared':
            c.controller = p
            if self.shared_owner != p:
                old = self.shared_owner; self.shared_owner = p
                if old is not None: self.flip_marker(old)
            return True
        fr = self.free_m(p)
        if not fr: return False
        self.p[c.controller].m[self.p[c.controller].m.index(c)] = None
        self.p[p].m[fr[0]] = c; c.controller = p
        return True

    # ── 소환 ──
    def can_special(self, c, p):
        """c를 지금 특수소환할 수 있는가. 규칙상 불가능한 후보는 처리 전에 걸러낸다(처리 중 실패 방지):
        소환 금지 [지속] · 같은 이름 규칙(정본 3-6 f: 자신의 효과로 같은 이름의 카드를 덱에서 특수소환할 수 없음) · 놓을 자리"""
        if self.rule('no_special', c, p): return False
        if self.same_name_blocked(c): return False
        return self.can_place(c, p)

    def same_name_blocked(self, c):
        """정본 3-6 f: 지금 처리(또는 발동 판정) 중인 효과의 주체와 같은 이름의 카드를 덱에서 특수소환할 수 없다"""
        return c.zone in ('main', 'upper') and self.src is not None and self.src.name == c.name and not self.same_name_ok()

    def can_place(self, c, p):
        """놓을 자리가 있는가. 공유 존은 언제든 고를 수 있으나(§10-2), 몬스터 존이 가득 찼을 때 공유 존을 쓸지는 AI가 판단"""
        if self.free_m(p): return True
        return self.shared is None and self.p[p].ai.use_shared(self, p, c, full=True)

    def def_allowed(self, p):
        """p의 몬스터가 수비 표시로 존재할 수 있는가 (격투가의 투기장 1번 등 [지속] 규칙)"""
        return not self.rule('no_defense', p)

    def release_cands(self, p):
        """일반소환의 제물로 릴리스할 수 있는 카드: 자신 필드의 몬스터 카드만 (사용자 재정 2026-09-30).
        장착 마법 취급된 몬스터(as_spell)는 몬스터가 아니므로 제외"""
        return [x for x in self.monsters(p) if x.is_monster() and x.flags.get('no_release_until', -1) < self.turn]

    def can_change_pos(self, c, p):
        """표시 형식 변경 (§8-1): 자신의 앞면 몬스터 · 몬스터당 1턴 1번 · 소환된 턴 불가.
        시점은 규칙서에 없어 자신 턴 · 체인이 없을 때로 둔다"""
        return (self.turn_player == p and not self.chain and c.controller == p and c.is_monster() and self.on_field(c)
                and c.faceup and c.summon_turn != self.turn and c.pos_turn != self.turn and not c.flags.get('no_pos_change')
                and (c.pos == 'def' or self.def_allowed(p)))

    def change_position(self, c, p):
        c.pos = 'def' if c.pos == 'atk' else 'atk'; c.pos_turn = self.turn
        self.L(f'{self.pname(p)} {c} 표시 형식 변경 → {"공격" if c.pos == "atk" else "수비"} 표시')
        self.emit('position', card=c, player=p)

    def summon_pos(self, c, p, how):
        """소환 표시 형식 (§5-2): 카드 텍스트가 정하지 않은 소환은 소환하는 플레이어가 앞면 공격 / 앞면 수비 표시를 고른다.
        수비 표시로 존재할 수 없으면(격투가의 투기장 1번 등) 공격 표시. 텍스트가 표시 형식을 정한 소환은 호출하는 쪽이 pos를 넘긴다"""
        if not self.def_allowed(p): return 'atk'
        f = getattr(self.p[p].ai, 'choose_summon_pos', None)
        return f(self, p, c, how) if f else 'atk'

    def special_summon(self, c, p, pos=None, by=None):
        """pos=None: 표시 형식을 AI가 고른다(summon_pos). 텍스트가 「공격 표시로 · 수비 표시로」를 정한 효과는 pos를 넘긴다"""
        if not self.can_special(c, p): return False
        if self.same_name_blocked(c):   # can_special이 걸러내므로 여기 오면 후보 선택 쪽 누락 — 안전장치
            self.L(f'{c}: 자신의 효과로 같은 이름의 카드를 덱에서 특수소환할 수 없음 (정본 3-6 f)', 'sys'); return False
        if pos is None: pos = self.summon_pos(c, p, 'special')
        if pos == 'def' and not self.def_allowed(p): pos = 'atk'
        prev = c.zone
        self._remove(c)
        self.place_monster(c, p, pos)
        c.summon_turn = self.turn
        self.L(f'{self.pname(p)} {c} 특수소환 ({"공격" if pos=="atk" else "수비"}, {prev}→{"공유 존" if c.zone=="shared" else "몬스터 존"})')
        self.emit('summon', card=c, player=p, how='special', prev=prev, by=by)
        return True

    def normal_summon(self, c, p, tributes=(), pos=None):
        """일반소환 (§5-2): 패에서 앞면 공격 표시 또는 앞면 수비 표시. 레벨에 따른 제물은 호출하는 쪽이 고른다.
        pos=None: 제물을 바친 뒤 표시 형식을 AI가 고른다(summon_pos)"""
        for t in tributes: self.tribute(t, ('summon', None))
        if pos is None: pos = self.summon_pos(c, p, 'normal')
        if pos == 'def' and not self.def_allowed(p): pos = 'atk'
        self._remove(c); self.place_monster(c, p, pos); c.summon_turn = self.turn
        self.p[p].normal_summons -= 1
        self.L(f'{self.pname(p)} {c} 일반소환' + (' (수비 표시)' if c.pos == 'def' else '')
               + (f' (제물 {", ".join(map(str, tributes))})' if tributes else ''))
        self.emit('summon', card=c, player=p, how='normal', prev='hand', by=None)

    @staticmethod
    def tributes_needed(level):
        return 0 if level <= 4 else 1 if level <= 7 else 2 if level <= 9 else 3

    # ── 카운터 ──
    def add_counter(self, c, name, n=1):
        if not self.on_field(c) or not c.faceup: return False
        c.counters[name] = c.counters.get(name, 0) + n
        self.L(f'{c}에 {name} 카운터 {n}개 → {c.counters[name]}개'); self.emit('counter', card=c, name=name, delta=n)
        self.state_check(); return True
    def remove_counter(self, c, name, n=1):
        k = min(n, c.counters.get(name, 0))
        if k <= 0: return 0
        c.counters[name] -= k
        if c.counters[name] == 0: del c.counters[name]
        self.L(f'{c}의 {name} 카운터 {k}개 제거'); self.emit('counter', card=c, name=name, delta=-k)
        self.state_check(); return k

    # ── HP ──
    def damage(self, p, amt, src=''):
        if amt <= 0: return
        if getattr(self, 'no_damage', {}).get(1 - p, -1) >= self.turn and src != '공유 존 마커' and not src.startswith('자해'):
            self.L(f'{self.pname(1-p)}은(는) 이 턴 대미지를 줄 수 없음 — {amt} 무효', 'sys'); return
        self.p[p].hp -= amt
        self.L(f'{self.pname(p)} {amt} 대미지 ({src}) → HP {self.p[p].hp}')
        self.emit('damage', player=p, amount=amt)
        if self.p[p].hp <= 0: raise GameOver(1 - p, f'{self.pname(p)} HP 0')
    def heal(self, p, amt):
        self.p[p].hp += amt; self.L(f'{self.pname(p)} HP {amt} 회복 → {self.p[p].hp}')

    # ── 드로우 / 서치 ──
    def draw(self, p, n=1, deck=None):
        pl = self.p[p]
        for _ in range(n):
            if deck == 'main': src = pl.main
            elif deck == 'upper': src = pl.upper
            else:
                if not pl.main and not pl.upper: raise GameOver(1 - p, f'{pl.name} 덱아웃')
                choice = pl.ai.choose_draw_deck(self, p) if pl.main and pl.upper else ('main' if pl.main else 'upper')
                src = pl.main if choice == 'main' else pl.upper
            if not src: raise GameOver(1 - p, f'{pl.name} 덱아웃 (지정 덱 없음)')
            c = src.pop(); c.zone = 'hand'; pl.hand.append(c)
            self.L(f'{pl.name} 드로우 ({"상급" if src is pl.upper else "메인"}) {c}', 'draw')
            self.emit('draw', player=p, card=c)

    def mill(self, p, n, deck=None, why='', fallback=False, chooser=None):
        """p의 덱 위에서부터 n장 제외 (제외 존은 앞면 공개, §10-7). 반환: 실제 제외 매수
        deck: 'main' / 'upper' — 텍스트가 지정한 그 덱만 (§6-7)
              None — 「덱의 위에서부터」처럼 덱을 지정하지 않은 효과: chooser가 메인 · 상급 중 한쪽을 고른다 (§6-7, §15-1)
        fallback: 텍스트에 「제외할 카드가 부족할 경우, 부족한 매수만큼을 … 대신 제외한다」가 있을 때만 다른 덱에서 채운다"""
        pl = self.p[p]
        if deck is None:
            ch = p if chooser is None else chooser
            deck = self.p[ch].ai.choose_mill_deck(self, ch, p, n) if pl.main and pl.upper else ('main' if pl.main else 'upper')
        order = (pl.main, pl.upper) if deck == 'main' else (pl.upper, pl.main)
        if not fallback: order = order[:1]
        k = 0
        for lst in order:
            while k < n and lst:
                c = lst.pop(); c.zone = 'banish'; c.controller = c.owner; c.faceup = True; pl.banish.append(c); k += 1
        if n: self.L(f'{pl.name} 덱 위에서 {k}장 제외{(" (" + why + ")") if why else ""} — 남은 덱 {len(pl.main)}/{len(pl.upper)}')
        if k: self.emit('milled', player=p, n=k)
        return k

    def deck_cards(self, p, which=('main', 'upper')):
        out = []
        for w in which: out += getattr(self.p[p], w)
        return out

    def search_cands(self, p, pred, which=('main', 'upper'), source=None):
        """서치 후보: 덱에서 pred를 만족하고, 서치 효과의 주체 카드와 이름이 다른 카드 (사용자 재정)"""
        src = source or self.src
        ok = self.same_name_ok() and source is None
        return [c for c in self.deck_cards(p, which) if pred(c) and (ok or not (src is not None and c.name == src.name))]

    def can_search(self, p, pred, which=('main', 'upper'), source=None):
        """발동 조건용: 지금 서치할 수 있는 카드가 있는가 (발동 판정 중에는 src = 발동하려는 카드)"""
        return bool(self.search_cands(p, pred, which, source))

    def search(self, p, pred, which=('main', 'upper'), why='서치', source=None):
        """덱에서 패에 넣기. 서치 효과의 주체 카드와 같은 이름의 카드는 가져올 수 없다 (사용자 재정)"""
        cands = self.search_cands(p, pred, which, source)
        if not cands: self.L(f'{why}: 대상 없음', 'sys'); return None
        c = self.p[p].ai.pick_search(self, p, cands, why)
        self.L(f'{self.pname(p)} {why}: {c} 패에 넣음')
        self.to_hand(c); self.shuffle(p); return c

    def same_name_ok(self):
        """텍스트에 같은 이름 카드를 가져오거나 특수소환한다는 문구 · 예외 조항이 있는 효과 (사용자 재정)"""
        e = getattr(self, 'src_eff', None)
        return bool(e is not None and getattr(e, 'same_name_ok', False))

    def salvage(self, p, cands, why='회수', source=None):
        """묘지 · 제외 존에서 패로. 효과 주체와 같은 이름의 카드는 가져올 수 없다 (사용자 재정)"""
        src = source or self.src
        if not (self.same_name_ok() and source is None):
            cands = [c for c in cands if not (src is not None and c.name == src.name)]
        if not cands: self.L(f'{why}: 대상 없음', 'sys'); return None
        c = max(cands, key=lambda x: self.p[p].ai.card_pri(self, p, x))
        self.to_hand(c); self.L(f'{self.pname(p)} {why}: {c} 패에 넣음'); return c

    def shuffle(self, p):
        self.rng.shuffle(self.p[p].main); self.rng.shuffle(self.p[p].upper)

    # ── 이벤트 ──
    def emit(self, kind, **kw):
        ev = dict(kind=kind, **kw); ev['turn'] = self.turn
        self.events.append(ev)
        for fl in list(self.floating):
            fl(self, ev)
        for src in self.continuous_sources():
            h = getattr(src, 'on_event', None)
            if h: h(self, src, ev)

    # ── 1턴 1회 ──
    def opt_ok(self, p, c, e):
        if e.opt is None: return True
        return self.p[p].opt.get((c.name, e.num), 0) < e.opt

    # ── 발동 가능 판정 ──
    def zone_ok(self, c, e, p):
        z = c.zone
        if z == 'hand' and 'hand' not in e.zones: return False
        if z in ('m', 's', 'shared', 'fieldz'):
            if 'field' not in e.zones or c.controller != p: return False
            if not c.faceup and not (c.is_spell_like() and e.spell_act): return False
            if self.is_neg(c): return False
        if z == 'grave' and 'grave' not in e.zones: return False
        if z == 'skill' and c.controller != p: return False
        if z == 'skill' and c.negated: return False
        if z in ('main', 'upper', 'banish'): return False
        if z == 'hand' and c.owner != p: return False
        return True

    def oath_ok(self, p, c):
        return self.p[p].oath < self.turn or c.has('번성충')

    def can_act(self, p, c, e, ev=None):
        if not self.zone_ok(c, e, p): return False
        if not self.opt_ok(p, c, e): return False
        if not self.oath_ok(p, c): return False
        if e.cond and not e.cond(self, c, p, ev): return False
        return True

    def spell_speed_ok(self, c, p, e):
        """마법 카드 발동 시점 (§8-2):
        일반 · 지속 · 필드 — 자신 턴, 체인이 없을 때 (단계 제한 없음, 사용자 재정 2026-09-30), 패 또는 세트에서
        신속 — 자신 턴: 패에서 발동 가능 / 상대 턴: 세트한 카드만 (「패에서도 발동할 수 있다」 카드는 예외)
               세트한 그 턴에는 발동 불가 (「이 턴에도 발동할 수 있다」로 세트된 카드는 예외) — 사용자 재정 2026-09-23
        트리거 — 패 또는 필드에서 (정본 1-2)"""
        if not e.spell_act: return True
        sub = c.d.get('subtype', '')
        own = self.turn_player == p
        if c.type == '필드' or sub in ('일반', '지속'):
            return own and not self.chain and (c.zone == 'hand' or (c.zone == 's' and not c.faceup))
        if sub == '신속':
            # 사용자 재정: 자신 턴에는 패에서 발동 가능 / 상대 턴에는 세트한 카드만 / 세트한 그 턴에는 발동 불가
            if c.zone == 'hand': return own or getattr(e, 'hand_ok', False)
            return c.zone == 's' and not c.faceup and (c.set_turn < self.turn or c.flags.get('act_this_turn') == self.turn)
        if sub == '트리거':
            return c.zone == 'hand' or (c.zone == 's' and not c.faceup)
        return True

    # ═════════════════════════ 발동 · 체인 ═════════════════════════
    def legal(self, p, c, e, ev=None):
        if c.type == '마법' and c.d.get('subtype') == '트리거' and e.spell_act and self.rule('no_trigger_spell', p): return False
        # 발동 조건은 「그 카드가 효과의 주체」인 상태로 판정한다 — 처리 때와 같은 규칙(같은 이름 서치 · 특수소환 금지 등)으로
        # 후보가 있는지 보아, 규칙상 처리할 수 없는 발동을 미리 막는다
        prev = (self.src, getattr(self, 'src_eff', None)); self.src, self.src_eff = c, e
        try:
            if not self.can_act(p, c, e, ev): return False
        finally:
            self.src, self.src_eff = prev
        if not self.spell_speed_ok(c, p, e): return False
        if e.spell_act and c.zone == 'hand':
            if c.type == '필드': pass
            elif not self.free_s(p): return False
        return True

    def activate(self, p, c, e, ev=None):
        link = Link(c, e, p, {'ev': ev, 'from_zone': c.zone})
        placed_from = c.zone
        if e.spell_act:
            if c.type == '필드':
                if c.zone == 'hand': self._remove(c); self.place_field(c, p)
            elif c.zone == 'hand':
                self._remove(c); self.place_spell(c, p, True)
            else: c.faceup = True
        self.L(f'{self.pname(p)} {c} {e.num}번 효과 발동' + (f' [{e.label}]' if e.label else '') + f' — 체인 {len(self.chain)+1}')
        link.ctx['opt_keys'] = [(c.name, e.num)]   # 이 발동이 소모하는 1턴 1회 (카드명 × 효과 번호, §6-4). 코스트 처리에서 바꿀 수 있다
        if e.cost and e.cost(self, c, p, link) is False:
            self.L(f'{c} 발동 취소 (코스트/대상 불가)', 'sys')
            if e.spell_act and placed_from == 'hand' and self.on_field(c): self._remove(c); c.zone = 'hand'; self.p[p].hand.append(c)
            return None
        for k in link.ctx['opt_keys']: self.p[p].opt[k] = self.p[p].opt.get(k, 0) + 1
        self.chain.append(link)
        self.emit('activate', link=link, player=p)
        return link

    def options(self, p, kinds, ev=None):
        out = []
        pl = self.p[p]
        cards = list(pl.hand) + self.field_cards(p) + list(pl.grave) + ([pl.skill] if pl.skill else [])
        for c in cards:
            for e in c.effects:
                if e.kind in kinds and self.legal(p, c, e, ev): out.append((c, e))
        return out

    def priority(self, start):
        if self.locked: return   # 종료 단계 a 이후에는 발동 불가 (§5-5)
        passes = 0; cur = start; guard = 0
        while guard < 60:
            if self.chain and getattr(self.chain[-1].eff, 'no_resp', False): break
            guard += 1
            opts = self.options(cur, ('quick', 'resp'), ev=self.chain)
            pick = self.p[cur].ai.respond(self, cur, opts) if opts else None
            if pick:
                c, e = pick
                if self.activate(cur, c, e, ev=self.chain[-1] if self.chain else None):
                    passes = 0; cur = 1 - cur; continue
            passes += 1
            if passes >= 2: break
            cur = 1 - cur
        self.resolve_chain()

    def resolve_chain(self):
        while self.chain:
            link = self.chain.pop()
            c, e, p = link.card, link.eff, link.player
            if link.negated:
                self.L(f'체인 {len(self.chain)+1} {c} {e.num}번 — 무효', 'res')
            elif link.replaced:
                self.L(f'체인 {len(self.chain)+1} {c} {e.num}번 — 처리 치환', 'res'); link.replaced(self, link)
            else:
                self.L(f'체인 {len(self.chain)+1} {c} {e.num}번 처리', 'res')
                self.src = c; self.src_eff = e
                if e.res: e.res(self, c, p, link)
                self.src = None; self.src_eff = None
            if e.spell_act and self.on_field(c) and c.type == '마법' and c.d.get('subtype') in ('일반', '신속', '트리거') \
               and not c.flags.get('stay'):
                if c.flags.get('banish_on_resolve'): self.L(f'{c} 발동 후 제외', 'sys'); self.banish(c, ('rule', None))
                else: self.send_grave(c, ('rule', None))
            if link.negated and e.spell_act and self.on_field(c) and c.type != '마법':
                pass
        self.triggers()

    def negate(self, link, destroy=False, by=None):
        if getattr(link.eff, 'unnegatable', False) or link.card.flags.get('unnegatable'):
            self.L(f'{link.card}은(는) 무효화되지 않음', 'sys'); return
        link.negated = True
        for k in link.ctx.get('opt_keys', [(link.card.name, link.eff.num)]):   # 무효화된 발동은 사용 횟수를 소모하지 않는다 (§6-5)
            if self.p[link.player].opt.get(k): self.p[link.player].opt[k] -= 1
        self.L(f'{link.card} {link.eff.num}번 효과 무효' + (' 후 파괴' if destroy else ''))
        if destroy and self.on_field(link.card): self.destroy(link.card, ('effect', by))

    # ── 트리거 수집 ──
    def state_check(self):
        for src in self.continuous_sources():
            h = getattr(src, 'state_check', None)
            if h: h(self, src)

    def triggers(self, depth=0):
        self.state_check()
        if self.locked or depth > 12 or not self.events: self.events = []; return
        evs = self.events; self.events = []; self.cur_evs = evs
        tp = self.turn_player; built = False
        for p in (tp, 1 - tp):
            pl = self.p[p]
            cards = list(pl.hand) + self.field_cards(p) + list(pl.grave) + ([pl.skill] if pl.skill else []) + list(pl.banish)
            cands = []
            for c in cards:
                for e in c.effects:
                    if e.kind not in ('trigger', 'summon', 'lastwill', 'battle'): continue
                    for ev in evs:
                        if self.legal(p, c, e, ev):
                            cands.append((c, e, ev)); break
            if not cands: continue
            order = pl.ai.choose_triggers(self, p, cands)
            seen_x = set(); order2 = []
            for c, e, ev in order:   # 「동시에 발동할 수 없다」 효과 묶음은 하나만
                ex = c.flags.get('exclusive_nums')
                if ex and e.num in ex:
                    if c.uid in seen_x: continue
                    seen_x.add(c.uid)
                order2.append((c, e, ev))
            order = order2
            for c, e, ev in order:
                if self.legal(p, c, e, ev):
                    if self.activate(p, c, e, ev): built = True
        if built: self.priority(1 - tp)
        elif self.events: self.triggers(depth + 1)

    def after_action(self, actor):
        """행동(소환 등) 뒤: 트리거 → 없으면 상대에게 우선권"""
        if self.events:
            evs = list(self.events)
            self.triggers()
            if not self.chain: self.priority(1 - actor)
        else:
            self.priority(1 - actor)

    def act(self, p, c, e):
        if self.activate(p, c, e):
            self.priority(1 - p)

    # ═════════════════════════ 전투 ═════════════════════════
    def can_declare_attack(self, p):
        """p가 이번 턴 아직 공격 선언을 할 수 있는 상태인가: 자신 턴 · 선공 1턴째가 아님 (§5-3) · 공격 봉인 없음 · 전투 단계 이전"""
        return self.turn_player == p and self.turn > 1 and self.no_attack.get(p) != self.turn and self.phase in ('준비', '진행', '전투')

    def can_direct(self, c):
        opp = 1 - c.controller
        return not self.monsters(opp) or self.rule('direct_attack', c)

    def attack_targets(self, c):
        return [m for m in self.monsters(1 - c.controller) if m.faceup and not self.rule('no_battle_target', m)]   # 뒷면은 공격 대상 아님(정본 1-1)

    def attack(self, a, target):
        p = a.controller; o = 1 - p
        a.attacks_made += 1
        self.L(f'{self.pname(p)} {a}(ATK {self.atk(a)}) → ' + (f'{target}' if target else '직접공격'))
        self.emit('attack', card=a, target=target)
        self.after_action(p)
        if not self.on_field(a) or a.controller != p or not a.faceup: return
        if target is not None and (not self.on_field(target) or target.controller != o):
            self.L('공격 대상 소멸 — 공격 종료', 'sys'); return
        if target is None:
            self.damage(o, self.atk(a), f'{a.name} 직접공격')
            self.emit('direct_hit', card=a)
        else:
            # 전투 판정 (§5-3). battle_win = [전투] 발동 사건: 전투로 카드를 '파괴하는 데 성공'했을 때만 (§7)
            av = self.atk(a)
            if target.pos == 'atk':
                tv = self.atk(target)
                if av > tv:
                    dt = self.destroy(target, ('battle', a), battle=True); self.damage(o, av - tv, '전투')
                    if dt: self.emit('battle_win', card=a, target=target, player=p)
                elif av < tv:
                    da = self.destroy(a, ('battle', target), battle=True); self.damage(p, tv - av, '전투')   # [유희왕] 기준선
                    if da: self.emit('battle_win', card=target, target=a, player=o)
                else:
                    da = self.destroy(a, ('battle', target), battle=True); dt = self.destroy(target, ('battle', a), battle=True)
                    if dt: self.emit('battle_win', card=a, target=target, player=p)
                    if da: self.emit('battle_win', card=target, target=a, player=o)
            else:
                tv = self.df(target)
                if av > tv:   # 수비 표시를 넘어도 HP 피해 없음 (정본 3-3)
                    if self.destroy(target, ('battle', a), battle=True): self.emit('battle_win', card=a, target=target, player=p)
                elif av < tv: self.damage(p, tv - av, '전투(수비 반사)')   # [유희왕] 기준선: 공격 몬스터는 파괴되지 않음
        self.triggers()
        if self.chain: self.resolve_chain()

    # ═════════════════════════ 턴 ═════════════════════════
    def set_phase(self, ph):
        self.phase = ph
        self.emit('phase', phase=ph)
        self.triggers()
        if self.chain: self.resolve_chain()

    def open_window(self):
        self.priority(self.turn_player)

    def play_turn(self):
        self.turn += 1; self.locked = False
        tp = self.turn_player; pl = self.p[tp]
        for x in self.p: x.opt = {}
        pl.normal_summons = 1
        for c in self.monsters(0) + self.monsters(1): c.attacks_made = 0; c.extra_attacks = 0
        self.snaps.append(dict(turn=self.turn, tp=tp, hp=[x.hp for x in self.p],
            field=[len(self.field_cards(i)) for i in (0, 1)], mons=[len(self.monsters(i)) for i in (0, 1)],
            hand=[len(x.hand) for x in self.p], grave=[len(x.grave) for x in self.p],
            atk=[sum(self.atk(m) for m in self.monsters(i)) for i in (0, 1)], deck=[len(x.main) + len(x.upper) for x in self.p]))
        self.log.append({'t': self.turn, 'ph': '', 'tp': tp, 'k': 'snap', 'm': '', 'data': self.board()})
        self.L(f'━━ {self.turn}턴 — {pl.name} ━━ HP {self.p[0].name} {self.p[0].hp} / {self.p[1].name} {self.p[1].hp}', 'turn')
        self.set_phase('준비')
        if not (self.turn == 1):   # 선공 1턴째에만 드로우 생략 (§5-1)
            self.draw(tp, 1)
        self.triggers()
        self.set_phase('진행'); self.open_window()
        pl.ai.main_phase(self, tp, '진행')
        self.set_phase('전투'); self.open_window()
        if self.turn > 1 and not pl.flags_no_attack(self):   # 선공 1턴째에는 공격 선언 불가 (§5-3) — 전투 단계 자체는 진행한다
            pl.ai.battle_phase(self, tp)
        self.set_phase('정비'); self.open_window()
        pl.ai.main_phase(self, tp, '정비')
        # 종료 단계 (§5-5): a 「턴 종료 시」 효과 → b 패 7장 → c 「턴 종료 시까지」 해제 → d 턴 종료
        self.set_phase('종료')
        for c in self.continuous_sources():   # [지속] 종료 단계 처리: 필드의 카드와 스킬 존의 스킬 (스킬은 필드가 아니지만 [지속]이 적용된다)
            f = getattr(c, 'end_process', None)
            if f and (self.on_field(c) or c.zone == 'skill'): f(self, c)
        self.emit('end_phase', player=tp)
        self.triggers()
        if self.chain: self.resolve_chain()
        self.locked = True   # a가 끝나면 양쪽 모두 더 이상 효과를 발동할 수 없다
        # b. 패 7장 초과 버리기 — 버려진 카드의 [유언]은 발동하지 않는다 (§5-5 재정)
        for _ in range(30):
            if len(pl.hand) <= 7: break
            c = pl.ai.pick_discard(self, tp, pl.hand); self.L(f'패 상한 — {c} 버림'); self.send_grave(c, ('rule', None))
        self.events = []
        # c. 턴 종료 시까지 효과 해제
        for c in self.all_field() + [x.skill for x in self.p if x.skill]:
            c.mods = [m for m in c.mods if m[2] != 'turn']; c.negated = False
            c.flags.pop('atk_set', None)
        for fn in [f for f in self.floating if getattr(f, 'until', None) == self.turn]:
            self.floating.remove(fn)
        for c in [c for c in self.all_field() if c.flags.get('return_at_end') == self.turn]:
            c.flags.pop('return_at_end'); getattr(c, 'end_return')(self, c)
        for x in self.p:
            for c in list(x.banish):
                if c.flags.get('return_from_banish') == self.turn:
                    c.flags.pop('return_from_banish'); self.L(f'{c} 제외에서 복귀', 'sys')
                    x.banish.remove(c); c.zone = None; self.place_monster(c, c.owner)
        self.events = []   # b · c 처리 중 생긴 사건은 발동 기회 없이 소멸
        self.turn_player = 1 - tp

    def board(self):
        def fc(c):
            if c.is_monster(): return f'{c.name}({self.atk(c)}{"" if c.faceup else ", 뒷면"}{", " + ",".join(f"{k}{v}" for k, v in c.counters.items()) if c.counters else ""})'
            return c.name + ('' if c.faceup else '(세트)')
        return {'hp': [x.hp for x in self.p], 'hand': [len(x.hand) for x in self.p],
                'deck': [f'{len(x.main)}/{len(x.upper)}' for x in self.p], 'grave': [len(x.grave) for x in self.p],
                'mons': [[fc(c) for c in self.monsters(i)] for i in (0, 1)],
                'spells': [[fc(c) for c in self.p[i].s if c] for i in (0, 1)],
                'field': (self.fieldz.name, self.fieldz.controller) if self.fieldz else None}

    def evaluate(self, p):
        """형세 판정 (롤아웃 절단용) → 0~1. evaluator가 지정되면(RF 형세 모델) 그것을, 아니면 수동 공식"""
        ev = getattr(self, 'evaluator', None)
        if ev is not None: return ev(self, p)
        import math
        o = 1 - p
        s = (self.p[p].hp - self.p[o].hp) / 1000 + 0.6 * (len(self.field_cards(p)) - len(self.field_cards(o))) \
            + 0.3 * (len(self.p[p].hand) - len(self.p[o].hand)) \
            + (sum(self.atk(m) for m in self.monsters(p)) - sum(self.atk(m) for m in self.monsters(o))) / 2000
        return 1 / (1 + math.exp(-s))

    # ═════════════════════════ 라운드 ═════════════════════════
    def setup(self):
        for i in (0, 1):
            pl = self.p[i]; dk = self.decks[i]
            for sec, lst in (('메인', pl.main), ('상급', pl.upper)):
                for n, name in dk[sec]:
                    for _ in range(n):
                        c = Card(self.impl.pool[name], i); c.zone = 'main' if sec == '메인' else 'upper'
                        self.impl.attach(c); lst.append(c)
            sk = Card(self.impl.pool[dk['스킬']], i); sk.zone = 'skill'; self.impl.attach(sk); pl.skill = sk
            self.shuffle(i)
        self.L(f'스킬 배치 — {self.p[0].skill} / {self.p[1].skill}', 'sys')
        self.emit('game_start'); self.triggers()
        self.L(f'선공: {self.p[self.first].name}', 'sys')
        for i in (0, 1):
            pl = self.p[i]
            n_hand = 5 + (2 if self.rule('hand7', i) else 0)
            k = pl.ai.choose_split(self, i, n_hand)
            k = max(n_hand - len(pl.upper), min(k, n_hand, len(pl.main)))
            for _ in range(k): c = pl.main.pop(); c.zone = 'hand'; pl.hand.append(c)
            for _ in range(n_hand - k): c = pl.upper.pop(); c.zone = 'hand'; pl.hand.append(c)
            self.L(f'{pl.name} 시작 패 (메인 {k} / 상급 {n_hand-k}): {", ".join(map(str, pl.hand))}', 'draw')
            back = pl.ai.mulligan(self, i, list(pl.hand))
            if back:
                for c in back:
                    pl.hand.remove(c); self._to_deck_raw(c)
                # 다시 뽑을 때 메인 · 상급 배분을 바꿔도 된다 (§4 STEP 6)
                nm = pl.ai.mulligan_split(self, i, back)
                nm = max(len(back) - len(pl.upper), min(nm, len(back), len(pl.main))); nu = len(back) - nm
                for _ in range(nm): self.draw(i, 1, 'main')
                for _ in range(nu): self.draw(i, 1, 'upper')
                self.L(f'{pl.name} 멀리건 {len(back)}장 ({", ".join(map(str, back))}) → 패: {", ".join(map(str, pl.hand))}', 'decision')
            else: self.L(f'{pl.name} 멀리건 안 함', 'decision')
        self.opening = [[c.name for c in self.p[i].hand] for i in (0, 1)]
        self.snaps = []

    def run(self):
        try:
            self.setup()
            while True:
                cap = getattr(self, 'turn_cap', None)
                if cap and self.turn >= cap[0] and getattr(self, 'script', None) and self.script['forced']:
                    return 'eval', self.evaluate(cap[1])
                if self.turn >= SAFETY_TURNS:   # 판정 없음 — 무한 진행 방지용 중단
                    raise StalledGame(f'{SAFETY_TURNS}턴 안에 라운드 종료 조건(§11-1)이 충족되지 않음')
                self.play_turn()
        except GameOver as go:
            for i in (0, 1):
                f = getattr(self.p[i].ai, 'end_game', None)
                if f: f(self, i, go.winner)
            self.L(f'■ 라운드 종료 — 승자: {self.p[go.winner].name if go.winner is not None else "무승부"} ({go.reason})', 'end')
            return go.winner, go.reason


def _flags_no_attack(self, g):
    return self.idx in getattr(g, 'no_attack', {}) and g.no_attack[self.idx] == g.turn
Player.flags_no_attack = _flags_no_attack

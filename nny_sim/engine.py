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
    def level(self):
        """flags['level_set']: 효과로 부여된 레벨(표시목 · 짐승조커 등)이 원래 레벨보다 우선"""
        v = self.flags.get('level_set')
        return v if v is not None else self.d.get('level', 0)
    @property
    def attr(self):
        """속성. flags['attr_set']: 효과로 부여된 속성 — 문자열 하나 또는 여러 속성의 튜플(「모두로 취급」)"""
        v = self.flags.get('attr_set')
        return v if v is not None else self.d.get('attr')
    def has_attr(self, a):
        v = self.attr
        return a in v if isinstance(v, (tuple, list, set, frozenset)) else v == a
    def is_monster(self):
        """flags['as_monster']: 효과로 몬스터로 취급되는 마법 · 필드 카드 (짐승조커 · 표시목 부여, 포커짐승들 — 플래그가 없는 카드는 그대로)"""
        return (self.type == '몬스터' or bool(self.flags.get('as_monster'))) and not self.flags.get('as_spell')
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


def link_targets(link):
    """그 발동의 「대상」: 발동 시(코스트 단계)에 골라 l.ctx에 넣어 둔 카드 (구현 관례 — 「대상으로 하고」는 코스트 단계에서 고른다).
    처리 시에 고르는 「고르고」 효과는 대상을 지정하지 않는 효과로 본다 (호박옥의 수호자 - 마르모르 · 카르분쿨루스, 각성의 태동)"""
    out = []
    for k, v in link.ctx.items():
        if k in ('ev', 'opt_keys', 'from_zone'): continue
        if isinstance(v, Card): out.append(v)
        elif isinstance(v, (list, tuple)): out += [x for x in v if isinstance(x, Card)]
    return out


# ─────────────────────────── 플레이어 ───────────────────────────
class Player:
    def __init__(self, idx, name, skill_def, ai):
        self.idx = idx; self.name = name; self.hp = START_HP
        self.main = []; self.upper = []; self.hand = []; self.grave = []; self.banish = []
        self.m = [None] * MZ; self.s = [None] * SZ; self.skill = None
        self.skill_def = skill_def; self.ai = ai
        self.normal_summons = 1; self.oath = -1       # 맹세 제약 만료 턴
        self.oath_group = '번성충'                     # 맹세 제약 동안 사용할 수 있는 카드군 (「자신은 「X」 카드만 사용할 수 있다」)
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
        self.act_limit = {}       # 플레이어 → (턴, 그 턴에 발동할 수 있는 효과 수) — 저주인형 - 비비안 1번
        self.act_count = {}       # (플레이어, 턴) → 발동한 효과 수

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

    # 효과 내성 플래그 — [지속] 공격력 · 수비력 증감도 받지 않는다 (2026-10-13: 예전에는 immune_others · immune_except만 보았다)
    MOD_IMMUNE_KEYS = ('immune_except', 'immune_others', 'immune_except_group', 'immune_all_until', 'immune_opp_until', 'immune_opp_perm',
                       'untargetable_opp', 'immune_opp_untargeted')
    def mod_applies(self, c, src):
        """src의 [지속] 증감(atk_mod · def_mod)이 c에 적용되는가: 자기 자신 · 무효화된 카드는 그대로, 내성 플래그가 있으면 Game.immune으로 판정"""
        if src is c or self.is_neg(c) or not any(k in c.flags for k in self.MOD_IMMUNE_KEYS): return True
        return not self.immune(c, src.controller, src)
    def atk(self, c):
        v = c.base_atk() + sum(x for s, x, _ in c.mods if s == 'atk')
        for src in self.continuous_sources():
            f = getattr(src, 'atk_mod', None)
            if f and self.mod_applies(c, src): v += f(self, src, c)
        if c.flags.get('atk_set') is not None: v = c.flags['atk_set']
        return max(0, v)
    def df(self, c):
        v = c.base_def() + sum(x for s, x, _ in c.mods if s == 'def')
        for src in self.continuous_sources():   # [지속] 수비력 증감 def_mod (포커짐승들 2026-10-12 추가 — def_mod가 없는 카드는 그대로)
            f = getattr(src, 'def_mod', None)
            if f and self.mod_applies(c, src): v += f(self, src, c)
        return max(0, v)
    def immune(self, c, by, src=None):
        """c가 플레이어 by의(src: 효과의 주체 카드, 모르면 None) 효과를 받지 않는가.
        카드 자신의 [지속]이 정한 내성(무효화되면 사라짐):
          flags['immune_except'] = 카드명 — 「그 카드 이외의 카드의 효과를 받지 않는다」 (자기 자신의 효과는 받는다)
          flags['immune_except_opp'] — immune_except의 예외 카드도 상대(by ≠ 컨트롤러)의 것만 받는다
          flags['immune_others'] — 「다른 카드의 효과를 받지 않는다」 (자신 · 상대 모두). src를 모르면 받지 않는 것으로 본다"""
        if self.on_field(c) and not self.is_neg(c):
            ex = c.flags.get('immune_except')
            # flags['immune_except_opp'] — 그 예외 카드도 「상대의」 것만 (퇴마의 부적: 「상대의 「저주 - 의심」 마법 이외의 카드의 효과를 받지 않는다」, 2026-10-15)
            if ex is not None and src is not c and not (src is not None and src.name == ex and (not c.flags.get('immune_except_opp') or by != c.controller)): return True
            if c.flags.get('immune_others') and src is not c: return True
            eg = self.flag(c, 'immune_except_group')   # 「「X」 카드 이외의 카드의 효과를 받지 않는다」 (호박옥) — 조건부면 callable 플래그(Game.flag)
            if eg is not None and src is not c and not (src is not None and eg in (src.d.get('groups') or ())): return True
            if c.flags.get('immune_all_until', -1) >= self.turn and src is not c: return True   # 고대의 봉인: 턴 종료 시까지 다른 카드의 효과
        if by is None or by == c.controller: return False
        if self.on_field(c) and not self.is_neg(c):   # 대상 지정 여부에 따른 내성 (호박옥의 수호자) — 플래그가 없는 카드는 그대로
            if self.flag(c, 'untargetable_opp') and (self.targeting_now(by) or getattr(self, 'probing', None) == by): return True   # 「상대 효과의 대상이 되지 않는다」
            if self.flag(c, 'immune_opp_untargeted') and not self.targeted_by(c, by): return True   # 「상대 카드의 대상을 지정하지 않는 효과를 받지 않는다」
        if c.flags.get('immune_opp_until', -1) >= self.turn: return True
        if c.flags.get('immune_opp_perm') and self.on_field(c): return True
        if c.flags.get('immune_all_until', -1) >= self.turn: return True
        return self.rule('immune', c, by)

    def blocked(self, c, cause):
        if not cause or cause[0] != 'effect' or cause[1] is None or not self.on_field(c): return False
        if self.immune(c, cause[1].controller, cause[1]):
            self.L(f'{c}은(는) 상대의 효과를 받지 않음', 'sys'); return True
        return False

    # ── 조건부 [지속] 플래그 · 대상 지정 (호박옥, 2026-10-12 추가 — 플래그를 쓰지 않는 카드의 동작은 그대로) ──
    def flag(self, c, key, default=None):
        """c.flags[key] 읽기. 값이 callable이면 (g, c) → 값으로 그때그때 계산한다 — 「이 카드에 봉인 카운터가 놓여 있는 한」 같은 조건부 [지속]"""
        v = c.flags.get(key, default)
        return v(self, c) if callable(v) else v

    def targeting_now(self, by):
        """by가 지금 발동하는 효과의 코스트 단계(대상을 고르는 중)인가"""
        l = getattr(self, 'costing', None)
        return l is not None and l.player == by

    def targeted_by(self, c, by):
        """c가 by의 효과의 대상인가: 그 발동의 코스트 단계이거나, 처리 중인 by의 효과가 발동 시 c를 골라 두었다(link_targets)"""
        if self.targeting_now(by): return True
        l = getattr(self, 'resolving_link', None)
        return l is not None and l.player == by and any(x is c for x in link_targets(l))

    def stays(self, c, cause, destroyed=False):
        """「파괴 이외의 방법으로 필드를 벗어나지 않는다」(flags['leave_only_destroy'], callable 가능): 효과 · 코스트로 묘지 · 덱 · 패 · 제외로
        옮기려 하면 남는다. 파괴와 규칙 처리(cause 'rule')는 막지 않는다 (ASSUME)"""
        if destroyed or not self.on_field(c) or self.is_neg(c) or not self.flag(c, 'leave_only_destroy'): return False
        if cause and cause[0] == 'rule': return False
        self.L(f'{c}은(는) 파괴 이외의 방법으로 필드를 벗어나지 않음', 'sys'); return True

    def must_attack(self, m):
        """「상대는 반드시 공격해야 한다」([지속] 규칙 'must_attack' — 격투가의 투기장 1번)가 몬스터 m에 적용되는가.
        그 효과를 받지 않는 몬스터(고대의 봉인 등)는 공격하지 않아도 된다 (설계도 확정 2026-10-10)"""
        for src in self.continuous_sources():
            f = getattr(src, 'rules', {}).get('must_attack')
            if f and f(self, src, m.controller) and not self.immune(m, src.controller, src): return True
        return False

    def attack_banned(self, m):
        """「공격할 수 없다」: flags['no_attack'](callable 가능) · flags['no_attack_until'](그 턴까지)"""
        return bool(self.flag(m, 'no_attack')) or m.flags.get('no_attack_until', -1) >= self.turn

    def battle_damage(self, p, amt, src, pair=None):
        """p가 받는 전투 대미지. [지속] 규칙 'half_battle_damage'(p): 「자신이 받는 전투 대미지는 절반이 된다」 (호박옥 - 봉인의 계약 3번, 1의 자리 버림)
        pair: 몬스터끼리의 전투면 (공격 몬스터, 공격 대상). [지속] 규칙 'no_battle_damage'(p, a, t): 그 전투로 p가 받는 대미지는 0
        (「이 카드가 몬스터와 전투할 때, 상대 플레이어에게 가하는 대미지는 0」 — 던전마스터 데스 칠 드래곤, 2026-10-12 추가 — 규칙이 없으면 그대로)"""
        if amt > 0 and pair is not None and self.rule('no_battle_damage', p, *pair):
            self.L(f'{self.pname(p)}이(가) 받는 전투 대미지 0: {amt} → 0', 'sys'); return
        if amt > 0 and self.rule('half_battle_damage', p):
            self.L(f'{self.pname(p)}이(가) 받는 전투 대미지 절반: {amt} → {amt // 2}', 'sys'); amt //= 2
        self.damage(p, amt, src)

    def is_neg(self, c): return c.negated or bool(c.flags.get('perma_neg')) or any(e.flags.get('negates_host') for e in c.equips)
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
            c.flags.pop('as_spell', None); c.flags.pop('perma_neg', None)
            for k in ('immune_opp_perm', 'stay', 'negates_host', 'immune_all_until', 'immune_opp_until', 'no_release_until',
                      'battle_indestr_until', 'no_pos_change_until', 'no_attack_until'): c.flags.pop(k, None)
            # 필드에 있는 동안만 부여된 특성 되돌리기 (표시목 · 짐승조커 · 올인의 레벨/속성/몬스터 취급, 포커짐승들 2026-10-12 추가):
            # flags['clear_on_leave'] = {플래그: 부여 전 값(None이면 삭제)} — 이 플래그가 없는 카드는 그대로
            for k, v in (c.flags.pop('clear_on_leave', None) or {}).items():
                if v is None: c.flags.pop(k, None)
                else: c.flags[k] = v
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
    def send_grave(self, c, cause=None, destroyed=False, from_battle=False, released=False):
        """released: 릴리스로 묘지에 보냄 (Game.tribute) — to_grave · leave_field 사건에 released=True (「이 카드가 릴리스되었을 때」, 포커짐승들)"""
        cause = cause or ('effect', self.src)
        if self.blocked(c, cause): return
        if self.stays(c, cause, destroyed): return
        prev = c.zone; ctrl = c.controller
        fu = c.faceup   # 사건 키 was_faceup: 묘지로 보내지기 직전 앞면이었는가 (「뒷면 표시의 이 카드가 묘지로 보내졌을 경우」 — 던전마스터 깜짝상자, 2026-10-12 추가)
        redirect = getattr(c, 'grave_redirect', None)
        was_field = self._remove(c)
        if redirect and redirect(self, c):
            self.L(f'{c} 묘지 대신 덱으로 (카드 효과)', 'sys'); self._to_deck_raw(c)
            if was_field: self.emit('leave_field', card=c, prev=prev, ctrl=ctrl, cause=cause, dest='deck', was_faceup=fu)
            return
        c.controller = c.owner; c.zone = 'grave'; c.faceup = True; self.p[c.owner].grave.append(c)
        self.emit('to_grave', card=c, prev=prev, ctrl=ctrl, cause=cause, destroyed=destroyed, battle=from_battle, released=released, was_faceup=fu)
        if was_field: self.emit('leave_field', card=c, prev=prev, ctrl=ctrl, cause=cause, dest='grave', released=released, was_faceup=fu)

    def destroy(self, c, cause=None, battle=False):
        cause = cause or ('effect', self.src)
        if not battle and self.blocked(c, cause): return False
        if self.rule('indestructible', c, battle):
            self.L(f'{c} 파괴되지 않음', 'sys'); return False
        if battle and c.flags.get('battle_indestr_until', -1) >= self.turn and self.on_field(c):   # 「(그 턴까지) 전투로는 파괴되지 않는다」 (임시 봉인)
            self.L(f'{c} 전투로 파괴되지 않음', 'sys'); return False
        self.L(f'{c} 파괴' + (' (전투)' if battle else ''))
        prev, ctrl = c.zone, c.controller   # destroyed 사건에 파괴 직전 위치 · 컨트롤러 (묘지 대신 덱으로 가는 카드도 — 격투가의 투기장 3번, 2026-10-13 추가)
        self.send_grave(c, cause, destroyed=True, from_battle=battle)
        self.emit('destroyed', card=c, cause=cause, battle=battle, prev=prev, ctrl=ctrl)
        return True

    def _to_deck_raw(self, c):
        c.controller = c.owner; c.faceup = True
        lst = self.p[c.owner].upper if c.deck_kind() == '상급' else self.p[c.owner].main
        lst.insert(self.rng.randrange(len(lst) + 1), c); c.zone = 'upper' if lst is self.p[c.owner].upper else 'main'

    def to_deck(self, c, cause=None):
        cause = cause or ('effect', self.src)
        if self.blocked(c, cause): return
        if self.stays(c, cause): return
        prev = c.zone; ctrl = c.controller
        was_field = self._remove(c); self._to_deck_raw(c)
        if was_field: self.emit('leave_field', card=c, prev=prev, ctrl=ctrl, cause=cause, dest='deck')

    def to_hand(self, c, cause=None, p=None):
        cause = cause or ('effect', self.src)
        if self.blocked(c, cause): return
        if c.zone in ('main', 'upper') and cause[0] == 'effect' and self.rule('no_deck_to_hand', c.owner if p is None else p):
            self.L(f'{c}: 효과로 덱에서 패에 넣을 수 없음', 'sys'); return
        if self.stays(c, cause): return
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
        if self.stays(c, cause): return
        prev = c.zone; ctrl = c.controller
        was_field = self._remove(c)
        c.controller = c.owner; c.zone = 'banish'; c.faceup = True; self.p[c.owner].banish.append(c)   # 제외 존은 앞면 공개 (§10-7)
        if was_field: self.emit('leave_field', card=c, prev=prev, ctrl=ctrl, cause=cause, dest='banish')

    def releasable(self, c):
        return c.flags.get('no_release_until', -1) < self.turn and not (self.flag(c, 'no_release') and self.on_field(c) and not self.is_neg(c))

    def tribute(self, c, cause=None):
        if not self.releasable(c): self.L(f'{c}은(는) 릴리스할 수 없음', 'sys'); return
        cause = cause or ('effect', self.src)
        if self.blocked(c, cause): return
        self.L(f'{c} 릴리스'); self.send_grave(c, cause, released=True)

    def can_change_control(self, c, p):
        """c의 컨트롤을 p에게 옮길 수 있는가: 새 컨트롤러의 빈 몬스터 존이 있어야 한다(공유 존의 몬스터도 — 설계도 확정 2026-10-07).
        옮길 수 없으면 처리할 수 없는 효과이므로 발동할 수 없다(정본 3-6 e)"""
        return c.controller == p or (bool(self.free_m(p)) and not self.field_limited(c, p))

    def field_limited(self, c, p):
        """[지속] 「자신 필드에 「X」 몬스터는 n장밖에 존재할 수 없다」(솔루나 아츠 1번 — rules['field_limit']) — c가 p의 필드에 새로 나올 수 없는가.
        소환(no_special과 같은 판정)뿐 아니라 제외 존에서의 복귀 · 컨트롤 획득에도 적용한다 (사용자 답변 2026-10-20)"""
        return self.rule('field_limit', c, p)

    def change_control(self, c, p):
        """컨트롤 변경. 공유 존은 마커가 가리키는 플레이어의 소유이므로, 공유 존의 몬스터가 상대에게 넘어가면 마커는 그대로 두고
        그 몬스터를 새 컨트롤러의 몬스터 존으로 옮긴다 (설계도 확정 2026-10-07 — 예전에는 공유 존에 둔 채 마커를 뒤집었다)"""
        if c.controller == p: return True
        fr = self.free_m(p)
        if not fr: return False
        if self.field_limited(c, p): self.L(f'{c} — {self.pname(p)} 필드에 같은 종류가 이미 있어 컨트롤을 옮길 수 없음', 'sys'); return False
        if c.zone == 'shared': self.shared = None
        else: self.p[c.controller].m[self.p[c.controller].m.index(c)] = None
        self.p[p].m[fr[0]] = c; c.zone = 'm'; c.controller = p
        return True

    # ── 소환 ──
    def can_special(self, c, p):
        """c를 지금 특수소환할 수 있는가. 규칙상 불가능한 후보는 처리 전에 걸러낸다(처리 중 실패 방지):
        소환 금지 [지속] · 같은 이름 규칙(정본 3-6 f: 자신의 효과로 같은 이름의 카드를 덱에서 특수소환할 수 없음) · 놓을 자리"""
        if self.rule('no_special', c, p): return False
        if c.flags.get('ss_by_skill_only') and (self.src is None or self.src.type != '스킬'): return False
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
        return [x for x in self.monsters(p) if x.is_monster() and self.releasable(x)]

    def can_change_pos(self, c, p):
        """표시 형식 변경 (§8-1): 자신의 앞면 몬스터 · 몬스터당 1턴 1번 · 소환된 턴 불가.
        시점은 규칙서에 없어 자신 턴 · 체인이 없을 때로 둔다"""
        return (self.turn_player == p and not self.chain and c.controller == p and c.is_monster() and self.on_field(c)
                and c.faceup and c.summon_turn != self.turn and c.pos_turn != self.turn and not self.flag(c, 'no_pos_change')
                and c.flags.get('no_pos_change_until', -1) < self.turn
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
        use_extra = self.p[p].normal_summons <= 0 and self.extra_normal_left(p, c) > 0   # 기본 일반소환을 다 썼으면 추가 일반소환 권리를 쓴다
        for t in tributes: self.tribute(t, ('summon', None))
        if pos is None: pos = self.summon_pos(c, p, 'normal')
        if pos == 'def' and not self.def_allowed(p): pos = 'atk'
        self._remove(c); self.place_monster(c, p, pos); c.summon_turn = self.turn
        if use_extra:
            k = (p, self.turn); self.extra_ns_used[k] = self.extra_ns_used.get(k, 0) + 1
            self.L(f'{self.pname(p)} 추가 일반소환 권리 사용', 'sys')
        else: self.p[p].normal_summons -= 1
        self.L(f'{self.pname(p)} {c} 일반소환' + (' (수비 표시)' if c.pos == 'def' else '')
               + (f' (제물 {", ".join(map(str, tributes))})' if tributes else ''))
        self.emit('summon', card=c, player=p, how='normal', prev='hand', by=None)

    # ── 추가 일반소환 (포커짐승들 2026-10-12 추가 — extra_normal을 주는 카드가 없으면 기본 1회 규칙 그대로) ──
    @property
    def extra_ns_used(self):
        """(플레이어, 턴) → 그 턴에 쓴 추가 일반소환 횟수"""
        d = self.__dict__.get('_extra_ns_used')
        if d is None: d = self.__dict__['_extra_ns_used'] = {}
        return d

    def extra_normal_left(self, p, c=None):
        """[지속] 「(「X」 몬스터를) 추가로 일반소환할 수 있다」 권리 중 이번 턴 남은 횟수.
        각 [지속] 카드의 extra_normal(g, src, p, c) = 그 카드가 p에게 주는 횟수 (c: 소환하려는 카드 — 카드군 제한 판정, None이면 제한 없이 센다)"""
        per = {}   # 같은 이름 카드가 여러 장이어도 권리는 겹치지 않는다(1턴 N번은 카드명 단위, §6-4) — 이름별 최댓값의 합
        for src in self.continuous_sources():
            f = getattr(src, 'extra_normal', None)
            if f: per[src.name] = max(per.get(src.name, 0), f(self, src, p, c))
        n = sum(per.values())
        return max(0, n - self.extra_ns_used.get((p, self.turn), 0)) if n else 0

    def can_normal(self, p, c=None):
        """p가 지금 (c를) 일반소환할 권리가 남았는가: 기본 1회(normal_summons) 또는 추가 일반소환 권리"""
        return self.p[p].normal_summons > 0 or self.extra_normal_left(p, c) > 0

    @staticmethod
    def tributes_needed(level):
        return 0 if level <= 4 else 1 if level <= 7 else 2 if level <= 9 else 3

    # ── 카운터 ──
    def add_counter(self, c, name, n=1):
        """카운터는 효과 내성과 무관하게 놓인다(퇴마의 부적 1번 괄호). 스킬 존의 스킬 카드에도 놓을 수 있다(희생제)"""
        if not (self.on_field(c) or c.zone == 'skill') or not c.faceup: return False
        c.counters[name] = c.counters.get(name, 0) + n
        self.L(f'{c}에 {name} 카운터 {n}개 → {c.counters[name]}개'); self.emit('counter', card=c, name=name, delta=n, total=c.counters[name])
        self.state_check(); return True
    def clear_counters_facedown(self, c):
        """정본 6-4: 카운터가 놓인 카드가 뒷면 표시가 되면 카운터는 전부 사라진다 (제거 효과가 아니므로 counter 사건을 내지 않는다)"""
        if c.counters:
            self.L(f'{c} 뒷면 — 카운터 소멸 ({", ".join(f"{k} {v}" for k, v in c.counters.items())})', 'sys')
            c.counters = {}; self.state_check()

    def remove_counter(self, c, name, n=1):
        k = min(n, c.counters.get(name, 0))
        if k <= 0: return 0
        c.counters[name] -= k
        if c.counters[name] == 0: del c.counters[name]
        self.L(f'{c}의 {name} 카운터 {k}개 제거'); self.emit('counter', card=c, name=name, delta=-k, total=c.counters.get(name, 0))
        self.state_check(); return k

    # ── HP ──
    def damage(self, p, amt, src=''):
        if amt <= 0: return
        if getattr(self, 'no_damage', {}).get(1 - p, -1) >= self.turn and src != '공유 존 마커' and not src.startswith('자해'):
            self.L(f'{self.pname(1-p)}은(는) 이 턴 대미지를 줄 수 없음 — {amt} 무효', 'sys'); return
        # [지속] 규칙 'no_effect_damage'(p, src): 「자신은 상대의 효과를 받지 않는다」 — 상대의 효과 대미지를 받지 않는다
        # (데이터버그 버터플라이 2번, 2026-10-12 추가 — 출처 판정은 규칙 쪽. 규칙이 없으면 그대로)
        if src != '공유 존 마커' and not str(src).startswith('자해') and self.rule('no_effect_damage', p, src):
            self.L(f'{self.pname(p)}은(는) 상대의 효과를 받지 않음 — 대미지 {amt} 무효 ({src})', 'sys'); return
        self.p[p].hp -= amt
        self.L(f'{self.pname(p)} {amt} 대미지 ({src}) → HP {self.p[p].hp}')
        self.emit('damage', player=p, amount=amt)
        if not getattr(self, '_hp_defer', 0): self.hp_check()

    def hp_check(self):
        """HP 0 판정. 효과 하나를 처리하는 동안(_hp_defer)은 미뤘다가 처리가 끝난 뒤 한 번에 본다 —
        양쪽 HP가 동시에 0이 되면 무승부(승점 없음, 설계도 확정 2026-10-07)"""
        dead = [i for i in (0, 1) if self.p[i].hp <= 0]
        if len(dead) == 2: raise GameOver(None, '양쪽 HP 동시 0 — 무승부')
        if dead: raise GameOver(1 - dead[0], f'{self.pname(dead[0])} HP 0')

    def deferring_hp(self, fn, *a):
        """fn(*a)을 HP 0 판정을 미룬 채 실행하고, 끝난 뒤 판정한다 (효과 하나의 처리 · [지속] 종료 처리)"""
        self._hp_defer = getattr(self, '_hp_defer', 0) + 1
        try: return fn(*a)
        finally:
            self._hp_defer -= 1
            if not self._hp_defer: self.hp_check()
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
            if not src:
                # 패배는 메인 덱과 상급 덱이 모두 떨어졌을 때만(정본 4 b). 한 덱만 비었으면 지정한 덱에서 뽑지 못할 뿐 (설계도 확정 2026-10-07)
                if not pl.main and not pl.upper: raise GameOver(1 - p, f'{pl.name} 덱아웃')
                self.L(f'{pl.name} {"메인" if deck == "main" else "상급"} 덱이 비어 드로우하지 못함', 'sys'); return
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

    def dump(self, p, n, why='', top=True):
        """p의 메인 덱 위에서부터 n장을 묘지로 보낸다 (「메인 덱 (맨) 위에서부터 카드를 n장 묘지로 보낸다」).
        덱에서 묘지로 간 카드도 묘지로 보내진 것이므로 [유언] 사건(to_grave, prev='main')이 생긴다 — 각 카드 텍스트의
        「덱에서 묘지로 보내졌을 경우 발동하지 않는다」 단서는 카드 쪽에서 거른다.
        「자신이 메인 덱 맨 위에서부터 카드를 묘지로 보낼 때 1장을 추가로 보낼 수 있다」([지속] dump_extra)는 top일 때 AI가 고른다.
        반환: 묘지로 보낸 카드 목록"""
        pl = self.p[p]
        if top and n > 0 and self.rule('dump_extra', p):
            f = getattr(pl.ai, 'choose_extra_dump', None)
            if (f(self, p, n) if f else len(pl.main) - n >= 8):
                n += 1; self.L(f'{pl.name} 1장 추가로 묘지로 보냄 (간절한 마음)', 'sys')
        out = []
        for _ in range(n):
            if not pl.main: break
            c = pl.main.pop(); c.zone = 'grave'; c.controller = c.owner; c.faceup = True; pl.grave.append(c); out.append(c)
        if n: self.L(f'{pl.name} 메인 덱 위에서 {len(out)}장 묘지로{(" (" + why + ")") if why else ""}: {", ".join(map(str, out))} — 남은 덱 {len(pl.main)}/{len(pl.upper)}')
        for c in out:
            self.emit('to_grave', card=c, prev='main', ctrl=p, cause=('effect', self.src), destroyed=False, battle=False)
        return out

    def deck_to_grave(self, p, c, why=''):
        """덱의 특정 카드 1장을 묘지로 (「메인 덱에서 카드 1장을 묘지로 보낸다」 — 위에서부터가 아님)"""
        prev = c.zone
        self._remove(c); c.zone = 'grave'; c.controller = c.owner; c.faceup = True; self.p[c.owner].grave.append(c)
        self.L(f'{self.pname(p)} 덱에서 {c} 묘지로{(" (" + why + ")") if why else ""}')
        self.emit('to_grave', card=c, prev=prev, ctrl=p, cause=('effect', self.src), destroyed=False, battle=False)

    def deck_cards(self, p, which=('main', 'upper')):
        out = []
        for w in which: out += getattr(self.p[p], w)
        return out

    def search_cands(self, p, pred, which=('main', 'upper'), source=None):
        """서치 후보: 덱에서 pred를 만족하고, 서치 효과의 주체 카드와 이름이 다른 카드 (사용자 재정)"""
        src = source or self.src
        if self.rule('no_deck_to_hand', p): return []   # 덱에서 패에 넣을 수 없다 [지속] — 서치 후보 없음
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
    @staticmethod
    def opt_key(c, e):
        """1턴 1번을 세는 단위: 카드명 × 효과 번호(전역 규칙 — 같은 이름 단위). 효과를 받아 얻은 효과(e.opt_per_card — 올인 2번 · 격투가 세레모니)는
        얻을 때마다 별개의 사용 횟수를 가지므로 그 카드 한 장 단위로 센다 (사용자 답변 2026-10-17)"""
        return (c.name, e.num, c.uid) if getattr(e, 'opt_per_card', False) else (c.name, e.num)

    def opt_ok(self, p, c, e):
        if e.opt is None: return True
        return self.p[p].opt.get(self.opt_key(c, e), 0) < e.opt

    # ── 발동 가능 판정 ──
    def zone_ok(self, c, e, p):
        z = c.zone
        if e.kind == 'lastwill' and c.uid in getattr(self, 'lw_grace', ()) and c.owner == p: return True   # Game.triggers의 [유언] 우선 선언
        if z in ('main', 'upper', 'banish'):   # 덱 · 제외 존에서 발동하는 효과는 그 영역을 적은 효과만 (호박옥 - 황금봉랍 2번)
            return ('deck' if z != 'banish' else 'banish') in e.zones and c.owner == p
        if z == 'hand' and 'hand' not in e.zones: return False
        if z in ('m', 's', 'shared', 'fieldz'):
            # e.owner_only: 「이 효과의 발동은, 원래 주인인 플레이어만 선언할 수 있다」 — 컨트롤러 대신 원래 주인 (던전마스터 깜짝상자, 2026-10-12 추가 — 표시가 없는 효과는 그대로)
            who = c.owner if getattr(e, 'owner_only', False) else c.controller
            # e.either_player: 「서로가 … 발동」 — 컨트롤러가 아닌 플레이어도 발동할 수 있다 (세제 2 · 3번, 사용자 답변 2026-10-20 — cards.Impl.attach가 텍스트로 표시)
            if 'field' not in e.zones or (who != p and not getattr(e, 'either_player', False)): return False
            # e.facedown_ok: 「뒷면 표시일 때만 발동할 수 있다」 뒷면 몬스터의 효과 (던전마스터 깜짝상자 — 표시가 없는 효과는 그대로)
            if not c.faceup and not (c.is_spell_like() and e.spell_act) and not getattr(e, 'facedown_ok', False): return False
            if self.is_neg(c): return False
        if z == 'grave' and 'grave' not in e.zones: return False
        if z == 'skill' and c.controller != p and not getattr(e, 'either_player', False): return False
        if z == 'skill' and c.negated: return False
        if z in ('main', 'upper', 'banish'): return False
        if z == 'hand' and c.owner != p: return False
        return True

    def oath_ok(self, p, c):
        if self.p[p].oath < self.turn: return True
        grp_ = self.p[p].oath_group; gs = c.d.get('groups')
        return (grp_ in gs) if gs is not None else c.has(grp_)

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
        lim = self.act_limit.get(p)
        if lim and lim[0] == self.turn and self.act_count.get((p, self.turn), 0) >= lim[1] \
           and not getattr(e, 'procedure', False): return False   # 비비안: 발동 횟수 제한 (소환 절차 e.procedure는 발동이 아님)
        # 발동 조건은 「그 카드가 효과의 주체」인 상태로 판정한다 — 처리 때와 같은 규칙(같은 이름 서치 · 특수소환 금지 등)으로
        # 후보가 있는지 보아, 규칙상 처리할 수 없는 발동을 미리 막는다
        prev = (self.src, getattr(self, 'src_eff', None)); self.src, self.src_eff = c, e
        # 코스트가 있는 효과의 발동 판정은 대상 지정 내성을 「가장 엄격하게」 본다(Game.probing): 「상대 효과의 대상이 되지 않는다」 카드는
        # 대상으로 보지 않고(코스트에서 고르면 대상), 「대상을 지정하지 않는 효과를 받지 않는다」 카드는 대상 지정으로 보지 않는다(처리 시 고르면 비대상).
        # → 발동 판정이 통과하면 코스트 단계 · 처리 · AI 점수의 후보는 늘 그 이상이라 빈 후보로 깨지지 않는다 (2026-10-13)
        prev_probe = getattr(self, 'probing', None)
        if e.cost: self.probing = p
        try:
            if not self.can_act(p, c, e, ev): return False
            if not self.cost_extra_ok(p, c, e): return False   # 두플리카토르로 2배가 된 코스트를 낼 수 없으면 발동 불가
            if not self.transfer_ok(p, c, e): return False     # 델레가토르로 상대가 대신 낼 수 없는 코스트면 발동 불가
        finally:
            self.src, self.src_eff = prev
            self.probing = prev_probe
        if not self.spell_speed_ok(c, p, e): return False
        if e.spell_act and c.zone == 'hand':
            if c.type == '필드': pass
            elif not self.free_s(p): return False
        return True

    # ── 코스트 지불자 (세리 - 델레가토르 1번 [지속]: 자신이 카드의 발동을 위해 지불해야 하는 코스트는 상대가 대신 지불한다) ──
    # 사용자 답변(2026-10-20): 상대가 대신 낼 수 있는 모든 코스트에 적용한다. 상대가 대신 낼 수 없으면 그 효과는 발동할 수 없다.
    # 단 덱 코스트는 상대 덱이 모자라도 발동할 수 있고, 대신 지불하다 덱이 모자라면(덱이 음수) 상대가 룰상 패배한다.
    # 코스트의 종류는 카드 텍스트의 코스트 문장(「…고 발동」)에서 읽는다 — Effect.cost_items (cards.parse_cost):
    #   self(「이 카드를 …」 · 「이 카드의 …」 · 「자신을 포함하는 …」) — 상대가 대신 낼 수 없다 → 발동 불가
    #   deck(「덱의 위에서부터 카드를 n장 제외」 · 「덱에서 카드를 n장 제외」) — 상대 덱에서 (Game.pay_deck_cost)
    #   그 밖 — 지불자를 받는 코스트 함수(Effect.cost_payable(g, c, p, 지불자) — 그 지불자가 낼 수 있는가)가 있을 때만 상대가 대신 낸다.
    #           cost_payable이 없는 코스트는 활성 플레이어 자신의 자원으로만 구현되어 있으므로 상대가 대신 낼 수 없는 것으로 본다 (ASSUME)
    def cost_payer(self, p):
        """p의 발동 코스트를 실제로 내는 플레이어"""
        return 1 - p if self.rule('cost_transfer', p) else p

    def transfer_ok(self, p, c, e):
        q = self.cost_payer(p)
        if q == p: return True
        items = getattr(e, 'cost_items', None)
        if not items: return True                       # 텍스트에 코스트가 없다 (코스트 함수는 대상 · 기록만)
        if any(i['self'] for i in items): return False  # 「이 카드」 코스트는 상대가 대신 낼 수 없다
        pay_ok = getattr(e, 'cost_payable', None)
        if pay_ok is not None: return bool(pay_ok(self, c, p, q))
        return all(i['deck'] for i in items)

    def pay_deck_cost(self, p, n, deck, why):
        """「덱의 위에서부터 카드를 n장 제외하고 발동」 코스트 (부족분은 다른 덱에서 — 세리 카드 문구). 델레가토르면 상대 덱에서 대신 내고,
        모자라면 그 플레이어의 덱이 음수가 되어 패배한다(사용자 답변 2026-10-20). 반환: 실제 제외 매수"""
        q = self.cost_payer(p)
        if q != p: self.L(f'델레가토르: 코스트를 {self.pname(q)}가 대신 지불', 'sys')
        k = self.mill(q, n, deck, why, fallback=True)
        if q != p and k < n:
            raise GameOver(p, f'{self.p[q].name} 대신 지불한 덱 코스트 {n}장 중 {k}장 — 덱이 음수가 되어 패배')
        return k

    # ── 두플리카토르 (세리 - 두플리카토르 1번 [지속]: 서로가 카드의 발동을 위해 코스트로 지불해야 하는 카드의 매수는 2배) ──
    # 카드 매수로 지불하는 코스트에 Effect.cost_spec = (동작, 후보 함수 또는 None, 원래 매수 중 후보에서 내는 매수, 늘어나는 매수)를 단다.
    # 정본 3-6 f 재정: 코스트가 「이 카드」만이면 「이 카드 1장」으로 보아 2배(이 카드 + 같은 곳의 카드 1장 — 후보 None),
    # 「이 카드를 포함한 n장」이면 이 카드를 뺀 나머지만 2배. 세리의 덱 위 제외 · 제외 존→덱 코스트는 cards4가 직접 2배로 한다.
    COST_ACTIONS = {'grave': 'send_grave', 'release': 'tribute', 'banish': 'banish', 'deck': 'to_deck', 'hand': 'to_hand'}

    def cost_specs(self, p, c, e):
        """지금 적용되는 코스트 명세 목록 (dupcost.py) — 두플리카토르가 없으면 빈 목록"""
        specs = getattr(e, 'cost_spec', None)
        if not specs or not self.rule('cost_double', p): return []
        return [s for s in specs if len(s) < 5 or s[4](self, c, p)]

    def cost_extra_pool(self, p, c, s, zone=None):
        """두플리카토르로 더 내야 하는 카드의 후보. 후보 함수가 없으면(「이 카드」 코스트) 이 카드가 있는 곳의 다른 카드"""
        act, pool = s[0], s[1]
        if pool is not None: return list(pool(self, c, p))   # 후보 함수가 정한 범위 그대로 (이 카드를 포함할 수 있는 코스트 — 재정 질문 데이터버그 12)
        z = zone or c.zone; pl = self.p[p]
        if z == 'hand': xs = list(pl.hand)
        elif z == 'grave': xs = list(pl.grave)
        elif z in ('m', 'shared'): xs = [x for x in self.monsters(p) if x.is_monster()]
        else: xs = self.field_cards(p)
        xs = [x for x in xs if x is not c]
        if act == 'release': xs = [x for x in xs if self.releasable(x)]
        return xs

    def cost_extra_ok(self, p, c, e):
        return all(len(self.cost_extra_pool(p, c, s)) >= s[2] + s[3] for s in self.cost_specs(p, c, e))

    def pay_cost_extra(self, p, c, specs, link):
        for s in specs:
            # 자신의 카드는 덜 아끼는 것부터, 상대의 카드(상대 카드를 코스트로 쓰는 효과)는 상대가 아끼는 것부터
            xs = sorted(self.cost_extra_pool(p, c, s, link.ctx.get('from_zone')),
                        key=lambda x: self.p[x.controller].ai.card_pri(self, x.controller, x) * (1 if x.controller == p else -1))[:s[3]]
            self.L(f'두플리카토르: 코스트 {s[3]}장 더 지불 — {", ".join(map(str, xs)) or "없음"}', 'sys')
            for x in xs:
                if s[0] == 'hand_opp': self.to_hand(x, ('cost', c), p=1 - p)
                elif s[0] == 'deck_grave': self.deck_to_grave(p, x, '두플리카토르 코스트')
                else: getattr(self, self.COST_ACTIONS[s[0]])(x, ('cost', c))

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
        link.ctx['opt_keys'] = [self.opt_key(c, e)]   # 이 발동이 소모하는 1턴 1회 (카드명 × 효과 번호, §6-4 — Game.opt_key). 코스트 처리에서 바꿀 수 있다
        prev_costing = getattr(self, 'costing', None); self.costing = link   # 코스트 단계 = 대상을 고르는 중 (Game.targeting_now)
        specs = self.cost_specs(p, c, e)   # 두플리카토르: 원래 코스트를 내기 전에 정한다 (코스트로 이 카드 · 조건이 바뀌므로)
        try: cancel = bool(e.cost) and e.cost(self, c, p, link) is False
        finally: self.costing = prev_costing
        if cancel:
            self.L(f'{c} 발동 취소 (코스트/대상 불가)', 'sys')
            if e.spell_act and placed_from == 'hand' and self.on_field(c): self._remove(c); c.zone = 'hand'; self.p[p].hand.append(c)
            return None
        if specs: self.pay_cost_extra(p, c, specs, link)
        for k in link.ctx['opt_keys']: self.p[p].opt[k] = self.p[p].opt.get(k, 0) + 1
        # e.procedure: 소환 절차(「…해야만 패에서 특수소환할 수 있다」 — 데이터버그 더 바이러스 · 더 딜리트, 2026-10-12 추가)는 효과의 발동이 아니다 —
        # 발동 횟수 · 발동 사건을 남기지 않는다 (no_resp · unnegatable과 함께 쓴다). 표시가 없는 효과는 그대로
        proc = getattr(e, 'procedure', False)
        if not proc: self.act_count[(p, self.turn)] = self.act_count.get((p, self.turn), 0) + 1
        self.chain.append(link)
        if not proc: self.emit('activate', link=link, player=p)
        return link

    def options(self, p, kinds, ev=None):
        out = []
        pl = self.p[p]
        cards = list(pl.hand) + self.field_cards(p) + list(pl.grave) + ([pl.skill] if pl.skill else [])
        # 상대 필드에 있는 자신 소유 카드의 「원래 주인만 선언할 수 있다」 효과 (e.owner_only — 던전마스터 깜짝상자, 2026-10-12 추가)
        cards += [x for x in self.field_cards(1 - p) if x.owner == p and any(getattr(e, 'owner_only', False) for e in x.effects)]
        # 상대 스킬 · 필드 카드의 「서로가 … 발동」 효과 (e.either_player — 세제 2 · 3번, 2026-10-20 추가)
        opp = self.p[1 - p]
        cards += [x for x in ([opp.skill] if opp.skill else []) + self.field_cards(1 - p)
                  if x not in cards and any(getattr(e, 'either_player', False) for e in x.effects)]
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
                self.L(f'체인 {len(self.chain)+1} {c} {e.num}번 — 처리 치환', 'res'); self.deferring_hp(link.replaced, self, link)
            else:
                self.L(f'체인 {len(self.chain)+1} {c} {e.num}번 처리', 'res')
                self.src = c; self.src_eff = e
                prev_res = getattr(self, 'resolving_link', None); self.resolving_link = link   # 처리 중인 발동 (Game.targeted_by) — 엔진의 resolving(불린)과 다른 이름
                if e.res: self.deferring_hp(e.res, self, c, p, link)
                self.resolving_link = prev_res
                self.src = None; self.src_eff = None
            if e.spell_act and self.on_field(c) and c.type == '마법' and c.d.get('subtype') in ('일반', '신속', '트리거') \
               and not c.flags.get('stay'):
                if c.flags.get('banish_on_resolve'): self.L(f'{c} 발동 후 제외', 'sys'); self.banish(c, ('rule', None))
                else: self.send_grave(c, ('rule', None))
            if link.negated and e.spell_act and self.on_field(c) and c.type != '마법':
                pass
        self.triggers()

    def negate_card(self, c, src=None, perma=None):
        """앞면 카드의 효과를 무효로 한다 (「그 카드를 턴 종료 시까지 무효로 한다」 등). 효과 내성에 막히면 False.
        perma: 그 값이 남아 있는 동안 무효(장착 · 「의심」처럼 효과가 끝날 때까지). 무효화 사건(negated, card=c)을 낸다 — 저주 - 강령"""
        src = src if src is not None else self.src
        if not self.on_field(c): return False
        if self.blocked(c, ('effect', src)): return False
        if perma is None: c.negated = True
        else: c.flags['perma_neg'] = perma
        self.emit('negated', link=None, card=c, player=c.controller, by=src)
        return True

    def negate(self, link, destroy=False, by=None):
        if getattr(link.eff, 'unnegatable', False) or link.card.flags.get('unnegatable'):
            self.L(f'{link.card}은(는) 무효화되지 않음', 'sys'); return
        link.negated = True
        for k in link.ctx.get('opt_keys', [(link.card.name, link.eff.num)]):   # 무효화된 발동은 사용 횟수를 소모하지 않는다 (§6-5)
            if self.p[link.player].opt.get(k): self.p[link.player].opt[k] -= 1
        self.L(f'{link.card} {link.eff.num}번 효과 무효' + (' 후 파괴' if destroy else ''))
        self.emit('negated', link=link, player=link.player, by=by)
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
        tp = self.turn_player; built = False; last = None
        def collect(p):
            pl = self.p[p]
            cards = list(pl.hand) + self.field_cards(p) + list(pl.grave) + ([pl.skill] if pl.skill else []) + list(pl.banish)
            cards += [x for x in pl.main + pl.upper if x.flags.get('deck_trigger')]   # 덱에서 발동하는 트리거를 가진 카드만
            out = []
            for c in cards:
                for e in c.effects:
                    if e.kind not in ('trigger', 'summon', 'lastwill', 'battle') or getattr(e, 'summon_negate', False): continue   # 소환 무효는 위에서만 묻는다
                    for ev in evs:
                        if e.kind == 'summon' and ev.get('negated'): continue   # 무효가 된 소환의 [소환] 효과는 묻지 않는다
                        if self.legal(p, c, e, ev):
                            out.append((c, e, ev)); break
            return out
        # [유언]은 우선적으로 발동 선언한다(정본 3-6 b): 사건 때 발동할 수 있던 [유언]은, 같은 선언 차례에 먼저 선언한 쪽의 코스트로
        # 그 카드가 묘지를 떠나도 발동한다 (재정 로그 2 — 헬 3번). lw_grace = 그런 카드의 uid (Game.zone_ok · [유언] 조건이 본다)
        # 소환 무효(Effect.summon_negate — 더 바이러스 2번)는 그 소환의 [소환] 효과보다 먼저 묻는다. 무효로 했으면 소환 사건에 negated가 달리고
        # [소환] 효과는 묻지 않는다 (설계도 확정 2026-10-10)
        for q in (tp, 1 - tp):
            pre = [(c, e, ev) for c in self.field_cards(q) for e in c.effects if getattr(e, 'summon_negate', False)
                   for ev in evs if ev.get('kind') == 'summon' and not ev.get('negated') and self.legal(q, c, e, ev)]
            for c, e, ev in self.p[q].ai.choose_triggers(self, q, pre) if pre else ():
                if not ev.get('negated') and self.legal(q, c, e, ev) and self.activate(q, c, e, ev): self.priority(1 - q)
        prev_grace = getattr(self, 'lw_grace', frozenset())
        self.lw_grace = prev_grace | frozenset(c.uid for q in (tp, 1 - tp) for c, e, _ in collect(q) if e.kind == 'lastwill')
        for p in (tp, 1 - tp):
            pl = self.p[p]
            cands = collect(p)
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
                    if self.activate(p, c, e, ev): built = True; last = p
        self.lw_grace = prev_grace
        # 조건이 채워진 효과는 번갈아 하지 않는다: 턴 플레이어가 다 선언한 뒤 상대가 이어서 선언하고, 마지막에 선언한 쪽의 상대부터
        # 번갈아 응답한다 (설계도 확정 2026-10-08 — 예전에는 늘 비턴 플레이어부터)
        if built: self.priority(1 - last)
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
        """발동하고 우선권을 넘긴다. 발동 링크를 돌려준다 — 코스트/대상 불가로 취소되면 None (AI가 같은 행동을 다시 고르지 않게)"""
        link = self.activate(p, c, e)
        if link:
            self.priority(1 - p)
        return link

    # ═════════════════════════ 전투 ═════════════════════════
    def can_declare_attack(self, p):
        """p가 이번 턴 아직 공격 선언을 할 수 있는 상태인가: 자신 턴 · 선공 1턴째가 아님 (§5-3) · 공격 봉인 없음 · 전투 단계 이전"""
        return self.turn_player == p and self.turn > 1 and self.no_attack.get(p) != self.turn and self.phase in ('준비', '진행', '전투')

    def blockers(self, p):
        """p 필드에서 상대의 직접공격을 막는 몬스터: 앞면 몬스터만. 상대 몬스터가 없거나 뒷면 몬스터뿐이면 직접공격할 수 있다
        (설계도 확정 2026-10-07 — 뒷면 몬스터는 공격 대상이 아니다, 정본 1-1)"""
        return [m for m in self.monsters(p) if m.faceup]

    def can_direct(self, c):
        opp = 1 - c.controller
        return not self.blockers(opp) or self.rule('direct_attack', c)

    def can_attack_with(self, m):
        """공격 선언할 수 있는 몬스터인가: 앞면 공격 표시만 (뒷면 공격 표시 몬스터는 공격할 수 없다 — 사용자 재정 2026-10-06)"""
        return m.faceup and m.pos == 'atk' and not self.attack_banned(m)

    def set_face_down(self, c, cause=None):
        """「뒷면 표시로 한다」 효과 (사용자 재정 2026-10-06): 표시 형식은 그대로 두고 뒷면으로 — 공격 표시 몬스터는
        뒷면 공격 표시, 수비 표시 몬스터는 뒷면 수비 표시가 된다. 텍스트가 「뒷면 수비 표시로」를 정하면 pos='def'를 넘긴다.
        뒷면 몬스터는 [지속]이 적용되지 않는다(continuous_sources는 앞면만). 뒷면이 되면 놓여 있던 카운터는 전부 사라진다(정본 6-4).
        장착 처리는 규칙 미확정 — 그대로 둔다(ASSUME)"""
        cause = cause or ('effect', self.src)
        if not self.on_field(c) or not c.is_monster() or not c.faceup: return False
        if self.blocked(c, cause): return False
        c.faceup = False; self.clear_counters_facedown(c)
        self.L(f'{c} 뒷면 {"공격" if c.pos == "atk" else "수비"} 표시로')
        self.emit('face_down', card=c, cause=cause)
        return True

    def attack_targets(self, c):
        return [m for m in self.monsters(1 - c.controller) if m.faceup and not self.rule('no_battle_target', m)]   # 뒷면은 공격 대상 아님(정본 1-1)

    def attack(self, a, target):
        p = a.controller; o = 1 - p
        if not self.can_attack_with(a):   # 뒷면 공격 표시 · 수비 표시는 공격 선언 불가 — AI 후보에서 이미 거르지만 엔진에서도 막는다
            self.L(f'{a}은(는) 공격할 수 없음 (앞면 공격 표시가 아님)', 'sys'); return
        a.attacks_made += 1
        self.L(f'{self.pname(p)} {a}(ATK {self.atk(a)}) → ' + (f'{target}' if target else '직접공격'))
        self.emit('attack', card=a, target=target)
        self.after_action(p)
        # 공격 선언 뒤의 응답으로 공격한 몬스터나 대상이 사라졌으면 그 공격은 끝나고, 공격하지 않은 것으로 보아 다시 공격 선언할 수 있다
        # (설계도 확정 2026-10-08)
        if not self.on_field(a) or a.controller != p or not a.faceup: return
        if target is not None and (not self.on_field(target) or target.controller != o or not target.faceup):
            a.attacks_made -= 1
            self.L('공격 대상 소멸 — 공격 종료 (공격하지 않은 것으로 봄)', 'sys'); return
        if target is None:
            self.battle_damage(o, self.atk(a), f'{a.name} 직접공격')
            self.emit('direct_hit', card=a)
        else:
            # 전투 판정 (§5-3). battle_win = [전투] 발동 사건: 전투로 카드를 '파괴하는 데 성공'했을 때만 (§7)
            av = self.atk(a)
            if target.pos == 'atk':
                tv = self.atk(target)
                if av > tv:
                    dt = self.destroy(target, ('battle', a), battle=True); self.battle_damage(o, av - tv, '전투', pair=(a, target))
                    if dt: self.emit('battle_win', card=a, target=target, player=p)
                elif av < tv:
                    da = self.destroy(a, ('battle', target), battle=True); self.battle_damage(p, tv - av, '전투', pair=(a, target))   # [유희왕] 기준선
                    if da: self.emit('battle_win', card=target, target=a, player=o)
                else:
                    da = self.destroy(a, ('battle', target), battle=True); dt = self.destroy(target, ('battle', a), battle=True)
                    if dt: self.emit('battle_win', card=a, target=target, player=p)
                    if da: self.emit('battle_win', card=target, target=a, player=o)
            else:
                tv = self.df(target)
                if av > tv:   # 수비 표시를 넘어도 HP 피해 없음 (정본 3-3)
                    if self.destroy(target, ('battle', a), battle=True): self.emit('battle_win', card=a, target=target, player=p)
                elif av < tv: self.battle_damage(p, tv - av, '전투(수비 반사)', pair=(a, target))   # [유희왕] 기준선: 공격 몬스터는 파괴되지 않음
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
        for c in self.monsters(0) + self.monsters(1):   # 영구 부여된 추가 공격(격투가 세레모니 재정, flags['perm_extra_attacks'])은 매 턴 다시 붙는다
            c.attacks_made = 0; c.extra_attacks = c.flags.get('perm_extra_attacks', 0)
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
        for m in self.monsters(tp):   # 「상대 몬스터 전부에 공격」: 공격 횟수 상한은 전투 단계 시작 시의 상대 몬스터 수
            if m.flags.get('attack_all'): m.flags['attack_all_cap'] = (self.turn, len(self.monsters(1 - tp)))
        if self.turn > 1 and not pl.flags_no_attack(self):   # 선공 1턴째에는 공격 선언 불가 (§5-3) — 전투 단계 자체는 진행한다
            pl.ai.battle_phase(self, tp)
        self.set_phase('정비'); self.open_window()
        pl.ai.main_phase(self, tp, '정비')
        # 종료 단계 (§5-5): a 「턴 종료 시」 효과 → b 패 7장 → c 「턴 종료 시까지」 해제 → d 턴 종료
        self.set_phase('종료')
        for c in self.continuous_sources():   # [지속] 종료 단계 처리: 필드의 카드와 스킬 존의 스킬 (스킬은 필드가 아니지만 [지속]이 적용된다)
            f = getattr(c, 'end_process', None)
            if f and (self.on_field(c) or c.zone == 'skill'): self.deferring_hp(f, self, c)
        self.emit('end_phase', player=tp)
        self.triggers()
        if self.chain: self.resolve_chain()
        # ASSUME(2026-10-11): 종료 단계 a의 「턴 종료 시」 처리 뒤, 잠기기 전에 턴 플레이어부터 우선권을 한 번 준다 —
        # 「(이 효과는 종료 단계에서만 사용할 수 있다)」 [신속](저주인형 - 비비안 · 처키)이 쓰일 자리. 예전에는 트리거가 있을 때만 창이 열렸다
        self.open_window()
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
                    c.flags.pop('return_from_banish')
                    # 돌아갈 몬스터 존 · 공유 존이 없거나 필드에 나올 수 없으면(솔루나 아츠 1번 등 — Game.field_limited) 그대로 제외 존에 남는다
                    # (사용자 답변 2026-10-20 — 예전에는 묘지로 보냈다)
                    if (not self.free_m(c.owner) and self.shared is not None) or self.field_limited(c, c.owner):
                        self.L(f'{c} 제외에서 복귀할 수 없음 — 제외 존에 남음', 'sys'); continue
                    self.L(f'{c} 제외에서 복귀', 'sys')
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

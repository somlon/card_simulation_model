"""던전마스터 테마 테스트 (nny_sim 폴더에서):  python -m unittest test_theme_dungeon -v
카드 18종의 효과와 이 테마로 추가된 엔진 기능(owner_only · facedown_ok · was_faceup · no_battle_damage)을 확인한다."""
import random, unittest
import season as SE
from ai import HeuristicAI
from cards import Impl, grp
from engine import Game, Card

DECKS = SE.load_decks()
ME, OPP = '던전마스터 셔플!', '솔루나 아츠'
BOX = '던전마스터 깜짝상자'; MOURNER = '던전마스터 망령'; KNIGHT = '던전마스터 다크나이트'; SACRIFICE = '던전마스터 새크리파이스'
TRAPPER = '던전마스터 트랩퍼'; ASSASSIN = '던전마스터 다크엘프 어새신'; MAGICIAN = '던전마스터 다크 매지션'; EMPEROR = '던전마스터 다크 엠퍼러'
INFERNO = '던전마스터 인페르노 드래곤'; HELL = '던전마스터 헬'; CONTROLLER = '던전마스터 컨트롤러'; DEATHCHILL = '던전마스터 데스 칠 드래곤'
NEEDLE = '트랩: 가시바늘'; BOX_TRAP = '트랩: 깜짝상자'; SPRING = '트랩: 거짓 샘물'; REPAIR = '트랩 리페어 시스템'; LAW = '암흑의 율법'
EX = '세리 - 엑삭토르'          # 1000 / 1300 (직접 놓으면 효과 없음)
KILLER = '매수당한 킬러'        # 2100 / 1500
CHIEF = '치프 세리 - 프로쿠라토르'   # 1500 / 3000


class Idle(HeuristicAI):
    """아무 것도 하지 않는 AI (강제 트리거만) — 테스트가 직접 조작한다"""
    def respond(self, g, p, opts): return None
    def choose_triggers(self, g, p, cands): return [(c, e, ev) for c, e, ev in cands if e.mandatory]
    def main_phase(self, g, p, ph): return None
    def battle_phase(self, g, p): return None
    def mulligan(self, g, p, hand): return []


class Yes(Idle):
    """임의 트리거도 모두 발동"""
    def choose_triggers(self, g, p, cands): return list(cands)


def make(ai=Idle, seed=5):
    da, db = DECKS[ME], DECKS[OPP]
    g = Game([dict(da, 이름='A'), dict(db, 이름='B')], [ai(ME), ai(OPP)], 0, random.Random(seed), [], Impl)
    g.setup(); g.turn = 3; g.turn_player = 0; g.phase = '진행'
    for p in (0, 1):   # 패를 덱으로 — 테스트가 필요한 카드만 넣는다
        for c in list(g.p[p].hand): g.p[p].hand.remove(c); g._to_deck_raw(c)
    g.events = []
    return g


def card(g, name, owner, zone):
    c = Card(Impl.pool[name], owner); Impl.attach(c); c.zone = zone
    if zone in ('hand', 'grave', 'main', 'upper', 'banish'): getattr(g.p[owner], zone).append(c)
    return c


def on_field(g, name, owner, pos='atk'):
    c = card(g, name, owner, None); g.place_monster(c, owner, pos); c.summon_turn = 0; return c


def spell_on_field(g, name, owner, faceup=True):
    c = card(g, name, owner, None); g.place_spell(c, owner, faceup); return c


def run_triggers(g):
    g.triggers()
    if g.chain: g.resolve_chain()


def eff(c, num):
    return next(e for e in c.effects if e.num == num)


# ═══════════════════════ 메인 덱 몬스터 ═══════════════════════
class BoxTest(unittest.TestCase):
    def test_quick_only_while_face_down_and_by_owner(self):
        g = make()
        box = on_field(g, BOX, 0); t = on_field(g, KILLER, 1)
        e1 = eff(box, 1)
        self.assertFalse(g.legal(0, box, e1))              # 앞면이면 발동할 수 없다
        g.set_face_down(box)
        self.assertTrue(g.legal(0, box, e1))
        self.assertFalse(g.legal(1, box, e1))
        g.act(0, box, e1)
        self.assertTrue(box.faceup); self.assertEqual(box.pos, 'def')   # 코스트: 앞면 수비 표시
        self.assertEqual(t.zone, 'grave')

    def test_owner_opens_box_on_opponent_field_after_shuffle(self):
        g = make()
        box = on_field(g, BOX, 0); g.set_face_down(box)
        a = on_field(g, EX, 1); g.set_face_down(a)
        b = on_field(g, KILLER, 1)
        sk = g.p[0].skill
        g.act(0, sk, eff(sk, 1))                             # 셔플! 1번: 뒷면 카드 맞바꿈
        self.assertIn(box, g.p[1].m); self.assertIn(a, g.p[0].m)
        self.assertEqual((box.controller, a.controller), (1, 0))
        self.assertFalse(box.faceup or a.faceup)
        self.assertIn((box, eff(box, 1)), g.options(0, ('quick',)))      # 원래 주인은 상대 필드의 상자를 연다
        self.assertNotIn((box, eff(box, 1)), g.options(1, ('quick',)))   # 컨트롤러(상대)는 열 수 없다
        g.act(0, box, eff(box, 1))
        self.assertEqual(b.zone, 'grave')                    # 원래 주인 기준 「상대 필드의 카드」
        self.assertTrue(box.faceup); self.assertEqual(box.controller, 1)

    def test_last_will_destroys_only_when_sent_face_down(self):
        g = make(ai=Yes)
        box = on_field(g, BOX, 0); g.set_face_down(box)
        t = on_field(g, KILLER, 1); src = on_field(g, EX, 1)
        g.destroy(box, ('effect', src))
        ev = next(e for e in g.events if e['kind'] == 'to_grave' and e['card'] is box)
        self.assertFalse(ev['was_faceup'])                   # 엔진: 보내지기 직전 뒷면
        run_triggers(g)
        self.assertEqual(box.zone, 'main')                   # 덱으로
        self.assertEqual(t.zone, 'grave')                    # 뒷면이었으므로 카드 1장 파괴 (상대 카드 우선)
        g2 = make(ai=Yes)
        box2 = on_field(g2, BOX, 0); t2 = on_field(g2, KILLER, 1)
        g2.destroy(box2, ('effect', t2)); run_triggers(g2)
        self.assertEqual(box2.zone, 'main'); self.assertEqual(t2.zone, 'm')   # 앞면이면 덱으로만


class MournerKnightTest(unittest.TestCase):
    def test_mourner_releases_itself_to_negate(self):
        g = make(ai=Yes); g.turn_player = 1
        m = on_field(g, MOURNER, 0); mine = on_field(g, EX, 0)
        ld = card(g, '럭키 다이스', 1, 'hand')
        l1 = g.activate(1, ld, eff(ld, 1))
        self.assertTrue(g.legal(0, m, eff(m, 1), g.chain))
        g.activate(0, m, eff(m, 1))
        self.assertEqual(m.zone, 'grave')                    # 코스트: 릴리스
        g.resolve_chain()
        self.assertTrue(l1.negated); self.assertEqual(mine.zone, 'm')
        self.assertEqual(m.zone, 'main')                     # 2번 [유언]: 덱으로

    def test_dark_knight_trigger_and_last_will(self):
        g = make(ai=Yes); g.turn_player = 1
        k = on_field(g, KNIGHT, 0)
        x = card(g, KILLER, 1, 'hand')
        g.special_summon(x, 1, 'atk'); run_triggers(g)
        self.assertEqual(x.zone, 'grave')                    # 상대 소환 → 자신 릴리스, 대상 파괴
        self.assertEqual(k.zone, 'main')                     # [유언] 덱으로
        self.assertTrue(g.p[0].hand and grp(g.p[0].hand[-1], '던전마스터') and g.p[0].hand[-1].deck_kind() == '상급')


# ═══════════════════════ 상급 덱 몬스터 ═══════════════════════
class UpperTest(unittest.TestCase):
    def test_sacrifice_three_hand_effects(self):
        g = make()
        s1 = card(g, SACRIFICE, 0, 'hand')
        self.assertTrue(g.legal(0, s1, eff(s1, 1)))
        g.act(0, s1, eff(s1, 1))
        self.assertEqual(s1.zone, 'grave')
        self.assertEqual(len(g.p[0].hand), 1)
        self.assertTrue(grp(g.p[0].hand[0], '던전마스터') and g.p[0].hand[0].name != SACRIFICE)   # 같은 이름은 서치 불가
        dc = card(g, DEATHCHILL, 0, 'grave'); s2 = card(g, SACRIFICE, 0, 'hand')
        g.act(0, s2, eff(s2, 2))
        self.assertEqual(dc.zone, 'm')
        s3 = card(g, SACRIFICE, 0, 'hand')
        g.act(0, s3, eff(s3, 3))
        sets = [x for x in g.p[0].s if x and not x.faceup]
        self.assertEqual(len(sets), 2)
        self.assertTrue(all(x.type == '마법' and (grp(x, '트랩') or grp(x, '다크')) for x in sets))

    def test_trapper_set_and_turn_two_face_down(self):
        g = make()
        tr = on_field(g, TRAPPER, 0)
        g.act(0, tr, eff(tr, 1))
        sets = [x for x in g.p[0].s if x and not x.faceup]
        self.assertEqual(len(sets), 1)
        self.assertTrue(grp(sets[0], '트랩') and sets[0].type == '마법')
        self.assertEqual(sets[0].flags.get('act_this_turn'), g.turn)   # 이 턴에도 발동할 수 있다
        box = on_field(g, BOX, 0); opp = on_field(g, KILLER, 1)
        g.act(0, tr, eff(tr, 2))
        self.assertFalse(box.faceup); self.assertFalse(opp.faceup)       # 자신 쪽은 앞면 깜짝상자를 고른다
        self.assertTrue(tr.faceup)

    def test_trapper_turns_continuous_spell_face_down_for_reuse(self):
        g = make()
        tr = on_field(g, TRAPPER, 0)
        rep = spell_on_field(g, REPAIR, 0, True)             # 이미 발동한 지속 마법
        on_field(g, KILLER, 1)
        g.act(0, tr, eff(tr, 2))
        self.assertEqual(rep.zone, 's'); self.assertFalse(rep.faceup)
        self.assertTrue(g.legal(0, rep, eff(rep, 1)))        # 세트 상태 → 자신 턴에 다시 발동할 수 있다

    def test_forced_last_will_opponent_draws(self):
        g = make()
        tr = on_field(g, TRAPPER, 0); n = len(g.p[1].hand)
        g.destroy(tr, ('effect', None)); run_triggers(g)
        self.assertEqual(len(g.p[1].hand), n + 1)

    def test_assassin_three_times_per_turn_and_release(self):
        g = make()
        ts = [on_field(g, EX, 1) for _ in range(3)]
        a = [card(g, ASSASSIN, 0, 'hand') for _ in range(4)]
        for i in range(3):
            self.assertTrue(g.legal(0, a[i], eff(a[i], 1)))
            g.act(0, a[i], eff(a[i], 1))
            self.assertEqual(a[i].zone, 'm')
        self.assertTrue(all(t.zone == 'grave' for t in ts))
        self.assertFalse(g.legal(0, a[3], eff(a[3], 1)))   # 1턴에 3번까지
        k = on_field(g, KILLER, 1); n = len(g.p[1].hand)
        g.act(0, a[0], eff(a[0], 2))
        self.assertEqual(a[0].zone, 'grave'); self.assertEqual(k.zone, 'grave')
        self.assertEqual(len(g.p[1].hand), n + 1)           # 3번 [유언] (강제) 상대 드로우

    def test_magician_search_end_phase_salvage_and_destroy(self):
        g = make()
        mg = on_field(g, MAGICIAN, 0); hell = card(g, HELL, 0, 'grave')
        g.act(0, mg, eff(mg, 1))
        self.assertTrue(any(c.name == LAW for c in g.p[0].hand))   # 「다크」 마법
        self.assertEqual(hell.zone, 'grave')
        g.set_phase('종료')
        self.assertEqual(hell.zone, 'hand')                  # 종료 단계에 묘지의 「던전마스터」 몬스터 회수
        g.phase = '진행'
        t = on_field(g, KILLER, 1)
        g.act(0, mg, eff(mg, 2)); self.assertEqual(t.zone, 'grave')

    def test_emperor_summons_from_hand_and_knight_from_deck(self):
        g = make()
        em = card(g, EMPEROR, 0, 'hand'); inf = card(g, INFERNO, 0, 'hand')
        self.assertTrue(g.legal(0, em, eff(em, 1)))
        g.act(0, em, eff(em, 1))
        self.assertEqual(inf.zone, 'm'); self.assertEqual(em.zone, 'hand')
        em2 = on_field(g, EMPEROR, 0)
        g.act(0, em2, eff(em2, 2))
        self.assertTrue(any(m.name == KNIGHT for m in g.monsters(0)))

    def test_inferno_destroys_opponent_monsters_2000_or_more(self):
        g = make()
        big = on_field(g, KILLER, 1); wall = on_field(g, CHIEF, 1, 'def'); small = on_field(g, EX, 1)
        fd = on_field(g, KILLER, 1); g.set_face_down(fd)
        mine = on_field(g, KILLER, 0)
        on_field(g, INFERNO, 0)
        g.state_check()
        self.assertEqual(big.zone, 'grave'); self.assertEqual(wall.zone, 'grave')   # 공격력 2000 이상 · 수비력 2000 이상
        self.assertEqual(small.zone, 'm'); self.assertEqual(fd.zone, 'm'); self.assertEqual(mine.zone, 'm')

    def test_hell_mourner_guard_and_burn(self):
        g = make()
        h = on_field(g, HELL, 0)
        self.assertFalse(g.immune(h, 1))
        g.act(0, h, eff(h, 1))
        ms = [m for m in g.monsters(0) if m.name == MOURNER]
        self.assertEqual(len(ms), 1)
        self.assertTrue(g.immune(h, 1)); self.assertTrue(g.immune(h, 0, ms[0]))   # 효과를 받지 않는다 (다른 모든 카드)
        self.assertTrue(g.rule('indestructible', h, True))
        hp = g.p[1].hp
        x = card(g, EX, 1, 'hand'); g.special_summon(x, 1, 'atk')
        self.assertEqual(g.p[1].hp, hp - 200)                # 2번: 상대 소환마다 200
        y = card(g, EX, 0, 'hand'); g.special_summon(y, 0, 'atk')
        self.assertEqual(g.p[1].hp, hp - 200)
        g.destroy(ms[0], ('effect', None))                   # 「망령」이 없어지면 보호도 꺼진다
        self.assertFalse(g.immune(h, 1)); self.assertFalse(g.rule('indestructible', h, True))

    def test_controller_effects_and_last_will(self):
        g = make()
        ct = on_field(g, CONTROLLER, 0)
        g.act(0, ct, eff(ct, 1))
        ss = [m for m in g.monsters(0) if m is not ct]
        self.assertEqual(len(ss), 1); self.assertTrue(grp(ss[0], '던전마스터'))
        n = len(g.p[0].hand)
        g.act(0, ct, eff(ct, 2))
        self.assertEqual(len(g.p[0].hand), n + 1)
        nh = len(g.p[1].hand)
        g.destroy(ct, ('effect', None)); run_triggers(g)
        self.assertEqual(ct.zone, 'upper'); self.assertEqual(len(g.p[1].hand), nh + 1)

    def test_death_chill_battle_damage_and_search_lock(self):
        g = make()
        d = on_field(g, DEATHCHILL, 0); t = on_field(g, EX, 1, 'atk')
        hp = g.p[1].hp
        g.attack(d, t)
        self.assertEqual(t.zone, 'grave'); self.assertEqual(g.p[1].hp, hp)      # 몬스터와 전투: 상대 대미지 0
        self.assertFalse(g.can_search(1, lambda x: True)); self.assertTrue(g.can_search(0, lambda x: True))
        g2 = make(); g2.turn_player = 1
        d2 = on_field(g2, DEATHCHILL, 0, 'def'); a = on_field(g2, EX, 1, 'atk')
        hp = g2.p[1].hp
        g2.attack(a, d2)
        self.assertEqual(g2.p[1].hp, hp)                     # 수비 반사 대미지도 0
        g3 = make()
        d3 = on_field(g3, DEATHCHILL, 0)
        g3.attack(d3, None)
        self.assertEqual(g3.p[1].hp, 1000)                   # 직접공격은 그대로


# ═══════════════════════ 마법 ═══════════════════════
class SpellTest(unittest.TestCase):
    def test_needle_destroys_summoned_monster(self):
        g = make(ai=Yes); g.turn_player = 1
        nd = card(g, NEEDLE, 0, 'hand'); x = card(g, KILLER, 1, 'hand')
        g.special_summon(x, 1, 'atk'); run_triggers(g)
        self.assertEqual(x.zone, 'grave'); self.assertEqual(nd.zone, 'grave')

    def test_box_trap_rewrites_monster_effect(self):
        g = make(); g.turn_player = 1
        k = on_field(g, KILLER, 1); mine = on_field(g, EX, 0)
        bt = card(g, BOX_TRAP, 0, 'hand')
        g.activate(1, k, eff(k, 2))                          # 킬러 2번: 내 카드 1장 파괴 (대상)
        self.assertTrue(g.legal(0, bt, eff(bt, 1), g.chain))
        g.activate(0, bt, eff(bt, 1)); g.resolve_chain()
        self.assertEqual(mine.zone, 'm')                     # 원래 효과는 처리되지 않는다
        self.assertFalse(k.faceup)                           # 그 2장: 발동한 상대 카드
        boxes = [m for m in g.monsters(0) if m.name == BOX]
        self.assertEqual(len(boxes), 1); self.assertFalse(boxes[0].faceup)      # + 덱에서 특수소환된 깜짝상자
        self.assertEqual(bt.zone, 'grave')
        self.assertEqual(g.p[1].opt.get((KILLER, 2)), 1)     # 재정: 변경된 원 효과도 사용한 것으로 친다

    def test_box_trap_keeps_opponent_spell_set(self):
        g = make(); g.turn_player = 1
        mine = on_field(g, EX, 0)
        ld = card(g, '럭키 다이스', 1, 'hand'); bt = card(g, BOX_TRAP, 0, 'hand')
        g.activate(1, ld, eff(ld, 1)); g.activate(0, bt, eff(bt, 1)); g.resolve_chain()
        self.assertEqual(ld.zone, 's'); self.assertFalse(ld.faceup)   # 세트 상태로 남는다 (ASSUME)
        self.assertEqual(mine.zone, 'm')
        g.emit('phase', phase='전투')
        self.assertFalse(ld.flags.get('stay'))               # 임시 stay는 다음 사건에서 풀린다

    def test_false_spring(self):
        g = make(ai=Yes); g.turn_player = 1
        sp = card(g, SPRING, 0, 'hand')
        weak = on_field(g, EX, 0, 'atk'); atk = on_field(g, KILLER, 1, 'atk')
        x = g.p[1].main[-1]
        g.to_hand(x, ('effect', atk)); run_triggers(g)        # 상대가 덱에서 카드를 패에 넣었다
        self.assertEqual(sp.zone, 'grave')
        hp0, hp1 = g.p[0].hp, g.p[1].hp
        g.attack(atk, weak)
        self.assertEqual(weak.zone, 'm')                     # 상대는 전투로 몬스터를 파괴할 수 없다
        self.assertEqual(g.p[0].hp, hp0 - 1100)              # 전투 대미지는 그대로
        g.destroy(weak, ('effect', atk))
        self.assertEqual(g.p[1].hp, hp1 - 300)               # 상대가 효과로 제거할 때마다 300

    def test_repair_returns_traps_and_draws(self):
        g = make()
        gs = [card(g, NEEDLE, 0, 'grave'), card(g, BOX_TRAP, 0, 'grave'), card(g, SPRING, 0, 'grave'), card(g, BOX, 0, 'grave')]
        r = card(g, REPAIR, 0, 'hand')
        g.act(0, r, eff(r, 1))
        self.assertEqual(sum(1 for x in gs if x.zone == 'grave'), 1)   # 3장까지
        self.assertEqual(len(g.p[0].hand), 1)                # 1장 드로우
        self.assertEqual(r.zone, 's'); self.assertTrue(r.faceup)       # 지속 마법은 남는다

    def test_law_rewrites_forced_last_will(self):
        g = make()
        spell_on_field(g, LAW, 0, True)
        a = on_field(g, ASSASSIN, 0)
        n1 = len(g.p[1].hand)
        g.destroy(a, ('effect', None)); run_triggers(g)
        self.assertEqual(len(g.p[1].hand), n1)               # 상대 드로우 대신
        self.assertEqual(a.zone, 'upper')                    # 덱으로 되돌리고
        self.assertEqual(len(g.p[0].hand), 1)
        self.assertTrue(grp(g.p[0].hand[0], '던전마스터') and g.p[0].hand[0].name != ASSASSIN)   # 「던전마스터」 카드 서치

    def test_law_activation_revives(self):
        g = make()
        dc = card(g, DEATHCHILL, 0, 'grave'); law = card(g, LAW, 0, 'hand')
        self.assertTrue(g.legal(0, law, eff(law, 2)))
        g.act(0, law, eff(law, 2))
        self.assertEqual(dc.zone, 'm'); self.assertEqual(law.zone, 's'); self.assertTrue(law.faceup)


# ═══════════════════════ 스킬 ═══════════════════════
class SkillTest(unittest.TestCase):
    def test_shuffle_swaps_keep_counts(self):
        g = make()
        sk = g.p[0].skill
        mine = on_field(g, EX, 0, 'atk'); g.set_face_down(mine)
        o1 = on_field(g, KILLER, 1); g.set_face_down(o1)
        o2 = on_field(g, CHIEF, 1, 'def'); g.set_face_down(o2)
        g.act(0, sk, eff(sk, 1))
        fd = lambda p: sum(1 for m in g.p[p].m if m and not m.faceup)
        self.assertEqual((fd(0), fd(1)), (1, 2))             # 각 필드의 뒷면 매수는 그대로 (맞바꿈만)
        self.assertEqual(mine.controller, 1)
        self.assertEqual(sum(1 for x in (o1, o2) if x.controller == 0), 1)

    def test_shuffle_does_not_take_opponent_box(self):
        g = make()
        sk = g.p[0].skill
        mine = on_field(g, EX, 0); g.set_face_down(mine)
        obox = on_field(g, BOX, 1); g.set_face_down(obox)
        self.assertLess(eff(sk, 1).score(g, sk, 0, None), 0)   # 상대 소유 깜짝상자는 받지 않는다

    def test_shuffle_flip_and_summon_from_hand(self):
        g = make()
        sk = g.p[0].skill
        x = on_field(g, KILLER, 0); g.set_face_down(x)
        g.act(0, sk, eff(sk, 2)); self.assertTrue(x.faceup)
        dc = card(g, DEATHCHILL, 0, 'hand'); sac = card(g, SACRIFICE, 0, 'hand')
        g.act(0, sk, eff(sk, 3))
        self.assertEqual(dc.zone, 'm'); self.assertEqual(sac.zone, 'hand')   # 레벨 5 이상 — 패에서만 쓰는 새크리파이스는 고르지 않음


if __name__ == '__main__':
    unittest.main()

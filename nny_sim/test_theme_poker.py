"""포커짐승들 20종 (cards8) 테스트 (nny_sim 폴더에서):  python3 -m unittest test_theme_poker -v
족보 [신속](스트레이트 · 플러쉬 · 풀 하우스 · 포카드) · 올인(시작 패 7장, 원페어 · 트리플) · 표시목 · 짐승조커(몬스터 취급 · 릴리스 드로우) ·
추가 일반소환 · 쇠망치 · 도박장(패에서 [신속], 1턴 2번) · 쥐 묘지 소생 · 상급 공개 서치 · 메이드에 실패한 몬스터"""
import random, unittest
import season as SE
from ai import HeuristicAI
from cards import Impl
from engine import Game, Card
import cards8 as K

DECKS = SE.load_decks()
ME = '올인'
OPP = '솔루나 아츠'


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


def make(ai=Idle, seed=5, opp=OPP):
    """A(0) = 올인, B(1) = opp. 3턴 A의 진행 단계. 패 · 덱 · 묘지는 비운다 (테스트가 채운다)"""
    da, db = DECKS[ME], DECKS[opp]
    g = Game([dict(da, 이름='A'), dict(db, 이름='B')], [ai(ME), ai(opp)], 0, random.Random(seed), [], Impl)
    g.setup(); g.turn = 3; g.turn_player = 0; g.phase = '진행'; g.events = []
    for p in (0, 1):
        for z in ('hand', 'main', 'upper', 'grave'): getattr(g.p[p], z).clear()
    return g


def put(g, name, owner, zone):
    c = Card(Impl.pool[name], owner); Impl.attach(c); c.zone = zone
    if zone in ('hand', 'grave', 'main', 'upper', 'banish'): getattr(g.p[owner], zone).append(c)
    return c


def mon(g, name, owner, pos='atk'):
    c = put(g, name, owner, None); g.place_monster(c, owner, pos, allow_shared=False); return c


def spell(g, name, owner, faceup=True):
    c = put(g, name, owner, None); g.place_spell(c, owner, faceup); return c


def eff(c, num): return next(e for e in c.effects if e.num == num)


def run(g):
    g.triggers()
    if g.chain: g.resolve_chain()


def filler(g, p, n=10, name='밑장빼기'):
    for _ in range(n): put(g, name, p, 'main')


RAB, RAB_F = '♠ 스트레이트를 부르는 토끼', '♠ 메이드에 실패한 토끼'
WOLF, WOLF_F = '◆ 플러쉬를 노리는 늑대', '◆ 메이드에 실패한 늑대'
DOG, DOG_F = '♥ 풀 하우스를 찾는 강아지', '♥ 메이드에 실패한 강아지'
CAT, CAT_F = '♣ 포카드를 보는 고양이', '♣ 메이드에 실패한 고양이'


class ComboTest(unittest.TestCase):
    def test_straight_releases_three_and_summons_rabbit(self):
        g = make(ai=Yes); filler(g, 0)
        up = put(g, K.RABBIT_UP, 0, 'upper')
        r = mon(g, RAB, 0); m2 = mon(g, WOLF_F, 0); m3 = put(g, DOG, 0, 'hand')
        e = eff(r, 2)
        self.assertTrue(g.legal(0, r, e))
        hand0 = len(g.p[0].hand)
        g.act(0, r, e); run(g)
        self.assertEqual(up.zone, 'm')
        self.assertTrue(all(x.zone == 'grave' for x in (r, m2, m3)))
        self.assertEqual(len(g.p[0].hand), hand0 - 1 + 3)   # 패의 강아지 릴리스 → 스트레이트 토끼 [소환] 3장 드로우

    def test_straight_needs_consecutive_levels(self):
        g = make(); put(g, K.RABBIT_UP, 0, 'upper')
        r = mon(g, RAB, 0); mon(g, WOLF_F, 0); mon(g, CAT, 0)   # 1 · 2 · 4
        self.assertFalse(g.legal(0, r, eff(r, 2)))

    def test_straight_can_use_opponent_monster(self):
        g = make(); filler(g, 0); up = put(g, K.RABBIT_UP, 0, 'upper')
        r = mon(g, RAB, 0); mon(g, WOLF, 0)
        opp3 = mon(g, DOG_F, 1)   # 상대 필드의 레벨 3
        self.assertTrue(g.legal(0, r, eff(r, 2)))
        g.act(0, r, eff(r, 2))
        self.assertEqual(opp3.zone, 'grave'); self.assertIn(opp3, g.p[1].grave); self.assertEqual(up.zone, 'm')

    def test_rabbit_effect_not_from_hand_without_gambling_hall(self):
        g = make(); put(g, K.RABBIT_UP, 0, 'upper')
        r = put(g, RAB, 0, 'hand'); mon(g, WOLF, 0); mon(g, DOG_F, 0)
        self.assertFalse(g.legal(0, r, eff(r, 2)))
        f = put(g, K.GAMBLE, 0, None); g.place_field(f, 0)
        self.assertTrue(g.legal(0, r, eff(r, 2)))

    def test_gambling_hall_two_per_turn(self):
        """패에서의 [신속] 허가는 1턴 2번 (토끼 2번 · 늑대 2번은 각각 카드명 1턴 1번이므로, 3번째는 1턴 1번 기록을 지워 시험)"""
        g = make(); filler(g, 0)
        f = put(g, K.GAMBLE, 0, None); g.place_field(f, 0)
        put(g, K.RABBIT_UP, 0, 'upper'); put(g, K.WOLF_UP, 0, 'upper'); put(g, K.WOLF_UP, 0, 'upper')
        r = put(g, RAB, 0, 'hand'); mon(g, WOLF_F, 1); mon(g, DOG_F, 1)        # 1 (패) · 2 · 3 (상대 필드)
        self.assertTrue(g.legal(0, r, eff(r, 2))); g.act(0, r, eff(r, 2))
        w = put(g, WOLF, 0, 'hand'); mon(g, WOLF, 1); mon(g, WOLF_F, 1)       # 다이아 3장 (패 1 + 상대 필드 2)
        self.assertTrue(g.legal(0, w, eff(w, 2))); g.act(0, w, eff(w, 2))
        self.assertEqual(g.p[0].opt.get((K.GAMBLE, 1)), 2)
        for m in g.monsters(0): g.send_grave(m)
        g.p[0].opt.pop((WOLF, 2), None)
        w2 = put(g, WOLF, 0, 'hand'); mon(g, WOLF, 1); mon(g, WOLF_F, 1)
        self.assertFalse(g.legal(0, w2, eff(w2, 2)))   # 도박장 2번을 다 씀
        w3 = mon(g, WOLF, 0)
        self.assertTrue(g.legal(0, w3, eff(w3, 2)))    # 필드에서는 도박장과 무관

    def test_flush_same_attribute(self):
        g = make(); filler(g, 0); up = put(g, K.WOLF_UP, 0, 'upper')
        w = mon(g, WOLF, 0); a = put(g, WOLF_F, 0, 'hand'); b = mon(g, WOLF, 1)
        self.assertTrue(g.legal(0, w, eff(w, 2)))
        g.act(0, w, eff(w, 2))
        self.assertEqual(up.zone, 'm'); self.assertTrue(all(x.zone == 'grave' for x in (w, a, b)))

    def test_rat_counts_as_every_suit(self):
        g = make(); filler(g, 0); put(g, K.WOLF_UP, 0, 'upper')
        w = mon(g, WOLF, 0); mon(g, '스트플을 원하는 시골쥐', 0); mon(g, '스트플을 원하는 도시쥐', 1)
        self.assertTrue(g.legal(0, w, eff(w, 2)))

    def test_full_house_from_hand_and_damage(self):
        g = make(ai=Yes); filler(g, 0); up = put(g, K.DOG_UP, 0, 'upper')
        d = put(g, DOG, 0, 'hand')
        put(g, DOG_F, 0, 'grave'); mon(g, DOG_F, 1)            # 레벨 3: 패 1 + 묘지 1 + 상대 필드 1
        put(g, CAT, 1, 'grave'); put(g, CAT_F, 0, 'grave')     # 레벨 4: 2장
        hp0 = g.p[1].hp
        self.assertTrue(g.legal(0, d, eff(d, 2)))
        g.act(0, d, eff(d, 2)); run(g)
        self.assertEqual(up.zone, 'm'); self.assertEqual(d.zone, 'main')
        self.assertEqual(g.p[1].hp, hp0 - 2500)

    def test_full_house_cannot_be_five_of_same_level(self):
        g = make(); put(g, K.DOG_UP, 0, 'upper')
        d = put(g, DOG, 0, 'hand')
        for _ in range(4): put(g, DOG_F, 0, 'grave')
        self.assertFalse(g.legal(0, d, eff(d, 2)))

    def test_four_of_a_kind_and_destroy(self):
        g = make(ai=Yes); filler(g, 0); up = put(g, K.CAT_UP, 0, 'upper')
        c = put(g, CAT, 0, 'hand')
        put(g, CAT_F, 0, 'grave'); put(g, CAT_F, 1, 'grave'); mon(g, CAT, 1)
        o1 = mon(g, WOLF, 1); o2 = mon(g, RAB, 1)
        for _ in range(2): put(g, '밑장빼기', 0, 'grave')
        self.assertTrue(g.legal(0, c, eff(c, 2)))
        g.act(0, c, eff(c, 2)); run(g)
        self.assertEqual(up.zone, 'm')
        self.assertTrue(o1.zone == 'grave' and o2.zone == 'grave')   # 묘지 2장 되돌림 → 상대 카드 2장 파괴

    def test_no_upper_target_no_activation(self):
        g = make()
        r = mon(g, RAB, 0); mon(g, WOLF, 0); mon(g, DOG, 0)
        self.assertFalse(g.legal(0, r, eff(r, 2)))   # 상급 덱에 스트레이트 토끼 없음


class AllInTest(unittest.TestCase):
    def test_hand7(self):
        g = Game([dict(DECKS[ME], 이름='A'), dict(DECKS[OPP], 이름='B')], [Idle(ME), Idle(OPP)], 0, random.Random(1), [], Impl)
        g.setup()
        self.assertEqual(len(g.p[0].hand), 7); self.assertEqual(len(g.p[1].hand), 5)

    def test_pair_steals_and_grants(self):
        g = make()
        a = mon(g, WOLF, 0); b = put(g, WOLF_F, 0, 'hand')
        t = mon(g, '솔루나 시아', 1)
        e = eff(a, 21)
        self.assertTrue(g.legal(0, a, e))
        g.act(0, a, e)
        self.assertEqual(t.controller, 0); self.assertIn(t, g.monsters(0))
        self.assertIsNotNone(t.flags.get('level_set')); self.assertIsNotNone(t.flags.get('attr_set'))
        self.assertTrue(a.zone == 'grave' and b.zone == 'grave')

    def test_pair_needs_skill(self):
        g = make()
        a = mon(g, WOLF, 0); put(g, WOLF_F, 0, 'hand'); mon(g, '솔루나 시아', 1)
        g.p[0].skill.negated = True
        self.assertFalse(g.legal(0, a, eff(a, 21)))

    def test_triple_summons_from_deck(self):
        g = make(); filler(g, 0, 3)
        x = put(g, '스트플을 원하는 도시쥐', 0, 'upper')
        a = mon(g, DOG, 0); put(g, DOG_F, 0, 'hand'); mon(g, DOG_F, 1)
        e = eff(a, 22)
        self.assertTrue(g.legal(0, a, e))
        g.act(0, a, e)
        self.assertEqual(x.zone, 'm')

    def test_triple_needs_own_card(self):
        g = make(); put(g, '스트플을 원하는 도시쥐', 0, 'upper')
        a = mon(g, DOG, 0)
        for _ in range(3): mon(g, DOG_F, 1)
        g.p[0].hand.clear()
        # 자신의 카드(a) 포함 3장은 가능 — a를 빼면 불가능한지 계획 함수로 확인
        ms = [m for m in K.pools(g, 0, True)[0] if m.card is not a]
        self.assertTrue(all(m.where == 'opp_f' for m in ms))
        self.assertIsNone(K.f_triple(ms))


class SpellTest(unittest.TestCase):
    def test_marker_grants_level_and_attribute_spell_as_monster(self):
        g = make()
        s = spell(g, '밑장빼기', 0)
        K.grant(g, s, 3, '하트')
        self.assertTrue(s.is_monster()); self.assertEqual(s.level, 3); self.assertTrue(s.has_attr('하트'))
        g.send_grave(s)
        self.assertFalse(s.is_monster()); self.assertIsNone(s.flags.get('level_set'))

    def test_marker_activation(self):
        g = make(); m = mon(g, WOLF, 0)
        mk = put(g, '표시목', 0, 'hand')
        self.assertTrue(g.legal(0, mk, eff(mk, 1)))
        g.act(0, mk, eff(mk, 1))
        self.assertTrue(g.on_field(mk))   # 지속 마법은 남는다
        t = next(x for x in (m, mk) if x.flags.get('level_set') is not None)
        self.assertIn(t.flags['attr_set'], K.SUITS)

    def test_joker_becomes_monster_and_released_draws(self):
        g = make(ai=Yes); filler(g, 0)
        j = put(g, '짐승조커', 0, 'hand')
        self.assertTrue(g.legal(0, j, eff(j, 1)))
        g.act(0, j, eff(j, 1))
        self.assertEqual(j.zone, 'm'); self.assertTrue(j.is_monster()); self.assertEqual(g.atk(j), 0)
        self.assertIn(j.flags['attr_set'], K.SUITS); self.assertTrue(1 <= j.level <= 10)
        hand0 = len(g.p[0].hand)
        g.tribute(j, ('cost', None)); run(g)
        self.assertEqual(j.zone, 'main'); self.assertFalse(j.is_monster())
        self.assertEqual(len(g.p[0].hand), hand0 + 1)

    def test_joker_from_hand_on_opponent_turn(self):
        g = make(); g.turn_player = 1
        j = put(g, '짐승조커', 0, 'hand')
        self.assertTrue(g.legal(0, j, eff(j, 1)))

    def test_bottom_deal_searches_monster(self):
        g = make(); x = put(g, CAT, 0, 'main'); put(g, '표시목', 0, 'main')
        s = put(g, '밑장빼기', 0, 'hand')
        g.act(0, s, eff(s, 1))
        self.assertEqual(x.zone, 'hand')

    def test_hammer_banishes_opponent_search(self):
        g = make(ai=Yes)
        h = spell(g, '포커짐승들의 쇠망치', 0, faceup=False); h.set_turn = 1
        x = put(g, '솔루나 시아', 1, 'main')
        g.turn_player = 1
        g.to_hand(x)
        run(g)
        self.assertEqual(x.zone, 'banish')

    def test_hammer_ignores_draw(self):
        g = make(ai=Yes)
        h = spell(g, '포커짐승들의 쇠망치', 0, faceup=False); h.set_turn = 1
        x = put(g, '솔루나 시아', 1, 'main')
        g.turn_player = 1
        g.draw(1, 1); run(g)
        self.assertEqual(x.zone, 'hand')


class MonsterTest(unittest.TestCase):
    def test_extra_normal_summon_with_dog(self):
        g = make()
        mon(g, DOG, 0)
        a = put(g, CAT, 0, 'hand'); b = put(g, RAB, 0, 'hand'); c = put(g, '솔루나 시아', 0, 'hand')
        g.normal_summon(a, 0)
        self.assertTrue(g.can_normal(0, b))
        self.assertFalse(g.can_normal(0, c))   # 추가 일반소환은 「포커짐승들」만
        g.normal_summon(b, 0)
        self.assertFalse(g.can_normal(0, put(g, WOLF, 0, 'hand')))

    def test_rat_revives_when_own_pk_destroyed(self):
        g = make(ai=Yes)
        rat = put(g, '스트플을 원하는 시골쥐', 0, 'grave'); filler(g, 0)
        m = mon(g, CAT, 0)
        g.destroy(m); run(g)
        self.assertIn(rat.zone, ('m', 'shared'))

    def test_reveal_search(self):
        g = make()
        w = put(g, K.WOLF_UP, 0, 'hand'); x = put(g, WOLF, 0, 'main')
        e = eff(w, 3)
        self.assertTrue(g.legal(0, w, e))
        g.act(0, w, e)
        self.assertEqual(w.zone, 'upper'); self.assertEqual(x.zone, 'hand')

    def test_failed_rabbit_cannot_attack_and_last_will(self):
        g = make(ai=Yes); filler(g, 0)
        r = mon(g, RAB_F, 0)
        self.assertTrue(g.attack_banned(r))
        put(g, '밑장빼기', 0, 'grave')
        hand0 = len(g.p[0].hand)
        g.destroy(r); run(g)
        self.assertEqual(len(g.p[0].grave), 0)        # 자신 포함 묘지 2장 덱으로
        self.assertEqual(len(g.p[0].hand), hand0 + 1)

    def test_failed_dog_burns_on_pk_activation(self):
        g = make(); filler(g, 0)
        mon(g, DOG_F, 0); put(g, CAT, 0, 'main')
        s = put(g, '밑장빼기', 0, 'hand'); hp0 = g.p[1].hp
        g.act(0, s, eff(s, 1))
        self.assertEqual(g.p[1].hp, hp0 - 200)

    def test_failed_cat_lowers_opponent_stats(self):
        g = make()
        mon(g, CAT_F, 0); o = mon(g, '솔루나 시아', 1)
        a0, d0 = g.atk(o), g.df(o)
        put(g, WOLF, 0, 'grave'); put(g, DOG, 0, 'grave')
        self.assertEqual(g.atk(o), max(0, a0 - 200)); self.assertEqual(g.df(o), max(0, d0 - 200))

    def test_flush_wolf_attack_counts_diamonds(self):
        g = make()
        w = mon(g, K.WOLF_UP, 0); mon(g, WOLF_F, 0)
        self.assertEqual(g.atk(w), 1500 + 500 * 2)

    def test_straight_rabbit_negates_opponent_effect(self):
        g = make(); g.turn_player = 1
        rb = mon(g, K.RABBIT_UP, 0)
        s = put(g, '밑장빼기', 1, 'hand'); x = put(g, CAT, 1, 'main')
        g.activate(1, s, eff(s, 1))
        e3 = eff(rb, 3)
        self.assertTrue(g.legal(0, rb, e3))
        g.activate(0, rb, e3); g.resolve_chain()
        self.assertEqual(x.zone, 'main')   # 상대의 서치가 무효
        self.assertFalse(g.legal(0, rb, e3))   # 1턴 1번

    def test_rabbit_battle_indestructible(self):
        g = make()
        r = mon(g, RAB, 0)
        self.assertTrue(g.rule('indestructible', r, True))
        self.assertFalse(g.rule('indestructible', r, False))


if __name__ == '__main__':
    unittest.main()

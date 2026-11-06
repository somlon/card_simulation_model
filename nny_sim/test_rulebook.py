"""정본 룰지 · 사용자 답변(2026-10-17) · 설계도 확정 사항 테스트 (nny_sim 폴더에서):  python -m unittest test_rulebook -v"""
import random, unittest
import match as M
from engine import GameOver
from test_new_mechanics import make, card, on_field, eff, Idle



import databug_fixture   # 데이터버그 카드 · 덱(카드 풀에서 보류 중 — 사용자 지시 2026-10-30)을 이 모듈 시험 동안만 넣는다


def setUpModule(): databug_fixture.install()


def tearDownModule(): databug_fixture.uninstall()

class EngineRulingTest(unittest.TestCase):
    def test_face_down_spell_ignores_negation(self):
        # 사용자 지시 2026-10-25: 뒷면 마법 카드는 대상 · 비대상 무효 효과를 전부 받지 않는다
        g = make('세제', '세제')
        s = card(g, '취득세', 1, None); g.place_spell(s, 1, False)
        self.assertFalse(g.negate_card(s, None))
        self.assertFalse(g.is_neg(s))
        s.faceup = True
        self.assertTrue(g.negate_card(s, None))
        g.set_spell_face_down(s)                                 # 앞면일 때 받은 무효도 뒷면이 되면 사라진다
        self.assertFalse(g.is_neg(s))

    def test_face_down_clears_counters(self):
        # 정본 6-4: 카운터가 놓인 카드가 뒷면 표시가 되면 카운터는 전부 사라진다
        g = make('세제', '세제')
        m = on_field(g, '세리 - 릭토르', 1); m.counters['봉인'] = 3
        g.set_face_down(m)
        self.assertEqual(m.counters, {})

    def test_simultaneous_zero_hp_is_draw(self):
        # 설계도 확정: 양쪽 HP가 동시에 0이면 무승부. 효과 하나의 처리 중에는 판정을 미룬다
        g = make('세제', '세제')
        g.p[0].hp = g.p[1].hp = 100
        def both(): g.damage(0, 500, 't'); g.damage(1, 500, 't')
        with self.assertRaises(GameOver) as cm: g.deferring_hp(both)
        self.assertIsNone(cm.exception.winner)

    def test_single_zero_hp_after_effect(self):
        g = make('세제', '세제')
        g.p[1].hp = 100
        with self.assertRaises(GameOver) as cm: g.deferring_hp(lambda: g.damage(1, 500, 't'))
        self.assertEqual(cm.exception.winner, 0)

    def test_attack_target_vanished_can_attack_again(self):
        # 설계도 확정: 응답으로 대상이 사라지면 공격하지 않은 것으로 보아 다시 공격 선언할 수 있다
        g = make('세제', '세제'); g.phase = '전투'
        a = on_field(g, '솔루나 시엘', 0)
        t = on_field(g, '세리 - 릭토르', 1)
        orig = g.after_action
        def vanish(actor):
            g.after_action = orig; g.to_deck(t, ('rule', None))
        g.after_action = vanish
        g.attack(a, t)
        self.assertEqual(a.attacks_made, 0)

    def test_shared_zone_control_change_moves_to_monster_zone(self):
        # 설계도 확정: 공유 존의 몬스터 컨트롤이 넘어가면 마커는 그대로, 새 컨트롤러의 몬스터 존으로 옮긴다
        g = make('세제', '세제')
        m = card(g, '세리 - 릭토르', 1, None)
        g.shareds[0] = m; m.zone = 'shared'; m.controller = 1; g.shared_owners[0] = 1
        self.assertTrue(g.change_control(m, 0))
        self.assertEqual((m.zone, m.controller, g.shared_owners[0]), ('m', 0, 1))
        self.assertIsNone(g.shareds[0])

    def test_control_change_needs_free_monster_zone(self):
        g = make('세제', '세제')
        for _ in range(5): on_field(g, '세리 - 엑삭토르', 0)
        m = on_field(g, '세리 - 릭토르', 1)
        self.assertFalse(g.can_change_control(m, 0))

    def test_one_empty_deck_is_not_deckout(self):
        # 정본 4 b: 메인 덱과 상급 덱이 모두 떨어졌을 때만 패배
        g = make('세제', '세제')
        g.p[0].main.clear()
        g.draw(0, 1, 'main')                                  # 지정한 덱이 비어 뽑지 못할 뿐
        g.p[0].upper.clear()
        with self.assertRaises(GameOver): g.draw(0, 1)


class GrantedEffectOptTest(unittest.TestCase):
    def test_granted_effect_counts_per_card(self):
        # 사용자 답변: 효과를 받아 얻은 효과는 얻을 때마다 별개의 사용 횟수 (같은 이름 2장이 각각 받아도 각각 1번)
        g = make('세제', '세제')
        a = on_field(g, '격투가 라이온하트', 0); b = on_field(g, '격투가 라이온하트', 0)
        from cards2 import cer_effect
        ea = cer_effect(1); eb = cer_effect(1)
        self.assertNotEqual(g.opt_key(a, ea), g.opt_key(b, eb))
        g.p[0].opt[g.opt_key(a, ea)] = 1
        self.assertFalse(g.opt_ok(0, a, ea)); self.assertTrue(g.opt_ok(0, b, eb))


class SequencingTest(unittest.TestCase):
    def test_chucky_no_damage_without_destroy(self):
        # 사용자 답변: 앞 효과(파괴)를 처리해야 뒤 효과(300 대미지)도 처리
        g = make('희생제', '세제')
        ch = on_field(g, '저주인형 - 처키', 0)
        t = on_field(g, '세리 - 릭토르', 1)
        e = eff(ch, 1)
        from engine import Link
        l = Link(ch, e, 0, {'t': t}); g.to_deck(t, ('rule', None))
        hp = g.p[1].hp
        e.res(g, ch, 0, l)
        self.assertEqual(g.p[1].hp, hp)

    def test_eclipse_does_nothing_when_short(self):
        # 사용자 답변: 월식 처리 때 봉인 카운터가 5개 미만이면 아무것도 하지 않는다
        g = make('호박옥 - 몽식의 계약', '세제')
        amb = on_field(g, '호박옥의 수호자 - 레시나', 0); amb.counters = {'봉인': 3}
        opp = on_field(g, '세리 - 릭토르', 1)
        ec = card(g, '월식', 0, 'hand')
        from engine import Link
        e = eff(ec, 1); e.res(g, ec, 0, Link(ec, e, 0, {}))
        self.assertTrue(opp.faceup); self.assertEqual(amb.counters.get('봉인'), 3)


class MatchRulingTest(unittest.TestCase):
    def test_match_is_at_most_three_rounds_and_draw_round_scores_nothing(self):
        # 설계도 확정: 라운드 수 3 고정, 무승부 라운드는 승점 없음 → 매치 무승부 가능
        from engine import Game
        orig = Game.run
        Game.run = lambda self: (self.setup(), (None, '양쪽 HP 동시 0 — 무승부'))[1]
        try:
            mw, rounds = M.play_match(dict(make('세제', '세제').decks[0]), dict(make('세제', '세제').decks[1]), 0, random.Random(1), [],
                                      lambda d: Idle(d['스킬']), side=False, learn_side=False)
        finally:
            Game.run = orig
        self.assertEqual(len(rounds), 3)
        self.assertIsNone(mw)
        self.assertTrue(all(r['chooser'] in (None, 0, 1) for r in rounds))


class DuplicatorTest(unittest.TestCase):
    """세리 - 두플리카토르: 서로의 카드 코스트 매수 2배 (재정 정리 2026-10-17, 정본 3-6 f)"""
    def test_self_only_cost_not_doubled(self):
        # 룰지 f 개정(사용자 지시 2026-10-25): 코스트가 「이 카드」만이면 2배가 되지 않는다
        g = make('던전마스터 셔플!', '세제')
        on_field(g, '세리 - 두플리카토르', 1)
        sac = card(g, '던전마스터 새크리파이스', 0, 'hand')
        other = card(g, '던전마스터 망령', 0, 'hand')
        g.p[0].hand[:] = [sac]                                  # 패에 이 카드뿐이어도 발동할 수 있다
        self.assertTrue(g.legal(0, sac, eff(sac, 1)))
        g.p[0].hand.append(other)
        g.activate(0, sac, eff(sac, 1))
        self.assertEqual((sac.zone, other.zone), ('grave', 'hand'))

    def test_counted_cost_doubles(self):
        g = make('데이터버그 패키지 프로그램', '세제')
        on_field(g, '세리 - 두플리카토르', 1)
        evo = on_field(g, '데이터버그 에볼루션 마스터', 0)
        ms = [on_field(g, '데이터버그 리틀버그', 0) for _ in range(2)]
        self.assertFalse(g.legal(0, evo, eff(evo, 1)))          # 2장 → 4장 필요 (에볼루션 자신 포함 3장뿐)
        ms.append(on_field(g, '데이터버그 리틀버그', 0))
        self.assertTrue(g.legal(0, evo, eff(evo, 1)))
        g.activate(0, evo, eff(evo, 1))
        self.assertEqual(len(g.monsters(0)), 0)

    def test_no_duplicator_no_change(self):
        g = make('던전마스터 셔플!', '세제')
        sac = card(g, '던전마스터 새크리파이스', 0, 'hand'); g.p[0].hand[:] = [sac]
        self.assertTrue(g.legal(0, sac, eff(sac, 1)))


if __name__ == '__main__':
    unittest.main()

"""디스코드 '?' 작업 요청(2026-11-03, jdiejd7788/세창): 「스킬 카드에 카드의 위치 이동을 유발하는 효과를 발동할 수 없게」.
cards.removal_text의 「이동 동사(파괴 · 제외 · 묘지로 · 패 · 덱으로)」 정의 그대로 — engine의 5개 위치 이동 동작
(destroy · banish · send_grave · to_hand · to_deck) 모두 스킬 카드(zone == 'skill')를 그대로 두는지 확인.
python -m unittest test_skill_no_move -v (nny_sim 폴더에서)"""
import unittest
from test_new_mechanics import make


class SkillCardStaysPutTest(unittest.TestCase):
    def setUp(self):
        self.g = make('세제', '투기장의 규칙')
        self.sk = self.g.p[0].skill
        self.assertEqual(self.sk.zone, 'skill')

    def test_destroy_is_noop(self):
        self.assertFalse(self.g.destroy(self.sk))
        self.assertEqual(self.sk.zone, 'skill')
        self.assertIs(self.g.p[0].skill, self.sk)
        self.assertNotIn(self.sk, self.g.p[0].grave)

    def test_send_grave_is_noop(self):
        self.g.send_grave(self.sk)
        self.assertEqual(self.sk.zone, 'skill')
        self.assertIs(self.g.p[0].skill, self.sk)
        self.assertNotIn(self.sk, self.g.p[0].grave)

    def test_to_hand_is_noop(self):
        self.g.to_hand(self.sk)
        self.assertEqual(self.sk.zone, 'skill')
        self.assertIs(self.g.p[0].skill, self.sk)
        self.assertNotIn(self.sk, self.g.p[0].hand)

    def test_to_deck_is_noop(self):
        before_main, before_upper = len(self.g.p[0].main), len(self.g.p[0].upper)
        self.g.to_deck(self.sk)
        self.assertEqual(self.sk.zone, 'skill')
        self.assertIs(self.g.p[0].skill, self.sk)
        self.assertEqual(len(self.g.p[0].main), before_main)
        self.assertEqual(len(self.g.p[0].upper), before_upper)

    def test_banish_is_noop(self):
        self.g.banish(self.sk)
        self.assertEqual(self.sk.zone, 'skill')
        self.assertIs(self.g.p[0].skill, self.sk)
        self.assertNotIn(self.sk, self.g.p[0].banish)


if __name__ == '__main__':
    unittest.main()

"""사용자 지시(2026-10-30) 테스트 (nny_sim 폴더에서):  python -m unittest test_play_fixes_1030 -v
① 대상을 지정하지 않는 코스트는 효과 내성을 보지 않는다 — 기적의 영웅(「다른 카드의 효과를 받지 않는다」)을 행운의 도적 1번 코스트로 묘지로
② 체인 처리 뒤에도 우선권을 다시 연다 — 횟수 제한이 없는 [신속](기적의 영웅 3번)을 체인 처리 뒤에 또 쓸 수 있다"""
import unittest
import blocks.lib as L
from test_new_mechanics import make, card, on_field, eff, Idle


class CostIgnoresImmunityTest(unittest.TestCase):
    def setUp(self):
        self.g = g = make('소원의 분수', '세제')
        self.thief = on_field(g, '행운의 도적', 0); self.hero = on_field(g, '기적의 영웅', 0)

    def test_pool_keeps_immune_card_only_for_cost(self):
        g = self.g; own = {'side': 'own', 'zone': 'field'}
        self.assertNotIn(self.hero, L.pick_pool(g, self.thief, 0, own))                 # 효과(처리)로는 고를 수 없다
        self.assertIn(self.hero, L.pick_pool(g, self.thief, 0, own, cost=True))         # 코스트로는 고를 수 있다

    def test_thief_cost_sends_hero_to_grave_and_draws_two(self):
        g = self.g; hand0 = len(g.p[0].hand)
        orig_w, orig_p = L.wants_cost, L.pick_cards
        L.wants_cost = lambda *a: True
        L.pick_cards = lambda g_, c, p, pool, n, k: [self.hero] if self.hero in pool else orig_p(g_, c, p, pool, n, k)
        try:
            self.assertTrue(g.act(0, self.thief, eff(self.thief, 1)))
        finally:
            L.wants_cost, L.pick_cards = orig_w, orig_p
        self.assertEqual(self.hero.zone, 'grave')
        self.assertEqual(len(g.p[0].hand), hand0 + 2)


class QuickAfterChainTest(unittest.TestCase):
    def test_quick_effect_can_be_used_again_after_chain_resolves(self):
        class HeroUser(Idle):
            """빈 체인에서 우선권을 받을 때마다 기적의 영웅 3번을 쓴다"""
            def respond(self, g, p, opts):
                return next(((c, e) for c, e in opts if c.name == '기적의 영웅' and e.num == 3 and not g.chain), None)
        g = make('세제', '소원의 분수', ai=HeroUser)
        hero = on_field(g, '기적의 영웅', 1)
        targets = [on_field(g, n, 0) for n in ('격투가 래빗 풋', '격투가 래빗 풋', '격투가 래빗 풋')]
        g.priority(0)   # 턴 플레이어(0)가 넘기면 상대(1)가 쓰고, 처리 뒤 다시 열린 우선권에서 또 쓴다
        uses = sum(1 for x in g.log if '「기적의 영웅」 3번 효과 발동' in x.get('m', ''))
        self.assertEqual(uses, 3)                        # 공격력/수비력 3000 → 1000씩 — 0이 되면 더는 발동할 수 없다
        self.assertEqual(g.atk(hero), 0)
        self.assertTrue(all(t.zone == 'grave' for t in targets))


if __name__ == '__main__':
    unittest.main()

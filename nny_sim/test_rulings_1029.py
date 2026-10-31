"""사용자 결정(2026-10-29) 테스트 (nny_sim 폴더에서):  python -m unittest test_rulings_1029 -v
명계의 규율 — 이 카드보다 먼저 발동해 처리를 기다리는 효과 중, 효과를 발동한 카드의 위치가 묘지인 것만 전부 무효(자신 것 포함)"""
import unittest
from engine import Link
from test_new_mechanics import make, card, on_field, eff


class NetherworldRuleTest(unittest.TestCase):
    def setUp(self):
        self.g = g = make('투기장의 규칙', '데이터버그 패키지 프로그램')
        m = on_field(g, '격투가 래빗 풋', 0)
        self.mine = Link(m, eff(m, 1), 0, {'from_zone': 'field'})
        w = card(g, '데이터버그 디지털 웜', 1, 'grave')
        self.grave = Link(w, eff(w, 1), 1, {'from_zone': 'grave'})
        f = on_field(g, '격투가 래빗 풋', 1)
        self.field = Link(f, eff(f, 1), 1, {'from_zone': 'field'})
        self.rule = card(g, '명계의 규율', 0, 'hand')
        self.e = eff(self.rule, 1)

    def test_negates_only_earlier_effects_activated_in_grave(self):
        g = self.g
        mg = card(g, '데이터버그 디지털 웜', 0, 'grave')
        mine_grave = Link(mg, eff(mg, 1), 0, {'from_zone': 'grave'})   # 자신이 묘지에서 발동한 효과도 무효
        g.chain[:] = [self.mine, mine_grave, self.grave, self.field]
        l = Link(self.rule, self.e, 0, {}); g.chain.append(l)
        self.e.res(g, self.rule, 0, l)
        self.assertTrue(mine_grave.negated and self.grave.negated)
        self.assertFalse(self.mine.negated or self.field.negated)       # 필드에서 발동한 효과는 그대로
        g.chain.clear()

    def test_later_effects_are_not_negated(self):
        g = self.g
        l = Link(self.rule, self.e, 0, {})
        g.chain[:] = [self.grave, l, self.field]
        self.e.res(g, self.rule, 0, l)
        self.assertTrue(self.grave.negated)
        self.assertFalse(self.field.negated)
        g.chain.clear()


if __name__ == '__main__':
    unittest.main()

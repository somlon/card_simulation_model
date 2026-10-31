"""소원의 분수(WSFT) 「자신의 효과를 발동하기 위해 묘지로 보내졌을 경우」(not_cost) 재현·회귀 테스트
(디스코드 soltop_ 제보 — 행운의 카드 - 조커 · 용기의 무기 - 검: 1번 효과를 정상적으로 사용해 처리가 끝나고
§8-2 규칙으로 묘지에 가도 [유언](2번)이 발동해 버리는 문제. 실행: python -m unittest test_wsft_lastwill_self_resolve -v"""
import unittest
from test_new_mechanics import make, card, eff


class LastwillNotCostSelfResolveTest(unittest.TestCase):
    def _activate_and_grave_event(self, name):
        g = make('소원의 분수', '세제')
        j = card(g, name, 0, 'hand')
        card(g, '행운의 도박사', 0, 'grave')   # recycle_lw가 함께 되돌릴 「행운」 카드 — 유언 발동 조건을 채워 둔다
        g.events = []
        g.activate(0, j, eff(j, 1))
        g.resolve_chain()
        ev = next(e for e in g.cur_evs if e.get('card') is j and e.get('kind') == 'to_grave')
        return g, j, ev

    def test_joker_lastwill_not_triggered_by_its_own_normal_resolve(self):
        g, j, ev = self._activate_and_grave_event('행운의 카드 - 조커')
        self.assertEqual(ev['cause'][0], 'self_resolve')
        self.assertFalse(g.legal(0, j, eff(j, 2), ev))

    def test_lastwill_still_triggers_when_sent_by_a_different_card(self):
        # not_cost 단서는 "이 카드 자신의 발동" 때문에 묘지로 간 경우만 막는다 — 다른 카드가 보낸 경우는 그대로 발동
        g = make('소원의 분수', '세제')
        j = card(g, '행운의 카드 - 조커', 0, 'field')
        other = card(g, '행운의 도박사', 0, 'grave')
        g.events = []
        g.send_grave(j, ('effect', other))
        ev = next(e for e in g.events if e.get('card') is j and e.get('kind') == 'to_grave')
        self.assertTrue(g.legal(0, j, eff(j, 2), ev))


if __name__ == '__main__':
    unittest.main()

"""남은 재정 답변 2차(사용자 2026-10-20, 「재정_질문_남은것_2026-10-19.pdf」 Q6 ~ Q10) 테스트 (nny_sim 폴더에서):  python -m unittest test_rulings_1020b -v
Q8 솔루나 아츠 1번 — 제외 존 복귀 · 컨트롤 획득도 막고, 돌아올 자리가 없으면 제외 존에 남는다 /
Q10 소원의 분수 [유언] 단서 「자신의 효과를 발동하기 위해」의 「자신」 = 이 카드
(Q6 격투가 1 · Q7 데이터버그 4는 현행 유지 — 기존 테스트)"""
import unittest
from test_new_mechanics import make, card, on_field, eff


def banished(g, name, owner):
    c = card(g, name, owner, 'banish'); c.faceup = True
    c.flags['return_from_banish'] = g.turn + 1   # play_turn이 턴을 하나 올린 뒤 그 턴 종료 시에 복귀
    return c


# ═══════════════════════ Q8 솔루나 아츠 1번 — 시아 · 시엘 각 1장 ═══════════════════════
class SolunaFieldLimitTest(unittest.TestCase):
    def test_banished_ciel_stays_when_ciel_on_field(self):
        g = make('솔루나 아츠', '소원의 분수')
        on_field(g, '솔루나 시엘', 0)
        b = banished(g, '솔루나 시엘', 0)
        n = len(g.log); g.play_turn()
        self.assertEqual(b.zone, 'banish'); self.assertIn(b, g.p[0].banish)
        self.assertEqual(sum(1 for m in g.monsters(0) if m.name == '솔루나 시엘'), 1)
        self.assertTrue(any('제외 존에 남음' in e['m'] for e in g.log[n:]))

    def test_banished_ciel_returns_when_allowed(self):
        g = make('솔루나 아츠', '소원의 분수')
        b = banished(g, '솔루나 시엘', 0)
        g.play_turn()
        self.assertEqual(b.zone, 'm')

    def test_no_room_stays_banished(self):
        # 돌아올 자리가 없으면 그대로 제외 존에 남는다 (예전: 묘지로)
        g = make('솔루나 아츠', '소원의 분수')
        for _ in range(5): on_field(g, '솔루나 시아 - 코로나 이그니스', 0)
        x = card(g, '솔루나 시아', 1, None); g.shared = x; x.zone = 'shared'; x.controller = 1
        b = banished(g, '솔루나 시엘', 0)
        n = len(g.log); g.play_turn()
        self.assertEqual(b.zone, 'banish'); self.assertNotIn(b, g.p[0].grave)
        self.assertTrue(any('제외 존에 남음' in e['m'] for e in g.log[n:]))

    def test_control_gain_blocked(self):
        g = make('솔루나 아츠', '솔루나 아츠')
        on_field(g, '솔루나 시엘', 0)
        t = on_field(g, '솔루나 시엘', 1)
        self.assertTrue(g.field_limited(t, 0))
        self.assertFalse(g.can_change_control(t, 0))
        self.assertFalse(g.change_control(t, 0))
        self.assertEqual(t.controller, 1)
        s = on_field(g, '솔루나 시아', 1)
        self.assertTrue(g.can_change_control(s, 0))       # 시아는 자신 필드에 없으므로 옮길 수 있다

    def test_summon_limit_unchanged(self):
        g = make('솔루나 아츠', '소원의 분수')
        on_field(g, '솔루나 시아', 0)
        h = card(g, '솔루나 시아', 0, 'hand')
        self.assertFalse(g.can_special(h, 0))


# ═══════════════════════ Q10 소원의 분수 — 「자신」 = 이 카드 ═══════════════════════
class WishSelfCostClauseTest(unittest.TestCase):
    def _setup(self):
        g = make('소원의 분수', '세제')
        c = card(g, '지혜의 원천 - 마도서', 0, 'grave')
        card(g, '지혜의 원천 - 마도서', 0, 'grave')                 # 함께 되돌릴 「지혜」 카드
        return g, c, eff(c, 2)

    def test_own_cost_does_not_trigger(self):
        g, c, e = self._setup()
        ev = {'kind': 'to_grave', 'card': c, 'prev': 's', 'cause': ('cost', c)}
        self.assertFalse(e.cond(g, c, 0, ev))                         # 이 카드의 효과를 발동하기 위해 묘지로

    def test_other_card_cost_triggers(self):
        g, c, e = self._setup()
        other = on_field(g, '희생의 성녀', 0)
        ev = {'kind': 'to_grave', 'card': c, 'prev': 's', 'cause': ('cost', other)}
        self.assertTrue(e.cond(g, c, 0, ev))                          # 다른 자신 카드의 코스트로 묘지로 — 발동한다 (예전: 발동하지 않음)

    def test_effect_destroy_triggers(self):
        g, c, e = self._setup()
        ev = {'kind': 'to_grave', 'card': c, 'prev': 's', 'cause': ('effect', None)}
        self.assertTrue(e.cond(g, c, 0, ev))


if __name__ == '__main__':
    unittest.main()

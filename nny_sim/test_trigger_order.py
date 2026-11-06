"""같은 타이밍 효과의 체인 순서(사용자 지시 2026-10-30) — policy.LearnedAI.order_triggers · ai.HeuristicAI.order_triggers (nny_sim 폴더에서):
python -m unittest test_trigger_order -v"""
import random, unittest
from types import SimpleNamespace as NS
import policy as P
from ai import HeuristicAI
from test_table import empty


def fake_game():
    pl = lambda s: NS(skill=NS(name=s), hp=8000, hand=[])
    g = NS(p=[pl('A'), pl('B')], turn=3, turn_player=0, rng=random.Random(1), log=[], dlog=[])
    g.field_cards = lambda p: []; g.monsters = lambda p: []; g.pname = lambda p: f'P{p}'
    g.L = lambda m, k='': g.log.append({'m': m, 'k': k})
    return g


def items(*names):
    """[(점수, 카드, 효과, 사건)] — 점수가 높은 것부터(휴리스틱 순서) 주지 않고 섞어서"""
    return [(s, NS(name=n), NS(num=1), {}) for s, n in names]


class TriggerOrderTest(unittest.TestCase):
    def test_heuristic_orders_by_score(self):
        out = HeuristicAI('A').order_triggers(fake_game(), 0, items((1, 'x'), (9, 'y'), (5, 'z')))
        self.assertEqual([c.name for _, c, _, _ in out], ['y', 'z', 'x'])

    def test_learned_without_data_keeps_heuristic_order(self):
        ai = P.LearnedAI('A', learn=False, table=empty())
        out = ai.order_triggers(fake_game(), 0, items((1, 'x'), (9, 'y'), (5, 'z')))
        self.assertEqual([c.name for _, c, _, _ in out], ['y', 'z', 'x'])

    def test_learned_follows_table_and_records_keys(self):
        t = empty(); key = f'A vs B|{P.LearnedAI.ORDER_DECISION}|x#1'
        for _ in range(300): t.update(key, key + '|x', 1)   # 「x 를 먼저 선언」이 늘 이겼다(L0 · L1 로 상황 무관)
        ai = P.LearnedAI('A', learn=True, table=t)
        g = fake_game(); out = ai.order_triggers(g, 0, items((1, 'x'), (9, 'y'), (5, 'z')))
        self.assertEqual(out[0][1].name, 'x')
        self.assertTrue(all(P.LearnedAI.ORDER_DECISION in k1 for k1, _ in ai.trace) and len(ai.trace) == 2)
        ai.end_game(g, 0, 0)   # 이긴 판: 고른 순서가 학습표에 더해진다
        self.assertEqual(t.L1[key][1], 301)

    def test_single_or_switched_off(self):
        ai = P.LearnedAI('A', learn=True, table=empty())
        self.assertEqual(len(ai.order_triggers(fake_game(), 0, items((1, 'x')))), 1)
        self.assertEqual(ai.trace, [])


if __name__ == '__main__':
    unittest.main()

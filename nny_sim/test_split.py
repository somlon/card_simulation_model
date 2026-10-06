"""시작 패 배분 · 멀리건 재배분 판단 테스트 (nny_sim 폴더에서):  python -m unittest test_split -v"""
import random, unittest
import season as SE
import policy as P
from ai import HeuristicAI
from cards import Impl
from engine import Game

DECKS = SE.load_decks()


def game(a, b, ais, first=0, seed=3):
    return Game([dict(DECKS[a], 이름='A'), dict(DECKS[b], 이름='B')], ais, first, random.Random(seed), [], Impl)


class Capture:
    """LearnedAI.choose 호출을 가로채 판단 이름 · 후보를 기록한다"""
    def __enter__(self):
        self.calls = []; self.orig = P.LearnedAI.choose
        def choose(ai, g, p, decision, opts, *a, **k):
            self.calls.append((p, decision, [lab for lab, _, _ in opts]))
            return self.orig(ai, g, p, decision, opts, *a, **k)
        P.LearnedAI.choose = choose
        return self

    def __exit__(self, *exc):
        P.LearnedAI.choose = self.orig


class EmptyTable:
    def __enter__(self):
        self.orig = P.POLICY
        t = P.Table.__new__(P.Table); t.path = '/dev/null'; t.L1 = {}; t.L2 = {}; t.games = 0
        P.POLICY = t
        return t

    def __exit__(self, *exc):
        P.POLICY = self.orig


def learned(name, **kw):
    return P.LearnedAI(DECKS[name]['스킬'], learn=kw.pop('learn', False), **kw)


class OpeningSplitTest(unittest.TestCase):
    def test_every_legal_split_is_a_candidate_keyed_by_matchup_and_turn_order(self):
        a, b = '투기장의 규칙', '세제'
        with Capture() as cap:
            g = game(a, b, [learned(a), learned(b)], first=1); g.setup()
        splits = [(p, d, labs) for p, d, labs in cap.calls if d.startswith('시작 패 배분')]
        self.assertEqual([(p, d) for p, d, _ in splits], [(0, '시작 패 배분(후공)'), (1, '시작 패 배분(선공)')])
        self.assertEqual(splits[0][2], [f'메인 {k}' for k in range(0, 6)])

    def test_learned_values_decide_the_split(self):
        a, b = '투기장의 규칙', '세제'
        with EmptyTable() as t:
            me, op = DECKS[a]['스킬'], DECKS[b]['스킬']
            t.L1[f'{me} vs {op}|시작 패 배분(선공)|메인 2'] = [900, 1000]   # 메인 2 / 상급 3의 승률이 압도적
            g = game(a, b, [learned(a), learned(b)], first=0); g.setup()
        line = next(e['m'] for e in g.log if e['m'].startswith('A 시작 패'))
        self.assertIn('메인 2 / 상급 3', line)

    def test_default_prior_reproduces_the_fixed_table_when_there_is_no_data(self):
        a, b = '솔루나 아츠', '세제'
        with EmptyTable():
            g = game(a, b, [learned(a), learned(b)], first=0); g.setup()
        k0, _ = HeuristicAI(DECKS[a]['스킬']).split_default(g, 0, 5)
        line = next(e['m'] for e in g.log if e['m'].startswith('A 시작 패'))
        self.assertIn(f'메인 {k0} / 상급 {5 - k0}', line)

    def test_split_learning_can_be_switched_off(self):
        a, b = '투기장의 규칙', '세제'
        ai = learned(a); ai.LEARN_SPLIT = False
        with Capture() as cap:
            g = game(a, b, [ai, learned(b)]); g.setup()
        self.assertFalse(any(p == 0 and d.startswith('시작 패') for p, d, _ in cap.calls))

    def test_thompson_exploration_only_while_learning(self):
        a, b = '투기장의 규칙', '세제'
        def first_split(ai_kw, seed):
            with EmptyTable():
                g = game(a, b, [learned(a, **ai_kw), learned(b)], seed=seed); g.setup()
            return next(e['m'] for e in g.log if e['m'].startswith('A 시작 패')).split('(')[1].split(')')[0]
        greedy = {first_split({}, s) for s in range(12)}
        explore = {first_split({'learn': True, 'eps': 0.1}, s) for s in range(12)}
        self.assertEqual(len(greedy), 1)
        self.assertGreater(len(explore), 1)


class MulliganSplitTest(unittest.TestCase):
    def test_redraw_can_change_the_main_upper_ratio(self):
        """멀리건으로 되돌린 메인 카드를 상급 덱에서 다시 뽑을 수 있다 (§4 STEP 6)"""
        a, b = '솔루나 아츠', '세제'

        class AllBackToUpper(HeuristicAI):
            def choose_split(self, g, p, n): return n                   # 메인 5
            def mulligan(self, g, p, hand): return list(hand)           # 전부 되돌림
            def mulligan_split(self, g, p, back): return 0              # 전부 상급에서

        g = game(a, b, [AllBackToUpper(DECKS[a]['스킬']), HeuristicAI(DECKS[b]['스킬'])]); g.setup()
        self.assertTrue(all(c.deck_kind() == '상급' for c in g.p[0].hand))
        self.assertEqual(len(g.p[0].hand), 5)

    def test_learned_redraw_split_candidates_cover_the_legal_range(self):
        a, b = '솔루나 아츠', '세제'

        class BackTwo(P.LearnedAI):
            def mulligan(self, g, p, hand): return [c for c in hand if c.deck_kind() == '메인'][:2]

        with Capture() as cap:
            g = game(a, b, [BackTwo(DECKS[a]['스킬'], learn=False), learned(b)]); g.setup()
        re = [(d, labs) for p, d, labs in cap.calls if p == 0 and d.startswith('시작 패 재배분')]
        self.assertEqual(len(re), 1)
        self.assertTrue(re[0][0].startswith('시작 패 재배분(선공·2장·남은 상급'))
        self.assertEqual(re[0][1], ['메인 0', '메인 1', '메인 2'])

    def test_heuristic_redraw_keeps_the_returned_ratio(self):
        a, b = '솔루나 아츠', '세제'
        g = game(a, b, [HeuristicAI(DECKS[a]['스킬']), HeuristicAI(DECKS[b]['스킬'])]); g.setup()
        back = g.p[0].hand[:3]
        self.assertEqual(g.p[0].ai.mulligan_split(g, 0, back), sum(1 for c in back if c.deck_kind() == '메인'))


if __name__ == '__main__':
    unittest.main()

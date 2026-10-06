"""2 · 3라운드 선후공 학습 테스트 (nny_sim 폴더에서):  python -m unittest test_first_choice -v"""
import random, unittest
import season as SE
import policy as P
import match as M
from ai import HeuristicAI

DECKS = SE.load_decks()
A, B = '투기장의 규칙', '세제'


class EmptyTable:
    def __enter__(self):
        self.orig = P.POLICY
        t = P.Table.__new__(P.Table); t.path = '/dev/null'; t.L0 = {}; t.L1 = {}; t.L2 = {}; t.games = 0
        P.POLICY = t
        return t

    def __exit__(self, *exc):
        P.POLICY = self.orig


class NoSide:
    """전략 덱 교체 학습표(SIDE)를 건드리지 않게 비운다"""
    def __enter__(self):
        self.orig = M.SIDE
        t = P.Table.__new__(P.Table); t.path = '/dev/null'; t.L0 = {}; t.L1 = {}; t.L2 = {}; t.games = 0
        M.SIDE = t

    def __exit__(self, *exc):
        M.SIDE = self.orig


def skill(name): return DECKS[name]['스킬']


class ChooseFirstTest(unittest.TestCase):
    def test_without_data_follows_the_deck_guideline(self):
        with EmptyTable():
            ai = P.LearnedAI(skill(A), learn=False)
            self.assertEqual(ai.choose_first(skill(A), skill(B), 2, random.Random(1)), HeuristicAI(skill(A)).wants_first(skill(B)))

    def test_learned_values_decide_per_matchup_and_round(self):
        with EmptyTable() as t:
            t.L1[f'{skill(A)} vs {skill(B)}|선후공 선택(2라운드)|후공'] = [700, 1000]
            t.L1[f'{skill(A)} vs {skill(B)}|선후공 선택(2라운드)|선공'] = [400, 1000]
            ai = P.LearnedAI(skill(A), learn=False)
            self.assertFalse(ai.choose_first(skill(A), skill(B), 2, random.Random(1)))
            self.assertTrue(ai.choose_first(skill(A), skill(B), 3, random.Random(1)))     # 3라운드는 따로 배운다
            self.assertTrue(ai.choose_first(skill(A), skill(A), 2, random.Random(1)))     # 상대가 다르면 따로 배운다

    def test_evaluation_does_not_consume_match_randomness(self):
        with EmptyTable():
            r = random.Random(5); before = r.getstate()
            P.LearnedAI(skill(A), learn=False).choose_first(skill(A), skill(B), 2, r)
            self.assertEqual(r.getstate(), before)

    def test_thompson_explores_both_options_while_learning(self):
        with EmptyTable():
            picks = {P.LearnedAI(skill(A), learn=True, eps=0.1).choose_first(skill(A), skill(B), 2, random.Random(s)) for s in range(20)}
        self.assertEqual(picks, {True, False})

    def test_switch_off_restores_guideline(self):
        with EmptyTable() as t:
            t.L1[f'{skill(A)} vs {skill(B)}|선후공 선택(2라운드)|후공'] = [900, 1000]
            ai = P.LearnedAI(skill(A), learn=False); ai.LEARN_FIRST = False
            self.assertEqual(ai.choose_first(skill(A), skill(B), 2, random.Random(1)), ai.wants_first(skill(B)))


class MatchCreditTest(unittest.TestCase):
    def test_choice_is_credited_with_the_round_it_started(self):
        with EmptyTable() as t, NoSide():
            for seed in range(6):
                t.L1.clear(); t.L2.clear()
                log = []
                mw, rounds = M.play_match(dict(DECKS[A]), dict(DECKS[B]), seed % 2, random.Random(seed), log,
                                          lambda d: P.LearnedAI(d['스킬'], learn=True), side=True, learn_side=False)
                keys = {k: v for k, v in t.L1.items() if '|선후공 선택(' in k}
                expected = {}
                for r in range(1, len(rounds)):
                    loser = 1 - rounds[r - 1]['winner']
                    me, op = [skill(A), skill(B)][loser], [skill(A), skill(B)][1 - loser]
                    lab = '선공' if rounds[r]['first'] == loser else '후공'
                    k = f'{me} vs {op}|선후공 선택({r + 1}라운드)|{lab}'
                    w, n = expected.get(k, (0, 0)); expected[k] = (w + int(rounds[r]['winner'] == loser), n + 1)
                self.assertEqual({k: tuple(v) for k, v in keys.items()}, expected)
                decisions = [e for e in log if e['k'] == 'decision' and '라운드 선후공' in e['m']]
                self.assertEqual(len(decisions), len(rounds) - 1)


if __name__ == '__main__':
    unittest.main()

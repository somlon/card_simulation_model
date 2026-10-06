"""레시피 학습기 · 시즌 자동 조정 · 시즌별 재학습 테스트 (nny_sim 폴더에서):  python -m unittest test_recipe -v"""
import json, os, random, tempfile, unittest
import deck_opt as DO
import season as SE
import train_table as TT
from cards import POOL

DECKS = SE.load_decks()


def fake_ev(prefer):
    """평가기 대역: 후보 레시피에 prefer 카드가 많을수록 이긴다(결정적)"""
    def ev(jobs):
        out = []
        for sk, counts, opps, n, seed, strat in jobs:
            k = counts.get(prefer, 0)
            m = n * len(opps) * 2
            out.append([1 if i < m * (0.3 + 0.2 * k) else 0 for i in range(m)])
        return out
    return ev


class NeighborTest(unittest.TestCase):
    def setUp(self):
        self.d = DECKS['세제']; self.st = DO.state_from_deck(self.d)

    def test_add_remove_and_swap_candidates_change_deck_size(self):
        c = DO.neighbors(self.st['skill'], self.st['counts'], self.st['strat'], random.Random(1))
        labs = [lab for lab, _, _ in c]
        self.assertTrue(any(l.startswith('+') for l in labs))          # 매수 증가
        self.assertTrue(any(l.startswith('-') and ' +' not in l for l in labs))   # 매수 감소
        base = DO.sizes(self.st['counts'], self.st['strat'])
        grown = [DO.sizes(cc, s) for lab, cc, s in c if lab.startswith('+')]
        self.assertTrue(all(g['메인'] + g['상급'] == base['메인'] + base['상급'] + 1 for g in grown))

    def test_log_guided_swaps_come_first(self):
        low = sorted(n for n, k in self.st['counts'].items() if k > 0)[0]
        contrib = {n: (0.1 if n == low else 0.6) for n in self.st['counts']}
        c = DO.neighbors(self.st['skill'], self.st['counts'], self.st['strat'], random.Random(1), contrib=contrib, n_out=1)
        swaps = [lab for lab, _, _ in c if lab.startswith('-') and ' +' in lab]
        self.assertTrue(swaps[0].startswith(f'-{low} +'))

    def test_every_candidate_is_legal(self):
        for lab, c, s in DO.neighbors(self.st['skill'], self.st['counts'], self.st['strat'], random.Random(2)):
            self.assertTrue(DO.valid(self.st['skill'], c, s), lab)


class OneRoundTest(unittest.TestCase):
    def test_adopts_a_significantly_better_candidate(self):
        st = DO.state_from_deck(DECKS['세제'])
        names = DO.legal_names(st['skill'])
        prefer = next(n for n in names if st['counts'].get(n, 0) == 0 and POOL[n]['deck'] == '메인')
        opps = [d for k, d in DECKS.items() if k != '세제']
        rec = DO.one_round(st, opps, ev=fake_ev(prefer), n=(1, 2, 20))
        self.assertTrue(rec['accepted'])
        self.assertEqual(st['counts'].get(prefer, 0), 1)
        self.assertEqual(len(st['history']), 1)
        self.assertIn('sizes_after', rec)

    def test_keeps_recipe_when_nothing_is_better(self):
        st = DO.state_from_deck(DECKS['세제']); before = dict(st['counts'])
        opps = [d for k, d in DECKS.items() if k != '세제']
        rec = DO.one_round(st, opps, ev=fake_ev('없는 카드'), n=(1, 2, 20))
        self.assertFalse(rec['accepted'])
        self.assertEqual(st['counts'], before)


class SeasonAdjustTest(unittest.TestCase):
    def test_season_adjust_uses_recipe_learner(self):
        d = DECKS['세제']
        st = DO.state_from_deck(d)
        prefer = next(n for n in DO.legal_names(st['skill']) if st['counts'].get(n, 0) == 0 and POOL[n]['deck'] == '메인')
        log = []
        nd, rec = SE.adjust(d, DECKS, log, ev=fake_ev(prefer), n=(1, 2, 20))
        self.assertEqual(rec['결정'], rec['best'])
        self.assertIn(prefer, dict((n, k) for k, n in nd['메인']))
        self.assertEqual(log, [rec])


class StageTest(unittest.TestCase):
    def test_deck_rows_roundtrip(self):
        rows = TT.deck_rows(DECKS['세제'])
        self.assertEqual(sum(k for k, _ in rows['전략']), 20)
        json.dumps(rows, ensure_ascii=False)


if __name__ == '__main__':
    unittest.main()

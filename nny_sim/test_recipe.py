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

    def test_selection_noise_is_not_adopted_without_confirmation(self):
        """최종 단계에서만 운 좋게 이긴 후보는 새 시드 확인 단계에서 걸러진다"""
        st = DO.state_from_deck(DECKS['세제'])
        opps = [d for k, d in DECKS.items() if k != '세제']
        def ev(jobs):
            out = []
            for sk, counts, o, n, seed, strat in jobs:
                m = n * len(o) * 2
                lucky = counts != st['counts'] and seed % 1000003 == 13     # 최종 단계(seed+13)에서만 후보가 이김
                out.append([1 if (i < m * 0.6 if lucky else i < m * 0.3) else 0 for i in range(m)])
            return out
        rec = DO.one_round(st, opps, ev=ev, n=(1, 2, 20))
        self.assertGreater(rec['z'], 1.96)
        self.assertFalse(rec['accepted'])
        self.assertIsNotNone(rec['confirm'])

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


class UnadjustedOfficialDeckTest(unittest.TestCase):
    """디스코드 요청(세창, 2026-11-04): AI 학습(season.py 자동 조정)이 쌓은 learned/decks/<스킬>.json은
    AI 자신의 학습용 레시피일 뿐 — 사람이 온라인에서 고르는 공식 덱(app/session.py official_decks)의
    레시피는 그걸로 바뀌면 안 된다. load_decks(adjusted=False)와 official_decks가 그 분리를 지키는지 확인."""
    SK = '세제'

    def setUp(self):
        self.path = os.path.join(SE.DECK_DIR, f'{self.SK}.json')
        self.had = os.path.exists(self.path)
        self.orig = open(self.path, encoding='utf-8').read() if self.had else None
        seed = SE.load_decks(adjusted=False)[self.SK]
        fake = dict(seed, 이름=seed['이름'] + ' [자동 조정 — 테스트용 가짜]')
        json.dump(fake, open(self.path, 'w', encoding='utf-8'), ensure_ascii=False)

    def tearDown(self):
        if self.had: open(self.path, 'w', encoding='utf-8').write(self.orig)
        else: os.remove(self.path)

    def test_load_decks_adjusted_false_ignores_training_override(self):
        self.assertIn('자동 조정', SE.load_decks(adjusted=True)[self.SK]['이름'])      # 학습 쪼그 조정판은 그대로 보임
        self.assertNotIn('자동 조정', SE.load_decks(adjusted=False)[self.SK]['이름'])  # 공식(사람용)은 원본 시드

    def test_official_decks_uses_unadjusted_recipe(self):
        import sys
        here = os.path.dirname(os.path.abspath(__file__))
        added = [os.path.join(here, 'app'), os.path.join(here, 'viewer')]
        sys.path[:0] = added
        try:
            import session as APPS
            store = APPS.Store(tempfile.mkdtemp(prefix='nny_officialdeck_'))
            od = store.official_decks()
        finally:
            for p in added: sys.path.remove(p)
        self.assertNotIn('자동 조정', od[f'o:{self.SK}']['이름'])


class StageTest(unittest.TestCase):
    def test_deck_rows_roundtrip(self):
        rows = TT.deck_rows(DECKS['세제'])
        self.assertEqual(sum(k for k, _ in rows['전략']), 20)
        json.dumps(rows, ensure_ascii=False)


if __name__ == '__main__':
    unittest.main()

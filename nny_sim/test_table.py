"""학습표(policy.Table) · 재학습 도구 테스트 (nny_sim 폴더에서):  python -m unittest test_table -v"""
import os, tempfile, unittest
import policy as P
import train_table as TT


def empty():
    t = P.Table.__new__(P.Table); t.path = '/dev/null'; t.L0 = {}; t.L1 = {}; t.L2 = {}; t.games = 0
    return t


class TableTest(unittest.TestCase):
    def test_k0_pools_over_opponents(self):
        self.assertEqual(P.k0_of('세제 vs 데쿠마|진행 행동|발동:소환세#1'), '세제 vs *|진행 행동|발동:소환세#1')
        self.assertIsNone(P.k0_of('키 형식 아님'))

    def test_without_L0_the_estimate_is_unchanged(self):
        t = empty(); t.L1['a vs b|d|x'] = [30, 40]; t.L2['a vs b|d|x|s'] = [3, 5]
        m1 = (30 + P.A * 0.6) / (40 + P.A); v = (3 + P.A * m1) / (5 + P.A)
        self.assertAlmostEqual(t.value('a vs b|d|x', 'a vs b|d|x|s', 0.6)[0], v)

    def test_L0_fills_the_gap_for_an_unseen_opponent(self):
        t = empty()
        for _ in range(200): t.update('a vs b|d|x', 'a vs b|d|x|s', 1)
        v_seen_elsewhere = t.value('a vs c|d|x', 'a vs c|d|x|s', 0.5)[0]
        self.assertGreater(v_seen_elsewhere, 0.75)        # 다른 상대에서 늘 이긴 후보 → 처음 보는 상대에서도 높게
        self.assertEqual(t.L0['a vs *|d|x'], [200, 200])

    def test_rebuild_L0_sums_L1(self):
        t = empty(); t.L1 = {'a vs b|d|x': [1, 2], 'a vs c|d|x': [3, 4], 'b vs a|d|x': [5, 6]}
        t.rebuild_L0()
        self.assertEqual(t.L0, {'a vs *|d|x': [4, 6], 'b vs *|d|x': [5, 6]})

    def test_gzip_roundtrip(self):
        t = empty(); t.update('a vs b|d|x', 'a vs b|d|x|s', 1); t.L1['a vs b|d|y'] = [0.12345, 1.98765]; t.games = 7
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 't.json.gz'); t.save(p); u = P.Table.load(p)
        self.assertEqual(u.L1['a vs b|d|x'], [1, 1]); self.assertEqual(u.L1['a vs b|d|y'], [0.123, 1.988])
        self.assertEqual((u.L0, u.games), (t.L0, 7))

    def test_instance_table_overrides_global(self):
        t = empty(); ai = P.LearnedAI('세제', learn=False, table=t)
        self.assertIs(ai.T, t)
        self.assertIs(P.LearnedAI('세제', learn=False).T, P.POLICY)


class TrainerOpsTest(unittest.TestCase):
    def test_cap_keeps_the_mean(self):
        D = {'k': [300, 400], 'j': [1, 2]}
        TT.cap_counts(D, 100)
        self.assertEqual(D, {'k': [75.0, 100], 'j': [1, 2]})

    def test_decay_and_prune(self):
        D = {'k': [1, 1], 'j': [10, 10]}
        dead = TT.decay(D, 0.5, prune=0.6)
        self.assertEqual((dead, D), (1, {'j': [5.0, 5.0]}))

    def test_merge_updates_all_levels(self):
        t = empty()
        TT.merge_policy(t, {'a vs b|d|x': [2, 3]}, {'a vs b|d|x|s': [2, 3]})
        self.assertEqual((t.L0['a vs *|d|x'], t.L1['a vs b|d|x'], t.L2['a vs b|d|x|s']), ([2, 3], [2, 3], [2, 3]))

    def test_chi2_change_detects_a_shift(self):
        a = {'x': {'win': 500, 'games': 1000}, 'y': {'win': 500, 'games': 1000}}
        b = {'x': {'win': 600, 'games': 1000}, 'y': {'win': 500, 'games': 1000}}
        self.assertGreater(TT.chi2_change(a, a)[2], 0.99)
        self.assertLess(TT.chi2_change(b, a)[2], 0.001)


if __name__ == '__main__':
    unittest.main()

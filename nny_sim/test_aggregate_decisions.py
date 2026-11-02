"""online_analysis/aggregate_decisions.py 스모크: python -m unittest test_aggregate_decisions -v
사람 기보가 아직 없어 AI끼리 돌린 기보 여러 개(seed별)를 모아 집계 파이프라인만 확인한다 —
승/패 판수가 서로 맞물리고, win_rate가 [0,1] 범위에 있는지가 핵심.
"""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, 'viewer'), os.path.join(HERE, 'online_analysis')]
import record as REC
from extract_decisions import extract_decisions
from aggregate_decisions import aggregate


def _rows_for_seeds(seeds):
    rows = []
    for seed in seeds:
        rec = REC.record_match('소원의 분수', '솔루나 아츠', seed=seed, first=seed % 2, ai='table')
        rows.extend(extract_decisions(rec))
    return rows


class AggregateDecisionsTest(unittest.TestCase):
    def test_by_choice_and_common_points_consistent(self):
        rows = _rows_for_seeds([1, 2, 3, 4])
        result = aggregate(rows)
        self.assertIn('by_choice', result)
        self.assertIn('common_points', result)
        self.assertGreater(len(result['by_choice']), 0)
        self.assertGreater(len(result['common_points']), 0)

        for row in result['by_choice']:
            self.assertGreater(row['n'], 0)
            self.assertGreaterEqual(row['wins'], 0)
            self.assertLessEqual(row['wins'], row['n'])
            self.assertGreaterEqual(row['win_rate'], 0.0)
            self.assertLessEqual(row['win_rate'], 1.0)

        choice_total = {(r['decision'], r['pick']): r['n'] for r in result['by_choice']}
        for row in result['common_points']:
            key = (row['decision'], row['pick'])
            self.assertEqual(row['won_n'] + row['lost_n'], row['n'])
            self.assertEqual(row['n'], choice_total[key])
            if row['n']:
                self.assertAlmostEqual(row['won_share'], row['won_n'] / row['n'])

        # by_choice는 판수(n) 내림차순이어야 한다
        ns = [r['n'] for r in result['by_choice']]
        self.assertEqual(ns, sorted(ns, reverse=True))

    def test_rows_without_match_result_excluded(self):
        rows = [
            {'decision': '우선권', 'pick': '패스', 'won_match': None},
            {'decision': '우선권', 'pick': None, 'won_match': True},
        ]
        result = aggregate(rows)
        self.assertEqual(result['by_choice'], [])
        self.assertEqual(result['common_points'], [])

    def test_empty_input(self):
        result = aggregate([])
        self.assertEqual(result, {'by_choice': [], 'common_points': []})


if __name__ == '__main__':
    unittest.main()

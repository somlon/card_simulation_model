"""online_analysis/report_decisions.py 스모크: python -m unittest test_report_decisions -v
AI끼리 돌린 기보로 aggregate() 결과를 만들고, 리포트 문장이 판수(n)를 빠짐없이 담는지,
표본이 적은 조합에 "(표본 적음)" 딱지가 붙는지 확인한다.
"""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, 'viewer'), os.path.join(HERE, 'online_analysis')]
import record as REC
from extract_decisions import extract_decisions
from aggregate_decisions import aggregate
from report_decisions import render_report, render_by_choice, render_common_points


def _aggregate_for_seeds(seeds):
    rows = []
    for seed in seeds:
        rec = REC.record_match('소원의 분수', '솔루나 아츠', seed=seed, first=seed % 2, ai='table')
        rows.extend(extract_decisions(rec))
    return aggregate(rows)


class ReportDecisionsTest(unittest.TestCase):
    def test_report_contains_sample_size_for_every_row(self):
        result = _aggregate_for_seeds([1, 2, 3, 4, 5, 6])
        report = render_report(result)
        self.assertIn('이긴 판에 자주 나온 선택', report)
        self.assertIn('상황별 카드 선택과 승률', report)
        for row in result['by_choice']:
            self.assertIn(f"{row['n']}판 중 {row['wins']}승", report)
        for row in result['common_points']:
            self.assertIn(f"이긴 판 {row['won_n']}회 / 진 판 {row['lost_n']}회", report)

    def test_low_sample_rows_are_flagged(self):
        by_choice = [{'decision': 'd', 'pick': 'p1', 'n': 1, 'wins': 1, 'win_rate': 1.0}]
        lines = render_by_choice(by_choice, min_n=5)
        self.assertIn('표본 적음', lines[0])

    def test_high_sample_rows_not_flagged(self):
        by_choice = [{'decision': 'd', 'pick': 'p1', 'n': 10, 'wins': 5, 'win_rate': 0.5}]
        lines = render_by_choice(by_choice, min_n=5)
        self.assertNotIn('표본 적음', lines[0])

    def test_common_points_low_sample_flagged(self):
        common_points = [{'decision': 'd', 'pick': 'p1', 'n': 2, 'won_n': 2, 'lost_n': 0, 'won_share': 1.0}]
        lines = render_common_points(common_points, min_n=5)
        self.assertIn('표본 적음', lines[0])

    def test_top_limits_rows(self):
        result = _aggregate_for_seeds([1, 2, 3, 4, 5, 6])
        self.assertGreater(len(result['by_choice']), 1)
        lines = render_by_choice(result['by_choice'], top=1)
        self.assertEqual(len(lines), 1)

    def test_empty_result(self):
        report = render_report({'by_choice': [], 'common_points': []})
        self.assertIn('집계할 판단 레코드가 없다', report)


if __name__ == '__main__':
    unittest.main()

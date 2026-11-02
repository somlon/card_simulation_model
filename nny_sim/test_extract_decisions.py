"""online_analysis/extract_decisions.py 스모크: python -m unittest test_extract_decisions -v
사람 기보가 아직 없어 AI끼리 돌린 기보(viewer.record.record_match)로 파이프라인만 확인한다 —
판단 레코드마다 라운드·매치 승패 레이블이 올바르게 붙는지가 핵심.
"""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, 'viewer'), os.path.join(HERE, 'online_analysis')]
import record as REC
from extract_decisions import extract_decisions


class ExtractDecisionsTest(unittest.TestCase):
    def test_labels_match_round_and_match_result(self):
        rec = REC.record_match('소원의 분수', '솔루나 아츠', seed=1, first=0, ai='table')
        rows = extract_decisions(rec)
        self.assertGreater(len(rows), 0, '판단이 하나도 안 뽑힘 — 기보 구조가 바뀌었는지 확인')

        rounds_meta = rec['meta']['rounds']
        match_winner = rec['meta']['winner']
        for row in rows:
            self.assertIn(row['player'], (0, 1))
            self.assertIsInstance(row['opts'], list)
            self.assertIsNotNone(row['state'], f"판단에 상태 스냅숏이 없음: {row['decision']}")
            self.assertIn('hp', row['state'])

            rr = rounds_meta[row['round'] - 1] if 0 < row['round'] <= len(rounds_meta) else None
            self.assertEqual(row['round_result'], rr)
            if rr is not None and rr.get('winner') is not None:
                self.assertEqual(row['won_round'], rr['winner'] == row['player'])
            if match_winner is not None:
                self.assertEqual(row['won_match'], match_winner == row['player'])

        # 적어도 하나는 승자가 가려진 매치여야 레이블 검증에 의미가 있다
        self.assertIsNotNone(match_winner, '시드 1 매치가 판정 없이 끝남 — 다른 시드로 바꿔야 함')
        self.assertTrue(any(row['won_match'] is True for row in rows))
        self.assertTrue(any(row['won_match'] is False for row in rows))

    def test_non_decision_frames_ignored(self):
        rec = REC.record_match('소원의 분수', '솔루나 아츠', seed=1, first=0, ai='table')
        rows = extract_decisions(rec)
        kinds = {fr['k'] for fr in rec['frames']}
        self.assertIn('decision', kinds)
        self.assertTrue(all(row.get('decision') for row in rows))


if __name__ == '__main__':
    unittest.main()

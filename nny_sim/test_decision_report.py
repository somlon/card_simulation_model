"""app/session.Store.decision_report() 스모크: python -m unittest test_decision_report -v
서버 엔드포인트(/api/analysis/decisions)가 결국 호출하는 Store 메서드가 online_analysis
파이프라인(extract→aggregate→report)을 재생 기록 저장소에 실제로 연결하는지 확인한다.
기보가 0건일 때는 "집계할 판단 레코드가 없다" 한 줄, 쌓이면 판수(n)를 담은 리포트를 낸다.
"""
import os, sys, tempfile, shutil, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app'), os.path.join(HERE, 'viewer')]
import session as SESS
import record as REC


class DecisionReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_decision_report_')
        self.store = SESS.Store(os.path.join(self.tmp, 'user'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_replays_yet(self):
        self.assertIn('없다', self.store.decision_report())

    def test_report_after_replays_saved(self):
        for seed in (1, 2, 3, 4, 5, 6):
            rec = REC.record_match('소원의 분수', '솔루나 아츠', seed=seed, first=seed % 2, ai='table')
            self.store.save_replay(rec)
        report = self.store.decision_report()
        self.assertIn('AI 실력 트랙', report)
        self.assertIn('승률', report)
        self.assertIn('n <', report)


if __name__ == '__main__':
    unittest.main()

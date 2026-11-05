"""오프라인판(app/main #109)에서 옮겨 온 화면 갱신 시험 — app/tests/board_sync_test.py 를 그대로 돌린다 (nny_sim 폴더에서):
python -m unittest test_online_board_sync -v

나 vs AI(가짜 사람 — 무작위 답) 2매치에서 사람에게 묻는 순간마다 화면이 받는 마지막 프레임의 상태가 엔진의 지금 상태와 같은지
(viewer/record.Recorder.sync — 효과 처리 뒤 필드가 바로 화면에). 이식 전 online/main 은 질문 131번 중 35번이 뒤처졌다(2026-11-05).
"""
import json, os, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'app', 'tests', 'board_sync_test.py')
TIMEOUT = 900   # 초 — 시험 스크립트 하나가 끝나야 하는 시간(매치 2개)


class BoardSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='nny_sync_')
        cards = os.path.join(self.tmp, 'cards'); os.makedirs(cards)
        with open(os.path.join(cards, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'ratio': 1.4, 'mat_size': [800, 600], 'faces': []}, f)
        self.args = [os.path.join(self.tmp, x) for x in ('split', 'cards', 'library', 'user')]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_screen_is_never_behind_engine_when_asking(self):
        r = subprocess.run([sys.executable, SCRIPT, HERE] + self.args, cwd=HERE, capture_output=True, text=True, timeout=TIMEOUT)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out[-3000:])
        self.assertIn('결과: 통과', out, out[-3000:])


if __name__ == '__main__':
    unittest.main()

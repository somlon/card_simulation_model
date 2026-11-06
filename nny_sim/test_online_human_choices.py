"""오프라인판(app/main)에서 옮겨 온 사람 자리 선택 시험 묶음 — app/tests/human_choice_test.py 를 그대로 돌린다 (nny_sim 폴더에서):
python -m unittest test_online_human_choices -v

제물 · 족보 재료 · 레벨/속성 부여 · 짐승조커 선언 · 번식지 카드를 사람이 직접 고르는지, 같은 이름 카드가 칸으로 따로 나오는지,
선택 코스트를 묻는지, 상대 뒷면 카드 이름이 후보 · 판단 줄에 나오지 않는지(app/main #97 · #98 · #108 · #112 이식, 2026-11-05).
"""
import os, subprocess, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'app', 'tests', 'human_choice_test.py')
TIMEOUT = 600   # 초 — 시험 스크립트 하나가 끝나야 하는 시간


class HumanChoicesTest(unittest.TestCase):
    def test_human_choice_script_passes(self):
        r = subprocess.run([sys.executable, SCRIPT, HERE], cwd=HERE, capture_output=True, text=True, timeout=TIMEOUT)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out[-3000:])
        self.assertIn('결과: 통과', out, out[-3000:])
        self.assertFalse([l for l in out.splitlines() if l.startswith('실패 ')], out[-3000:])   # check() 가 남긴 실패 줄


if __name__ == '__main__':
    unittest.main()

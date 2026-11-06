"""오프라인판(app/main #89)에서 옮겨 온 라운드 사이 사람의 스킬 교체 시험 — app/tests/side_skill_test.py 를 그대로 돌린다 (nny_sim 폴더에서):
python -m unittest test_online_side_skill -v

전략 덱의 스킬 카드로 바꾸면 새 스킬 태그에 맞지 않는 메인 · 상급 카드를 표시하고(misfit), 그 카드를 모두 전략 덱으로 보내기 전에는
「교체 끝」을 받지 않는다. 이식 전 online/main 은 이 상황에서 스킬 교체 후보 자체를 내지 않았다(2026-11-05).
"""
import os, subprocess, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'app', 'tests', 'side_skill_test.py')
TIMEOUT = 300   # 초


class SideSkillTest(unittest.TestCase):
    def test_skill_swap_marks_and_blocks_misfits(self):
        r = subprocess.run([sys.executable, SCRIPT, HERE], cwd=HERE, capture_output=True, text=True, timeout=TIMEOUT)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out[-3000:])
        self.assertIn('결과: 통과', out, out[-3000:])


if __name__ == '__main__':
    unittest.main()

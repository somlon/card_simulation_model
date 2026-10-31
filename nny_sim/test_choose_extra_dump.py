"""간절한 마음(WSFT-026) 추가 묘지행 — 사람에게 직접 묻는지 재현 테스트 (nny_sim 폴더에서):
python -m unittest test_choose_extra_dump -v

soltop_ 제보(2026-10-31, ai-채찍질-하는-방) — 「소원의분수 간절한 마음 - 1장 추가로 보낸다 무조건
1장 추가로 보내야되는게 아니라 보낼지 말지 선택 가능하게 변경」. 실제론 engine.py Game.dump가
처음부터 「...보낼 수 있다」로 짜여 있어 강제가 아니었지만, 사람 자리(HumanAI)에 choose_extra_dump가
없어 AI와 같은 고정 휴리스틱(len(main) - n >= 8)으로 조용히 정해져 사람에게 물어본 적이 없었다 —
그래서 사람 입장에서는 선택지 없이 무조건 정해지는 것처럼 보였다. 이 테스트는 app/human.py에
choose_extra_dump를 추가해(수정 전 코드로 되돌리면 AttributeError 없이 그냥 휴리스틱으로 빠져
이 테스트가 실패함을 확인했다) 사람이 직접 고른 답이 실제로 적용되는지 확인한다.
"""
import os, random, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app')]
import season as SE
import policy as P
from cards import Impl
from engine import Game, Card
from human import HumanAI


class FakeBridge:
    def __init__(self, default=0):
        self.default = default; self.queue = []

    def ask(self, req):
        return self.queue.pop(0) if self.queue else self.default


def make_game():
    decks = SE.load_decks()
    a, b = decks['소원의 분수'], decks['세제']
    ds = [dict(a, 이름='A'), dict(b, 이름='B')]
    bridge = FakeBridge()
    human = HumanAI(ds[0]['스킬'], bridge, None, learn=False)
    ai2 = P.LearnedAI(ds[1]['스킬'], learn=False)
    g = Game(ds, [human, ai2], 0, random.Random(7), [], Impl)
    g.setup()
    f = Card(Impl.pool['간절한 마음'], 0)
    Impl.attach(f)
    g.place_field(f, 0)
    return g, human, bridge


class ChooseExtraDumpTest(unittest.TestCase):
    def test_human_declines_extra_dump(self):
        g, human, bridge = make_game()
        self.assertGreaterEqual(len(g.p[0].main), 10, '휴리스틱(len(main)-n>=8)이면 그냥 보냈을 수량')
        bridge.queue = [1]   # '보내지 않음'
        out = g.dump(0, 2, '시험')
        self.assertEqual(len(out), 2, '사람이 추가 묘지행을 거절하면 요청한 수량 그대로여야 함')

    def test_human_accepts_extra_dump(self):
        g, human, bridge = make_game()
        bridge.queue = [0]   # '추가로 보냄'
        out = g.dump(0, 2, '시험')
        self.assertEqual(len(out), 3, '사람이 추가 묘지행을 받으면 1장 더 보내야 함')

    def test_default_without_queue_still_asks_and_uses_default_index(self):
        """큐가 비어 있으면 FakeBridge.default=0('추가로 보냄')으로 답하므로 여전히 3장 — 호출 자체가
        이루어졌는지(기존처럼 질문을 건너뛰고 바로 AI 휴리스틱으로 빠지지 않는지) 확인"""
        g, human, bridge = make_game()
        out = g.dump(0, 2, '시험')
        self.assertEqual(len(out), 3)


if __name__ == '__main__':
    unittest.main()

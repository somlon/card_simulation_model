"""사람 모드 트리거 발동 순서 선택 재현 테스트 (nny_sim 폴더에서): python -m unittest test_trigger_order -v

soltop_ 제보(디스코드 ai-채찍질-하는-방, 2026-10-31, `?` 재제보 9건 중 1번) — 동시에 발동할 수 있는
효과가 둘 이상일 때 사람에게 발동 순서를 고를 기회가 없었다(AI는 점수로 자동 정렬, 사람은 트리거
수집 순서 그대로 발동됐다). app/human.py의 HumanAI.choose_triggers가 선택된 효과가 2개 이상이면
그 발동 순서도 사람에게 묻고, 고른 순서를 그대로 돌려주는지 확인한다(1개 이하면 순서 질문 없이
바로 반환돼야 한다 — 불필요한 질문 추가 없음).
"""
import os, random, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app')]
import season as SE
import policy as P
from cards import Impl
from engine import Game
from human import HumanAI


class FakeBridge:
    """실제 스레드·화면 없이: 큐에 쌓인 답이 있으면 그걸, 없으면 기본값(0)을 돌려주는 가짜 Bridge"""
    def __init__(self, default=0):
        self.default = default; self.queue = []

    def ask(self, req):
        return self.queue.pop(0) if self.queue else self.default


class FakeEffect:
    """choose_triggers·act_score가 보는 최소 필드만 갖춘 가짜 효과 — 실제 카드 효과 없이 순서 로직만 검증"""
    def __init__(self, num, mandatory=False):
        self.num = num; self.mandatory = mandatory; self.score = None


class FakeCard:
    def __init__(self, name):
        self.name = name


def make_game():
    decks = SE.load_decks()
    a, b = decks['소원의 분수'], decks['세제']
    ds = [dict(a, 이름='A'), dict(b, 이름='B')]
    bridge = FakeBridge()
    human = HumanAI(ds[0]['스킬'], bridge, None, learn=False)
    ai2 = P.LearnedAI(ds[1]['스킬'], learn=False)
    g = Game(ds, [human, ai2], 0, random.Random(7), [], Impl)
    g.setup()
    return g, human, bridge


class TriggerOrderTest(unittest.TestCase):
    def test_two_optional_triggers_ask_order_and_respect_choice(self):
        g, human, bridge = make_game()
        cands = [(FakeCard('카드A'), FakeEffect(1), None), (FakeCard('카드B'), FakeEffect(1), None)]
        # 둘 다 "발동"(각 idx0) 고른 뒤, 순서 질문에서 두 번째(idx1=카드B)를 먼저 고름
        bridge.queue = [0, 0, 1]
        order = human.choose_triggers(g, 0, cands)
        self.assertEqual([c.name for c, _, _ in order], ['카드B', '카드A'],
                          '사람이 고른 발동 순서(카드B를 먼저)가 그대로 반영되어야 함')

    def test_mandatory_triggers_are_all_kept_but_order_is_asked(self):
        g, human, bridge = make_game()
        cands = [(FakeCard('카드A'), FakeEffect(1, mandatory=True), None),
                  (FakeCard('카드B'), FakeEffect(1, mandatory=True), None)]
        bridge.queue = [1]   # 필수 효과라 발동 여부는 안 묻고, 순서만 물어 카드B를 먼저 고름
        order = human.choose_triggers(g, 0, cands)
        self.assertEqual([c.name for c, _, _ in order], ['카드B', '카드A'])

    def test_single_trigger_no_order_question_asked(self):
        g, human, bridge = make_game()
        cands = [(FakeCard('카드A'), FakeEffect(1, mandatory=True), None)]
        bridge.queue = []   # 질문거리가 없어야 한다 — 큐가 비어 있는데도 기본값만으로 통과해야 함
        order = human.choose_triggers(g, 0, cands)
        self.assertEqual([c.name for c, _, _ in order], ['카드A'])

    def test_declined_optional_trigger_is_dropped_before_order_question(self):
        g, human, bridge = make_game()
        cands = [(FakeCard('카드A'), FakeEffect(1), None), (FakeCard('카드B'), FakeEffect(1), None)]
        bridge.queue = [0, 1]   # 카드A는 발동(idx0), 카드B는 안 함(idx1) → 순서 질문 자체가 없어야 함
        order = human.choose_triggers(g, 0, cands)
        self.assertEqual([c.name for c, _, _ in order], ['카드A'])


if __name__ == '__main__':
    unittest.main()

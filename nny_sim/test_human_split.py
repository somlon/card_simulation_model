"""시작 패 배분 · 멀리건 재배분 — 사람에게 직접 묻는지 재현 테스트 (nny_sim 폴더에서):
python -m unittest test_human_split -v

jdiejd7788(세창) 제보(디스코드, 2026-11-03) — "온라인 버전에서 사람 vs ai 대전을 하는데 시작 패
비율을 사람 플레이어가 직접 정할 수 없어". 실제론 policy.LearnedAI.choose_split·mulligan_split이
choose_summon_pos(soltop_ 제보로 이미 고쳐짐)와 같은 문제로 LearnedAI.choose를 self.choose가 아니라
직접 불러 사람 자리(HumanAI)의 choose를 거치지 않아, choose_extra_dump 때와 같은 패턴으로 사람도
AI와 같은 학습값 기반 자동 배분으로 조용히 정해지고 있었다(물어본 적이 없음). 이 테스트는 app/human.py에
choose_split·mulligan_split을 추가해(수정 전으로 되돌리면 AttributeError 없이 LearnedAI 쪽 메서드로
빠져 bridge.ask가 불리지 않아 이 테스트가 실패함을 확인했다) 사람이 직접 고른 배분이 실제로 적용되는지
확인한다.
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
    """기본은 0번 답, 다만 picker(decision, labels)가 있으면 그 결정에서만 picker로 답을 고른다"""
    def __init__(self, default=0, picker=None):
        self.default = default; self.picker = picker; self.calls = []

    def ask(self, req):
        self.calls.append(req)
        if self.picker:
            i = self.picker(req['decision'], [o['label'] for o in req['opts']])
            if i is not None: return i
        return self.default


def make_game(seed=7, picker=None):
    decks = SE.load_decks()
    a, b = decks['소원의 분수'], decks['세제']
    ds = [dict(a, 이름='A'), dict(b, 이름='B')]
    bridge = FakeBridge(picker=picker)
    human = HumanAI(ds[0]['스킬'], bridge, None, learn=False)
    ai2 = P.LearnedAI(ds[1]['스킬'], learn=False)
    g = Game(ds, [human, ai2], 0, random.Random(seed), [], Impl)
    return g, human, bridge


def pick_max_main(decision, labels):
    """'시작 패 배분'·'시작 패 재배분' 질문에서 메인 매수가 가장 큰 후보를 고름(그 외 질문은 None → 기본값)"""
    if not decision.startswith('시작 패'): return None
    ks = [int(lab.split()[1]) for lab in labels]
    return ks.index(max(ks))


class ChooseSplitTest(unittest.TestCase):
    def test_setup_asks_human_for_split(self):
        g, human, bridge = make_game()
        g.setup()
        asked = [c for c in bridge.calls if c['decision'].startswith('시작 패 배분')]
        self.assertEqual(len(asked), 1, '시작 패 배분은 사람에게 물어야 함(한 번)')

    def test_human_pick_is_applied(self):
        g, human, bridge = make_game(picker=pick_max_main)
        g.setup()
        line = next(e['m'] for e in g.log if e['m'].startswith('A 시작 패'))
        asked = next(c for c in bridge.calls if c['decision'].startswith('시작 패 배분'))
        k_asked = max(int(o['label'].split()[1]) for o in asked['opts'])
        self.assertIn(f'메인 {k_asked}', line, '사람이 고른 메인 매수가 실제 시작 패에 그대로 반영돼야 함')

    def test_mulligan_split_asks_human(self):
        g, human, bridge = make_game()
        g.setup()
        back = list(g.p[0].hand)[:2]
        for c in back: g.p[0].hand.remove(c)
        bridge.calls.clear()
        human.mulligan_split(g, 0, back)
        asked = [c for c in bridge.calls if c['decision'].startswith('시작 패 재배분')]
        self.assertEqual(len(asked), 1, '멀리건 재배분도 사람에게 물어야 함')


if __name__ == '__main__':
    unittest.main()

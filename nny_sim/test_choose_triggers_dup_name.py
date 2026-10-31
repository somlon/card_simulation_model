"""동일 카드명 효과 중복 질문 재현 테스트 (nny_sim 폴더에서): python -m unittest test_choose_triggers_dup_name -v

soltop_ 제보 9건 중 7번(2026-10-31, ai-채찍질-하는-방, 원문 재확인): "동일 카드명 효과를 여러 장 쓸 수
있게 됐을 때 중복으로 물어본다 — 1턴 1회라 여러 장 중 1장만 응답 물어보면 된다." 1턴 1회는
engine.py Game.opt_key 로 카드명×효과번호 단위로 공유되므로(opt_per_card 가 아닌 한), 같은 이름의
같은 효과 번호를 가진 카드가 cands 에 여러 장 있어도 이번 턴에 실제로 쓸 수 있는 횟수(남은 opt
한도, 보통 1)만큼만 물어야 한다. 수정 전 app/human.py HumanAI.choose_triggers 는 cands 의 각 (c,e,ev)
마다 무조건 하나씩 물어 같은 질문을 여러 번 반복했다(이 테스트는 수정 전 코드로 되돌리면 2장짜리
그룹에서 질문이 2번(delta) 나와 실패함을 확인했다). g.setup()의 멀리건 등으로 bridge.ask가 이미
호출된 뒤라 절대 횟수 대신 호출 전후 델타(delta)로 센다."""
import os, random, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, 'app')]
import season as SE
import policy as P
from cards import Impl
from engine import Game, Card, Effect
from human import HumanAI


class FakeBridge:
    def __init__(self, default=0):
        self.default = default; self.queue = []; self.asked = []

    def ask(self, req):
        self.asked.append(req)
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
    return g, human, bridge


def dup_cards(g, name, n):
    out = []
    for _ in range(n):
        c = Card(Impl.pool[name], 0); Impl.attach(c); c.zone = 'grave'; g.p[0].grave.append(c); out.append(c)
    return out


def ask_delta(bridge, fn):
    """fn()을 호출하고, 그 호출 동안 bridge.ask가 몇 번 불렸는지(델타)와 fn()의 반환값을 함께 돌려준다"""
    base = len(bridge.asked)
    result = fn()
    return result, len(bridge.asked) - base


class ChooseTriggersDupNameTest(unittest.TestCase):
    def test_shared_opt_group_asked_only_once(self):
        g, human, bridge = make_game()
        c1, c2 = dup_cards(g, '소원의 분수', 2)
        cands = [(c1, Effect(num=99, kind='lastwill', mandatory=False, opt=1), None),
                 (c2, Effect(num=99, kind='lastwill', mandatory=False, opt=1), None)]
        bridge.queue = [1]   # 첫(유일한) 질문에 '안 함'
        chosen, delta = ask_delta(bridge, lambda: human.choose_triggers(g, 0, cands))
        self.assertEqual(delta, 1, '같은 이름×효과번호(opt 공유)는 한 번만 물어야 한다')
        self.assertEqual(chosen, [])

    def test_shared_opt_group_three_copies_still_one_ask(self):
        g, human, bridge = make_game()
        c1, c2, c3 = dup_cards(g, '소원의 분수', 3)
        cands = [(c1, Effect(num=99, kind='lastwill', mandatory=False, opt=1), None),
                 (c2, Effect(num=99, kind='lastwill', mandatory=False, opt=1), None),
                 (c3, Effect(num=99, kind='lastwill', mandatory=False, opt=1), None)]
        bridge.queue = [0]   # '발동'
        chosen, delta = ask_delta(bridge, lambda: human.choose_triggers(g, 0, cands))
        self.assertEqual(delta, 1, '3장이라도 공유 한도(1)만큼만 물어야 한다')
        self.assertEqual(len(chosen), 1, '발동을 택하면 대표로 1장만 선택된다')

    def test_already_used_this_turn_asks_nothing(self):
        g, human, bridge = make_game()
        c1, c2 = dup_cards(g, '소원의 분수', 2)
        e1 = Effect(num=99, kind='lastwill', mandatory=False, opt=1)
        g.p[0].opt[g.opt_key(c1, e1)] = 1   # 이미 이번 턴에 이 이름×번호를 썼다고 가정
        cands = [(c1, e1, None), (c2, Effect(num=99, kind='lastwill', mandatory=False, opt=1), None)]
        chosen, delta = ask_delta(bridge, lambda: human.choose_triggers(g, 0, cands))
        self.assertEqual(delta, 0, '남은 한도가 0이면 아예 묻지 않아야 한다')
        self.assertEqual(chosen, [])

    def test_unlimited_opt_is_unaffected(self):
        """opt=None(무제한)인 효과는 같은 이름이어도 공유 한도가 없으므로 기존처럼 각각 물어야 한다
        (이번 수정이 손대지 않아야 하는 범위 — 회귀 확인용)"""
        g, human, bridge = make_game()
        c1, c2 = dup_cards(g, '소원의 분수', 2)
        cands = [(c1, Effect(num=99, kind='lastwill', mandatory=False, opt=None), None),
                 (c2, Effect(num=99, kind='lastwill', mandatory=False, opt=None), None)]
        bridge.queue = [1, 1]   # 둘 다 '안 함'
        _, delta = ask_delta(bridge, lambda: human.choose_triggers(g, 0, cands))
        self.assertEqual(delta, 2, 'opt=None 이면 공유 한도가 없어 각각 물어야 한다')

    def test_mandatory_unaffected(self):
        """필수(mandatory) 효과는 "발동할지" 질문 없이 전부 자동 포함 — 기존 동작 그대로(이 테스트가 보는
        변경 범위 밖). 2장 다 뽑히면 "먼저 발동할 효과" 순서 질문 1번은 그대로 남는다(soltop_ 1번 — 이번
        수정과 무관, 회귀 확인용)."""
        g, human, bridge = make_game()
        c1, c2 = dup_cards(g, '소원의 분수', 2)
        cands = [(c1, Effect(num=99, kind='lastwill', mandatory=True, opt=1), None),
                 (c2, Effect(num=99, kind='lastwill', mandatory=True, opt=1), None)]
        bridge.queue = [0]   # 순서 질문: 첫 후보를 먼저
        chosen, delta = ask_delta(bridge, lambda: human.choose_triggers(g, 0, cands))
        self.assertEqual(delta, 1, '"발동할지"는 안 묻지만 순서 질문 1번은 그대로 있어야 한다')
        self.assertEqual(len(chosen), 2)


if __name__ == '__main__':
    unittest.main()

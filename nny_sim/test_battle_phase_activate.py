"""전투 단계에서 효과 발동 선택지 재현 테스트 (nny_sim 폴더에서): python -m unittest test_battle_phase_activate -v

soltop_ 제보 9건 중 4번(디스코드 메시지 1566019686980784200): "전투 단계 - 우선권 포기 시 효과 발동이
선택지에 표기되지 않고 공격명령만 보이는 문제. 우선권 포기를 했더라도 선택지에 있어야함."
원인: main_phase는 g.options(p, ('ignition','quick'))를 행동 목록에 더하는데(human.py 208~209행),
battle_phase는 공격 후보만 만들고 ignition/quick 발동 후보를 전혀 넣지 않아 사람은 전투 단계에서
자신의 효과를 발동할 수 없었다(engine.py의 spell_speed_ok 주석대로 마법 발동엔 '단계 제한 없음'이라
규칙상 전투 단계에서도 발동할 수 있어야 한다). 이 테스트는 g.options · g.act를 가짜로 바꿔 전투 단계
행동 목록에 '발동:' 후보가 실제로 나타나고, 그걸 고르면 g.act가 불리는지만 확인한다(카드 효과 자체의
처리는 다른 테스트가 담당 — 여기서는 human.py의 선택지 구성만 본다).
"""
import os, random, sys, types, unittest

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
    g.p[0].hand.clear()
    g.turn = 3; g.turn_player = 0; g.phase = '전투'
    return g, human, bridge


class BattlePhaseActivateOptionTest(unittest.TestCase):
    def test_activation_option_present_and_act_called(self):
        g, human, bridge = make_game()
        card = Card(Impl.pool['던전마스터 깜짝상자'], 0); Impl.attach(card)
        g.place_monster(card, 0, 'atk'); card.summon_turn = g.turn - 1
        card.attacks_made = 999   # 공격 후보에서 제외 — 발동 후보만 본다
        eff = types.SimpleNamespace(num=1, mandatory=False, score=None)

        calls = {'options': 0, 'act': []}

        def fake_options(p, kinds, ev=None):
            calls['options'] += 1
            if kinds == ('ignition', 'quick') and p == 0 and calls['options'] == 1:
                return [(card, eff)]
            return []   # 둘째 호출부터는 발동 후보가 없음(1턴 1번 소진 가정) — 전투 단계가 끝나는지 확인

        def fake_act(p, c, e):
            calls['act'].append((p, c, e)); return True

        g.options = fake_options
        g.act = fake_act

        bridge.queue = [1]   # 첫 선택지: ['공격 종료', '발동:던전마스터 깜짝상자#1'] 중 index 1
        human.battle_phase(g, 0)

        self.assertEqual(len(calls['act']), 1, '전투 단계 행동 목록에 발동 후보가 없거나 선택해도 g.act가 불리지 않음')
        self.assertEqual(calls['act'][0], (0, card, eff))


if __name__ == '__main__':
    unittest.main()

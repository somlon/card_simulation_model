"""사람 모드 상급(제물) 일반소환 재현 테스트 (nny_sim 폴더에서):  python -m unittest test_human_tribute -v
세창 체크 — app/human.py 행동 목록에 제물 소환 후보는 있었으나(ai.py extra_summon_options 상속) 제물로 릴리스할
몬스터를 AI가 자동으로(가치 낮은 순) 골랐다. 사람이 직접 고르도록 human.py에 pick_tribute_set·do_extra를 추가했다.
이 테스트는 상급 하나(레벨 5, 제물 1장 필요) + 필드에 2레벨 이상 몬스터 2장뿐인 상태에서 사람이 제물을 직접
골라 상급 일반소환을 실제로 마칠 수 있는지를 자동으로 확인한다.
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
    """실제 스레드·화면 없이: 큐에 쌓인 답이 있으면 그걸, 없으면 기본값(0 = 첫 후보)을 돌려주는 가짜 Bridge
    (setup() 중의 멀리건 질문처럼 이 테스트와 무관한 질문은 전부 기본값 0 = '유지' 로 흘려보낸다)"""
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
    g.p[0].hand.clear()          # 멀리건 끝난 뒤 — 이 테스트와 무관한 기본 패를 지우고 제물소환 상황만 둔다
    g.turn = 3; g.turn_player = 0; g.phase = '진행'
    return g, human, bridge


def place(g, name, owner, pos='atk'):
    c = Card(Impl.pool[name], owner); Impl.attach(c)
    g.place_monster(c, owner, pos); c.summon_turn = g.turn - 1
    return c


def in_hand(g, name, owner):
    c = Card(Impl.pool[name], owner); Impl.attach(c)
    c.zone = 'hand'; g.p[owner].hand.append(c)
    return c


class HumanTributeSummonTest(unittest.TestCase):
    def test_human_can_choose_tribute_and_complete_upper_summon(self):
        g, human, bridge = make_game()
        t1 = place(g, '던전마스터 깜짝상자', 0)   # 레벨 3 — 필드의 제물 후보 1
        t2 = place(g, '던전마스터 망령', 0)       # 레벨 3 — 필드의 제물 후보 2
        upper = in_hand(g, '격투가 스네이크 스케일', 0)   # 레벨 5 — 제물 1장 필요
        self.assertEqual(g.tributes_needed(upper.level), 1)

        # 행동 목록에서 '제물소환:격투가 스네이크 스케일' 후보가 실제로 뜨는지 확인
        acts = [('종료', 0, None)]
        for lab, s, pay in human.extra_summon_options(g, 0):
            acts.append((lab, s, ('extra', pay[1], pay)))
        labels = [a[0] for a in acts]
        self.assertIn('소환:격투가 스네이크 스케일', labels, '제물 일반소환 후보가 사람 행동 목록에 없음')

        # 사람 선택 순서: [행동 목록에서 그 후보 선택, 제물로 t2를 고름(t1,t2 중 1번째=t2)]
        pick_idx = labels.index('소환:격투가 스네이크 스케일')
        bridge.queue = [pick_idx, 1]   # 1 → remaining 목록(t1,t2) 중 t2
        human.main_phase(g, 0, '진행')

        self.assertEqual(upper.zone, 'm')
        self.assertTrue(upper.faceup)
        # 제물로 고른 쪽(t2)은 필드를 떠나야 하고, 고르지 않은 쪽(t1)은 그대로 남아야 한다.
        # (t2 「던전마스터 망령」은 릴리스되면 덱으로 돌아가는 자체 효과가 있어 정확한 목적지는 카드마다
        #  다르다 — 여기서는 "사람이 고른 쪽만 필드를 떠난다"만 확인한다)
        field = g.monsters(0)
        self.assertNotIn(t2, field, '사람이 고른 제물(t2)은 필드를 떠나야 함')
        self.assertIn(t1, field, '사람이 고르지 않은 쪽(t1)은 그대로 필드에 남아야 함')


if __name__ == '__main__':
    unittest.main()

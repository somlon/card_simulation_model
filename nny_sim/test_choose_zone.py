"""사람 자리 「놓을 존 직접 고르기」 재현 테스트 (nny_sim 폴더에서):  python -m unittest test_choose_zone -v
app/main 커밋 97baeff(choose_zone)을 online 레이어에 포팅 — 엔진의 Game.pick_zone은 이미 online/main에
있었으나(getattr(..., 'choose_zone', None)로 사람 자리를 묻게 돼 있음) HumanAI 쪽에 choose_zone이
없어서 사람은 항상 첫 빈 몬스터/마법 존에만 놓였다(공유 존도 선택 못 함). 이 테스트는 사람이 첫 빈칸이
아닌 다른 빈 존(과 공유 존)을 직접 골라 실제로 그 자리에 놓이는지 확인한다.
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
    return g, human, bridge


class ChooseZoneTest(unittest.TestCase):
    def test_human_picks_non_default_monster_zone(self):
        g, human, bridge = make_game()
        c = Card(Impl.pool['던전마스터 깜짝상자'], 0); Impl.attach(c)
        opts = g.free_m(0)
        self.assertGreater(len(opts), 1, '몬스터 존이 전부 비어 있어야 선택지가 여러 개여야 함')
        bridge.queue = [2]   # 후보 중 3번째(opts[2])를 고름 — 첫 빈칸이 아님
        ok = g.place_monster(c, 0, 'atk')
        self.assertTrue(ok)
        self.assertEqual(c.zone, 'm')
        self.assertIs(g.p[0].m[opts[2]], c, '사람이 고른 존(첫 칸이 아닌)에 실제로 놓여야 함')

    def test_human_picks_shared_zone_even_when_monster_zone_free(self):
        # 공유 존 2칸(사용자 지시 2026-10-30) — choose_zone의 opts = free_m + ['shared0', 'shared1']
        g, human, bridge = make_game()
        self.assertTrue(all(x is None for x in g.shareds))
        c = Card(Impl.pool['던전마스터 깜짝상자'], 0); Impl.attach(c)
        opts = g.free_m(0)
        shared_idx = len(opts) + 1   # 뒤에서 두 칸 중 두 번째('shared1')를 고름 — 첫 칸이 아님을 확인
        bridge.queue = [shared_idx]
        ok = g.place_monster(c, 0, 'atk')
        self.assertTrue(ok)
        self.assertEqual(c.zone, 'shared', '몬스터 존이 비어 있어도 사람이 공유 존을 직접 고르면 그쪽에 놓여야 함(§10-2)')
        self.assertIs(g.shareds[1], c, '사람이 고른 칸(두 번째)에 실제로 놓여야 함')

    def test_default_without_queue_still_first_empty_zone(self):
        """큐가 비어 있으면(기존 테스트들의 FakeBridge.default=0 과 동일) 여전히 첫 빈칸 — 다른 사람-모드
        테스트들의 기존 큐 순서가 choose_zone 추가로 깨지지 않음을 확인"""
        g, human, bridge = make_game()
        c = Card(Impl.pool['던전마스터 깜짝상자'], 0); Impl.attach(c)
        opts = g.free_m(0)
        ok = g.place_monster(c, 0, 'atk')
        self.assertTrue(ok)
        self.assertIs(g.p[0].m[opts[0]], c)


if __name__ == '__main__':
    unittest.main()

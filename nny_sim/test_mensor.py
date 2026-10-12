"""세리 - 멘소르 소환 유발 효과 테스트 (nny_sim 폴더에서):  python -m unittest test_mensor -v
효과: 서로의 메인 덱 매수가 다르면 많은 쪽 덱을 위에서 차이만큼 제외한다. 내 덱이 많으면 내 덱이 깎이므로 AI는 쓰지 않는다.
「세리 - 멘소르」는 카드 풀 교체(2026-10-08)로 빠졌다 — 구현은 cards4.py에 남아 있어 카드가 풀에 돌아오면 이 테스트가 다시 돈다.
지금 카드 중 「자기 덱을 깎으면 쓰지 않는」 판단(VETO)을 가진 소환 유발 효과는 없다(엑삭토르 · 프로쿠라토르는 점수만 다름)."""
import random, unittest
import cards
import season as SE
import policy as P
from ai import HeuristicAI
from cards import Impl
from engine import Game, Card

DECKS = SE.load_decks()


def make(ai):
    da, db = DECKS['세제'], DECKS['세제']                   # 세리 덱끼리: 같은 덱이라 시작 메인 덱 매수가 같다
    mk = (lambda d: P.LearnedAI(d['스킬'], learn=False)) if ai is P.LearnedAI else (lambda d: ai(d['스킬']))
    g = Game([dict(da, 이름='A'), dict(db, 이름='B')], [mk(da), mk(db)], 0, random.Random(4), [], Impl)
    g.setup(); g.turn = 3; g.turn_player = 0; g.phase = '진행'
    return g


def mensor_trigger(g):
    c = Card(Impl.pool['세리 - 멘소르'], 0); Impl.attach(c); c.zone = None
    g.place_monster(c, 0, 'atk')
    e = c.effects[0]
    return c, e, {'type': 'summon', 'card': c}


@unittest.skipUnless('세리 - 멘소르' in cards.POOL, '카드 풀에서 빠진 카드 (2026-10-08)')
class MensorTest(unittest.TestCase):
    def check(self, ai, own_more):
        g = make(ai)
        mine, theirs = g.p[0].main, g.p[1].main
        if own_more: del theirs[len(mine) - 5:]
        else: del mine[len(theirs) - 5:]
        self.assertEqual(len(mine) > len(theirs), own_more)
        c, e, ev = mensor_trigger(g)
        return g.p[0].ai.choose_triggers(g, 0, [(c, e, ev)])

    def test_heuristic_declines_self_mill(self):
        self.assertEqual(self.check(HeuristicAI, own_more=True), [])
        self.assertEqual(len(self.check(HeuristicAI, own_more=False)), 1)

    def test_learned_declines_self_mill(self):
        self.assertEqual(self.check(P.LearnedAI, own_more=True), [])

    def test_effect_mills_the_larger_deck(self):
        g = make(HeuristicAI)
        del g.p[0].main[len(g.p[1].main) - 3:]           # 상대가 3장 더 많다
        c, e, ev = mensor_trigger(g)
        n0, n1 = len(g.p[0].main), len(g.p[1].main)
        self.assertEqual(n1 - n0, 3)
        e.res(g, c, 0, None)
        self.assertEqual((len(g.p[0].main), len(g.p[1].main)), (n0, n1 - 3))


if __name__ == '__main__':
    unittest.main()

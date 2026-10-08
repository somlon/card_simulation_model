"""뒷면 공격 표시 테스트 (nny_sim 폴더에서):  python -m unittest test_facedown -v
사용자 재정 2026-10-06: 뒷면으로 하는 효과를 받은 공격 표시 몬스터는 뒷면 공격 표시가 된다.
뒷면 공격 표시 몬스터는 공격할 수 없고, 상대는 그 몬스터를 무시하고 직접공격할 수 있다."""
import random, unittest
import season as SE
import policy as P
from ai import HeuristicAI
from cards import Impl
from engine import Game, Card

DECKS = SE.load_decks()


def make(ai=HeuristicAI):
    da, db = DECKS['투기장의 규칙'], DECKS['세제']
    mk = (lambda d: P.LearnedAI(d['스킬'], learn=False)) if ai is P.LearnedAI else (lambda d: ai(d['스킬']))
    g = Game([dict(da, 이름='A'), dict(db, 이름='B')], [mk(da), mk(db)], 0, random.Random(11), [], Impl)
    g.setup(); g.turn = 3; g.turn_player = 0; g.phase = '진행'
    return g


def put(g, name, owner, pos='atk'):
    c = Card(Impl.pool[name], owner); Impl.attach(c); c.zone = None
    g.place_monster(c, owner, pos); c.summon_turn = 0
    return c


class FaceDownTest(unittest.TestCase):
    def test_attack_position_becomes_face_down_attack(self):
        g = make()
        m = put(g, '세리 - 릭토르', 1, 'atk')
        self.assertTrue(g.set_face_down(m))
        self.assertFalse(m.faceup); self.assertEqual(m.pos, 'atk')

    def test_defense_position_becomes_face_down_defense(self):
        g = make()
        m = put(g, '세리 - 릭토르', 1, 'def')
        self.assertTrue(g.set_face_down(m))
        self.assertFalse(m.faceup); self.assertEqual(m.pos, 'def')

    def test_face_down_attack_monster_cannot_attack(self):
        g = make()
        m = put(g, '격투가 라이노 혼', 0, 'atk'); g.set_face_down(m)
        self.assertFalse(g.can_attack_with(m))
        hp = g.p[1].hp
        g.attack(m, None)                                   # 엔진도 막는다
        self.assertEqual(g.p[1].hp, hp)

    def test_opponent_can_attack_directly_past_face_down_attack_monster(self):
        g = make()
        blocker = put(g, '세리 - 릭토르', 1, 'atk'); g.set_face_down(blocker)
        a = put(g, '격투가 라이노 혼', 0, 'atk')
        self.assertTrue(g.can_direct(a))
        self.assertNotIn(blocker, g.attack_targets(a))       # 뒷면은 공격 대상 아님
        hp = g.p[1].hp
        g.attack(a, None)
        self.assertEqual(g.p[1].hp, hp - 3000)

    def test_face_down_defense_still_blocks_direct_attack(self):
        g = make()
        blocker = put(g, '세리 - 릭토르', 1, 'def'); g.set_face_down(blocker)
        a = put(g, '격투가 라이노 혼', 0, 'atk')
        self.assertFalse(g.can_direct(a))

    def test_learned_ai_takes_the_direct_attack(self):
        g = make(P.LearnedAI)
        blocker = put(g, '세리 - 릭토르', 1, 'atk'); g.set_face_down(blocker)
        put(g, '격투가 라이노 혼', 0, 'atk')
        g.phase = '전투'
        hp = g.p[1].hp
        g.p[0].ai.battle_phase(g, 0)
        self.assertLess(g.p[1].hp, hp)


if __name__ == '__main__':
    unittest.main()

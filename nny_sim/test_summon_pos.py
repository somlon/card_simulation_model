"""소환 표시 형식 선택 테스트 (nny_sim 폴더에서):  python -m unittest test_summon_pos -v
모든 일반소환 · 특수소환에서 텍스트가 표시 형식을 정하지 않으면 AI가 공격 / 수비 표시를 고른다(Game.summon_pos)."""
import random, unittest
import season as SE
import policy as P
from ai import HeuristicAI
from cards import Impl
from engine import Game, Card

DECKS = SE.load_decks()


def make_game(ai_cls=HeuristicAI):
    a, b = DECKS['번성충-기생'], DECKS['투기장의 규칙']
    decks = [dict(a, 이름='A'), dict(b, 이름='B')]
    mk = (lambda d: P.LearnedAI(d['스킬'], learn=False)) if ai_cls is P.LearnedAI else (lambda d: ai_cls(d['스킬']))
    g = Game(decks, [mk(a), mk(b)], 0, random.Random(7), [], Impl)
    g.setup()
    g.turn = 1; g.turn_player = 0; g.phase = '진행'
    return g


def in_hand(g, name, owner):
    c = Card(Impl.pool[name], owner); Impl.attach(c)
    c.zone = 'hand'; g.p[owner].hand.append(c)
    return c


class SummonPositionTest(unittest.TestCase):
    def test_zero_attack_special_summon_goes_to_defense(self):
        g = make_game()
        c = in_hand(g, '번성충-기생유생', 0)
        self.assertTrue(g.special_summon(c, 0))
        self.assertEqual(c.pos, 'def')                     # 공격력 0 — 수비 표시면 공격받아도 HP 피해 없음

    def test_attack_when_it_can_attack_this_turn(self):
        g = make_game()
        g.turn = 3                                          # 선공 1턴이 아니고 전투 단계 이전
        c = in_hand(g, '솔루나 시엘', 0)
        self.assertTrue(g.special_summon(c, 0))
        self.assertEqual(c.pos, 'atk')                     # 상대 필드가 비어 직접공격 가능

    def test_first_turn_high_defense_monster_goes_to_defense(self):
        g = make_game()
        c = in_hand(g, '세리 - 멘소르', 0)                   # 공 700 / 수 1500, 선공 1턴(공격 불가)
        g.normal_summon(c, 0)
        self.assertEqual(c.pos, 'def')

    def test_text_fixed_position_is_respected(self):
        g = make_game()
        c = in_hand(g, '번성충-기생유생', 0)
        self.assertTrue(g.special_summon(c, 0, 'atk'))     # 텍스트가 「공격 표시로」를 정한 효과는 pos를 넘긴다
        self.assertEqual(c.pos, 'atk')

    def test_defense_forbidden_by_arena(self):
        g = make_game()
        arena = in_hand(g, '격투가의 투기장', 1)
        g._remove(arena); g.place_field(arena, 1)          # 상대(자리 1)의 투기장: 자리 0 몬스터는 수비 표시 불가
        c = in_hand(g, '번성충-기생유생', 0)
        self.assertTrue(g.special_summon(c, 0))
        self.assertEqual(c.pos, 'atk')

    def test_learned_ai_logs_and_follows_prior_without_data(self):
        g = make_game(P.LearnedAI)
        c = in_hand(g, '번성충-기생유생', 0)
        self.assertTrue(g.special_summon(c, 0))
        self.assertEqual(c.pos, 'def')
        dec = [e for e in g.log if e['k'] == 'decision' and e.get('data') and e['data']['decision'].startswith('소환 표시 형식')]
        self.assertTrue(dec)
        self.assertEqual(dec[-1]['data']['pick'], '수비 표시:번성충-기생유생')

    def test_ai_without_hook_keeps_attack(self):
        g = make_game()
        class NoHook:                                       # 표시 형식 판단 함수가 없는 AI → 예전처럼 공격 표시
            def use_shared(self, g, p, c, full=True): return False
        g.p[0].ai = NoHook()
        c = in_hand(g, '번성충-기생유생', 0)
        self.assertTrue(g.special_summon(c, 0))
        self.assertEqual(c.pos, 'atk')


if __name__ == '__main__':
    unittest.main()

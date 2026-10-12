"""종료 · 패스 평가(보유 가치) 테스트 (nny_sim 폴더에서):  python -m unittest test_pass_eval -v"""
import random, unittest
import season as SE
import policy as P
from ai import HeuristicAI
from cards import Impl
from engine import Game, Card, Link, Effect
from drl.agent import DRLAI

DECKS = SE.load_decks()


def make(ai=HeuristicAI):
    da, db = DECKS['소원의 분수'], DECKS['세제']   # 카드 풀 교체(2026-10-08): 투기장의 규칙 → 소원의 분수
    mk = (lambda d: P.LearnedAI(d['스킬'], learn=False)) if ai is P.LearnedAI else (lambda d: ai(d['스킬']))
    g = Game([dict(da, 이름='A'), dict(db, 이름='B')], [mk(da), mk(db)], 0, random.Random(11), [], Impl)
    g.setup(); g.turn = 3; g.turn_player = 0; g.phase = '진행'
    return g


def card(g, name, owner, zone, faceup=True):
    c = Card(Impl.pool[name], owner); Impl.attach(c); c.zone = zone; c.faceup = faceup
    if zone == 'hand': g.p[owner].hand.append(c)
    return c


class HoldValueTest(unittest.TestCase):
    def test_hand_trap_and_set_quick_spell_have_hold_value(self):
        g = make(); ai = g.p[0].ai
        self.assertGreater(ai.hold_value(g, 0, card(g, '매수당한 킬러', 0, 'hand')), 0)             # 패에서 [신속]
        self.assertGreater(ai.hold_value(g, 0, card(g, '코인 - 행운의 네잎클로버', 0, 'hand')), 0)  # 패에서 [신속] (일반소환할 수 있는 몬스터)
        self.assertGreater(ai.hold_value(g, 0, card(g, '명계의 규율', 0, 'hand')), 0)              # 트리거 마법: 세트해 두면 상대 턴에 쓸 수 있다
        self.assertGreater(ai.hold_value(g, 0, card(g, '고대의 봉인', 0, 's', faceup=False)), 0)   # 세트한 신속 마법

    def test_cards_without_opponent_turn_use_have_no_hold_value(self):
        g = make(); ai = g.p[0].ai
        self.assertEqual(ai.hold_value(g, 0, card(g, '럭키 다이스', 0, 'hand')), 0)              # 일반 마법
        self.assertEqual(ai.hold_value(g, 0, card(g, '시아 아츠 - 일광', 0, 'hand')), 0)         # 필드 마법 (필드에서의 [트리거] · [신속]은 패에서 못 쓴다)
        self.assertEqual(ai.hold_value(g, 0, card(g, '세리 - 릭토르', 0, 'hand')), 0)            # 유언만 있는 몬스터

    def test_hold_value_is_capped(self):
        g = make(); ai = g.p[0].ai
        self.assertLessEqual(ai.hold_value(g, 0, card(g, '솔루나 아츠 - 이클립스 오버드라이브', 0, 'hand')), ai.HOLD_CAP)

    def test_reserve_sums_hand_and_set_spells(self):
        g = make(); ai = g.p[0].ai
        g.p[0].hand[:] = []
        a = card(g, '명계의 규율', 0, 'hand'); card(g, '럭키 다이스', 0, 'hand')
        b = card(g, '고대의 봉인', 0, 's', faceup=False); g.place_spell(b, 0, False)
        self.assertAlmostEqual(ai.reserve(g, 0), ai.hold_value(g, 0, a) + ai.hold_value(g, 0, b))

    def test_response_cost_is_discounted_by_the_threat_being_answered(self):
        g = make(); ai = g.p[0].ai
        c = card(g, '명계의 규율', 0, 'hand')
        full = ai.spend_cost(g, 0, c, respond=True)
        src = card(g, '세리 - 엑삭토르', 1, 'hand')
        g.chain.append(Link(src, next(e for e in src.effects if e.threat >= 600), 1))
        self.assertLess(ai.spend_cost(g, 0, c, respond=True), full)
        g.chain.clear()

    def test_pass_eval_off_restores_old_scores(self):
        g = make(); ai = g.p[0].ai; ai.PASS_EVAL = False
        self.assertEqual(ai.spend_cost(g, 0, card(g, '명계의 규율', 0, 'hand')), 0)

    def test_drl_keeps_training_time_candidate_scores(self):
        self.assertFalse(DRLAI.PASS_EVAL)


class LearnedPassScoreTest(unittest.TestCase):
    def _capture(self, ai):
        seen = {}
        def choose(g, p, decision, opts, *a, **k):
            seen[decision] = opts; return None
        ai.choose = choose
        return seen

    def test_end_option_scores_the_reserve(self):
        g = make(P.LearnedAI); ai = g.p[0].ai
        g.p[0].hand[:] = []
        card(g, '명계의 규율', 0, 'hand')
        card(g, '코인 - 행운의 네잎클로버', 0, 'hand')   # 레벨 4 · 「솔루나」 아님 → 일반소환 후보 점수 = 20 + 공격력/100
        seen = self._capture(ai)
        ai.main_phase(g, 0, '진행')
        opts = seen['진행 행동']
        R = ai.reserve(g, 0)
        self.assertGreater(R, 0)
        self.assertEqual(dict((lab, s) for lab, s, _ in opts)['종료'], R)
        summon = [s for lab, s, _ in opts if lab == '소환:코인 - 행운의 네잎클로버']
        self.assertEqual(len(summon), 1)
        # 패의 [신속] 몬스터를 일반소환하면 그 보유 가치를 잃는다
        self.assertLess(summon[0], 20 + g.atk(g.p[0].hand[1]) / 100 + R)

    def test_pass_option_scores_the_reserve(self):
        g = make(P.LearnedAI); ai = g.p[0].ai
        g.p[0].hand[:] = []
        c = card(g, '명계의 규율', 0, 'hand')
        e = Effect(9, 'quick', ('hand',), score=lambda *a: 30)
        seen = self._capture(ai)
        ai.respond(g, 0, [(c, e)])
        d = dict((lab, s) for lab, s, _ in seen['우선권'])
        R = ai.reserve(g, 0)
        self.assertEqual(d['패스'], R)
        self.assertAlmostEqual(d['명계의 규율#9'], 30 + R - ai.hold_value(g, 0, c))   # 체인이 비어 있으면 할인 없음

if __name__ == '__main__':
    unittest.main()

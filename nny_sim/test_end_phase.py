"""종료 단계 처리 테스트 (nny_sim 폴더에서):  python -m unittest test_end_phase -v
스킬 존의 스킬도 [지속] 「턴 종료 시」 처리(end_process)와 종료 시 트리거가 실행되어야 한다."""
import math, random, re, unittest
import season as SE
from ai import HeuristicAI
from cards import Impl
from engine import Game, Card

DECKS = SE.load_decks()


class Idle(HeuristicAI):
    """진행 · 전투 단계에서 아무것도 하지 않는 AI (종료 단계만 관찰하기 위해)"""
    def main_phase(self, g, p, ph): return
    def battle_phase(self, g, p): return
    def respond(self, g, p, opts): return None


def make(a, b, ai=Idle, first=0, seed=3):
    da, db = DECKS[a], DECKS[b]
    g = Game([dict(da, 이름='A'), dict(db, 이름='B')], [ai(da['스킬']), ai(db['스킬'])], first, random.Random(seed), [], Impl)
    g.setup()
    return g


def new_card(name, owner):
    c = Card(Impl.pool[name], owner); Impl.attach(c)
    return c


class DecumaEndPhaseTest(unittest.TestCase):
    def test_turn_player_mills_tenth_of_main_each_end_phase(self):
        g = make('데쿠마', '투기장의 규칙')
        for _ in range(2):                                       # 데쿠마 턴 · 상대 턴 모두
            q = g.turn_player
            before = len(g.p[q].main)
            n0 = len(g.log)
            g.play_turn()
            mills = [e['m'] for e in g.log[n0:] if '(데쿠마)' in e['m'] and '제외' in e['m']]
            self.assertEqual(len(mills), 1, mills)
            k = int(re.search(r'(\d+)장 제외', mills[0]).group(1))
            self.assertEqual(k, math.ceil(before / 10) if q == 0 else math.ceil(before / 10) + (1 if g.rule('decuma_plus', 0) else 0))

    def test_decuma_effect_is_an_activation_on_the_chain(self):
        g = make('데쿠마', '투기장의 규칙')
        n0 = len(g.log)
        g.play_turn()
        acts = [e['m'] for e in g.log[n0:] if '「데쿠마」 1번 효과 발동' in e['m']]
        self.assertEqual(len(acts), 1)

    def test_anaboke_negates_this_turn_mill(self):
        g = make('데쿠마', '투기장의 규칙')
        ana = new_card('아나보케', 0); ana.zone = 'hand'; g.p[0].hand.append(ana)

        class UseAnaboke(Idle):
            def respond(self, g, p, opts):
                for c, e in opts:
                    if c.name == '아나보케': return (c, e)
                return None
        g.p[0].ai = UseAnaboke('데쿠마')
        before = len(g.p[0].main)
        n0 = len(g.log)
        g.play_turn()                                            # 데쿠마(자리 0)의 1턴: 자신 턴이라 패에서 신속 마법 발동 가능
        self.assertTrue(any('아나보케: 이 턴 데쿠마 제외 무효' in e['m'] for e in g.log[n0:]))
        self.assertEqual(len(g.p[0].main), before)               # 제외 없음
        self.assertEqual(g.decuma_double, 0)                     # 다음 자신 턴 종료 시 2배

    def test_anaboke_cannot_be_activated_without_decuma_on_chain(self):
        g = make('데쿠마', '투기장의 규칙')
        ana = new_card('아나보케', 0); ana.zone = 'hand'; g.p[0].hand.append(ana)
        g.phase = '종료'
        self.assertFalse(any(c.name == '아나보케' for c, e in g.options(0, ('quick',))))


class ParasiteEndPhaseTest(unittest.TestCase):
    def test_counters_decrease_at_own_end_phase_and_control_returns(self):
        g = make('번성충-기생', '투기장의 규칙')
        m = new_card('격투가 래빗 풋', 1); m.zone = None
        g.place_monster(m, 1); g.add_counter(m, '기생', 2)        # 상태 점검으로 자리 0이 컨트롤을 얻는다
        self.assertEqual(m.controller, 0)
        g.turn_player = 0
        g.play_turn()                                            # 기생(자리 0)의 종료 단계: 카운터 2 → 1
        self.assertEqual(m.counters.get('기생'), 1)
        self.assertEqual(m.controller, 0)
        g.play_turn()                                            # 상대 턴의 종료 단계: 변화 없음
        self.assertEqual(m.counters.get('기생'), 1)
        g.play_turn()                                            # 다시 자신의 종료 단계: 1 → 0, 컨트롤 반환
        self.assertFalse(m.counters.get('기생'))
        self.assertEqual(m.controller, 1)


if __name__ == '__main__':
    unittest.main()

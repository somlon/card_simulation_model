"""종료 단계 처리 테스트 (nny_sim 폴더에서):  python -m unittest test_end_phase -v
스킬 존의 스킬도 [지속] 「턴 종료 시」 처리(end_process)와 종료 시 트리거가 실행되어야 한다.
카드 풀 교체(2026-10-08) 뒤: 「데쿠마」 1번(서로의 턴 종료 시 · 강제) → 「희생제」 4번(상대 턴 종료 시 · 강제) · 「솔루나 아츠」 2번(턴 종료 시),
「아나보케」의 대응 → 「저주인형 - 처키」 1번(종료 단계에서만)의 대응으로 옮겼다. 빠진 카드만 쓰는 테스트는 그 카드가 풀에 있을 때만 돈다."""
import random, unittest
import cards
import season as SE
from ai import HeuristicAI
from cards import Impl
from engine import Game, Card

DECKS = SE.load_decks()
RETIRED_MSG = '카드 풀에서 빠진 카드 (2026-10-08)'


class Idle(HeuristicAI):
    """진행 · 전투 단계에서 아무것도 하지 않는 AI (종료 단계만 관찰하기 위해)"""
    def main_phase(self, g, p, ph): return
    def battle_phase(self, g, p): return
    def respond(self, g, p, opts): return None


def make(a, b, ai=Idle, first=0, seed=3, skill_a=None):
    """skill_a: 자리 0의 스킬만 바꿔 끼운다 — 카드 풀에서 빠진 스킬(덱 파일도 보관으로 옮겨짐)을 지금 덱에 얹어 시험할 때"""
    da, db = DECKS[a], DECKS[b]
    if skill_a: da = dict(da, 스킬=skill_a)
    g = Game([dict(da, 이름='A'), dict(db, 이름='B')], [ai(da['스킬']), ai(db['스킬'])], first, random.Random(seed), [], Impl)
    g.setup()
    return g


def new_card(name, owner):
    c = Card(Impl.pool[name], owner); Impl.attach(c)
    return c


def on_field(g, name, owner):
    c = new_card(name, owner); c.zone = None
    g.place_monster(c, owner)
    return c


class SkillEndPhaseTest(unittest.TestCase):
    def test_skill_trigger_sets_arts_at_each_end_phase(self):
        # 솔루나 아츠 2번: 「턴 종료 시에」 자신 필드에 시아 · 시엘이 모두 있으면 덱에서 아츠 카드 1장 세트 — 자신 턴 · 상대 턴 모두
        g = make('솔루나 아츠', '소원의 분수')
        on_field(g, '솔루나 시아', 0); on_field(g, '솔루나 시엘', 0)
        for _ in range(2):                                       # 솔루나 아츠 턴 · 상대 턴 모두
            before = [x for x in g.p[0].s if x]
            deck0 = len(g.deck_cards(0))
            n0 = len(g.log)
            g.play_turn()
            acts = [e['m'] for e in g.log[n0:] if '「솔루나 아츠」 2번 효과 발동' in e['m']]
            sets = [e['m'] for e in g.log[n0:] if e['m'].startswith('덱에서') and '세트' in e['m']]
            self.assertEqual(len(acts), 1, acts)
            self.assertEqual(len(sets), 1, sets)
            new = [x for x in g.p[0].s if x and x not in before]
            self.assertEqual(len(new), 1)
            self.assertTrue(new[0].has('아츠') and not new[0].faceup)  # 덱의 「아츠」 마법이 세트(뒷면)로
            self.assertEqual(len(g.deck_cards(0)), deck0 - 1)    # 1턴(선공)은 드로우 없음, 2턴은 상대 턴

    def test_sacrifice_settlement_is_an_activation_on_the_chain(self):
        # 희생제 4번: 「상대 턴의 종료 시」 저주 카운터를 전부 제거하고 제거한 수 × 300 대미지 (강제) — 체인에 올라가는 발동
        g = make('희생제', '소원의 분수')
        sk = g.p[0].skill
        g.add_counter(sk, '저주', 3)                              # 3개: 희생제 3번(4개가 되었을 때)은 유발되지 않는다
        for q in (0, 1):                                         # 희생제(자리 0) 턴 · 상대 턴
            self.assertEqual(g.turn_player, q)
            hp0 = g.p[0].hp
            n0 = len(g.log)
            g.play_turn()
            acts = [e['m'] for e in g.log[n0:] if '「희생제」 4번 효과 발동' in e['m']]
            if q == 0:                                           # 자신 턴의 종료 시: 처리 없음
                self.assertEqual(acts, [])
                self.assertEqual(sk.counters.get('저주'), 3)
                self.assertEqual(g.p[0].hp, hp0)
            else:                                                # 상대 턴의 종료 시: 3개 제거 · 900 대미지
                self.assertEqual(len(acts), 1, acts)
                self.assertFalse(sk.counters.get('저주'))
                self.assertEqual(g.p[0].hp, hp0 - 300 * 3)

    def test_chucky_responds_to_settlement_on_the_chain(self):
        # 희생제 4번 발동에 처키 1번(종료 단계에서만)으로 체인 — 처키가 먼저 처리되어 카운터 2개를 쓰고, 정산은 남은 카운터로만
        g = make('희생제', '소원의 분수')
        sk = g.p[0].skill
        chucky = on_field(g, '저주인형 - 처키', 0)
        target = on_field(g, '솔루나 시엘', 1)
        sk.counters['저주'] = 4                                  # 직접 놓는다: 희생제 3번(4개가 되었을 때)이 유발되지 않게

        class UseChucky(Idle):
            seen = None                                          # 처키를 발동할 때의 저주 카운터 수
            def respond(self, g, p, opts):
                if self.seen is None and any(l.card.name == '희생제' and l.eff.num == 4 for l in g.chain):
                    for c, e in opts:
                        if c is chucky and e.num == 1:
                            self.seen = sk.counters.get('저주', 0); return (c, e)
                return None
        g.p[0].ai = UseChucky('희생제')
        g.turn_player = 1                                        # 상대(자리 1)의 턴: 종료 단계에 희생제 4번이 발동한다
        hp0, hp1 = g.p[0].hp, g.p[1].hp
        n0 = len(g.log)
        g.play_turn()
        ms = [e['m'] for e in g.log[n0:]]
        idx = lambda s: next(i for i, m in enumerate(ms) if s in m)
        n = g.p[0].ai.seen
        self.assertIsNotNone(n)                                  # 체인에 희생제 4번이 있을 때 처키를 발동할 수 있었다
        self.assertLess(idx('「희생제」 4번 효과 발동'), idx('「저주인형 - 처키」 1번 효과 발동'))
        self.assertLess(idx('「저주인형 - 처키」 1번 처리'), idx('「희생제」 4번 처리'))   # 체인 역순 처리
        self.assertTrue(any(m == f'{target} 파괴' for m in ms[idx('「저주인형 - 처키」 1번 처리'):]))   # 처키가 대상을 파괴 (상대가 이후 되살릴 수 있어 위치 대신 기록으로 확인)
        self.assertEqual(g.p[1].hp, hp1 - 300)
        self.assertFalse(sk.counters.get('저주'))
        self.assertEqual(g.p[0].hp, hp0 - 300 * (n - 2))          # 처키 코스트 2개를 뺀 나머지만 정산


@unittest.skipUnless('데쿠마' in cards.POOL and '아나보케' in cards.POOL, RETIRED_MSG)
class AnabokeTest(unittest.TestCase):
    def test_anaboke_cannot_be_activated_without_decuma_on_chain(self):
        g = make('세제', '소원의 분수', skill_a='데쿠마')
        ana = new_card('아나보케', 0); ana.zone = 'hand'; g.p[0].hand.append(ana)
        g.phase = '종료'
        self.assertFalse(any(c.name == '아나보케' for c, e in g.options(0, ('quick',))))


# (번성충-기생 스킬의 종료 단계 테스트는 기생 축 삭제(사용자 지시 2026-10-13)와 함께 지움)


if __name__ == '__main__':
    unittest.main()

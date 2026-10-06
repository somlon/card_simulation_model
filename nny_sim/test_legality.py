"""규칙상 처리할 수 없는 행동의 사전 차단 테스트 (nny_sim 폴더에서):  python -m unittest test_legality -v"""
import random, unittest
import season as SE
from ai import HeuristicAI
from cards import Impl
from engine import Game, Card

DECKS = SE.load_decks()


def make(a, b):
    da, db = DECKS[a], DECKS[b]
    g = Game([dict(da, 이름='A'), dict(db, 이름='B')], [HeuristicAI(da['스킬']), HeuristicAI(db['스킬'])], 0, random.Random(5), [], Impl)
    g.setup(); g.turn = 3; g.turn_player = 0; g.phase = '진행'
    return g


def card(g, name, owner, zone):
    c = Card(Impl.pool[name], owner); Impl.attach(c); c.zone = zone
    if zone in ('hand', 'grave', 'main', 'upper'): getattr(g.p[owner], zone).append(c)
    return c


def strip_deck(g, p, keep):
    """덱을 keep(카드 이름 → 판정)만 남기고 비운다"""
    for z in ('main', 'upper'):
        lst = getattr(g.p[p], z)
        lst[:] = [c for c in lst if keep(c)]


class SameNameRuleTest(unittest.TestCase):
    def test_can_special_blocks_same_name_from_deck_while_that_card_is_the_source(self):
        g = make('세제', '투기장의 규칙')
        src = card(g, '세리 - 릭토르', 0, 'grave')
        same = card(g, '세리 - 릭토르', 0, 'main'); other = card(g, '세리 - 엑삭토르', 0, 'main')
        g.src = src
        self.assertFalse(g.can_special(same, 0))
        self.assertTrue(g.can_special(other, 0))
        g.src = None
        self.assertTrue(g.can_special(same, 0))           # 효과 주체가 없으면 같은 이름 규칙은 적용되지 않는다

    def test_seri_last_will_never_picks_a_same_name_card(self):
        g = make('세제', '투기장의 규칙')
        strip_deck(g, 0, lambda c: c.name in ('세리 - 릭토르', '세리 - 엑삭토르'))
        m = card(g, '세리 - 릭토르', 0, 'hand'); g._remove(m); g.place_monster(m, 0)
        n0 = len(g.log)
        g.destroy(m, ('rule', None)); g.triggers()
        if g.chain: g.resolve_chain()
        new = g.log[n0:]
        self.assertFalse(any('같은 이름의 카드를 덱에서 특수소환할 수 없음' in e['m'] for e in new))
        summoned = [e['m'] for e in new if '특수소환 (' in e['m']]
        self.assertTrue(summoned and '세리 - 엑삭토르' in summoned[0])

    def test_legality_check_restores_effect_source(self):
        g = make('세제', '투기장의 규칙')
        g.src = None
        g.options(0, ('ignition', 'quick'))
        self.assertIsNone(g.src)


class NoTargetActivationTest(unittest.TestCase):
    def test_dual_combat_needs_a_searchable_card(self):
        g = make('솔루나 아츠', '투기장의 규칙')
        dc = card(g, '솔루나 아츠 - 듀얼 컴뱃', 0, 'hand')
        self.assertTrue(any(c is dc for c, e in g.options(0, ('quick',))))
        strip_deck(g, 0, lambda c: not (c.has('시아') or c.has('시엘')))
        self.assertFalse(any(c is dc for c, e in g.options(0, ('quick',))))

    def test_rabbit_foot_needs_a_fighter_in_deck(self):
        g = make('투기장의 규칙', '세제')
        rf = card(g, '격투가 래빗 풋', 0, 'hand')
        self.assertTrue(any(c is rf for c, e in g.options(0, ('quick',))))
        strip_deck(g, 0, lambda c: not c.has('격투가'))
        self.assertFalse(any(c is rf for c, e in g.options(0, ('quick',))))

    def test_weevil_needs_a_spell_to_search(self):
        g = make('번성충-대발생', '세제')
        g.turn_player = 1                                    # 상대 턴의 진행 단계에 패에서 쓰는 카드
        w = card(g, '번성충-먹이바구미', 0, 'hand')
        self.assertTrue(any(c is w for c, e in g.options(0, ('quick',))))
        strip_deck(g, 0, lambda c: not (c.type == '마법' and c.has('번성충')))
        self.assertFalse(any(c is w for c, e in g.options(0, ('quick',))))


if __name__ == '__main__':
    unittest.main()

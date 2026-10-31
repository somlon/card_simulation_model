"""규칙상 처리할 수 없는 행동의 사전 차단 테스트 (nny_sim 폴더에서):  python -m unittest test_legality -v
2026-10-08 카드 풀 교체: 상대 덱 「투기장의 규칙」 → 현재 덱, 풀에서 빠진 카드(래빗 풋 · 먹이바구미)는 같은 판정을 쓰는 현재 카드로 옮김"""
import random, unittest
import season as SE
from ai import HeuristicAI
from cards import Impl, grp
from engine import Game, Card

DECKS = SE.load_decks()


def make(a, b):
    da, db = DECKS[a], DECKS[b]
    g = Game([dict(da, 이름='A'), dict(db, 이름='B')], [HeuristicAI(da['스킬']), HeuristicAI(db['스킬'])], 0, random.Random(5), [], Impl)
    g.setup(); g.turn = 3; g.turn_player = 0; g.phase = '진행'
    return g


def card(g, name, owner, zone):
    c = Card(Impl.pool[name], owner); Impl.attach(c); c.zone = zone
    if zone in ('hand', 'grave', 'main', 'upper', 'banish'): getattr(g.p[owner], zone).append(c)
    return c


def strip_deck(g, p, keep):
    """덱을 keep(카드 이름 → 판정)만 남기고 비운다"""
    for z in ('main', 'upper'):
        lst = getattr(g.p[p], z)
        lst[:] = [c for c in lst if keep(c)]


class SameNameRuleTest(unittest.TestCase):
    def test_can_special_blocks_same_name_from_deck_while_that_card_is_the_source(self):
        g = make('세제', '솔루나 아츠')
        src = card(g, '세리 - 릭토르', 0, 'grave')
        same = card(g, '세리 - 릭토르', 0, 'main'); other = card(g, '세리 - 엑삭토르', 0, 'main')
        g.src = src
        self.assertFalse(g.can_special(same, 0))
        self.assertTrue(g.can_special(other, 0))
        g.src = None
        self.assertTrue(g.can_special(same, 0))           # 효과 주체가 없으면 같은 이름 규칙은 적용되지 않는다

    def test_seri_last_will_never_picks_a_same_name_card(self):
        g = make('세제', '솔루나 아츠')
        strip_deck(g, 0, lambda c: c.name in ('세리 - 릭토르', '세리 - 엑삭토르'))
        for _ in range(3): card(g, '소환세', 0, 'banish')   # [유언] 코스트: 제외 존에서 3장 덱으로 (2026-10-08 텍스트) — 「세리」 몬스터가 아니라 소환 후보는 그대로
        m = card(g, '세리 - 릭토르', 0, 'hand'); g._remove(m); g.place_monster(m, 0)
        n0 = len(g.log)
        g.destroy(m, ('rule', None)); g.triggers()
        if g.chain: g.resolve_chain()
        new = g.log[n0:]
        self.assertFalse(any('같은 이름의 카드를 덱에서 특수소환할 수 없음' in e['m'] for e in new))
        summoned = [e['m'] for e in new if '특수소환 (' in e['m']]
        self.assertTrue(summoned and '세리 - 엑삭토르' in summoned[0])

    def test_legality_check_restores_effect_source(self):
        g = make('세제', '솔루나 아츠')
        g.src = None
        g.options(0, ('ignition', 'quick'))
        self.assertIsNone(g.src)


class NoTargetActivationTest(unittest.TestCase):
    def test_dual_combat_needs_a_searchable_card(self):
        g = make('솔루나 아츠', '세제')
        dc = card(g, '솔루나 아츠 - 듀얼 컴뱃', 0, 'hand')
        self.assertTrue(any(c is dc for c, e in g.options(0, ('quick',))))
        strip_deck(g, 0, lambda c: not (c.has('시아') or c.has('시엘')))
        self.assertFalse(any(c is dc for c, e in g.options(0, ('quick',))))

    def test_unwritten_rule_needs_a_curse_in_deck(self):
        # 옛 「격투가 래빗 풋」(패에서 발동 · 덱 서치) 테스트를 옮김: 서치할 카드가 덱에 없으면 패에서 발동 후보가 아니다
        g = make('희생제', '세제')
        ur = card(g, '저주 - 불문율', 0, 'hand')
        self.assertTrue(any(c is ur for c, e in g.options(0, ('ignition',))))
        strip_deck(g, 0, lambda c: not grp(c, '저주'))
        self.assertFalse(any(c is ur for c, e in g.options(0, ('ignition',))))

    def test_wish_needs_a_coin_to_search(self):
        # 옛 「번성충-먹이바구미」(상대 턴에 패에서 발동 · 덱 서치) 테스트를 옮김: 「소망」 [트리거] 상대가 효과를 발동했을 때 · 덱에서 「코인」 서치
        g = make('소원의 분수', '세제')
        g.turn_player = 1                                    # 상대 턴의 진행 단계에 패에서 쓰는 카드
        w = card(g, '소망', 0, 'hand')
        tax = card(g, '소환세', 1, 'hand')
        self.assertTrue(g.activate(1, tax, tax.effects[0]))  # 상대의 효과 발동 → 체인 1
        self.assertTrue(any(c is w for c, e in g.options(0, ('resp',), ev=g.chain)))
        strip_deck(g, 0, lambda c: not grp(c, '코인'))
        self.assertFalse(any(c is w for c, e in g.options(0, ('resp',), ev=g.chain)))


if __name__ == '__main__':
    unittest.main()

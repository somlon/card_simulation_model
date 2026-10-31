"""2026-10-29 사용자 지시 수정 테스트 (nny_sim 폴더에서):  python3 -m unittest test_play_fixes -v
① 놓을 존 고르기 훅(Game.pick_zone — choose_zone 을 가진 플레이어만 고르고, AI는 첫 빈칸 그대로)
② 번성충-메뚜기여왕 1번: 상대 필드의 몬스터만 릴리스
③ 호박옥 - 아우렘 티라누스 4번: 상대 필드에 카드가 없어도 봉인 카운터가 있으면 발동(아무것도 파괴하지 않음)
⑤ 덱 규칙: 전략 덱 카드는 주 스킬 또는 전략 덱의 스킬 카드 태그에 맞으면 된다"""
import random, unittest
import season as SE
import deck as D
from ai import HeuristicAI
from cards import Impl, POOL
from engine import Game, Card

DECKS = SE.load_decks()


def make(a, b, ais=None):
    da, db = DECKS[a], DECKS[b]
    g = Game([dict(da, 이름='A'), dict(db, 이름='B')], ais or [HeuristicAI(da['스킬']), HeuristicAI(db['스킬'])], 0, random.Random(5), [], Impl)
    g.setup(); g.turn = 3; g.turn_player = 0; g.phase = '진행'
    return g


def card(g, name, owner, zone, slot=None):
    c = Card(Impl.pool[name], owner); Impl.attach(c); c.zone = zone; c.controller = owner
    if zone in ('hand', 'grave', 'main', 'upper', 'banish'): getattr(g.p[owner], zone).append(c)
    if zone in ('m', 's'): getattr(g.p[owner], zone)[slot] = c
    return c


def by_code(code):
    return next(n for n, d in POOL.items() if d.get('code') == code)


def eff(c, num):
    return next(e for e in c.effects if e.num == num)


class Picker(HeuristicAI):
    """놓을 존을 직접 고르는 플레이어(사람 자리 대역): 후보 중 정해 둔 것"""
    def __init__(self, skill, want):
        super().__init__(skill); self.want = want; self.asked = []

    def choose_zone(self, g, p, c, kind, opts):
        self.asked.append((kind, list(opts)))
        return self.want if self.want in opts else opts[-1]


class ZoneTest(unittest.TestCase):
    def test_ai_without_hook_uses_first_free_slot(self):
        g = make('투기장의 규칙', '세제')
        m = next(c for c in g.p[0].hand + g.p[0].main if c.is_monster())
        g._remove(m); self.assertTrue(g.place_monster(m, 0))
        self.assertIs(g.p[0].m[0], m); self.assertEqual(m.zone, 'm')

    def test_picker_chooses_monster_slot_and_shared_zone(self):
        sk = DECKS['투기장의 규칙']['스킬']
        g = make('투기장의 규칙', '세제', [Picker(sk, 2), HeuristicAI(DECKS['세제']['스킬'])])
        m = next(c for c in g.p[0].hand + g.p[0].main if c.is_monster())
        g._remove(m); g.place_monster(m, 0)
        self.assertIs(g.p[0].m[2], m)
        self.assertEqual(g.p[0].ai.asked[-1], ('monster', [0, 1, 2, 'shared0', 'shared1']))   # 몬스터 존 3칸 + 빈 공유 존 2칸(사용자 지시 2026-10-30)
        g.p[0].ai.want = 'shared1'
        m2 = next(c for c in g.p[0].hand + g.p[0].main if c.is_monster() and c is not m)
        g._remove(m2); g.place_monster(m2, 0)
        self.assertIs(g.shareds[1], m2); self.assertEqual(g.shared_owners, [None, 0])   # 마커는 칸마다

    def test_picker_chooses_spell_slot(self):
        sk = DECKS['투기장의 규칙']['스킬']
        g = make('투기장의 규칙', '세제', [Picker(sk, 2), HeuristicAI(DECKS['세제']['스킬'])])
        s = next(c for c in g.p[0].hand + g.p[0].main if c.type == '마법')
        g._remove(s); g.place_spell(s, 0)
        self.assertIs(g.p[0].s[2], s); self.assertEqual(g.p[0].ai.asked[-1], ('spell', [0, 1, 2, 3, 4]))


class LocustQueenTest(unittest.TestCase):
    def test_releases_only_opponent_monsters(self):
        g = make('번성충-대발생', '투기장의 규칙')   # 세제의 세리 - 두플리카토르는 코스트 2배라 상대 몬스터 1장으로는 발동할 수 없다
        queen = card(g, by_code('SWRM-004'), 0, 'hand')
        e1 = eff(queen, 1)
        spell = next(c for c in g.p[1].hand + g.p[1].main if c.type == '마법')
        g.p[1].main.remove(spell) if spell in g.p[1].main else g.p[1].hand.remove(spell)
        spell.zone = 's'; spell.controller = 1; g.p[1].s[0] = spell
        self.assertFalse(g.legal(0, queen, e1), '상대 필드에 마법 카드만 있으면 발동할 수 없다(몬스터만 릴리스)')
        mon = next(c for c in g.p[1].hand + g.p[1].main if c.is_monster())
        (g.p[1].main if mon in g.p[1].main else g.p[1].hand).remove(mon)
        mon.zone = 'm'; mon.controller = 1; mon.faceup = True; g.p[1].m[0] = mon
        self.assertTrue(g.legal(0, queen, e1))


class TyrannusTest(unittest.TestCase):
    def test_effect4_activates_with_empty_opponent_field_and_destroys_nothing(self):
        g = make('호박옥 - 몽식의 계약', '세제')
        t = card(g, by_code('AMBR-001'), 0, 'm', 0); t.faceup = True; t.counters['봉인'] = 3
        e4 = eff(t, 4)
        self.assertFalse(any(g.p[1].m) or any(g.p[1].s) or any(g.shareds) or g.fieldz)
        self.assertTrue(g.legal(0, t, e4), '봉인 카운터가 있으면 상대 필드가 비어도 발동할 수 있다')
        grave1 = len(g.p[1].grave)
        self.assertTrue(g.activate(0, t, e4)); g.resolve_chain()
        self.assertLess(t.counters.get('봉인', 0), 3)          # 1개 이상 제거
        self.assertEqual(len(g.p[1].grave), grave1)          # 아무것도 파괴하지 않음

    def test_effect4_needs_counters(self):
        g = make('호박옥 - 몽식의 계약', '세제')
        t = card(g, by_code('AMBR-001'), 0, 'm', 0); t.faceup = True
        self.assertFalse(g.legal(0, t, eff(t, 4)))


class StrategySkillTagTest(unittest.TestCase):
    def base_deck(self):
        d = DECKS['투기장의 규칙']
        return {'이름': 't', '스킬': d['스킬'], '메인': [list(x) for x in d['메인']], '상급': [list(x) for x in d['상급']], '전략': []}

    def other(self, skill):
        """주 스킬에는 맞지 않고 skill 에는 맞는 메인 덱 카드"""
        me = self.base_deck()['스킬']
        return next(n for n, c in sorted(POOL.items()) if c['type'] != '스킬' and c.get('deck') == '메인' and 1 <= (c.get('level') or 1) <= 10
                    and set(c['tags']) & D.skill_allowed(POOL[skill]) and not set(c['tags']) & D.skill_allowed(POOL[me]))

    def test_strategy_card_may_fit_a_strategy_skill_card(self):
        d = self.base_deck(); s2 = next(n for n in sorted(POOL) if POOL[n]['type'] == '스킬' and n != d['스킬'])
        x = self.other(s2)
        d['전략'] = [[1, x]]
        self.assertTrue(any(x in e for e in D.validate(d, policy=False)[0]), '전략 덱에 그 스킬 카드가 없으면 오류')
        d['전략'] = [[1, s2], [1, x]]
        self.assertFalse(any(x in e for e in D.validate(d, policy=False)[0]), '전략 덱의 스킬 카드 태그에 맞으면 전략 덱에 넣을 수 있다')
        d['메인'].append([1, x])
        self.assertTrue(any(x in e and '[메인]' in e for e in D.validate(d, policy=False)[0]), '메인 · 상급 덱은 주 스킬 태그만')


if __name__ == '__main__':
    unittest.main()

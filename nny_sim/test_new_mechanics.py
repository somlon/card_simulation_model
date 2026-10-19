"""2026-10-08 카드 텍스트로 새로 생긴 메커니즘 테스트 (nny_sim 폴더에서):  python -m unittest test_new_mechanics -v
- 소원의 분수: 덱에서 묘지로(dump) · [유언] 단서 · 간절한 마음 · 스킬 1번 · 기적의 영웅
- 저주인형: 희생제 1 · 3 · 4번, 퇴마의 부적 2번 효과 변경, 저주인형 3장 특수 승리, 비비안 발동 횟수 제한
- 아츠: 2번은 1번 처리 시 자동 처리 · 1턴 1회 · 1번 무효 시 함께 무효
- 세리 [유언] 코스트, 고정 카드(deck.LOCKED)"""
import random, unittest
import season as SE
import deck as D, deck_opt as DO, match as M
from ai import HeuristicAI
from cards import Impl, POOL
from engine import Game, Card, GameOver

DECKS = SE.load_decks()


class Idle(HeuristicAI):
    """아무 것도 하지 않는 AI (트리거 · 대응 · 행동 없음) — 테스트가 직접 조작한다"""
    def respond(self, g, p, opts): return None
    def choose_triggers(self, g, p, cands): return [(c, e, ev) for c, e, ev in cands if e.mandatory]
    def main_phase(self, g, p, ph): return None
    def battle_phase(self, g, p): return None
    def mulligan(self, g, p, hand): return []


class Yes(Idle):
    """임의 트리거도 모두 발동"""
    def choose_triggers(self, g, p, cands): return list(cands)


def make(a, b, ai=Idle, seed=5):
    da, db = DECKS[a], DECKS[b]
    g = Game([dict(da, 이름='A'), dict(db, 이름='B')], [ai(da['스킬']), ai(db['스킬'])], 0, random.Random(seed), [], Impl)
    g.setup(); g.turn = 3; g.turn_player = 0; g.phase = '진행'
    return g


def card(g, name, owner, zone):
    c = Card(Impl.pool[name], owner); Impl.attach(c); c.zone = zone
    if zone in ('hand', 'grave', 'main', 'upper', 'banish'): getattr(g.p[owner], zone).append(c)
    return c


def on_field(g, name, owner):
    c = card(g, name, owner, None); g.place_monster(c, owner); return c


def run_triggers(g):
    g.triggers()
    if g.chain: g.resolve_chain()


def eff(c, num):
    return next(e for e in c.effects if e.num == num)


# ═══════════════════════ 소원의 분수 ═══════════════════════
class WishTest(unittest.TestCase):
    def test_dump_moves_top_cards_with_grave_events(self):
        g = make('소원의 분수', '세제')
        top = list(g.p[0].main[-2:]); n0 = len(g.p[0].main)
        g.events = []
        out = g.dump(0, 2, '시험')
        self.assertEqual(set(map(id, out)), set(map(id, top)))
        self.assertEqual(len(g.p[0].main), n0 - 2)
        evs = [e for e in g.events if e['kind'] == 'to_grave']
        self.assertEqual(len(evs), 2)
        self.assertTrue(all(e['prev'] == 'main' and e['card'].zone == 'grave' for e in evs))

    def test_coin_last_will_not_from_deck_but_from_hand(self):
        g = make('소원의 분수', '세제', ai=Yes)
        coin = card(g, '코인 - 행운의 네잎클로버', 0, 'main')          # 맨 위
        g.events = []; g.dump(0, 1, '시험')
        self.assertIs(coin.zone, 'grave')
        self.assertFalse(g.legal(0, coin, eff(coin, 2), g.events[-1]))  # 덱에서 묘지로 → [유언] 발동하지 않음
        g.events = []
        coin2 = card(g, '코인 - 행운의 네잎클로버', 0, 'hand')
        g.L('---'); n0 = len(g.log); grave0 = len(g.p[0].grave)
        g.act(0, coin2, eff(coin2, 1))                                    # 1번: 패에서 공개하고 버린다 → [유언]
        msgs = [e['m'] for e in g.log[n0:]]
        self.assertIs(coin2.zone, 'grave')
        self.assertTrue(any('「코인 - 행운의 네잎클로버」 2번 효과 발동' in m for m in msgs))
        self.assertGreaterEqual(len(g.p[0].grave), grave0 + 1 + 2)       # 자신 + 덱 위 2장

    def test_gambler_last_will_from_deck_searches_luck(self):
        g = make('소원의 분수', '세제', ai=Yes)
        gam = card(g, '행운의 도박사', 0, 'main')
        hand0 = len(g.p[0].hand)
        g.dump(0, 1, '시험'); run_triggers(g)
        new = g.p[0].hand[hand0:]
        self.assertTrue(new and all('행운' in x.d['groups'] for x in new))

    def test_earnest_heart_adds_one_card(self):
        g = make('소원의 분수', '세제')
        f = card(g, '간절한 마음', 0, None); g.place_field(f, 0)
        self.assertGreaterEqual(len(g.p[0].main), 10)
        out = g.dump(0, 2, '시험')
        self.assertEqual(len(out), 3)

    def _fill_grave(self, g):
        for name in ('행운의 도박사', '행운의 카드 - 조커', '용기의 모험가', '용기의 무기 - 검',
                     '지혜의 사서', '지혜의 원천 - 마도서', '희생의 의사', '희생의 상징 - 펜던트'):
            card(g, name, 0, 'grave')

    def test_skill_summons_hero_and_hero_rules(self):
        g = make('소원의 분수', '솔루나 아츠')   # 세제(서로 발동마다 1장 제외)가 아닌 상대 — 제외 매수를 정확히 세기 위해
        self._fill_grave(g)
        sk = g.p[0].skill; e1 = eff(sk, 1)
        self.assertTrue(g.legal(0, sk, e1))
        ban0 = len(g.p[0].banish)
        g.act(0, sk, e1)
        hero = next(m for m in g.monsters(0) if m.name == '기적의 영웅')
        self.assertEqual(len(g.p[0].banish), ban0 + 8)
        # 다른 카드의 효과로는 특수소환할 수 없다
        other = card(g, '기적의 영웅', 0, 'upper')
        g.src = card(g, '희생의 성녀', 0, 'grave')
        self.assertFalse(g.can_special(other, 0))
        g.src = None
        # 다른 카드의 효과를 받지 않는다
        self.assertTrue(g.immune(hero, 1)); self.assertTrue(g.immune(hero, 0))
        # 3 · 4번은 공격력이 0이 되면 더는 발동할 수 없다 (합쳐 3번)
        for i in range(3):
            t = card(g, '세리 - 엑삭토르', 1, None); g.place_monster(t, 1)
            self.assertTrue(g.legal(0, hero, eff(hero, 3)), i)
            g.act(0, hero, eff(hero, 3))
        t = card(g, '세리 - 엑삭토르', 1, None); g.place_monster(t, 1)
        self.assertEqual(g.atk(hero), 0)
        self.assertFalse(g.legal(0, hero, eff(hero, 3)))


# ═══════════════════════ 저주인형 ═══════════════════════
class DollTest(unittest.TestCase):
    def test_talisman_placed_in_opponent_zone_at_start(self):
        g = make('희생제', '세제')
        tal = [x for x in g.spells(1) if x.name == '퇴마의 부적']
        self.assertEqual(len(tal), 1)
        self.assertEqual(tal[0].controller, 1); self.assertEqual(tal[0].owner, 0)
        self.assertFalse(any(x.name == '퇴마의 부적' for x in g.p[0].main + g.p[0].upper))

    def test_sacrifice_3_triggers_on_crossing_four_within_one_chain(self):
        g = make('희생제', '세제', ai=Yes)
        sk = g.p[0].skill
        sk.counters['저주'] = 2
        up0 = len(g.p[0].upper)
        g.events = []
        g.add_counter(sk, '저주', 1); g.add_counter(sk, '저주', 1); g.add_counter(sk, '저주', 1)   # 3 → 4 → 5 를 한 묶음으로
        run_triggers(g)
        self.assertEqual(len(g.p[0].upper), up0 - 1)

    def test_sacrifice_4_settles_at_opponent_turn_end(self):
        g = make('희생제', '세제')
        sk = g.p[0].skill; sk.counters['저주'] = 3
        hp0 = g.p[0].hp
        g.turn_player = 1; g.phase = '종료'
        g.emit('end_phase', player=1); run_triggers(g)
        self.assertEqual(g.p[0].hp, hp0 - 900)
        self.assertFalse(sk.counters.get('저주'))

    def test_talisman_replaces_next_effect_and_can_destroy_ace(self):
        g = make('희생제', '세제')
        tal = next(x for x in g.spells(1) if x.name == '퇴마의 부적')
        tal.counters['퇴마'] = 4
        ace = on_field(g, '저주인형 - 저주인형', 0)
        self.assertTrue(g.immune(ace, 1))                       # 부적 이외의 효과는 받지 않는다
        src = card(g, '소환세', 1, 'hand')
        g.turn_player = 1
        link = g.activate(1, src, eff(src, 1))
        self.assertIsNotNone(link.replaced)
        g.resolve_chain()
        self.assertFalse(g.on_field(ace))
        self.assertEqual(tal.counters.get('퇴마', 0), 0)

    def test_doubt_negates_pending_talisman_effect_then_goes_to_grave(self):
        # 설계도 확정(2026-10-10): 의심은 처리를 기다리는 부적의 효과(바뀐 효과 포함)를 무효로 하고, 쓰고 나면 묘지로 간다.
        # 부적 1번 「상대의 「저주 - 의심」 마법 이외의 카드의 효과를 받지 않는다」 — 미러전: 자기 의심은 자기가 컨트롤하는 부적에 듣지 않는다
        g = make('희생제', '희생제')
        mine = next(x for x in g.spells(0) if x.name == '퇴마의 부적')
        theirs = next(x for x in g.spells(1) if x.name == '퇴마의 부적')
        d = card(g, '저주 - 의심', 0, 'hand')
        self.assertFalse(g.legal(0, d, eff(d, 1)))              # 처리를 기다리는 부적 효과가 없으면 처리할 수 없으므로 발동 불가
        mine.counters['퇴마'] = 4; theirs.counters['퇴마'] = 4
        own = card(g, '소환세', 0, 'hand')
        own_link = g.activate(0, own, eff(own, 1))               # 0의 발동 → 0이 컨트롤하는 부적(mine)이 바꿈
        self.assertIsNotNone(own_link.replaced)
        self.assertFalse(g.legal(0, d, eff(d, 1)))              # 자기 의심은 자기 부적의 바뀐 효과를 무효로 하지 못한다
        g.chain.clear(); mine.flags.pop('replace_pending', None); mine.counters.clear()   # mine이 다음 발동(의심)을 바꾸지 않게
        g.turn_player = 1
        src = card(g, '소환세', 1, 'hand')
        link = g.activate(1, src, eff(src, 1))                   # 1의 발동 → theirs가 바꿈
        self.assertIsNotNone(link.replaced)
        g.turn_player = 0                                        # (패의 신속 마법은 자신 턴에 발동 — 시점 규칙과 별개로 처리만 확인)
        self.assertTrue(g.legal(0, d, eff(d, 1)))
        g.activate(0, d, eff(d, 1)); g.resolve_chain()
        self.assertTrue(link.negated)
        self.assertEqual(theirs.counters.get('퇴마', 0), 4)      # 바뀐 효과가 무효 — 카운터 그대로
        self.assertEqual(d.zone, 'grave')                        # 의심은 처리 후 묘지로
        self.assertFalse(theirs.flags.get('perma_neg'))

    def test_third_ace_banished_wins(self):
        g = make('희생제', '세제')
        for _ in range(2): card(g, '저주인형 - 저주인형', 0, 'banish')
        ace = on_field(g, '저주인형 - 저주인형', 0)
        with self.assertRaises(GameOver) as cm:
            g.act(0, ace, eff(ace, 2))
        self.assertEqual(cm.exception.winner, 0)

    def test_vivian_limits_opponent_activations(self):
        g = make('희생제', '세제')
        g.p[0].skill.counters['저주'] = 4
        viv = on_field(g, '저주인형 - 비비안', 0)
        g.phase = '종료'
        self.assertTrue(g.legal(0, viv, eff(viv, 1)))
        g.act(0, viv, eff(viv, 1))
        self.assertEqual(g.act_limit.get(1), (g.turn + 1, 4))
        g.turn += 1; g.turn_player = 1; g.phase = '진행'
        c = card(g, '소환세', 1, 'hand')
        g.act_count[(1, g.turn)] = 4
        self.assertFalse(g.legal(1, c, eff(c, 1)))
        g.act_count[(1, g.turn)] = 3
        self.assertTrue(g.legal(1, c, eff(c, 1)))


# ═══════════════════════ 아츠 2번 ═══════════════════════
class ArtsRuleTest(unittest.TestCase):
    def _game(self):
        g = make('솔루나 아츠', '세제')
        for c in g.all_field(): g._remove(c)
        g.p[0].hand.clear()   # 성광난무 1번은 패의 「시아」 수만큼 파괴 — 패를 비워 처리 결과를 고정
        return g

    def test_second_effect_resolves_with_first_once_per_turn(self):
        g = self._game()
        sia = on_field(g, '솔루나 시아', 0); ciel = on_field(g, '솔루나 시엘', 0)
        for _ in range(3): on_field(g, '세리 - 엑삭토르', 1)
        hand0 = len(g.p[0].hand)
        a1 = card(g, '시아 아츠 - 성광난무', 0, 'hand')
        n0 = len(g.log)
        g.act(0, a1, eff(a1, 1))
        msgs = [e['m'] for e in g.log[n0:]]
        self.assertTrue(any('2번 처리' in m for m in msgs))           # 시엘이 있으므로 2번도 처리
        self.assertEqual(g.p[0].opt.get(('시아 아츠 - 성광난무', 2)), 1)

    def test_second_effect_needs_condition_at_resolution(self):
        g = self._game()
        sia = on_field(g, '솔루나 시아', 0)
        on_field(g, '세리 - 엑삭토르', 1)
        a1 = card(g, '시아 아츠 - 성광난무', 0, 'hand')
        n0 = len(g.log)
        g.act(0, a1, eff(a1, 1))
        self.assertFalse(any('2번 처리' in e['m'] for e in g.log[n0:]))   # 시엘 없음

    def test_negated_first_effect_takes_second_with_it(self):
        g = self._game()
        on_field(g, '솔루나 시아', 0); on_field(g, '솔루나 시엘', 0)
        on_field(g, '세리 - 엑삭토르', 1)
        a1 = card(g, '시아 아츠 - 성광난무', 0, 'hand')
        link = g.activate(0, a1, eff(a1, 1))
        g.negate(link)
        n0 = len(g.log)
        g.resolve_chain()
        self.assertFalse(any('2번 처리' in e['m'] for e in g.log[n0:]))
        self.assertFalse(g.p[0].opt.get(('시아 아츠 - 성광난무', 2)))   # 2번 1턴 1회를 쓰지 않았다

    def test_sia_3_activates_without_ciel_and_does_nothing(self):
        g = self._game()
        sia = on_field(g, '솔루나 시아', 0)
        src = card(g, '소환세', 1, 'hand'); g.turn_player = 1
        link = g.activate(1, src, eff(src, 1))
        self.assertTrue(g.legal(0, sia, eff(sia, 3), g.chain))
        g.activate(0, sia, eff(sia, 3), g.chain[-1])
        g.resolve_chain()
        self.assertFalse(link.negated)


# ═══════════════════════ 세리 · 덱 ═══════════════════════
class SeriAndDeckTest(unittest.TestCase):
    def test_seri_last_will_needs_three_banished(self):
        g = make('세제', '솔루나 아츠')
        g.p[0].banish.clear()
        m = card(g, '세리 - 릭토르', 0, 'grave')
        ev = {'kind': 'to_grave', 'card': m, 'prev': 'm', 'ctrl': 0, 'cause': ('rule', None)}
        self.assertFalse(g.legal(0, m, eff(m, 2), ev))
        for _ in range(3): card(g, '소환세', 0, 'banish')
        self.assertTrue(g.legal(0, m, eff(m, 2), ev))

    def test_locked_talisman(self):
        st = DO.state_from_deck(DECKS['희생제'])
        self.assertTrue(DO.valid('희생제', st['counts'], st['strat']))
        c = dict(st['counts']); c['퇴마의 부적'] = 0
        self.assertFalse(DO.valid('희생제', c, st['strat']))
        nb = DO.neighbors('희생제', st['counts'], st['strat'], random.Random(1))
        self.assertTrue(all(cnt.get('퇴마의 부적', 0) == 1 for _, cnt, _ in nb))
        act = M.counts_of(DECKS['희생제'])
        self.assertNotIn('퇴마의 부적', M.swap_outs(act, '저주 - 재앙'))


class BanishReturn(unittest.TestCase):
    """월영침식 코스트로 「턴 종료 시까지 제외」된 시엘이 턴 종료 시 돌아올 자리 (F19)"""
    def _banished_ciel(self, g):
        c = card(g, '솔루나 시엘', 0, 'banish'); c.flags['return_from_banish'] = g.turn + 1   # play_turn이 턴을 1 올린다
        return c

    def test_returns_to_free_zone(self):
        g = make('솔루나 아츠', '세제'); c = self._banished_ciel(g)
        g.play_turn()
        self.assertIn(c.zone, ('m', 'shared')); self.assertNotIn(c, g.p[0].banish)

    def test_no_zone_left_goes_to_grave(self):
        g = make('솔루나 아츠', '세제'); c = self._banished_ciel(g)
        for _ in range(5): on_field(g, '솔루나 시아', 0)
        s = card(g, '솔루나 시아', 1, None); g.place_monster(s, 1)   # 상대가 공유 존까지 채운 상태
        if s.zone != 'shared': g._remove(s); g.shared = s; s.zone = 'shared'; s.controller = 1
        g.play_turn()
        self.assertEqual(c.zone, 'grave'); self.assertIn(c, g.p[0].grave); self.assertNotIn(c, g.p[0].banish)


if __name__ == '__main__':
    unittest.main()

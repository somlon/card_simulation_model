"""행동 세금 재정(사용자 답변 2026-10-27 · 10-28) 테스트 (nny_sim 폴더에서):  python -m unittest test_rulings_1028 -v
세 - 아이라리움 1번 · 세제 1번 · 취득세 1번 「서로가 …할 때마다, 그 플레이어는 자신의 덱의 위에서부터 카드를 n장 제외한다」 = 그 행동을 하는 플레이어가 내는 코스트:
- 자신이 발동한 효과의 처리에서 반드시 하는 행동은 발동할 때, 조건 · 선택이 붙은 행동 · 상대 효과로 하는 행동 · 턴 시작 드로우는 행동 직전에
- 1번에 n장 (한 발동의 처리 안에서는 플레이어 · 행동마다 1번) · 두플리카토르 2배 · 델레가토르 상대가 대신
- 덱이 모자라도 발동 · 행동할 수 있고, 두 덱을 합쳐도 모자라면 지불한 플레이어가 덱아웃 패배"""
import unittest
import cards as C
from cards import POOL, VETO
from engine import Effect, GameOver, Link
from test_new_mechanics import make, card, on_field, eff


def field_card(g, name, owner):
    """필드 카드 · 지속 마법을 앞면으로 놓는다"""
    c = card(g, name, owner, None)
    if c.type == '필드': g.place_field(c, owner)
    else: g.place_spell(c, owner, True)
    return c


def banished(g):
    return len(g.p[0].banish), len(g.p[1].banish)


def keep_decks(g, p, main, upper):
    """p의 덱을 메인 main장 · 상급 upper장으로 줄인다"""
    del g.p[p].main[main:]; del g.p[p].upper[upper:]


# ═══════════════════════ 카드 텍스트 판정 ═══════════════════════
class TaxTextTest(unittest.TestCase):
    def test_action_taxes_from_text(self):
        self.assertEqual(C.action_taxes(POOL['세 - 아이라리움']), [(1, 'draw', 2)])
        self.assertEqual(C.action_taxes(POOL['세제']), [(1, 'activate', 1)])
        self.assertEqual(C.action_taxes(POOL['취득세']), [(1, 'special', 2)])
        self.assertEqual(C.action_taxes(POOL['격투가 래빗 풋']), [])

    def test_sure_acts(self):
        cases = [('격투가 래빗 풋', 1, {'draw'}),                 # 덱에서 패에 넣는다
                 ('행운의 도적', 1, {'draw'}),                    # 1장은 반드시 드로우 (추가 드로우는 같은 발동)
                 ('스트플을 원하는 시골쥐', 2, {'draw'}),         # 「3장까지 되돌리고」 다음의 드로우는 반드시
                 ('솔루나 아츠 - 듀얼 컴뱃', 1, {'draw'}),
                 ('데이터버그 백업', 1, {'draw', 'special'}),
                 ('데이터버그 다운로드', 1, {'special'}),
                 ('행운의 카드 - 조커', 1, set()),                 # 「…경우, 드로우」
                 ('영웅의 조건 - 행운', 2, set()),                 # 「특수소환하거나 패에 넣는다」
                 ('격투가 입장', 1, set()),                        # 「패에 넣거나 특수소환한다」
                 ('호박옥의 수호자 - 실렉스', 3, set()),           # 「덱/묘지에서」
                 ('투기장의 규칙', 3, set()),                      # 「원하는 수까지 … 그 수만큼 드로우」
                 ('번성충-대장정', 1, set()),                      # 「확인하고 그 중 … 패에 넣고」
                 ('번성충-맵시기생벌', 1, set()),                  # 「…벗어났을 경우」 (나중에)
                 ('번성충-먹이바구미', 1, set()),                  # 「…때마다」
                 ('던전마스터 트랩퍼', 3, set()),                  # 「상대는 … 드로우」
                 ('번성충-노린재', 1, set()),                      # 바꾼 뒤의 효과 문장
                 ('트랩: 깜짝상자', 1, set()),                     # 바꾼 뒤의 효과 문장(안에 카드 이름 「」)
                 ('데이터버그 로딩', 1, set()),                    # 발동 선언이 없는 효과
                 ('데이터버그 앤트', 2, set())]                    # 「가능한 만큼」
        for name, num, want in cases:
            line = next(l for l in POOL[name]['text'].split('\n') if l.startswith(f'{num}.'))
            self.assertEqual(set(C.sure_acts(line)), want, name)

    def test_attached_to_cards(self):
        g = make('투기장의 규칙', '데이터버그 패키지 프로그램')
        a = card(g, '세 - 아이라리움', 0, 'hand')
        self.assertEqual(a.action_tax, [(1, 'draw', 2)])
        self.assertEqual(eff(a, 0).sure_acts, frozenset())               # 0번(카드를 놓는 발동)은 [지속] 문장을 처리로 보지 않는다
        self.assertEqual(eff(card(g, '격투가 래빗 풋', 0, 'hand'), 1).sure_acts, frozenset({'draw'}))


# ═══════════════════════ 세 - 아이라리움 1번 (드로우 · 덱에서 패에 넣기) ═══════════════════════
class AilariumTest(unittest.TestCase):
    def setUp(self):
        self.g = make('투기장의 규칙', '데이터버그 패키지 프로그램')   # 두 덱 모두 세금 스킬이 없다
        self.a = field_card(self.g, '세 - 아이라리움', 1)              # 「서로가」 — 컨트롤러와 관계없이 두 플레이어 모두

    def test_sure_search_pays_at_activation(self):
        g = self.g
        r = card(g, '격투가 래빗 풋', 0, 'hand'); e = eff(r, 1)
        b0 = banished(g)
        link = g.activate(0, r, e)
        self.assertEqual(banished(g), (b0[0] + 2, b0[1]))              # 발동할 때 코스트로 2장
        self.assertEqual(link.ctx['taxed'], {(0, 'draw')})
        h0 = len(g.p[0].hand)
        g.resolve_chain()
        self.assertEqual(banished(g), (b0[0] + 2, b0[1]))              # 처리 때 덱에서 패에 넣어도 다시 내지 않는다
        self.assertEqual(len(g.p[0].hand), h0)                         # 1장 넣고 1장 버림

    def test_turn_draw_pays_right_before(self):
        g = self.g
        top3 = g.p[0].main[-3:]
        g.draw(0, 1, 'main', cause=('rule', None))                     # 턴 시작 드로우도 포함
        self.assertIn(top3[0], g.p[0].hand)                            # 위 2장을 먼저 제외하고 그다음 카드를 드로우
        self.assertTrue(all(x in g.p[0].banish for x in top3[1:]))

    def test_opponent_forced_draw_paid_by_drawer(self):
        g = self.g
        x = card(g, '던전마스터 트랩퍼', 1, 'grave'); e = eff(x, 3)   # [유언] 상대는 카드를 1장 드로우한다
        b0 = banished(g); h0 = len(g.p[0].hand)
        g.activate(1, x, e)
        self.assertEqual(banished(g), b0)                              # 발동한 쪽(1)은 드로우하지 않는다
        g.resolve_chain()
        self.assertEqual(len(g.p[0].hand), h0 + 1)
        self.assertEqual(banished(g), (b0[0] + 2, b0[1]))              # 드로우하는 쪽(0)이 직전에 낸다

    def test_once_per_resolution(self):
        g = self.g
        b0 = banished(g)
        g.acting_link = Link(card(g, '행운의 카드 - 조커', 0, 'hand'), Effect(1, 'ignition'), 0, {})
        try:
            g.draw(0, 1, 'main'); g.draw(0, 1, 'main')                 # 한 발동의 처리 안의 드로우 · 덱→패는 1번만
            g.to_hand(g.p[0].main[-1])
        finally: g.acting_link = None
        self.assertEqual(banished(g), (b0[0] + 2, b0[1]))
        g.draw(0, 1, 'main')                                           # 다른 행동 — 다시 낸다
        self.assertEqual(banished(g), (b0[0] + 4, b0[1]))

    def test_chosen_deck_card_is_not_taxed(self):
        g = self.g
        x = g.p[0].main[-1]                                            # 맨 위 카드를 덱에서 패에 넣는다
        g.to_hand(x)
        self.assertIn(x, g.p[0].hand)
        self.assertNotIn(x, g.p[0].banish)

    def test_shortfall_of_both_decks_loses(self):
        g = self.g
        keep_decks(g, 0, 1, 0)
        with self.assertRaises(GameOver) as cm: g.draw(0, 1, cause=('rule', None))
        self.assertEqual(cm.exception.winner, 1)
        self.assertIn('덱아웃', cm.exception.reason)

    def test_other_deck_fills_shortfall(self):
        g = self.g
        keep_decks(g, 0, 1, 1)                                         # 한 덱으로는 모자라도 두 덱을 합쳐 2장이면 낸다
        g.pay_tax(0, 'draw')
        self.assertEqual((len(g.p[0].main), len(g.p[0].upper)), (0, 0))

    def test_duplicator_doubles(self):
        g = self.g
        on_field(g, '세리 - 두플리카토르', 1)
        b0 = banished(g)
        g.draw(0, 1, 'main', cause=('rule', None))
        self.assertEqual(banished(g), (b0[0] + 4, b0[1]))

    def test_delegator_opponent_pays(self):
        g = self.g
        on_field(g, '세리 - 델레가토르', 0)                             # 0의 코스트는 1이 대신 낸다
        b0 = banished(g)
        g.draw(0, 1, 'main', cause=('rule', None))
        self.assertEqual(banished(g), (b0[0], b0[1] + 2))
        keep_decks(g, 1, 1, 0)
        with self.assertRaises(GameOver) as cm: g.draw(0, 1, 'main', cause=('rule', None))
        self.assertEqual(cm.exception.winner, 0)                        # 대신 내다 모자란 쪽(1)이 패배

    def test_not_applied_when_negated_or_absent(self):
        g = self.g
        self.a.negated = True
        b0 = banished(g)
        g.draw(0, 1, 'main')
        self.assertEqual(banished(g), b0)


# ═══════════════════════ 세제 1번 (효과의 발동) ═══════════════════════
class TaxSkillActivateTest(unittest.TestCase):
    def test_both_players_pay_at_activation(self):
        g = make('세제', '데이터버그 패키지 프로그램')                   # 0의 스킬 = 세제
        r = card(g, '격투가 래빗 풋', 0, 'hand')
        b0 = banished(g)
        g.activate(0, r, eff(r, 1))
        self.assertEqual(banished(g), (b0[0] + 1, b0[1]))              # 발동할 때 1장 (사건 뒤가 아니라 코스트로)
        x = card(g, '격투가 래빗 풋', 1, 'hand')
        g.activate(1, x, eff(x, 1))
        self.assertEqual(banished(g), (b0[0] + 1, b0[1] + 1))          # 「서로가」

    def test_activation_with_empty_deck_loses(self):
        g = make('세제', '데이터버그 패키지 프로그램')
        keep_decks(g, 0, 0, 0)
        r = card(g, '격투가 래빗 풋', 0, 'hand')
        with self.assertRaises(GameOver) as cm: g.activate(0, r, eff(r, 1))
        self.assertEqual(cm.exception.winner, 1)


# ═══════════════════════ 취득세 1번 (특수소환) ═══════════════════════
class AcquisitionTaxTest(unittest.TestCase):
    def setUp(self):
        self.g = make('투기장의 규칙', '데이터버그 패키지 프로그램')
        field_card(self.g, '취득세', 0)

    def test_sure_summon_pays_at_activation(self):
        g = self.g
        d = card(g, '데이터버그 다운로드', 1, 'hand'); e = eff(d, 1)   # 메인 덱에서 「데이터버그」 몬스터를 특수소환한다
        b0 = banished(g)
        g.activate(1, d, e)
        self.assertEqual(banished(g), (b0[0], b0[1] + 2))
        g.resolve_chain()
        self.assertEqual(banished(g), (b0[0], b0[1] + 2))

    def test_other_summon_pays_right_before(self):
        g = self.g
        m = card(g, '격투가 래빗 풋', 0, 'hand')
        b0 = banished(g)
        self.assertTrue(g.special_summon(m, 0))
        self.assertEqual(banished(g), (b0[0] + 2, b0[1]))


# ═══════════════════════ AI: 스스로 지는 발동은 고르지 않는다 ═══════════════════════
class TaxRuinTest(unittest.TestCase):
    def test_ruin_veto(self):
        g = make('투기장의 규칙', '데이터버그 패키지 프로그램')
        field_card(g, '세 - 아이라리움', 1)
        r = card(g, '격투가 래빗 풋', 0, 'hand'); e = eff(r, 1)
        self.assertFalse(g.tax_ruin(0, r, e))
        keep_decks(g, 0, 1, 0)
        self.assertTrue(g.tax_ruin(0, r, e))                           # 발동할 때 2장 — 덱 1장
        self.assertEqual(C.act_score(g, r, e, 0, None, 0), VETO)       # 규칙상 발동할 수 있지만 AI는 고르지 않는다
        j = card(g, '행운의 카드 - 조커', 0, 'hand')
        self.assertFalse(g.tax_ruin(0, j, eff(j, 1)))                  # 조건부 드로우는 발동할 때 내지 않는다
        on_field(g, '세리 - 델레가토르', 0)
        self.assertFalse(g.tax_ruin(0, r, e))                          # 상대가 대신 낸다

    def test_mandatory_not_vetoed(self):
        g = make('세제', '데이터버그 패키지 프로그램')
        keep_decks(g, 0, 0, 0)
        x = card(g, '던전마스터 트랩퍼', 0, 'grave'); e = eff(x, 3)    # 강제 [유언]
        self.assertTrue(e.mandatory)
        self.assertTrue(g.tax_ruin(0, x, e))
        self.assertNotEqual(C.act_score(g, x, e, 0, None, 1), VETO)


if __name__ == '__main__':
    unittest.main()

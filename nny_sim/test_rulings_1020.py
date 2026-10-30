"""남은 재정 답변(사용자 2026-10-20, 「재정_질문_남은것_2026-10-19.pdf」 Q1 ~ Q5) 테스트 (nny_sim 폴더에서):  python -m unittest test_rulings_1020 -v
Q1 포커짐승들 족보 × 두플리카토르 — 이 카드를 뺀 나머지만 2배 / Q3 델레가토르 — 상대가 대신 낼 수 있는 모든 코스트, 낼 수 없으면 발동 불가,
덱 코스트는 덱이 음수가 되면 패배 / Q4 세제 2 · 3번 상대도 사용 · 이탈세 2번 「필드의 카드를 필드가 아닌 위치로 이동시키는 효과」
(Q2 호박옥 2 · Q5 셔플!은 현행 유지 — 기존 테스트)"""
import unittest
import cards as C
import cards4 as S
import cards8 as K
from engine import Effect, GameOver, Link
from test_new_mechanics import make, card, on_field, eff
import test_theme_poker as TP


def link_of(g, c, num, p, **ctx):
    return Link(c, eff(c, num), p, dict(ctx))


# ═══════════════════════ Q4 이탈세 2번 · 각성의 태동 — 필드에서 벗어나게 하는 효과 ═══════════════════════

import databug_fixture   # 데이터버그 카드 · 덱(카드 풀에서 보류 중 — 사용자 지시 2026-10-30)을 이 모듈 시험 동안만 넣는다


def setUpModule(): databug_fixture.install()


def tearDownModule(): databug_fixture.uninstall()

class MovesOffFieldTest(unittest.TestCase):
    def test_text_removal_of_opponent_field(self):
        g = make('세제', '데이터버그 패키지 프로그램')
        on_field(g, '세리 - 릭토르', 0)
        w = on_field(g, '데이터버그 디지털 웜', 1)
        self.assertTrue(C.moves_off_field(g, link_of(g, w, 1, 1), 0))    # 「상대 필드의 카드 1장을 파괴한다」
        self.assertTrue(C.moves_off_field(g, link_of(g, w, 2, 1), 0))    # 「필드의 카드 1장을 파괴한다」 (앞 구절의 자신 필드는 뺀다)

    def test_no_field_cards_or_search_is_not_removal(self):
        g = make('세제', '투기장의 규칙')
        w = on_field(g, '격투가 래빗 풋', 1)
        self.assertFalse(C.moves_off_field(g, link_of(g, w, 1, 1), 0))   # 자신 필드에 카드가 없다
        on_field(g, '세리 - 릭토르', 0)
        self.assertFalse(C.moves_off_field(g, link_of(g, w, 1, 1), 0))   # 덱에서 서치 · 패 버리기는 필드를 벗어나게 하지 않는다

    def test_target_reference_needs_own_field_target(self):
        g = make('세제', '세제')
        mine = on_field(g, '세리 - 릭토르', 0)
        k = on_field(g, '매수당한 킬러', 1)
        self.assertTrue(C.moves_off_field(g, link_of(g, k, 2, 1, t=mine), 0))   # 「그 카드를 파괴한다」 — 대상이 자신 필드의 카드
        other = on_field(g, '세리 - 엑삭토르', 1)
        self.assertFalse(C.moves_off_field(g, link_of(g, k, 2, 1, t=other), 0))

    def test_protection_text_is_not_removal(self):
        g = make('세제', '세제')
        on_field(g, '세리 - 릭토르', 0)
        x = card(g, '호박옥의 수호자 - 레시나', 1, 'hand')
        fake = Link(x, Effect(2, 'quick', ('field',)), 1, {})            # 2번 문장 「릴리스되지 않고, 효과로 파괴되지 않는다」 — 보호 문구
        self.assertFalse(C.moves_off_field(g, fake, 0))

    def test_departure_tax_trigger_uses_ruling(self):
        g = make('세제', '데이터버그 패키지 프로그램')
        on_field(g, '세리 - 릭토르', 0)
        t = card(g, '이탈세', 0, 'hand')
        w = on_field(g, '데이터버그 디지털 웜', 1)
        g.chain = [link_of(g, w, 1, 1)]
        self.assertTrue(eff(t, 2).cond(g, t, 0, None))
        r = on_field(g, '격투가 래빗 풋', 1)
        g.chain = [link_of(g, r, 1, 1)]
        self.assertFalse(eff(t, 2).cond(g, t, 0, None))


# ═══════════════════════ Q4 세제 2 · 3번 — 상대도 발동할 수 있다 ═══════════════════════
class TaxSkillEitherPlayerTest(unittest.TestCase):
    def test_marked_from_text(self):
        g = make('세제', '세제')
        sk = g.p[0].skill
        self.assertTrue(getattr(eff(sk, 2), 'either_player', False))
        self.assertTrue(getattr(eff(sk, 3), 'either_player', False))
        self.assertFalse(any(e.num == 1 for e in sk.effects))         # 1번은 [지속] 「서로가 … 할 때마다」 — 발동하는 효과가 아니다

    def test_opponent_activates_tax_skill(self):
        g = make('투기장의 규칙', '세제')       # 0 = 턴 플레이어(투기장), 1 = 세제 스킬
        sk = g.p[1].skill; e = eff(sk, 2)
        self.assertIn((sk, e), g.options(0, ('ignition',)))
        b0, h0 = len(g.p[0].banish), len(g.p[0].hand)
        g.act(0, sk, e); g.resolve_chain()
        self.assertGreaterEqual(len(g.p[0].banish) - b0, 9)            # 발동한 쪽(0)이 자신의 덱에서 9장 제외 (+ 세제 1번)
        self.assertEqual(len(g.p[0].hand) - h0, 2)                     # 자신의 메인 덱에서 2장 드로우
        self.assertEqual(g.p[0].opt.get(g.opt_key(sk, e)), 1)
        self.assertFalse(g.legal(0, sk, e))                            # 1턴 1번 (발동한 플레이어 기준)


# ═══════════════════════ Q3 델레가토르 — 상대가 대신 내는 코스트 ═══════════════════════
class DelegatorTest(unittest.TestCase):
    def setUp(self):
        self.g = make('세제', '데이터버그 패키지 프로그램')
        self.d = on_field(self.g, '세리 - 델레가토르', 0)

    def test_payer_is_opponent(self):
        self.assertEqual(self.g.cost_payer(0), 1)
        self.assertEqual(self.g.cost_payer(1), 1)

    def test_deck_cost_paid_by_opponent(self):
        g = self.g
        a0, b0 = len(g.p[0].banish), len(g.p[1].banish)
        S.tax_cost(g, 0, 3, '시험')
        self.assertEqual((len(g.p[0].banish) - a0, len(g.p[1].banish) - b0), (0, 3))

    def test_deck_cost_shortfall_loses(self):
        # 덱 코스트는 상대 덱이 모자라도 발동할 수 있고, 대신 지불하다 모자라면 덱이 음수 → 패배
        g = self.g
        sk = g.p[0].skill; e = eff(sk, 2)
        del g.p[1].main[2:]; g.p[1].upper.clear()
        self.assertTrue(g.transfer_ok(0, sk, e))
        with self.assertRaises(GameOver) as cm: S.tax_cost(g, 0, 9, '시험')
        self.assertEqual(cm.exception.winner, 0)

    def test_self_cost_cannot_be_paid_by_opponent(self):
        g = self.g
        x = card(g, '명계의 징벌', 0, 'grave')   # 「묘지의 이 카드를 제외하고 발동」
        self.assertFalse(g.transfer_ok(0, x, eff(x, 2)))
        g._remove(self.d); self.d.zone = 'grave'; g.p[0].grave.append(self.d)
        self.assertTrue(g.transfer_ok(0, x, eff(x, 2)))                # 델레가토르가 없으면 자신이 낸다

    def test_banish_return_cost_from_opponent_banish_zone(self):
        g = self.g
        r = on_field(g, '세리 - 릭토르', 0); e = eff(r, 2)            # [유언] 자신의 제외 존에서 3장 골라 덱으로
        g.p[1].banish.clear()
        self.assertFalse(g.transfer_ok(0, r, e))                       # 상대 제외 존에 3장이 없다 → 대신 낼 수 없음 → 발동 불가
        for _ in range(3): card(g, '데이터버그 앤트', 1, 'banish')
        self.assertTrue(g.transfer_ok(0, r, e))
        n0 = len(g.p[0].banish)
        e.cost(g, r, 0, Link(r, e, 0, {}))
        self.assertEqual((len(g.p[1].banish), len(g.p[0].banish)), (0, n0))

    def test_tax_skill_draw_check_when_transferred(self):
        g = self.g
        sk = g.p[0].skill; e = eff(sk, 2)
        del g.p[0].main[3:]                                            # 자신 메인 덱 3장 — 코스트 9장은 상대가 낸다
        self.assertTrue(e.cond(g, sk, 0, None))
        g._remove(self.d); self.d.zone = 'grave'; g.p[0].grave.append(self.d)
        self.assertFalse(e.cond(g, sk, 0, None))                       # 자신이 내면 9장 + 드로우 2장이 필요


# ═══════════════════════ Q1 포커짐승들 족보 × 두플리카토르 ═══════════════════════
class PokerDuplicatorTest(unittest.TestCase):
    def _dup(self, g, owner=1):
        TP.mon(g, '세리 - 두플리카토르', owner)                        # 「서로가」 — 상대 필드에 있어도 적용

    def test_sizes_from_text(self):
        g = TP.make()
        r = TP.mon(g, TP.RAB, 0); d = TP.mon(g, TP.DOG, 0)
        self.assertEqual(K.combo_sizes(g, r, 0, 'straight'), 3)
        self.assertEqual(K.combo_sizes(g, d, 0, 'full'), [(3, 2), (2, 3)])
        self._dup(g)
        self.assertEqual(K.combo_sizes(g, r, 0, 'straight'), 5)        # 이 카드 + 2 × 2장
        self.assertEqual(K.combo_sizes(g, d, 0, 'full'), [(5, 4), (3, 6)])
        self.assertEqual(K.combo_sizes(g, r, 0, 'pair'), 3)            # 올인 원페어 「자신을 포함하는 … 2장」
        self.assertEqual(K.combo_sizes(g, r, 0, 'triple'), 6)          # 트리플 「자신의 몬스터를 포함하는」 — 이 카드가 없으니 전체 2배

    def test_straight_needs_five_consecutive_with_duplicator(self):
        g = TP.make(); TP.filler(g, 0); up = TP.put(g, K.RABBIT_UP, 0, 'upper')
        r = TP.mon(g, TP.RAB, 0); TP.mon(g, TP.WOLF_F, 0); TP.mon(g, TP.DOG_F, 0)   # 레벨 1 · 2 · 3
        self.assertTrue(g.legal(0, r, eff(r, 2)))
        self._dup(g)
        self.assertFalse(g.legal(0, r, eff(r, 2)))                     # 두플리카토르: 연속 5장 필요
        m4 = TP.mon(g, TP.CAT_F, 0); m5 = TP.mon(g, '스트플을 원하는 시골쥐', 0)
        self.assertTrue(g.legal(0, r, eff(r, 2)))
        g.act(0, r, eff(r, 2))
        self.assertEqual(up.zone, 'm')
        self.assertTrue(m4.zone == 'grave' and m5.zone == 'grave')

    def test_full_house_doubles_other_cards(self):
        g = TP.make(); TP.filler(g, 0); TP.put(g, K.DOG_UP, 0, 'upper')
        d = TP.put(g, TP.DOG, 0, 'hand')
        for _ in range(2): TP.put(g, TP.DOG_F, 0, 'grave')          # 레벨 3: 이 카드 + 2
        for _ in range(3): TP.put(g, TP.CAT_F, 0, 'grave')          # 레벨 4: 3
        self.assertTrue(g.legal(0, d, eff(d, 2)))
        self._dup(g)
        self.assertFalse(g.legal(0, d, eff(d, 2)))                     # 3장 묶음 → 이 카드 + 2 그대로면 다른 묶음 6장 필요
        for _ in range(3): TP.put(g, TP.CAT_F, 1, 'grave')          # 레벨 4: 6장
        self.assertTrue(g.legal(0, d, eff(d, 2)))


if __name__ == '__main__':
    unittest.main()

"""2026-10-29 사용자 지시 2차 수정 테스트 (nny_sim 폴더에서):  python3 -m unittest test_play_fixes2 -v
② 같은 이름 규칙: 효과 문장이 이 카드를 직접 소환 · 패에 넣지 않으면 발동한 카드 자신도 고를 수 없다(저주인형 - 저주인형 3번 · 던전마스터 새크리파이스 2번)
③ 카드가 무효화되면 체인에 있는 그 카드의 발동한 효과도 무효(애나벨 [소환] ← 바이러스 모스키토)
④ 무효화된 카드 한 장은 이 턴 같은 번호의 효과를 다시 발동할 수 없다(다른 동명 카드는 할 수 있다)"""
import unittest
from test_play_fixes import DECKS, make, card, by_code, eff
from cards import POOL


class SameNameTest(unittest.TestCase):
    def test_cursed_doll_lastwill_cannot_pick_itself(self):
        g = make('희생제', '세제')
        doll = card(g, by_code('CRSD-007'), 0, 'main')   # 3번 처리 중: 이 카드는 이미 덱으로 돌아가 있다
        e3 = eff(doll, 3)
        self.assertFalse(getattr(e3, 'self_ok', False))
        other = card(g, by_code('CRSD-001'), 0, 'main')   # 다른 「저주인형」 몬스터
        g.src, g.src_eff = doll, e3
        try:
            self.assertFalse(g.can_special(doll, 0), '덱으로 돌아간 이 카드는 특수소환할 수 없다')
            twin = card(g, by_code('CRSD-007'), 0, 'main')
            self.assertFalse(g.can_special(twin, 0), '같은 이름의 다른 카드도 안 된다')
            self.assertTrue(g.can_special(other, 0))
        finally:
            g.src = g.src_eff = None

    def test_sacrifice_cannot_revive_itself(self):
        """새크리파이스 2번 「패의 이 카드를 버리고 발동. 묘지에서 「던전마스터」 몬스터를 1장 특수소환한다」 — 버린 이 카드는 고를 수 없다"""
        import blocks.lib as L
        g = make('던전마스터 셔플!', '세제')
        sac = card(g, by_code('DGMS-004'), 0, 'hand'); ghost = card(g, by_code('DGMS-002'), 0, 'grave')
        e2 = eff(sac, 2)
        self.assertFalse(getattr(e2, 'self_ok', False))
        k = next(b.k for b in e2.do_steps if b.name == 'special')
        self.assertTrue(g.activate(0, sac, e2))
        self.assertEqual(sac.zone, 'grave')
        g.src, g.src_eff = sac, e2
        try: cands = L.summon_cands(g, sac, 0, k)
        finally: g.src = g.src_eff = None
        self.assertIn(ghost, cands); self.assertNotIn(sac, cands)
        g.resolve_chain()
        self.assertEqual(sac.zone, 'grave'); self.assertTrue(g.on_field(ghost))

    def test_self_summon_text_still_allowed(self):
        g = make('던전마스터 셔플!', '세제')
        sin = card(g, by_code('DGMS-006'), 0, 'hand')   # 「이 카드를 특수소환한다」
        self.assertTrue(getattr(eff(sin, 1), 'self_ok', False))


class CardNegationTest(unittest.TestCase):
    def test_negating_card_negates_its_link_on_chain(self):
        g = make('희생제', '투기장의 규칙')
        ann = card(g, by_code('CRSD-004'), 0, 'm', 0); ann.faceup = True
        e1 = eff(ann, 1)
        hand0 = len(g.p[0].hand)
        link = g.activate(0, ann, e1)
        self.assertIsNotNone(link)
        g.negate_card(ann, src=None, perma=True)   # 바이러스 모스키토 장착처럼 「그 몬스터의 효과를 무효로 한다」
        g.resolve_chain()
        self.assertTrue(link.negated)
        self.assertEqual(len(g.p[0].hand), hand0, '무효화된 카드의 [소환] 효과는 처리되지 않는다(서치 없음)')
        self.assertTrue(any('무효라 처리하지 않음' in e['m'] for e in g.log))

    def test_virus_mosquito_chain(self):
        g = make('희생제', '투기장의 규칙')
        ann = card(g, by_code('CRSD-004'), 0, 'm', 0); ann.faceup = True
        mos = card(g, by_code('COMN-002'), 1, 'hand')
        link = g.activate(0, ann, eff(ann, 1))
        hand0 = len(g.p[0].hand)
        self.assertTrue(g.activate(1, mos, eff(mos, 1), ev=link))
        g.resolve_chain()
        self.assertIn(mos, ann.equips)
        self.assertTrue(link.negated)
        self.assertEqual(len(g.p[0].hand), hand0)


class NegatedReuseTest(unittest.TestCase):
    def test_negated_card_cannot_reactivate_same_effect_but_twin_can(self):
        g = make('던전마스터 셔플!', '세제')
        a = card(g, by_code('DGMS-006'), 0, 'hand'); b = card(g, by_code('DGMS-006'), 0, 'hand')
        opp = card(g, by_code('COMN-005'), 1, 'm', 0); opp.faceup = True   # 파괴할 카드
        e1 = eff(a, 1)
        link = g.activate(0, a, e1)
        g.negate(link, by=opp)
        g.resolve_chain()
        self.assertEqual(a.zone, 'hand')
        self.assertFalse(g.legal(0, a, e1), '무효화된 그 카드는 이 턴 1번 효과를 다시 발동할 수 없다')
        self.assertTrue(g.legal(0, b, eff(b, 1)), '패의 다른 동명 카드는 발동할 수 있다(무효화된 발동은 횟수를 쓰지 않음 §6-5)')
        g.turn += 1
        self.assertTrue(g.legal(0, a, e1), '다음 턴에는 다시 발동할 수 있다')


class ComboOptionsTest(unittest.TestCase):
    """① 사람 자리가 고를 족보 재료 후보(cards8.plan_options) — AI의 최선(cards8.plan)이 들어 있고, 모든 후보가 그 족보의 매수 · 조건을 지킨다"""
    def test_straight_options(self):
        import cards8
        import test_theme_poker as TP
        g = TP.make(); TP.filler(g, 0); TP.put(g, cards8.RABBIT_UP, 0, 'upper')
        r = TP.mon(g, TP.RAB, 0); TP.mon(g, TP.WOLF_F, 0); TP.put(g, TP.DOG, 0, 'hand'); TP.mon(g, TP.WOLF, 0)
        opts = cards8.plan_options(g, r, 0, 'straight')
        best = cards8.plan(g, r, 0, 'straight', fresh=True)
        self.assertTrue(opts)
        self.assertIn(sorted(m.card.uid for m in best[1]), [sorted(m.card.uid for m in sel) for _, sel in opts])
        for _, sel in opts:
            lv = sorted(m.lv for m in sel)
            self.assertEqual(len(sel), 3); self.assertIn(r, [m.card for m in sel])
            self.assertEqual(lv, list(range(lv[0], lv[0] + 3)), '연속되는 레벨 3장')


if __name__ == '__main__':
    unittest.main()

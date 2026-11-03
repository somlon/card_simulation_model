"""재정질문/002 답변(세창 2026-11-01, 디스코드) 테스트 (nny_sim 폴더에서):  python3 -m unittest test_rulings_1101b -v
효과를 부여하는 효과(A22 — build.do_grant · [지속] 부여 — build.cont_granted_effect)로 부여받은 효과의 번호는
고정값(base)이 아니라 받는 카드의 그때까지 효과 번호 최댓값 + 1이어야 한다(동적 계산, ② 채택).
수정 전 코드(고정 base)로는 두 테스트 모두 실패했다(FGTR-007은 31, PKBS-016은 21/22로 나와야 했음)."""
import unittest
import test_theme_fighter as TF
from cards import Impl, POOL
from engine import Card


class GrantedEffectNumberIsDynamicTest(unittest.TestCase):
    def test_runtime_grant_numbers_from_recipients_own_max(self):
        """FGTR-007(격투가 세레모니)이 전투승 몬스터에게 효과를 부여(A22, build.do_grant, stack=True) —
        번호는 받는 카드(TIGER)의 그때까지 효과 번호 최댓값 + 1부터 부여마다 하나씩이어야 한다."""
        g = TF.make(ai=TF.Yes)
        t = TF.mon(g, TF.TIGER, 0); o = TF.mon(g, '솔루나 시아', 1)
        own_max = max(e.num for e in t.effects)
        c1 = TF.spell(g, TF.CER, 0, faceup=False); c1.set_turn = 1
        TF.win(g, t, o); TF.run(g)
        self.assertTrue(any(e.num == own_max + 1 for e in t.effects))
        # 중첩(stack) — 두 번째 부여는 그 다음 번호
        g.turn += 2; g.turn_player = 0; g.p[0].opt = {}
        c2 = TF.spell(g, TF.CER, 0, faceup=False); c2.set_turn = 1
        o2 = TF.mon(g, '솔루나 시엘', 1)
        g.events = []; TF.win(g, t, o2); TF.run(g)
        self.assertTrue(any(e.num == own_max + 2 for e in t.effects))

    def test_cont_grant_numbers_from_recipients_own_max(self):
        """PKBS-016이 「포커짐승들」 카드군 전체에 [지속]으로 부여하는 두 효과(2-a·2-b, build.cont_grant → attach) —
        번호는 고정값(21·22)이 아니라 받는 카드의 그때까지 효과 번호 최댓값 + 1, + 2여야 한다 — 그래서 자기
        효과 번호 개수가 다른 두 「포커짐승들」 카드(PKBS-001: 2장, PKBS-005: 3장)는 부여받는 번호도 서로 다르다."""
        def attach(code):
            d = next(x for x in POOL.values() if x.get('code') == code)
            c = Card(d, 0); Impl.attach(c); return c

        few = attach('PKBS-001')   # 자기 효과 2장(num 2·3) — 부여는 4·5여야 함
        many = attach('PKBS-005')  # 자기 효과 3장(num 2·3·4) — 부여는 5·6여야 함
        own_few = sorted(e.num for e in few.effects)[:-2]
        own_many = sorted(e.num for e in many.effects)[:-2]
        self.assertLess(len(own_few), len(own_many))
        self.assertEqual(sorted(e.num for e in few.effects)[-2:], [max(own_few) + 1, max(own_few) + 2])
        self.assertEqual(sorted(e.num for e in many.effects)[-2:], [max(own_many) + 1, max(own_many) + 2])
        self.assertNotEqual(sorted(e.num for e in few.effects)[-2:], sorted(e.num for e in many.effects)[-2:])


if __name__ == '__main__':
    unittest.main()

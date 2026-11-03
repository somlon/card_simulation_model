"""재정질문/001 답변(세창 2026-11-01, 디스코드) 테스트 (nny_sim 폴더에서):  python3 -m unittest test_rulings_1101c -v
「시아 아츠 - 성광난무」(SLNA-016 1번) 코스트(자신 필드의 「시아」 몬스터를 패로 되돌림)의 부수효과(장착 대상 이탈
— 상대 소유 「바이러스 모스키토」가 묘지로, engine._remove의 장착 카드 일반 규칙)로 유일한 대상(상대 필드의 그
장착 카드)이 사라지는 경우 — ② 채택(대상은 코스트 지불 전에 확정돼야 한다): 발동 전체(이미 치른 코스트 포함)를
취소하지 않고, 대상만 불발로 처리해야 한다.
수정 전 코드로는 cost()가 코스트(패로 되돌림)를 이미 치른 뒤 pick이 대상 없음으로 False를 돌려줘 발동 전체가
'취소'로 기록됐다 — 그런데 실제로는 시아가 패로 돌아간 상태가 그대로 남아(코스트가 롤백되지 않음) 기록과 실제
상태가 어긋났다(이 거짓 취소 자체도 버그)."""
import unittest
from test_new_mechanics import make, card, on_field, eff


class CostSideEffectRemovesOnlyTargetTest(unittest.TestCase):
    def _game(self):
        g = make('솔루나 아츠', '세제')
        for c in g.all_field(): g._remove(c)
        g.p[0].hand.clear()
        return g

    def test_activation_commits_cost_and_fizzles_target_instead_of_cancelling(self):
        g = self._game()
        sia = on_field(g, '솔루나 시아', 0)
        moskito = card(g, '바이러스 모스키토', 1, None)
        g.place_spell(moskito, 1, True)
        moskito.flags['stay'] = True; moskito.equip_to = sia; sia.equips.append(moskito)
        self.assertEqual(g.field_cards(1), [moskito])   # 상대(1) 필드에 지금은 모스키토 1장 — 유일한 대상
        a1 = card(g, '시아 아츠 - 성광난무', 0, 'hand')
        n0 = len(g.log)
        link = g.activate(0, a1, eff(a1, 1))
        msgs = [e['m'] for e in g.log[n0:]]
        self.assertIsNotNone(link, '코스트(패로 되돌림)는 이미 정당하게 치러졌으니 발동 자체가 취소되면 안 된다')
        self.assertFalse(any('발동 취소' in m for m in msgs), msgs)
        self.assertIn(sia, g.p[0].hand)   # 코스트는 그대로 적용됨 — 시아는 패로 돌아갔다
        self.assertEqual(g.field_cards(1), [])          # 모스키토는 장착 대상 이탈로 묘지로 갔다(일반 규칙, 버그와 무관)
        self.assertEqual(g.p[0].grave, [])               # 대상이 없어 파괴 처리는 아무 일도 하지 않았다(불발)
        g.resolve_chain()   # 체인 처리까지 끝까지 돌려도 오류 없이 끝나야 한다


if __name__ == '__main__':
    unittest.main()
